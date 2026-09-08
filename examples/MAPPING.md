# Making your neighbourhood right

`fetch_terrain.py` builds your town out of two public datasets: the ground from
USGS lidar, and everything on it from [OpenStreetMap](https://www.openstreetmap.org).

The ground is as good as it gets — 1 metre, from an aeroplane, and you cannot
improve on it. **Everything else is a map that people made, and you can make it
better.** If your school's roof is the wrong shape, or the trees on your street
are missing, or the playground isn't there, that is not a bug in this program.
It is a thing nobody has got round to mapping yet.

Fix it in OpenStreetMap and it appears in your build. It also appears for
everyone else who ever uses that map, which is the good part.

## What this example reads

Everything below is a real OSM tag. If it is there, this uses it; if it is not,
it falls back to something sensible.

### Buildings

| Tag | What it does | If missing |
|---|---|---|
| `building=*` | Makes it a building at all | not built |
| `height=12` | Exact height in metres. **Best thing you can add.** | falls back to levels |
| `building:levels=4` | How many floors | a guess from the building type |
| `building:colour=Red` | Wall colour. A name or `#8B4513` | white |
| `building:material=brick` | Wall material — brick, wood, concrete, glass, stone | from the colour, else white |
| `roof:shape=gabled` | The silhouette. See below | flat |
| `roof:height=3` | How tall the roof is above the walls | 3 m if it has a shape |
| `roof:levels=1` | Another way of saying it | — |
| `roof:colour=grey` | Roof colour | grey |
| `roof:material=slate` | Roof material | grey concrete |

`roof:shape` understands `flat`, `gabled`, `hipped`, `pyramidal`, `skillion`,
`dome`, `gambrel`, `mansard`, `half-hipped`, `onion` and `round`. At one block
to the metre some of those look alike, so similar ones borrow the nearest
shape.

**A four storey school is not four times a house floor.** If a building has
`building:levels` but no `height`, this assumes a storey height based on what
kind of building it is — 4.2 m for a school, 3 m for a house, 2.6 m for a
garage. Adding a real `height` beats every guess.

### The ground around them

| Tag | What it becomes |
|---|---|
| `leisure=playground` | wood-chip brown |
| `leisure=pitch` + `sport=basketball` | a green hard court |
| `leisure=pitch` + `sport=baseball` | grass, a shade off the ordinary kind |
| `leisure=park`, `landuse=grass` | grass |
| `amenity=school` | school grounds |
| `amenity=parking`, `service=parking_aisle` | car park |
| `highway=residential`, `tertiary`, `service` | road |
| `highway=footway`, `path` | pavement |
| `footway=crossing` + `crossing:markings=zebra` | painted white crossing |
| `natural=water`, `waterway=*` | water |
| `natural=tree` | a tree, with `height` if it has one |
| `playground=swing` / `slide` / `climbingframe` / `sandpit` / `seesaw` / `roundabout` / `springy` / `monkeybar` / `climbingwall` / `structure` | that piece of playground equipment |
| `amenity=bench` / `waste_basket` / `drinking_water` / `bicycle_parking` | street furniture |
| `highway=street_lamp` / `bus_stop` | a lamp post, a bus stop |
| `emergency=fire_hydrant` | a hydrant |
| `surface=asphalt` / `concrete` / `sand` / `dirt` | that surface |
| `width=6`, `lanes=2` | how wide a road is drawn |

## How to change it

1. Make an account at [openstreetmap.org](https://www.openstreetmap.org).
2. Find your street and click **Edit**. The built-in editor is called iD and
   runs in the browser; nothing to install.
3. Click a building, then **Add field** to add tags from the tables above.
4. Save, with a note saying what you changed.
5. Wait a few minutes, then run `fetch_terrain.py` again. Your change will be
   in it.

### Rules worth knowing before you start

These are OpenStreetMap's, not ours, and they matter:

- **Map only what is really there.** Go and look, or use your own memory of the
  place. It is a map of the world, not of what would be fun.
- **Never copy from Google Maps, Google Earth, or Apple Maps.** Not the
  imagery, not the outlines, not the names. It is against their terms and
  copied data has to be deleted, along with anything built on top of it. The
  aerial imagery inside the OSM editor is licensed for this and is fine.
- **Do not map private information about people.** No names of who lives where.
  House numbers are fine — they are on the front of the house.
- **Do not map the inside of buildings you do not own or run.** Interior floor
  plans of a school are exempt from public records law in most states precisely
  because of what they could be used for. The outside is public; the inside is
  not yours to publish.
- **Small and correct beats large and guessed.** Adding `roof:shape` to your own
  house, having looked at it, is worth more than a hundred guesses.

### Good first things to add

Roughly easiest first, and each one visibly changes your build:

1. `addr:housenumber` on your house, if it is missing.
2. `building:levels` — count the rows of windows.
3. `roof:shape` — is it flat, or does it come to a ridge (`gabled`), or slope
   in from all four sides (`hipped`)?
4. `building:colour` — what colour is it, really?
5. `natural=tree` for the trees on your street. One click each.
6. `leisure=playground` if your school's is not drawn.
7. `crossing:markings=zebra` on the crossing you use to get to school.
8. The **playground equipment**. `leisure=playground` draws the area; the
   swings, slide and climbing frame are separate points inside it, tagged
   `playground=swing`, `playground=slide` and so on. Around Roberts there are
   two playground outlines and nothing at all inside them, so this is the
   single biggest difference anyone could make there.

Each of these takes about a minute and changes something you can walk up to.

## What you cannot fix this way

Some things are not in any public dataset and are not worth adding to one:

- **The exact height of the ground.** 1 metre is the best there is.
- **What is inside a playground, unless somebody maps it.** The two playgrounds
  at Roberts are outlines with nothing in them. That is not a limit of the
  data — it is a limit of what has been mapped, and it is the easiest kind of
  thing to fix.
- **Anything inside a building.** See above.
- **Paint on the playground** — a mural, a hopscotch grid, a rainbow by the
  door. There is no tag that would put those in a build. You can add the
  artwork itself as `tourism=artwork` + `artwork_type=mural`, which records
  that it exists, and then build it by hand in Minecraft — which is the more
  fun half anyway.
