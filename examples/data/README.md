# The landscape windows, and how to get them back

`fetch_planet.py` writes an `.npz` here and `build_town.py` reads it. The small
ones are in the repository; the metre-scale ones are not, because they are
large, there is no end to how many of them there could be, and git keeps every
version of everything for ever.

So this file is the record. Every window below is one command, and the command
is the whole definition of it — same command, same bytes, because the source
data is a fixed published product and the reader is deterministic.

## Committed

These are small and stay in the repository, so the examples run with no network
at all.

| file | what | source |
|---|---|---|
| `roberts.npz` | Roberts Elementary, Medford MA | USGS lidar + OpenStreetMap |
| `mars_gale.npz` | Gale Crater | MOLA, 463 m |
| `mars_olympus.npz` | Olympus Mons | MOLA, 463 m |
| `mars_hellas.npz` | Hellas Planitia | MOLA, 463 m |
| `moon_tranquillity.npz` | Tranquility Base | LOLA, 118 m |
| `moon_apollo15.npz` | Hadley Rille | LOLA, 118 m |
| `moon_malapert_massif.npz` | Malapert Massif | LOLA, 118 m |

## Fetched on demand

Each is a few seconds and a few megabytes of HTTP range requests. Run these
from the `examples` directory.

### Apollo 15, Hadley Rille — LROC NAC stereo, 2 m per pixel

```sh
# the landing site itself: flat, because Apollo 15 landed on a mare plain
python fetch_planet.py --dem apollo15 --size 300 --name moon_apollo15_hires

# the rille: 323 m deep, and no gaps at this particular window
python fetch_planet.py --dem apollo15 --lat 26.132 --lon 3.5467 \
    --size 300 --name moon_hadley_rille_2m

# both at once, coarsened to 4 m so the pair fits in one contiguous map
python fetch_planet.py --dem apollo15 --lat 26.132 --lon 3.5878 \
    --size 1480 --rows 740 --stride 2 --name moon_hadley_full
```

The starting column matters more than it looks. West of about column 400 the
NAC stereo pair runs out and the coverage becomes ragged, so a window that
reaches for the far rim of the rille buys it with holes:

| starts at | nodata | width at 4 m |
|---|---|---|
| col 420 | 0.02% | 740 blocks |
| col 380 | 1.45% | 760 |
| col 340 | 3.97% | 780 |
| col 300 | 6.37% | 800 |

### Apollo 12, Surveyor Crater — 2 m per pixel

```sh
python fetch_planet.py --dem apollo12 --lat -3.0157 --lon 336.5847 \
    --size 600 --name moon_surveyor_crater
```

208 m across and 21 m rim to floor, measured off the data; the catalogued
diameter is about 200 m. Conrad put Intrepid on the rim, close enough to walk
down to Surveyor 3 on the inner slope. None of the six missions landed *in* a
crater — a crater floor is the last place you want to set down — and this is
the closest any of them came.

### Apollo 14, Cone Crater — 2 m per pixel

```sh
python fetch_planet.py --dem apollo14 --lat -3.634361 --lon 342.544006 \
    --size 1100 --rows 800 --name moon_cone_crater
```

2.20 x 1.60 km holding both Antares and Cone Crater, 1,481 m apart. The crater
is 351 m across against a published figure of about 340.

Its depth depends entirely on which rim you stand on, which is worth knowing
before quoting a number: Cone sits on the flank of a ridge, so it is 44 m from
the west rim down to the floor, while the ground east of it simply keeps
climbing and never really has a rim. Measuring from over there gives 88 m,
which is the ridge and not the crater.

### Malapert Massif — LOLA 5 m south pole site grid

```sh
python fetch_planet.py --dem malapert --size 300 --name moon_malapert_massif_hires
```

## Making your own

`--dem` lists what is available; `fetch_planet.py --list` shows the sites and
the nine further LOLA 5 m grids that are not wired up yet. `--check` prints
what a DEM covers without reading any pixels, which is the cheap way to find
out whether the thing you want is in it.

Two switches decide what a window costs:

- `--size` and `--rows` are in PIXELS OF THE SOURCE, not blocks.
- `--stride` averages n x n of those into one block. A 2 m DEM at `--stride 3`
  is 6 m to the block, which is how a window covers ground it could not afford
  at full resolution.

Then `build_town.py --name <name> --crust 1 --dry-run` will tell you how many
blocks it would place before you place any of them.
