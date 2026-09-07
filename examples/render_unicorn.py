import connect
import render_stl
import os
import math

# get the user's position
mc, args = connect.connect_from_args("Render a unicorn in minecraft")
pos = mc.player.getTilePos()

path = "data"
phi = -math.pi/2.0 # rotate so unicorn is standing up
stlfile = os.path.join(path,"alicorn-rmd-repaired.stl")

render_stl.render_stl(mc, stlfile, maxsize=100, xpos=-13, ypos=76, zpos=341, phi=phi, material="WHITE_CONCRETE", ordered_render=False)


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

