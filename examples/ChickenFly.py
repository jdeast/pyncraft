import connect
from pyncraft.minecraft import Minecraft
mc = connect.connect_from_args("ChickenFly")[0]

import random, time

# Get player position
x,y,z = mc.player.getPos()

# Spawn a chicken on player's position,and record the chicken's entity id
chicken = mc.spawnEntity(x, y, z, 93)

for i in range(30):
    # Get player position
    x,y,z = mc.player.getPos()
    # Add a random number on x and z position
    x += random.uniform(-3, 3)
    z += random.uniform(-3, 3)
    # Teleport chicken
    mc.entity.setPos(chicken, x, y+3, z)
    # Sleep 0.5 seconds
    time.sleep(0.5)