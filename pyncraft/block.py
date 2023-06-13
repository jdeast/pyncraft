'''
This isn't tested (and isn't that useful since the 1.13/FruitJuice update), 
but has been modified with the intent of maintaining backward compatibility 
with mcpi-developed programs, and may be extended as a list of allowed blocks.
NOTE: See data/blocks_1.19.csv for many more available blocks
'''
class Block:
    """Minecraft PI block description. Can be sent to Minecraft.setBlock/s"""
    def __init__(self, id, data=0):
        self.id = id
        self.data = data

    def __cmp__(self, rhs):
        return hash(self) - hash(rhs)

    def __eq__(self, rhs):
        return self.id == rhs.id and self.data == rhs.data

    def __hash__(self):
        return (self.id << 8) + self.data

    def withData(self, data):
        return Block(self.id, data)

    def __iter__(self):
        """Allows a Block to be sent whenever id [and data] is needed"""
        return iter((self.id, self.data))
        
    def __repr__(self):
        return "Block(%d, %d)"%(self.id, self.data)

AIR                 = Block("AIR")
STONE               = Block("STONE")
GRASS               = Block("GRASS_BLOCK")
DIRT                = Block("DIRT")
COBBLESTONE         = Block("COBBLESTONE")
WOOD_PLANKS         = Block("OAK_PLANKS")
SAPLING             = Block("OAK_SAPLING")
BEDROCK             = Block("BEDROCK")
WATER_FLOWING       = Block("WATER")
WATER               = WATER_FLOWING
WATER_STATIONARY    = Block("WATER")
LAVA_FLOWING        = Block("LAVA")
LAVA                = LAVA_FLOWING
LAVA_STATIONARY     = Block("LAVA")
SAND                = Block("SAND")
GRAVEL              = Block("GRAVEL")
GOLD_ORE            = Block("GOLD_ORE")
IRON_ORE            = Block("IRON_ORE")
COAL_ORE            = Block("COAL_ORE")
WOOD                = Block("OAK_LOG")
LEAVES              = Block("OAK_LEAVES")
GLASS               = Block("GLASS")
LAPIS_LAZULI_ORE    = Block("LAPIS_ORE")
LAPIS_LAZULI_BLOCK  = Block("LAPIS_BLOCK")
SANDSTONE           = Block("SANDSTONE")
BED                 = Block("WHITE_BED") # NOTE: this doesn't really work (2-block piece needs special handling)
COBWEB              = Block("COBWEB")
GRASS_TALL          = Block("TALL_GRASS")
WOOL                = Block("WHITE_WOOL")
FLOWER_YELLOW       = Block("DANDELION")
FLOWER_CYAN         = Block(38)
MUSHROOM_BROWN      = Block("BROWN_MUSHROOM")
MUSHROOM_RED        = Block("RED_MUSHROOM")
GOLD_BLOCK          = Block("GOLD_BLOCK")
IRON_BLOCK          = Block("IRON_BLOCK")
STONE_SLAB_DOUBLE   = Block(43)
STONE_SLAB          = Block("STONE_SLAB")
BRICK_BLOCK         = Block("BRICKS")
TNT                 = Block("TNT")
BOOKSHELF           = Block("BOOKSHELF")
MOSS_STONE          = Block("MOSS_STONE")
OBSIDIAN            = Block("OBSIDIAN")
TORCH               = Block("TORCH")
FIRE                = Block("FIRE")
STAIRS_WOOD         = Block("OAK_STAIRS")
CHEST               = Block("CHEST")
DIAMOND_ORE         = Block("DIAMOND_ORE")
DIAMOND_BLOCK       = Block("DIAMOND_BLOCK")
CRAFTING_TABLE      = Block("CRAFTING_TABLE")
FARMLAND            = Block("FARMLAND")
FURNACE_INACTIVE    = Block("FURNACE_INACTIVE")
FURNACE_ACTIVE      = Block("FURNACE_ACTIVE")
DOOR_WOOD           = Block("OAK_DOOR") # NOTE: this doesn't really work (2-block piece needs special handling)
LADDER              = Block("LADDER")
STAIRS_COBBLESTONE  = Block("COBBLESTONE_STAIRS")
DOOR_IRON           = Block("IRON_DOOR")
REDSTONE_ORE        = Block("REDSTONE_ORE")
SNOW                = Block("SNOW")
ICE                 = Block("ICE")
SNOW_BLOCK          = Block("SNOW_BLOCK")
CACTUS              = Block("CACTUS")
CLAY                = Block("CLAY")
SUGAR_CANE          = Block("SUGAR_CANE")
FENCE               = Block("OAK_FENCE")
GLOWSTONE_BLOCK     = Block("GLOWSTONE")
BEDROCK_INVISIBLE   = Block("BEDROCK")
STONE_BRICK         = Block("STONE_BRICKS")
GLASS_PANE          = Block("GLASS_PANE")
MELON               = Block("MELON")
FENCE_GATE          = Block("OAK_FENCE_GATE")
GLOWING_OBSIDIAN    = Block("GLOWING_OBSIDIAN")
NETHER_REACTOR_CORE = Block(247)
