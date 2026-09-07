"""minecraftstuff: the drawing helpers.

MinecraftDrawing and MinecraftTurtle were both broken for years without anyone
noticing, because nothing exercised them. These are the cases that were wrong.
"""
import pytest

from pyncraft.block import Block, STONE, AIR
from pyncraft.minecraft import Vec3
from pyncraft.minecraftstuff import MinecraftDrawing, MinecraftTurtle, Points


class RecordingMinecraft:
    """Captures setBlock calls instead of talking to a server."""

    def __init__(self, height=64):
        self.blocks = {}
        self.calls = []
        self._height = height

    def setBlock(self, x, y, z, block, *rest):
        self.calls.append((x, y, z, block) + rest)
        self.blocks[(x, y, z)] = block

    def getHeight(self, x, z):
        return self._height


@pytest.fixture
def mc():
    return RecordingMinecraft()


# ── Block ────────────────────────────────────────────────────────────────────

def test_block_is_hashable_and_printable():
    # (id << 8) + data and "%d" both raised TypeError on a named material
    assert hash(STONE) == hash(Block("STONE"))
    assert repr(STONE) == "Block(STONE, 0)"
    assert len({STONE, Block("STONE"), AIR}) == 2


def test_blocks_sort():
    assert sorted([Block("STONE"), Block("AIR")])[0].id == "AIR"


# ── getLine ──────────────────────────────────────────────────────────────────

def test_getline_accepts_floats(mc):
    # abs(dx) << 1 raised TypeError, and player.getPos() returns floats
    d = MinecraftDrawing(mc)
    pts = d.getLine(0.0, 64.0, 0.0, 3.0, 64.0, 0.0)
    assert [(p.x, p.y, p.z) for p in pts] == [(0, 64, 0), (1, 64, 0), (2, 64, 0), (3, 64, 0)]


def test_getline_floors_negative_coordinates(mc):
    d = MinecraftDrawing(mc)
    assert (d.getLine(-0.5, 0, 0, -0.5, 0, 0)[0].x) == -1


def test_getline_single_point(mc):
    d = MinecraftDrawing(mc)
    assert len(d.getLine(1, 1, 1, 1, 1, 1)) == 1


def test_getline_is_symmetric_in_length(mc):
    d = MinecraftDrawing(mc)
    assert len(d.getLine(0, 0, 0, 5, 3, 2)) == len(d.getLine(5, 3, 2, 0, 0, 0))


# ── drawing ──────────────────────────────────────────────────────────────────

def test_drawpoint_does_not_pass_blockdata_as_the_facing(mc):
    # setBlock's 5th argument is the FACING now; forwarding blockData sent
    # world.setBlock(x,y,z,OAK_STAIRS,0) and the server rejected it, so every
    # directional block silently failed to place.
    d = MinecraftDrawing(mc)
    d.drawPoint3d(0, 64, 0, "OAK_STAIRS")
    assert mc.calls == [(0, 64, 0, "OAK_STAIRS")]


def test_drawpoint_still_accepts_a_blockdata_argument(mc):
    d = MinecraftDrawing(mc)
    d.drawPoint3d(0, 64, 0, "OAK_STAIRS", 3)
    assert mc.calls[-1] == (0, 64, 0, "OAK_STAIRS")


def test_drawline_places_every_block(mc):
    d = MinecraftDrawing(mc)
    d.drawLine(0, 64, 0, 4, 64, 0, "STONE")
    assert [mc.blocks.get((x, 64, 0)) for x in range(5)] == ["STONE"] * 5


def test_drawface_wireframe_closes_the_polygon(mc):
    d = MinecraftDrawing(mc)
    pts = Points()
    for x, z in [(0, 0), (3, 0), (3, 3)]:
        pts.add(x, 64, z)
    d.drawFace(pts, False, "STONE")
    # the edge back to the first vertex must be drawn too
    assert (1, 64, 1) in mc.blocks or (2, 64, 2) in mc.blocks


def test_sphere_is_symmetric(mc):
    d = MinecraftDrawing(mc)
    d.drawSphere(0, 64, 0, 4, "STONE")
    xs = [x for (x, y, z) in mc.blocks]
    assert min(xs) == -max(xs)


# ── MinecraftTurtle ──────────────────────────────────────────────────────────

def test_turtle_can_be_constructed(mc):
    # the last line of __init__ called _drawTurtle, which read .id off a string
    t = MinecraftTurtle(mc, Vec3(0, 64, 0))
    assert t.turtleblock == "DIAMOND_BLOCK"


def test_turtle_draws_itself_at_z_not_y_twice(mc):
    MinecraftTurtle(mc, Vec3(1, 64, 7))
    assert mc.calls[-1][:3] == (1, 64, 7)


def test_turtle_position_default_is_not_shared():
    import inspect
    assert inspect.signature(MinecraftTurtle.__init__).parameters["position"].default is None


def test_turtle_leaves_a_trail(mc):
    t = MinecraftTurtle(mc, Vec3(0, 64, 0))
    t.penblock("RED_CONCRETE")
    t.speed(0)
    t.forward(4)
    trail = [p for p, b in mc.blocks.items() if b == "RED_CONCRETE"]
    assert len(trail) >= 4


def test_penblock_accepts_a_block_object(mc):
    t = MinecraftTurtle(mc, Vec3(0, 64, 0))
    t.penblock(Block("GOLD_BLOCK"))
    assert t._penblock == "GOLD_BLOCK"


def test_penup_stops_drawing(mc):
    t = MinecraftTurtle(mc, Vec3(0, 64, 0))
    t.penblock("RED_CONCRETE")
    t.speed(0)
    t.penup()
    t.forward(4)
    assert not [b for b in mc.blocks.values() if b == "RED_CONCRETE"]
