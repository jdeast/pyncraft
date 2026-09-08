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

import osm_blocks

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

# How tall one storey is, by what kind of building it is. Used only when OSM
# gives building:levels but no explicit height, which is the common case.
#
# A single 3 m default is the usual convention and it makes institutional
# buildings look squat: a four storey brick school came out 12 m, about the
# height of a house and a half, because school floors are nothing like house
# floors. These are floor-to-floor figures, and the type they are chosen from
# is in the data, so every school gets the school number without anything here
# knowing which school it is.
STOREY_HEIGHT = {
    "house": 3.0, "detached": 3.0, "semidetached_house": 3.0,
    "residential": 3.0, "apartments": 3.1, "terrace": 3.0, "bungalow": 3.0,
    "school": 4.2, "college": 4.2, "university": 4.2, "kindergarten": 3.6,
    "civic": 4.2, "public": 4.2, "government": 4.0, "hospital": 4.0,
    "church": 6.0, "chapel": 5.0, "cathedral": 8.0,
    "office": 3.7, "commercial": 3.9, "retail": 4.2, "supermarket": 5.0,
    "industrial": 5.0, "warehouse": 6.0, "hangar": 8.0,
    "garage": 2.6, "garages": 2.6, "shed": 2.4, "hut": 2.4, "carport": 2.6,
}
DEFAULT_STOREY_HEIGHT = 3.0     # when the type says nothing either

# What to assume when a building gives neither a height nor a storey count.
DEFAULT_HEIGHTS = {
    "garage": 2.6, "garages": 2.6, "shed": 2.4, "hut": 2.4, "carport": 2.6,
    "roof": 3.0, "greenhouse": 3.0,
    "house": 6.5, "detached": 6.5, "semidetached_house": 6.5, "bungalow": 4.0,
    "apartments": 12.0, "school": 12.6, "church": 12.0,
    "industrial": 8.0, "warehouse": 9.0, "commercial": 7.0, "retail": 6.0,
}
DEFAULT_BUILDING_HEIGHT = 6.0   # metres, when it says nothing at all

# What the ground is made of, as small integers written into the surface layer.
# 0 means nothing said, which comes out as whatever the body's default soil is.
#
# The order matters: a later kind painted over an earlier one wins, so the list
# runs from the most general to the most specific. Grass first, a footpath last,
# because a path crossing a park should be a path.
SURFACE = {
    "grass": 1,
    "park": 2,
    "schoolyard": 3,
    "sand": 4,
    "dirt": 5,
    "asphalt": 6,
    "concrete": 7,
    "parking": 8,
    "road": 9,
    "path": 10,
    "playground": 11,
    "court": 12,
    "pitch": 13,
    "water": 14,
    # Last, so it paints over the road it crosses.
    "crossing": 15,
}

# How wide to draw a way that is a line rather than an area, in metres. These
# are the values OSM itself suggests when a way carries no explicit width.
ROAD_WIDTH = {
    "motorway": 14.0, "trunk": 12.0, "primary": 10.0, "secondary": 9.0,
    "tertiary": 8.0, "residential": 6.0, "unclassified": 6.0,
    "service": 4.0, "living_street": 5.0,
    "footway": 1.8, "path": 1.5, "cycleway": 2.0, "steps": 1.5,
    "pedestrian": 4.0, "track": 3.0,
}


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


def fetch_elevation(east, north, half, zone, cell=1.0, verbose=True):
    """A square of bare-earth elevation, one metre per pixel, in metres.

    The bounding box is given in UTM and the image is asked for in UTM, so the
    service does the reprojection and every pixel is already a square metre.
    Asking in latitude/longitude instead lets the service pick its own extent
    to match the requested aspect ratio, which silently widens the area.
    """
    size = int(round(half * 2 / cell))
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
        print("  elevation: %d x %d cells of %.2f m around %.1f, %.1f (UTM %d)"
              % (size, size, cell, east, north, zone))
        if cell < 1.0:
            # Worth saying out loud. The service will happily return whatever
            # grid is asked for, and below a metre it is interpolating rather
            # than revealing anything, because 3DEP is natively 1 m here.
            print("             (3DEP is natively 1 m: finer cells sharpen the")
            print("              buildings and surfaces, not the ground itself)")
    tif = get(ELEVATION, params, binary=True)
    ground = np.array(Image.open(io.BytesIO(tif))).astype(np.float32)

    # The service returns very negative values where it has no data.
    ground[ground < -1000] = np.nan
    return ground


