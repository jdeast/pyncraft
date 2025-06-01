from typing import Callable, Iterable, Union, Optional

import numpy as np



class Coord(np.ndarray):
    """
    Implement 3D coordinates as a 3-element (x, y, z) numpy array subclass.

    This avoids having to reinvent the wheel for basic vector operations.
    You can pass in a Vec3, list, tuple, pd.Series or individual x, y, z values.
    They must be numeric (int or float).

    Parameters
    ----------
    x : int, float, Iterable
        The x coordinate or a 3-element iterable containing x, y, z coordinates.
        Positive x is east, negative x is west.
    y : int, float, None
        The y coordinate (vertical position). Positive y is up, negative y is 
        down. Unused if `x` is an iterable.
    z : int, float, None
        The z coordinate. Positive z is south, negative z is north. Unused if 
        `x` is an iterable.
    """

    __int_types__ = (int, np.int32, np.int64)
    __float_types__ = (float, np.float32, np.float64)
    __numeric__ = __int_types__ + __float_types__
    
    def __new__(cls, 
                x: Union[int, float, Iterable], 
                y: Union[int, float, None] = None, 
                z: Union[int, float, None] = None
    ):
        if isinstance(x, Iterable):
            x = [v for i, v in enumerate(x) if i < 4]
            if len(x) != 3:
                raise ValueError(f"Expected 3 coordinates, got {len(x)}: {x}")
            x, y, z = tuple(x)
        else:
            if not isinstance(x, cls.__numeric__):
                raise TypeError(f"x must be int or float, got {type(x)}: {x}")
            if not isinstance(y, cls.__numeric__):
                raise TypeError(f"y must be int or float, got {type(y)}: {y}")
            if not isinstance(z, cls.__numeric__):
                raise TypeError(f"z must be int or float, got {type(z)}: {z}")
        
        obj = np.asarray([x, y, z]).view(cls)
        return obj
    
    # accessor methods convert numpy int/float to Python int/float
    @property
    def x(self):
        return int(self[0]) if isinstance(self[0], self.__int_types__) else float(self[0])

    @x.setter
    def x(self, value):
        self[0] = value

    @property
    def y(self):
        return int(self[1]) if isinstance(self[1], self.__int_types__) else float(self[1])

    @y.setter
    def y(self, value):
        self[1] = value

    @property
    def z(self):
        return int(self[2]) if isinstance(self[2], self.__int_types__) else float(self[2])

    @z.setter
    def z(self, value):
        self[2] = value

    
    def adjust(self, axis: str, delta: Union[int, float]) -> 'Coord':
        """
        Copy Coord and adjust one axis (x, y or z) by delta
        """
        axis = {'x': 0, 'y': 1, 'z': 2}.get(axis.lower())
        coord = self.copy()
        coord[axis] += delta
        return coord


    def block(self, as_int: bool = True) -> 'Coord':
        """
        Get the whole-number block coordinates as Coord object By Flooring.

        If as_int is True, returns the block coordinate as an integer.
        Otherwise, float.
        """
        block = np.floor(self)
        if as_int:
            block = block.astype(int)
        return block
    
    
    def midblock(self) -> 'Coord':
        return self.block(as_int=False) + Coord(0.5, 0.0, 0.5)
    

    def coplane(self, c2: 'Coord') -> bool:
        """
        Check if second coordinate is in the same plane.
        """

        return Vec3D(self, c2).coplane()
    

    def direction(self, c2: 'Coord') -> 'Vec3D':
        """
        Get the unit vector from c1 to c2 (normalized to length 1).
        """
        return Vec3D(self, c2).direction()
    
    
    def cardinal_direction(self, c2: 'Coord', *args, **kwargs) -> Union[str, 'Coord']:
        """
        Get the Cardinal Direction of a Second Coordinate.

        See help for Vec3D.cardinal_direction() for details.
        """
        return Vec3D(self, c2).cardinal_direction(*args, **kwargs)
    

    def distance(self, c2: 'Coord') -> float:
        """
        Calculate the distance between two coordinates.
        """
        return float(np.sqrt(((self - c2) ** 2).sum()))
        


