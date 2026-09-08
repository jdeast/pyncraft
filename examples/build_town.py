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

# Blocks that fall when nothing holds them up, and what to use instead.
#
# This matters only because a crust floats, and it very nearly does not
# announce itself. Blocks are placed with physics off -- deliberately, because
# running block physics for every one of half a million placements is what
# stalled the server and got it killed by the watchdog -- so gravity is never
# evaluated at build time and a crust of regolith sits in mid-air looking
# perfectly solid. It stays that way until anything at all causes a block
# update nearby. Mine one block and the update spreads, every neighbour
# discovers it is unsupported, and the landscape drains away.
#
# The Moon's top three layers were concrete powder and Mars's top two were red
# sand, so both were a landslide waiting for the first pickaxe. The substitutes
# are chosen to keep the colour: the point of the palette is that regolith is
# grey, not that it is dust.
_COLOURS = ("WHITE", "ORANGE", "MAGENTA", "LIGHT_BLUE", "YELLOW", "LIME",
            "PINK", "GRAY", "LIGHT_GRAY", "CYAN", "PURPLE", "BLUE", "BROWN",
            "GREEN", "RED", "BLACK")
FALLING = {"%s_CONCRETE_POWDER" % c: "%s_CONCRETE" % c for c in _COLOURS}
FALLING.update({
    "SAND": "SANDSTONE",
    "SUSPICIOUS_SAND": "SANDSTONE",
    "RED_SAND": "RED_SANDSTONE",
    "GRAVEL": "COBBLESTONE",
    "SUSPICIOUS_GRAVEL": "COBBLESTONE",
    "ANVIL": "IRON_BLOCK",
    "POINTED_DRIPSTONE": "DRIPSTONE_BLOCK",
    "SCAFFOLDING": "OAK_PLANKS",
    "DRAGON_EGG": "OBSIDIAN",
})


def anchored(material):
    """The nearest block of the same colour that stays where it is put."""
    return FALLING.get(material, material)


WALL = "WHITE_CONCRETE"
ROOF = "GRAY_CONCRETE"

# What each land-cover kind is made of, keyed by the small integers
# fetch_terrain.py writes into the surface layer. Chosen to look like the thing
# rather than to be maximally visible: a road should read as a road from ground
# level, not as a stripe on a map.
SURFACE_BLOCKS = {
    1:  "GRASS_BLOCK",            # grass
    2:  "GRASS_BLOCK",            # park
    3:  "GRASS_BLOCK",            # schoolyard
    4:  "SAND",                   # sand
    5:  "COARSE_DIRT",            # dirt
    6:  "GRAY_CONCRETE",          # asphalt
    7:  "LIGHT_GRAY_CONCRETE",    # concrete
    8:  "CYAN_TERRACOTTA",        # parking, worn asphalt
    9:  "BLACK_CONCRETE",         # road
    10: "LIGHT_GRAY_CONCRETE",    # footway or pavement
    11: "BROWN_TERRACOTTA",       # playground, wood chips and rubber matting
    12: "GREEN_CONCRETE",         # a hard court, painted the way they are here
    13: "MOSS_BLOCK",             # a grass pitch, a shade off the ordinary grass
    14: "WATER",                  # water
    15: "WHITE_CONCRETE",         # a painted crossing
}

# A tree, as a trunk and a blob of leaves. Not botany, but a street of houses
# reads completely differently with them.
TRUNK = "OAK_LOG"
LEAVES = "OAK_LEAVES"

