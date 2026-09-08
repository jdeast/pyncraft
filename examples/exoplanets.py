#!/usr/bin/env python3
"""Build a real planetary system, floating in the sky, where it is right now.

    python exoplanets.py                          # TRAPPIST-1, the default
    python exoplanets.py --system "Kepler-90"
    python exoplanets.py --date 2026-07-04        # where they were that day
    python exoplanets.py --line                   # strung out, as a diagram
    python exoplanets.py --true-scale             # honest, and enormous
    python exoplanets.py --list                   # systems worth a look

The numbers come from the NASA Exoplanet Archive, live, over its TAP service.
Nothing here is typed in from a textbook: change the archive and this changes.

WHERE THE PLANETS ACTUALLY ARE

The archive publishes, for most planets, a transit midpoint, a period, an
eccentricity and an argument of periastron. That is enough to say where a
planet is at any moment: get the true anomaly at transit from omega, turn it
into a mean anomaly, advance that to the date you want, and solve Kepler's
equation to get back to a position. So this builds the system as it stands
today, with each orbit outlined so you can see the shape it is moving along.

--line gives the older arrangement instead -- every planet on the +X axis at
its own distance -- which is easier to read as a diagram and tells you nothing
about where anything actually is.

THE SCALE PROBLEM, AND WHAT IS ACTUALLY DONE ABOUT IT

A planetary system cannot be drawn to scale and also be looked at. In
TRAPPIST-1 -- the most compact system known, so the kindest possible case --
the outermost orbit is nearly two thousand times the radius of the smallest
planet. Drawn at one block per planet radius the system is 1,925 blocks
across, and a server running view-distance 10 shows you 160 blocks of it. You
would be standing inside eight percent of a thing you could never see.

So there are two rulers, and this is loud about it:

  - ORBITS are scaled to fit --span blocks, which is what you can fly around.
  - BODIES are scaled so the smallest planet is --planet-blocks in radius,
    which is what makes them visible at all.

The ratio between the two is printed and goes on the sign beside the star.
Every orrery ever built does this; the dishonest ones just do not say so.
--true-scale collapses both to one number and is worth doing once, so that the
number stops being an abstraction.

Chasing round planets is what blows the scale up, and it is not worth it. At
any span you can actually look at, a planet is a few blocks, and a few blocks
is a lump however carefully it is carved. A legible system of small lumps
beats a beautiful sphere you have to fly for a minute to get away from.
"""
import argparse
import csv
import datetime
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import numpy as np
except ImportError:
    sys.exit("This needs numpy: pip install numpy")

import connect

ARCHIVE = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
USER_AGENT = "pyncraft exoplanets (https://github.com/jdeast/pyncraft)"

R_EARTH_KM = 6371.0
R_SUN_KM = 695700.0
AU_KM = 1.495978707e8
PC_LY = 3.261563777
DAYS_PER_YEAR = 365.25
M_EARTH_PER_M_SUN = 332946.0
JD_UNIX_EPOCH = 2440587.5

COLUMNS = ("pl_name,hostname,pl_rade,pl_bmasse,pl_dens,pl_orbsmax,pl_orbper,"
           "pl_eqt,pl_ratdor,pl_ratror,pl_orbincl,pl_orbeccen,pl_orblper,"
           "pl_tranmid,st_teff,st_rad,st_mass,sy_dist,sy_pnum")

# Blocks that give off light, with roughly the colour they read as in game.
# Stars are matched against this and nothing else: a star that does not glow is
# not a star. The gap at the blue end is real -- Minecraft has no blue light
# source -- so everything hotter than about 8000 K comes out the same white.
STAR_BLOCKS = {
    "MAGMA_BLOCK":           (142,  70,  35),
    "SHROOMLIGHT":           (240, 146,  70),
    "OCHRE_FROGLIGHT":       (247, 226, 152),
    "GLOWSTONE":             (255, 203, 111),
    "PEARLESCENT_FROGLIGHT": (247, 217, 232),
    "SEA_LANTERN":           (206, 233, 226),
    "VERDANT_FROGLIGHT":     (215, 240, 190),
}

# Rocky worlds, coldest to hottest, by equilibrium temperature in kelvin.
ROCK_BY_TEMP = (
    (180.0, ["PACKED_ICE", "BLUE_ICE"]),
    (320.0, ["GRASS_BLOCK", "STONE"]),
    # Red sandstone, not red sand: these hang in the sky with nothing under
    # them, and a gravity-affected block up there is one block update away
    # from raining the planet onto the ground.
    (600.0, ["TERRACOTTA", "RED_SANDSTONE"]),
    (1200.0, ["BLACKSTONE", "BASALT"]),
    (float("inf"), ["MAGMA_BLOCK", "NETHERRACK"]),
)

ORBIT_BLOCK = "WHITE_CONCRETE"

# Names the archive files under something else. Kepler-90 is the famous one:
# it has eight planets, more than any system but ours, and it is in the tables
# as KOI-351 because the Kepler Object of Interest number came first.
ALIASES = {
    "kepler-90": "KOI-351",
}


# ── making text fit on a sign ──────────────────────────────────────────────
#
# Minecraft's font is not fixed width, so "how many characters" is the wrong
# question and cutting at fifteen of them sometimes cuts in the middle of a
# word and sometimes leaves half the sign empty. These are the pixel widths of
# the default font -- nearly everything is six, and a handful of thin
# characters are less -- and a sign line is about ninety pixels wide.
CHAR_PX = {" ": 4, "!": 2, ".": 2, ",": 2, ":": 2, ";": 2, "'": 2, "`": 2,
           "|": 2, "i": 2, "l": 3, "t": 4, "I": 4, "[": 4, "]": 4, '"': 4,
           "(": 5, ")": 5, "{": 5, "}": 5, "<": 5, ">": 5, "f": 5, "k": 5,
           "*": 5}
