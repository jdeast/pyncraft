import connect
# -*- coding: utf-8 -*-
"""
Created on Wed Oct  2 22:32:11 2019

@author: Eric
"""

from pyncraft.minecraft import Minecraft
mc = connect.connect_from_args("setSignOnPlayerPos")[0]

# Get player position
x,y,z = mc.player.getTilePos()
# Set a BIRCH_SIGN
mc.setSign(x,y,z, "BIRCH_SIGN", 0, "Hi", "I'm", "MinecraftDawn")