import os, math

import message, render_stl
import connect

mc, args = connect.connect_from_args("STEM night demo")

x=0
y=0
z=0

# write text in blocks
#text = " STEM Night\nRoberts 2025"
#message.message(mc, text, x=x, y=y, z=z)

# Space telescope
# https://webbtelescope.org/contents/media/products/01G0MSRACZN6NDZTYHZJ44WWCY
path = "data"
stlfile = os.path.join(path,'JWST.stl')
phi = -math.pi/2.0 # rotate so sun shield is down
theta = math.pi # rotate so sun shield is down
size = 100
render_stl.render_stl(mc,stlfile,maxsize=size, xpos=x+165, ypos=y, zpos=z-35, phi=phi, theta=theta)

