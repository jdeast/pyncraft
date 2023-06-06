from pyncraft.minecraft import Minecraft
import time,random

mc = Minecraft.create(address="192.168.1.239", port = 4711)

flowers=["DANDELION","POPPY","BLUE_ORCHID","ALLIUM","AZURE_BLUET","RED_TULIP","ORANGE_TULIP","WHITE_TULIP","PINK_TULIP","OXEYE_DAISY","CORNFLOWER","LILY_OF_THE_VALLEY"]

while True:
    x, y, z = mc.player.getPos()
    mc.setBlock(x, y, z, flowers[random.randint(0,len(flowers)-1)])
    time.sleep(0.3)
