"""Coord and Vec3D.

Every case here is a bug that shipped. They are cheap to keep.
"""
import math

import pytest

from pyncraft.coord import Coord, Vec3D


def test_accepts_three_numbers_or_one_iterable():
    assert list(Coord(1, 2, 3)) == [1, 2, 3]
    assert list(Coord([1, 2, 3])) == [1, 2, 3]
    assert list(Coord((1, 2, 3))) == [1, 2, 3]


def test_rejects_the_wrong_number_of_coordinates():
    with pytest.raises(ValueError):
        Coord([1, 2])
    with pytest.raises(TypeError):
        Coord("x", 2, 3)


def test_stores_floats_so_a_later_fractional_assignment_is_not_truncated():
    # Coord(1,2,3) used to be an int array, so c.x = 1.5 silently became 1 --
    # and player positions are fractional.
    c = Coord(1, 2, 3)
    c.x = 1.5
    assert c.x == 1.5


def test_adjust_rejects_an_unknown_axis():
    # dict.get returned None for a typo and coord[None] += delta broadcasts, so
    # adjust("w", 5) used to move all three axes instead of raising.
    c = Coord(10, 20, 30)
    assert list(c.adjust("y", 5)) == [10, 25, 30]
    with pytest.raises(ValueError):
        c.adjust("w", 5)


def test_adjust_does_not_mutate_the_original():
    c = Coord(1, 1, 1)
    c.adjust("x", 10)
    assert c.x == 1


def test_block_floors_including_negatives():
    assert list(Coord(1.7, 2.9, -0.3).block()) == [1, 2, -1]


def test_distance_and_direction():
    assert Coord(0, 0, 0).distance(Coord(3, 4, 0)) == 5.0
    assert list(Coord(0, 0, 0).direction(Coord(0, 0, 10))) == [0.0, 0.0, 1.0]


def test_coplane_returns_a_bool_and_vec3d_reports_the_plane():
    # Coord.coplane was annotated -> bool but returned Vec3D.coplane's string.
    assert Coord(0, 0, 0).coplane(Coord(5, 0, 7)) is True
    assert Coord(0, 0, 0).coplane(Coord(5, 3, 7)) is False
    assert Vec3D(Coord(0, 0, 0), Coord(5, 0, 7)).coplane() == "y"


@pytest.mark.parametrize("target,expected", [
    ((0, 0, -10), "north"),
    ((10, 0, 0), "east"),
    ((0, 0, 10), "south"),
    ((-10, 0, 0), "west"),
])
def test_cardinal_direction(target, expected):
    assert Coord(0, 0, 0).cardinal_direction(Coord(*target)) == expected


def test_cardinal_direction_unrounded_does_not_raise():
    # `radians` was only assigned in the rounded branch, so compass_points=0
    # raised NameError.
    origin = Coord(0, 0, 0)
    assert origin.cardinal_direction(Coord(1, 0, -1),
                                     returns="degrees", compass_points=0) == pytest.approx(45.0)
    assert origin.cardinal_direction(Coord(1, 0, -1),
                                     returns="radians", compass_points=0) == pytest.approx(math.pi / 4)


def test_cardinal_direction_rejects_a_bad_returns_value():
    with pytest.raises(ValueError):
        Coord(0, 0, 0).cardinal_direction(Coord(1, 0, 0), returns="bogus")


def test_straight_up_is_indeterminate():
    with pytest.raises(ValueError):
        Coord(0, 0, 0).cardinal_direction(Coord(0, 10, 0))


def test_vec3d_rotation():
    v = Vec3D(Coord(1, 0, 0))
    v.rotateLeft()
    assert [v.x, v.y, v.z] == [0, 0, -1]
    v.rotateRight()
    assert [v.x, v.y, v.z] == [1, 0, 0]
