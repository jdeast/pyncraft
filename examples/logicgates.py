import pyncraft.minecraft as minecraft
import ipdb

''' 
This program builds the 8 fundamental logic gates from which all computing can be accomplished. 
It demonstrates the use of directional (NORTH,SOUTH,EAST,WEST) and facing (WALL,FLOOR,CEILING) 
arguments to place torches and levers, which requires FruitJuice-0.2.0.jar or later.

It follows this youtube video:
# https://www.youtube.com/watch?v=nfIRIInU2Vg
'''

mc = minecraft.Minecraft.create(address="192.168.1.239",port = 4711)

x =0
y=-60
z=0

size = 100
xsize = 16
zsize = 40

#mc.player.setTilePos(x-10, y, z-10)

# make the pad
mc.setBlocks(x,y,z,x+size,y+5,z+size,"AIR")
mc.setBlocks(x,y-1,z,x+size,y-1,z+size,"GRASS_BLOCK")
mc.setBlocks(x,y-1,z,x+xsize,y-1,z+zsize,"STONE")

z+=2

# buffer gate
mc.setBlock(x+1,y,z,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z,x+7,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+8,y,z,"REDSTONE_LAMP")
mc.setSign(x+2,y,z-1,"BIRCH_SIGN",4,"Buffer","Gate")

z += 5

# INVERSE gate
# NOTE: when this is built, it's in the on state, but the switch must be cycled to be turned on
# Not sure if that can be fixed by modifying block data in the FruitJuice plugin
mc.setBlock(x+1,y,z,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z,x+7,y,z,"REDSTONE_WIRE")
mc.setBlock(x+3,y,z,"STONE")
mc.setBlock(x+4,y,z,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+8,y,z,"REDSTONE_LAMP")
mc.setSign(x+3,y+1,z,"BIRCH_SIGN",4,"Inverse","Gate")
#mc.setWallSign(x+2, y, z, "BIRCH_WALL_SIGN", 1, "INVERSE","Gate")

z += 5

# OR gate
mc.setBlock(x+1,y,z-1,"LEVER","WEST","FLOOR")
mc.setBlock(x+1,y,z+1,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z-1,x+3,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+2,y,z+1,x+3,y,z+1,"REDSTONE_WIRE")
mc.setBlocks(x+3,y,z,x+7,y,z,"REDSTONE_WIRE")
mc.setBlock(x+8,y,z,"REDSTONE_LAMP")
mc.setSign(x+4,y,z+1,"BIRCH_SIGN",4,"OR","Gate")

z += 5

# NOR gate
# NOTE: when this is built, it's in the on state, but a switch must be cycled to be turned on
mc.setBlock(x+1,y,z-1,"LEVER","WEST","FLOOR")
mc.setBlock(x+1,y,z+1,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z-1,x+3,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+2,y,z+1,x+3,y,z+1,"REDSTONE_WIRE")
mc.setBlocks(x+3,y,z,x+7,y,z,"REDSTONE_WIRE")
mc.setBlock(x+4,y,z,"STONE")
mc.setBlock(x+4,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+5,y,z,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+8,y,z,"REDSTONE_LAMP")
mc.setSign(x+4,y,z+1,"BIRCH_SIGN",4,"NOR","Gate")

z += 5

# AND gate
mc.setBlock(x+1,y,z-1,"LEVER","WEST","FLOOR")
mc.setBlock(x+1,y,z+1,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z-1,x+3,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+2,y,z+1,x+3,y,z+1,"REDSTONE_WIRE")
mc.setBlocks(x+5,y,z,x+7,y,z,"REDSTONE_WIRE")
mc.setBlocks(x+4,y,z-1,x+4,y,z+1,"STONE")
mc.setBlock(x+4,y+1,z-1,"REDSTONE_TORCH")
mc.setBlock(x+4,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+5,y,z,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+4,y+1,z+1,"REDSTONE_TORCH")
mc.setBlock(x+8,y,z,"REDSTONE_LAMP")
mc.setWallSign(x+3, y, z, "BIRCH_WALL_SIGN", 1, "AND","Gate")

z += 5