# The small things, as a list of (dx, dy, dz, block) offsets from the point.
# None of them are mapped around Roberts Elementary, which is rather the point:
# the moment somebody adds a swing to OpenStreetMap it appears in their build,
# which is a far better reason to edit a map than being told to.
#
# Deliberately crude. A swing made of two posts and a bar is recognisably a
# swing from across a playground, and anything fussier would be invisible at
# one block to the metre and wrong at any other scale.
PROPS = {
    "play_swing": [(0, 0, 0, "OAK_FENCE"), (0, 1, 0, "OAK_FENCE"),
                   (2, 0, 0, "OAK_FENCE"), (2, 1, 0, "OAK_FENCE"),
                   (0, 2, 0, "OAK_FENCE"), (1, 2, 0, "OAK_FENCE"),
                   (2, 2, 0, "OAK_FENCE"),
                   (1, 1, 0, "OAK_HANGING_SIGN")],
    "play_slide": [(0, 0, 0, "OAK_PLANKS"), (0, 1, 0, "OAK_PLANKS"),
                   (0, 2, 0, "OAK_PLANKS"), (1, 2, 0, "SMOOTH_STONE_SLAB"),
                   (2, 1, 0, "SMOOTH_STONE_SLAB"), (3, 0, 0, "SMOOTH_STONE_SLAB")],
    "play_climbingframe": [(0, 0, 0, "OAK_FENCE"), (0, 1, 0, "OAK_FENCE"),
                           (2, 0, 0, "OAK_FENCE"), (2, 1, 0, "OAK_FENCE"),
                           (0, 0, 2, "OAK_FENCE"), (0, 1, 2, "OAK_FENCE"),
                           (2, 0, 2, "OAK_FENCE"), (2, 1, 2, "OAK_FENCE"),
                           (1, 2, 1, "OAK_PLANKS"), (0, 2, 1, "OAK_PLANKS"),
                           (2, 2, 1, "OAK_PLANKS"), (1, 2, 0, "OAK_PLANKS"),
                           (1, 2, 2, "OAK_PLANKS")],
    "play_sandpit": [(dx, 0, dz, "SAND") for dx in range(-1, 2) for dz in range(-1, 2)],
    "play_seesaw": [(0, 0, 0, "COBBLESTONE"), (-1, 0, 0, "OAK_SLAB"),
                    (1, 1, 0, "OAK_SLAB"), (2, 1, 0, "OAK_SLAB")],
    "play_roundabout": [(dx, 0, dz, "SMOOTH_STONE_SLAB")
                        for dx in range(-1, 2) for dz in range(-1, 2)
                        if abs(dx) + abs(dz) <= 2],
    "play_springy": [(0, 0, 0, "OAK_FENCE"), (0, 1, 0, "OAK_SLAB")],
    "play_structure": [(0, 0, 0, "OAK_PLANKS"), (0, 1, 0, "OAK_PLANKS"),
                       (1, 0, 0, "OAK_FENCE"), (0, 0, 1, "OAK_FENCE"),
                       (0, 2, 0, "OAK_SLAB")],
    "play_basketswing": [(0, 0, 0, "OAK_FENCE"), (0, 1, 0, "OAK_FENCE"),
                         (2, 0, 0, "OAK_FENCE"), (2, 1, 0, "OAK_FENCE"),
                         (1, 1, 0, "OAK_TRAPDOOR")],
    "play_climbingwall": [(0, 0, 0, "COBBLESTONE"), (0, 1, 0, "COBBLESTONE"),
                          (0, 2, 0, "COBBLESTONE"), (1, 0, 0, "COBBLESTONE"),
                          (1, 1, 0, "COBBLESTONE")],
    "play_monkeybar": [(0, 0, 0, "OAK_FENCE"), (0, 1, 0, "OAK_FENCE"),
                       (3, 0, 0, "OAK_FENCE"), (3, 1, 0, "OAK_FENCE"),
                       (1, 2, 0, "OAK_FENCE"), (2, 2, 0, "OAK_FENCE"),
                       (0, 2, 0, "OAK_FENCE"), (3, 2, 0, "OAK_FENCE")],

    "bench": [(0, 0, 0, "OAK_STAIRS"), (1, 0, 0, "OAK_STAIRS")],
    "waste_basket": [(0, 0, 0, "CAULDRON")],
    "drinking_water": [(0, 0, 0, "STONE_BRICKS"), (0, 1, 0, "STONE_BRICK_SLAB")],
    "bicycle_parking": [(0, 0, 0, "OAK_FENCE"), (1, 0, 0, "OAK_FENCE")],
    "street_lamp": [(0, 0, 0, "COBBLESTONE_WALL"), (0, 1, 0, "COBBLESTONE_WALL"),
                    (0, 2, 0, "COBBLESTONE_WALL"), (0, 3, 0, "LANTERN")],
    "bus_stop": [(0, 0, 0, "COBBLESTONE_WALL"), (0, 1, 0, "COBBLESTONE_WALL"),
                 (0, 2, 0, "OAK_SIGN")],
    "fire_hydrant": [(0, 0, 0, "RED_CONCRETE")],
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load(name):
    path = os.path.join(DATA_DIR, name + ".npz")
    if not os.path.exists(path):
        sys.exit("No data called %r.\nRun:  python fetch_terrain.py --name %s" % (name, name))
    d = np.load(path)
    # Files fetched before land cover existed have no surface layer; an empty
    # one means "whatever the body's default soil is", which is what they got.
    surface = d["surface"] if "surface" in d.files else np.zeros(d["ground"].shape,
                                                                dtype=np.uint8)
    mats = (d["building_materials"] if "building_materials" in d.files
            else np.zeros(d["ground"].shape, dtype=np.uint8))
    ids = (d["building_ids"] if "building_ids" in d.files
           else np.zeros(d["ground"].shape, dtype=np.uint16))
    trees = d["trees"] if "trees" in d.files else np.zeros((0, 3), dtype=np.float32)
    return (d["ground"], d["buildings"], surface, mats, ids, trees,
            json.loads(str(d["meta"])))


def edge_distance(mask):
    """How many cells in from the edge of a shape each cell is.

    Iterative erosion rather than scipy: the footprints are small, this is a
    handful of array operations each, and it saves a dependency that would have
    to compile on a school laptop.
    """
    d = np.zeros(mask.shape, dtype=np.int32)
    current = mask.copy()
    step = 0
    while current.any():
        step += 1
        inner = current.copy()
        inner[1:, :] &= current[:-1, :]
        inner[:-1, :] &= current[1:, :]
        inner[:, 1:] &= current[:, :-1]
        inner[:, :-1] &= current[:, 1:]
        inner[0, :] = inner[-1, :] = False
        inner[:, 0] = inner[:, -1] = False
        d[current & ~inner] = step
        current = inner
    return d


def roof_profile(mask, shape, peak):
    """How many blocks the roof rises above the walls, per cell.

    Only the shapes that actually change the silhouette are distinguished.
    A gabled roof and a hipped roof look quite different from the street; a
    gambrel and a mansard do not, at one block per metre, so they borrow the
    nearest one rather than pretending to a precision the grid cannot show.
    """
    if peak <= 0 or shape in ("flat", "", None):
        return np.zeros(mask.shape, dtype=np.int32)

    if shape in ("skillion", "lean_to", "shed"):
        # A single slope, low side to high side, across the longer axis.
        rows, cols = np.where(mask)
        if not len(rows):
            return np.zeros(mask.shape, dtype=np.int32)
        if np.ptp(rows) >= np.ptp(cols):
            t = (np.arange(mask.shape[0])[:, None] - rows.min()) / max(np.ptp(rows), 1)
            t = np.broadcast_to(t, mask.shape)
        else:
            t = (np.arange(mask.shape[1])[None, :] - cols.min()) / max(np.ptp(cols), 1)
            t = np.broadcast_to(t, mask.shape)
        return np.where(mask, np.rint(t * peak), 0).astype(np.int32)

    if shape in ("gabled", "gambrel", "half-hipped", "round", "barrel"):
        # A ridge down the longer axis: height falls off across the short one.
        rows, cols = np.where(mask)
        if not len(rows):
            return np.zeros(mask.shape, dtype=np.int32)
        if np.ptp(rows) >= np.ptp(cols):
            mid = (cols.min() + cols.max()) / 2.0
            span = max((cols.max() - cols.min()) / 2.0, 1.0)
            d = np.abs(np.arange(mask.shape[1])[None, :] - mid) / span
        else:
            mid = (rows.min() + rows.max()) / 2.0
            span = max((rows.max() - rows.min()) / 2.0, 1.0)
            d = np.abs(np.arange(mask.shape[0])[:, None] - mid) / span
        d = np.broadcast_to(d, mask.shape)
        return np.where(mask, np.rint((1.0 - np.clip(d, 0, 1)) * peak), 0).astype(np.int32)

    # hipped, pyramidal, dome, onion, mansard: falls away towards every edge.
    d = edge_distance(mask).astype(float)
    if d.max() <= 0:
        return np.zeros(mask.shape, dtype=np.int32)
    profile = d / d.max()
    if shape in ("dome", "onion", "round"):
        profile = np.sqrt(np.clip(profile, 0, 1))     # rounded rather than conical
    return np.where(mask, np.rint(profile * peak), 0).astype(np.int32)


def to_voxels(ground, buildings, base_y, depth, hollow=True, body="earth",
              north="-Z", surface=None, materials=None, material_palette=None,
              metres_per_cell=1.0, building_ids=None, trees=None, roof_info=None,
              prop_kinds=None, crust=None):
    """Turn two heightmaps into one labelled array ready for buildVoxels.

    Labels rather than materials, so the whole town is one array and one call:
    1..len(soil) are the soil layers, then stone, then walls and roof.
    """
    # Rasters are [row, col] with row 0 north and col 0 west. Transposing makes
    # the column index X, so +X is east either way.
    #
    # Getting this wrong is quiet. Mapping row->X and col->Z, which is what the
    # obvious loop over ground.shape does, is not a rotation but a REFLECTION
    # across the NW-SE diagonal: north-west and south-east stay put while
    # north-east and south-west swap. A rotated map announces itself; a mirrored
    # one looks entirely convincing. Roberts was built that way and nobody
    # noticed until someone asked which way was north.
    ground = np.asarray(ground).T
    buildings = np.asarray(buildings).T
    surface = None if surface is None else np.asarray(surface).T
    materials = None if materials is None else np.asarray(materials).T
    building_ids = None if building_ids is None else np.asarray(building_ids).T

    # Which way north points.
    #
    # "-Z" is Minecraft's own north, and the default, because the point of
    # building a real place is that it looks like the real place: stand in it
    # with a compass, or open F3, and the directions agree with the ones you
    # would get standing there. Sunrise is in the east in both.
    #
    # "+Z" is map and graph-paper convention instead -- x to the right, z up
    # the page -- which suits a coordinate worked out on paper, at the cost of
    # running north-south opposite to everything in the game.
    if north == "+Z":
        ground = ground[:, ::-1]
        buildings = buildings[:, ::-1]
        if surface is not None:
            surface = surface[:, ::-1]
        if materials is not None:
            materials = materials[:, ::-1]
        if building_ids is not None:
            building_ids = building_ids[:, ::-1]
    elif north != "-Z":
        raise ValueError("north must be '+Z' (map convention) or '-Z' (Minecraft's own)")

    palette_for = PALETTES.get(body, PALETTES["earth"])
    soil = palette_for["soil"]
    deep = palette_for["deep"]

    # Gaps in the data become the lowest point rather than a hole, so a crater
    # floor does not end up with a pit through the middle of it.
    ground = np.nan_to_num(ground, nan=float(np.nanmin(ground)))

    # Metres to blocks.
    #
    # Both heightmaps are in METRES, and one block is metres_per_cell across --
    # so a block is that tall too, and the build keeps true proportions. At one
    # metre per cell the two numbers are equal and this does nothing, which is
    # exactly why it went unnoticed: at 0.25 m per cell a 12 m school came out
    # 12 blocks, which is 3 m, which is one storey rather than four.
    per_block = float(metres_per_cell) if metres_per_cell else 1.0

    # Everything measured from the lowest point, so the build sits on top of
    # base_y rather than wherever sea level happens to be.
    floor = float(ground.min())
    ground_h = np.rint((ground - floor) / per_block).astype(int) + depth
    build_h = np.rint(buildings / per_block).astype(int)

    nx, nz = ground.shape
    height = int(ground_h.max() + max(build_h.max(), 0)) + 1
    world = np.zeros((nx, height, nz), dtype=np.int32)

    stone = len(soil) + 1
    wall = stone + 1
    roof = wall + 1

    # Land cover materials come after everything else in the palette, so the
    # soil labels keep the numbers the rest of this function expects.
    extra = []
    label_for_surface = {}
    if surface is not None:
        for code in np.unique(surface):
            if code == 0:
                continue
            material = SURFACE_BLOCKS.get(int(code))
            if material is None:
                continue
            if material not in extra:
                extra.append(material)
            label_for_surface[int(code)] = roof + 1 + extra.index(material)

    # Ground. Columns filled from the bottom: stone, then the soil layers, with
    # SOIL[0] on top.
    #
    # CRUST. Filling every column from the floor costs blocks in proportion to
    # the relief, which is fine for a town on a metre of slope and ruinous for
    # a landscape. Hadley Rille is 200 m deep; at 2 m to the block that is a
    # hundred blocks of stone under every square of plain, and a 400 m square
    # comes to 850,000 blocks -- more than has crashed this server before.
    # With crust=5 the same square is 200,000 whatever the relief, because the
    # cost stops depending on the depth of the valley. You are walking on the
    # surface either way; the difference is only visible from underneath, and
    # from underneath there is nothing to see.
    #
    # But a FLAT crust is both too much and too little. Too much because on
    # level ground one block is plenty -- nothing can see past it. Too little
    # because where the ground drops sharply, a column whose neighbour sits
    # more than `crust` blocks below it has daylight under its lip, and you
    # see straight through the wall of the valley you came to look at.
    #
    # So `crust` is a MINIMUM, and each column is thickened to cover the drop
    # to its lowest neighbour. On Hadley Rille that turns 1.37M blocks into
    # 310k -- four times cheaper -- while closing 671 columns of holes that a
    # flat crust of five left open, because the deepest drop there is 81
    # blocks and no sane constant covers it.
    #
    # The label is i + 1, not len(soil) - i. The latter reads the list
    # backwards and buries the grass: yards came out coarse dirt with the turf
    # three blocks down, and Mars had terracotta on top instead of red sand.
    # Anywhere with a land-cover tag was painted over afterwards and looked
    # right, so only the untagged ground -- which is to say people's gardens --
    # showed it.
    # How far below each column's top its lowest neighbour sits. Off the edge
    # of the map there is no neighbour, so nothing is required there and the
    # rim comes out thin, which is what a cut-out of terrain should look like.
    thickness = None
    if crust is not None:
        drop = np.zeros_like(ground_h)
        for axis in (0, 1):
            for step in (1, -1):
                shifted = np.roll(ground_h, step, axis=axis)
                if axis == 0:
                    if step == 1:
                        shifted[0, :] = ground_h[0, :]
                    else:
                        shifted[-1, :] = ground_h[-1, :]
                else:
                    if step == 1:
                        shifted[:, 0] = ground_h[:, 0]
                    else:
                        shifted[:, -1] = ground_h[:, -1]
                drop = np.maximum(drop, ground_h - shifted)
        thickness = np.maximum(int(crust), np.maximum(drop, 0))

    for x in range(nx):
        col = ground_h[x]
        for z in range(nz):
            top = col[z]
            bottom = 0 if crust is None else max(0, top - int(thickness[x, z]))
            world[x, bottom:top, z] = stone
            for i, _ in enumerate(soil):
                y = top - 1 - i
                if y >= 0 and y >= bottom:
                    world[x, y, z] = i + 1

    # The top block of each column, where the land cover says what it is. Only
    # the surface changes: what a road is made of underneath is still soil, and
    # a build that replaced whole columns would take four times the blocks to
    # no visible effect.
    if surface is not None and label_for_surface:
        for x in range(nx):
            for z in range(nz):
                code = int(surface[x, z])
                if not code:
                    continue
                label = label_for_surface.get(code)
                if label is None:
                    continue
                top = ground_h[x, z] - 1
                if top >= 0:
                    world[x, top, z] = label

    # Per-building wall and roof materials, where the fetcher recorded them.
    # Without this every building is the same white box and the red brick
    # school is indistinguishable from the house next door.
    wall_label = {}
    roof_label = {}
    if materials is not None and material_palette:
        for i, pair in enumerate(material_palette):
            w_mat, r_mat = (pair[0], pair[1]) if len(pair) == 2 else (WALL, ROOF)
            for mat, table in ((w_mat, wall_label), (r_mat, roof_label)):
                if mat not in extra:
                    extra.append(mat)
                table[i + 1] = roof + 1 + extra.index(mat)

    # One floor level per building.
    #
    # Letting every column sit on its own patch of ground makes the floor and
    # the roof follow the terrain, so a building on a metre of slope gets a
    # roof a metre out of level. Real buildings are built on a level
    # foundation, and the roof is the thing that shows it.
    #
    # The lowest ground under the footprint is the level used, so the uphill
    # side is embedded rather than the downhill side left floating.
    base_for = {}
    if building_ids is not None:
        for bid in np.unique(building_ids):
            if bid == 0:
                continue
            base_for[int(bid)] = int(ground_h[building_ids == bid].min())

    # Buildings, standing on the ground.
    solid = build_h > 0
    for x in range(nx):
        for z in range(nz):
            if not solid[x, z]:
                continue
            bid = int(building_ids[x, z]) if building_ids is not None else 0
            base = base_for.get(bid, ground_h[x, z])
            top = base + build_h[x, z]
            code = int(materials[x, z]) if materials is not None else 0
            w_lab = wall_label.get(code, wall)
            r_lab = roof_label.get(code, roof)
            world[x, base:top, z] = w_lab
            if top - 1 < height:
                world[x, top - 1, z] = r_lab

    # Pitched roofs, where the building says it has one. Built after the walls
    # so the flat top is already there to sit on, and before the hollowing so a
    # pitched roof is left solid rather than carved into a shell.
    if roof_info and building_ids is not None:
        for bid_s, info in roof_info.items():
            bid = int(bid_s)
            peak_m = float(info.get("height") or 0.0)
            shape_name = (info.get("shape") or "flat").lower()
            if peak_m <= 0 or shape_name in ("flat", ""):
                continue
            mask = building_ids == bid
            if not mask.any():
                continue
            rows, cols = np.where(mask)
            r0, r1 = rows.min(), rows.max() + 1
            c0, c1 = cols.min(), cols.max() + 1
            sub = mask[r0:r1, c0:c1]
            peak = int(round(peak_m / per_block))
            profile = roof_profile(sub, shape_name, peak)
            base = base_for.get(bid, 0)
            wall_top = base + int(build_h[mask].max())
            r_lab = roof_label.get(int(materials[rows[0], cols[0]])
                                   if materials is not None else 0, roof)
            for i in range(sub.shape[0]):
                for j in range(sub.shape[1]):
                    rise = int(profile[i, j])
                    if rise <= 0:
                        continue
                    x, z = r0 + i, c0 + j
                    for y in range(wall_top, min(wall_top + rise, height)):
                        world[x, y, z] = r_lab

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
                bid = int(building_ids[x, z]) if building_ids is not None else 0
                base = base_for.get(bid, ground_h[x, z])
                top = base + build_h[x, z]
                # Keep the floor and the roof, hollow the rest.
                if top - 1 > base + 1:
                    world[x, base + 1:top - 1, z] = 0

    # The small things last, so they stand on whatever the ground turned out
    # to be rather than being buried by it.
    if trees is not None and len(trees):
        if TRUNK not in extra:
            extra.append(TRUNK)
        if LEAVES not in extra:
            extra.append(LEAVES)
        trunk_label = roof + 1 + extra.index(TRUNK)
        leaf_label = roof + 1 + extra.index(LEAVES)

        def label_for(material):
            if material not in extra:
                extra.append(material)
            return roof + 1 + extra.index(material)

        for entry in trees:
            row, col, height_m = entry[0], entry[1], entry[2]
            kind_index = int(entry[3]) if len(entry) > 3 else 0
            kind = (prop_kinds[kind_index]
                    if prop_kinds and kind_index < len(prop_kinds) else "tree")
            if kind != "tree":
                # Anything that is not a tree is a little arrangement of blocks.
                recipe = PROPS.get(kind)
                if not recipe:
                    continue
                x = int(col)
                z = int(row) if north == "-Z" else (nz - 1 - int(row))
                if not (0 <= x < nx and 0 <= z < nz):
                    continue
                base = int(ground_h[x, z])
                for dx, dy, dz, material in recipe:
                    px, py, pz = x + dx, base + dy, z + dz
                    if (0 <= px < nx and 0 <= pz < nz and 0 <= py < height
                            and world[px, py, pz] == 0):
                        world[px, py, pz] = label_for(material)
                continue
            # Same axis handling as everything else: column becomes X, row
            # becomes Z, flipped if north is +Z.
            x = int(col)
            z = int(row) if north == "-Z" else (nz - 1 - int(row))
            if not (0 <= x < nx and 0 <= z < nz):
                continue
            base = int(ground_h[x, z])
            trunk = max(int(round(height_m / per_block * 0.55)), 2)
            crown = max(int(round(height_m / per_block * 0.45)), 2)
            for y in range(base, min(base + trunk, height)):
                world[x, y, z] = trunk_label
            r = max(crown // 2, 1)
            top = base + trunk
            for dy in range(-r, crown - r):
                for dx in range(-r, r + 1):
                    for dz in range(-r, r + 1):
                        if dx * dx + dy * dy + dz * dz > r * r + 1:
                            continue
                        px, py, pz = x + dx, top + dy, z + dz
                        if (0 <= px < nx and 0 <= pz < nz and 0 <= py < height
                                and world[px, py, pz] == 0):
                            world[px, py, pz] = leaf_label

    palette = soil + [deep, WALL, ROOF] + extra
    if crust is not None:
        # Only when there is a crust. A build filled to the floor rests on
        # something, so sand on Mars can behave like sand, which is half the
        # reason it is sand.
        palette = [anchored(m) for m in palette]
    return world, palette


def place_house_numbers(mc, meta, building_ids, buildings, ground, surface,
                        ox, oy, oz, scale, depth, world_shape):
    """A sign with the house number, on the ground outside each building.

    OSM carries addr:housenumber on three quarters of the buildings here, which
    is a lot of information going spare. Whether it is worth having is a matter
    of taste and easy to find out: it is behind a flag.

    The sign goes on the first free cell just outside the footprint, preferring
    a side that faces a path or a road, because that is where the front door is.
    """
    info = meta.get("roof_info") or {}
    # Number on the first line, street on the second. A real house sign does
    # not carry the street name, but this is a map you are standing inside and
    # the street is the thing that tells you where you are.
    numbers = {int(k): (v.get("addr", ""), v.get("street", ""))
               for k, v in info.items() if v.get("addr")}
    if not numbers:
        return 0

    ids = np.asarray(building_ids).T
    solid = np.asarray(buildings).T > 0
    surf = np.asarray(surface).T
    g = np.nan_to_num(np.asarray(ground).T, nan=float(np.nanmin(ground)))
    per_block = float(scale) if scale else 1.0
    floor = float(g.min())
    ground_h = np.rint((g - floor) / per_block).astype(int) + depth

    legend = meta.get("surface_legend") or {}
    # Named street_codes, not street: the loop below binds street to the name
    # on the sign, and shadowing this set made every lookup a type error.
    street_codes = {legend.get("path"), legend.get("road"), legend.get("parking")}
    street_codes.discard(None)

    nx, _, nz = world_shape
    placed = 0
    for bid, (number, street) in numbers.items():
        cells = np.where(ids == bid)
        if not len(cells[0]):
            continue
        # Walk the footprint's edge looking for a neighbour that is outdoors,
        # and prefer one that is pavement or road.
        best = None
        for cx, cz in zip(*cells):
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                px, pz = int(cx) + dx, int(cz) + dz
                if not (0 <= px < nx and 0 <= pz < nz):
                    continue
                if solid[px, pz]:
                    continue
                score = 2 if int(surf[px, pz]) in street_codes else 1
                if best is None or score > best[0]:
                    best = (score, px, pz, dx, dz)
            if best and best[0] == 2:
                break
        if best is None:
            continue
        _, px, pz, dx, dz = best

        # Face the sign away from the building it belongs to, which is the way
        # somebody walking up the street would read it. Every sign faced north
        # before, so half of them were readable only from inside a house.
        #
        # +X is east and +Z is south, which is Minecraft's own convention and
        # the one the rest of the build uses.
        facing = {(1, 0): "EAST", (-1, 0): "WEST",
                  (0, 1): "SOUTH", (0, -1): "NORTH"}.get((dx, dz), "NORTH")
        sy = oy + int(ground_h[px, pz])
        try:
            mc.setSign(ox + px, sy, oz + pz, "OAK_SIGN", facing,
                       str(number), str(street), "", "")
            placed += 1
        except Exception:
            # One bad sign should not stop the rest; a build is worth more than
            # a complete set of numbers.
            continue
    return placed


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
    p.add_argument("--crust", type=int, default=None,
                   help="build the ground as a crust this many blocks thick "
                        "instead of filling down to the lowest point. Costs the "
                        "same however deep the valley, which is what makes a "
                        "metre-scale landscape buildable at all")
    p.add_argument("--bare", action="store_true",
                   help="ignore the land cover and leave plain ground")
    p.add_argument("--house-numbers", action="store_true",
                   help="put a sign with the house number outside each building "
                        "that has one. 76%% of the buildings around Roberts do, "
                        "which is a great many signs; try it and see.")
    p.add_argument("--clear", action="store_true", help="remove a previous build")
    p.add_argument("--dry-run", action="store_true",
                   help="work out the commands but send nothing")
    args = p.parse_args()

    ground, buildings, surface, materials, building_ids, trees, meta = load(args.name)
    body = meta.get("body", "earth")
    scale = meta.get("metres_per_cell", 1.0)
    where = meta.get("what") or "%.4f, %.4f" % (meta.get("lat", 0), meta.get("lon", 0))

    print("%s -- %s" % (args.name, where))
    span_x = ground.shape[1] * scale
    span_z = ground.shape[0] * scale
    print("  %dx%d cells at %s m each = %.0f x %.0f m"
          % (ground.shape[0], ground.shape[1],
             ("%g" % scale), span_x, span_z))
    if meta.get("vscale", 1.0) != 1.0:
        print("  heights exaggerated x%.1f" % meta["vscale"])
    if int((buildings > 0).sum()):
        print("  %d building cells" % int((buildings > 0).sum()))
    if surface is not None and int((surface > 0).sum()) and not args.bare:
        legend = {v: k for k, v in (meta.get("surface_legend") or {}).items()}
        counts = {legend.get(int(c), str(c)): int((surface == c).sum())
                  for c in np.unique(surface) if c}
        print("  land cover: %s" % ", ".join(
            "%s %d" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))

    world, palette = to_voxels(ground, buildings, 0, args.depth,
                               hollow=not args.solid, body=body,
                               surface=None if args.bare else surface,
                               materials=None if args.bare else materials,
                               material_palette=meta.get("material_palette"),
                               metres_per_cell=scale,
                               building_ids=None if args.bare else building_ids,
                               trees=None if args.bare else trees,
                               roof_info=None if args.bare else meta.get("roof_info"),
                               prop_kinds=meta.get("prop_kinds"),
                               crust=args.crust)
    blocks = int((world != 0).sum())
    print("%d blocks, %d high" % (blocks, world.shape[1]))
    if args.crust:
        solid = int(np.rint((ground - np.nanmin(ground)) / scale + args.depth).sum())
        print("  crust %d blocks: %.2fM instead of %.2fM"
              % (args.crust, blocks / 1e6, solid / 1e6))

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

    if args.house_numbers:
        placed = place_house_numbers(mc, meta, building_ids, buildings, ground,
                                     surface, x, y, z, scale, args.depth,
                                     world.shape)
        print("placed %d house number signs" % placed)
        mc.postToChat("%d house numbers" % placed)


if __name__ == "__main__":
    main()
