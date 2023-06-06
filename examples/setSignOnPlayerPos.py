# -*- coding: utf-8 -*-
"""
Created on Wed Oct  2 22:32:11 2019

@author: Eric
"""

from pyncraft.minecraft import Minecraft
mc = Minecraft.create(address="192.168.1.239",port = 4721)

# Get player position
x,y,z = mc.player.getTilePos()
# Set a BIRCH_SIGN
mc.setSign(x,y,z, "BIRCH_SIGN", 0, "Hi", "I'm", "MinecraftDawn")