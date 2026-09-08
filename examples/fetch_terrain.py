#!/usr/bin/env python3
"""Fetch real terrain and buildings for a place, ready to build in Minecraft.

    python fetch_terrain.py --lat 42.4219085 --lon -71.0992821 \
                            --size 400 --name roberts

Writes data/<name>.npz holding a ground heightmap and a building height map,
both one metre per cell, which is the same as one Minecraft block. build_town.py
reads that file and puts it in the world; you only need this script if you want
somewhere other than the place already shipped.

WHY THERE IS NO GDAL HERE

The obvious tools are rasterio and pyproj, and they drag in GDAL. That is a
wall for exactly the person this is for: a kid on a school laptop, where a
dependency that compiles from source simply fails. So instead:

  - The elevation service is asked to reproject, by passing the bounding box in
    UTM metres and asking for the image in the same. No client-side warping.
  - The GeoTIFF that comes back is read with Pillow, which handles 32-bit float
    TIFF and has wheels everywhere.
  - The one piece of projection maths, WGS84 latitude/longitude to UTM, is
    thirty lines below and is checked against the elevation service's own
    answer by --check.

That leaves requests, Pillow and numpy, all of which install anywhere.

WHAT IT WILL AND WILL NOT GIVE YOU

Ground comes from USGS 3DEP lidar, which is bare earth: buildings and trees are
already removed. Buildings come from OpenStreetMap footprints, extruded to
their tagged height, or to three metres per storey, or to a default when
untagged.

That means the OUTSIDE of buildings, at one-metre resolution. It does not mean
windows, doors, or anything indoors, and no public dataset offers those. For a
school, that boundary is not an accident worth working around: interior floor
plans are exempt from disclosure under most states' public records laws
precisely because they are the reconnaissance material for attacking one.
Build the shell from real data and let the people who use the building design
the inside.
"""
import argparse
import io
import json
import math
import os
import sys
import urllib.parse
import urllib.request

try:
    import numpy as np
except ImportError:
    sys.exit("This needs numpy: pip install numpy")

try:
    from PIL import Image
except ImportError:
    sys.exit("This needs Pillow to read the elevation GeoTIFF: pip install pillow")


ELEVATION = ("https://elevation.nationalmap.gov/arcgis/rest/services"
             "/3DEPElevation/ImageServer/exportImage")
OVERPASS = "https://overpass-api.de/api/interpreter"

# Public services rightly want to know who is calling. Overpass answers an
# unidentified urllib with a 406 that does not say why.
USER_AGENT = "pyncraft fetch_terrain (https://github.com/jdeast/pyncraft)"

DEFAULT_STOREY_HEIGHT = 3.0     # metres, when a building says how many floors
DEFAULT_BUILDING_HEIGHT = 6.0   # metres, when it says nothing at all


# ── projection ─────────────────────────────────────────────────────────────

