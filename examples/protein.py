#!/usr/bin/env python3
"""Build a real protein, from the Protein Data Bank, at a size you can walk round.

    python protein.py                       # ubiquitin, the standard example
    python protein.py --pdb 1MBN            # myoglobin, the first ever solved
    python protein.py --pdb 4HHB --style spacefill
    python protein.py --list                # some worth looking at

The coordinates come from the RCSB Protein Data Bank, live. Every atom in the
file was measured -- by X-ray crystallography, mostly -- and the numbers are in
angstroms, which is a tenth of a nanometre. A carbon atom is about 1.7 A
across. You are about to stand next to one the size of a shed.

WHY A BACKBONE AND NOT A BALL OF ATOMS

A protein is a single long chain that folds into one particular shape, and the
shape is the whole point: it is what decides what the protein does, and a chain
with the same links in a different arrangement does a different job or no job
at all. Drawn as every atom, that chain is invisible -- you get a solid lump,
because the inside of a protein is packed.

So the default draws only the path the chain takes, one point per amino acid,
joined up. That is the fold. --style spacefill gives the lump, which is worth
seeing once, because it is what the protein actually is: the fold you were
admiring has no gaps in it anywhere.

THE COLOURS ARE THE SECONDARY STRUCTURE, AND THEY ARE MEASURED

Where the chain coils into a spiral it is an ALPHA HELIX; where it runs
alongside itself in flat ribbons it is a BETA SHEET; the rest is loops holding
those together. Those are not guessed here or worked out from the geometry --
a PDB file records them, in HELIX and SHEET lines put there by the people who
solved the structure, and this reads them. Red is helix, yellow is sheet, white
is everything else.

Ubiquitin is a good first look precisely because it has both: one long helix
lying across a sheet of five strands. Myoglobin is nothing but helix.
Green fluorescent protein is a barrel of eleven strands with the bit that
glows threaded up the middle.
"""
import argparse
import io
import math
import os
import sys
import time
import urllib.error
import urllib.request

try:
    import numpy as np
except ImportError:
    sys.exit("This needs numpy: pip install numpy")

import connect

RCSB = "https://files.rcsb.org/download/%s.pdb"
USER_AGENT = "pyncraft protein (https://github.com/jdeast/pyncraft)"

# Worth a look, with the number of amino acids, because that is what decides
# how long it takes and how big it comes out.
INTERESTING = [
    ("1UBQ", 76, "Ubiquitin -- one helix on a five-strand sheet. The classic."),
    ("1CRN", 46, "Crambin. The smallest thing here; good for a quick try."),
    ("1MBN", 153, "Myoglobin -- all helix, and the first protein ever solved."),
    ("2LYZ", 129, "Lysozyme, from egg white. It cuts open bacteria."),
    ("4INS", 102, "Insulin. Four short chains, two molecules in the file."),
    ("1EMA", 221, "Green fluorescent protein -- a barrel of eleven strands."),
    ("1TIM", 494, "Triosephosphate isomerase -- the TIM barrel, 8 and 8."),
    ("4HHB", 574, "Haemoglobin. Four chains, four hemes, carries your oxygen."),
    ("6VXX", 2916, "The SARS-CoV-2 spike. Enormous; use --size and be patient."),
]

# Standard CPK colours, which every chemistry textbook and every molecular
# viewer has used since Corey, Pauling and Koltun built them out of plastic in
# the sixties. Carbon black, oxygen red, nitrogen blue, sulphur yellow.
ELEMENT_BLOCKS = {
    "C": "GRAY_CONCRETE",
    "N": "BLUE_CONCRETE",
    "O": "RED_CONCRETE",
    "S": "YELLOW_CONCRETE",
    "P": "ORANGE_CONCRETE",
    "H": "WHITE_CONCRETE",
    "FE": "BROWN_CONCRETE",
    "MG": "LIME_CONCRETE",
    "ZN": "LIGHT_GRAY_CONCRETE",
    "CA": "CYAN_CONCRETE",
    "NA": "PURPLE_CONCRETE",
    "CL": "GREEN_CONCRETE",
}
DEFAULT_ELEMENT = "PINK_CONCRETE"

# Van der Waals radii in angstroms -- how big an atom actually is, which is not
# the same as how far its bonds reach.
VDW = {"C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "P": 1.80, "H": 1.20,
       "FE": 2.05, "MG": 1.73, "ZN": 1.39, "CA": 2.31, "NA": 2.27, "CL": 1.75}
DEFAULT_VDW = 1.70

STRUCTURE_BLOCKS = {"H": "RED_CONCRETE", "E": "YELLOW_CONCRETE", "-": "WHITE_CONCRETE"}

