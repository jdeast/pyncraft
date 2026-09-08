"""The archive has holes in it, and the maths that fills them has to be right.

Most columns in the NASA Exoplanet Archive are empty for most planets, because
it is a catalogue of measurements and nobody measures everything. Three
standard relations fill the gaps, all ported from EXOZIPPy rather than imported
from it -- https://github.com/jdeast/EXOZIPPy -- and all three are the kind of
thing that gives a plausible wrong answer if a constant is mistyped.

So they are checked against bodies whose real values are known: the planets of
this solar system, and the handful of exoplanets whose numbers are famous.

No network. Everything here is arithmetic.
"""
import datetime
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

exo = pytest.importorskip("exoplanets")


# ── Kepler's third law ─────────────────────────────────────────────────────

@pytest.mark.parametrize("name,period_d,mstar,a_au", [
    ("Earth",       365.25,   1.0,    1.0),
    ("Mercury",      87.969,  1.0,    0.387098),
    ("Jupiter",    4332.59,   1.0,    5.2044),
    ("Neptune",   60182.0,    1.0,   30.07),
    ("TRAPPIST-1 b",  1.510826, 0.0898, 0.01154),
    ("TRAPPIST-1 h", 18.772866, 0.0898, 0.06189),
])
def test_kepler_matches_reality(name, period_d, mstar, a_au):
    """In solar units a^3 = M P^2, so there is no constant to get wrong."""
    got = exo.kepler_a_au(period_d, mstar)
    assert got == pytest.approx(a_au, rel=0.002), name


def test_kepler_needs_a_period_and_a_mass():
    with pytest.raises(exo.InsufficientData):
        exo.kepler_a_au(None, 1.0)
    with pytest.raises(exo.InsufficientData):
        exo.kepler_a_au(365.25, None)


def test_planet_mass_barely_matters_but_is_included():
    """Including the planet's mass must change the answer, but only just."""
    bare = exo.kepler_a_au(365.25, 1.0)
    with_earth = exo.kepler_a_au(365.25, 1.0, 1.0)
    assert with_earth > bare
    assert with_earth == pytest.approx(bare, rel=1e-5)


# ── Chen & Kipping ─────────────────────────────────────────────────────────

def test_chen_is_continuous_at_every_break():
    """The segment normalisations chain, so the curve must not jump."""
    for m in exo.CHEN_MASS_BREAKS:
        below = exo.chen_radius(m * (1 - 1e-9))
        above = exo.chen_radius(m * (1 + 1e-9))
        assert below == pytest.approx(above, rel=1e-6), m


def test_chen_puts_earth_at_one_earth_radius():
    """The Terran segment is normalised to 1, so this is exact by construction."""
    assert exo.chen_radius(1.0) == pytest.approx(1.0, rel=1e-9)


@pytest.mark.parametrize("name,mass_earth,radius_earth,tol", [
    ("Mars",     0.107,  0.532, 0.15),
    ("Venus",    0.815,  0.949, 0.15),
    ("Neptune", 17.15,   3.86,  0.20),
    ("Jupiter", 317.8,  11.21,  0.30),
])
def test_chen_is_in_the_right_neighbourhood(name, mass_earth, radius_earth, tol):
    """It is a population fit with real scatter, not a formula for one planet.

    Chen & Kipping quote 4% scatter for Terran worlds and 15% for Neptunian,
    and the Jovian segment is nearly flat because it is fitted across a
    population containing inflated hot Jupiters. So the tolerances here are
    loose on purpose: tightening them would be testing a claim the relation
    does not make. This is a fallback for planets with no measured radius, and
    the code says so wherever it uses one.
    """
    assert exo.chen_radius(mass_earth) == pytest.approx(radius_earth, rel=tol), name


def test_chen_is_monotonic_where_it_should_be():
    """Radius rises with mass everywhere except the Jovian shelf."""
    masses = np.logspace(-2, 2, 60)          # up to 100 Earth masses
    radii = [exo.chen_radius(m) for m in masses]
    assert all(b > a for a, b in zip(radii, radii[1:]))


