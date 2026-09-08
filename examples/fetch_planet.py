#!/usr/bin/env python3
"""Fetch Mars or lunar terrain, ready to build in Minecraft.

    python fetch_planet.py --body mars --place gale
    python fetch_planet.py --body moon --place tranquillity
    python fetch_planet.py --body mars --lat -4.5 --lon 137.4 --size 400

Same idea as fetch_terrain.py, better subject: no buildings to worry about, no
licence to check, and walking the floor of Gale Crater at true proportions is
the sort of thing a ten year old remembers.

HOW IT GETS THE DATA

The global elevation models are single enormous GeoTIFFs -- Mars is 46080 by
23040 and 2.1 GB, the Moon is 92160 by 46080 and 8.5 GB -- and downloading
either to crop out a few hundred pixels would be absurd.

They do not have to be. Both are uncompressed, 16-bit, and stored one strip per
row, so any block of rows is one contiguous run of bytes, and the server sends
byte ranges. So: read the TIFF header to find where the rows live, then ask for
exactly the rows wanted. A 400-pixel window off Mars is about 35 MB rather than
2.1 GB, and it needs no GDAL, no rasterio, and nothing beyond the standard
library plus numpy.

The TIFF header parsing is below. It handles precisely the case these two
files are -- uncompressed, one strip per row, classic TIFF for Mars and
BigTIFF for the Moon, which at 8.5 GB has no choice: classic TIFF offsets
are 32-bit and cannot reach past 4 GB. Anything else raises rather than
being guessed at, because a misread header gives a landscape that looks
perfectly plausible and is wrong.

VERTICAL EXAGGERATION

Real proportions are honest and often dull. Olympus Mons is 22 km high and 600
km across, so at true scale it is a slope you would not notice walking up.
--vscale multiplies the heights; 1 is truthful, 3 or 4 makes a landscape read
the way the photographs make you expect it to. The default is 1, and the number
used is recorded in the file so a build never silently lies about its scale.
"""
import argparse
import json
import math
import os
import struct
import sys
import urllib.error
import urllib.request

try:
    import numpy as np
except ImportError:
    sys.exit("This needs numpy: pip install numpy")

USER_AGENT = "pyncraft fetch_planet (https://github.com/jdeast/pyncraft)"

# Both are simple cylindrical (plate carree) global mosaics, uncompressed
# 16-bit signed, one strip per row.
BODIES = {
    "mars": {
        "url": "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif",
        "metres_per_pixel": 463.0,
        "units_per_metre": 1.0,          # MOLA DEM is metres above the areoid
        "source": "USGS / MGS MOLA 463 m global DEM",
        "surface": "Mars",
    },
    "moon": {
        "url": "https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif",
        "metres_per_pixel": 118.45,
        "units_per_metre": 2.0,          # LOLA LDEM is stored in half metres
        "source": "USGS / LRO LOLA 118 m global DEM",
        "surface": "Moon",
    },
}

# Somewhere to start, so nobody has to look up coordinates to try it.
PLACES = {
    "mars": {
        "gale":     (-5.4, 137.8, "Gale Crater, where Curiosity landed"),
        "olympus":  (18.65, 226.2, "Olympus Mons, the largest volcano known"),
        "valles":   (-14.0, 301.4, "Valles Marineris, a canyon the length of the USA"),
        "jezero":   (18.44, 77.45, "Jezero Crater, where Perseverance landed"),
        "hellas":   (-42.4, 70.5, "Hellas Planitia, the deepest place on Mars"),
    },
    "moon": {
        "tranquillity": (0.67, 23.47, "Tranquility Base, Apollo 11"),
        "tycho":        (-43.31, 348.68, "Tycho, the crater with the bright rays"),
        "copernicus":   (9.62, 339.92, "Copernicus, terraced walls and a central peak"),
        "hadley":       (26.13, 3.63, "Hadley Rille, Apollo 15"),
        "shackleton":   (-89.9, 0.0, "Shackleton, on the south pole"),
    },
}

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8,
             11: 4, 12: 8, 16: 8, 17: 8, 18: 8}


# ── reading a window out of a remote TIFF ──────────────────────────────────

