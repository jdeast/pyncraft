from pyncraft.minecraft import Minecraft
from pyncraft.vec3 import Vec3
import stltovoxel
import time, math, os, random
import ipdb
import numpy as np
import datetime


''' 
STL files are standard files that represent 3D objects. They can be googled 
(they're often used for 3D printing) or you can create your own in something like solidworks.
This program can import these drawings into minecraft using the stltovoxel library.
'''

# the longest dimension is scaled to this many blocks within minecraft. 
# Increase for higher definition/larger size. 
# Decrease for smaller size/faster rendering.
# rendering time goes as maxsize^3
maxsize = 75.0

# resolution of the drawing. decrease if too big/takes too long. increase if there are holes (or missing rows/columns)
resolution = 200

# the server can easily be overloaded with rapid-fire setBlock commands. 
# The smaller the wait, the faster render, but the more likely it'll break the server
wait_between_blocks = 0.05

# rotation of the STL file -- change these for an arbitrary rotation of the model
theta = 0.0
psi = 0.0
phi = 0.0

path = "data"

# https://www.ameede.net/dinosaur-t-rex-h003332-file-stl-free-download-3d-model-for-cnc-and-3d-printer/
stlfile = os.path.join(path,"T-Rex.stl")
xyzfile = os.path.splitext(stlfile)[0] + "_" + str(resolution) + '.xyz'

# convert the STL file to a series of XYZ positions. 
# if the xyz file doesn't exist (from a previous run), create it
if not os.path.exists(xyzfile):
   stltovoxel.convert_file(stlfile, xyzfile, resolution=resolution)

# get the user's position
mc = Minecraft.create(address="192.168.1.239",port = 4711)

try:
   pos = mc.player.getTilePos()
except:
   pos = Vec3(0,50,0)
   print("No players found; placing at " + str(pos.x) + ',' + str(pos.y) + ',' + str(pos.z))

# read the file
xyz = np.loadtxt(xyzfile)

# rotate with Euler angles
x = xyz[:,0]
y = xyz[:,1]
z = xyz[:,2]
xrot = x*(np.cos(theta)*np.cos(psi)) + y*(np.sin(phi)*np.sin(theta)*np.cos(psi) - np.cos(phi)*np.sin(psi)) + z*(np.cos(phi)*np.sin(theta)*np.cos(psi) + np.sin(phi)*np.sin(psi))
yrot = x*(np.cos(theta)*np.sin(psi)) + y*(np.sin(phi)*np.sin(theta)*np.sin(psi) + np.cos(phi)*np.cos(psi)) + z*(np.cos(phi)*np.sin(theta)*np.sin(psi) - np.sin(phi)*np.cos(psi))
zrot = x*(-np.sin(theta))            + y*(np.sin(phi)*np.cos(theta))                                       + z*(np.cos(phi)*np.cos(theta))
xyz[:,0] = xrot
xyz[:,1] = yrot
xyz[:,2] = zrot

# scale to desired size
maxrange = max([(np.max(xyz[:,0])-np.min(xyz[:,0])),(np.max(xyz[:,1])-np.min(xyz[:,1])),(np.max(xyz[:,2])-np.min(xyz[:,2]))])
scale = maxsize/maxrange

# move to the player position and round
xyz[:,0] = np.round((xyz[:,0] - np.min(xyz[:,0]))*scale + pos.x)
xyz[:,1] = np.round((xyz[:,1] - np.min(xyz[:,1]))*scale + pos.y)
xyz[:,2] = np.round((xyz[:,2] - np.min(xyz[:,2]))*scale + pos.z)

# remove duplicates (minimizes server communication, especially when resolution is high)
xyz = np.unique(xyz,axis=0)

x = xyz[:,0]
y = xyz[:,1]
z = xyz[:,2]

t0 = datetime.datetime.utcnow()
print("rendering will take ~" + str(len(x)*wait_between_blocks/60) + " minutes for " + str(len(x)) + " blocks")
time.sleep(5)

# render each block in minecraft
for i in range(len(x)):
   mc.setBlock(x[i],y[i],z[i],'OAK_PLANKS')
   print((x[i],y[i],z[i]))
   # you can overload the server pretty quickly without waiting
   time.sleep(wait_between_blocks) 

print("rendering took " + str((datetime.datetime.utcnow()-t0).total_seconds()) + " seconds for " + str(len(x)) + " blocks")
