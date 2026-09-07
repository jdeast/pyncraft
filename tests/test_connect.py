"""examples/connect.py: how an example decides which server to talk to.

Worth testing despite living in examples/, because getting it wrong is how a
home IP address ends up in a public repository, and because a bad environment
variable used to break the import rather than the connection.
"""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))

ENV_VARS = ("PYNCRAFT_HOST", "PYNCRAFT_ADDRESS", "PYNCRAFT_PORT", "PYNCRAFT_PLAYER")


@pytest.fixture
def connect(monkeypatch):
    """Reload connect.py with a given environment."""
    def build(**env):
        for name in ENV_VARS:
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        import connect as module
        return importlib.reload(module)
    return build


def test_defaults_to_localhost(connect):
    c = connect()
    assert c.DEFAULT_HOST == "localhost"
    assert c.DEFAULT_PORT == 4711
    assert c.DEFAULT_PLAYER == ""


def test_environment_overrides_all_three(connect):
    c = connect(PYNCRAFT_HOST="mc.example.org", PYNCRAFT_PORT="4712",
                PYNCRAFT_PLAYER="steve")
    assert (c.DEFAULT_HOST, c.DEFAULT_PORT, c.DEFAULT_PLAYER) == \
        ("mc.example.org", 4712, "steve")


def test_address_is_accepted_as_an_alias_for_host(connect):
    assert connect(PYNCRAFT_ADDRESS="alias.example.org").DEFAULT_HOST == "alias.example.org"


def test_host_wins_over_address(connect):
    c = connect(PYNCRAFT_HOST="wins.example.org", PYNCRAFT_ADDRESS="loses.example.org")
    assert c.DEFAULT_HOST == "wins.example.org"


@pytest.mark.parametrize("bad", ["not-a-number", "", "4711.5", "99999", "0", "-1"])
def test_a_bad_port_falls_back_instead_of_breaking_the_import(connect, bad):
    # This runs at import time. Raising here would blow up before any example's
    # own code ran, with a traceback pointing at connect.py rather than at the
    # environment variable that actually caused it.
    assert connect(PYNCRAFT_PORT=bad).DEFAULT_PORT == 4711


def test_command_line_arguments_default_from_the_environment(connect):
    import argparse
    c = connect(PYNCRAFT_HOST="mc.example.org", PYNCRAFT_PORT="4712")
    parser = argparse.ArgumentParser()
    c.add_arguments(parser)
    args = parser.parse_args([])
    assert (args.host, args.port) == ("mc.example.org", 4712)


def test_an_explicit_flag_beats_the_environment(connect):
    import argparse
    c = connect(PYNCRAFT_HOST="fromenv.example.org")
    parser = argparse.ArgumentParser()
    c.add_arguments(parser)
    assert parser.parse_args(["--host", "fromflag.example.org"]).host == "fromflag.example.org"


def test_connect_passes_what_it_was_given(connect, monkeypatch):
    c = connect(PYNCRAFT_HOST="ignored.example.org")
    seen = {}

    def fake_create(address, port, playerName):
        seen.update(address=address, port=port, playerName=playerName)
        return "connection"

    monkeypatch.setattr(c.Minecraft, "create", staticmethod(fake_create))
    assert c.connect("given.example.org", 4712, "steve") == "connection"
    assert seen == {"address": "given.example.org", "port": 4712, "playerName": "steve"}


def test_connect_falls_back_to_the_defaults(connect, monkeypatch):
    c = connect(PYNCRAFT_HOST="fromenv.example.org", PYNCRAFT_PORT="4712")
    seen = {}
    monkeypatch.setattr(c.Minecraft, "create",
                        staticmethod(lambda address, port, playerName: seen.update(
                            address=address, port=port, playerName=playerName)))
    c.connect()
    assert seen["address"] == "fromenv.example.org"
    assert seen["port"] == 4712


def test_no_example_hardcodes_a_server_address():
    """The whole point of connect.py.

    Every example pointed at one particular LAN address, so none of them worked
    for anybody else, and three work-in-progress ones carried a home external
    IP. This fails if that creeps back.
    """
    import re
    examples = Path(__file__).resolve().parent.parent / "examples"
    literal_ip = re.compile(r'address\s*=\s*["\']\d{1,3}(\.\d{1,3}){3}')
    offenders = [p.name for p in examples.glob("*.py")
                 if literal_ip.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert offenders == [], "hardcoded server address in: %s" % ", ".join(offenders)
