from .connection import Connection
from .vec3 import Vec3
from .event import BlockEvent, ChatEvent, ArrowHitEvent
#from .entity import Entity
#from .block import Block
from .util import flatten
from warnings import warn
from .logger import *
import sys
import time

""" Minecraft PI low level api v0.1_1

    Note: many methods have the parameter *arg. This solution makes it
    simple to allow different types, and variable number of arguments.
    The actual magic is a mix of flatten_parameters() and __iter__. Example:
    A Cube class could implement __iter__ to work in Minecraft.setBlocks(c, id).

    (Because of this, it's possible to "erase" arguments. CmdPlayer removes
     entityId, by injecting [] that flattens to nothing)

    @author: Aron Nieminen, Mojang AB"""


def intFloor(*args):
    return [int(x) for x in flatten(args)]

class CmdPositioner:
    """Methods for setting and getting positions"""
    def __init__(self, connection, packagePrefix):
        self.conn = connection
        self.pkg = packagePrefix

    def getPos(self, ID) -> Vec3:
        """Get entity position (entityId:int) => Vec3"""
        s = self.conn.sendReceive(self.pkg + b".getPos", ID)
        return Vec3(*list(map(float, s.split(","))))

    def setPos(self, ID, x:float, y:float, z:float) -> None:
        """Set entity position (entityId:int, x,y,z)"""
        self.conn.send(self.pkg + b".setPos", ID, x, y, z)

    def getTilePos(self, ID) -> Vec3:
        """Get entity tile position (entityId:int) => Vec3"""
        s = self.conn.sendReceive(self.pkg + b".getTile", ID)
        return Vec3(*list(map(int, s.split(","))))

    def setTilePos(self, ID, x:int, y:int, z:int) -> None:
        """Set entity tile position (entityId:int) => Vec3"""
        self.conn.send(self.pkg + b".setTile", ID, x, y, z)
        
    def getDirection(self, ID) -> Vec3:
        """Get direction of the entity"""
        s = self.conn.sendReceive(self.pkg + b".getDirection", ID)
        return Vec3(*list(s.split(",")))
        
    def setDirection(self, ID, x:float, y:float, z:float) -> None:
        """Set direction of the entity"""
        self.conn.send(self.pkg + b".setDirection", ID, x, y, z)
        
    def getRotation(self, ID) -> float:
        """Get rotation if the entity"""
        s = self.conn.sendReceive(self.pkg + b".getRotation", ID)
        return float(s)
    
    def setRotation(self, ID, yaw) -> float:
        """Set rotation if the entity"""
        self.conn.send(self.pkg + b".setRotation", ID, yaw)
        
    def getPitch(self, ID) -> float:
        """Get pitch if the entity"""
        s = self.conn.sendReceive(self.pkg + b".getPitch", ID)
        return float(s)
    
    def setPitch(self, ID, pitch) -> None:
        """Set pitch if the entity"""
        self.conn.send(self.pkg + b".setPitch", ID, pitch)
        
    def setting(self, setting, status) -> None:
        """Set a player setting (setting, status). keys: autojump"""
        self.conn.send(self.pkg + b".setting", setting, 1 if bool(status) else 0)

class CmdEntity(CmdPositioner):
    """Methods for entities"""
    def __init__(self, connection):
        CmdPositioner.__init__(self, connection, b"entity")
        
    def getName(self, ID):
        """Get the list name of the player with entity id => [name:str]
        
        Also can be used to find name of entity if entity is not a player."""
        return self.conn.sendReceive(b"entity.getName", ID)


