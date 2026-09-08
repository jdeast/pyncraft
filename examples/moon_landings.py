#!/usr/bin/env python3
"""Where people have landed on the Moon, and where they might land next.

    python moon_landings.py --list
    python moon_landings.py --site apollo15            # terrain and hardware
    python moon_landings.py --site malapert_massif
    python moon_landings.py --site apollo15 --hardware-only

THE SCALE PROBLEM, WHICH IS REAL AND WORTH KNOWING

The best global lunar elevation map is LOLA, at 118 metres per pixel. The Apollo
Lunar Module is 7 metres tall. So on a true-scale map of the landing site the
whole spacecraft is one sixteenth of one block: not small, absent.

There is no clever way round that. Rather than quietly exaggerating, this builds
the two things at their own scales and says so on a sign in front of each:

  - the LANDSCAPE at 118 m per block, which is the real data and shows you
    Hadley Rille or the wall of Malapert as they actually are;
  - the HARDWARE on a pad beside it at half a metre per block, big enough to
    walk around, with a sign giving its real size and how many blocks it would
    be over on the landscape.

Standing between the two is the point. The lander is a speck.

ARE THESE THE REAL DESIGNS?

Apollo, yes. The Lunar Module and the Lunar Roving Vehicle flew, their
dimensions are published to the centimetre, and the block models below use them.

Artemis, no, and nobody has them. Artemis III is to land on a version of
SpaceX's Starship, which is still being developed -- the lunar variant is based
on a Starship design that has not flown yet -- and the Artemis III lander
arrangement has been through contract changes as recently as late 2025. Blue
Origin's Blue Moon Mk2 is contracted for a later mission and exists as a
full-scale crew cabin mockup at Johnson Space Center rather than a flown
vehicle. What is below is the published outline shape at the published overall
size, and it will be wrong in the details. It is drawn in a different palette
from the Apollo hardware for that reason.
"""
import argparse
import math
import os
import sys
import time

import numpy as np

import connect

# ── where ──────────────────────────────────────────────────────────────────
#
# Apollo coordinates are where the descent stages actually are, from the
# landing site surveys. Artemis regions are the nine NASA narrowed to in
# October 2024; a "region" is tens of kilometres across and the exact spot
# inside it is not chosen, so these are the centre of the region or NASA's
# notional site where one has been published.
SITES = {
    "apollo11": (0.674, 23.473, "Apollo 11, Tranquility Base, July 1969", "flown"),
    "apollo12": (-3.012, 336.578, "Apollo 12, Ocean of Storms, November 1969", "flown"),
    "apollo14": (-3.645, 342.522, "Apollo 14, Fra Mauro, February 1971", "flown"),
    "apollo15": (26.132, 3.634, "Apollo 15, Hadley Rille -- first rover, July 1971", "flown"),
    "apollo16": (-8.973, 15.501, "Apollo 16, Descartes Highlands, April 1972", "flown"),
    "apollo17": (20.191, 30.772, "Apollo 17, Taurus-Littrow, December 1972 -- last", "flown"),

    "malapert_massif": (-85.964, 357.681, "Malapert Massif -- NASA notional site", "candidate"),
    "mons_mouton": (-84.6, 31.0, "Mons Mouton, a flat-topped mountain", "candidate"),
}

# The other seven Artemis III candidate regions, named but without a published
# point to build from. Finding coordinates for these is the exercise; see
# --list and the notes at the bottom of this file.
OTHER_ARTEMIS_REGIONS = [
    "Peak near Cabeus B", "Haworth", "Mons Mouton Plateau",
    "Nobile Rim 1", "Nobile Rim 2", "de Gerlache Rim 2", "Slater Plain",
]

# ── the hardware, in metres ────────────────────────────────────────────────

APOLLO_LM = {
    "name": "Apollo Lunar Module",
    "real": "7.0 m tall, 9.4 m across the legs, 15,200 kg",
    "height_m": 7.0,
}
LRV = {
    "name": "Lunar Roving Vehicle",
    "real": "3.1 m long, 1.8 m wide, 210 kg, top speed 13 km/h",
    "height_m": 1.1,
}
STARSHIP_HLS = {
    "name": "Starship HLS (design not final)",
    "real": "about 50 m tall, 9 m across -- published outline only",
    "height_m": 50.0,
}