# NAND gate (equivalent to inverted OR gate)
# NOTE: when this is built, it's in the on state, but both switches must be cycled to function
# NOTE 2: in the video he calls this "NOR", but it's actually "NAND"
mc.setBlock(x+1,y,z-1,"LEVER","WEST","FLOOR")
mc.setBlock(x+1,y,z+1,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z-1,x+3,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+2,y,z+1,x+3,y,z+1,"REDSTONE_WIRE")
mc.setBlocks(x+5,y,z,x+7,y,z,"REDSTONE_WIRE")
mc.setBlocks(x+4,y,z-1,x+4,y,z+1,"STONE")
mc.setBlock(x+4,y+1,z-1,"REDSTONE_TORCH")
mc.setBlock(x+4,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+4,y+1,z+1,"REDSTONE_TORCH")
mc.setBlock(x+8,y,z,"REDSTONE_LAMP")
mc.setWallSign(x+3, y, z, "BIRCH_WALL_SIGN", 1, "NAND","Gate")

z += 5

# XOR gate
mc.setBlock(x+1,y,z-1,"LEVER","WEST","FLOOR")
mc.setBlock(x+1,y,z+1,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z-1,x+3,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+2,y,z+1,x+3,y,z+1,"REDSTONE_WIRE")
mc.setBlocks(x+4,y,z-1,x+4,y,z+1,"STONE")
mc.setBlock(x+4,y+1,z-1,"REDSTONE_TORCH")
mc.setBlock(x+4,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+4,y+1,z+1,"REDSTONE_TORCH")
mc.setBlock(x+5,y,z-1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+5,y,z+1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+5,y,z,"STONE")
mc.setBlock(x+5,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+6,y,z,"REDSTONE_WALL_TORCH","EAST")
mc.setBlocks(x+6,y,z-1,x+7,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+6,y,z+1,x+7,y,z+1,"REDSTONE_WIRE")
mc.setBlock(x+8,y,z-1,"STONE")
mc.setBlock(x+8,y,z+1,"STONE")
mc.setBlock(x+9,y,z-1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+9,y,z+1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlocks(x+9,y,z,x+10,y,z,"REDSTONE_WIRE")
mc.setBlock(x+11,y,z,"REDSTONE_LAMP")
mc.setWallSign(x+3, y, z, "BIRCH_WALL_SIGN", 1, "XOR","Gate")

z += 5

# XNOR gate
# NOTE: when this is built, it's in the on state, but a switch must be cycled to be turned on
mc.setBlock(x+1,y,z-1,"LEVER","WEST","FLOOR")
mc.setBlock(x+1,y,z+1,"LEVER","WEST","FLOOR")
mc.setBlocks(x+2,y,z-1,x+3,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+2,y,z+1,x+3,y,z+1,"REDSTONE_WIRE")
mc.setBlocks(x+4,y,z-1,x+4,y,z+1,"STONE")
mc.setBlock(x+4,y+1,z-1,"REDSTONE_TORCH")
mc.setBlock(x+4,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+4,y+1,z+1,"REDSTONE_TORCH")
mc.setBlock(x+5,y,z-1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+5,y,z+1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+5,y,z,"STONE")
mc.setBlock(x+5,y+1,z,"REDSTONE_WIRE")
mc.setBlock(x+6,y,z,"REDSTONE_WALL_TORCH","EAST")
mc.setBlocks(x+6,y,z-1,x+7,y,z-1,"REDSTONE_WIRE")
mc.setBlocks(x+6,y,z+1,x+7,y,z+1,"REDSTONE_WIRE")
mc.setBlock(x+8,y,z-1,"STONE")
mc.setBlock(x+8,y,z+1,"STONE")
mc.setBlock(x+9,y,z-1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+9,y,z+1,"REDSTONE_WALL_TORCH","EAST")
mc.setBlocks(x+9,y,z,x+10,y,z,"REDSTONE_WIRE")
mc.setBlock(x+11,y,z,"STONE")
mc.setBlock(x+12,y,z,"REDSTONE_WALL_TORCH","EAST")
mc.setBlock(x+13,y,z,"REDSTONE_WIRE")
mc.setBlock(x+14,y,z,"REDSTONE_LAMP")
mc.setWallSign(x+3, y, z, "BIRCH_WALL_SIGN", 1, "XNOR","Gate")

#mc.setBlock(0,-60,10,"COMPARATOR","EAST")
#mc.setBlock(0,-60,12,"COMPARATOR","WEST")
#mc.setBlock(0,-60,14,"COMPARATOR","NORTH")
#mc.setBlock(0,-60,16,"COMPARATOR","SOUTH")