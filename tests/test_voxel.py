"""Splitting a voxel set into as few box fills as possible.

The reason this matters: one world.setBlock per block is slow enough to be the
whole experience on a Raspberry Pi serving a class. world.setBlocks fills a
cuboid in one command, so the useful question is how few boxes a real shape
splits into. These tests pin both the correctness (every voxel covered exactly
once, with the right material) and the compression, because a refactor that
quietly stops merging would still pass a correctness-only suite.
"""
import numpy as np
import pytest

from pyncraft import voxel


def covered(boxes, shape):
    """Paint the boxes back into an array, counting how often each cell is hit."""
    hits = np.zeros(shape, dtype=int)
    labels = np.zeros(shape, dtype=int)
    for x1, y1, z1, x2, y2, z2, label in boxes:
        hits[x1:x2 + 1, y1:y2 + 1, z1:z2 + 1] += 1
        labels[x1:x2 + 1, y1:y2 + 1, z1:z2 + 1] = label
    return hits, labels


def check_exact(array):
    """Every non-empty cell covered exactly once, with its own label."""
    boxes = list(voxel.decompose(array))
    hits, labels = covered(boxes, array.shape)
    assert np.array_equal(hits > 0, array != 0), "coverage does not match the input"
    assert hits.max(initial=0) <= 1, "some cell was covered by two boxes"
    assert np.array_equal(labels, array), "a cell came out as the wrong material"
    return boxes


# ── the shapes real examples actually produce ──────────────────────────────

def test_a_solid_cuboid_is_one_command():
    a = np.ones((8, 4, 6), dtype=int)
    assert len(check_exact(a)) == 1


def test_a_flat_slab_is_one_command():
    # What a floor, or a single terrain layer, looks like.
    a = np.zeros((32, 1, 32), dtype=int)
    a[:] = 1
    assert len(check_exact(a)) == 1


def test_a_single_block_is_one_command():
    a = np.zeros((3, 3, 3), dtype=int)
    a[1, 1, 1] = 1
    boxes = check_exact(a)
    assert boxes == [(1, 1, 1, 1, 1, 1, 1)]


def test_empty_produces_nothing():
    assert list(voxel.decompose(np.zeros((4, 4, 4), dtype=int))) == []
    assert list(voxel.decompose(np.zeros((0, 0, 0), dtype=int))) == []


def test_two_materials_are_never_merged():
    a = np.zeros((4, 1, 1), dtype=int)
    a[0:2, 0, 0] = 1
    a[2:4, 0, 0] = 2
    boxes = check_exact(a)
    assert len(boxes) == 2
    assert {b[6] for b in boxes} == {1, 2}


def test_a_hollow_shell_is_covered_exactly_once():
    # Overlapping boxes would place blocks twice: correct-looking but twice the
    # commands, and the second write can undo a neighbour's block state.
    a = np.ones((6, 6, 6), dtype=int)
    a[1:5, 1:5, 1:5] = 0
    check_exact(a)


def test_terrain_shaped_data_compresses_hard():
    # A heightmap is the case that matters: mostly smooth, with columns of
    # equal height merging into slabs.
    rng = np.random.default_rng(0)
    nx = nz = 48
    ground = np.zeros((nx, 8, nz), dtype=int)
    # A gentle surface, so neighbouring columns usually agree.
    heights = (4 + 2 * np.sin(np.linspace(0, 3, nx))[:, None]
                 + 1 * np.cos(np.linspace(0, 3, nz))[None, :]).astype(int)
    for x in range(nx):
        for z in range(nz):
            ground[x, :heights[x, z], z] = 1

    boxes = check_exact(ground)
    blocks = int((ground != 0).sum())
    assert blocks > 8000, "test data should be big enough to be meaningful"
    # The point of the whole module. Without merging this is one command per
    # block; a tenth of that is the difference between usable and not.
    assert len(boxes) < blocks / 10, (
        "expected heavy compression, got %d boxes for %d blocks" % (len(boxes), blocks))


def test_worst_case_degrades_to_one_box_per_block_and_no_worse():
    # Alternating materials cannot merge at all. That is fine -- it is exactly
    # the number of commands you would have sent anyway -- but it must not
    # somehow produce MORE.
    a = np.indices((6, 6, 6)).sum(axis=0) % 2 + 1
    boxes = check_exact(a)
    assert len(boxes) <= a.size


@pytest.mark.parametrize("seed", range(8))
def test_random_shapes_are_always_covered_exactly(seed):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 3, size=(7, 5, 6))
    check_exact(a)


# ── points in, boxes out ───────────────────────────────────────────────────

def test_points_without_materials():
    array, palette, offset = voxel.to_array([(0, 0, 0), (1, 0, 0), (2, 0, 0)])
    assert palette == [None]          # the caller supplies block=
    assert offset == (0, 0, 0)
    assert len(list(voxel.decompose(array))) == 1

def test_points_are_shifted_so_the_array_stays_small():
    # Points far from the origin must not allocate an array that reaches back
    # to 0,0,0 -- that is how a build near x=100000 becomes a memory error.
    array, palette, offset = voxel.to_array([(1000, 2000, 3000), (1001, 2000, 3000)])
    assert offset == (1000, 2000, 3000)
    assert array.shape == (2, 1, 1)

def test_points_with_materials_build_a_palette():
    array, palette, offset = voxel.to_array(
        [(0, 0, 0, "STONE"), (1, 0, 0, "STONE"), (2, 0, 0, "DIRT")])
    assert palette == ["STONE", "DIRT"]
    boxes = list(voxel.decompose(array))
    assert len(boxes) == 2

def test_a_later_point_wins_where_two_collide():
    # Same as sending the two commands in order.
    array, palette, offset = voxel.to_array([(0, 0, 0, "STONE"), (0, 0, 0, "DIRT")])
    assert palette[array[0, 0, 0] - 1] == "DIRT"

def test_bad_point_width_is_rejected():
    with pytest.raises(ValueError):
        voxel.to_array([(1, 2)])

def test_no_points_is_not_an_error():
    array, palette, offset = voxel.to_array([])
    assert array.size == 0


# ── the commands themselves ────────────────────────────────────────────────

def test_a_single_block_uses_setBlock_not_setBlocks():
    a = np.zeros((3, 3, 3), dtype=int)
    a[0, 0, 0] = 1
    cmds = list(voxel.commands_for(a, [None], (0, 0, 0), "STONE"))
    assert cmds == [(b"world.setBlock", (0, 0, 0, "STONE"))]


def test_a_run_uses_setBlocks():
    a = np.zeros((4, 1, 1), dtype=int)
    a[:, 0, 0] = 1
    (name, args), = voxel.commands_for(a, [None], (0, 0, 0), "STONE")
    assert name == b"world.setBlocks"
    assert args == (0, 0, 0, 3, 0, 0, "STONE")


def test_the_offset_is_added_to_every_coordinate():
    a = np.zeros((2, 1, 1), dtype=int)
    a[:, 0, 0] = 1
    (name, args), = voxel.commands_for(a, [None], (100, 64, -50), "STONE")
    assert args == (100, 64, -50, 101, 64, -50, "STONE")


def test_a_missing_material_is_an_error_rather_than_a_bad_build():
    a = np.ones((1, 1, 1), dtype=int)
    with pytest.raises(ValueError):
        list(voxel.commands_for(a, [None], (0, 0, 0), None))
