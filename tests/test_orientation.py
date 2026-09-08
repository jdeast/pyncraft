"""Which way is north.

Rasters are [row, col] with row 0 at the north and col 0 at the west, which is
how every image and every DEM arrives. Turning that into blocks involves two
separate decisions, and only one of them is a matter of taste.

The first is not: the column index has to become X. Mapping row to X and col to
Z -- which is what the obvious loop over `ground.shape` does -- is not a
rotation but a REFLECTION across the NW-SE diagonal. North-west and south-east
stay where they belong while north-east and south-west swap over. A rotated map
announces itself the moment you look at it; a mirrored one looks entirely
convincing. Roberts Elementary was built that way and nobody noticed until
somebody asked which way north was.

The second is a choice. Minecraft's own north is -Z, which is what the compass
and the F3 screen agree on, and that is the default: the point of building a
real place is that it looks like the real place, so standing in it with a
compass should give the directions you would get standing there. Map and
graph-paper convention -- north up the page, +Z -- is available for a
coordinate worked out on paper. Both are tested, because a silent change to
either produces a convincing wrong answer.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

build_town = pytest.importorskip("build_town")

N = 10
LAST = N - 1


def corner(row, col, north="-Z", n=N):
    """One tall marker at a single raster cell; returns its (x, z) in blocks."""
    ground = np.zeros((n, n), dtype=float)
    buildings = np.zeros((n, n), dtype=float)
    buildings[row, col] = 9.0
    world, palette = build_town.to_voxels(ground, buildings, 0, 1,
                                          hollow=False, north=north)
    label = palette.index("WHITE_CONCRETE") + 1
    xs, _, zs = np.where(world == label)
    assert len(xs), "the marker was not placed at all"
    return int(xs[0]), int(zs[0])


# ── east is +X either way, which is the part that is not a choice ──────────

@pytest.mark.parametrize("north", ["+Z", "-Z"])
def test_east_is_plus_x(north):
    west = corner(5, 2, north)
    east = corner(5, 7, north)
    assert east[0] > west[0], "a more easterly column must be a larger X"
    assert east[1] == west[1], "the same row must not change Z"


@pytest.mark.parametrize("north", ["+Z", "-Z"])
def test_north_south_runs_along_z(north):
    n = corner(2, 5, north)
    s = corner(7, 5, north)
    assert n[0] == s[0], "the same column must not change X"
    assert n[1] != s[1], "different rows must differ in Z"


@pytest.mark.parametrize("north", ["+Z", "-Z"])
def test_the_map_is_not_mirrored(north):
    """North-east must be east of north-west and on the same north-south line.

    This is the check that catches a transpose. Under a reflection the
    north-east corner ends up sharing a Z with the SOUTH-west one instead.
    """
    nw = corner(0, 0, north)
    ne = corner(0, LAST, north)
    sw = corner(LAST, 0, north)
    assert ne[1] == nw[1], "north-east and north-west must share a Z"
    assert sw[0] == nw[0], "south-west and north-west must share an X"
    assert ne[0] > nw[0], "north-east must be east of north-west"


# ── the default: the game compass, so it looks like the real place ────────

def test_default_matches_the_game_compass():
    """The default has to agree with the compass, or the place does not look
    like the place. Minecraft north is -Z."""
    north_marker = corner(0, 5)      # row 0 is the northern edge
    south_marker = corner(LAST, 5)
    assert north_marker[1] < south_marker[1], "north should be the smaller Z"


def test_default_corners():
    assert corner(0, 0) == (0, 0)            # north-west: west, north
    assert corner(0, LAST) == (LAST, 0)      # north-east
    assert corner(LAST, 0) == (0, LAST)      # south-west
    assert corner(LAST, LAST) == (LAST, LAST)  # south-east


# ── the alternative: map convention, north up the page ────────────────────

def test_plus_z_gives_map_convention():
    north_marker = corner(0, 5, "+Z")
    south_marker = corner(LAST, 5, "+Z")
    assert north_marker[1] > south_marker[1], "with north=+Z, north is the larger Z"


def test_the_two_conventions_are_mirror_images():
    a = corner(0, 3, "+Z")
    b = corner(0, 3, "-Z")
    assert a[0] == b[0], "east-west must be identical between the two"
    assert a[1] + b[1] == LAST, "north-south must be exactly reversed"


def test_an_unknown_convention_is_refused():
    ground = np.zeros((4, 4))
    with pytest.raises(ValueError):
        build_town.to_voxels(ground, ground, 0, 1, north="up")


# ── shape ─────────────────────────────────────────────────────────────────

def test_a_non_square_area_is_not_silently_transposed():
    # Invisible on a square, obvious on a rectangle.
    ground = np.zeros((4, 12), dtype=float)      # 4 north-south, 12 west-east
    world, _ = build_town.to_voxels(ground, ground, 0, 1)
    nx, _, nz = world.shape
    assert (nx, nz) == (12, 4), (
        "12 cells west-east must become 12 blocks of X and 4 of Z, got %dx%d" % (nx, nz))