def overpass(query, verbose=True):
    """Run an Overpass query and return its elements."""
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read()).get("elements", [])


def fetch_landcover(lat, lon, half_deg, verbose=True):
    """Everything that says what the ground is: parks, pitches, roads, paths.

    Without this a town is buildings standing on undifferentiated grass, and
    the things that actually make a place recognisable -- the playground, the
    basketball court, the road you walk down -- are simply absent. They were
    absent here for exactly one reason: the query only ever asked for
    way["building"].
    """
    box = (lat - half_deg, lon - half_deg, lat + half_deg, lon + half_deg)
    query = """
[out:json][timeout:120];
(
  way["leisure"]%s;
  way["landuse"]%s;
  way["amenity"]%s;
  way["natural"="water"]%s;
  way["waterway"]%s;
  way["highway"]%s;
  way["footway"]%s;
  node["natural"="tree"]%s;
  node["playground"]%s;
  node["amenity"~"bench|waste_basket|drinking_water|bicycle_parking"]%s;
  node["highway"~"street_lamp|bus_stop"]%s;
  node["emergency"="fire_hydrant"]%s;
);
out geom tags;
""" % (("(%f,%f,%f,%f)" % box,) * 12)

    if verbose:
        print("  land cover: querying OpenStreetMap")
    features = []
    trees = []
    for element in overpass(query):
        if element.get("type") == "node":
            # The small things: a tree, a swing, a bench, a lamp post. None of
            # them are mapped around Roberts, which is the point -- the moment
            # somebody adds one it turns up in their build, and that is a much
            # better reason to edit a map than being told to.
            kind = prop_kind(element.get("tags", {}))
            if kind:
                trees.append((element["lat"], element["lon"], kind,
                              element["tags"]))
            continue
        geometry = element.get("geometry")
        if not geometry or len(geometry) < 2:
            continue
        tags = element.get("tags", {})
        kind = surface_kind(tags)
        if kind is None:
            continue
        closed = (len(geometry) > 3
                  and geometry[0]["lat"] == geometry[-1]["lat"]
                  and geometry[0]["lon"] == geometry[-1]["lon"])
        features.append({
            "points": [(p["lat"], p["lon"]) for p in geometry],
            "kind": kind,
            "area": closed and "highway" not in tags,
            "width": way_width(tags),
            "name": tags.get("name", ""),
        })
    if verbose and trees:
        counts = {}
        for _lat, _lon, kind, _t in trees:
            counts[kind] = counts.get(kind, 0) + 1
        print("    %d point features: %s" % (len(trees), ", ".join(
            "%s %d" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))))
    return features, trees


def surface_kind(tags):
    """Which surface a way represents, or None if it says nothing useful.

    Checked most specific first: a basketball court is a court, not merely the
    asphalt it is surfaced with, and not merely the park it sits in.
    """
    leisure = tags.get("leisure")
    if leisure == "playground":
        return "playground"
    if leisure == "pitch":
        sport = (tags.get("sport") or "").lower()
        if any(s in sport for s in ("basketball", "tennis", "pickleball", "volleyball")):
            return "court"
        return "pitch"
    if leisure in ("park", "garden", "recreation_ground", "common"):
        return "park"
    if leisure == "swimming_pool":
        return "water"

    if tags.get("amenity") == "school":
        return "schoolyard"
    if tags.get("amenity") == "parking":
        return "parking"

    if tags.get("natural") == "water" or tags.get("waterway"):
        return "water"

    landuse = tags.get("landuse")
    if landuse in ("grass", "meadow", "village_green", "recreation_ground"):
        return "grass"
    if landuse in ("forest", "wood"):
        return "grass"

    highway = tags.get("highway")
    if highway:
        # A marked crossing is painted white on the road, and there are thirty
        # of them within 250 m of the school. Unmarked ones are just tarmac and
        # get drawn as the road they are part of.
        markings = tags.get("crossing:markings")
        if tags.get("footway") == "crossing" or highway == "crossing":
            if markings and markings not in ("no", "surface"):
                return "crossing"
            if tags.get("crossing") in ("zebra", "marked"):
                return "crossing"
            return "road"
        if highway in ("footway", "path", "steps", "cycleway", "pedestrian"):
            return "path"
        # A parking aisle is the lane you drive down inside a car park. It is
        # the same asphalt as the rest of the car park, and drawing it as a
        # road puts a black stripe through the middle of one.
        service = tags.get("service")
        if service == "parking_aisle":
            return "parking"
        if service in ("driveway", "alley"):
            return "asphalt"
        if highway in ROAD_WIDTH:
            return "road"
        return None

    # A bare surface tag, on something that is not otherwise described.
    surface = tags.get("surface")
    if surface in ("asphalt", "paved"):
        return "asphalt"
    if surface in ("concrete", "paving_stones"):
        return "concrete"
    if surface in ("sand",):
        return "sand"
    if surface in ("dirt", "ground", "earth", "gravel", "fine_gravel"):
        return "dirt"
    if surface in ("grass",):
        return "grass"
    return None


