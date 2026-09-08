#!/usr/bin/env python3
"""Build an STL file in Minecraft.

    python render_stl.py --model unicorn
    python render_stl.py --file data/T-Rex.stl --size 60 --material WHITE_CONCRETE

STL is the format 3D printers use, so there are millions of them about, free,
of almost anything. stltovoxel turns one into a cloud of filled cubes, and this
turns those into blocks.

WHAT CHANGED, AND WHY IT MATTERS HERE

This used to send one world.setBlock per block with a sleep in between, and its
own documentation explained that the sleep was there so as not to crash the
server. A hundred thousand block model took sixteen minutes and there was no
way round it.

mc.buildVoxels splits the shape into maximal boxes and fills each with one
command, and paces itself, which is what the sleep was really for.

That inverts an assumption this file was built on. Hollowing a model out --
discarding every block with all six neighbours filled -- used to be the main
way to make rendering bearable, because it removed most of the blocks. With box
decomposition it does the opposite: a solid lump is a handful of large boxes,
while a shell is a thin curved surface that merges into almost nothing. Solid
is now both quicker to send and fewer commands. Hollow is still worth having,
because walking around inside a T-Rex is its own reward, but it is a choice
about what you want rather than a way to go faster -- so the default flipped.
"""
import argparse
import math
import os
import sys
import time

import numpy as np

import connect

DEFAULT_MATERIAL = "OAK_PLANKS"


def voxelise(stlfile, resolution=200, verbose=True):
    """STL to an (n, 3) array of filled cube centres, caching the slow part.

    stltovoxel is needed only here, and only the first time a given model and
    resolution are used, so it is imported at the point of use. Everything else
    in this file works without it.
    """
    xyzfile = "%s_%d.xyz" % (os.path.splitext(stlfile)[0], resolution)

    if not os.path.exists(xyzfile):
        if not os.path.exists(stlfile):
            raise SystemExit("No such STL file: %s" % stlfile)
        try:
            import stltovoxel
        except ImportError:
            raise SystemExit(
                "Turning an STL into cubes needs one more library:\n"
                "    pip install stl-to-voxel\n"
                "It is needed the first time you use a model; after that the\n"
                "result is cached beside the STL as a .xyz file.")
        if verbose:
            print("voxelising %s at resolution %d (once, then cached)"
                  % (os.path.basename(stlfile), resolution))
        stltovoxel.convert_file(stlfile, xyzfile, resolution=resolution)

    return np.loadtxt(xyzfile)


def rotate(xyz, theta=0.0, psi=0.0, phi=0.0):
    """Euler rotation, so a model can be stood the right way up.

    Most STLs are modelled Z-up and Minecraft is Y-up, so phi = -pi/2 is the
    usual case and most of the models below want it.
    """
    if not (theta or psi or phi):
        return xyz
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    ct, st = math.cos(theta), math.sin(theta)
    cp, sp = math.cos(psi), math.sin(psi)
    cf, sf = math.cos(phi), math.sin(phi)
    out = np.empty_like(xyz)
    out[:, 0] = x * (ct * cp) + y * (sf * st * cp - cf * sp) + z * (cf * st * cp + sf * sp)
    out[:, 1] = x * (ct * sp) + y * (sf * st * sp + cf * cp) + z * (cf * st * sp - sf * cp)
    out[:, 2] = x * (-st) + y * (sf * ct) + z * (cf * ct)
    return out


def to_grid(xyz, size=25, max_x=None, max_y=None, max_z=None):
    """Scale a point cloud onto a block grid, keeping its proportions.

    Whichever of max_x/max_y/max_z comes first sets the scale; otherwise the
    longest side becomes `size` blocks. The aspect ratio is always kept.
    """
    span = xyz.max(axis=0) - xyz.min(axis=0)
    span = np.where(span == 0, 1.0, span)

    if max_x is not None:
        scale = max_x / span[0]
    elif max_y is not None:
        scale = max_y / span[1]
    elif max_z is not None:
        scale = max_z / span[2]
    else:
        scale = size / span.max()

    grid = np.rint((xyz - xyz.min(axis=0)) * scale).astype(int)
    return np.unique(grid, axis=0)


def to_array(grid):
    """An (n, 3) list of integer cells to a dense boolean array."""
    if not len(grid):
        return np.zeros((0, 0, 0), dtype=bool)
    shape = grid.max(axis=0) + 1
    array = np.zeros(tuple(int(v) for v in shape), dtype=bool)
    array[grid[:, 0], grid[:, 1], grid[:, 2]] = True
    return array


