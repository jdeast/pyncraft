#!/usr/bin/env python3
"""Build a real place in Minecraft, from real elevation and real buildings.

    python build_town.py                       # the shipped data
    python build_town.py --host my.server      # somewhere else
    python build_town.py --clear               # take it away again

The data file was made by fetch_terrain.py from USGS lidar and OpenStreetMap.
One cell is one metre is one block, so the result is at true scale: if the
school is twelve metres tall, it is twelve blocks tall, and walking across the
playground takes as long as walking across the playground.

This is the shape every "real data in Minecraft" example takes -- get
coordinates out of a professional source, turn them into blocks -- and it is
short because mc.buildVoxels does the hard part. A 400 by 400 metre town is
several hundred thousand blocks; sent one at a time that is minutes of waiting,
so instead the shape is split into maximal boxes and each is filled with one
command.

The buildings are shells: correct footprint, correct height, hollow inside.
Nothing about the interiors comes from the data, and for a school that is on
purpose -- see the note at the top of fetch_terrain.py. Decide for yourself
what goes inside; that is the better half of the project anyway.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np
except ImportError:
    sys.exit("This needs numpy: pip install numpy")

import connect
from pyncraft.minecraft import Minecraft

# The ground, from the surface down, then whatever is beneath all of it.
# Chosen per body, because grass on Mars would be a lie told in the first
# second of looking at it.
PALETTES = {
    "earth": {
        "soil": ["GRASS_BLOCK", "DIRT", "DIRT", "COARSE_DIRT"],
        "deep": "STONE",
    },
    "mars": {
        # Rust, getting darker with depth. Red sand on top because the surface
        # really is dust, and it behaves like dust when you dig it.
        "soil": ["RED_SAND", "RED_SAND", "RED_TERRACOTTA", "TERRACOTTA"],
        "deep": "GRANITE",
    },
    "moon": {
        # Regolith is grey and almost colourless, and the point of the Moon is
        # the shape rather than the palette.
        "soil": ["LIGHT_GRAY_CONCRETE_POWDER", "LIGHT_GRAY_CONCRETE_POWDER",
                 "GRAY_CONCRETE_POWDER", "GRAY_CONCRETE"],
        "deep": "DEEPSLATE",
    },
}

WALL = "WHITE_CONCRETE"
ROOF = "GRAY_CONCRETE"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load(name):
    path = os.path.join(DATA_DIR, name + ".npz")
    if not os.path.exists(path):
        sys.exit("No data called %r.\nRun:  python fetch_terrain.py --name %s" % (name, name))
    d = np.load(path)
    return d["ground"], d["buildings"], json.loads(str(d["meta"]))


def to_voxels(ground, buildings, base_y, depth, hollow=True, body="earth"):
    """Turn two heightmaps into one labelled array ready for buildVoxels.

    Labels rather than materials, so the whole town is one array and one call:
    1..len(soil) are the soil layers, then stone, then walls and roof.
    """
    palette_for = PALETTES.get(body, PALETTES["earth"])
    soil = palette_for["soil"]
    deep = palette_for["deep"]

    # Gaps in the data become the lowest point rather than a hole, so a crater
    # floor does not end up with a pit through the middle of it.
    ground = np.nan_to_num(ground, nan=float(np.nanmin(ground)))

    # Everything measured from the lowest point, so the build sits on top of
    # base_y rather than wherever sea level happens to be.
    floor = float(ground.min())
    ground_h = np.rint(ground - floor).astype(int) + depth
    build_h = np.rint(buildings).astype(int)

    nx, nz = ground.shape
    height = int(ground_h.max() + max(build_h.max(), 0)) + 1
    world = np.zeros((nx, height, nz), dtype=np.int32)

    stone = len(soil) + 1
    wall = stone + 1
    roof = wall + 1

    # Ground. Columns, filled from the bottom: stone, then the soil layers with
    # grass on top.
    for x in range(nx):
        col = ground_h[x]
        for z in range(nz):
            top = col[z]
            world[x, :top, z] = stone
            for i, _ in enumerate(soil):
                y = top - 1 - i
                if y >= 0:
                    world[x, y, z] = len(soil) - i

    # Buildings, standing on the ground.
    solid = build_h > 0
    for x in range(nx):
        for z in range(nz):
            if not solid[x, z]:
                continue
            base = ground_h[x, z]
            top = base + build_h[x, z]
            world[x, base:top, z] = wall
            if top - 1 < height:
                world[x, top - 1, z] = roof

    if hollow:
        # Carve the inside out, leaving a one-block shell. Without this a town
        # is a solid lump: many more blocks, and you cannot walk into anything.
        inner = solid.copy()
        inner[0, :] = inner[-1, :] = inner[:, 0] = inner[:, -1] = False
        # A cell is interior only if all four neighbours are also building.
        inner[1:-1, 1:-1] &= (solid[:-2, 1:-1] & solid[2:, 1:-1]
                              & solid[1:-1, :-2] & solid[1:-1, 2:])
        for x in range(nx):
            for z in range(nz):
                if not inner[x, z]:
                    continue
                base = ground_h[x, z]
                top = base + build_h[x, z]
                # Keep the floor and the roof, hollow the rest.
                if top - 1 > base + 1:
                    world[x, base + 1:top - 1, z] = 0

    palette = soil + [deep, WALL, ROOF]
    return world, palette


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    connect.add_arguments(p)
    p.add_argument("--name", default="roberts", help="which data file to build")
    p.add_argument("--at", nargs=3, type=int, metavar=("X", "Y", "Z"),
                   help="where to put the corner (default: where you are standing)")
    p.add_argument("--depth", type=int, default=4,
                   help="blocks of ground beneath the lowest point (default 4)")
    p.add_argument("--solid", action="store_true",
                   help="fill the buildings in rather than leaving shells")
    p.add_argument("--clear", action="store_true", help="remove a previous build")
    p.add_argument("--dry-run", action="store_true",
                   help="work out the commands but send nothing")
    args = p.parse_args()

    ground, buildings, meta = load(args.name)
    body = meta.get("body", "earth")
    scale = meta.get("metres_per_cell", 1.0)
    where = meta.get("what") or "%.4f, %.4f" % (meta.get("lat", 0), meta.get("lon", 0))

    print("%s -- %s" % (args.name, where))
    print("  %dx%d cells at %.0f m each = %.1f x %.1f km"
          % (ground.shape[0], ground.shape[1], scale,
             ground.shape[0] * scale / 1000.0, ground.shape[1] * scale / 1000.0))
    if meta.get("vscale", 1.0) != 1.0:
        print("  heights exaggerated x%.1f" % meta["vscale"])
    if int((buildings > 0).sum()):
        print("  %d building cells" % int((buildings > 0).sum()))

    world, palette = to_voxels(ground, buildings, 0, args.depth,
                               hollow=not args.solid, body=body)
    blocks = int((world != 0).sum())
    print("%d blocks, %d high" % (blocks, world.shape[1]))

    if args.dry_run:
        from pyncraft import voxel
        t = time.time()
        n = sum(1 for _ in voxel.decompose(world))
        print("would send %d commands (%.0fx fewer than one per block), planned in %.1fs"
              % (n, blocks / max(n, 1), time.time() - t))
        return

    # connect_from_args builds its own parser and is for scripts that have
    # none; this one does, so hand over the values it already parsed.
    mc = connect.connect(args.host, args.port, args.player)

    if args.at:
        x, y, z = args.at
    else:
        pos = mc.player.getTilePos()
        x, y, z = pos.x, pos.y, pos.z
    print("building at %d, %d, %d" % (x, y, z))

    if args.clear:
        nx, ny, nz = world.shape
        mc.setBlocks(x, y, z, x + nx - 1, y + ny - 1, z + nz - 1, "AIR")
        print("cleared")
        return

    t = time.time()
    sent = mc.buildVoxels(world, palette=palette, origin=(x, y, z))
    dt = time.time() - t
    print("sent %d commands in %.1fs -- %.0f blocks per second, %.0fx fewer commands"
          % (sent, dt, blocks / max(dt, 0.01), blocks / max(sent, 1)))
    mc.postToChat("Built %s: %d blocks" % (args.name, blocks))


if __name__ == "__main__":
    main()