SIGN_PX = 88


def fit(text, px=SIGN_PX):
    """As much of text as will actually render on one line of a sign."""
    out, used = [], 0
    for ch in str(text):
        w = CHAR_PX.get(ch, 6)
        if used + w > px:
            break
        out.append(ch)
        used += w
    return "".join(out)


# What each kind of planet is called when there is no room for the full thing.
SHORT_KIND = {
    "gas giant": "gas giant", "ice giant": "ice giant",
    "sub-Neptune": "sub-Nept", "low density, likely icy": "icy",
    "frozen rock": "frozen", "temperate rock": "temperate",
    "hot rock": "hot", "baked rock": "baked", "molten rock": "molten",
    "unknown": "?", "rock": "rock",
}


def _au(a):
    """A semi-major axis in AU, with enough digits to be useful and no more.

    TRAPPIST-1 runs from 0.0115 to 0.0619 AU and 55 Cnc d is 5.5, so a fixed
    number of decimal places is either useless at one end or absurd at the
    other.
    """
    a = float(a)
    if a >= 10.0:
        return "%.1f" % a
    if a >= 1.0:
        return "%.2f" % a
    if a >= 0.1:
        return "%.3f" % a
    return "%.4f" % a


def spectral_type(teff):
    """The one letter astronomers put in front of everything."""
    for limit, letter in ((30000, "O"), (10000, "B"), (7500, "A"),
                          (6000, "F"), (5200, "G"), (3700, "K")):
        if teff >= limit:
            return letter
    return "M"


# ── filling the archive's gaps ─────────────────────────────────────────────
#
# The archive is a catalogue of measurements, not of planets, so a column is
# empty whenever nobody measured that particular thing. Of 6,360 planets it
# has a transit midpoint for 80%, an eccentricity for 83%, an inclination for
# 76% and an argument of periastron for only 33%. Refusing to draw a planet
# because one cell is blank would throw most of them away, and every blank
# here has a standard way to be filled that astronomers already trust.
#
# The maths is ported from EXOZIPPy, which is where it is done properly:
# https://github.com/jdeast/EXOZIPPy  (components/planet/physics.py)
# Ported rather than imported: EXOZIPPy pulls in PyTensor and a fitting stack,
# which is an enormous dependency for a handful of formulae.

# Chen & Kipping 2017, ApJ 834, 17, Table 2 -- a continuous broken power law
# giving radius from mass in Earth units. The segment normalisations chain, so
# neighbouring segments meet exactly at the break masses rather than jumping.
CHEN_MASS_BREAKS = (2.04, 131.58079, 26644.8321)          # Earth masses
CHEN_EXPONENTS = (0.279, 0.589, -0.044, 0.881)
_T1, _T2, _T3 = CHEN_MASS_BREAKS
_S1, _S2, _S3, _S4 = CHEN_EXPONENTS
_N1 = 1.0
_N2 = _T1 ** (_S1 - _S2)
_N3 = _N2 * _T2 ** (_S2 - _S3)
_N4 = _N3 * _T3 ** (_S3 - _S4)

# What to assume for the argument of periastron when the archive has none,
# which is two planets in every three.
#
# When the orbit is circular omega is not a physical angle at all -- there is
# no periastron for it to point at -- it is purely a phase offset, and the
# convention is to place periastron at the transit so that tc = tp. That is
# omega = -90 degrees.
#
# It is worth knowing that this choice cannot affect anything at e = 0, and
# not merely as a matter of taste: the true anomaly at transit is pi/2 - omega,
# and the position angle is omega + f, so the two cancel identically and the
# planet ends up in the same place whatever is assumed. (There is a test for
# exactly that.) It matters only for a planet with a measured eccentricity and
# no measured omega, where any choice is a guess and this one is at least the
# conventional guess.
OMEGA_WHEN_UNKNOWN = -90.0


class InsufficientData(Exception):
    """Not enough in the archive to place or size this planet."""


def chen_radius(mass_earth):
    """Radius in Earth radii from mass in Earth masses (Chen & Kipping 2017)."""
    m = float(mass_earth)
    if m <= 0:
        raise InsufficientData("mass is not positive")
    if m <= _T1:
        return _N1 * m ** _S1
    if m <= _T2:
        return _N2 * m ** _S2
    if m <= _T3:
        return _N3 * m ** _S3
    return _N4 * m ** _S4


def kepler_a_au(period_days, star_mass_sun, planet_mass_earth=None):
    """Semi-major axis from the period, by Kepler's third law.

    In solar units the law is just a^3 = M P^2, with a in AU, M in solar masses
    and P in years, so there is no gravitational constant to get wrong. The
    planet's own mass belongs in the total and almost never matters: for
    TRAPPIST-1 b it moves the answer by two parts in a hundred thousand.
    """
    if not period_days or not star_mass_sun:
        raise InsufficientData("no period or no stellar mass")
    m_total = float(star_mass_sun)
    if planet_mass_earth:
        m_total += float(planet_mass_earth) / M_EARTH_PER_M_SUN
    years = float(period_days) / DAYS_PER_YEAR
    return (m_total * years * years) ** (1.0 / 3.0)


def resolve_orbit(pl, star):
    """Semi-major axis in AU, and how we know it.

    a/R* is the transit observable -- it comes straight out of the shape of the
    light curve and needs to know neither how big the star is nor how far away
    -- so where it exists it is the thing to trust.
    """
    ratdor, rstar = pl.get("a_over_rstar"), star.get("radius_sun")
    if ratdor and rstar:
        return ratdor * rstar * R_SUN_KM / AU_KM, "a/R* x R*"
    if pl.get("a_au"):
        return pl["a_au"], "archive"
    a = kepler_a_au(pl.get("period_d"), star.get("mass_sun"), pl.get("mass_earth"))
    return a, "Kepler from P"