def _get(url, start, end):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Range": "bytes=%d-%d" % (start, end)})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def read_tiff_header(url):
    """Enough of the TIFF header to know where each row of pixels lives.

    Deliberately narrow: these two files are uncompressed with one strip per
    row, and anything else raises rather than being guessed at. A silently
    misread header would produce a landscape that looks plausible and is wrong.
    """
    head = _get(url, 0, 65535)
    if head[:2] not in (b"II", b"MM"):
        raise ValueError("not a TIFF: %r" % head[:4])
    bo = "<" if head[:2] == b"II" else ">"

    # Mars is classic TIFF; the Moon is BigTIFF, because at 8.5 GB it has to be
    # -- classic TIFF offsets are 32-bit and cannot address past 4 GB. Same
    # layout otherwise, with 64-bit counts and offsets and 20-byte entries.
    magic = struct.unpack(bo + "H", head[2:4])[0]
    if magic == 42:
        big = False
        ifd = struct.unpack(bo + "I", head[4:8])[0]
    elif magic == 43:
        big = True
        offset_size = struct.unpack(bo + "H", head[4:6])[0]
        if offset_size != 8:
            raise ValueError("BigTIFF with %d-byte offsets is not handled" % offset_size)
        ifd = struct.unpack(bo + "Q", head[8:16])[0]
    else:
        raise ValueError("not a TIFF: magic %d" % magic)

    def at(off, n):
        return head[off:off + n] if off + n <= len(head) else _get(url, off, off + n - 1)

    if big:
        count = struct.unpack(bo + "Q", at(ifd, 8))[0]
        entry_size, header_size, off_fmt, inline_max = 20, 8, "Q", 8
    else:
        count = struct.unpack(bo + "H", at(ifd, 2))[0]
        entry_size, header_size, off_fmt, inline_max = 12, 2, "I", 4

    entries = at(ifd + header_size, count * entry_size)
    tags = {}
    for i in range(count):
        e = entries[i * entry_size:(i + 1) * entry_size]
        if big:
            tag, typ, cnt = struct.unpack(bo + "HHQ", e[:12])
            payload = e[12:20]
        else:
            tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
            payload = e[8:12]
        nbytes = TYPE_SIZE.get(typ, 1) * cnt
        raw = payload if nbytes <= inline_max else at(
            struct.unpack(bo + off_fmt, payload)[0], nbytes)
        fmt = {1: "B", 3: "H", 4: "I", 16: "Q", 6: "b", 8: "h", 9: "i"}.get(typ)
        if fmt:
            tags[tag] = struct.unpack(bo + fmt * cnt, raw[:struct.calcsize(fmt) * cnt])
        else:
            tags[tag] = raw          # doubles and the like, decoded by the caller

    info = {
        "byte_order": bo,
        "width": tags[256][0],
        "height": tags[257][0],
        "bits": tags[258][0],
        "compression": tags.get(259, (1,))[0],
        "rows_per_strip": tags.get(278, (1,))[0],
        "strip_offsets": tags[273],
        "strip_bytes": tags[279],
        "sample_format": tags.get(339, (1,))[0],
    }

    # Where the image actually sits. Guessing this is the mistake that hurts:
    # the wrong longitude convention puts you somewhere else entirely and the
    # elevations still look like a landscape, so nothing announces the error.
    if 33550 in tags and 33922 in tags:
        scale = struct.unpack(bo + "3d", bytes(tags[33550]) if not isinstance(tags[33550], bytes)
                              else tags[33550])
        tie = struct.unpack(bo + "6d", bytes(tags[33922]) if not isinstance(tags[33922], bytes)
                            else tags[33922])
        info["x_min"] = tie[3]
        info["y_max"] = tie[4]
        info["x_scale"] = scale[0]
        info["y_scale"] = scale[1]
        info["x_max"] = tie[3] + info["width"] * scale[0]
        info["y_min"] = tie[4] - info["height"] * scale[1]
    else:
        raise ValueError("no georeferencing tags; refusing to guess where this is")
    if info["compression"] != 1:
        raise ValueError("this only reads uncompressed TIFFs (compression=%d)"
                         % info["compression"])
    if info["rows_per_strip"] != 1:
        raise ValueError("this expects one strip per row (got %d)" % info["rows_per_strip"])
    if info["bits"] != 16:
        raise ValueError("this expects 16-bit samples (got %d)" % info["bits"])
    return info


def read_window(url, info, row0, col0, rows, cols):
    """A rows x cols window, read as one contiguous range request.

    Rows are contiguous in the file, so the whole block is one range. That
    pulls in columns nobody asked for -- the full width of each row -- but one
    request of a few tens of megabytes beats several hundred small ones, and
    the wasted bytes never touch the disk.
    """
    bo = info["byte_order"]
    width = info["width"]
    row_bytes = info["strip_bytes"][0]

    start = info["strip_offsets"][row0]
    end = info["strip_offsets"][row0 + rows - 1] + row_bytes - 1
    raw = _get(url, start, end)

    dtype = np.dtype(("<i2" if bo == "<" else ">i2"))
    block = np.frombuffer(raw, dtype=dtype, count=rows * width).reshape(rows, width)
    # Wrap in longitude, so a window across the antimeridian still works.
    idx = (np.arange(col0, col0 + cols) % width)
    return block[:, idx].astype(np.float32)