class Vec3D(Coord):
    """
    A 3D vector class that takes one or two Coord objects as input.
    """
    
    def __init__(self, c1: Coord, c2: Coord = None):

        v = c1 if c2 is None else c2 - c1
        
        self.x = v.x
        self.y = v.y
        self.z = v.z


    def rotateLeft(self):  self.x, self.z = self.z, -self.x

    def rotateRight(self): self.x, self.z = -self.z, self.x
    

    def is_unit(self):
        """Test if the vector is a unit vector (normalized to length 1)."""
        return np.isclose(np.linalg.norm(self), 1.0)
    

    def direction(self) -> Coord:
        """
        Get the unit vector from c1 to c2 (normalized to length 1).
        """
        return (self) / np.linalg.norm(self)
    

    def coplane(self, by_block: bool = True) -> bool:
        """
        Check if second coordinate is in the same plane.
        """

        if by_block:
            pass

        plane = ''
        if np.isclose(self.x, 0.0):
            plane += 'x'
        if np.isclose(self.y, 0.0):
            plane += 'y'
        if np.isclose(self.z, 0.0):
            plane += 'z'

        return plane
    
    
    def cardinal_direction(
            self, 
            returns: str = 'string',
            compass_points: int = 4
        ) -> Union[str, int, Coord]:
        """
        Get the Cardinal Direction Of The Vector In The XY Plane.

        Uses the x and z components only, and returns the closest direction
        based on the number fo compass points.  Direction may be returned 
        as a string ("north"), minecraft rotation value (0-15), degrees (0-360),
        radians (0-2pi), or a Vec3D/Coord unit vector with y==0.

        Note that when there is a tie (like x=1 and z=-1 with 4 compass points),
        I'm not doing anything specific to resolve (north or east in this case).
        Could return 'indeteminate', None/np.nan or raise an exception.  Also
        leaving it up to the user whether to convert Coords to integer.

        Parameters
        ----------
        returns : str
            The type of return value. Can be 'string', 'rotation', 'coord', or 
            'degrees'. Default is 'string'.
        compass_points : int
            The number of compass points to use for the direction. 
            Default is 4 (north, east, south, west). If set to 8, it will also
            return northeast, southeast, southwest, and northwest.  If set
            to 16, it will return all 16 compass points ('northnortheast', 
            'northeast', 'eastnortheast', 'east', etc).  
        
        Returns
        -------
        Union[str, int, Coord]:
            If returns is string: 'north', 'south', 'east', 'west',.
        """
        ok = {'string', 'rotation', 'coord', 'degrees', 'radians'} 
        invalid = {returns} - ok
        if invalid:
            raise ValueError(
                'Invalid returns argument "{returns}"; must be one of:\n   '
                + ', '.join(list(ok)))
        
        if self.x == 0 and self.z == 0:
            raise ValueError('Vector point straight up or down; indeterminate.')

        # drop the y component and normalize the xz vector (z -> y)
        xz = np.delete(self, 1)
        xz = xz / np.linalg.norm(xz)

        # atan2 returns angle from x-axis (east), so swap arguments and invert z
        # calculate fraction of a turn [0, 1) from North = 0 degrees
        frac360 = (np.arctan2(xz.x, -xz.y) / (np.pi * 2)) % 1.0

        bearings = ['north', 'northnortheast', 'northeast', 'eastnortheast', 
                    'east', 'eastsoutheast', 'southeast', 'southsoutheast', 
                    'south', 'southsouthwest', 'southwest', 'westsouthwest',
                    'west', 'westnorthwest', 'northwest', 'northnorthwest',
                    'north']

        if compass_points > 0:
            # convert to a rotation value, rounded to the nearest compass point
            rotation = int(
                np.round(frac360 * compass_points) * 16 / compass_points)

            if returns == 'rotation':
                return rotation
            elif returns == 'degrees':
                return rotation * 360 / 16
            elif returns == 'string':
                return bearings[rotation]
            else: 
                radians = rotation * 2 * np.pi / 16
                if returns == 'radians':
                    return radians
                else:
                    # rounded unit vector in the xz plane
                    coord = Coord(np.sin(radians), 0, -np.cos(radians))
                    if compass_points == 4:
                        coord = coord.astype(int)
                    return coord
        elif returns in ('string', 'rotation'):
            raise ValueError(
                f'Must set compass_points > 0 for returns "string" or "rotation"')
        else:
            # return results without rounding
            if returns == 'degrees':
                return frac360 * 360
            else:
                if returns == 'radians':
                    return radians
                else:
                    return Coord(np.sin(radians), 0,-np.cos(radians))