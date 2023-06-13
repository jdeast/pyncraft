#Martin O'Hanlon, Jason Eastman
#www.stuffaboutcode.com
#FruitJuice Tests

import pyncraft.minecraft as minecraft
import pyncraft.block as block
import pyncraft.entity as entity
import time, math, csv, os
import numpy as np
import ipdb

wait_between_tests = 5.0


def runBlockTests(mc):
    """runBlockTests - tests creation of all blocks for all data values known to FruitJuice
    
    A sign is placed next to the created block so user can view in Minecraft whether block created correctly or not
    Known issues:
    - some LEAVES missing but because they decay by the time user sees them
    
    Author: Tim Cummings https://www.triptera.com.au/wordpress/
    Author: Jason Eastman https://github.com/jdeast
    """

    # read the csv file of block ids in
    # NOTE: many properties in this CSV file are not populated
    # NOTE 2: other properties can be added to the CSV file

    # there has to be a more pythonic way to do this...
    csvfile = os.path.join("data","blocks_1.19.csv")
    blocks = {}
    with open(csvfile, 'r') as data:
        reader = csv.reader(data)
        header = next(reader)
        for head in header: 
            if 'is_' in head: headtype = bool
            elif head == 'stack_size' or head == 'numerical_id': headtype = int
            else: headtype = str
            blocks[head] = np.empty(0,dtype=headtype)
        for row in reader:
            for i in range(len(row)):
                if header[i] == 'id': row[i] = row[i].upper()
                elif 'is_' in header[i]: row[i] = (row[i] == "TRUE")
                elif header[i] == "stack_size" or header[i] == "numerical_id": row[i] = int(row[i])
                blocks[header[i]] = np.append(blocks[header[i]],row[i])

    solids=["STONE","GRASS","DIRT","COBBLESTONE","BEDROCK","SAND","GRAVEL","GOLD_ORE","IRON_ORE","COAL_ORE","GLASS","LAPIS_LAZULI_ORE",
            "LAPIS_LAZULI_BLOCK","COBWEB","GOLD_BLOCK","IRON_BLOCK","BRICK_BLOCK","TNT","BOOKSHELF","MOSS_STONE","OBSIDIAN",
            "DIAMOND_ORE","DIAMOND_BLOCK","CRAFTING_TABLE","FARMLAND","REDSTONE_ORE","CLAY","PUMPKIN","MELON","NETHERRACK","SOUL_SAND",
            "GLOWSTONE_BLOCK","GLASS_PANE","LIT_PUMPKIN","END_STONE","EMERALD_ORE","GLOWING_OBSIDIAN","ICE",
            "SNOW_BLOCK","MYCELIUM","NETHER_BRICK","NETHER_REACTOR_CORE"]
    fences=["FENCE","FENCE_NETHER_BRICK","FENCE_SPRUCE","FENCE_BIRCH","FENCE_JUNGLE","FENCE_DARK_OAK","FENCE_ACACIA"]
    woods=["WOOD_PLANKS"]
    trees=["WOOD","LEAVES"]
    trees2=["LEAVES2"] #options are acacia and dark oak
    plants=["DEAD_BUSH","FLOWER_CYAN","FLOWER_YELLOW","SUGAR_CANE"]
    liquids=["WATER","LAVA"]
    beds=["BED"]
    coloureds=["WOOL","STAINED_GLASS"]
    flats=["RAIL","RAIL_POWERED","RAIL_DETECTOR","RAIL_ACTIVATOR","TRAPDOOR","TRAPDOOR_IRON"]
    slabs=["STONE_SLAB","STONE_SLAB_DOUBLE","WOODEN_SLAB"]
    torches=["TORCH","TORCH_REDSTONE"]
    gases=["AIR","FIRE"]
    stairs=["STAIRS_WOOD","STAIRS_COBBLESTONE","STAIRS_BRICK","STAIRS_STONE_BRICK","STAIRS_NETHER_BRICK","STAIRS_SANDSTONE"]
    signs=["SIGN_WALL"]
    doors=["DOOR_WOOD","DOOR_IRON","DOOR_SPRUCE","DOOR_BIRCH","DOOR_JUNGLE","DOOR_ACACIA","DOOR_DARK_OAK"]
    gates=["FENCE_GATE"]
    wallmounts=["SIGN_WALL","LADDER","CHEST","FURNACE_INACTIVE","FURNACE_ACTIVE"]
    saplings=["SAPLING"]
    tallgrasses=["GRASS_TALL"]
    stonebricks=["STONE_BRICK"]
    snowblocks=["SNOW"]
    sandstones=["SANDSTONE"]
    cacti=["CACTUS"]
    mushrooms=["MUSHROOM_BROWN","MUSHROOM_RED"]
    
    # location for platform showing all block types
    xtest = 100
    ytest = 20
    ztest = 0
    mc.postToChat("runBlockTests(): Creating test blocks at x=" + str(xtest) + " y=" + str(ytest) + " z=" + str(ztest))

    x=xtest
    y=ytest-1
    z=ztest
    mc.setBlocks(x,y,z,x+110,y,z+110,"STONE")

    #clearing area above the test area
    #clear the area in segments, otherwise it breaks the server
    for y_inc in range(1, 10):
        mc.setBlocks(x,y+y_inc,z,x+110,y+y_inc,z+110,"AIR")
        time.sleep(2)

    # move the player to the test position
    mc.player.setTilePos(xtest, ytest, ztest)
    time.sleep(1)

    # place all blocks
    nblocks = 1
    x=xtest+10
    y=ytest
    z=ztest+10
    for i in range(len(blocks['id'])):
        if blocks['is_liquid'][i]: continue # skip liquid blocks
        #if not blocks['is_block'][i]: continue # skip dropped items
        if blocks['is_broken'][i]: continue # skip broken blocks

        # plants cannot be placed on stone
        if blocks['is_plant'][i]:
            mc.setBlock(x,y-1,z,"GRASS_BLOCK")

        z += 1    
        mc.setBlock(x-1,y,z,"STONE")
        mc.setSign(x-1,y+1,z, "BIRCH_SIGN", 8, "id=" + blocks['id'][i])
        mc.setBlock(x,y,z,blocks['id'][i])
        time.sleep(0.15)


        placed_blockid = mc.getBlock(x,y,z)
        if placed_blockid != blocks['id'][i]: 
            print(blocks['id'][i] + " is broken")
        time.sleep(0.01)

        nblocks += 1
        # start a new row
        if (nblocks % 100) == 0: 
            x+= 4
            z = ztest+10

    mc.postToChat("runBlockTests() complete")