def way_width(tags):
    """How wide to draw a linear way, in metres."""
    explicit = tags.get("width") or tags.get("est_width")
    if explicit:
        try:
            return max(float(str(explicit).split()[0]), 1.0)
        except ValueError:
            pass
    lanes = tags.get("lanes")
    highway = tags.get("highway")
    base = ROAD_WIDTH.get(highway, 4.0)
    if lanes:
        try:
            return max(float(lanes) * 3.2, base)
        except ValueError:
            pass
    return base


def fetch_buildings(lat, lon, half_deg, verbose=True):
    """Building footprints from OpenStreetMap, with whatever height they carry."""
    query = """
[out:json][timeout:60];
(way["building"](%f,%f,%f,%f););
out geom tags;
""" % (lat - half_deg, lon - half_deg, lat + half_deg, lon + half_deg)

    if verbose:
        print("  buildings: querying OpenStreetMap")
    buildings = []
    skipped = 0
    for element in overpass(query):
        geometry = element.get("geometry")
        if not geometry or len(geometry) < 3:
            continue
        tags = element.get("tags", {})
        if is_site_not_structure(tags):
            skipped += 1
            continue
        buildings.append({
            "points": [(p["lat"], p["lon"]) for p in geometry],
            "height": building_height(tags),
            "name": tags.get("name", ""),
            # What OSM says it is made of. The school is tagged
            # building:colour=Red, so it comes out brick instead of the same
            # white box as everything else.
            "wall": osm_blocks.wall_block(tags),
            "roof": osm_blocks.roof_block(tags),
            "roof_shape": (tags.get("roof:shape") or "flat").lower(),
            "roof_height": roof_height(tags),
            "addr": tags.get("addr:housenumber", ""),
            "street": short_street(tags.get("addr:street", "")),
        })
    if verbose and skipped:
        print("    ignored %d site outline(s) tagged as buildings" % skipped)
    return buildings


# The grounds of an institution are often drawn as one polygon and then given a
# building tag as well, which is how Roberts Elementary ended up as a single
# 10,393 m2 block six metres tall sitting on top of its own playground. The
# actual school is a separate 2,408 m2 way with building:levels=4.
#
# Telling them apart: the real building says how tall it is, and the site does
# not, because nobody tags the height of a school yard. So an institutional
# polygon with no stated height or storeys is grounds, not a structure. It
# still gets drawn -- as a surface, by fetch_landcover -- just not extruded.
SITE_AMENITIES = {"school", "college", "university", "kindergarten",
                  "hospital", "place_of_worship", "prison"}


def is_site_not_structure(tags):
    if tags.get("amenity") not in SITE_AMENITIES:
        return False
    return not (tags.get("height") or tags.get("building:levels"))


# A Minecraft sign line holds about fifteen characters before it stops
# fitting, and American street names are mostly one long word plus a suffix.
# Shortening the suffix the way a postal address does buys back the room.
STREET_SUFFIXES = {
    "street": "St", "avenue": "Ave", "road": "Rd", "drive": "Dr",
    "boulevard": "Blvd", "court": "Ct", "place": "Pl", "lane": "Ln",
    "terrace": "Ter", "circle": "Cir", "square": "Sq", "parkway": "Pkwy",
    "highway": "Hwy", "trail": "Trl", "way": "Way", "alley": "Aly",
    "crescent": "Cres", "gardens": "Gdns", "close": "Cl", "walk": "Wlk",
    "north": "N", "south": "S", "east": "E", "west": "W",
}