def test_chen_rejects_a_nonsense_mass():
    with pytest.raises(exo.InsufficientData):
        exo.chen_radius(0.0)
    with pytest.raises(exo.InsufficientData):
        exo.chen_radius(-3.0)


# ── choosing where a number comes from ─────────────────────────────────────

STAR = {"radius_sun": 0.1192, "mass_sun": 0.0898}


def test_a_over_rstar_is_preferred_over_the_archive_value():
    """a/R* is the transit observable, so it wins when both are present."""
    pl = {"a_over_rstar": 20.843, "a_au": 0.9999, "period_d": 1.5108,
          "mass_earth": 1.374}
    a, how = exo.resolve_orbit(pl, STAR)
    assert how == "a/R* x R*"
    assert a == pytest.approx(0.01154, rel=0.01)


def test_orbit_falls_back_to_the_archive_then_to_kepler():
    a, how = exo.resolve_orbit({"a_au": 0.05, "period_d": 1.5}, STAR)
    assert (a, how) == (0.05, "archive")

    a, how = exo.resolve_orbit({"period_d": 1.510826}, STAR)
    assert how == "Kepler from P"
    assert a == pytest.approx(0.01154, rel=0.002)


def test_orbit_gives_up_loudly_when_it_must():
    with pytest.raises(exo.InsufficientData):
        exo.resolve_orbit({}, {"radius_sun": 1.0})


def test_radius_prefers_measurement_then_ratio_then_mass():
    assert exo.resolve_radius({"radius_earth": 1.1}, STAR) == (1.1, "archive")

    r, how = exo.resolve_radius({"r_over_rstar": 0.08590}, STAR)
    assert how == "Rp/R* x R*"
    assert r == pytest.approx(1.117, rel=0.02)

    r, how = exo.resolve_radius({"mass_earth": 1.374}, STAR)
    assert how == "Chen & Kipping from M"
    assert r == pytest.approx(exo.chen_radius(1.374))

    with pytest.raises(exo.InsufficientData):
        exo.resolve_radius({}, STAR)


# ── what a planet is made of ───────────────────────────────────────────────

def test_a_dense_super_earth_is_rock_not_a_small_gas_world():
    """55 Cnc e: 1.88 Earth radii and 6.66 g/cm3, at 1958 K. Rock, molten."""
    mats, kind = exo.planet_materials(1.875, 1958.0, 6.66)
    assert kind == "molten rock"
    assert mats[0] == "MAGMA_BLOCK"


def test_a_dense_giant_is_still_a_giant():
    """55 Cnc d: 13 Earth radii at 3.08 g/cm3. Massive gas giants are dense.

    This is the case that radius-then-density gets backwards, and it built a
    thirteen-Earth-radius ball of ice before it was fixed.
    """
    mats, kind = exo.planet_materials(13.0, 105.0, 3.08)
    assert kind == "gas giant"


def test_the_trappist_habitable_zone_comes_out_green():
    """e, f and g are the three in the habitable zone, and nothing says so
    in the code -- it falls out of the equilibrium temperatures."""
    green = {}
    for letter, radius, eqt in [("b", 1.116, 397.6), ("c", 1.097, 339.7),
                                ("d", 0.788, 286.2), ("e", 0.920, 249.7),
                                ("f", 1.045, 217.7), ("g", 1.129, 197.3),
                                ("h", 0.755, 171.7)]:
        mats, kind = exo.planet_materials(radius, eqt, None)
        green[letter] = mats[0] == "GRASS_BLOCK"
    assert green["e"] and green["f"] and green["g"]
    assert not green["b"] and not green["c"] and not green["h"]


def test_no_radius_at_all_is_survivable():
    mats, kind = exo.planet_materials(None, None, None)
    assert kind == "unknown" and mats == ["STONE"]