# A rainbow from the start of the chain to the end, which is the other way
# people colour these: it shows you which way the chain runs.
RAINBOW = ["RED_CONCRETE", "ORANGE_CONCRETE", "YELLOW_CONCRETE", "LIME_CONCRETE",
           "GREEN_CONCRETE", "CYAN_CONCRETE", "LIGHT_BLUE_CONCRETE",
           "BLUE_CONCRETE", "PURPLE_CONCRETE", "MAGENTA_CONCRETE"]

CHAIN_BLOCKS = ["RED_CONCRETE", "BLUE_CONCRETE", "YELLOW_CONCRETE",
                "LIME_CONCRETE", "MAGENTA_CONCRETE", "CYAN_CONCRETE",
                "ORANGE_CONCRETE", "WHITE_CONCRETE"]


# ── the Protein Data Bank ──────────────────────────────────────────────────

def fetch(pdb_id, cache_dir, refresh=False):
    """The PDB entry, cached on disk. These files are small and never change."""
    pdb_id = pdb_id.strip().upper()
    path = os.path.join(cache_dir, "pdb_%s.pdb" % pdb_id)
    if os.path.exists(path) and not refresh:
        return io.open(path, encoding="latin-1").read()
    req = urllib.request.Request(RCSB % pdb_id, headers={"User-Agent": USER_AGENT})
    try:
        text = urllib.request.urlopen(req, timeout=120).read().decode("latin-1")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SystemExit("No PDB entry called %r. They are four characters, "
                             "like 1UBQ. --list shows some." % pdb_id)
        raise SystemExit("The PDB said no (%s)." % e)
    os.makedirs(cache_dir, exist_ok=True)
    io.open(path, "w", encoding="latin-1", newline="").write(text)
    return text


def parse(text, waters=False, ligands=True):
    """Atoms, secondary structure and a title, out of a PDB file.

    The format is punch-card fixed columns, which is why it is parsed by
    character position rather than by splitting: an atom called "CA" in columns
    13-16 is an alpha carbon, and one called "CA" in columns 77-78 is a calcium
    ion, and splitting on whitespace loses the difference.

    Only the first MODEL is used. An NMR structure holds twenty or so poses of
    the same molecule, and drawing them all at once gives a haystack.
    """
    atoms, helix, sheet = [], set(), set()
    title, model = [], 0
    for ln in text.splitlines():
        rec = ln[:6]
        if rec == "TITLE ":
            title.append(ln[10:].strip())
        elif rec == "MODEL ":
            model += 1
            if model > 1:
                break
        elif rec == "HELIX ":
            # start and end residue of a helix, inclusive, on one chain
            try:
                ch, a, b = ln[19], int(ln[21:25]), int(ln[33:37])
            except ValueError:
                continue
            for r in range(a, b + 1):
                helix.add((ch, r))
        elif rec == "SHEET ":
            try:
                ch, a, b = ln[21], int(ln[22:26]), int(ln[33:37])
            except ValueError:
                continue
            for r in range(a, b + 1):
                sheet.add((ch, r))
        elif rec in ("ATOM  ", "HETATM"):
            resname = ln[17:20].strip()
            if rec == "HETATM":
                if resname in ("HOH", "DOD", "WAT") and not waters:
                    continue
                if not ligands:
                    continue
            alt = ln[16]
            if alt not in (" ", "A"):
                continue          # one conformer of a disordered side chain
            try:
                x, y, z = float(ln[30:38]), float(ln[38:46]), float(ln[46:54])
                resseq = int(ln[22:26])
            except ValueError:
                continue
            element = (ln[76:78].strip() or ln[12:14].strip()).upper()
            atoms.append({
                "name": ln[12:16].strip(), "element": element,
                "chain": ln[21], "resseq": resseq, "resname": resname,
                "hetatm": rec == "HETATM", "xyz": (x, y, z),
            })
    return atoms, helix, sheet, " ".join(title)


def backbone(atoms):
    """The alpha carbons, in order, one per amino acid, split by chain.

    The alpha carbon is the one every amino acid has in the middle of it, so
    joining them up in sequence traces the chain itself and nothing else.
    """
    chains = {}
    for a in atoms:
        if a["name"] == "CA" and not a["hetatm"] and a["element"] in ("C", ""):
            chains.setdefault(a["chain"], []).append(a)
    for ch in chains:
        chains[ch].sort(key=lambda a: a["resseq"])
    return chains


# ── drawing ────────────────────────────────────────────────────────────────