def resolve_radius(pl, star):
    """Planet radius in Earth radii, and how we know it."""
    if pl.get("radius_earth"):
        return pl["radius_earth"], "archive"
    ratror, rstar = pl.get("r_over_rstar"), star.get("radius_sun")
    if ratror and rstar:
        return ratror * rstar * R_SUN_KM / R_EARTH_KM, "Rp/R* x R*"
    if pl.get("mass_earth"):
        return chen_radius(pl["mass_earth"]), "Chen & Kipping from M"
    raise InsufficientData("no radius, no Rp/R*, and no mass")


def resolve_inclination(pl):
    """Orbital inclination in degrees, and how we know it.

    90 degrees is edge-on, which is the orientation that makes a planet cross
    in front of its star, which is how most of them were found in the first
    place. So 90 is both the commonest real value and the right thing to assume
    when the column is empty: a transiting planet whose inclination was never
    published is transiting, therefore near 90.
    """
    i = pl.get("incl_deg")
    return (90.0, "assumed") if i is None else (i, "archive")


def resolve_shape(pl):
    """Eccentricity and argument of periastron, with the usual defaults."""
    e = pl.get("ecc")
    w = pl.get("omega_deg")
    notes = []
    if e is None:
        e, notes = 0.0, notes + ["e=0 assumed"]
    if w is None:
        w = OMEGA_WHEN_UNKNOWN
        # Only worth mentioning when it can actually change the answer.
        if e:
            notes.append("omega assumed")
    return (max(0.0, min(0.95, float(e))), float(w) % 360.0,
            ", ".join(notes) if notes else "archive")


# ── where a planet is right now ────────────────────────────────────────────

def solve_kepler(mean_anomaly, ecc, tol=1e-12, iters=80):
    """Kepler's equation M = E - e sin E, solved for E by Newton's method.

    The one equation in celestial mechanics with no closed-form solution, and
    the reason orbital positions are computed rather than looked up. Newton
    converges in a handful of steps at the eccentricities in this catalogue;
    starting from pi rather than M keeps it stable if a very eccentric planet
    ever turns up.
    """
    m = (float(mean_anomaly) + math.pi) % (2.0 * math.pi) - math.pi
    e = float(ecc)
    E = m if e < 0.8 else math.pi
    for _ in range(iters):
        denom = 1.0 - e * math.cos(E)
        if denom == 0.0:
            break
        step = (E - e * math.sin(E) - m) / denom
        E -= step
        if abs(step) < tol:
            break
    return E


def true_from_ecc(E, e):
    return 2.0 * math.atan2(math.sqrt(1.0 + e) * math.sin(E / 2.0),
                            math.sqrt(1.0 - e) * math.cos(E / 2.0))


def ecc_from_true(f, e):
    return 2.0 * math.atan2(math.sqrt(1.0 - e) * math.sin(f / 2.0),
                            math.sqrt(1.0 + e) * math.cos(f / 2.0))


def true_anomaly_at(jd, tc, period_d, ecc, omega_deg):
    """Where the planet is in its orbit at Julian date jd.

    The chain: at mid-transit the planet is directly between us and the star,
    which fixes the true anomaly at f = pi/2 - omega. Convert that to a mean
    anomaly, which is the one angle that advances uniformly with time, walk it
    forward to the date wanted, and solve Kepler's equation to get back to a
    real position.

    Without a transit midpoint there is no zero point for the clock, so the
    phase is unknowable and this says so rather than quietly picking one.
    """
    if not tc or not period_d:
        raise InsufficientData("no transit midpoint, so no orbital phase")
    f_tc = math.pi / 2.0 - math.radians(omega_deg)
    E_tc = ecc_from_true(f_tc, ecc)
    m_tc = E_tc - ecc * math.sin(E_tc)
    m = m_tc + 2.0 * math.pi * (float(jd) - float(tc)) / float(period_d)
    return true_from_ecc(solve_kepler(m, ecc), ecc)


def orbit_xz(a, ecc, omega_deg, f):
    """Position in the orbital plane, star at the focus, in whatever a is in."""
    w = math.radians(omega_deg)
    r = a * (1.0 - ecc * ecc) / (1.0 + ecc * math.cos(f))
    return r * math.cos(w + f), r * math.sin(w + f)


