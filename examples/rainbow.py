from pyncraft.minecraft import Minecraft
import time, math

mc = Minecraft.create(address="192.168.1.239", port=4711, playerName='.saranova8124')

# block IDs of the rainbow
rainbow = ["RED_WOOL","ORANGE_WOOL","YELLOW_WOOL","GREEN_WOOL","BLUE_WOOL","PURPLE_WOOL"]

radius = 30
#swap these lines to make a rainbow tunnel that follows the user
#while True:
if True:
   pos = mc.player.getTilePos()
   for angle in range(360):
      for i in range(len(rainbow)):
         x = pos.x + (radius - i) * math.cos(angle*math.pi/180)
         y = pos.y + (radius - i) * math.sin(angle*math.pi/180)
         #ipdb.set_trace()
         if y > pos.y:
            mc.setBlock(x,y,pos.z,rainbow[i])
            time.sleep(0.01)