def to_utm(lat, lon):
    """WGS84 latitude/longitude to UTM easting, northing and zone.

    Northern hemisphere only, which covers the United States. Checked against
    the elevation service's own reprojection by --check; they agree to about a
    metre, which is the size of one block.
    """
    a = 6378137.0                       # WGS84 semi-major axis
    f = 1 / 298.257223563               # flattening
    k0 = 0.9996                         # UTM scale factor on the central meridian
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)

    zone = int((lon + 180) / 6) + 1
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    p = math.radians(lat)
    l = math.radians(lon)

    N = a / math.sqrt(1 - e2 * math.sin(p) ** 2)
    T = math.tan(p) ** 2
    C = ep2 * math.cos(p) ** 2
    A = math.cos(p) * (l - lon0)

    M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * p
             - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * p)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * p)
             - (35 * e2 ** 3 / 3072) * math.sin(6 * p))

    east = k0 * N * (A + (1 - T + C) * A ** 3 / 6
                     + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000.0
    north = k0 * (M + N * math.tan(p) * (A ** 2 / 2
                  + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24
                  + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6 / 720))
    return east, north, zone


def utm_epsg(zone):
    """NAD83 UTM, which is what USGS elevation data is published in."""
    return 26900 + zone


# ── fetching ───────────────────────────────────────────────────────────────

def get(url, params, binary=False, timeout=120):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if binary else json.loads(data)


def fetch_elevation(east, north, half, zone, verbose=True):
    """A square of bare-earth elevation, one metre per pixel, in metres.

    The bounding box is given in UTM and the image is asked for in UTM, so the
    service does the reprojection and every pixel is already a square metre.
    Asking in latitude/longitude instead lets the service pick its own extent
    to match the requested aspect ratio, which silently widens the area.
    """
    size = int(half * 2)
    bbox = "%f,%f,%f,%f" % (east - half, north - half, east + half, north + half)
    sr = utm_epsg(zone)
    params = {
        "bbox": bbox, "bboxSR": sr, "imageSR": sr,
        "size": "%d,%d" % (size, size),
        "format": "tiff", "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    }
    if verbose:
        print("  elevation: %dx%d m around %.1f, %.1f (UTM %d)" % (size, size, east, north, zone))
    tif = get(ELEVATION, params, binary=True)
    ground = np.array(Image.open(io.BytesIO(tif))).astype(np.float32)

    # The service returns very negative values where it has no data.
    ground[ground < -1000] = np.nan
    return ground


def fetch_buildings(lat, lon, half_deg, verbose=True):
    """Building footprints from OpenStreetMap, with whatever height they carry."""
    query = """
[out:json][timeout:60];
(way["building"](%f,%f,%f,%f););
out geom tags;
""" % (lat - half_deg, lon - half_deg, lat + half_deg, lon + half_deg)

    if verbose:
        print("  buildings: querying OpenStreetMap")
    # Overpass wants the query as a form field, and refuses urllib's default
    # User-Agent with a 406 that says nothing about why.
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())

    buildings = []
    for element in data.get("elements", []):
        geometry = element.get("geometry")
        if not geometry or len(geometry) < 3:
            continue
        tags = element.get("tags", {})
        buildings.append({
            "points": [(p["lat"], p["lon"]) for p in geometry],
            "height": building_height(tags),
            "name": tags.get("name", ""),
        })
    return buildings


def building_height(tags):
    """Metres, from whatever the tags offer, in order of how much they know."""
    height = tags.get("height")
    if height:
        try:
            return float(str(height).split()[0])
        except ValueError:
            pass
    levels = tags.get("building:levels")
    if levels:
        try:
            return float(levels) * DEFAULT_STOREY_HEIGHT
        except ValueError:
            pass
    return DEFAULT_BUILDING_HEIGHT


# ── rasterising ────────────────────────────────────────────────────────────

def fill_polygon(target, polygon, value):
    """Paint a filled polygon into an array, in place, taking the max.

    A scanline fill under the even-odd rule. Shapely would do this, and would
    also mean GDAL; the whole algorithm is fifteen lines and it only has to
    handle simple footprints.

    Max rather than assignment so that overlapping parts of a building keep the
    taller height instead of whichever happened to be drawn last.
    """
    if len(polygon) < 3:
        return
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    y0 = max(int(math.floor(min(ys))), 0)
    y1 = min(int(math.ceil(max(ys))), target.shape[0] - 1)

    for y in range(y0, y1 + 1):
        centre = y + 0.5
        crossings = []
        for i in range(len(polygon)):
            ax, ay = polygon[i]
            bx, by = polygon[(i + 1) % len(polygon)]
            if (ay > centre) != (by > centre):          # the edge spans this row
                crossings.append(ax + (centre - ay) / (by - ay) * (bx - ax))
        crossings.sort()
        for i in range(0, len(crossings) - 1, 2):
            xa = max(int(math.ceil(crossings[i] - 0.5)), 0)
            xb = min(int(math.floor(crossings[i + 1] - 0.5)), target.shape[1] - 1)
            if xb >= xa:
                np.maximum(target[y, xa:xb + 1], value, out=target[y, xa:xb + 1])


def rasterise_buildings(buildings, east, north, half, zone, shape):
    """Building heights on the same grid as the ground, in metres."""
    heights = np.zeros(shape, dtype=np.float32)
    x0 = east - half
    y0 = north - half
    used = 0
    for b in buildings:
        pixels = []
        for lat, lon in b["points"]:
            e, n, z = to_utm(lat, lon)
            if z != zone:
                pixels = []
                break
            # Rows run north to south, the way the image comes back.
            pixels.append((e - x0, (shape[0] - 1) - (n - y0)))
        if not pixels:
            continue
        # Skip anything entirely outside, which the bounding-box query returns
        # plenty of.
        px = [p[0] for p in pixels]
        py = [p[1] for p in pixels]
        if max(px) < 0 or min(px) > shape[1] or max(py) < 0 or min(py) > shape[0]:
            continue
        fill_polygon(heights, pixels, b["height"])
        used += 1
    return heights, used


# ── checking ───────────────────────────────────────────────────────────────

def check_projection(lat, lon, verbose=True):
    """Compare our UTM against the elevation service's, which does it properly.

    Asked in UTM and answered in UTM, the extent should come back as the one we
    sent. Any real disagreement shows up as a shift of many metres.
    """
    east, north, zone = to_utm(lat, lon)
    half = 200.0
    bbox = "%f,%f,%f,%f" % (east - half, north - half, east + half, north + half)
    j = get(ELEVATION, {"bbox": bbox, "bboxSR": utm_epsg(zone), "imageSR": utm_epsg(zone),
                        "size": "400,400", "format": "tiff", "pixelType": "F32", "f": "json"})
    e = j["extent"]
    dx = abs(e["xmin"] - (east - half))
    dy = abs(e["ymin"] - (north - half))
    if verbose:
        print("projection check at %.6f, %.6f" % (lat, lon))
        print("  our UTM:      %.2f, %.2f  (zone %d)" % (east, north, zone))
        print("  service says: xmin=%.2f ymin=%.2f" % (e["xmin"], e["ymin"]))
        print("  difference:   %.2f m east, %.2f m north" % (dx, dy))
        print("  %s" % ("agrees within a block" if max(dx, dy) < 1.5
                        else "DISAGREES -- do not trust the output"))
    return max(dx, dy) < 1.5


# ── main ───────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lat", type=float, default=42.4219085,
                   help="centre latitude (default: Roberts Elementary, Medford MA)")
    p.add_argument("--lon", type=float, default=-71.0992821, help="centre longitude")
    p.add_argument("--size", type=int, default=400,
                   help="side of the square to fetch, in metres (default 400)")
    p.add_argument("--name", default="roberts", help="output name, written to data/<name>.npz")
    p.add_argument("--check", action="store_true",
                   help="check our projection against the elevation service and stop")
    args = p.parse_args()

    if args.check:
        sys.exit(0 if check_projection(args.lat, args.lon) else 1)

    east, north, zone = to_utm(args.lat, args.lon)
    half = args.size / 2.0

    print("fetching %dm around %.6f, %.6f" % (args.size, args.lat, args.lon))
    ground = fetch_elevation(east, north, half, zone)
    print("    ground %s, %.1f to %.1f m" % (ground.shape,
                                             np.nanmin(ground), np.nanmax(ground)))

    # A degree of latitude is about 111 km; longitude shrinks with latitude.
    half_deg = (half * 1.4) / 111000.0
    buildings = fetch_buildings(args.lat, args.lon, half_deg)
    print("    %d footprints returned" % len(buildings))

    heights, used = rasterise_buildings(buildings, east, north, half, zone, ground.shape)
    print("    %d within the area, covering %d square metres"
          % (used, int((heights > 0).sum())))

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, args.name + ".npz")

    np.savez_compressed(
        out,
        ground=ground.astype(np.float32),
        buildings=heights.astype(np.float32),
        meta=json.dumps({
            "lat": args.lat, "lon": args.lon, "size": args.size,
            "utm_zone": zone, "east": east, "north": north,
            "metres_per_cell": 1.0,
            "source_ground": "USGS 3DEP (bare earth lidar)",
            "source_buildings": "OpenStreetMap footprints, extruded",
        }),
    )
    print("wrote %s (%.1f KB)" % (out, os.path.getsize(out) / 1024.0))
    print("now run:  python build_town.py --name %s" % args.name)


if __name__ == "__main__":
    main()