def julian_date(when=None):
    """Julian date from a datetime, or now.

    Close enough: the archive's transit midpoints are barycentric and this is
    UTC, which differ by up to about eight minutes of light travel time across
    Earth's orbit. On a planet with a period of days that is a fraction of a
    degree, and this is a picture, not an ephemeris.
    """
    when = when or datetime.datetime.now(datetime.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when.timestamp() / 86400.0 + JD_UNIX_EPOCH


# ── the archive ────────────────────────────────────────────────────────────

def fetch_system(host, cache_dir, refresh=False):
    """Every known planet of one star, newest archive values, cached on disk.

    pscomppars is the composite table: one row per planet, each parameter taken
    from the best measurement of it rather than from a single paper. That is
    what you want for drawing a picture and is not what you want for doing
    statistics, which is worth knowing before quoting any of it.
    """
    host = ALIASES.get(host.strip().lower(), host.strip())
    safe = "".join(c if c.isalnum() else "_" for c in host)
    path = os.path.join(cache_dir, "exo4_%s.csv" % safe)
    if os.path.exists(path) and not refresh:
        text = io.open(path, encoding="utf-8").read()
    else:
        query = ("select %s from pscomppars where hostname='%s' order by pl_orbsmax"
                 % (COLUMNS, host.replace("'", "''")))
        url = ARCHIVE + "?query=" + urllib.parse.quote(query) + "&format=csv"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            text = urllib.request.urlopen(req, timeout=120).read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise SystemExit("The archive said no (%s). Check the host name "
                             "spelling with --list." % e)
        os.makedirs(cache_dir, exist_ok=True)
        io.open(path, "w", encoding="utf-8", newline="").write(text)

    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        # Exact match failed. Rather than telling somebody their spelling is
        # wrong, go and look: the archive is happy to do a LIKE, and the answer
        # is nearly always a name that is almost the one they typed.
        near = _search(host)
        msg = "No planets found around %r." % host
        if near:
            msg += "\nDid you mean:\n" + "\n".join(
                "    --system \"%s\"   (%s planets)" % (h, p) for h, p in near[:8])
        else:
            msg += "\n--list shows systems with five or more planets."
        raise SystemExit(msg)

    def num(row, key):
        try:
            return float(row[key])
        except (TypeError, ValueError, KeyError):
            return None

    planets = []
    for row in rows:
        planets.append({
            "name": row["pl_name"],
            "radius_earth": num(row, "pl_rade"),
            "mass_earth": num(row, "pl_bmasse"),
            "density": num(row, "pl_dens"),
            "a_au": num(row, "pl_orbsmax"),
            "period_d": num(row, "pl_orbper"),
            "eqt_k": num(row, "pl_eqt"),
            "a_over_rstar": num(row, "pl_ratdor"),
            "r_over_rstar": num(row, "pl_ratror"),
            "incl_deg": num(row, "pl_orbincl"),
            "ecc": num(row, "pl_orbeccen"),
            "omega_deg": num(row, "pl_orblper"),
            "tc": num(row, "pl_tranmid"),
        })
    star = {
        "name": rows[0]["hostname"],
        "teff": num(rows[0], "st_teff"),
        "radius_sun": num(rows[0], "st_rad"),
        "mass_sun": num(rows[0], "st_mass"),
        "dist_pc": num(rows[0], "sy_dist"),
        "n_planets": num(rows[0], "sy_pnum"),
    }

    usable, missing = [], []
    for pl in planets:
        try:
            pl["radius_earth"], pl["radius_from"] = resolve_radius(pl, star)
            pl["a_au"], pl["a_from"] = resolve_orbit(pl, star)
        except InsufficientData as e:
            missing.append("%s (%s)" % (pl["name"], e))
            continue
        pl["incl_deg"], pl["incl_from"] = resolve_inclination(pl)
        pl["ecc"], pl["omega_deg"], pl["shape_from"] = resolve_shape(pl)
        usable.append(pl)
    usable.sort(key=lambda p: p["a_au"])
    return star, usable, missing


def _search(host):
    """Host names containing what was asked for, most planets first."""
    stem = host.replace("'", "").strip()
    query = ("select distinct hostname,sy_pnum from pscomppars "
             "where upper(hostname) like upper('%%%s%%') order by sy_pnum desc" % stem)
    url = ARCHIVE + "?query=" + urllib.parse.quote(query) + "&format=csv"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        rows = list(csv.DictReader(io.StringIO(
            urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))))
    except Exception:
        return []
    return [(r["hostname"], r["sy_pnum"]) for r in rows]


def list_systems(limit=30):
    """Systems with the most known planets, which are the ones worth building."""
    query = ("select distinct hostname,sy_pnum,st_teff,st_rad,sy_dist "
             "from pscomppars where sy_pnum >= 5 order by sy_pnum desc, sy_dist asc")
    url = ARCHIVE + "?query=" + urllib.parse.quote(query) + "&format=csv"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    rows = list(csv.DictReader(io.StringIO(
        urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))))
    print("%-22s %7s %8s %9s  %s" % ("host", "planets", "Teff K", "dist ly", "type"))
    for row in rows[:limit]:
        try:
            teff = float(row["st_teff"])
            dist = float(row["sy_dist"]) * PC_LY
        except (TypeError, ValueError):
            teff, dist = 0.0, 0.0
        print("%-22s %7s %8.0f %9.1f  %s"
              % (row["hostname"], row["sy_pnum"], teff, dist,
                 spectral_type(teff) if teff else "?"))
    print()
    print("Use the host name exactly:  --system \"%s\"" % rows[0]["hostname"])


# ── colour ─────────────────────────────────────────────────────────────────

def blackbody_rgb(teff):
    """Colour of a blackbody at teff, as 0-255 sRGB.

    Tanner Helland's fit to the Planck curve, accurate enough between 1000 and
    40000 K that nothing at block resolution could tell the difference.
    """
    t = max(1000.0, min(40000.0, float(teff))) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        r = 329.698727446 * (t - 60.0) ** -0.1332047592
        g = 288.1221695283 * (t - 60.0) ** -0.0755148492
    if t >= 66:
        b = 255.0
    elif t <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10.0) - 305.0447927307
    return tuple(int(max(0.0, min(255.0, v))) for v in (r, g, b))


def nearest(rgb, palette):
    r, g, b = rgb
    return min(palette, key=lambda k: (r - palette[k][0]) ** 2
               + (g - palette[k][1]) ** 2 + (b - palette[k][2]) ** 2)


def star_material(teff):
    return nearest(blackbody_rgb(teff), STAR_BLOCKS)