def build_apollo_lm(scale=0.5):
    """The Lunar Module, as (dx, dy, dz, block) at `scale` metres per block.

    Descent stage is a squat gold-foiled box on four legs; ascent stage is the
    smaller white crew compartment on top with its single window. Not a model
    of the real thing so much as the silhouette everybody recognises.
    """
    b = lambda m: max(int(round(m / scale)), 1)
    out = []

    leg_span = b(9.4) // 2          # legs reach this far from the centre
    desc_r = b(4.2) // 2            # descent stage half-width
    desc_h = b(3.2)
    asc_h = b(3.8)

    # Four landing legs, out and down, with a round footpad on the end.
    for sx, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        steps = max(leg_span - desc_r, 1)
        for i in range(steps + 1):
            t = i / steps
            x = int(round(sx * (desc_r + (leg_span - desc_r) * t)))
            z = int(round(sz * (desc_r + (leg_span - desc_r) * t)))
            y = int(round(desc_h * 0.55 * (1 - t)))
            out.append((x, y, z, "IRON_BARS"))
        px, pz = sx * leg_span, sz * leg_span
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if abs(dx) + abs(dz) <= 1:
                    out.append((px + dx, 0, pz + dz, "IRON_BLOCK"))

    # Descent stage: the gold-wrapped octagon that stays behind on the Moon.
    for x in range(-desc_r, desc_r + 1):
        for z in range(-desc_r, desc_r + 1):
            if abs(x) + abs(z) > desc_r + desc_r // 2:
                continue                      # corner off, making it octagonal
            for y in range(1, desc_h + 1):
                out.append((x, y, z, "GOLD_BLOCK"))

    # Ascent stage: smaller, white, with the crew window facing out.
    asc_r = max(desc_r - 1, 1)
    for x in range(-asc_r, asc_r + 1):
        for z in range(-asc_r, asc_r + 1):
            if abs(x) + abs(z) > asc_r + asc_r // 2:
                continue
            for y in range(desc_h + 1, desc_h + asc_h + 1):
                out.append((x, y, z, "WHITE_CONCRETE"))
    win_y = desc_h + max(asc_h - 2, 1)
    for dx in (-1, 0, 1):
        out.append((dx, win_y, -asc_r, "BLACK_STAINED_GLASS"))

    # Docking hatch on top, the ladder down the front leg, and the plaque.
    out.append((0, desc_h + asc_h + 1, 0, "IRON_TRAPDOOR"))
    for y in range(1, desc_h + 1):
        out.append((0, y, -desc_r - 1, "LADDER"))
    out.append((0, 1, -desc_r - 2, "OAK_SIGN"))
    return out