def runEntityTests(mc):
    """runEntityTests - tests creation of all entities known to FruitJuice
    
    A sign is placed next to the created entity so user can view in Minecraft whether block created correctly or not
    Known issues:
    - Some entities untested yet ["LEASH_HITCH","SNOWBALL","FIREBALL","SMALL_FIREBALL","ENDER_SIGNAL","PRIMED_TNT","DRAGON_FIREBALL","WITHER_SKULL","HUSK"]
    - Some entities don't spawn on one test but will spawn on a subsequent test
    
    Author: Tim Cummings https://www.triptera.com.au/wordpress/
    """
    all=["EXPERIENCE_ORB","AREA_EFFECT_CLOUD","ELDER_GUARDIAN","WITHER_SKELETON","STRAY","EGG","LEASH_HITCH","PAINTING","ARROW","SNOWBALL","FIREBALL","SMALL_FIREBALL","ENDER_PEARL","ENDER_SIGNAL","THROWN_EXP_BOTTLE","ITEM_FRAME","WITHER_SKULL","PRIMED_TNT","HUSK","SPECTRAL_ARROW","SHULKER_BULLET","DRAGON_FIREBALL","ZOMBIE_VILLAGER","SKELETON_HORSE","ZOMBIE_HORSE","ARMOR_STAND","DONKEY","MULE","EVOKER_FANGS","EVOKER","VEX","VINDICATOR","ILLUSIONER","MINECART_COMMAND","BOAT","MINECART","MINECART_CHEST","MINECART_FURNACE","MINECART_TNT","MINECART_HOPPER","MINECART_MOB_SPAWNER","CREEPER","SKELETON","SPIDER","GIANT","ZOMBIE","SLIME","GHAST","PIG_ZOMBIE","ENDERMAN","CAVE_SPIDER","SILVERFISH","BLAZE","MAGMA_CUBE","ENDER_DRAGON","WITHER","BAT","WITCH","ENDERMITE","GUARDIAN","SHULKER","PIG","SHEEP","COW","CHICKEN","SQUID","WOLF","MUSHROOM_COW","SNOWMAN","OCELOT","IRON_GOLEM","HORSE","RABBIT","POLAR_BEAR","LLAMA","LLAMA_SPIT","PARROT","VILLAGER","ENDER_CRYSTAL"]
    livers=["VILLAGER","WITHER_SKELETON","EGG","ZOMBIE_VILLAGER","SKELETON_HORSE","ZOMBIE_HORSE","DONKEY","MULE",
        "WITCH","SHULKER","PIG","SHEEP","COW","WOLF","MUSHROOM_COW","CREEPER",
        "OCELOT","IRON_GOLEM","HORSE","RABBIT","POLAR_BEAR","LLAMA","EVOKER","VINDICATOR","ENDERMITE"]
    items=["EXPERIENCE_ORB","AREA_EFFECT_CLOUD","ARROW","ENDER_PEARL","THROWN_EXP_BOTTLE","SPECTRAL_ARROW","SHULKER_BULLET","ARMOR_STAND","EVOKER_FANGS","VEX","BLAZE",
        "LLAMA_SPIT","ENDER_CRYSTAL"]
    minecarts=["MINECART_COMMAND","MINECART","MINECART_CHEST","MINECART_FURNACE","MINECART_TNT","MINECART_HOPPER","MINECART_MOB_SPAWNER"]
    floats=["BOAT"]
    sinks=["SQUID",]
    hangers=["PAINTING","ITEM_FRAME",]
    todo=["LEASH_HITCH","SNOWBALL","FIREBALL","SMALL_FIREBALL","ENDER_SIGNAL","PRIMED_TNT","DRAGON_FIREBALL","WITHER_SKULL","HUSK"]
    giants=["ELDER_GUARDIAN","GUARDIAN","GIANT","ENDER_DRAGON","GHAST"]
    cavers=["MAGMA_CUBE","BAT","PARROT","CHICKEN","STRAY","SKELETON","SPIDER","ZOMBIE","SLIME","CAVE_SPIDER","PIG_ZOMBIE","ENDERMAN","SNOWMAN","SILVERFISH","ILLUSIONER"]
    bosses=["WITHER"]
    # location for platform showing all block types
    xtest = 50
    ytest = 50
    ztest = 50
    wall="GLASS"
    roof="STONE"
    floor="STONE"
    fence="BIRCH_FENCE"
    signmount="STONE"

    torch="TORCH"
    rail="RAIL"
    wallsignid="BIRCH_SIGN"
    sign="BIRCH_SIGN"


    mc.postToChat("runEntityTests(): Creating test entities at x=" + str(xtest) + " y=" + str(ytest) + " z=" + str(ztest))
    #mc.setBlocks(xtest,ytest-1,ztest,xtest+100,ytest+50,ztest+100,"AIR")
    
    #clear the area in segments, otherwise it breaks the server
    #clearing area
    for y_inc in range(0, 10):
        mc.setBlocks(xtest,ytest+y_inc,ztest,xtest+100,ytest+y_inc,ztest+100,"AIR")
        time.sleep(2)

    mc.setBlocks(xtest-10,ytest-1,ztest-11,xtest+110,ytest-1,ztest+110,"STONE")
    mc.player.setTilePos(xtest, ytest, ztest)

    dance = False
    if dance:
        mc.postToChat("Dancing villager")
        r = 10
        x=xtest
        y=ytest
        z=ztest + r
        id=mc.spawnEntity(x,y,z,entity.VILLAGER)
        theta = 0
        while theta <= 2 * math.pi:
            time.sleep(0.1)
            theta += 0.1
            x = xtest + math.sin(theta) * r
            z = ztest + math.cos(theta) * r
            mc.entity.setPos(id,x,y,z)
    

    # create set of all block ids to ensure they all get tested
    # note some blocks have different names but same ids so they only have to be tested once per id
    # create a map of ids to names so can see which ones haven't been tested by name
    untested=set()
    entitymap={}
    for varname in dir(entity):
        var=getattr(entity,varname)
        try:
            # check var has data and id and add id to untested set
            if varname[0] != '_': 
                untested.add(var.id)
                try:
                    names=entitymap[var.id]
                    names.append(varname)
                except KeyError:
                    entitymap[var.id]=[varname]
        except AttributeError:
            #only interested in objects with an id which behave like entities
            pass
    
    
    time.sleep(1)    
    x=xtest
    y=ytest
    z=ztest
    for key in items:
        z += 2
        if z > 98:
            z = ztest
            x += 10
        e = getattr(entity,key)
        mc.setBlock(x+2,y,z,signmount)
        mc.setSign(x+2,y+1,z,sign,4,key,"id=" + str(e.id))
        mc.spawnEntity(x,y,z,e)
        untested.discard(e.id)
        time.sleep(0.25)

    for key in hangers:
        z += 3
        if z > 97:
            z = ztest
            x += 10
        e = getattr(entity,key)
        mc.setBlocks(x+2,y,z-1,x+2,y+2,z+1,signmount)
        mc.setSign(x+1,y,z,wallsignid,4,key,"id=" + str(e.id))
        mc.spawnEntity(x+1,y+2,z,e)
        untested.discard(e.id)
        time.sleep(0.25)

    z = ztest - 4
    x += 10
    time.sleep(1)

    for key in livers:
        z += 4
        if z > 96:
            z = ztest
            x += 10
        e = getattr(entity,key)
        mc.setBlocks(x-2,y,z-2,x+2,y,z+2,fence)
        mc.setBlocks(x-1,y,z-1,x+1,y,z+1,"AIR")
        mc.setBlock(x-3,y,z-1,torch)
        mc.setSign(x-3,y,z,wallsignid,4,key,"id=" + str(e.id))
        mc.spawnEntity(x,y,z,e)
        untested.discard(e.id)
        time.sleep(0.25)


    x+=10
    z=ztest - 3
    time.sleep(1)
    for key in minecarts:
        z += 3
        if z > 97:
            z = ztest
            x += 10
        e = getattr(entity,key)
        mc.setBlock(x+2,y,z,signmount)
        mc.setSign(x+2,y+1,z,sign,4,key,"id=" + str(e.id))
        mc.setBlock(x+2,y,z-1,torch)
        mc.setBlocks(x,y,z-1,x,y,z+1,rail)
        mc.spawnEntity(x,y,z,e)
        untested.discard(e.id)
        time.sleep(0.25)

    for key in floats:
        z += 5
        if z > 95:
            z = ztest
            x += 10
        e = getattr(entity,key)
        mc.setBlock(x+2,y,z,signmount)
        mc.setSign(x+2,y+1,z,sign,4,key,"id=" + str(e.id))
        mc.setBlock(x+2,y,z-1,torch)
        mc.setBlocks(x-2,y-2,z-3,x+2,y-1,z+2,floor)
        mc.setBlocks(x-1,y-1,z-2,x+1,y-1,z+1,"WATER")
        mc.spawnEntity(x,y,z,e)
        untested.discard(e.id)
        time.sleep(0.25)
            
    x+=10
    z=ztest - 4
    time.sleep(1)
    for key in cavers:
        z += 4
        if z > 96:
            z = ztest
            x += 10
        e = getattr(entity,key)
        mc.setBlocks(x,y,z,x+4,y+3,z+4,wall)
        mc.setBlocks(x,y+4,z,x+4,y+4,z+4,roof)
        mc.setBlocks(x-2,y-1,z,x+6,y-1,z+4,floor)
        mc.setBlocks(x+1,y,z+1,x+3,y+3,z+3,"AIR")
        mc.setBlock(x-1,y,z+1,torch)
        mc.setSign(x-1,y,z+2,sign,4,key,"id=" + str(e.id))
        mc.spawnEntity(x+2,y,z+2,e)
        untested.discard(e.id)
        time.sleep(0.25)

    x=xtest
    y=ytest+10
    z=ztest
    time.sleep(1)
    for key in giants:
        e = getattr(entity,key)
        mc.setBlocks(x,y,z,x+20,y+20,z+20,wall)
        mc.setBlocks(x,y+21,z,x+20,y+21,z+20,roof)
        mc.setBlocks(x-5,y-1,z-1,x+20,y-1,z+21,floor)
        mc.setBlocks(x+1,y,z+1,x+19,y+20,z+19,"AIR")
        mc.setSign(x-1,y,z+2,sign,4,key,"id=" + str(e.id))
        mc.spawnEntity(x+10,y+5,z+10,e)
        untested.discard(e.id)
        time.sleep(0.25)

        z += 20
        if z > 80:
            z = ztest
            x += 25

    for key in bosses:
        e = getattr(entity,key)
        mc.setBlocks(x,y,z,x+20,y+20,z+20,"BEDROCK")
        mc.setBlocks(x,y+21,z,x+20,y+21,z+20,"BEDROCK")
        mc.setBlocks(x-5,y-1,z-1,x+20,y-1,z+21,"BEDROCK")
        mc.setBlocks(x+1,y,z+1,x+19,y+20,z+19,"AIR")
        mc.setBlocks(x+1,y,z+8,x+19,y,z+12,torch)
        mc.setBlocks(x+1,y+10,z+2,x+1,y+15,z+18,torch)
        mc.setBlocks(x+19,y+10,z+2,x+19,y+15,z+18,torch)
        mc.setBlocks(x+1,y+10,z+19,x+19,y+15,z+19,torch)
        mc.setBlocks(x+1,y+10,z+1,x+19,y+15,z+1,torch)
        mc.setBlocks(x,y,z+9,x+3,y+3,z+11,"BEDROCK")
        mc.setBlocks(x+4,y,z+9,x+19,y+3,z+11,wall)
        mc.setBlocks(x,y,z+10,x+19,y+2,z+10,"AIR")
        mc.setSign(x-1,y,z+2,sign,4,key,"id=" + str(e.id))
        mc.spawnEntity(x+10,y+5,z+10,e)
        untested.discard(e.id)
        time.sleep(0.25)
        z += 20
        if z > 80:
            z = ztest
            x += 25

    for key in sinks:
        e = getattr(entity,key)
        mc.setBlocks(x,y,z,x+20,y+20,z+20,wall)
        mc.setBlocks(x,y+21,z,x+20,y+21,z+20,roof)
        mc.setBlocks(x-5,y-1,z-1,x+20,y-1,z+21,floor)
        mc.setBlocks(x+1,y,z+1,x+19,y+20,z+19,"WATER")
        mc.setSign(x-1,y,z+2,sign,4,key,"id=" + str(e.id))
        mc.spawnEntity(x+10,y,z+10,e)
        untested.discard(e.id)
        time.sleep(0.25)
        z += 20
        if z > 80:
            z = ztest
            x += 25
    
    #Display list of all entities which did not get tested
    for id in untested:
        untest="Untested entity " + str(id)
        for varname in entitymap[id]:
            untest+=" " + varname
        mc.postToChat(untest)
        print(untest)
    mc.postToChat("runEntityTests() completed. Use command")
    mc.postToChat("/kill @e[type=!player]")
    mc.postToChat("to remove test entities")