def planet_materials(radius_earth, eqt_k, density):
    """What a planet is probably made of, from what the archive actually knows.

    Radius is the strong signal: above about four Earth radii nothing is known
    that is not mostly gas, because rock that big would have swept up an
    atmosphere it could not lose. Below about 1.6 nearly everything is rock.
    """
    if radius_earth is None:
        return ["STONE"], "unknown"

    # Density settles it wherever it is known -- but only at the small end. A
    # massive gas giant is dense too: 55 Cnc d is 4 Jupiter masses and
    # 3.1 g/cm3, because that much gas under its own weight compresses. So
    # above about four Earth radii the radius has the final say. Nothing made
    # of rock gets that big.
    dense = None if density is None else density >= 3.0

    if radius_earth >= 6.0:
        return ["ORANGE_TERRACOTTA", "WHITE_TERRACOTTA",
                "LIGHT_GRAY_TERRACOTTA", "BROWN_TERRACOTTA"], "gas giant"
    if radius_earth >= 4.0:
        return ["CYAN_TERRACOTTA", "LIGHT_BLUE_TERRACOTTA"], "ice giant"
    if radius_earth >= 1.7 and dense is not True:
        return ["PACKED_ICE", "LIGHT_BLUE_CONCRETE"], "sub-Neptune"
    if dense is False and radius_earth > 1.2:
        return ["PACKED_ICE", "BLUE_ICE"], "low density, likely icy"

    t = eqt_k if eqt_k is not None else 255.0
    for limit, mats in ROCK_BY_TEMP:
        if t < limit:
            kind = {"PACKED_ICE": "frozen rock", "GRASS_BLOCK": "temperate rock",
                    "TERRACOTTA": "hot rock", "BLACKSTONE": "baked rock",
                    "MAGMA_BLOCK": "molten rock"}[mats[0]]
            return mats, kind
    return ["STONE"], "rock"


# ── geometry ───────────────────────────────────────────────────────────────

def sphere(radius, materials, banded=False):
    """A ball of the given radius, labelled for buildVoxels.

    Hollow above four blocks of radius: a solid ball of radius 35 is 180,000
    blocks and a shell of the same is 15,000, and from outside -- which is the
    only place you can be -- they are identical. Below that the shell starts to
    tear at the poles, so small bodies stay solid; they cost nothing anyway.

    More than one material is either banded by latitude, which is what a gas
    giant looks like, or mottled, which is what a rock looks like. Banding a
    rocky planet gives a ball that is grass on top and stone underneath, like a
    badly iced cake, and nothing in the sky looks like that.
    """
    r = max(float(radius), 0.5)
    n = int(math.ceil(r)) * 2 + 1
    c = n // 2
    ax = np.arange(n) - c
    x, y, z = np.meshgrid(ax, ax, ax, indexing="ij")
    d = np.sqrt(x * x + y * y + z * z)

    # Half a block of slack turns a radius of 1.5 into a solid 3x3x3 cube,
    # because every cell of the cube is within 2.0 of the middle. A quarter
    # keeps the corners off and the ball reads as a ball at every size small
    # enough to matter, which is all of them: at a span you can look at, no
    # planet is more than a few blocks across.
    solid = d <= r + 0.25
    if r > 4.0:
        solid &= d >= r - max(1.5, r * 0.05)

    world = np.zeros((n, n, n), dtype=np.int32)
    if len(materials) == 1:
        world[solid] = 1
        return world, list(materials)

    if banded:
        edges = np.linspace(-r - 0.5, r + 0.5, len(materials) + 1)
        for i in range(len(materials)):
            world[solid & (y >= edges[i]) & (y < edges[i + 1])] = i + 1
    else:
        rng = np.random.default_rng(int(r * 1000) + len(materials))
        pick = rng.random(world.shape)
        world[solid] = 1
        world[solid & (pick > 0.72)] = 2
        for i in range(2, len(materials)):
            world[solid & (pick > 0.72 + 0.1 * (i - 1))] = i + 1
    world[solid & (world == 0)] = 1
    return world, list(materials)


def orbit_ring(a_blocks, ecc, omega_deg, incl_deg, step=5.0):
    """Points tracing one orbit, evenly spaced all the way round.

    Two things have to be right and neither is free.

    Stepping in true anomaly bunches the dots up at periastron, where the
    planet moves fastest and the ellipse curves hardest, and spreads them at
    apastron. So this measures real arc length along the curve instead.

    And the curve is closed, so the gap between the last dot and the first is
    a gap like any other. Walking round dropping a dot every `step` blocks
    leaves whatever is left over at the seam, which showed up as two dots
    almost on top of each other at one point of every orbit. Instead: measure
    the whole perimeter, divide it by the nearest whole number of dots to the
    spacing asked for, and place them at exactly that spacing. The result is
    even everywhere including the join, at a spacing near `step` rather than
    exactly it -- which is the right trade, since nobody can see five blocks
    against five and a quarter, and everybody sees a double dot.
    """
    tilt = math.sin(math.radians(90.0 - incl_deg))

    # A fine walk round the ellipse, and the running distance along it.
    fine = 4096
    curve, arc = [], [0.0]
    for k in range(fine + 1):
        x, z = orbit_xz(a_blocks, ecc, omega_deg, 2.0 * math.pi * k / fine)
        curve.append((x, -z * tilt, z))
        if k:
            arc.append(arc[-1] + math.dist(curve[-1], curve[-2]))
    perimeter = arc[-1]
    if perimeter <= 0:
        return []

    count = max(8, int(round(perimeter / max(step, 0.5))))
    pts, j = set(), 0
    for k in range(count):
        target = perimeter * k / count
        while j < len(arc) - 2 and arc[j + 1] < target:
            j += 1
        run = arc[j + 1] - arc[j]
        t = 0.0 if run <= 0 else (target - arc[j]) / run
        pts.add(tuple(int(round(curve[j][d] + (curve[j + 1][d] - curve[j][d]) * t))
                      for d in range(3)))
    return sorted(pts)