def build_lrv(scale=0.5):
    """The Lunar Roving Vehicle: two seats, four wire wheels, a dish aerial."""
    b = lambda m: max(int(round(m / scale)), 1)
    out = []
    length, width = b(3.1), b(1.8)

    for x in range(length):
        for z in range(width):
            out.append((x, 1, z, "LIGHT_GRAY_CONCRETE"))          # chassis
    for x in (0, length - 1):
        for z in (0, width - 1):
            out.append((x, 0, z, "IRON_BARS"))                    # wire wheels
    for z in range(width):                                        # seat backs
        out.append((length // 2, 2, z, "LIGHT_GRAY_CONCRETE"))
    out.append((0, 2, width // 2, "IRON_BARS"))                   # aerial mast
    out.append((0, 3, width // 2, "WHITE_CONCRETE"))              # dish
    return out


def build_starship_hls(scale=1.0):
    """Starship HLS, at the published outline. The details are not settled."""
    b = lambda m: max(int(round(m / scale)), 1)
    out = []
    radius = max(b(9.0) // 2, 2)
    height = b(50.0)

    for y in range(height):
        # Tapers to a nose over the top fifth.
        t = max(0.0, (y - height * 0.8) / (height * 0.2))
        r = max(int(round(radius * (1 - 0.75 * t))), 1)
        for x in range(-r, r + 1):
            for z in range(-r, r + 1):
                if x * x + z * z > r * r:
                    continue
                if x * x + z * z < (r - 1) * (r - 1) and 2 < y < height - 2:
                    continue                       # hollow, so it has a shell
                out.append((x, y, z, "LIGHT_GRAY_CONCRETE"))

    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):             # landing legs
        for i in range(1, radius + 3):
            out.append((sx * (radius + i - 1), max(0, 3 - i), sz * (radius + i - 1),
                        "IRON_BLOCK"))
    lock = b(20.0)                                                # crew airlock
    for y in range(lock, lock + max(b(3.0), 2)):
        out.append((0, y, -radius, "BLACK_STAINED_GLASS"))
    return out


HARDWARE = {
    "apollo_lm": (build_apollo_lm, APOLLO_LM, 0.5),
    "lrv": (build_lrv, LRV, 0.5),
    "starship_hls": (build_starship_hls, STARSHIP_HLS, 1.0),
}


def place(mc, recipe, ox, oy, oz):
    """Turn a list of (dx, dy, dz, block) into one buildVoxels call."""
    if not recipe:
        return 0
    xs = [r[0] for r in recipe]
    ys = [r[1] for r in recipe]
    zs = [r[2] for r in recipe]
    lo = (min(xs), min(ys), min(zs))
    points = [(x - lo[0], y - lo[1], z - lo[2], block) for x, y, z, block in recipe]
    return mc.buildVoxels(points, origin=(ox + lo[0], oy + lo[1], oz + lo[2]))


# Sites with a metre-scale DEM, mapped to the entry in fetch_planet.SITE_DEMS.
#
# LOLA's global map is 118 m to the pixel, which is the best there is for the
# whole Moon and nowhere near the best there is for a landing site. Where
# somebody has pointed a stereo camera or a dense laser track at the ground we
# actually care about, there is 2 m or 5 m data, and using it changes what the
# build is: at 118 m the Lunar Module is one sixteenth of a block and has to
# stand on a pad beside the map with a sign apologising, and at 2 m it is four
# blocks tall and stands where it landed.
HIRES = {
    "apollo15": "apollo15",
    "malapert_massif": "malapert",
}

# A metre-scale window is a lot more blocks per square kilometre, so it wants
# to be smaller across and hollow underneath.
HIRES_SIZE = 300
HIRES_CRUST = 5


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    connect.add_arguments(p)
    p.add_argument("--site", choices=sorted(SITES), help="which landing site")
    p.add_argument("--at", nargs=3, type=int, metavar=("X", "Y", "Z"),
                   help="where to build (default: where you are standing)")
    p.add_argument("--size", type=int, default=200,
                   help="landscape across, in LOLA pixels of 118 m (default 200)")
    p.add_argument("--hardware-only", action="store_true",
                   help="skip the landscape and just build the spacecraft")
    p.add_argument("--global-dem", action="store_true",
                   help="use LOLA's 118 m global map even where there is "
                        "better. Worth doing once, beside the good one, to see "
                        "what sixty times the resolution actually buys")
    p.add_argument("--list", action="store_true", help="list the sites and stop")
    args = p.parse_args()

    if args.list:
        print("Flown, and the coordinates are where the descent stages are:")
        for k, (lat, lon, what, kind) in sorted(SITES.items()):
            if kind == "flown":
                print("  %-16s %8.3f %8.3f   %s" % (k, lat, lon, what))
        print()
        print("Artemis III candidate regions with a published point to build from:")
        for k, (lat, lon, what, kind) in sorted(SITES.items()):
            if kind == "candidate":
                print("  %-16s %8.3f %8.3f   %s" % (k, lat, lon, what))
        print()
        print("The other seven regions NASA narrowed to in October 2024, which")
        print("this cannot build because it has no coordinates for them:")
        for name in OTHER_ARTEMIS_REGIONS:
            print("    %s" % name)
        print()
        print("Finding those coordinates is the exercise. Where to look:")
        print("  - USGS Astrogeology publishes navigational grids for all nine")
        print("    candidate sites; each grid carries the region's extent.")
        print("  - The LPI Lunar South Pole Atlas maps the regions.")
        print("  - LPSC abstracts on individual sites usually give a notional")
        print("    landing point to three decimal places.")
        print("  Then add a line to SITES in this file and build it. Longitude")
        print("  is degrees EAST, 0-360, which is what the LOLA mosaic uses.")
        return

    if not args.site:
        sys.exit("Give --site (see --list).")

    lat, lon, what, kind = SITES[args.site]
    mc = connect.connect(args.host, args.port, args.player)

    if args.at:
        ox, oy, oz = args.at
    else:
        pos = mc.player.getTilePos()
        ox, oy, oz = pos.x, pos.y, pos.z

    print("%s" % what)
    print("  %.3f, %.3f  (%s)" % (lat, lon, kind))

    # The landscape, at the best resolution anyone has published for it.
    metres_per_block = 118.45
    if not args.hardware_only:
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        dem = None if args.global_dem else HIRES.get(args.site)
        name = "moon_%s%s" % (args.site, "_hires" if dem else "")
        data = os.path.join(here, "data", name + ".npz")

        if not os.path.exists(data):
            if dem:
                print("  fetching the landscape (site DEM, metre scale)")
                cmd = [sys.executable, "fetch_planet.py", "--dem", dem,
                       "--size", str(HIRES_SIZE), "--name", name]
            else:
                print("  fetching the landscape (LOLA, 118 m per pixel)")
                cmd = [sys.executable, "fetch_planet.py", "--body", "moon",
                       "--lat", str(lat), "--lon", str(lon),
                       "--size", str(args.size), "--name", name]
            subprocess.check_call(cmd, cwd=here)

        import build_town
        g, b, surf, mats, ids, props, meta = build_town.load(name)
        metres_per_block = meta["metres_per_cell"]
        world, palette = build_town.to_voxels(
            g, b, 0, 3, body="moon", metres_per_cell=metres_per_block,
            crust=HIRES_CRUST if dem else None)
        print("  landscape: %d blocks, one block = %g m, %.1f km across"
              % (int((world != 0).sum()), metres_per_block,
                 world.shape[0] * metres_per_block / 1000.0))
        if dem:
            print("  source: %s" % meta.get("source_ground", "?"))
            print("  that is %.0fx finer than the 118 m global map"
                  % (118.45 / metres_per_block))
        mc.buildVoxels(world, palette=palette, origin=(ox, oy, oz))
        pad_x = ox + world.shape[0] + 8
    else:
        pad_x = ox + 8

    # The hardware, on a pad beside it, at a scale you can walk around.
    wanted = ["starship_hls"] if kind == "candidate" else ["apollo_lm"]
    if args.site == "apollo15":
        wanted.append("lrv")          # the first mission to carry a rover
    if args.site in ("apollo16", "apollo17"):
        wanted.append("lrv")

    here = pad_x
    for key in wanted:
        builder, spec, scale = HARDWARE[key]
        recipe = builder(scale)
        sent = place(mc, recipe, here, oy, oz)
        blocks_on_map = spec["height_m"] / metres_per_block
        print("  %s: %d blocks, %d commands, 1 block = %.2f m"
              % (spec["name"], len(recipe), sent, scale))
        print("     real size %s" % spec["real"])
        if blocks_on_map >= 1.0:
            print("     on the landscape beside it, %.1f blocks tall -- which at"
                  % blocks_on_map)
            print("     this resolution is something you can actually see")
        else:
            print("     on the landscape it would be %.2f blocks tall"
                  % blocks_on_map)
        mc.setSign(here, oy, oz - 4, "OAK_SIGN", "NORTH",
                   spec["name"][:15], spec["real"][:15],
                   "1 block=%.1fm" % scale,
                   "%.2f blk on map" % blocks_on_map)
        here += 40

    mc.postToChat("%s -- landscape at %g m/block, hardware at its own scale."
                  % (what, metres_per_block))


if __name__ == "__main__":
    main()