# Point features small enough to be one object rather than an area. The name
# on the left is what this calls it; build_town.py knows how to build each one.
def prop_kind(tags):
    """What small thing a node is, or None if it is not one we build."""
    if tags.get("natural") == "tree":
        return "tree"
    play = tags.get("playground")
    if play in ("swing", "slide", "climbingframe", "sandpit", "seesaw",
                "roundabout", "springy", "structure", "basketswing",
                "climbingwall", "monkeybar"):
        return "play_" + play
    amenity = tags.get("amenity")
    if amenity in ("bench", "waste_basket", "drinking_water", "bicycle_parking"):
        return amenity
    highway = tags.get("highway")
    if highway in ("street_lamp", "bus_stop"):
        return highway
    if tags.get("emergency") == "fire_hydrant":
        return "fire_hydrant"
    return None


def short_street(name):
    """A street name that fits on a sign.

    Only the suffix and any leading compass direction are abbreviated, which is
    how the post office writes them, so the result still reads as itself.
    Anything still too long is cut rather than wrapped, because a name split
    across two lines is harder to read than a shortened one.
    """
    if not name:
        return ""
    words = name.split()
    out = []
    for i, w in enumerate(words):
        key = w.lower().strip(".")
        # Only abbreviate a compass word at the front and a suffix at the back;
        # "West Street" should not become "W St" if West is the actual name.
        if key in STREET_SUFFIXES and (i == len(words) - 1 or
                                       (i == 0 and len(words) > 2)):
            out.append(STREET_SUFFIXES[key])
        else:
            out.append(w)
    short = " ".join(out)
    if len(short) <= 15:
        return short
    # Still too long. Dropping the suffix reads far better than cutting a word
    # in half: "Massachusetts" beats "Massachusetts .".
    if len(out) > 1:
        without_suffix = " ".join(out[:-1])
        if len(without_suffix) <= 15:
            return without_suffix
        short = without_suffix
    return short[:15]


def roof_height(tags):
    """How tall the roof itself is, in metres, above the walls.

    Explicit roof:height wins. Otherwise roof:levels, otherwise a modest pitch
    for the shapes that have one and nothing for the shapes that do not. A flat
    roof is flat and that is the default, because most tagged buildings say
    nothing and most buildings in a town are not steeply pitched.
    """
    explicit = tags.get("roof:height")
    if explicit:
        try:
            return float(str(explicit).split()[0])
        except ValueError:
            pass
    levels = tags.get("roof:levels")
    if levels:
        try:
            return float(levels) * 2.5
        except ValueError:
            pass
    shape = (tags.get("roof:shape") or "").lower()
    if shape in ("gabled", "hipped", "half-hipped", "gambrel", "mansard",
                 "pyramidal", "dome", "round", "onion", "skillion"):
        return 3.0          # a plain domestic pitch
    return 0.0


def building_height(tags):
    """Metres, from whatever the tags offer, in order of how much they know."""
    height = tags.get("height")
    if height:
        try:
            return float(str(height).split()[0])
        except ValueError:
            pass
    kind = (tags.get("building") or "").lower()

    levels = tags.get("building:levels")
    if levels:
        try:
            storey = STOREY_HEIGHT.get(kind, DEFAULT_STOREY_HEIGHT)
            height = float(levels) * storey
            # A pitched roof adds to the height, and OSM counts it separately
            # when it bothers to say so.
            roof_levels = tags.get("roof:levels")
            if roof_levels:
                try:
                    height += float(roof_levels) * storey * 0.7
                except ValueError:
                    pass
            return height
        except ValueError:
            pass
    return DEFAULT_HEIGHTS.get(kind, DEFAULT_BUILDING_HEIGHT)


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


def stroke_line(target, points, width_cells, value):
    """Draw a thick line, for a way that is a road rather than an area.

    A road in OpenStreetMap is a centre line with a width implied by its class,
    so it has to be given a thickness or it comes out one cell wide however
    important it is. Done by stamping a disc along each segment, which is
    simple, slightly slow, and produces properly rounded corners and junctions
    where two roads meet.
    """
    r = max(width_cells / 2.0, 0.5)
    ir = int(math.ceil(r))
    h, w = target.shape
    for i in range(len(points) - 1):
        ax, ay = points[i]
        bx, by = points[i + 1]
        length = math.hypot(bx - ax, by - ay)
        steps = max(int(length) + 1, 1)
        for t in range(steps + 1):
            cx = ax + (bx - ax) * t / steps
            cy = ay + (by - ay) * t / steps
            x0 = max(int(cx - ir), 0)
            x1 = min(int(cx + ir) + 1, w)
            y0 = max(int(cy - ir), 0)
            y1 = min(int(cy + ir) + 1, h)
            if x1 <= x0 or y1 <= y0:
                continue
            ys, xs = np.ogrid[y0:y1, x0:x1]
            inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
            block = target[y0:y1, x0:x1]
            block[inside] = value