# ── building ───────────────────────────────────────────────────────────────

def plan(star, planets, planet_blocks, span, true_scale, jd):
    """The two rulers, and where every body goes.

    Bodies and orbits are measured with different ones, and this is the single
    place that is decided. Returns (km per block for bodies, km per block for
    orbits, star radius in blocks).
    """
    body_km = min(p["radius_earth"] * R_EARTH_KM for p in planets) / float(planet_blocks)
    widest = max(p["a_au"] for p in planets) * AU_KM
    orbit_km = body_km if true_scale else widest / float(span)
    star_r = (star.get("radius_sun") or 0.1) * R_SUN_KM / body_km

    for p in planets:
        p["r_blocks"] = p["radius_earth"] * R_EARTH_KM / body_km
        p["a_blocks"] = p["a_au"] * AU_KM / orbit_km
        p["materials"], p["kind"] = planet_materials(
            p["radius_earth"], p["eqt_k"], p["density"])
        try:
            f = true_anomaly_at(jd, p.get("tc"), p["period_d"],
                                p["ecc"], p["omega_deg"])
            p["phase_from"] = "tc + Kepler"
        except InsufficientData:
            f = 0.0
            p["phase_from"] = "unknown: at periastron"
        p["true_anomaly"] = f
        x, z = orbit_xz(p["a_blocks"], p["ecc"], p["omega_deg"], f)
        tilt = math.sin(math.radians(90.0 - p["incl_deg"]))
        p["pos"] = (x, -z * tilt, z)
    return body_km, orbit_km, star_r


