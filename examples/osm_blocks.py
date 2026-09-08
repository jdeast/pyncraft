"""Turn what OpenStreetMap says a building is made of into Minecraft blocks.

OSM carries `building:colour`, `building:material`, `roof:colour` and
`roof:material` on a good many buildings, and using them is the difference
between a town of identical white boxes and a town where the red brick school
is recognisably the red brick school.

Colours arrive either as a hex triple or as a name, and neither is guaranteed
to be one Minecraft happens to have. So rather than a lookup table of names,
every candidate block is given its approximate colour and the nearest one wins.
That handles `#8B4513` and `Red` and `darkslategray` alike, and degrades
sensibly for anything unusual instead of failing.

One deliberate interpretation: a building tagged simply "Red" is treated as red
BRICK rather than pillar-box red, because at the scale of a whole building that
is nearly always what the tagger meant. Roofs are not treated that way -- a red
roof is usually tile or painted metal.
"""

# Approximate sRGB of blocks worth building walls and roofs out of. Sampled
# from the textures rather than guessed, and deliberately a short list: too many
# near-identical greys and the nearest-colour match becomes a coin toss.
BLOCK_COLOURS = {
    "WHITE_CONCRETE":        (207, 213, 214),
    "LIGHT_GRAY_CONCRETE":   (125, 125, 115),
    "GRAY_CONCRETE":         (54, 57, 61),
    "BLACK_CONCRETE":        (8, 10, 15),
    "BROWN_CONCRETE":        (96, 59, 31),
    "RED_CONCRETE":          (142, 32, 32),
    "ORANGE_CONCRETE":       (224, 97, 0),
    "YELLOW_CONCRETE":       (240, 175, 21),
    "LIME_CONCRETE":         (94, 168, 24),
    "GREEN_CONCRETE":        (73, 91, 36),
    "CYAN_CONCRETE":         (21, 119, 136),
    "LIGHT_BLUE_CONCRETE":   (36, 137, 199),
    "BLUE_CONCRETE":         (44, 46, 143),
    "PURPLE_CONCRETE":       (100, 31, 156),
    "MAGENTA_CONCRETE":      (169, 48, 159),
    "PINK_CONCRETE":         (213, 101, 142),
    "BRICKS":                (150, 97, 83),
    "TERRACOTTA":            (152, 94, 67),
    "WHITE_TERRACOTTA":      (209, 178, 161),
    "BROWN_TERRACOTTA":      (77, 51, 35),
    "SANDSTONE":             (216, 203, 155),
    "STONE_BRICKS":          (122, 122, 122),
    "SMOOTH_STONE":          (158, 158, 158),
    "OAK_PLANKS":            (162, 130, 78),
    "SPRUCE_PLANKS":         (114, 84, 48),
    "QUARTZ_BLOCK":          (236, 233, 226),
    "DEEPSLATE_TILES":       (54, 54, 58),
}

# What a material is, when the tagger said so. Material beats colour for
# texture: "brick, painted white" should still look like brick.
MATERIAL_BLOCKS = {
    "brick": "BRICKS",
    "brick_block": "BRICKS",
    "concrete": "LIGHT_GRAY_CONCRETE",
    "cement_block": "LIGHT_GRAY_CONCRETE",
    "stone": "STONE_BRICKS",
    "sandstone": "SANDSTONE",
    "limestone": "SANDSTONE",
    "granite": "STONE_BRICKS",
    "wood": "OAK_PLANKS",
    "timber_framing": "OAK_PLANKS",
    "glass": "GLASS",
    "metal": "IRON_BLOCK",
    "steel": "IRON_BLOCK",
    "plaster": "WHITE_CONCRETE",
    "stucco": "WHITE_TERRACOTTA",
    "vinyl_siding": "WHITE_CONCRETE",
    "shingle": "SPRUCE_PLANKS",
    "tile": "BRICKS",
    "roof_tiles": "BRICKS",
    "slate": "DEEPSLATE_TILES",
    "asphalt": "BLACK_CONCRETE",
    "tar_paper": "BLACK_CONCRETE",
}

# Enough CSS names to cover what turns up in practice.
NAMED_COLOURS = {
    "white": (255, 255, 255), "black": (0, 0, 0), "grey": (128, 128, 128),
    "gray": (128, 128, 128), "lightgrey": (211, 211, 211),
    "lightgray": (211, 211, 211), "darkgrey": (105, 105, 105),
    "darkgray": (105, 105, 105), "silver": (192, 192, 192),
    "red": (150, 97, 83),          # see the note above: a red building is brick
    "darkred": (110, 50, 40), "maroon": (128, 0, 0),
    "brown": (139, 69, 19), "tan": (210, 180, 140), "beige": (245, 245, 220),
    "cream": (255, 253, 208), "orange": (255, 165, 0),
    "yellow": (255, 255, 0), "gold": (255, 215, 0),
    "green": (0, 128, 0), "darkgreen": (0, 100, 0), "olive": (128, 128, 0),
    "blue": (0, 0, 255), "lightblue": (173, 216, 230), "navy": (0, 0, 128),
    "purple": (128, 0, 128), "violet": (238, 130, 238),
    "pink": (255, 192, 203), "cyan": (0, 255, 255), "teal": (0, 128, 128),
    "sandstone": (216, 203, 155), "terracotta": (152, 94, 67),
}


def parse_colour(value):
    """A colour tag to (r, g, b), or None if it is not one we understand."""
    if not value:
        return None
    v = str(value).strip().lower().replace(" ", "").replace("_", "")
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            try:
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None
        return None
    return NAMED_COLOURS.get(v)


def nearest_block(rgb, palette=None):
    """The block whose colour is closest, by plain squared distance in sRGB.

    Perceptual colour spaces would be more correct and are not worth the
    dependency here: the palette is small and well separated, and the answer is
    the same for anything that is not a borderline grey.
    """
    palette = palette or BLOCK_COLOURS
    r, g, b = rgb
    best, best_d = None, None
    for name, (br, bg, bb) in palette.items():
        d = (r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2
        if best_d is None or d < best_d:
            best, best_d = name, d
    return best


def wall_block(tags, default="WHITE_CONCRETE"):
    """What a building's walls should be made of, from its tags."""
    material = (tags.get("building:material") or tags.get("material") or "").lower()
    if material in MATERIAL_BLOCKS:
        return MATERIAL_BLOCKS[material]

    rgb = parse_colour(tags.get("building:colour") or tags.get("building:color"))
    if rgb:
        return nearest_block(rgb)

    # Some building types have an obvious answer even with nothing else said.
    kind = (tags.get("building") or "").lower()
    if kind in ("garage", "garages", "shed", "hut", "carport"):
        return "SPRUCE_PLANKS"
    if kind == "greenhouse":
        return "GLASS"
    return default


def roof_block(tags, default="GRAY_CONCRETE"):
    """What a building's roof should be made of."""
    material = (tags.get("roof:material") or "").lower()
    if material in MATERIAL_BLOCKS:
        return MATERIAL_BLOCKS[material]

    rgb = parse_colour(tags.get("roof:colour") or tags.get("roof:color"))
    if rgb:
        # Unlike walls, a red roof is tile or painted metal rather than brick,
        # so the brick reading of "red" is not wanted here.
        palette = dict(BLOCK_COLOURS)
        palette.pop("BRICKS", None)
        return nearest_block(rgb, palette)
    return default