class CmdPlayer(CmdPositioner):
    """Methods for the host player"""
    def __init__(self, connection, playerId):
        CmdPositioner.__init__(self, connection,  b"player")
        self.conn = connection
        self.playerId=playerId

    def getPos(self) -> Vec3:
        return CmdPositioner.getPos(self, self.playerId)
    def setPos(self, x:float, y:float, z:float) -> None:
        return CmdPositioner.setPos(self, self.playerId, x, y, z)
    def getTilePos(self) -> Vec3:
        return CmdPositioner.getTilePos(self, self.playerId)
    def setTilePos(self, x:int, y:int, z:int) -> None:
        return CmdPositioner.setTilePos(self, self.playerId, x, y, z)
    def getDirection(self) -> Vec3:
        return CmdPositioner.getDirection(self, self.playerId)
    def setDirection(self, x:float, y:float, z:float) -> None:
        return CmdPositioner.setDirection(self, self.playerId, x, y, z)
    def getRotation(self) -> float:
        return CmdPositioner.getRotation(self, self.playerId)
    def setRotation(self, yaw) -> None:
        return CmdPositioner.setRotation(self, self.playerId, yaw)
    def getPitch(self) -> float:
        return CmdPositioner.getPitch(self, self.playerId)
    def setPitch(self, pitch) -> None:
        return CmdPositioner.setPitch(self, self.playerId, pitch)
    
    def getFoodLevel(self) -> int:
        return self.conn.sendReceive(self.pkg + b".getFoodLevel", self.playerId)
    
    def setFoodLevel(self, foodLevel:int) -> None:
        self.conn.send(self.pkg + b".setFoodLevel", self.playerId, foodLevel)
        
    def getHealth(self) -> float:
        return self.conn.sendReceive(self.pkg + b".getHealth", self.playerId)
    
    def setHealth(self, health:float) -> None:
        self.conn.send(self.pkg + b".setHealth", self.playerId, health)
    
    def sendTitle(self, title:str, subTitle:str="", fadeIn:int=10, stay:int=70, fadeOut:int=20) -> None:
        self.conn.send(self.pkg + b".sendTitle", self.playerId, title, subTitle, fadeIn, stay, fadeOut)
 
class CmdPlayerEntity(CmdPlayer):
    """ use entity to build a player """
    def __init__(self, connection,playerId):
        CmdPositioner.__init__(self, connection,  b"entity")
        self.conn = connection
        self.playerId=playerId
        
    def getPos(self):
            return CmdPositioner.getPos(self, self.playerId)

class CmdCamera:
    def __init__(self, connection):
        self.conn = connection

    def setNormal(self, *args) -> None:
        """Set camera mode to normal Minecraft view ([entityId])"""
        self.conn.send(b"camera.mode.setNormal", args)

    def setFixed(self) -> None:
        """Set camera mode to fixed view"""
        self.conn.send(b"camera.mode.setFixed")

    def setFollow(self, *args) -> None:
        """Set camera mode to follow an entity ([entityId])"""
        self.conn.send(b"camera.mode.setFollow", args)

    def setPos(self, x:float, y:float, z:float) -> None:
        """Set camera entity position (x,y,z)"""
        self.conn.send(b"camera.setPos", x, y, z)


class CmdEvents:
    """Events"""
    def __init__(self, connection):
        self.conn = connection

    def clearAll(self):
        """Clear all old events"""
        self.conn.send(b"events.clear")

    def pollBlockHits(self):
        """Only triggered by sword => [BlockEvent]"""
        s = self.conn.sendReceive(b"events.block.hits")
        events = [e for e in s.split("|") if e]
        return [BlockEvent.Hit(*list(map(int, e.split(",")))) for e in events]

    def pollArrowHits(self):
        """Only triggered by sword => [BlockEvent]"""
        s = self.conn.sendReceive(b"events.arrow.hits")
        events = [e for e in s.split("|") if e]
        return [ArrowHitEvent.Hit(*list(map(int, e.split(",")))) for e in events]
    
    def pollChatPosts(self):
        """Triggered by posts to chat => [ChatEvent]"""
        s = self.conn.sendReceive(b"events.chat.posts")
        events = [e for e in s.split("|") if e]
        return [ChatEvent.Post(int(e[:e.find(",")]), e[e.find(",") + 1:]) for e in events]


def reshape_blocks(names, xs, ys, zs):
    """The server's flat block list into [y][x][z], which is the order it uses.

    Kept out of the Minecraft class so it can be tested without a server: the
    whole bug was in the arithmetic, and the arithmetic needs no socket.
    """
    if len(names) != xs * ys * zs:
        # `warn` here is this package's logger, not warnings.warn: the
        # `from .logger import *` above shadows it. That is worth knowing
        # before writing a test that waits for a warning which never arrives.
        warn("getBlocks: expected %d blocks, got %d" % (xs * ys * zs, len(names)))
    out, k = [], 0
    for _ in range(ys):
        slab = []
        for _ in range(xs):
            slab.append(names[k:k + zs])
            k += zs
        out.append(slab)
    return out



