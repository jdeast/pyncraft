''' 
Use professional astronomy libraries to query a star catalog
for bright stars and place glowstone at their true, observed positions within 
minecraft based on the time/location specified.

NOTE: The distances/brightnesses are not to scale. 

NOTE 2: astroquery is not a pyncraft dependency, but required here. 
You must install astroquery separately:

pip install astroquery

6/12/2023: Written, Jason Eastman
'''

from astroquery.vizier import Vizier
from astropy.coordinates import EarthLocation,SkyCoord
from astropy.time import Time
from astropy import units as u
from astropy.coordinates import AltAz
from astropy.coordinates import Angle

import math
import ipdb

# pyncraft connection
import pyncraft.minecraft as minecraft
mc = minecraft.Minecraft.create(address="192.168.1.239",port = 4711)

# radius and center of the celestial sphere
r = 100
x0 = 0
y0 = -60
z0 = 0

try: mc.player.setTilePos(x0, y0, z0)
except: pass

# query the Bright Star catalog
cat = Vizier(catalog="V/50/catalog",columns=['*', '_RAJ2000', '_DEJ2000'])

# the default just takes the first 50 stars, ROW_LIMIT=-1 takes them all
# this is fine for the bright star catalog (~9000 stars), but if you swap 
# "V/50/catalog" for bigger catalogs, unlimited rows can be 10s of GBs
# and stress both your computer and the servers that host the catalogs
cat.ROW_LIMIT = -1 

# only select stars brighter than V=4 
# this is a decent limit to see recognizable constellations 
brightstars = cat.query_constraints(Vmag="<4.0")[0]

# at the default time/location, look for the big dipper, 
# vertical with the handle down on the northern horizon
# or specify an address (e.g., your address)
#observing_location = EarthLocation.of_address("Cambridge, MA")

# equivalent way of specifying Cambridge, MA (lon is East longitude)
observing_location = EarthLocation(lat='42.3736', lon='-71.1097', height=100*u.m)  

# specify a particular UTC time like this
observing_time = Time('2023-02-05 23:00:00')  # 7 pm ET

# or specify the current time like this
#observing_time = Time.now() 

# function to convert from RA/Dec to alt/az based on location/time
aa = AltAz(location=observing_location, obstime=observing_time)

# add cardinal directions on signs for orientation
offset = 5
mc.setSign(x0,y0,z0-offset,"BIRCH_SIGN",0,"North")
mc.setSign(x0+offset,y0,z0,"BIRCH_SIGN",4,"East")
mc.setSign(x0,y0,z0+offset,"BIRCH_SIGN",8,"South")
mc.setSign(x0-offset,y0,z0,"BIRCH_SIGN",12,"West")

# loop over each star in the catalog
for star in brightstars:

	# convert from RA/dec (star coordinates) to alt/az (earth coordinates)
	coord = SkyCoord(Angle(star['_RAJ2000'],unit=u.deg),Angle(star['_DEJ2000'],unit=u.deg))
	altaz = coord.transform_to(aa)

	# convert alt az to xyz
	# +X is East, +Z is South, +Y is up
	x =  r*math.cos(altaz.alt.rad)*math.sin(altaz.az.rad)
	y =  r*math.sin(altaz.alt.rad)
	z = -r*math.cos(altaz.alt.rad)*math.cos(altaz.az.rad)

	# if it's above the horizon, plot it
	if y > 0:
		mc.setBlock(x+x0,y+y0,z+z0,"GLOWSTONE")
		print(x+x0,y+y0,z+z0)