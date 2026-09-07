import connect
from pyncraft.minecraft import Minecraft
from pyncraft.vec3 import Vec3
try:
    import stltovoxel
except ImportError:
    raise SystemExit(
        "This example needs one more library. Run:\n"
        "    pip install stl-to-voxel")
import time, math, os, random
import numpy as np
import datetime
import argparse


''' 
renders an stl file

stlfile - the path to a valid STL file. STL files are standard files that represent 3D objects. They can be googled 
(they're often used for 3D printing) or you can create your own in something like solidworks.
This program imports these drawings into minecraft using the stltovoxel library.

maxx - scale the x dimension to this number of blocks
maxy - scale the y dimension to this number of blocks
maxz - scale the z dimension to this number of blocks
maxsize - scale the maximum dimension to this number of blocks

the longest dimension is scaled to this many blocks within minecraft. 
Increase for higher definition/larger size. 

NOTE: the aspect ratio is always maintained. If more than one of (maxx, maxy, maxz, maxsize) is specified, only the first in this order is respected.

Decrease for smaller size/faster rendering. Rendering time goes as maxsize^2 (maxsize^3 if solid==True)

xpos - x coordinate of the corner of the model
ypos - y coordinate of the corner of the model
zpos - z coordinate of the corner of the model
theta - rotation angle (radians)
psi - rotation angle (radians)
phi - rotation about the X axis (radians)
wait_between_blocks - time, in seconds, to wait between placing subsequent blocks (so we don't crash the server)
resolution - resolution of the STL file
material - The material to use, default OAK_PLANKS
solid - By default, the object is hollowed out such that any block surrounded that would 
        have been surrounded by other blocks is removed. This makes rendering faster.
        It's also fun to explore inside the objects. 
        Set this to retain all blocks.
ordered_render - When an object is hollowed out, the blocks are resorted into hash tables. 
                 Set ordered_render=True to resort by X, Y, Z. 
                 Both hash ordered and XYZ ordered is pretty neat to watch. 

'''

def render_stl(mc,stlfile,maxsize=25,maxx=None,maxy=None,maxz=None,xpos=0,ypos=50.0,zpos=0.0,
               theta=0.0,psi=0.0,phi=0.0,wait_between_blocks=0.01, resolution=200,material='OAK_PLANKS', 
               use_player_position=False, solid=False, ordered_render=False):

   xyzfile = os.path.splitext(stlfile)[0] + "_" + str(resolution) + '.xyz'

   # convert the STL file to a series of XYZ positions. 
   # if the xyz file doesn't exist (from a previous run), create it
   if not os.path.exists(xyzfile):
      if not os.path.exists(stlfile):
         print("ERROR: no XYZ or STL file exists; check path")
         return
      stltovoxel.convert_file(stlfile, xyzfile, resolution=resolution)

   if use_player_position:
      pos = mc.player.getTilePos()
   else:
      pos = Vec3(xpos,ypos,zpos)

   # read the file
   xyz = np.loadtxt(xyzfile)

   # rotate with Euler angles theta, psi, phi
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

   # make it hollow to speed up rendering
   # this scrambles the order of xyz. resort it by setting ordered_render=True
   # but random rendering is actually a pretty nice effect, especially for large objects 
   if not solid: xyz = shell(xyz, ordered_render=ordered_render)

   #print(np.shape(xyz))
   #print(np.shape(xyz2))

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

def shell(xyz, ordered_render=False):

   neighbor_offsets = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
   xyz_set = set(map(tuple, xyz)) 

   shell_xyz = []

   # If any neighbor is missing, the position is exposed
   for x, y, z in xyz_set:
      if any((x + dx, y + dy, z + dz) not in xyz_set for dx, dy, dz in neighbor_offsets):

         t1 = datetime.datetime.utcnow()
         if len(shell_xyz)==0:
            shell_xyz = np.transpose(np.array([[x,y,z]]))
         else:
            shell_xyz = np.hstack((shell_xyz,np.transpose(np.array([[x,y,z]]))))

   if ordered_render:
      return np.array(sorted(np.transpose(shell_xyz), key=lambda pos: (pos[0], pos[1], pos[2])))
   else: 
      return np.transpose(shell_xyz)

if __name__ == "__main__":

   parser = argparse.ArgumentParser(description='Import STL files into Minecraft')
   parser.add_argument('-j','--jwst', dest='jwst', action='store_true', default=False, help="Render JWST")
   parser.add_argument('-w','--carnival', dest='carnival_wheel', action='store_true', default=False, help="Render Carnival Wheel")
   parser.add_argument('-d','--trex', dest='trex', action='store_true', default=False, help="Render T-Rex")
   parser.add_argument('-u','--unicorn', dest='unicorn', action='store_true', default=False, help="Render Unicorn")
   parser.add_argument('-t','--tajmahal', dest='tajmahal', action='store_true', default=False, help="Render Taj Mahal")
   parser.add_argument('-c','--colosseum', dest='colosseum', action='store_true', default=False, help="Render Colosseum")


   connect.add_arguments(parser)
   opt = parser.parse_args()

   path = "data"

   # get the user's position
   mc = connect.connect(opt.host, opt.port, opt.player)
   pos = mc.player.getTilePos()

   if opt.jwst:
      # Space telescope
      # https://webbtelescope.org/contents/media/products/01G0MSRACZN6NDZTYHZJ44WWCY
      stlfile = os.path.join(path,'JWST.stl')
      phi = -math.pi/2.0 # rotate so sun shield is down
      theta = math.pi # rotate so sun shield is down
      render_stl.render_stl(mc,stlfile,maxsize=200, xpos=x+150, ypos=y, zpos=z)

   if opt.carnival_wheel:
      # solidworks drawing by Blake Eastman
      stlfile = os.path.join(path,"carnival_wheel_assy.STL")
      render_stl.render_stl(mc,stlfile,maxsize=200, xpos=x+150, ypos=y, zpos=z)

   if opt.trex:
      # https://www.ameede.net/dinosaur-t-rex-h003332-file-stl-free-download-3d-model-for-cnc-and-3d-printer/
      stlfile = os.path.join(path,"T-Rex.stl")

   if opt.unicorn:
      stlfile = os.path.join(path,"alicorn-rmd-repaired.stl")
      phi = -math.pi/2.0 # rotate so unicorn is standing up
      render_stl(mc, stlfile, maxsize=100, xpos=2000, ypos=-60, zpos=2000, phi=phi, material="WHITE_CONCRETE")

   if opt.tajmahal:
      # https://www.printables.com/model/264372-taj-mahal-agra-india/files
      phi = 0 #-math.pi/2.0 # rotate so unicorn is standing up
      stlfile = os.path.join(path,"taj-mahal-by-miniworld3d.stl")
      render_stl(mc, stlfile, maxsize=100, xpos=0, ypos=-60, zpos=6000, phi=phi, material="WHITE_CONCRETE")

   if opt.colosseum:
      #https://www.printables.com/model/217557-coliseum/files
      stlfile = os.path.join(path,"colosseum_final.stl")
      phi = -math.pi/2.0
      render_stl(mc, stlfile, maxsize=30, xpos=1000, ypos=-60, zpos=1000, phi=phi, material="WHITE_CONCRETE")