def connected(a, b):
    """Points from a to b, each sharing a face with the one before.

    Rounding along a straight line steps diagonally, and two blocks meeting
    only at an edge leave a gap you can see through -- which on a chain reads
    as the chain being broken, exactly where it is not.
    """
    cur = list(a)
    pts = [tuple(cur)]
    while tuple(cur) != tuple(b):
        far = max(range(3), key=lambda i: abs(b[i] - cur[i]))
        cur[far] += 1 if b[far] > cur[far] else -1
        pts.append(tuple(cur))
    return pts


def ball(radius):
    """Offsets of a solid ball, for stamping along a line or onto an atom."""
    r = max(float(radius), 0.5)
    n = int(math.ceil(r))
    ax = np.arange(-n, n + 1)
    x, y, z = np.meshgrid(ax, ax, ax, indexing="ij")
    keep = (x * x + y * y + z * z) <= (r + 0.25) ** 2
    return np.stack([x[keep], y[keep], z[keep]], axis=1)


def to_blocks(atoms, size):
    """Angstroms to block coordinates, keeping the shape and centring on zero.

    Returns the positions, the scale in blocks per angstrom, and the shape of
    the box they fit in.
    """
    xyz = np.array([a["xyz"] for a in atoms], dtype=float)
    span = xyz.max(axis=0) - xyz.min(axis=0)
    scale = float(size) / max(span.max(), 1e-6)
    grid = np.rint((xyz - xyz.min(axis=0)) * scale).astype(int)
    return grid, scale, grid.max(axis=0) + 1


def build_backbone(atoms, helix, sheet, size, thickness, colour_by):
    """The chain, as a tube through every alpha carbon."""
    chains = backbone(atoms)
    if not chains:
        raise SystemExit("No alpha carbons in this entry, so there is no chain "
                         "to trace. Try --style spacefill.")
    flat = [a for ch in sorted(chains) for a in chains[ch]]
    grid, scale, shape = to_blocks(flat, size)

    palette, index = [], {}

    def label(material):
        if material not in index:
            palette.append(material)
            index[material] = len(palette)
        return index[material]

    pad = int(math.ceil(thickness)) + 1
    world = np.zeros(tuple(shape + 2 * pad), dtype=np.int32)
    offsets = ball(thickness)

    n = len(flat)
    pos = 0
    for ch in sorted(chains):
        residues = chains[ch]
        for i, atom in enumerate(residues):
            if colour_by == "structure":
                key = (atom["chain"], atom["resseq"])
                mat = STRUCTURE_BLOCKS["H" if key in helix else
                                       "E" if key in sheet else "-"]
            elif colour_by == "rainbow":
                mat = RAINBOW[int(len(RAINBOW) * pos / max(n, 1)) % len(RAINBOW)]
            else:
                mat = CHAIN_BLOCKS[sorted(chains).index(ch) % len(CHAIN_BLOCKS)]
            lab = label(mat)

            here = tuple(grid[pos] + pad)
            stamp = offsets + here
            world[stamp[:, 0], stamp[:, 1], stamp[:, 2]] = lab

            # Join it to the previous residue of the same chain. Alpha carbons
            # sit 3.8 A apart, which at any useful scale is several blocks, so
            # without this the chain is a string of loose beads.
            if i:
                prev = tuple(grid[pos - 1] + pad)
                for p in connected(prev, here)[1:-1]:
                    stamp = offsets + np.array(p)
                    world[stamp[:, 0], stamp[:, 1], stamp[:, 2]] = lab
            pos += 1
    return world, palette, scale, len(flat)


