"""Street names that fit on a sign.

A Minecraft sign line holds about fifteen characters. American street names are
mostly one long word and a suffix, so abbreviating the suffix the way the post
office does buys back the room while leaving the name recognisable.

A real house sign does not carry the street name at all. These do, because a
build is a map you are standing inside and the street is what tells you where
you are.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

ft = pytest.importorskip("fetch_terrain")

LIMIT = 15


@pytest.mark.parametrize("full,expected", [
    ("Court Street", "Court St"),
    ("Park Street", "Park St"),
    ("Winthrop Circle", "Winthrop Cir"),
    ("Auburn Court", "Auburn Ct"),
    ("Hillside Avenue", "Hillside Ave"),
    ("Grove Road", "Grove Rd"),
])
def test_the_suffix_is_abbreviated(full, expected):
    assert ft.short_street(full) == expected


def test_a_leading_compass_word_is_abbreviated_too():
    assert ft.short_street("West Main Street") == "W Main St"
    assert ft.short_street("North Border Road") == "N Border Rd"


def test_a_compass_word_that_is_the_name_survives():
    """"West Street" is a street called West, not a westerly street."""
    assert ft.short_street("West Street") == "West St"


@pytest.mark.parametrize("full", [
    "Court Street", "Massachusetts Avenue", "Commonwealth Avenue",
    "Very Long Sounding Boulevard Name", "Rue de la Paix",
])
def test_everything_fits_on_a_sign(full):
    assert len(ft.short_street(full)) <= LIMIT


def test_a_long_name_drops_the_suffix_rather_than_cutting_a_word():
    """"Massachusetts" beats "Massachusetts ." for something to read."""
    out = ft.short_street("Massachusetts Avenue")
    assert out == "Massachusetts"
    assert not out.endswith("."), "a cut-off word is worse than a missing suffix"


def test_nothing_in_gives_nothing_out():
    assert ft.short_street("") == ""
    assert ft.short_street(None) == ""


def test_an_unknown_suffix_is_left_alone():
    # Not every street ends in something abbreviable.
    assert ft.short_street("Broadway") == "Broadway"
    assert ft.short_street("The Fenway") == "The Fenway"
