"""The wire protocol, exercised against a fake socket.

These assert the exact bytes pyncraft puts on the wire, which is the contract
with FruitJuice, and the bytes it accepts back.
"""
import pytest

from pyncraft.connection import Connection, ConnectionClosed, RequestError
from pyncraft.minecraft import Minecraft
from pyncraft.vec3 import Vec3


class FakeSocket:
    """Just enough socket for Connection: records sends, replays replies."""

    def __init__(self, replies=()):
        self.sent = []
        self._to_read = "".join(r + "\n" for r in replies)
        self.closed = False

    # Connection.__init__
    def connect(self, addr):
        pass

    def makefile(self, mode, encoding=None):
        import io
        return io.StringIO(self._to_read)

    def sendall(self, data):
        self.sent.append(data)

    # drain()
    def recv(self, n):
        return b""

    def close(self):
        self.closed = True


@pytest.fixture
def conn(monkeypatch):
    def build(replies=()):
        sock = FakeSocket(replies)
        monkeypatch.setattr("socket.socket", lambda *a, **k: sock)
        # select never reports readable, so drain() is a no-op
        monkeypatch.setattr("select.select", lambda *a, **k: ([], [], []))
        c = Connection("localhost", 4711)
        c._fake = sock
        return c
    return build


def last_sent(c):
    return c._fake.sent[-1].decode("utf-8").strip()


# ── framing ──────────────────────────────────────────────────────────────────

def test_send_frames_as_name_of_comma_separated_args(conn):
    c = conn()
    c.send(b"world.setBlock", 1, 2, 3, "STONE")
    assert last_sent(c) == "world.setBlock(1,2,3,STONE)"


def test_send_flattens_nested_arguments(conn):
    # CmdPlayer relies on this: an empty playerId list must vanish entirely
    c = conn()
    c.send(b"player.getPos", [])
    assert last_sent(c) == "player.getPos()"
    c.send(b"player.setPos", [], 1, 2, 3)
    assert last_sent(c) == "player.setPos(1,2,3)"


def test_receive_raises_on_a_fail_reply(conn):
    c = conn(["Fail,no such thing"])
    with pytest.raises(RequestError):
        c.receive()


def test_receive_raises_when_the_server_hangs_up(conn):
    # this used to return "" and look like an ordinary answer
    c = conn([])
    with pytest.raises(ConnectionClosed):
        c.receive()


def test_receive_uses_one_file_object_so_batched_replies_are_not_lost(conn):
    # a fresh makefile() per call buffered both replies and threw one away
    c = conn(["first", "second"])
    assert c.receive() == "first"
    assert c.receive() == "second"


# ── the commands FruitJuice actually implements ──────────────────────────────

@pytest.fixture
def mc(conn):
    def build(replies=()):
        c = conn(replies)
        m = Minecraft(c, [])
        m._fake = c._fake
        return m
    return build


def test_setblock_omits_the_facing_unless_asked(mc):
    # defaulting to WEST and always sending it made every stair face west
    m = mc()
    m.setBlock(1, 2, 3, "OAK_STAIRS")
    assert m._fake.sent[-1].decode().strip() == "world.setBlock(1,2,3,OAK_STAIRS)"


def test_setblock_sends_the_facing_when_given(mc):
    m = mc()
    m.setBlock(1, 2, 3, "OAK_STAIRS", "EAST")
    assert m._fake.sent[-1].decode().strip() == "world.setBlock(1,2,3,OAK_STAIRS,EAST)"


def test_getblockdata_parses_the_state_into_a_dict(mc):
    m = mc(["minecraft:oak_stairs[facing=east,half=bottom,shape=straight]"])
    got = m.getBlockData(0, 64, 0)
    assert got["material"] == "OAK_STAIRS"
    assert got["facing"] == "east"
    assert got["half"] == "bottom"
    assert (got["x"], got["y"], got["z"]) == (0, 64, 0)


def test_getblockdata_handles_a_block_with_no_state(mc):
    m = mc(["minecraft:stone"])
    assert m.getBlockData(0, 64, 0)["material"] == "STONE"


def test_getblockdata_unparsed_keeps_the_state_as_one_string(mc):
    # the value contains commas inside its brackets, so it must not be split
    m = mc(["minecraft:red_bed[facing=south,part=foot]"])
    got = m.getBlockData(0, 64, 0, parse=False)
    assert got["state"] == "facing=south,part=foot"


def test_getblockdata_accepts_a_vec3(mc):
    m = mc(["minecraft:stone"])
    got = m.getBlockData(Vec3(1, 2, 3))
    assert (got["x"], got["y"], got["z"]) == (1, 2, 3)


def test_player_commands_send_the_id_when_one_was_given(mc):
    m = Minecraft(mc()._fake and mc().conn, 42)
    m.player.setPos(10, 64, 20)
    assert m.conn._fake.sent[-1].decode().strip() == "player.setPos(42,10,64,20)"


def test_player_commands_send_no_id_by_default(mc):
    m = mc()
    m.player.setPos(10, 64, 20)
    assert m._fake.sent[-1].decode().strip() == "player.setPos(10,64,20)"
