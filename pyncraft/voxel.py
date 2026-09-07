"""Turning a pile of coordinates into as few Minecraft commands as possible.

Every interesting example ends the same way: some professional library hands
you a few hundred thousand coordinates, and now they have to become blocks.
Done naively that is one `world.setBlock` per block, and on a Raspberry Pi
serving a class it is slow enough to be the whole experience.

The fix is not a faster socket. It is sending fewer commands: `world.setBlocks`
fills a whole cuboid in one, so a build made of large uniform regions -- which
terrain, buildings and crystals all are -- collapses to a small number of box
fills. Splitting a voxel set into maximal boxes is what this module does.

    >>> import numpy as np
    >>> from pyncraft.voxel import decompose
    >>> a = np.zeros((4, 1, 4), dtype=int); a[:, 0, :] = 1
    >>> list(decompose(a))                    # one box, not sixteen blocks
    [(0, 0, 0, 3, 0, 3, 1)]

The decomposition is greedy: take the first unused voxel, grow it as far as it
will go along x, then y, then z, emit that box, repeat. It is not the minimal
decomposition -- that problem is NP-hard -- but it is linear-ish, it is easy to
be confident about, and on real data it removes most of the work. A worst case
of alternating materials degenerates to one box per voxel, which is exactly
what you would have sent anyway.
"""
import numpy as np

__all__ = ["decompose", "to_array", "commands_for"]


def to_array(points, shape=None):
    """Turn a list of (x, y, z) or (x, y, z, material) into a labelled array.

    Returns (array, palette), where array holds 0 for empty and 1..n for
    materials, and palette[i - 1] is the material for label i. Coordinates are
    shifted so the lowest corner is at the origin; the caller adds the offset
    back when placing, which keeps the array small when the points are far from
    0,0,0.

    Also returns the offset that was subtracted.
    """
    points = list(points)
    if not points:
        return np.zeros((0, 0, 0), dtype=np.int32), [], (0, 0, 0)

    width = len(points[0])
    if width not in (3, 4):
        raise ValueError("points must be (x, y, z) or (x, y, z, material), got %d values"
                         % width)

    coords = np.array([p[:3] for p in points], dtype=np.int64)
    if width == 4:
        materials = [p[3] for p in points]
    else:
        materials = None

    lo = coords.min(axis=0)
    coords -= lo
    hi = coords.max(axis=0)

    array = np.zeros(tuple(hi + 1), dtype=np.int32)
    palette = []

    if materials is None:
        array[coords[:, 0], coords[:, 1], coords[:, 2]] = 1
        palette = [None]            # caller supplies the single material
    else:
        # Stable ordering, so the same input always produces the same palette.
        index = {}
        labels = np.empty(len(materials), dtype=np.int32)
        for i, m in enumerate(materials):
            if m not in index:
                index[m] = len(palette) + 1
                palette.append(m)
            labels[i] = index[m]
        # Later points win where two land on the same block, which matches the
        # behaviour of sending the commands one after another.
        array[coords[:, 0], coords[:, 1], coords[:, 2]] = labels

    return array, palette, tuple(int(v) for v in lo)


def decompose(array):
    """Split a labelled 3D array into maximal same-label boxes.

    Yields (x1, y1, z1, x2, y2, z2, label) with inclusive bounds, for every
    non-zero label. Zero means empty and is never emitted.
    """
    if array.size == 0:
        return

    remaining = array.astype(np.int32, copy=True)
    nx, ny, nz = remaining.shape

    # np.nonzero once, then walk it, rather than scanning the whole volume
    # repeatedly. Consumed voxels are zeroed as boxes are emitted, so a
    # coordinate is skipped if an earlier box already covered it.
    xs, ys, zs = np.nonzero(remaining)

    for x, y, z in zip(xs, ys, zs):
        label = remaining[x, y, z]
        if label == 0:
            continue                      # already swallowed by an earlier box

        # Grow along x while the whole run matches.
        x2 = x
        while x2 + 1 < nx and remaining[x2 + 1, y, z] == label:
            x2 += 1

        # Grow along y, but only while the entire x-run at that y matches.
        y2 = y
        while y2 + 1 < ny and np.all(remaining[x:x2 + 1, y2 + 1, z] == label):
            y2 += 1

        # Then along z, requiring the whole xy-slab to match.
        z2 = z
        while z2 + 1 < nz and np.all(remaining[x:x2 + 1, y:y2 + 1, z2 + 1] == label):
            z2 += 1

        remaining[x:x2 + 1, y:y2 + 1, z:z2 + 1] = 0
        yield (int(x), int(y), int(z), int(x2), int(y2), int(z2), int(label))


def commands_for(array, palette, offset=(0, 0, 0), single=None):
    """Yield (name, args) command tuples for a labelled array.

    A one-block box becomes world.setBlock; anything larger becomes
    world.setBlocks, which is the whole point.
    """
    ox, oy, oz = offset
    for x1, y1, z1, x2, y2, z2, label in decompose(array):
        material = single if palette[label - 1] is None else palette[label - 1]
        if material is None:
            raise ValueError("no material given: pass block=... or use "
                             "(x, y, z, material) points")
        if (x1, y1, z1) == (x2, y2, z2):
            yield (b"world.setBlock", (x1 + ox, y1 + oy, z1 + oz, material))
        else:
            yield (b"world.setBlocks",
                   (x1 + ox, y1 + oy, z1 + oz, x2 + ox, y2 + oy, z2 + oz, material))
