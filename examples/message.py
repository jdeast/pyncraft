import connect
import os

# pyncraft library
from pyncraft.minecraft import Minecraft

# imports from this repo
import render_stl

def message(mc, text, charwidth=13,charheight=13,charspace=14,x=0,y=0,z=0, hostname='localhost',port=4711, fixedwidth=False):

   path = "data"

   x0 = x
   for element in text:
      if element == '\n':
         x = x0
         y -= charheight*1.2
         continue

      stlfile = os.path.join(path, element.upper() + '.stl')

      # skip unsupported characters
      if not os.path.isfile(stlfile): 
         x += charspace
         continue

      # I kinda like this stylistic font with fixed widths/variable heights
      if fixedwidth:
         render_stl.render_stl.render_stl(mc,stlfile,xpos=x,ypos=y,zpos=z,maxx=charwidth,resolution=charwidth*5)
         x += charspace
      else:
         # But this looks professional (fixed height/variable spacing/variable width)
         xrange,yrange,zrange = render_stl.render_stl(mc,stlfile,xpos=x,ypos=y,zpos=z,maxy=charheight,resolution=charwidth*5)
         x += (xrange+2)

if __name__ == "__main__":

   # when a sign won't cut it, write it in blocks!
   # STL files from https://www.thingiverse.com/thing:15198

   mc, args = connect.connect_from_args("Write a message in blocks")

   text = " STEM Night\nRoberts 2025"

   message(mc, text)
 