def runTests(mc):

    #Hello World
    mc.postToChat("Hello Minecraft World, testing starts")

    #get/setPos
    #get/setTilePos
    pos = mc.player.getPos()
    tilePos = mc.player.getTilePos()
    mc.postToChat("player.getPos()=" + str(pos.x) + ":" + str(pos.y) + ":" + str(pos.z))
    time.sleep(wait_between_tests)

    height = mc.getHeight(pos.x,pos.z)
    mc.postToChat("getHeight()=" + str(height))
    time.sleep(wait_between_tests)

    mc.player.setPos(pos.x,pos.y + 10,pos.z)
    mc.postToChat("player.getTilePos()=" + str(tilePos.x) + ":" + str(tilePos.y) + ":" + str(tilePos.z))
    time.sleep(wait_between_tests)

    mc.player.setTilePos(tilePos.x, tilePos.y, tilePos.z)
    direction = mc.player.getDirection()
    mc.postToChat("player.getDirection()=" + str(direction))
    time.sleep(wait_between_tests)

    rotation = mc.player.getRotation()
    mc.postToChat("player.getRotation()=" + str(rotation))
    time.sleep(wait_between_tests)

    pitch = mc.player.getPitch()
    mc.postToChat("player.getPitch()=" + str(pitch))
    time.sleep(wait_between_tests)

    mc.player.setDirection(0,0,1)
    mc.player.setRotation(180)
    mc.player.setPitch(-45)

    #getBlock
    below = mc.getBlock(pos.x,pos.y-1,pos.z)
    mc.postToChat("block below is - " + str(below))
    time.sleep(wait_between_tests)

    #getBlockWithData (no longer supported by FruitJuice)
    #blockBelow = mc.getBlockWithData(pos.x, pos.y-1, pos.z)
    #mc.postToChat("block data below is = " + str(blockBelow.data))
    #ipdb.set_trace()

    #setBlock
    mc.setBlock(pos.x,pos.y+2,pos.z, "gold_block")
    mc.postToChat("set gold block at " + str(pos.x) + ":" + str(pos.y+2) + ":" + str(pos.z))
    time.sleep(wait_between_tests)

    #setBlocks
    mc.setBlocks(pos.x,pos.y + 10,pos.z,
                 pos.x + 5, pos.y + 15, pos.z + 5,
                 "white_wool")
    mc.postToChat("set white wool blocks from " + str(pos.x) + ":" + str(pos.y+10) + ":" + str(pos.z) + " to " + str(pos.x+5) + ":" + str(pos.y+15) + ":" + str(pos.z+5))
    time.sleep(wait_between_tests)


    #getBlocks
    #listOfBlocks = mc.getBlocks(pos.x,pos.y + 10,pos.z,
    #                            pos.x + 5, pos.y + 15, pos.z + 5)
    #print(listOfBlocks)

    #getPlayerEntityIds
    playerids = mc.getPlayerEntityIds()
    mc.postToChat("playerIds()=" + str(playerids))
    if len(playerids) > 0:
        playername = mc.entity.getName(playerids[0])
        mc.postToChat("player with id " + str(playerids[0]) + " has name " + playername)
        playerid = mc.getPlayerEntityId(playername)
        mc.postToChat("player with name " + playername + " has id " + str(playerid))
        time.sleep(wait_between_tests)

    #entity commands
    pos = mc.entity.getPos(playerids[0])
    tilePos = mc.entity.getTilePos(playerids[0])
    mc.postToChat("entity.getPos()=" + str(pos.x) + ":" + str(pos.y) + ":" + str(pos.z))
    mc.entity.setPos(playerids[0],pos.x,pos.y + 10,pos.z)
    mc.postToChat("entity.getTilePos()=" + str(tilePos.x) + ":" + str(tilePos.y) + ":" + str(tilePos.z))
    mc.entity.setTilePos(playerids[0],tilePos.x, tilePos.y, tilePos.z)
    time.sleep(wait_between_tests)

    #direction = mc.entity.getDirection(playerids[0])
    #mc.postToChat("entity.getDirection()=" + str(direction))
    #time.sleep(wait_between_tests)

    rotation = mc.entity.getRotation(playerids[0])
    mc.postToChat("entity.getRotation()=" + str(rotation))
    time.sleep(wait_between_tests)

    pitch = mc.entity.getPitch(playerids[0])
    mc.postToChat("entity.getPitch()=" + str(pitch))
    time.sleep(wait_between_tests)

    mc.entity.setDirection(playerids[0],0,0,1)
    mc.entity.setRotation(playerids[0],180)
    mc.entity.setPitch(playerids[0],-45)
    time.sleep(wait_between_tests)

