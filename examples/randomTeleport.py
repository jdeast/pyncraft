import connect
from pyncraft.minecraft import Minecraft
mc = connect.connect_from_args("randomTeleport")[0]

import random

# Random position
x = random.randrange(-1000, 1000)
z = random.randrange(-1000, 1000)
y = mc.getHeight(x, z) # doesn't respect relative coordinates
y=0


# Teleport player
mc.player.setTilePos(x, y, z)