class Minecraft:
    """The main class to interact with a running instance of Minecraft Pi."""
    def __init__(self, connection, playerId):
        self.conn = connection

        self.camera = CmdCamera(connection)
        self.entity = CmdEntity(connection)
        self.cmdplayer = CmdPlayer(connection,playerId)

        # not sure why mcpi_e did this, but it doesn't work with empty playerIds
        #self.player = CmdPlayerEntity(connection,playerId)
        self.player = CmdPlayer(connection,playerId)

        self.events = CmdEvents(connection)
        self.playerId = playerId
        self.settings = settings

    def getBlock(self, x:int, y:int, z:int) -> str:
        """Get block (x,y,z) => id:int"""
        return self.conn.sendReceive(b"world.getBlock", x, y, z)

    def getBlockData(self, x, y=None, z=None, parse: bool = True) -> dict:
        """Get a block's material and state (x,y,z) => dict

        Takes either three coordinates or one Vec3/Coord. Returns a dict with
        the coordinates, the material, and whatever state applies to that block
        type. For an east-facing oak stair:

            {"x": 0, "y": 64, "z": 0, "material": "OAK_STAIRS",
             "facing": "east", "half": "bottom", "shape": "straight"}

        With parse=False the state is left as one string under "state".

        Needs FruitJuice 0.4.0 or newer; older servers reply that
        world.getBlockData is not supported, which raises RequestError.
        """
        if y is None and z is None:
            x, y, z = (x.x, x.y, x.z) if hasattr(x, "x") else tuple(x)

        data = {"x": x, "y": y, "z": z}
        raw = self.conn.sendReceive(b"world.getBlockData", x, y, z).strip()
        if not raw:
            return data

        # The server sends BlockData.getAsString(), e.g.
        #   minecraft:oak_stairs[facing=east,half=bottom,shape=straight]
        # Note the commas live inside the brackets, so this cannot be split on
        # commas the way getBlocks() is.
        attrs = ""
        if raw.endswith("]") and "[" in raw:
            raw, _, rest = raw.partition("[")
            attrs = rest[:-1]

        data["material"] = raw.split(":")[-1].upper()

        if parse:
            for pair in filter(None, attrs.split(",")):
                key, _, value = pair.partition("=")
                data[key] = value
        else:
            data["state"] = attrs

        return data

    def getBlocks(self, x1:int, y1:int, z1:int, x2:int, y2:int, z2:int) -> list:
        """A cuboid of blocks, as nested lists indexed [y][x][z].

        The order is the server's, and it is not the obvious one: FruitJuice
        walks the cuboid with Y outermost, then X, then Z. So the flat reply is
        a stack of horizontal slabs, each slab a set of rows running east, each
        row running south.

        This used to reshape into slabs of xSize * ySize, which is the right
        SIZE only when the cuboid happens to be as tall as it is deep. Any
        other shape silently came back scrambled -- every block was a real
        block from somewhere in the box, just not from where you thought, so
        nothing looked wrong until the answer was checked against a place
        somebody could actually stand.
        """
        blocks = self.conn.sendReceive(b"world.getBlocks", x1, y1, z1, x2, y2, z2)
        return reshape_blocks(blocks.split(","),
                              abs(x1 - x2) + 1, abs(y1 - y2) + 1, abs(z1 - z2) + 1)

    # DIRECTION: NORTH SOUTH EAST WEST
    # FACE: FLOOR, CEILING, WALL
    def setBlock(self, x:int, y:int, z:int, block:str,
                 direction:str=None, face:str=None) -> None:
        """Set a block (x,y,z,block,[direction],[face])

        direction is a facing such as "NORTH"; leave it out to let minecraft
        pick, which is almost always what you want. This used to default to
        "WEST", which forced every stair, furnace and chest to face west.

        Beds, doors and tall plants fill both of the blocks they occupy; the
        server handles that, so only give the position of the lower or foot half.
        """
        args = [x, y, z, block]
        if direction is not None:
            args.append(direction)
            if face is not None:
                args.append(face)
        self.conn.send(b"world.setBlock", *args)

    def setBlocks(self, x1:int, y1:int, z1:int, x2:int, y2:int, z2:int, block) -> None: 
        """Set a cuboid of blocks (x1,y1,z1,x2,y2,z2,id,[data])"""
        self.conn.send(b"world.setBlocks", x1, y1, z1, x2, y2, z2, block)

    def buildVoxels(self, voxels, block=None, palette=None, origin=None,
                    chunk:int=512, blocks_per_second:int=25000) -> int:
        """Place a lot of blocks at once. Returns the number of commands sent.

        This is the front door for every "real data -> blocks" example: a
        heightmap, a voxelised STL, a crystal lattice, a protein. All of them
        end up with a few hundred thousand coordinates, and sending one
        setBlock each is slow enough to be the whole experience.

        Instead the shape is split into maximal boxes and each box is filled
        with one world.setBlocks. Real data is mostly large uniform regions, so
        this usually turns hundreds of thousands of commands into thousands.

        `voxels` may be:

          - a 3D numpy array, where 0 is empty and any other value is a block.
            With `block=` given, every non-zero cell is that block. With
            `palette=` given, cell value i means palette[i - 1].
          - an iterable of (x, y, z), all placed as `block`.
          - an iterable of (x, y, z, material), each placed as its own material.

        `origin` is where the lowest corner lands, defaulting to the player's
        position, so a build appears where you are standing rather than at
        0,0,0. Coordinates are relative to it.

        Nothing here reads a reply: setBlock and setBlocks answer nothing, so
        the whole build is one-way and there is no round trip per block.

        `blocks_per_second` paces the send so the server can keep up. The
        server places blocks on its main thread -- the one running the game --
        and a build sent faster than it can absorb stalls that thread until
        Paper's watchdog concludes it has hung and stops the server.

        The default is deliberately modest, because the limit in practice is
        not the block writes but the CHUNK LOADING they force. Building into
        terrain the server has never generated makes the main thread block on
        generation, and a Raspberry Pi generating several hundred fresh chunks
        while also placing blocks is what the watchdog notices. Raise it freely
        on better hardware, or when building somewhere already explored; pass 0
        to send as fast as the socket allows.

        Two things help more than raising it: build where the world already
        exists, and build a big shape in pieces rather than all at once.
        """
        import numpy as np
        from . import voxel

        if isinstance(voxels, np.ndarray):
            array = voxels
            if array.ndim != 3:
                raise ValueError("a voxel array must be 3D (x, y, z), got %dD"
                                 % array.ndim)
            if palette is None:
                # Every non-zero cell is the same block, so flatten to labels of
                # 1 and let the single material stand in for the palette.
                array = (array != 0).astype(np.int32)
                pal = [None]
            else:
                array = array.astype(np.int32)
                pal = list(palette)
            offset = (0, 0, 0)
        else:
            array, pal, offset = voxel.to_array(voxels)

        if array.size == 0:
            return 0

        if origin is None:
            p = self.player.getTilePos()
            origin = (p.x, p.y, p.z)
        ox, oy, oz = (int(origin[0]) + offset[0],
                      int(origin[1]) + offset[1],
                      int(origin[2]) + offset[2])

        # Paced by BLOCKS, not by commands.
        #
        # The server does this work on its main thread, the one that also runs
        # the game. One world.setBlocks filling a 10,000-block cuboid costs it
        # far more than one filling ten, so counting commands measures the
        # wrong thing entirely.
        #
        # Sending 768,000 blocks as fast as the socket would take them -- 1.2
        # seconds -- stalled the main thread long enough for Paper's watchdog
        # to decide the server had hung, and it killed it. Not a hypothetical:
        # that is how this limit came to be here.
        #
        # blocks_per_second=0 removes the limit, for a server that can take it.
        budget = blocks_per_second
        sent = 0
        placed = 0
        batch = []
        started = time.time()

        for name, args in voxel.commands_for(array, pal, (ox, oy, oz), block):
            batch.append(self.conn.build(name, *args))
            if name == b"world.setBlocks":
                x1, y1, z1, x2, y2, z2 = args[:6]
                placed += (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)
            else:
                placed += 1

            if len(batch) >= chunk:
                self.conn.sendBatch(batch, chunk=chunk)
                sent += len(batch)
                batch = []
                if budget:
                    # How far ahead of the budget we are, and wait it out.
                    ahead = placed / float(budget) - (time.time() - started)
                    if ahead > 0:
                        time.sleep(ahead)

        if batch:
            self.conn.sendBatch(batch, chunk=chunk)
            sent += len(batch)

        return sent

    def getHeight(self, x:int, z:int) -> int:
        """Get the height of the world (x,z) => int"""
        return self.conn.sendReceive(b"world.getHeight", x, z)

    def getPlayerEntityIds(self) -> list:
        """Get the entity ids of the connected players => [id:int]"""
        ids = self.conn.sendReceive(b"world.getPlayerIds")
        return list(map(int, ids.split("|")))

    def postToChat(self, *msg) -> None:
        """Post a message to the game chat"""
        self.conn.send(b"chat.post", msg)
        
    # TODO：Modify into a py file to process sign
    def setSign(self, x:int, y:int, z:int, signType:str, signDir:int, line1:str="", line2:str="", line3:str="", line4:str="") -> None:
        minecraftSignsType = ["SPRUCE_SIGN","ACACIA_SIGN","BIRCH_SIGN","DARK_OAK_SIGN","JUNGLE_SIGN","OAK_SIGN"]
        
        # ["SPRUCE_WALL_SIGN","ACACIA_WALL_SIGN","BIRCH_WALL_SIGN","DARK_OAK_WALL_SIGN","JUNGLE_WALL_SIGN","OAK_WALL_SIGN"]
        minecraftSignsDir = {0:'SOUTH',
                             1:'SOUTH_SOUTH_WEST',
                             2:'SOUTH_WEST',
                             3:'WEST_SOUTH_WEST',
                             4:'WEST',
                             5:'WEST_NORTH_WEST',
                             6:'NORTH_WEST',
                             7:'NORTH_NORTH_WEST',
                             8:'NORTH',
                             9:'NORTH_NORTH_EAST',
                             10:'NORTH_EAST',
                             11:'EAST_NORTH_EAST',
                             12:'EAST',
                             13:'EAST_SOUTH_EAST',
                             14:'SOUTH_EAST',
                             15:'SOUTH_SOUTH_EAST'
                             }
        
        if type(signDir) == int:
            if 0 <= signDir < 16:
                signDir = minecraftSignsDir.get(signDir)
        elif type(signDir) == str:
            for k,v in minecraftSignsDir.items():
                if signDir == v:
                    break
            else:
                signDir = minecraftSignsDir.get(0)
            
        signType = signType.upper()
        if signType not in minecraftSignsType: raise Exception("Sign name error")
        self.conn.send(b"world.setSign", x, y, z , signType, signDir, line1 ,line2 ,line3 ,line4)
    
    def setWallSign(self, x:int, y:int, z:int, signType:str, signDir:int, line1="",line2="",line3="",line4="") -> None:
        minecraftSignsType = ["SPRUCE_WALL_SIGN","ACACIA_WALL_SIGN","BIRCH_WALL_SIGN","DARK_OAK_WALL_SIGN","JUNGLE_WALL_SIGN","OAK_WALL_SIGN"]
        
        minecraftSignsDir = {0:'SOUTH',
                             1:'WEST',
                             2:'NORTH',
                             3:'EAST'}
        
        if type(signDir) == int:
            if 0 <= signDir < 4:
                signDir = minecraftSignsDir.get(signDir)
        elif type(signDir) == str:
            for k,v in minecraftSignsDir.items():
                if signDir == v:
                    break
            else:
                signDir = minecraftSignsDir.get(0)
            
        signType = signType.upper()
        if signType not in minecraftSignsType: raise Exception("Sign name error")
        self.conn.send(b"world.setWallSign", x, y, z , signType, signDir, line1 ,line2 ,line3 ,line4)
        
    def spawnEntity(self, x:int, y:int, z:int, entityID:int) -> int:
        """Spawn entity (x,y,z,id,[data])"""
        return int(self.conn.sendReceive(b"world.spawnEntity", x, y, z, entityID))
    
    def createExplosion(self, x:int, y:int, z:int, power:int=4) -> None:
        self.conn.send(b"world.createExplosion", x, y, z, power)

    def getPlayerEntityId(self, name:str) -> int:
        """Get the entity id of the named player => [id:int]"""
        return int(self.conn.sendReceive(b"world.getPlayerId", name))

    def setting(self, setting, status):
        """Set a world setting (setting, status). keys: world_immutable, nametags_visible"""
        self.conn.send(b"world.setting", setting, 1 if bool(status) else 0)

    @staticmethod
    def create(address = "localhost", port = 4711, playerName = ""):
        #return Minecraft(Connection(address, port))


        log("Running Python version:"+sys.version)
        conn=Connection(address, port)
        playerId = []
        if playerName != "":
           playerId = int(conn.sendReceive(b"world.getPlayerId", playerName))
           log("get {} playerid={}".format(playerName, playerId))

        return Minecraft(conn,playerId)

if __name__ == "__main__":
    mc = Minecraft.create()
    mc.postToChat("Hello, Minecraft!")