def build_spacefill(atoms, size, colour_by, chains_present):
    """Every atom, at the size it really is."""
    grid, scale, shape = to_blocks(atoms, size)
    palette, index = [], {}

    def label(material):
        if material not in index:
            palette.append(material)
            index[material] = len(palette)
        return index[material]

    radii = {}
    for a in atoms:
        radii.setdefault(a["element"], VDW.get(a["element"], DEFAULT_VDW))
    pad = int(math.ceil(max(radii.values()) * scale)) + 1
    world = np.zeros(tuple(shape + 2 * pad), dtype=np.int32)

    stamps = {e: ball(r * scale) for e, r in radii.items()}
    order = sorted(range(len(atoms)),
                   key=lambda i: -radii[atoms[i]["element"]])
    for i in order:
        a = atoms[i]
        if colour_by == "chain":
            mat = CHAIN_BLOCKS[chains_present.index(a["chain"]) % len(CHAIN_BLOCKS)]
        else:
            mat = ELEMENT_BLOCKS.get(a["element"], DEFAULT_ELEMENT)
        lab = label(mat)
        stamp = stamps[a["element"]] + grid[i] + pad
        world[stamp[:, 0], stamp[:, 1], stamp[:, 2]] = lab
    return world, palette, scale, len(atoms)


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    connect.add_arguments(p)
    p.add_argument("--pdb", default="1UBQ", help="a four character PDB id (default 1UBQ)")
    p.add_argument("--style", choices=("backbone", "spacefill"), default="backbone",
                   help="the fold, or every atom (default backbone)")
    p.add_argument("--colour", choices=("structure", "rainbow", "chain", "element"),
                   default=None, help="default: structure for a backbone, "
                                      "element for spacefill")
    p.add_argument("--size", type=int, default=120,
                   help="longest side, in blocks (default 120)")
    p.add_argument("--thickness", type=float, default=1.6,
                   help="radius of the backbone tube, in blocks (default 1.6)")
    p.add_argument("--at", nargs=3, type=int, metavar=("X", "Y", "Z"),
                   help="where to put it (default: where you are standing)")
    p.add_argument("--waters", action="store_true",
                   help="include the water molecules, which are usually most of "
                        "the HETATM records and always in the way")
    p.add_argument("--no-ligands", action="store_true",
                   help="protein only: no hemes, no metals, no drugs")
    p.add_argument("--pace", type=int, default=12000, help="blocks per second")
    p.add_argument("--budget", type=int, default=900000,
                   help="refuse to place more blocks than this (default 900000)")
    p.add_argument("--force", action="store_true", help="build it anyway")
    p.add_argument("--refresh", action="store_true", help="re-download the entry")
    p.add_argument("--list", action="store_true", help="list some proteins and stop")
    p.add_argument("--dry-run", action="store_true", help="print the plan only")
    args = p.parse_args()

    if args.list:
        print("%-6s %8s  %s" % ("pdb", "residues", "what it is"))
        for pid, n, what in INTERESTING:
            print("%-6s %8d  %s" % (pid, n, what))
        print()
        print("Any of the ~200,000 entries at rcsb.org works: --pdb <id>.")
        return

    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    text = fetch(args.pdb, data, args.refresh)
    atoms, helix, sheet, title = parse(text, waters=args.waters,
                                      ligands=not args.no_ligands)
    if not atoms:
        raise SystemExit("No atoms in %s, which should not happen." % args.pdb)

    chains_present = sorted({a["chain"] for a in atoms})
    colour = args.colour or ("structure" if args.style == "backbone" else "element")

    print("%s -- %s" % (args.pdb.upper(), title[:70]))
    print("  %d atoms, %d chains (%s)"
          % (len(atoms), len(chains_present), ", ".join(chains_present)))
    print("  %d residues in a helix, %d in a sheet, as recorded by the people "
          "who solved it" % (len(helix), len(sheet)))

    if args.style == "backbone":
        world, palette, scale, n = build_backbone(
            atoms, helix, sheet, args.size, args.thickness, colour)
        print("  tracing %d alpha carbons" % n)
    else:
        world, palette, scale, n = build_spacefill(
            atoms, args.size, colour, chains_present)
        print("  drawing all %d atoms at their van der Waals radii" % n)

    blocks = int((world != 0).sum())
    nx, ny, nz = world.shape
    print()
    print("  1 block = %.3f angstroms, so a carbon atom is %.1f blocks across"
          % (1.0 / scale, 2 * 1.7 * scale))
    print("  %d x %d x %d, %d blocks, about %.0f seconds"
          % (nx, ny, nz, blocks, blocks / float(args.pace)))
    print("  colours: %s" % ", ".join(palette))

    if blocks > args.budget and not args.force:
        fits = args.size * (float(args.budget) / blocks) ** (1.0 / 3.0)
        print()
        print("  That is over the budget of %d." % args.budget)
        print("  --size %d would fit; --force builds it anyway." % int(fits * 0.95))
        return

    if args.dry_run:
        return

    mc = connect.connect(args.host, args.port, args.player)
    if args.at:
        ox, oy, oz = args.at
    else:
        pos = mc.player.getTilePos()
        ox, oy, oz = pos.x, pos.y + 2, pos.z
    print()
    print("building at %d, %d, %d" % (ox, oy, oz))
    mc.postToChat("%s: %s" % (args.pdb.upper(), title[:80]))
    started = time.time()
    sent = mc.buildVoxels(world, palette=palette, origin=(ox, oy, oz),
                          blocks_per_second=args.pace)
    print("  %d commands in %.0fs" % (sent, time.time() - started))
    if args.style == "backbone" and colour == "structure":
        mc.postToChat("Red is alpha helix, yellow is beta sheet, white is the "
                      "loops that hold them together.")
    print("  stand at %d %d %d" % (ox + nx // 2, oy + ny + 4, oz + nz // 2))


if __name__ == "__main__":
    main()
