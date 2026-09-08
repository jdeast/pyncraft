"""Twelve metres has to be twelve metres, whatever a block is worth.

Both heightmaps are in METRES. A block is `metres_per_cell` across, so it is
that tall too, and a build keeps true proportions.

At one metre per cell the metre count and the block count are the same number,
which is why this went unnoticed for so long: everything was built at 1 m and
worked. At 0.25 m per cell the school -- 4 storeys, `building:levels=4`, 12 m --
came out 12 blocks, which is 3 m, which is one storey. It looked like a
bungalow and nothing in the code objected.

So: a building of a given height in metres must come out the same height in
metres at every resolution, and these check exactly that.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

build_town = pytest.importorskip("build_town")


def tallest_building(world, palette):
    """How many blocks tall the built structure is, walls and roof together.

    The top block of a building is the roof, a different material from the
    walls, so counting only the walls is one short of the height.
    """
    wall = palette.index("WHITE_CONCRETE") + 1
    roof = palette.index("GRAY_CONCRETE") + 1
    xs, ys, zs = np.where(world == wall)
    if not len(ys):
        return 0
    x, z = xs[0], zs[0]
    column = world[x, :, z]
    filled = np.where((column == wall) | (column == roof))[0]
    return int(filled.max() - filled.min() + 1)


def one_building(height_m, cell):
    ground = np.zeros((12, 12), dtype=float)
    buildings = np.zeros((12, 12), dtype=float)
    buildings[4:8, 4:8] = height_m
    return build_town.to_voxels(ground, buildings, 0, 2, hollow=False,
                                metres_per_cell=cell)


@pytest.mark.parametrize("cell,expected_blocks", [
    (1.0, 12),      # a block is a metre
    (0.5, 24),      # two blocks to the metre
    (0.25, 48),     # four blocks to the metre: the case that was wrong
    (2.0, 6),       # coarser than a metre
])
def test_a_twelve_metre_building_is_twelve_metres(cell, expected_blocks):
    world, palette = one_building(12.0, cell)
    blocks = tallest_building(world, palette)
    assert blocks == expected_blocks, (
        "12 m at %g m per block should be %d blocks, got %d (= %.1f m)"
        % (cell, expected_blocks, blocks, blocks * cell))
    assert abs(blocks * cell - 12.0) < 1e-6, "the height in metres must not change"


@pytest.mark.parametrize("cell", [1.0, 0.5, 0.25])
def test_terrain_relief_keeps_its_height(cell):
    """A 4 m rise must stay a 4 m rise, not shrink with the cell size."""
    ground = np.zeros((10, 10), dtype=float)
    ground[5:, :] = 4.0                      # a 4 m step across the middle
    buildings = np.zeros((10, 10), dtype=float)
    world, palette = build_town.to_voxels(ground, buildings, 0, 2,
                                          metres_per_cell=cell)
    solid = world != 0
    low = int(solid[:, :, 0].sum(axis=1).max())      # column height, low side
    high = int(solid[:, :, -1].sum(axis=1).max())
    # Whichever side is taller, the difference is the step.
    step_blocks = abs(high - low)
    assert abs(step_blocks * cell - 4.0) < cell, (
        "a 4 m step came out %.2f m at %g m per block" % (step_blocks * cell, cell))


def test_a_finer_grid_makes_a_taller_world_not_a_flatter_one():
    """The bug in one line: finer cells must not squash the build."""
    coarse, _ = one_building(12.0, 1.0)
    fine, _ = one_building(12.0, 0.25)
    assert fine.shape[1] > coarse.shape[1], (
        "at four blocks to the metre the world must be taller, not the same")


def test_the_default_is_one_metre_per_block():
    """Anything that does not say gets metres, which is what it always was."""
    world, palette = build_town.to_voxels(
        np.zeros((6, 6)), np.full((6, 6), 9.0), 0, 1, hollow=False)
    assert tallest_building(world, palette) == 9


# ── a building is built on a level foundation ─────────────────────────────

def test_a_building_on_a_slope_has_a_level_roof():
    """The terrain must not print through the roof.

    Letting every column stand on its own patch of ground gives a building on
    a slope a sloping floor and a sloping roof, which no building has. The
    school sat on a metre of fall and its roof was four blocks out of level at
    0.25 m per block, which reads as a mistake from any distance.
    """
    n = 12
    ground = np.tile(np.linspace(0.0, 3.0, n), (n, 1))   # a 3 m fall across
    buildings = np.zeros((n, n), dtype=float)
    ids = np.zeros((n, n), dtype=np.uint16)
    buildings[3:9, 3:9] = 9.0
    ids[3:9, 3:9] = 1

    world, palette = build_town.to_voxels(ground, buildings, 0, 2, hollow=False,
                                          metres_per_cell=0.25, building_ids=ids)
    idsT = ids.T
    tops = []
    for x, z in zip(*np.where(idsT > 0)):
        column = world[x, :, z]
        filled = np.where(column != 0)[0]
        if len(filled):
            tops.append(int(filled.max()))
    assert tops, "the building was not placed"
    assert max(tops) == min(tops), (
        "the roof should be level; it varies by %d blocks" % (max(tops) - min(tops)))


def test_without_ids_the_old_behaviour_is_unchanged():
    """No id raster means no grouping, and the roof follows the ground.

    Not desirable, but it is what a file fetched before ids existed contains,
    and it must still build rather than fail.
    """
    n = 8
    ground = np.tile(np.linspace(0.0, 2.0, n), (n, 1))
    buildings = np.zeros((n, n), dtype=float)
    buildings[2:6, 2:6] = 6.0
    world, palette = build_town.to_voxels(ground, buildings, 0, 1, hollow=False,
                                          metres_per_cell=0.5)
    assert (world != 0).any(), "it should still build something"


def test_the_building_reaches_the_ground_on_the_uphill_side():
    """Levelling must embed the uphill side, not leave the downhill floating."""
    n = 10
    ground = np.tile(np.linspace(0.0, 2.0, n), (n, 1))
    buildings = np.zeros((n, n), dtype=float)
    ids = np.zeros((n, n), dtype=np.uint16)
    buildings[2:8, 2:8] = 6.0
    ids[2:8, 2:8] = 1
    world, _ = build_town.to_voxels(ground, buildings, 0, 2, hollow=False,
                                    metres_per_cell=0.5, building_ids=ids)
    # No column under the footprint may have a gap between ground and building.
    idsT = ids.T
    for x, z in zip(*np.where(idsT > 0)):
        column = world[x, :, z]
        filled = np.where(column != 0)[0]
        assert filled.max() - filled.min() + 1 == len(filled), (
            "column at %d,%d has a gap: the building is floating" % (x, z))


# ── the ground is the right way up ────────────────────────────────────────

@pytest.mark.parametrize("body,expected_top", [
    ("earth", "GRASS_BLOCK"),
    ("mars", "RED_SAND"),
    ("moon", "LIGHT_GRAY_CONCRETE_POWDER"),
])
def test_the_first_soil_layer_is_the_one_you_walk_on(body, expected_top):
    """SOIL[0] is the surface, and it has to end up on the surface.

    Indexing the soil list backwards buries it: yards came out coarse dirt
    with the turf three blocks down, and Mars had terracotta on top instead of
    red sand. Anywhere carrying a land-cover tag gets painted over afterwards
    and looked right, so only untagged ground -- gardens, mostly -- showed it,
    which is why it survived several rebuilds.
    """
    ground = np.zeros((5, 5), dtype=float)
    buildings = np.zeros((5, 5), dtype=float)
    world, palette = build_town.to_voxels(ground, buildings, 0, 5, body=body)
    column = world[2, :, 2]
    filled = np.where(column != 0)[0]
    top_block = palette[column[filled.max()] - 1]
    assert top_block == expected_top, (
        "%s should have %s on top, got %s" % (body, expected_top, top_block))


def test_the_soil_layers_run_in_order_downwards():
    """Below the surface, the layers follow the list in order."""
    ground = np.zeros((4, 4), dtype=float)
    world, palette = build_town.to_voxels(ground, np.zeros((4, 4)), 0, 6,
                                          body="earth")
    column = world[1, :, 1]
    filled = np.where(column != 0)[0]
    stack = [palette[column[y] - 1] for y in reversed(filled)]
    assert stack[:4] == ["GRASS_BLOCK", "DIRT", "DIRT", "COARSE_DIRT"], stack[:4]
    assert stack[4] == "STONE", "below the soil it should be the deep block"
