"""getBlocks comes back in the server's order, which is not the obvious one.

FruitJuice walks a cuboid with Y outermost, then X, then Z -- a stack of
horizontal slabs, each slab rows running east, each row running south. The
client reshaped it into slabs of xSize * ySize instead, which is the right
size only when the box happens to be as tall as it is deep.

That is the worst kind of wrong. Every value returned was a real block from
somewhere inside the box, so nothing was empty, nothing raised, and a scan of
a landing site reported the Lunar Module spread over thirty blocks of height
it did not occupy. It only showed up when the answer was checked against
somewhere a person could stand.
"""
import pytest

from pyncraft.minecraft import reshape_blocks


def _server_order(xs, ys, zs):
    """What the plugin actually sends: for y, for x, for z."""
    return ["%d_%d_%d" % (x, y, z)
            for y in range(ys) for x in range(xs) for z in range(zs)]


@pytest.mark.parametrize("xs,ys,zs", [
    (1, 1, 1), (3, 3, 3), (2, 3, 4), (4, 3, 2), (5, 1, 9), (1, 7, 2), (10, 2, 3),
])
def test_every_block_lands_where_it_belongs(xs, ys, zs):
    grid = reshape_blocks(_server_order(xs, ys, zs), xs, ys, zs)
    assert len(grid) == ys
    assert all(len(slab) == xs for slab in grid)
    assert all(len(row) == zs for slab in grid for row in slab)
    for y in range(ys):
        for x in range(xs):
            for z in range(zs):
                assert grid[y][x][z] == "%d_%d_%d" % (x, y, z)


def test_the_shape_that_used_to_work_by_accident():
    """A cube was fine, which is why this survived: ySize == zSize hid it."""
    xs = ys = zs = 4
    grid = reshape_blocks(_server_order(xs, ys, zs), xs, ys, zs)
    assert grid[2][1][3] == "1_2_3"


def test_a_short_reply_says_so_rather_than_lying(capsys):
    """It complains through pyncraft's own logger, not warnings.warn.

    `from .logger import *` in minecraft.py shadows the `warn` imported from
    warnings a line earlier, so the message is printed rather than raised.
    Worth knowing before writing a test that waits for a warning that is never
    going to arrive.
    """
    reshape_blocks(["STONE"] * 5, 2, 3, 4)
    assert "expected 24 blocks, got 5" in capsys.readouterr().out


def test_nothing_is_invented_or_dropped():
    names = _server_order(3, 4, 5)
    grid = reshape_blocks(names, 3, 4, 5)
    flat = [v for slab in grid for row in slab for v in row]
    assert sorted(flat) == sorted(names)
