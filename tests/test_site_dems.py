"""The metre-scale DEMs have to be read where they actually are.

Reading the right file in the wrong place is the one error in this whole
pipeline that never announces itself. A landscape built from the wrong pixels
is still a perfectly convincing landscape -- hills, valleys, a plausible
range of elevations -- and nothing about it looks wrong until somebody who
knows the site says "that isn't Hadley Rille".

So every projection here is checked by inverting it: take the corner pixels,
turn them back into latitude and longitude, and require that they reproduce
the extent the data product publishes. That is a real check with a real
answer, and it is the reason unproject() exists at all.

Nothing here touches the network. The header values are the ones the actual
files carry, recorded here so the arithmetic can be tested without an 8 GB
download or an internet connection.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

fetch_planet = pytest.importorskip("fetch_planet")
build_town = pytest.importorskip("build_town")


# The georeferencing tags exactly as the two files carry them.
APOLLO15 = {
    "width": 2555, "height": 14311,
    "x_min": -4810338.0000014, "y_max": 804664.00000024,
    "x_scale": 2.0000000000006, "y_scale": 2.0000000000006,
}
APOLLO15_PROJ = fetch_planet.SITE_DEMS["apollo15"]["projection"]

MALAPERT = {
    "width": 4200, "height": 4200,
    "x_min": -11000.0, "y_max": 132000.0,
    "x_scale": 5.0, "y_scale": 5.0,
}
MALAPERT_PROJ = fetch_planet.SITE_DEMS["malapert"]["projection"]


def _full(info):
    """Fill in the derived extent the reader normally computes."""
    out = dict(info)
    out["x_max"] = info["x_min"] + info["width"] * info["x_scale"]
    out["y_min"] = info["y_max"] - info["height"] * info["y_scale"]
    return out


# ── the published extents ──────────────────────────────────────────────────

def test_apollo15_corners_match_the_published_extent():
    """LROC publishes 25.59-26.54 N, 3.50-3.69 E for this DTM."""
    info = _full(APOLLO15)
    n_lat, w_lon = fetch_planet.unproject(0, 0, info, APOLLO15_PROJ)
    s_lat, e_lon = fetch_planet.unproject(info["width"] - 1, info["height"] - 1,
                                          info, APOLLO15_PROJ)
    assert n_lat == pytest.approx(26.54, abs=0.01)
    assert s_lat == pytest.approx(25.59, abs=0.01)
    assert w_lon == pytest.approx(3.50, abs=0.01)
    assert e_lon == pytest.approx(3.69, abs=0.01)


def test_malapert_covers_the_massif():
    """Site23 is a 21 km square centred near 86 S, and must contain the peak."""
    info = _full(MALAPERT)
    lat0, _ = fetch_planet.unproject(0, 0, info, MALAPERT_PROJ)
    lat1, _ = fetch_planet.unproject(info["width"] - 1, info["height"] - 1,
                                     info, MALAPERT_PROJ)
    assert min(lat0, lat1) < -85.964 < max(lat0, lat1)
    assert info["width"] * info["x_scale"] == pytest.approx(21000.0)


@pytest.mark.parametrize("name,info,proj,lat,lon", [
    ("apollo15", APOLLO15, APOLLO15_PROJ, 26.132, 3.634),
    ("apollo15", APOLLO15, APOLLO15_PROJ, 25.90, 3.55),
    ("malapert", MALAPERT, MALAPERT_PROJ, -85.964, 357.681),
    ("malapert", MALAPERT, MALAPERT_PROJ, -86.10, 2.0),
])
def test_projection_round_trips(name, info, proj, lat, lon):
    """Forward then back must land where it started, to well under a pixel."""
    full = _full(info)
    col, row = fetch_planet.pixel_for(lat, lon, full, proj)
    assert 0 <= col < full["width"], "%s: %s,%s fell outside" % (name, lat, lon)
    assert 0 <= row < full["height"]
    back_lat, back_lon = fetch_planet.unproject(col, row, full, proj)
    # A pixel is 2 or 5 metres, which is under 0.0002 degrees of latitude.
    assert back_lat == pytest.approx(lat, abs=0.001)
    assert ((back_lon - lon + 180.0) % 360.0) - 180.0 == pytest.approx(0.0, abs=0.001)


def test_the_landing_site_is_in_its_own_dem():
    """Each site DEM must actually contain the coordinates it is filed under."""
    for name, dem in fetch_planet.SITE_DEMS.items():
        info = _full(APOLLO15 if name == "apollo15" else MALAPERT)
        col, row = fetch_planet.pixel_for(dem["lat"], dem["lon"], info,
                                          dem["projection"])
        assert 0 <= col < info["width"], name
        assert 0 <= row < info["height"], name


def test_polar_stereographic_pole_is_the_origin():
    """The south pole projects to x=0, y=0, which is the whole point of it."""
    x, y = fetch_planet._project(-90.0, 0.0, {}, MALAPERT_PROJ)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)
    # And longitude does not matter at the pole.
    x2, y2 = fetch_planet._project(-90.0, 137.0, {}, MALAPERT_PROJ)
    assert x2 == pytest.approx(0.0, abs=1e-6)
    assert y2 == pytest.approx(0.0, abs=1e-6)


def test_global_mosaic_still_spans_the_whole_body():
    """The change must not have moved the global DEMs, which worked."""
    info = _full({"width": 92160, "height": 46080,
                  "x_min": -180.0, "y_max": 90.0,
                  "x_scale": 360.0 / 92160, "y_scale": 180.0 / 46080})
    cyl = {"kind": "cylindrical"}
    lat, lon = fetch_planet.unproject(0, 0, info, cyl)
    assert lat == pytest.approx(90.0, abs=0.01)
    assert lon == pytest.approx(-180.0, abs=0.01)
    col, row = fetch_planet.pixel_for(0.67, 23.47, info, cyl)   # Tranquility
    assert 0 <= col < info["width"] and 0 <= row < info["height"]


# ── the crust ──────────────────────────────────────────────────────────────

def test_a_crust_is_far_cheaper_than_filling_to_the_floor():
    """The point of a crust: cost follows area, not the depth of the valley."""
    shallow = np.zeros((40, 40)); shallow[20:, :] = -300.0
    deeper = np.zeros((40, 40)); deeper[20:, :] = -3000.0
    for ground in (shallow, deeper):
        crusted, _ = build_town.to_voxels(ground, np.zeros_like(ground), 0, 3,
                                          body="moon", metres_per_cell=2.0, crust=1)
        solid, _ = build_town.to_voxels(ground, np.zeros_like(ground), 0, 3,
                                        body="moon", metres_per_cell=2.0)
        assert int((crusted != 0).sum()) < int((solid != 0).sum()) / 8


def test_the_crust_thickens_to_cover_a_cliff():
    """A flat crust leaves daylight under the lip of any drop taller than it.

    This is what `crust` being a minimum rather than a thickness buys: on
    level ground one block is plenty, and at the top of a cliff the column
    reaches down far enough that you cannot see under it. On Hadley Rille the
    deepest drop is 81 blocks, so no sane constant would have covered it -- a
    flat crust of five left 671 columns open.
    """
    ground = np.zeros((20, 20))
    ground[10:, :] = -160.0                    # an 80-block cliff at 2 m
    world, _ = build_town.to_voxels(ground, np.zeros_like(ground), 0, 3,
                                    body="moon", metres_per_cell=2.0, crust=1)
    nx, ny, nz = world.shape
    tops, bottoms = {}, {}
    for x in range(nx):
        for z in range(nz):
            filled = np.nonzero(world[x, :, z])[0]
            assert len(filled), "column %d,%d is empty" % (x, z)
            tops[(x, z)] = int(filled.max())
            bottoms[(x, z)] = int(filled.min())
            # solid from bottom to top, no floating shelf
            assert len(filled) == tops[(x, z)] - bottoms[(x, z)] + 1

    # Nothing may see under a column: every neighbour's top is at or above
    # this column's lowest block.
    for (x, z), bottom in bottoms.items():
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n in tops:
                assert tops[n] >= bottom - 1,                     "gap at %d,%d: neighbour top %d, this bottom %d" % (
                        x, z, tops[n], bottom)


def test_flat_ground_only_needs_one_block():
    """Where nothing can see past it, one block is the whole crust."""
    world, _ = build_town.to_voxels(np.zeros((12, 12)), np.zeros((12, 12)), 0, 1,
                                    body="moon", metres_per_cell=2.0, crust=1)
    assert int((world != 0).sum()) == 12 * 12


def test_crust_keeps_the_surface_where_it_was():
    """A crust may only remove blocks from underneath, never move the top."""
    rng = np.random.default_rng(11)
    ground = rng.random((25, 25)) * 120.0

    solid, _ = build_town.to_voxels(ground, np.zeros_like(ground), 0, 3,
                                    body="moon", metres_per_cell=2.0)
    crust, _ = build_town.to_voxels(ground, np.zeros_like(ground), 0, 3,
                                    body="moon", metres_per_cell=2.0, crust=6)
    assert solid.shape == crust.shape
    nx, ny, nz = solid.shape
    for x in range(nx):
        for z in range(nz):
            a = np.nonzero(solid[x, :, z])[0]
            b = np.nonzero(crust[x, :, z])[0]
            assert a.max() == b.max(), "top of column %d,%d moved" % (x, z)
    # And it is a strict subset: nothing new appeared.
    assert np.all((crust != 0) <= (solid != 0))


# ── coarsening a window ────────────────────────────────────────────────────

def test_downsample_averages_rather_than_samples():
    """Taking every nth pixel would be quicker and wrong.

    Point sampling a surface with real detail in it means a narrow ridge
    either survives at full height or vanishes entirely, depending on where
    the grid happens to land. Averaging loses the detail, which is what a
    coarser map is supposed to do.
    """
    grid = np.arange(16, dtype=float).reshape(4, 4)
    out = fetch_planet.downsample(grid, 2)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx((0 + 1 + 4 + 5) / 4.0)
    assert out[1, 1] == pytest.approx((10 + 11 + 14 + 15) / 4.0)


def test_stride_of_one_changes_nothing():
    grid = np.random.default_rng(0).random((5, 7))
    assert np.array_equal(fetch_planet.downsample(grid, 1), grid)


def test_a_partial_block_is_trimmed_not_averaged_against_nothing():
    assert fetch_planet.downsample(np.ones((5, 7)), 2).shape == (2, 3)


def test_downsample_ignores_gaps_but_keeps_a_whole_one():
    grid = np.ones((4, 4))
    grid[0, 0] = np.nan                     # one gap among three real values
    grid[2:4, 2:4] = np.nan                 # a block that is all gap
    out = fetch_planet.downsample(grid, 2)
    assert out[0, 0] == pytest.approx(1.0)
    assert np.isnan(out[1, 1])


def test_nodata_has_to_be_masked_before_anything_averages_it():
    """The ordering bug, which produced a hole 1e35 times deeper than the crater.

    The NAC DTM marks nodata with -3.4e38. Averaging a 2x2 block containing
    one of those gives about -8.5e37: not obviously a gap, no longer equal to
    the nodata value so a later test for it fails, and a perfectly ordinary
    looking number until you notice the units. Masking first turns it into a
    NaN, which nanmean simply ignores.
    """
    nodata = -3.4028226e38
    block = np.full((2, 2), -1900.0)
    block[0, 0] = nodata

    averaged_first = fetch_planet.downsample(block.copy(), 2)[0, 0]
    assert averaged_first < -8e37
    assert averaged_first != nodata, "and so cannot be spotted afterwards"

    masked = block.copy()
    masked[masked <= nodata + abs(nodata) * 1e-6] = np.nan
    assert fetch_planet.downsample(masked, 2)[0, 0] == pytest.approx(-1900.0)


# ── a crust has to stay up ─────────────────────────────────────────────────

def test_a_crust_contains_nothing_that_falls():
    """The one that actually collapsed a landscape.

    Blocks go in with physics off, deliberately: evaluating gravity for half a
    million placements is what stalled the server. So a floating crust of
    concrete powder never learns it is unsupported, and looks perfect -- until
    any block update reaches it. Break one block and the update spreads
    outward, every neighbour finds nothing beneath it, and the map drains
    away.

    The Moon's top three soil layers were concrete powder and Mars's top two
    were red sand, so both were a landslide waiting for a pickaxe.
    """
    for body in ("moon", "mars", "earth"):
        _, palette = build_town.to_voxels(
            np.zeros((8, 8)), np.zeros((8, 8)), 0, 3,
            body=body, metres_per_cell=2.0, crust=1)
        for material in palette:
            assert material not in build_town.FALLING, "%s: %s" % (body, material)


def test_without_a_crust_sand_is_still_sand():
    """A build filled to the floor rests on something, so nothing is swapped.

    Mars is red sand on top because the surface really is dust and behaves
    like dust when you dig it, which is worth keeping where it is safe.
    """
    _, palette = build_town.to_voxels(np.zeros((8, 8)), np.zeros((8, 8)), 0, 3,
                                      body="mars", metres_per_cell=2.0)
    assert "RED_SAND" in palette


def test_the_substitute_keeps_the_colour():
    assert build_town.anchored("RED_SAND") == "RED_SANDSTONE"
    assert build_town.anchored("GRAY_CONCRETE_POWDER") == "GRAY_CONCRETE"
    assert build_town.anchored("LIGHT_GRAY_CONCRETE_POWDER") == "LIGHT_GRAY_CONCRETE"
    assert build_town.anchored("STONE") == "STONE"
    # every colour of powder has a concrete of the same name
    for name, solid in build_town.FALLING.items():
        if name.endswith("_CONCRETE_POWDER"):
            assert solid == name.replace("_POWDER", "")