def to_cells(points, east, north, half, zone, shape, cell):
    """Latitude/longitude pairs to cell coordinates, or None if off-grid."""
    x0 = east - half
    y0 = north - half
    out = []
    for lat, lon in points:
        e, nn, z = to_utm(lat, lon)
        if z != zone:
            return None
        out.append(((e - x0) / cell, (shape[0] - 1) - (nn - y0) / cell))
    return out


def rasterise_landcover(features, east, north, half, zone, shape, cell):
    """Paint the surface layer: parks, courts, parking, roads, paths.

    Painted in the order SURFACE lists them, general before specific, so a path
    across a park ends up a path and a basketball court inside a schoolyard ends
    up a court.
    """
    surface = np.zeros(shape, dtype=np.uint8)
    by_kind = {}
    for f in features:
        by_kind.setdefault(f["kind"], []).append(f)

    used = 0
    for kind, value in sorted(SURFACE.items(), key=lambda kv: kv[1]):
        for f in by_kind.get(kind, []):
            cells = to_cells(f["points"], east, north, half, zone, shape, cell)
            if not cells:
                continue
            xs = [p[0] for p in cells]
            ys = [p[1] for p in cells]
            if max(xs) < 0 or min(xs) > shape[1] or max(ys) < 0 or min(ys) > shape[0]:
                continue
            if f["area"]:
                fill_polygon(surface, cells, value)
            else:
                stroke_line(surface, cells, f["width"] / cell, value)
            used += 1
    return surface, used


