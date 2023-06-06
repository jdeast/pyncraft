from pyncraft.minecraft import Minecraft
import stltovoxel
import time
import ipdb
import math
import os
import numpy as np
import random

# the maximum dimension is scaled to this many blocks within minecraft
maxsize = 50.0 

# resolution of the drawing. decrease if too big/takes too long. increase if there are holes
resolution = 100 

path = "data"
stlfile = os.path.join(path,"gumball_machine.STL")
xyzfile = os.path.splitext(stlfile)[0] + "_" + str(resolution) + '.xyz'

# convert the STL file to a series of XYZ positions. 
# if the xyz file doesn't exist (from a previous run), create it
if not os.path.exists(xyzfile):
   stltovoxel.convert_file(stlfile, xyzfile, resolution=resolution)

# get the user's position
mc = Minecraft.create(address="192.168.1.239",port = 4711)
pos = mc.player.getTilePos()

#ipdb.set_trace()

#pos.x = 60
#pos.y = 62
#pos.z = 920

# read the file
xyz = np.loadtxt(xyzfile)
x = xyz[:,0]
y = xyz[:,1]
z = xyz[:,2]

# scale to maxsize
maxrange = max([(np.max(x)-np.min(x)),(np.max(y)-np.min(y)),(np.max(z)-np.min(z))])
scale = maxsize/maxrange
x = (x - np.min(x))*scale + pos.x
y = (y - np.min(y))*scale + pos.y
z = (z - np.min(z))*scale + pos.z

rainbow = [14,1,4,13,11,10,2]

# render each block in minecraft (make the base oak plank, and the jar glass)
for i in range(len(x)):
   if y[i] > pos.y+27:#89:
      mc.setBlock(x[i],y[i],z[i],"GLASS")
   else:
      mc.setBlock(x[i],y[i],z[i],"OAK_PLANKS")
   print((x[i],y[i],z[i]))
   #time.sleep(0.1)

minx = pos.x + 6 #66
maxx = minx + 7 #73
miny = pos.y+ 27#89 
maxy = miny + 21 # 110
minz = pos.z + 12 #932
maxz = minz + 8 #940

# delete old gumballs
for i in range(maxx-minx+1):
   x = minx + i
   for j  in range(maxy-miny+1):
      y = miny+j
      for k in range(maxz-minz+1):
         z = minz+k
         mc.setBlock(x,y,z,"AIR")
         print((x,y,z))


# make new gumballs
rainbow = ["RED_WOOL","ORANGE_WOOL","YELLOW_WOOL","GREEN_WOOL","BLUE_WOOL","PURPLE_WOOL"]

n_gumballs = 200
for i in range(n_gumballs):
   x = random.randint(minx,maxx)      
   y = random.randint(miny,maxy)
   z = random.randint(minz,maxz)
   ndx = random.randint(0,5)
   mc.setBlock(x,y,z,rainbow[ndx])
   print((x,y,z))

