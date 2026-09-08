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

def test_crust_costs_the_same_however_deep_the_valley():
    """The whole reason for the crust: cost stops depending on the relief.

    Not that every crusted build costs the same -- at the very lowest point a
    column is only `depth` blocks tall, so a flat map is cheaper than a
    cliffed one no matter what. The property that matters is that making the
    cliff ten times deeper costs nothing extra, and without a crust it costs
    ten times as much.
    """
    shallow = np.zeros((40, 40), dtype=float)
    shallow[20:, :] = -300.0
    deeper = np.zeros((40, 40), dtype=float)
    deeper[20:, :] = -3000.0         # ten times the relief, same shape

    crusted = []
    solid = []
    for ground in (shallow, deeper):
        world, _ = build_town.to_voxels(
            ground, np.zeros_like(ground), 0, 3, body="moon",
            metres_per_cell=2.0, crust=5)
        crusted.append(int((world != 0).sum()))
        world, _ = build_town.to_voxels(
            ground, np.zeros_like(ground), 0, 3, body="moon",
            metres_per_cell=2.0)
        solid.append(int((world != 0).sum()))

    assert crusted[0] == crusted[1], "crust cost must not follow the relief"
    assert solid[1] > solid[0] * 9, "without a crust it should, and does"
    assert crusted[1] * 20 < solid[1]


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