# ── geography ──────────────────────────────────────────────────────────────

def pixel_for(lat, lon, info):
    """Which pixel a latitude and longitude fall on, from the file's own extent.

    Both mosaics are simple cylindrical in projected metres and run -180..180,
    but that is read from the tie point rather than assumed. Getting it wrong
    is not loud: 137.8 East read as though the image started at 0 lands a third
    of the way round the planet, on terrain that looks perfectly reasonable.
    """
    # Longitude east, folded to the range the image actually covers.
    lon = ((lon + 180.0) % 360.0) - 180.0

    x_span = info["x_max"] - info["x_min"]
    y_span = info["y_max"] - info["y_min"]
    x = (lon + 180.0) / 360.0 * x_span + info["x_min"]
    y = info["y_max"] - (90.0 - lat) / 180.0 * y_span

    col = int(round((x - info["x_min"]) / info["x_scale"]))
    row = int(round((info["y_max"] - y) / info["y_scale"]))
    return col, row


# ── main ───────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--body", choices=sorted(BODIES), default="mars")
    p.add_argument("--place", help="a named landing site or feature; --list to see them")
    p.add_argument("--lat", type=float, help="centre latitude, if not using --place")
    p.add_argument("--lon", type=float, help="centre longitude, degrees east")
    p.add_argument("--size", type=int, default=400, help="window across, in pixels (default 400)")
    p.add_argument("--vscale", type=float, default=1.0,
                   help="vertical exaggeration; 1 is true scale (default 1)")
    p.add_argument("--name", help="output name (default: body_place)")
    p.add_argument("--list", action="store_true", help="list the named places and stop")
    args = p.parse_args()

    if args.list:
        for body in sorted(PLACES):
            print(body + ":")
            for name, (lat, lon, what) in sorted(PLACES[body].items()):
                print("  %-14s %7.2f, %7.2f   %s" % (name, lat, lon, what))
        return

    body = BODIES[args.body]
    if args.place:
        if args.place not in PLACES[args.body]:
            sys.exit("No place called %r on %s. Try --list." % (args.place, args.body))
        lat, lon, what = PLACES[args.body][args.place]
    elif args.lat is not None and args.lon is not None:
        lat, lon, what = args.lat, args.lon, "%.2f, %.2f" % (args.lat, args.lon)
    else:
        sys.exit("Give --place, or both --lat and --lon. --list shows the places.")

    name = args.name or ("%s_%s" % (args.body, args.place or "custom"))
    mpp = body["metres_per_pixel"]

    print("%s: %s" % (body["surface"], what))
    print("  reading the header of a %s global DEM" % body["surface"])
    info = read_tiff_header(body["url"])
    print("  %d x %d, %d-bit, %.0f m per pixel"
          % (info["width"], info["height"], info["bits"], mpp))

    cx, cy = pixel_for(lat, lon, info)
    half = args.size // 2
    row0 = max(0, min(cy - half, info["height"] - args.size))
    col0 = cx - half

    span_km = args.size * mpp / 1000.0
    mb = args.size * info["strip_bytes"][0] / 1e6
    print("  window %d x %d pixels = %.0f x %.0f km  (about %.0f MB of range requests)"
          % (args.size, args.size, span_km, span_km, mb))

    raw = read_window(body["url"], info, row0, col0, args.size, args.size)
    ground = raw / body["units_per_metre"]

    # The nodata value in both products is the most negative 16-bit integer.
    ground[raw <= -32768 + 1] = np.nan
    lo, hi = float(np.nanmin(ground)), float(np.nanmax(ground))
    print("  elevation %.0f to %.0f m  (relief %.0f m over %.0f km)"
          % (lo, hi, hi - lo, span_km))

    if args.vscale != 1.0:
        mid = (lo + hi) / 2.0
        ground = (ground - mid) * args.vscale + mid
        print("  vertical exaggeration x%.1f -> relief %.0f m"
              % (args.vscale, (hi - lo) * args.vscale))

    # One block per pixel horizontally, one block per metre_per_pixel vertically,
    # so the aspect ratio is true unless --vscale says otherwise.
    ground_blocks = ground / mpp

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name + ".npz")
    np.savez_compressed(
        out,
        ground=ground_blocks.astype(np.float32),
        buildings=np.zeros(ground.shape, dtype=np.float32),
        meta=json.dumps({
            "body": args.body, "place": args.place, "what": what,
            "lat": lat, "lon": lon, "size": args.size,
            "metres_per_pixel": mpp, "vscale": args.vscale,
            "elevation_min_m": lo, "elevation_max_m": hi,
            "metres_per_cell": mpp,
            "source_ground": body["source"],
        }),
    )
    print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024.0))
    print("now run:  python build_town.py --name %s" % name)


if __name__ == "__main__":
    main()