# ── colour ─────────────────────────────────────────────────────────────────

def test_hotter_stars_are_bluer():
    """Whatever else the fit does, red must fall and blue must rise."""
    temps = [2000, 3000, 4000, 5000, 6000, 8000, 12000, 30000]
    ratios = []
    for t in temps:
        r, g, b = exo.blackbody_rgb(t)
        ratios.append(b / max(r, 1))
    assert all(b >= a for a, b in zip(ratios, ratios[1:]))


def test_a_cool_dwarf_glows_orange_and_the_sun_does_not():
    assert exo.star_material(2566.0) == "SHROOMLIGHT"
    r, g, b = exo.blackbody_rgb(5772.0)
    assert r > 240 and g > 230 and b > 200          # the Sun is white
    assert exo.star_material(5772.0) != "SHROOMLIGHT"


def test_every_star_gets_a_block_that_actually_glows():
    for t in range(1000, 40001, 500):
        assert exo.star_material(float(t)) in exo.STAR_BLOCKS


def test_spectral_types_land_on_the_right_letters():
    for teff, letter in [(2566, "M"), (4500, "K"), (5772, "G"),
                         (6500, "F"), (8500, "A"), (15000, "B"), (35000, "O")]:
        assert exo.spectral_type(teff) == letter


# ── geometry ───────────────────────────────────────────────────────────────