def hollow(array):
    """Keep only the shell: drop every block with all six neighbours filled.

    The old version did this by appending to a numpy array inside a Python loop
    over a set, which is quadratic and was the slowest part of a large model.
    Shifting the whole array six ways gives the same answer in six operations.
    """
    if array.size == 0:
        return array
    interior = np.ones_like(array)
    interior[:-1, :, :] &= array[1:, :, :]
    interior[1:, :, :] &= array[:-1, :, :]
    interior[:, :-1, :] &= array[:, 1:, :]
    interior[:, 1:, :] &= array[:, :-1, :]
    interior[:, :, :-1] &= array[:, :, 1:]
    interior[:, :, 1:] &= array[:, :, :-1]
    # A cell on the face of the box has no outside neighbour, so nothing there
    # is interior however solid the model is.
    interior[0, :, :] = interior[-1, :, :] = False
    interior[:, 0, :] = interior[:, -1, :] = False
    interior[:, :, 0] = interior[:, :, -1] = False
    return array & ~interior


def render_stl(mc, stlfile, size=25, max_x=None, max_y=None, max_z=None,
               origin=None, theta=0.0, psi=0.0, phi=0.0, resolution=200,
               material=DEFAULT_MATERIAL, solid=True, blocks_per_second=25000,
               verbose=True):
    """Put an STL model in the world. Returns (blocks, commands, seconds)."""
    xyz = voxelise(stlfile, resolution, verbose=verbose)
    xyz = rotate(xyz, theta, psi, phi)
    array = to_array(to_grid(xyz, size, max_x, max_y, max_z))

    filled = int(array.sum())
    if not solid:
        array = hollow(array)
        if verbose:
            print("  hollowed: %d blocks of %d kept" % (int(array.sum()), filled))

    if origin is None:
        p = mc.player.getTilePos()
        origin = (p.x, p.y, p.z)

    blocks = int(array.sum())
    if verbose:
        print("  %s: %d blocks, %d x %d x %d"
              % (os.path.basename(stlfile), blocks,
                 array.shape[0], array.shape[1], array.shape[2]))

    started = time.time()
    commands = mc.buildVoxels(array, block=material, origin=origin,
                              blocks_per_second=blocks_per_second)
    elapsed = time.time() - started
    if verbose:
        print("  %d commands in %.1fs (%.0fx fewer than one per block)"
              % (commands, elapsed, blocks / max(commands, 1)))
    return blocks, commands, elapsed


# The models the old script knew about, with the rotation each needs to stand
# up. Kept as data, so adding one is a line rather than another branch -- the
# old version had six near-identical branches and two of them were broken.
MODELS = {
    "unicorn":   ("alicorn-rmd-repaired.stl", -math.pi / 2, 100, "WHITE_CONCRETE"),
    "trex":      ("T-Rex.stl", -math.pi / 2, 60, "LIME_TERRACOTTA"),
    "tajmahal":  ("taj-mahal-by-miniworld3d.stl", 0.0, 100, "WHITE_CONCRETE"),
    "colosseum": ("Colosseum_final.stl", -math.pi / 2, 60, "SMOOTH_SANDSTONE"),
    "jwst":      ("JWST.stl", -math.pi / 2, 120, "GOLD_BLOCK"),
    "carnival":  ("carnival_wheel_assy.STL", 0.0, 80, "IRON_BLOCK"),
}

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    connect.add_arguments(p)
    p.add_argument("--model", choices=sorted(MODELS),
                   help="one of the models this knows about; --list to see them")
    p.add_argument("--file", help="any other STL file")
    p.add_argument("--size", type=int, default=None, help="longest side, in blocks")
    p.add_argument("--material", default=None, help="which block to build it from")
    p.add_argument("--resolution", type=int, default=200, help="voxelising resolution")
    p.add_argument("--at", nargs=3, type=int, metavar=("X", "Y", "Z"),
                   help="where to put it (default: where you are standing)")
    p.add_argument("--hollow", action="store_true",
                   help="keep only the shell, so you can walk about inside. Slower "
                        "to send than solid now that whole boxes go at once")
    p.add_argument("--list", action="store_true", help="list the models and stop")
    args = p.parse_args()

    if args.list:
        for name, (filename, _phi, size, material) in sorted(MODELS.items()):
            missing = "" if os.path.exists(os.path.join(DATA, filename)) \
                else "   -- not downloaded, see fetch_models.py"
            print("  %-10s %-34s %3d blocks, %s%s"
                  % (name, filename, size, material, missing))
        return

    if args.model:
        filename, phi, size, material = MODELS[args.model]
        stlfile = os.path.join(DATA, filename)
    elif args.file:
        stlfile, phi, size, material = args.file, 0.0, 40, DEFAULT_MATERIAL
    else:
        sys.exit("Give --model (--list shows them) or --file <something.stl>.")

    mc = connect.connect(args.host, args.port, args.player)
    render_stl(mc, stlfile,
               size=args.size or size,
               material=args.material or material,
               phi=phi, resolution=args.resolution,
               origin=tuple(args.at) if args.at else None,
               solid=not args.hollow)


if __name__ == "__main__":
    main()
