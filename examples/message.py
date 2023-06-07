from pyncraft.minecraft import Minecraft
from pyncraft.vec3 import Vec3
import stltovoxel
import time, math, os, random
import ipdb
import numpy as np
import datetime

''' 
renders an stl file

stlfile - the path to a valid STL file
maxx - scale the x dimension to this number of blocks
maxy - scale the y dimension to this number of blocks
maxz - scale the z dimension to this number of blocks
maxsize - scale the maximum dimension to this number of blocks
NOTE: the aspect ratio is maintained. If more than one of (maxx, maxy, maxz, maxsize) is specified, only the first in this order is respected.
xpos - x coordinate of the corner of the model
ypos - y coordinate of the corner of the model
zpos - z coordinate of the corner of the model
theta - rotation angle
psi - rotation angle
phi - rotation angle
wait_between_blocks - time, in seconds, to wait between placing subsequent blocks (so we don't crash the server)
resolution - resolution of the STL file
material - The material to use, default OAK_PLANKS

'''
def render_stl(mc,stlfile,maxsize=25,maxx=None,maxy=None,maxz=None,xpos=0,ypos=50.0,zpos=0.0,theta=0.0,psi=0.0,phi=0.0,wait_between_blocks=0.05, resolution=200,material='OAK_PLANKS'):

   xyzfile = os.path.splitext(stlfile)[0] + "_" + str(resolution) + '.xyz'

   # convert the STL file to a series of XYZ positions. 
   # if the xyz file doesn't exist (from a previous run), create it
   if not os.path.exists(xyzfile):
      stltovoxel.convert_file(stlfile, xyzfile, resolution=resolution)

   pos = Vec3(xpos,ypos,zpos)

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
   xrange = np.max(xyz[:,0])-np.min(xyz[:,0])
   yrange = np.max(xyz[:,1])-np.min(xyz[:,1])
   zrange = np.max(xyz[:,2])-np.min(xyz[:,2])
   if maxx != None: scale = maxx/xrange
   elif maxy != None: scale = maxy/yrange
   elif maxz != None: scale = maxz/zrange
   else: 
      maxrange = np.max([xrange,yrange,zrange])
      scale = maxsize/maxrange

   # move to desired position and round
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

   # render each block in minecraft
   for i in range(len(x)):
      mc.setBlock(x[i],y[i],z[i],material)
      print((x[i],y[i],z[i]))
      # you can overload the server pretty quickly without waiting
      time.sleep(wait_between_blocks) 

   print("rendering took " + str((datetime.datetime.utcnow()-t0).total_seconds()) + " seconds for " + str(len(x)) + " blocks")

   return ( np.max(xyz[:,0])-np.min(xyz[:,0]), np.max(xyz[:,1])-np.min(xyz[:,1]), np.max(xyz[:,2])-np.min(xyz[:,2]) )

# when a sign won't cut it, write it in blocks!
message = "welcome to pyncraft"

charwidth = 10
charheight = 10
charspace = 11

x = 100
y = -20
z = 100

mc = Minecraft.create(address="192.168.1.239",port = 4711)
path = "data"

for element in message:
   stlfile = os.path.join(path,"Letter_" + element.upper() + '.stl')

   # skip unsupported characters
   if not os.path.isfile(stlfile): 
      x += charspace
      continue

   # I kinda like this stylistic font with fixed widths/variable heights
   #render_stl(mc,stlfile,xpos=x,ypos=y,zpos=z,maxx=charwidth,resolution=charwidth*5)
   #x += charspace

   # But this looks professional (fixed height/variable spacing/variable width)
   xrange,yrange,zrange = render_stl(mc,stlfile,xpos=x,ypos=y,zpos=z,maxy=charheight,resolution=charwidth*5)
   x += (xrange+2)