def test_small_planets_are_solid_and_big_stars_are_shells():
    small, _ = exo.sphere(2.5, ["STONE"])
    assert small[small.shape[0] // 2, small.shape[1] // 2,
                small.shape[2] // 2] != 0, "a small planet should be solid"

    big, _ = exo.sphere(30.0, ["GLOWSTONE"])
    assert big[big.shape[0] // 2, big.shape[1] // 2, big.shape[2] // 2] == 0
    solid_cost = 4.0 / 3.0 * np.pi * 30.0 ** 3
    assert int((big != 0).sum()) < solid_cost / 2.0


def test_a_shell_has_no_holes_in_it():
    """Looking straight through a star would rather give the game away."""
    for r in (8.0, 20.0, 34.5, 60.0):
        world, _ = exo.sphere(r, ["GLOWSTONE"])
        n = world.shape[0]
        c = n // 2
        # Every ray through the middle along each axis must hit something.
        assert world[:, c, c].sum() > 0
        assert world[c, :, c].sum() > 0
        assert world[c, c, :].sum() > 0
        # And the poles specifically, which is where a thin shell tears.
        assert world[c, 0:2, c].sum() > 0 or world[c, 1:3, c].sum() > 0


def test_banding_gives_every_material_a_share():
    mats = ["ORANGE_TERRACOTTA", "WHITE_TERRACOTTA", "LIGHT_GRAY_TERRACOTTA"]
    world, palette = exo.sphere(12.0, mats, banded=True)
    assert palette == mats
    for i in range(len(mats)):
        assert int((world == i + 1).sum()) > 0


def test_mottling_is_mostly_the_first_material_and_repeatable():
    mats = ["GRASS_BLOCK", "STONE"]
    a, _ = exo.sphere(6.0, mats, banded=False)
    b, _ = exo.sphere(6.0, mats, banded=False)
    assert np.array_equal(a, b), "same planet, same look, every time"
    first = int((a == 1).sum())
    second = int((a == 2).sum())
    assert first > second > 0


# ── inclination ────────────────────────────────────────────────────────────

def test_inclination_defaults_to_edge_on():
    """Missing inclination means 90 degrees, and says it was assumed.

    A planet in this catalogue with no published inclination is nearly always
    one that was found by transiting, which means it is very close to edge-on
    already. Assuming 90 is both the best guess and the one that puts every
    planet at the same height, which is what makes the build navigable.
    """
    i, how = exo.resolve_inclination({})
    assert (i, how) == (90.0, "assumed")
    i, how = exo.resolve_inclination({"incl_deg": None})
    assert (i, how) == (90.0, "assumed")


def test_a_published_inclination_is_used():
    i, how = exo.resolve_inclination({"incl_deg": 89.73})
    assert (i, how) == (89.73, "archive")


def test_edge_on_puts_every_planet_at_the_same_height():
    """cos(90 degrees) is zero, so the whole system lies in one plane."""
    assert math.cos(math.radians(90.0)) == pytest.approx(0.0, abs=1e-15)
    for a_blocks in (100.0, 3856.0, 140000.0):
        assert a_blocks * math.cos(math.radians(90.0)) == pytest.approx(0.0, abs=1e-9)


def test_a_tilted_orbit_lifts_the_planet_off_the_plane():
    """TRAPPIST-1 h: 3856 blocks out at 89.81 degrees is about 13 blocks up."""
    dy = 3856.0 * math.cos(math.radians(89.81))
    assert 10.0 < dy < 16.0
    # And the sign of the offset follows which side of 90 the inclination is.
    assert 100.0 * math.cos(math.radians(89.0)) > 0
    assert 100.0 * math.cos(math.radians(91.0)) < 0


# ── Kepler's equation and orbital phase ────────────────────────────────────

TC, PERIOD = 2457322.514193, 1.510826          # TRAPPIST-1 b


def _wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def test_the_solver_inverts_its_own_equation():
    """Whatever E comes back, E - e sin E must be the M that went in.

    Compared as angles rather than as numbers: the solver folds M into
    -pi..pi, so at the ends of the range it hands back -pi where +pi went in.
    Those are the same direction and the difference is not an error.
    """
    for e in (0.0, 0.05, 0.3, 0.7, 0.9):
        for m in np.linspace(-math.pi, math.pi, 33):
            E = exo.solve_kepler(m, e)
            assert _wrap(E - e * math.sin(E) - m) == pytest.approx(0.0, abs=1e-9)


def test_true_and_eccentric_anomaly_are_inverses():
    for e in (0.0, 0.2, 0.6, 0.9):
        for f in np.linspace(-math.pi + 0.01, math.pi - 0.01, 21):
            assert _wrap(exo.true_from_ecc(exo.ecc_from_true(f, e), e) - f) \
                == pytest.approx(0.0, abs=1e-9)


def test_at_mid_transit_the_planet_is_where_it_should_be():
    """f = pi/2 - omega is the definition of transit, so it must hold at tc."""
    for w in (0.0, 45.0, -90.0, 200.0, 336.86):
        for e in (0.0, 0.2):
            f = exo.true_anomaly_at(TC, TC, PERIOD, e, w)
            assert _wrap(f - (math.pi / 2.0 - math.radians(w))) \
                == pytest.approx(0.0, abs=1e-9), (w, e)


def test_a_planet_comes_back_after_exactly_one_period():
    for e, w in ((0.0, 90.0), (0.3, 40.0), (0.62, 200.0)):
        a = exo.true_anomaly_at(TC + 1234.5, TC, PERIOD, e, w)
        b = exo.true_anomaly_at(TC + 1234.5 + PERIOD, TC, PERIOD, e, w)
        assert _wrap(a - b) == pytest.approx(0.0, abs=1e-8)


def test_omega_cannot_matter_on_a_circular_orbit():
    """The reason a made-up omega is harmless where the archive has none.

    Two thirds of planets have no published argument of periastron, and for a
    circular orbit there is no periastron for it to describe -- it is a phase
    offset and nothing more. The convention is to put periastron at the transit
    so that tc = tp, which is omega = -90 degrees, and that is what this
    assumes.

    It cannot change the picture, and not just as a matter of taste: the true
    anomaly at transit is pi/2 - omega and the position angle is omega + f, so
    omega cancels identically. Every value below must give the same point.
    """
    ref = None
    for w in (-90.0, 0.0, 37.0, 90.0, 250.0, 336.86):
        f = exo.true_anomaly_at(TC + 500.0, TC, PERIOD, 0.0, w)
        x, z = exo.orbit_xz(1.0, 0.0, w, f)
        if ref is None:
            ref = (x, z)
        assert x == pytest.approx(ref[0], abs=1e-9), w
        assert z == pytest.approx(ref[1], abs=1e-9), w


def test_the_assumed_omega_is_the_conventional_one():
    assert exo.OMEGA_WHEN_UNKNOWN == -90.0
    e, w, how = exo.resolve_shape({})
    assert (e, w) == (0.0, 270.0)          # -90 mod 360
    assert "e=0 assumed" in how
    # With a real eccentricity and no omega it is a guess, and says so.
    e, w, how = exo.resolve_shape({"ecc": 0.3})
    assert w == 270.0 and "omega assumed" in how
    # And a fully measured orbit claims nothing.
    e, w, how = exo.resolve_shape({"ecc": 0.00622, "omega_deg": 336.86})
    assert how == "archive"


def test_no_transit_midpoint_means_the_phase_is_unknown():
    with pytest.raises(exo.InsufficientData):
        exo.true_anomaly_at(2460000.0, None, PERIOD, 0.0, 90.0)


def test_an_eccentric_orbit_is_off_centre():
    """Star at the focus, not the middle: r at periastron and apastron differ."""
    peri = exo.orbit_xz(100.0, 0.4, 0.0, 0.0)
    apo = exo.orbit_xz(100.0, 0.4, 0.0, math.pi)
    assert math.hypot(*peri) == pytest.approx(60.0, rel=1e-9)     # a(1-e)
    assert math.hypot(*apo) == pytest.approx(140.0, rel=1e-9)     # a(1+e)


def test_orbit_dots_lie_on_the_orbit():
    pts = exo.orbit_ring(120.0, 0.3, 40.0, 89.8, step=5.0)
    assert len(pts) > 40
    for x, y, z in pts:
        r = math.hypot(x, z)
        assert 120.0 * (1 - 0.3) - 3 <= r <= 120.0 * (1 + 0.3) + 3
    circ = exo.orbit_ring(50.0, 0.0, 0.0, 90.0, step=5.0)
    for x, y, z in circ:
        assert math.hypot(x, z) == pytest.approx(50.0, abs=1.5)
        assert y == 0                       # edge-on: no tilt at all


def _gaps(pts):
    """Distances between neighbouring dots, right round the closed loop.

    Ordered by angle about the focus, which works because an ellipse is
    star-shaped about its focus: every ray from it crosses the curve once.
    """
    pts = sorted(pts, key=lambda p: math.atan2(p[2], p[0]))
    return [math.dist(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def test_orbit_dots_are_evenly_spaced_including_the_seam():
    """The bug this fixes: two dots almost on top of each other at the join.

    Walking round and dropping a dot every `step` blocks leaves the remainder
    at the point where the walk closes, so one gap is whatever is left over --
    which was sometimes almost nothing, and looked like a blot on an otherwise
    even ring. Dividing the perimeter into a whole number of equal pieces
    spaces them evenly everywhere, at a spacing near `step` rather than
    exactly it, which nobody can see and everybody prefers.
    """
    for a, e in ((56.0, 0.006), (300.0, 0.006), (120.0, 0.4), (77.0, 0.0)):
        gaps = _gaps(exo.orbit_ring(a, e, 40.0, 89.8, step=5.0))
        assert min(gaps) > 3.0, (a, e, min(gaps))       # no doubled-up dots
        assert max(gaps) - min(gaps) < 2.5, (a, e, min(gaps), max(gaps))
        assert 4.0 < sum(gaps) / len(gaps) < 6.0, (a, e)


def test_the_spacing_asked_for_is_roughly_what_you_get():
    for step in (3.0, 5.0, 8.0):
        gaps = _gaps(exo.orbit_ring(150.0, 0.05, 0.0, 90.0, step=step))
        assert sum(gaps) / len(gaps) == pytest.approx(step, rel=0.15), step


# ── sign text ──────────────────────────────────────────────────────────────

def test_sign_lines_are_measured_in_pixels_not_characters():
    """Minecraft's font is not fixed width, so counting characters cuts text.

    Sixteen narrow letters fit where twelve wide ones do not, and a line
    trimmed to fifteen characters was sometimes still too long for the sign
    and sometimes half empty.
    """
    for line in ("TRAPPIST-1 b temperate rock", "5968 180 5954",
                 "a=0.0115 AU", "1.12 Re  e=0.006", "iiiiiiiiiiiiiiiiiiiiii"):
        out = exo.fit(line)
        assert sum(exo.CHAR_PX.get(c, 6) for c in out) <= exo.SIGN_PX, line
    # A line of thin letters keeps more of them than a line of wide ones.
    assert len(exo.fit("i" * 60)) > len(exo.fit("m" * 60))
    # Anything that already fits is untouched.
    assert exo.fit("a=0.0115 AU") == "a=0.0115 AU"


def test_semi_major_axis_is_shown_in_au_with_useful_digits():
    """It was being printed in blocks, which says nothing about the planet."""
    assert exo._au(0.01154) == "0.0115"
    assert exo._au(0.3849) == "0.385"
    assert exo._au(5.204) == "5.20"
    assert exo._au(30.07) == "30.1"


def test_julian_date_matches_a_known_epoch():
    """J2000.0 is JD 2451545.0 at 2000-01-01 12:00 UTC, by definition."""
    j2000 = datetime.datetime(2000, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert exo.julian_date(j2000) == pytest.approx(2451545.0, abs=1e-6)


# ── shape ──────────────────────────────────────────────────────────────────

def test_a_planet_is_the_same_size_in_every_direction():
    """The complaint that started this: a planet that looked stretched.

    It was not the geometry -- it was two builds at slightly different heights
    left on top of each other, which is what the build manifest now prevents.
    The geometry should still be checked, because a lopsided ball is exactly
    the sort of thing nobody would question.
    """
    for r in (1.0, 1.5, 2.2, 3.0, 8.0, 20.0):
        world, _ = exo.sphere(r, ["STONE"])
        filled = world != 0
        widths = [int(filled.any(axis=(1, 2)).sum()),
                  int(filled.any(axis=(0, 2)).sum()),
                  int(filled.any(axis=(0, 1)).sum())]
        assert widths[0] == widths[1] == widths[2], (r, widths)
        # and symmetric under reflection in each axis
        assert np.array_equal(filled, filled[::-1, :, :])
        assert np.array_equal(filled, filled[:, ::-1, :])
        assert np.array_equal(filled, filled[:, :, ::-1])


def test_a_small_planet_is_a_ball_and_not_a_cube():
    """Half a block of slack made a radius of 1.478 into a solid 3x3x3.

    Every cell of a 3x3x3 is within 2.0 of the middle, so `d <= r + 0.5` kept
    the corners and the planet came out square. A quarter of a block drops
    them. This is the whole reason the slack is 0.25.
    """
    for r in (1.4, 1.478, 1.5, 2.0, 2.5, 3.0):
        world, _ = exo.sphere(r, ["STONE"])
        n = world.shape[0]
        for x in (0, n - 1):
            for y in (0, n - 1):
                for z in (0, n - 1):
                    assert world[x, y, z] == 0, "corner kept at r=%s" % r
        assert int((world != 0).sum()) < n ** 3


def test_planets_stay_in_size_order():
    """Whatever the rounding does, a bigger planet must not come out smaller."""
    sizes = [int((exo.sphere(r, ["STONE"])[0] != 0).sum())
             for r in (1.5, 2.0, 2.5, 3.0, 4.0)]
    assert all(b >= a for a, b in zip(sizes, sizes[1:])), sizes