def rasterise_buildings(buildings, east, north, half, zone, shape, cell=1.0,
                       materials=None, ids=None, roofs=None):
    """Building heights on the same grid as the ground, in metres."""
    heights = np.zeros(shape, dtype=np.float32)
    used = 0
    for b in buildings:
        pixels = to_cells(b["points"], east, north, half, zone, shape, cell)
        if not pixels:
            continue
        # Skip anything entirely outside, which the bounding-box query returns
        # plenty of.
        px = [p[0] for p in pixels]
        py = [p[1] for p in pixels]
        if max(px) < 0 or min(px) > shape[1] or max(py) < 0 or min(py) > shape[0]:
            continue
        fill_polygon(heights, pixels, b["height"])
        if ids is not None:
            # One number per footprint, so the builder can give each building a
            # single floor level instead of letting every column sit on its own
            # patch of ground. Without this the terrain prints straight through
            # the roof.
            used_id = used + 1
            if used_id < 65535:
                fill_polygon(ids, pixels, used_id)
                if roofs is not None:
                    roofs[used_id] = {"shape": b.get("roof_shape", "flat"),
                                      "height": b.get("roof_height", 0.0),
                                      "addr": b.get("addr", ""),
                                      "street": b.get("street", "")}
        if materials is not None:
            # Which wall and roof this footprint wants, as an index into a
            # palette built up as we go. Painted like the heights, so where two
            # footprints overlap the later one wins in both layers together.
            key = (b.get("wall", "WHITE_CONCRETE"), b.get("roof", "GRAY_CONCRETE"))
            if key not in materials["palette"]:
                materials["palette"].append(key)
            fill_polygon(materials["index"], pixels,
                         materials["palette"].index(key) + 1)
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
    p.add_argument("--resolution", type=float, default=1.0, metavar="M",
                   help="metres per cell, and therefore per block (default 1.0). "
                        "0.5 or 0.25 sharpen buildings, kerbs and courts; the "
                        "ground itself is 1 m data whatever you ask for.")
    p.add_argument("--no-landcover", action="store_true",
                   help="buildings and bare ground only")
    p.add_argument("--check", action="store_true",
                   help="check our projection against the elevation service and stop")
    args = p.parse_args()

    if args.check:
        sys.exit(0 if check_projection(args.lat, args.lon) else 1)

    east, north, zone = to_utm(args.lat, args.lon)
    half = args.size / 2.0

    cell = args.resolution
    if cell <= 0:
        sys.exit("--resolution must be greater than zero")

    print("fetching %dm around %.6f, %.6f at %.2f m per cell"
          % (args.size, args.lat, args.lon, cell))
    ground = fetch_elevation(east, north, half, zone, cell=cell)
    print("    ground %s, %.1f to %.1f m" % (ground.shape,
                                             np.nanmin(ground), np.nanmax(ground)))

    # A degree of latitude is about 111 km; longitude shrinks with latitude.
    half_deg = (half * 1.4) / 111000.0
    buildings = fetch_buildings(args.lat, args.lon, half_deg)
    print("    %d footprints returned" % len(buildings))

    materials = {"palette": [], "index": np.zeros(ground.shape, dtype=np.uint8)}
    building_ids = np.zeros(ground.shape, dtype=np.uint16)
    roof_info = {}
    heights, used = rasterise_buildings(buildings, east, north, half, zone,
                                        ground.shape, cell, materials,
                                        building_ids, roof_info)
    shapes = {}
    for info in roof_info.values():
        shapes[info["shape"]] = shapes.get(info["shape"], 0) + 1
    if shapes:
        print("    roof shapes: %s" % ", ".join(
            "%s %d" % (k, v) for k, v in sorted(shapes.items(), key=lambda kv: -kv[1])))
    walls = {}
    for w, _r in materials["palette"]:
        walls[w] = walls.get(w, 0) + 1
    if walls:
        print("    walls from OSM tags: %s" % ", ".join(
            "%s x%d" % (k, v) for k, v in sorted(walls.items(), key=lambda kv: -kv[1])))
    print("    %d within the area, covering %d square metres"
          % (used, int((heights > 0).sum() * cell * cell)))

    tree_cells = []
    kinds = []
    if args.no_landcover:
        surface = np.zeros(ground.shape, dtype=np.uint8)
    else:
        features, trees = fetch_landcover(args.lat, args.lon, half_deg)
        print("    %d land cover features returned" % len(features))
        surface, drawn = rasterise_landcover(features, east, north, half, zone,
                                             ground.shape, cell)
        named = {v: k for k, v in SURFACE.items()}
        counts = {named[v]: int((surface == v).sum())
                  for v in np.unique(surface) if v}
        print("    %d drawn: %s" % (drawn, ", ".join(
            "%s %d" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))))

    if not args.no_landcover and trees:
        x0, y0 = east - half, north - half
        kinds = []
        for lat_t, lon_t, kind, ttags in trees:
            e, nn, z = to_utm(lat_t, lon_t)
            if z != zone:
                continue
            cx = (e - x0) / cell
            cy = (ground.shape[0] - 1) - (nn - y0) / cell
            if 0 <= cx < ground.shape[1] and 0 <= cy < ground.shape[0]:
                # Height if it is tagged, otherwise something ordinary.
                try:
                    h = float(str(ttags.get("height", "")).split()[0])
                except (ValueError, IndexError):
                    h = 8.0
                if kind not in kinds:
                    kinds.append(kind)
                tree_cells.append((int(cy), int(cx), h, kinds.index(kind)))

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, args.name + ".npz")

    np.savez_compressed(
        out,
        ground=ground.astype(np.float32),
        buildings=heights.astype(np.float32),
        surface=surface,
        building_materials=materials["index"],
        building_ids=building_ids,
        trees=np.array(tree_cells, dtype=np.float32) if tree_cells
              else np.zeros((0, 4), dtype=np.float32),
        meta=json.dumps({
            "lat": args.lat, "lon": args.lon, "size": args.size,
            "utm_zone": zone, "east": east, "north": north,
            "metres_per_cell": cell,
            "surface_legend": SURFACE,
            "material_palette": materials["palette"],
            "roof_info": {str(k): v for k, v in roof_info.items()},
            "prop_kinds": kinds if not args.no_landcover else [],
            "source_ground": "USGS 3DEP (bare earth lidar, 1 m native)",
            "source_buildings": "OpenStreetMap footprints, extruded",
            "source_surface": "OpenStreetMap leisure/landuse/highway",
        }),
    )
    print("wrote %s (%.1f KB)" % (out, os.path.getsize(out) / 1024.0))
    print("now run:  python build_town.py --name %s" % args.name)


if __name__ == "__main__":
    main()
