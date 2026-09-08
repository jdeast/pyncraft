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
import warnings

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
        "projection": {"kind": "cylindrical"},
    },
    "moon": {
        "url": "https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif",
        "metres_per_pixel": 118.45,
        "units_per_metre": 2.0,          # LOLA LDEM is stored in half metres
        "source": "USGS / LRO LOLA 118 m global DEM",
        "surface": "Moon",
        "projection": {"kind": "cylindrical"},
    },
}

# -- the metre-scale ones ---------------------------------------------------
#
# The global mosaics above cover everywhere, which is why they are coarse.
# For the places anybody actually wants to stand there is far better, and it
# is the same kind of file served the same way, so the reader below needs
# almost nothing new to handle it.
#
#   LOLA global      118 m/pixel   the whole Moon
#   SLDEM2015         59 m/pixel   LOLA merged with Kaguya, within 60 deg
#   LOLA south pole  10-240 m/px   the Artemis end of the Moon
#   LOLA site grids     5 m/pixel  ten candidate south pole landing sites
#   LROC NAC DTM      1-2 m/pixel  stereo pairs, the Apollo sites among them
#
# At 118 m a Lunar Module is one sixteenth of a block and has to be built on
# a pad beside the map with a sign apologising for the scale. At 2 m it is
# four blocks tall and can stand where it actually stands.
#
# These are per-site rasters in their own map projections, not global
# cylindrical mosaics, so each carries the projection needed to find a pixel
# in it. Those parameters are not guessed: they are what the file's own
# GeoTIFF keys say, and unproject() below turns the corner pixels back into
# latitude and longitude to check they reproduce the published extent.
SITE_DEMS = {
    "apollo11": {
        "body": "moon",
        "url": "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/"
               "LROLRC_2001/DATA/SDP/NAC_DTM/APOLLO11/NAC_DTM_APOLLO11.TIF",
        "metres_per_pixel": 2.0,
        "units_per_metre": 1.0,
        "lat": 0.674, "lon": 23.473,
        "what": "Apollo 11, Tranquility Base -- LROC NAC stereo DTM",
        "source": "LROC / NAC_DTM_APOLLO11, 2 m per pixel",
        "extent": None,
        "projection": {"kind": "equirectangular", "radius_m": 1737400.0,
                       "centre_lon": 180.0, "standard_parallel": 1.0},
    },
    "apollo12": {
        "body": "moon",
        "url": "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/"
               "LROLRC_2001/DATA/SDP/NAC_DTM/APOLLO12/NAC_DTM_APOLLO12.TIF",
        "metres_per_pixel": 2.0,
        "units_per_metre": 1.0,
        "lat": -3.012, "lon": 336.578,
        "what": "Apollo 12, Surveyor Crater -- LROC NAC stereo DTM",
        "source": "LROC / NAC_DTM_APOLLO12, 2 m per pixel",
        "extent": None,
        "projection": {"kind": "equirectangular", "radius_m": 1737400.0,
                       "centre_lon": 180.0, "standard_parallel": -3.0},
    },
    "apollo14": {
        "body": "moon",
        "url": "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/"
               "LROLRC_2001/DATA/SDP/NAC_DTM/APOLLO14/NAC_DTM_APOLLO14.TIF",
        "metres_per_pixel": 2.0,
        "units_per_metre": 1.0,
        "lat": -3.645, "lon": 342.522,
        "what": "Apollo 14, Fra Mauro and Cone Crater -- LROC NAC stereo DTM",
        "source": "LROC / NAC_DTM_APOLLO14, 2 m per pixel",
        "extent": None,
        "projection": {"kind": "equirectangular", "radius_m": 1737400.0,
                       "centre_lon": 180.0, "standard_parallel": -3.0},
    },
    "apollo15": {
        "body": "moon",
        "url": "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/"
               "LROLRC_2001/DATA/SDP/NAC_DTM/APOLLO15/NAC_DTM_APOLLO15.TIF",
        "metres_per_pixel": 2.0,
        "units_per_metre": 1.0,
        "lat": 26.132, "lon": 3.634,
        "what": "Apollo 15, Hadley Rille -- LROC NAC stereo DTM",
        "source": "LROC / NAC_DTM_APOLLO15, 2 m per pixel",
        "extent": (25.59, 26.54, 3.50, 3.69),
        "projection": {"kind": "equirectangular", "radius_m": 1737400.0,
                       "centre_lon": 180.0, "standard_parallel": 26.0},
    },
    "malapert": {
        "body": "moon",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site23/"
               "Site23_final_adj_5mpp_surf.tif",
        "metres_per_pixel": 5.0,
        "units_per_metre": 1.0,
        "lat": -85.964, "lon": 357.681,
        "what": "Malapert Massif -- Artemis candidate site 23, LOLA 5 m",
        "source": "NASA PGDA / LOLA 5 m south pole site grid (Barker+ 2021)",
        "extent": None,
        "projection": {"kind": "polar_stereographic", "radius_m": 1737400.0,
                       "centre_lon": 0.0, "scale_factor": 1.0, "south": True},
    },
}

