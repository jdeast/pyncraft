"""Connect an example to a Minecraft server running the FruitJuice plugin.

Defaults to localhost, which is right when the server is on the same machine as
the code -- the usual case when someone is learning. Point it elsewhere with
--host, or set PYNCRAFT_HOST once so every example picks it up:

    python rainbow.py                        # localhost
    python rainbow.py --host mc.example.org  # somewhere else
    export PYNCRAFT_HOST=mc.example.org      # for the whole session

The address deliberately does not live in the examples themselves. A hardcoded
address is wrong for everyone except the person who wrote it, and if it happens
to be a home IP address it is also something you did not mean to publish.
"""

import argparse
import os
import sys

from pyncraft.minecraft import Minecraft

def _port_from_environment(default=4711):
    """PYNCRAFT_PORT, or the default if it is missing or not a usable port.

    Deliberately does not raise. This runs at import time, so a typo in the
    variable would otherwise blow up with a ValueError before any example got
    to run, and the traceback would point at this line rather than at the
    environment variable that actually caused it.
    """
    raw = os.environ.get("PYNCRAFT_PORT")
    if raw is None:
        return default
    try:
        port = int(raw)
    except ValueError:
        print("Ignoring PYNCRAFT_PORT=%r: not a number. Using %d."
              % (raw, default), file=sys.stderr)
        return default
    if not 1 <= port <= 65535:
        print("Ignoring PYNCRAFT_PORT=%d: not a valid port. Using %d."
              % (port, default), file=sys.stderr)
        return default
    return port


# PYNCRAFT_ADDRESS is accepted as well, because it reads just as naturally and
# is the name the RCON work in PR #3 reached for.
DEFAULT_HOST = (os.environ.get("PYNCRAFT_HOST")
                or os.environ.get("PYNCRAFT_ADDRESS")
                or "localhost")
DEFAULT_PORT = _port_from_environment()
DEFAULT_PLAYER = os.environ.get("PYNCRAFT_PLAYER", "")


def add_arguments(parser):
    """Add --host/--port/--player to an existing parser.

    For examples that already parse arguments of their own.
    """
    parser.add_argument(
        "--host", default=DEFAULT_HOST,
        help="server address (default: %(default)s, or $PYNCRAFT_HOST)")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help="FruitJuice port (default: %(default)s)")
    parser.add_argument(
        "--player", default=DEFAULT_PLAYER,
        help="which player to control, if more than one is online")
    return parser


def connect(host=None, port=None, player=None):
    """Connect, falling back to the defaults above."""
    return Minecraft.create(
        address=host or DEFAULT_HOST,
        port=port or DEFAULT_PORT,
        playerName=DEFAULT_PLAYER if player is None else player)


def connect_from_args(description=None, argv=None):
    """Parse --host/--port/--player and connect. Returns (mc, args).

    For examples with no arguments of their own.
    """
    parser = argparse.ArgumentParser(description=description)
    add_arguments(parser)
    args = parser.parse_args(argv)
    return connect(args.host, args.port, args.player), args
