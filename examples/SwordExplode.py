# -*- coding: utf-8 -*-
"""
Created on Tue Oct  1 21:31:06 2019

@author: Eric
"""

from pyncraft.minecraft import Minecraft
mc = Minecraft.create(address="192.168.1.239",port = 4721)

while True:
    # Get list of events
    hitBlocks = mc.events.pollBlockHits()
    # If events not None
    if hitBlocks:
        # Get the first event
        hitBlock = hitBlocks[0]
        # Get the event position
        x,y,z = hitBlock.pos
        # Create a explosion on the position
        mc.createExplosion(x, y, z)