def build_body(mc, world, palette, centre, pace):
    nx, ny, nz = world.shape
    origin = (int(centre[0] - nx // 2), int(centre[1] - ny // 2),
              int(centre[2] - nz // 2))
    mc.buildVoxels(world, palette=palette, origin=origin, blocks_per_second=pace)
    return (origin[0], origin[1], origin[2],
            origin[0] + nx - 1, origin[1] + ny - 1, origin[2] + nz - 1)


# ── remembering what was built, so it can be unbuilt ───────────────────────
#
# Every build writes down the boxes it filled, and the next build of the same
# system clears them first. Without this, changing anything that moves a body
# leaves the old one behind: adding inclination shifted the planets three
# blocks up, and what you got was two spheres one above the other, ten blocks
# tall and seven wide. It looked exactly like an elongated planet, which is a
# thing close-in planets really are, so it was entirely believable and
# completely wrong.

def manifest_path(data_dir, host):
    safe = "".join(c if c.isalnum() else "_" for c in host)
    return os.path.join(data_dir, "exo_build_%s.json" % safe)


def clear_previous(mc, data_dir, host, pace):
    path = manifest_path(data_dir, host)
    if not os.path.exists(path):
        return 0
    try:
        boxes = json.load(io.open(path, encoding="utf-8"))["boxes"]
    except (ValueError, KeyError):
        return 0
    for x1, y1, z1, x2, y2, z2 in boxes:
        mc.setBlocks(x1, y1, z1, x2, y2, z2, "AIR")
    return len(boxes)


def save_manifest(data_dir, host, boxes):
    os.makedirs(data_dir, exist_ok=True)
    io.open(manifest_path(data_dir, host), "w", encoding="utf-8").write(
        json.dumps({"boxes": [list(map(int, b)) for b in boxes]}, indent=1))


def signpost(mc, star, planets, sx, sy, sz, star_r, body_km, orbit_km, when):
    """A row of signs by the star with every planet's coordinates on it.

    Without this you fly off into an empty sky hoping you have not drifted,
    which is atmospheric the first time and tiresome the second.
    """
    z = int(sz - max(star_r, 6) - 14)
    boxes = []

    # Reading order.
    #
    # These signs face north, so you read them standing to the north of them
    # looking south -- and facing south, east is on your LEFT. So a row built
    # from west to east reads backwards, star last. Laying it out from east to
    # west puts the star on the reader's left and the planets in order after
    # it, which is how anybody would expect to find them.
    order = [None] + list(planets)              # None is the star
    x_for = {}
    right = int(sx + 6)
    for i, item in enumerate(order):
        x_for[i] = right - i * 3
    x_lo, x_hi = min(x_for.values()) - 2, max(x_for.values()) + 2

    mc.setBlocks(x_lo, sy - 2, z - 2, x_hi, sy - 2, z + 2, "POLISHED_ANDESITE")
    boxes.append((x_lo, sy - 2, z - 2, x_hi, sy + 1, z + 2))

    exagg = orbit_km / body_km
    for i, item in enumerate(order):
        x = x_for[i]
        mc.setBlock(x, sy - 1, z, "POLISHED_BLACKSTONE")
        if item is None:
            lines = (star["name"],
                     "%d %d %d" % (sx, sy, sz),
                     when,
                     "true scale" if exagg < 1.01 else "bodies x%.0f" % exagg)
        else:
            px, py, pz = item["pos"]
            short = item["name"].replace(star["name"], "").strip() or item["name"]
            lines = ("%s %s" % (short, SHORT_KIND.get(item["kind"], item["kind"])),
                     "%d %d %d" % (int(sx + round(px)), int(sy + round(py)),
                                   int(sz + round(pz))),
                     # a in AU, which is what a semi-major axis is measured in.
                     # It was showing the value in blocks, which is a fact
                     # about this build and not about the planet.
                     "a=%s AU" % _au(item["a_au"]),
                     "%.2f Re  e=%.3f" % (item["radius_earth"], item["ecc"]))
        mc.setSign(x, sy, z, "OAK_SIGN", "NORTH", *[fit(v) for v in lines])
    return z, boxes


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    connect.add_arguments(p)
    p.add_argument("--system", default="TRAPPIST-1",
                   help="host star name, exactly as the archive spells it")
    p.add_argument("--span", type=float, default=300.0,
                   help="blocks from the star to the outermost planet -- the "
                        "size of the whole build, so make it something you can "
                        "fly round (default 300)")
    p.add_argument("--planet-blocks", type=float, default=1.5,
                   help="radius of the SMALLEST planet, in blocks. Below about "
                        "1.4 a ball has no corners left to round off and comes "
                        "out a cross (default 1.5)")
    p.add_argument("--true-scale", action="store_true",
                   help="one ruler for bodies and orbits: honest, and usually "
                        "thousands of blocks across")
    p.add_argument("--line", action="store_true",
                   help="ignore the real positions and string the planets along "
                        "+X, which reads better as a diagram")
    p.add_argument("--date", help="YYYY-MM-DD to place the planets (default today)")
    p.add_argument("--no-orbits", action="store_true", help="skip the orbit outlines")
    p.add_argument("--orbit-step", type=float, default=5.0,
                   help="blocks between the dots of an orbit. The spacing used "
                        "is the nearest one that divides the orbit evenly, so "
                        "there is no double dot at the seam (default 5)")
    p.add_argument("--at", nargs=3, type=int, metavar=("X", "Y", "Z"),
                   default=[6000, 180, 6000],
                   help="where the star goes (default 6000 180 6000)")
    p.add_argument("--no-signs", action="store_true", help="skip the labels")
    p.add_argument("--keep-old", action="store_true",
                   help="do not clear the previous build of this system first")
    p.add_argument("--clear", action="store_true",
                   help="remove the previous build of this system and stop")
    p.add_argument("--pace", type=int, default=12000, help="blocks per second")
    p.add_argument("--budget", type=int, default=800000,
                   help="refuse to build more blocks than this (default 800000)")
    p.add_argument("--force", action="store_true", help="build anyway")
    p.add_argument("--refresh", action="store_true", help="re-query the archive")
    p.add_argument("--list", action="store_true", help="list systems and stop")
    p.add_argument("--tour", action="store_true", help="fly past every planet")
    p.add_argument("--dry-run", action="store_true", help="print the plan only")
    args = p.parse_args()

    if args.list:
        list_systems()
        return

    when = (datetime.datetime.strptime(args.date, "%Y-%m-%d").replace(
        tzinfo=datetime.timezone.utc) if args.date
        else datetime.datetime.now(datetime.timezone.utc))
    jd = julian_date(when)

    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    if args.clear:
        mc = connect.connect(args.host, args.port, args.player)
        host = ALIASES.get(args.system.strip().lower(), args.system.strip())
        n = clear_previous(mc, data, host, args.pace)
        print("cleared %d boxes from the previous build of %s" % (n, host))
        return

    star, planets, missing = fetch_system(args.system, data, args.refresh)
    body_km, orbit_km, star_r = plan(star, planets, args.planet_blocks,
                                     args.span, args.true_scale, jd)
    star_block = star_material(star["teff"] or 5000.0)
    rgb = blackbody_rgb(star["teff"] or 5000.0)

    if args.line:
        for pl in planets:
            pl["pos"] = (pl["a_blocks"],
                         pl["a_blocks"] * math.cos(math.radians(pl["incl_deg"])),
                         0.0)

    print("%s -- %d planets returned, %d of them drawable"
          % (star["name"], len(planets) + len(missing), len(planets)))
    if missing:
        print("  not enough data to draw, so left out:")
        for m in missing:
            print("      %s" % m)
    listed = int(star["n_planets"] or 0)
    if listed and listed != len(planets) + len(missing):
        print("  (the archive counts %d in the system; the rest are filed under"
              % listed)
        print("   a companion star's name, which is its own hostname)")
    print("  %s star, %.0f K, %.3f solar radii, %.1f light years away"
          % (spectral_type(star["teff"] or 0), star["teff"] or 0,
             star["radius_sun"] or 0, (star["dist_pc"] or 0) * PC_LY))
    print("  colour %s -> %s" % (rgb, star_block))
    print()
    print("  as it stands on %s (JD %.3f)" % (when.strftime("%Y-%m-%d"), jd))
    print("  bodies:  1 block = %8.0f km" % body_km)
    print("  orbits:  1 block = %8.0f km" % orbit_km)
    exagg = orbit_km / body_km
    if exagg < 1.01:
        print("  one ruler for both -- true scale")
    else:
        print("  so the bodies are drawn %.0f times too big for the orbits."
              % exagg)
        print("  Every orrery does this; --true-scale does not.")
    print("  star radius %.1f blocks (%.0f across)" % (star_r, star_r * 2))

    inner = min(q["a_blocks"] for q in planets)
    if star_r > inner * 0.8:
        print("  WARNING: the star is nearly as big as the innermost orbit.")
        print("  Try --planet-blocks %.2f, or a larger --span."
              % (args.planet_blocks * inner * 0.5 / max(star_r, 1e-9)))
    print()

    print("  %-16s %8s %8s %7s %7s %7s  %-18s %s"
          % ("planet", "a (AU)", "R/Earth", "a blks", "e", "incl",
             "made of", "phase"))
    for pl in planets:
        print("  %-16s %8s %8.2f %7.0f %7.4f %7.2f  %-18s %s"
              % (pl["name"], _au(pl["a_au"]), pl["radius_earth"],
                 pl["a_blocks"], pl["ecc"], pl["incl_deg"], pl["kind"],
                 pl["phase_from"]))

    total = int((sphere(star_r, [star_block])[0] != 0).sum())
    for pl in planets:
        total += int((sphere(pl["r_blocks"], pl["materials"],
                             banded="giant" in pl["kind"])[0] != 0).sum())
    rings = 0
    if not args.no_orbits and not args.line:
        for pl in planets:
            rings += len(orbit_ring(pl["a_blocks"], pl["ecc"], pl["omega_deg"],
                                    pl["incl_deg"], args.orbit_step))
    print()
    print("  %d blocks of bodies + %d of orbit outline = %d, about %.0f seconds"
          % (total, rings, total + rings, (total + rings) / 12000.0))
    print("  the outermost planet is %.0f blocks from the star"
          % max(q["a_blocks"] for q in planets))

    if total + rings > args.budget and not args.force:
        fits = args.planet_blocks * (float(args.budget) / (total + rings)) ** 0.5
        print()
        print("  That is over the budget of %d." % args.budget)
        print("  --planet-blocks %.2f would fit; --force builds it anyway."
              % max(0.3, fits * 0.95))
        return

    if args.dry_run:
        return

    mc = connect.connect(args.host, args.port, args.player)
    sx, sy, sz = args.at
    boxes = []

    if not args.tour:
        if not args.keep_old:
            n = clear_previous(mc, data, star["name"], args.pace)
            if n:
                print()
                print("cleared %d boxes from the previous build" % n)

        world, palette = sphere(star_r, [star_block])
        print()
        print("building the star: %d blocks of %s"
              % (int((world != 0).sum()), star_block))
        mc.postToChat("%s as it stands on %s. Bodies and orbits are on "
                      "different scales -- see the sign."
                      % (star["name"], when.strftime("%d %b %Y")))
        boxes.append(build_body(mc, world, palette, (sx, sy, sz), args.pace))

        if not args.no_orbits and not args.line:
            for pl in planets:
                pts = orbit_ring(pl["a_blocks"], pl["ecc"], pl["omega_deg"],
                                 pl["incl_deg"], args.orbit_step)
                # origin=(0,0,0) because these are already absolute. Left
                # out, buildVoxels defaults the origin to the PLAYER, and the
                # whole orbit is drawn that far from where it belongs -- which
                # here put it at y=360, above the world, so it vanished
                # silently and the ring simply was not there.
                mc.buildVoxels([(sx + x, sy + y, sz + z) for x, y, z in pts],
                               block=ORBIT_BLOCK, origin=(0, 0, 0),
                               blocks_per_second=args.pace)
                xs = [x for x, _, _ in pts]
                ys = [y for _, y, _ in pts]
                zs = [z for _, _, z in pts]
                boxes.append((sx + min(xs), sy + min(ys), sz + min(zs),
                              sx + max(xs), sy + max(ys), sz + max(zs)))
            print("  orbit outlines: %d blocks" % rings)

        for pl in planets:
            world, palette = sphere(pl["r_blocks"], pl["materials"],
                                    banded="giant" in pl["kind"])
            px, py, pz = pl["pos"]
            at = (int(sx + round(px)), int(sy + round(py)), int(sz + round(pz)))
            print("  %-16s %5d blocks at %d,%d,%d  (%s)"
                  % (pl["name"], int((world != 0).sum()), at[0], at[1], at[2],
                     pl["materials"][0]))
            boxes.append(build_body(mc, world, palette, at, args.pace))

            if not args.no_signs:
                base = int(at[1] - max(pl["r_blocks"], 1) - 3)
                mc.setBlock(at[0], base, at[2], "POLISHED_BLACKSTONE")
                short = pl["name"].replace(star["name"], "").strip() or pl["name"]
                mc.setSign(at[0], base + 1, at[2], "OAK_SIGN", "NORTH",
                           *[fit(v) for v in (
                               short,
                               "%.2f Re" % pl["radius_earth"],
                               ("%.0f K" % pl["eqt_k"]) if pl["eqt_k"] else "",
                               "a=%s AU" % _au(pl["a_au"]))])
                boxes.append((at[0], base, at[2], at[0], base + 1, at[2]))

        if not args.no_signs:
            board_z, board_boxes = signpost(mc, star, planets, sx, sy, sz,
                                            star_r, body_km, orbit_km,
                                            when.strftime("%d %b %Y"))
            boxes.extend(board_boxes)
            print()
            print("  noticeboard at %d %d %d -- stand south of it, looking"
                  % (sx - 6, sy, board_z))
            print("  north: the star is on the right, then b, c, d to the left")

        save_manifest(data, star["name"], boxes)
        print()
        print("  %-18s /tp %d %d %d" % (star["name"], sx, sy, sz))
        for pl in planets:
            px, py, pz = pl["pos"]
            print("  %-18s /tp %d %d %d"
                  % (pl["name"], int(sx + round(px)), int(sy + round(py)),
                     int(sz + round(pz))))

    if args.tour:
        mc.postToChat("%s, as it stands on %s."
                      % (star["name"], when.strftime("%d %b %Y")))
        for pl in planets:
            px, py, pz = pl["pos"]
            x, y, z = int(sx + round(px)), int(sy + round(py)), int(sz + round(pz))
            mc.postToChat("%s -- %.2f Earth radii, %.0f blocks out"
                          % (pl["name"], pl["radius_earth"], pl["a_blocks"]))
            back = max(10.0, pl["r_blocks"] * 6)
            d = math.hypot(px, pz) or 1.0
            mc.player.setTilePos(int(x + px / d * back), y + 3,
                                 int(z + pz / d * back))
            time.sleep(0.6)
            mc.player.setDirection(-px / d, -0.2, -pz / d)
            time.sleep(3.5)


if __name__ == "__main__":
    main()