# The other nine 5 m/pixel south pole grids, on the same server under the same
# naming. Adding one is a line in SITE_DEMS above, which is the exercise.
OTHER_5M_SITES = {
    "Site01": "Connecting ridge", "Site04": "Shackleton rim",
    "Site06": "Nobile rim 1", "Site07": "Peak near Shackleton",
    "Site11": "de Gerlache rim", "Site20": "Leibnitz beta plateau",
    "Haworth": "Haworth", "Shoemaker": "Shoemaker", "DM2": "Nobile rim 2",
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
    # 16-bit signed integers for the global mosaics, 32-bit floats for the
    # site DEMs. Both are fixed width and uncompressed, so the arithmetic that
    # finds a row is unchanged; only the dtype differs.
    if info["bits"] == 16 and info["sample_format"] in (1, 2):
        info["sample_dtype"] = "i2"
        info["nodata"] = -32767.0
    elif info["bits"] == 32 and info["sample_format"] == 3:
        info["sample_dtype"] = "f4"
        info["nodata"] = None
    else:
        raise ValueError("this reads 16-bit integer or 32-bit float samples, "
                         "not %d-bit format %d" % (info["bits"], info["sample_format"]))

    # GDAL writes the nodata value as an ASCII string in tag 42113. Both site
    # DEMs have one -- a huge negative number for the NAC DTM, a literal "nan"
    # for the LOLA grid -- and without it the gaps in coverage build as a floor
    # at minus 3e38, which is not a subtle wrongness but is an avoidable one.
    if 42113 in tags:
        try:
            info["nodata"] = float(
                bytes(tags[42113]).decode("ascii", "replace").strip("\x00 \t"))
        except (TypeError, ValueError):
            pass
    return info


def downsample(grid, stride):
    """Average stride x stride pixels into one, ignoring gaps.

    Taking every nth pixel instead would be quicker and wrong: it is point
    sampling a surface with real detail in it, so a narrow ridge either
    survives at full height or vanishes entirely depending on where the grid
    happens to fall. Averaging keeps the shape and quietly loses the detail,
    which is what a coarser map is supposed to do.

    A window is trimmed to a whole number of blocks first, so the last part
    row is dropped rather than averaged against nothing.
    """
    stride = int(stride)
    if stride <= 1:
        return grid
    rows = (grid.shape[0] // stride) * stride
    cols = (grid.shape[1] // stride) * stride
    block = grid[:rows, :cols].reshape(rows // stride, stride,
                                       cols // stride, stride)
    with warnings.catch_warnings():
        # A block that is entirely nodata averages to nan, which is correct
        # and which numpy would rather warn about every time.
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(block, axis=(1, 3))


def read_window(url, info, row0, col0, rows, cols, wrap=True):
    """A rows x cols window, read as one contiguous range request.

    Rows are contiguous in the file, so the whole block is one range. That
    pulls in columns nobody asked for -- the full width of each row -- but one
    request of a few tens of megabytes beats several hundred small ones, and
    the wasted bytes never touch the disk.
    """
    bo = info["byte_order"]
    width = info["width"]
    offsets = info["strip_offsets"]
    counts = info["strip_bytes"]
    dtype = np.dtype(bo + info["sample_dtype"])

    # Rows are NOT necessarily in file order.
    #
    # Apollo 15 stores them one after another, which is what this used to
    # assume: take the offset of the first row, the offset of the last, and
    # ask for everything between. Apollo 12 keeps row 0 at the very END of the
    # file, after every other row, with a gap in the middle for good measure.
    # Reading it as one run returned bytes that were all real numbers from
    # somewhere in the image, just not the rows asked for -- elevations came
    # out at 3e38 and the landscape was noise.
    #
    # So: group the wanted rows into runs that really are contiguous, and ask
    # for one byte range per run. A file that is in order still costs exactly
    # one request. Runs are also capped, because a single very large range
    # comes back truncated from this server and numpy then reads off the end.
    MAX_RUN = 8 << 20
    runs = []
    for r in range(row0, row0 + rows):
        off, cnt = offsets[r], counts[r]
        if runs and off == runs[-1][1] and (off + cnt - runs[-1][0]) <= MAX_RUN:
            runs[-1][1] = off + cnt
            runs[-1][2].append(r)
        else:
            runs.append([off, off + cnt, [r]])

    rowdata = {}
    for start, end, wanted in runs:
        raw = _get(url, start, end - 1)
        if len(raw) < end - start:
            raise ValueError("short read: asked for %d bytes, got %d"
                             % (end - start, len(raw)))
        pos = 0
        for r in wanted:
            rowdata[r] = np.frombuffer(raw, dtype=dtype, count=width, offset=pos)
            pos += counts[r]

    block = np.stack([rowdata[r] for r in range(row0, row0 + rows)])
    if wrap:
        # A global mosaic joins up, so a window across the antimeridian works.
        idx = np.arange(col0, col0 + cols) % width
    else:
        # A site raster does not. Running off the edge should hold the edge
        # rather than reappear on the far side of the image.
        idx = np.clip(np.arange(col0, col0 + cols), 0, width - 1)
    return block[:, idx].astype(np.float32)


# ── geography ──────────────────────────────────────────────────────────────

def _project(lat, lon, info, proj):
    """Latitude and longitude to the raster's own projected metres."""
    kind = proj["kind"]

    if kind == "cylindrical":
        # A global mosaic: use the image's own extent rather than a formula,
        # because the tie point is the only thing that says where zero is.
        lon = ((lon + 180.0) % 360.0) - 180.0
        x_span = info["x_max"] - info["x_min"]
        y_span = info["y_max"] - info["y_min"]
        return ((lon + 180.0) / 360.0 * x_span + info["x_min"],
                info["y_max"] - (90.0 - lat) / 180.0 * y_span)

    R = proj["radius_m"]
    dlon = ((lon - proj.get("centre_lon", 0.0) + 180.0) % 360.0) - 180.0

    if kind == "equirectangular":
        # Spherical, with the parallel of true scale the file names.
        return (R * math.radians(dlon)
                * math.cos(math.radians(proj.get("standard_parallel", 0.0))),
                R * math.radians(lat))

    if kind == "polar_stereographic":
        k0 = proj.get("scale_factor", 1.0)
        a = math.radians(dlon)
        if proj.get("south"):
            rho = 2.0 * R * k0 * math.tan(math.pi / 4.0 + math.radians(lat) / 2.0)
            return rho * math.sin(a), rho * math.cos(a)
        rho = 2.0 * R * k0 * math.tan(math.pi / 4.0 - math.radians(lat) / 2.0)
        return rho * math.sin(a), -rho * math.cos(a)

    raise ValueError("unknown projection %r" % kind)


def unproject(col, row, info, proj):
    """The other way round, which is what checks the projection is right.

    Nothing is built with this -- it is the test. If turning pixel 0,0 back
    into a latitude and longitude does not reproduce the extent the product
    publishes, the forward projection is wrong, and the landscape would come
    out somewhere else entirely while still looking perfectly plausible.
    """
    x = info["x_min"] + col * info["x_scale"]
    y = info["y_max"] - row * info["y_scale"]
    kind = proj["kind"]

    if kind == "cylindrical":
        x_span = info["x_max"] - info["x_min"]
        y_span = info["y_max"] - info["y_min"]
        return (90.0 - (info["y_max"] - y) / y_span * 180.0,
                (x - info["x_min"]) / x_span * 360.0 - 180.0)

    R = proj["radius_m"]
    lon0 = proj.get("centre_lon", 0.0)

    if kind == "equirectangular":
        lat = math.degrees(y / R)
        lon = lon0 + math.degrees(x / (R * math.cos(
            math.radians(proj.get("standard_parallel", 0.0)))))
        return lat, ((lon + 180.0) % 360.0) - 180.0

    if kind == "polar_stereographic":
        k0 = proj.get("scale_factor", 1.0)
        c = 2.0 * math.atan(math.hypot(x, y) / (2.0 * R * k0))
        if proj.get("south"):
            lat = math.degrees(c - math.pi / 2.0)
            lon = lon0 + math.degrees(math.atan2(x, y))
        else:
            lat = math.degrees(math.pi / 2.0 - c)
            lon = lon0 + math.degrees(math.atan2(x, -y))
        return lat, ((lon + 180.0) % 360.0) - 180.0

    raise ValueError("unknown projection %r" % kind)


def pixel_for(lat, lon, info, proj=None):
    """Which pixel a latitude and longitude fall on, from the file's own extent.

    Both mosaics are simple cylindrical in projected metres and run -180..180,
    but that is read from the tie point rather than assumed. Getting it wrong
    is not loud: 137.8 East read as though the image started at 0 lands a third
    of the way round the planet, on terrain that looks perfectly reasonable.
    """
    x, y = _project(lat, lon, info, proj or {"kind": "cylindrical"})
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
    p.add_argument("--size", type=int, default=400,
                   help="window across, in PIXELS of the source map (default 400)")
    p.add_argument("--rows", type=int,
                   help="window north-south, in pixels (default: same as --size). "
                        "The interesting axis is often only one of them")
    p.add_argument("--stride", type=int, default=1,
                   help="average this many pixels square into one block. A 2 m "
                        "DEM at --stride 3 is 6 m to the block, which is how a "
                        "window covers ground it could not afford at full "
                        "resolution (default 1)")
    p.add_argument("--vscale", type=float, default=1.0,
                   help="vertical exaggeration; 1 is true scale (default 1)")
    p.add_argument("--name", help="output name (default: body_place)")
    p.add_argument("--dem", choices=sorted(SITE_DEMS),
                   help="use a metre-scale site DEM instead of the global mosaic")
    p.add_argument("--list", action="store_true", help="list the named places and stop")
    p.add_argument("--check", action="store_true",
                   help="project the corners back to lat/lon and stop, to prove "
                        "the DEM is being read where it actually is")
    args = p.parse_args()

    if args.list:
        for body in sorted(PLACES):
            print(body + ":")
            for name, (lat, lon, what) in sorted(PLACES[body].items()):
                print("  %-14s %7.2f, %7.2f   %s" % (name, lat, lon, what))
        print()
        print("metre-scale site DEMs (--dem), far better than the global mosaic:")
        for name, d in sorted(SITE_DEMS.items()):
            print("  %-14s %7.2f, %7.2f   %g m/pixel  %s"
                  % (name, d["lat"], d["lon"], d["metres_per_pixel"], d["what"]))
        print()
        print("Nine more LOLA 5 m south pole grids exist and are not wired up yet:")
        for key, what in sorted(OTHER_5M_SITES.items()):
            print("    %-10s %s" % (key, what))
        print("  They are at https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/<name>/")
        print("  named <name>_final_adj_5mpp_surf.tif, same projection as")
        print("  malapert above. Adding one is a line in SITE_DEMS.")
        return

    # A site DEM overrides the body: it is a different file, in its own
    # projection, and it decides which body we are on.
    dem = None
    if args.dem:
        dem = SITE_DEMS[args.dem]
        args.body = dem["body"]
    body = BODIES[args.body]
    if dem and not args.place and args.lat is None:
        lat, lon, what = dem["lat"], dem["lon"], dem["what"]
    elif args.place:
        if args.place not in PLACES[args.body]:
            sys.exit("No place called %r on %s. Try --list." % (args.place, args.body))
        lat, lon, what = PLACES[args.body][args.place]
    elif args.lat is not None and args.lon is not None:
        lat, lon, what = args.lat, args.lon, "%.2f, %.2f" % (args.lat, args.lon)
    else:
        sys.exit("Give --place, or both --lat and --lon. --list shows the places.")

    source = dem or body
    name = args.name or ("%s_%s" % (args.body, args.dem or args.place or "custom"))
    mpp = source["metres_per_pixel"]
    proj = source.get("projection", {"kind": "cylindrical"})
    url = source["url"]

    print("%s: %s" % (body["surface"], what))
    print("  reading the header of %s"
          % (("the %s global DEM" % body["surface"]) if not dem else source["source"]))
    info = read_tiff_header(url)
    print("  %d x %d, %d-bit %s, %g m per pixel"
          % (info["width"], info["height"], info["bits"],
             "float" if info["sample_dtype"] == "f4" else "integer", mpp))

    # Prove the projection before reading a single pixel of data. Turning the
    # corners back into latitude and longitude costs nothing and catches the
    # one error that never announces itself -- reading the right file in the
    # wrong place, which still produces a perfectly convincing landscape.
    if dem or args.check:
        (n_lat, w_lon) = unproject(0, 0, info, proj)
        (s_lat, e_lon) = unproject(info["width"] - 1, info["height"] - 1, info, proj)
        print("  covers  lat %.4f to %.4f,  lon %.4f to %.4f"
              % (min(n_lat, s_lat), max(n_lat, s_lat),
                 min(w_lon, e_lon), max(w_lon, e_lon)))
        if dem and dem.get("extent"):
            lo_la, hi_la, lo_lo, hi_lo = dem["extent"]
            print("  published %.2f to %.2f,  %.2f to %.2f  (should match above)"
                  % (lo_la, hi_la, lo_lo, hi_lo))
        print("  %.2f x %.2f km at %g m per pixel"
              % (info["width"] * mpp / 1000.0, info["height"] * mpp / 1000.0, mpp))
    if args.check:
        return

    rows_wanted = args.rows or args.size
    cx, cy = pixel_for(lat, lon, info, proj)
    half = args.size // 2
    half_rows = rows_wanted // 2

    # A global mosaic wraps and is huge, so a window always fits. A site DEM
    # is a few thousand pixels across and asking for the middle of a 21 km
    # square is easy to get wrong, so say so rather than silently clamping to
    # a corner and building the wrong hillside.
    if dem:
        if not (0 <= cx < info["width"] and 0 <= cy < info["height"]):
            sys.exit("%.4f, %.4f is not inside %s (pixel %d,%d of %d x %d).\n"
                     "Use --check to see what it covers."
                     % (lat, lon, args.dem, cx, cy, info["width"], info["height"]))
        if args.size > info["width"]:
            print("  note: --size %d is wider than the DEM (%d); trimming"
                  % (args.size, info["width"]))
            args.size = info["width"]
            half = args.size // 2
        if rows_wanted > info["height"]:
            rows_wanted = info["height"]
            half_rows = rows_wanted // 2
        col0 = max(0, min(cx - half, info["width"] - args.size))
    else:
        col0 = cx - half
    row0 = max(0, min(cy - half_rows, info["height"] - rows_wanted))

    span_x = args.size * mpp / 1000.0
    span_z = rows_wanted * mpp / 1000.0
    mb = rows_wanted * info["strip_bytes"][0] / 1e6
    print("  window %d x %d pixels = %.2f x %.2f km  (about %.0f MB of range requests)"
          % (args.size, rows_wanted, span_x, span_z, mb))

    raw = read_window(url, info, row0, col0, rows_wanted, args.size,
                      wrap=dem is None)

    # Gaps become NaN BEFORE anything averages them. The global mosaics mark
    # nodata with the most negative 16-bit integer; the site DEMs say what
    # they use in the TIFF, and for the NAC DTM that is -3.4e38.
    #
    # Averaging first is a quiet disaster: one nodata pixel in a 2x2 block
    # drags the average to -8.5e37, which is not obviously a gap, is not
    # caught by a later "is this the nodata value" test because it no longer
    # equals it, and builds as a hole a hundred billion times deeper than the
    # crater. NaN spreads harmlessly instead, and nanmean ignores it.
    nodata = info.get("nodata")
    if nodata is not None and nodata == nodata:
        raw[raw <= nodata + abs(nodata) * 1e-6] = np.nan
    raw[~np.isfinite(raw)] = np.nan

    if args.stride > 1:
        before = raw.shape
        raw = downsample(raw, args.stride)
        mpp = mpp * args.stride
        print("  averaged %dx%d pixels per block: %s -> %s at %g m per block"
              % (args.stride, args.stride, "x".join(map(str, before)),
                 "x".join(map(str, raw.shape)), mpp))
    ground = raw / source["units_per_metre"]
    gaps = int(np.isnan(ground).sum())
    if gaps:
        print("  %d of %d pixels have no data (%.1f%%)"
              % (gaps, ground.size, 100.0 * gaps / ground.size))
    lo, hi = float(np.nanmin(ground)), float(np.nanmax(ground))
    print("  elevation %.0f to %.0f m  (relief %.0f m over %.2f km)"
          % (lo, hi, hi - lo, max(span_x, span_z)))

    if args.vscale != 1.0:
        mid = (lo + hi) / 2.0
        ground = (ground - mid) * args.vscale + mid
        print("  vertical exaggeration x%.1f -> relief %.0f m"
              % (args.vscale, (hi - lo) * args.vscale))

    # Stored in METRES, the same as fetch_terrain.py, because build_town.py is
    # what knows how many metres a block is and does the conversion. Dividing
    # here as well would shrink everything by that factor twice over.

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name + ".npz")
    np.savez_compressed(
        out,
        ground=ground.astype(np.float32),
        buildings=np.zeros(ground.shape, dtype=np.float32),
        meta=json.dumps({
            "body": args.body, "place": args.place, "what": what,
            "lat": lat, "lon": lon, "size": args.size,
            "rows": rows_wanted, "stride": args.stride,
            "metres_per_pixel": mpp, "vscale": args.vscale,
            "elevation_min_m": lo, "elevation_max_m": hi,
            "metres_per_cell": mpp,
            "dem": args.dem,
            "source_ground": source["source"],
        }),
    )
    print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024.0))
    print("now run:  python build_town.py --name %s" % name)


if __name__ == "__main__":
    main()
