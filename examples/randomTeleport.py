from pyncraft.minecraft import Minecraft
mc = Minecraft.create(address="192.168.1.239", port = 4711)

import random

# Random position
x = random.randrange(-1000, 1000)
z = random.randrange(-1000, 1000)
y = mc.getHeight(x, z) # doesn't respect relative coordinates
y=0

import ipdb
ipdb.set_trace()

# Teleport player
mc.player.setTilePos(x, y, z)