#    #block hit events
#    mc.postToChat("hit a block with sword")
#    blockHit = False
#    while not blockHit:
#        time.sleep(1)
#        blockEvents = mc.events.pollBlockHits()
#        for blockEvent in blockEvents:
#            mc.postToChat("You hit block - x:" + str(blockEvent.pos.x) + " y:" + str(blockEvent.pos.y) + " z:" + str(blockEvent.pos.z))
#            blockHit = True

#    entity_types = mc.getEntityTypes()
#    mc.postToChat("The last found was entity: id=" + str(entity_types[-1].id) + " name=" + entity_types[-1].name)
#    time.sleep(wait_between_tests)

    mc.spawnEntity(tilePos.x + 2, tilePos.y + 2, tilePos.x + 2, entity.CREEPER)
    mc.postToChat("Creeper spawned")
    time.sleep(wait_between_tests)

    mc.postToChat("Post To Chat - Run full block and entity test Y/N?")
    chatPosted = False
    fullTests = False
    while not chatPosted:
        time.sleep(1)
        chatPosts = mc.events.pollChatPosts()
        for chatPost in chatPosts:
            mc.postToChat("Echo " + chatPost.message)
            chatPosted = True
            if chatPost.message == "Y":
                fullTests = True
    time.sleep(wait_between_tests)

    
    mc.postToChat("Tests complete")

# Library Tests
mc = minecraft.Minecraft.create(address="192.168.1.239",port = 4711)


runBlockTests(mc)
runEntityTests(mc)
runTests(mc)

mc.setBlock(0,-60,0,"PRISMARINE_STAIRS","EAST")
mc.setBlock(0,-60,2,"PRISMARINE_STAIRS","WEST")
mc.setBlock(0,-60,4,"PRISMARINE_STAIRS","NORTH")
mc.setBlock(0,-60,6,"PRISMARINE_STAIRS","SOUTH")
mc.setBlock(0,-60,8,"STONE")
mc.setBlock(0,-60,10,"COMPARATOR","EAST")
mc.setBlock(0,-60,12,"COMPARATOR","WEST")
mc.setBlock(0,-60,14,"COMPARATOR","NORTH")
mc.setBlock(0,-60,16,"COMPARATOR","SOUTH")

#ipdb.set_trace()

mc.postToChat("ALL TESTS COMPLETE")
