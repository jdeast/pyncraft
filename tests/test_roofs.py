"""Roof shapes, from OSM's roof:shape tag.

A street of flat-topped boxes does not look like a street of houses, and
roof:shape is the tag that fixes it. It is absent around Roberts Elementary --
nobody there has mapped one -- which is exactly why it is worth supporting:
the point is that any child can add it and see their own street change.

Only the shapes that alter the silhouette are told apart. A gambrel and a
mansard are genuinely different roofs and, at one block to the metre, look the
same, so they borrow the nearest shape rather than claiming a precision the
grid cannot show.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

build_town = pytest.importorskip("build_town")


def footprint(rows=9, cols=13, pad=2):
    m = np.zeros((rows + 2 * pad, cols + 2 * pad), dtype=bool)
    m[pad:pad + rows, pad:pad + cols] = True
    return m, pad, rows, cols


def test_flat_is_flat():
    m, _, _, _ = footprint()
    assert build_town.roof_profile(m, "flat", 6).max() == 0


def test_no_peak_means_no_roof():
    m, _, _, _ = footprint()
    assert build_town.roof_profile(m, "gabled", 0).max() == 0


def test_nothing_is_built_outside_the_footprint():
    m, _, _, _ = footprint()
    for shape in ("gabled", "hipped", "pyramidal", "skillion", "dome"):
        p = build_town.roof_profile(m, shape, 5)
        assert not p[~m].any(), "%s spilled outside the footprint" % shape


def test_gabled_has_a_ridge_along_the_long_axis():
    """Flat along the ridge, a triangle across it. That is what makes it gabled."""
    m, pad, rows, cols = footprint(9, 13)
    p = build_town.roof_profile(m, "gabled", 6)
    along = p[pad + rows // 2, pad:pad + cols]
    across = p[pad:pad + rows, pad + cols // 2]
    assert len(set(along.tolist())) == 1, "the ridge should be level: %s" % along
    assert across[0] < across[len(across) // 2] > across[-1], (
        "it should rise to the ridge and fall away: %s" % across)
    assert across.max() == 6


def test_hipped_falls_away_on_all_four_sides():
    m, pad, rows, cols = footprint(9, 13)
    p = build_town.roof_profile(m, "hipped", 6)
    along = p[pad + rows // 2, pad:pad + cols]
    across = p[pad:pad + rows, pad + cols // 2]
    for cut, name in ((along, "along"), (across, "across")):
        assert cut[0] < cut.max() and cut[-1] < cut.max(), (
            "a hipped roof should slope at both ends %s: %s" % (name, cut))


def test_gabled_and_hipped_differ():
    """If these two came out the same the tag would be doing nothing."""
    m, _, _, _ = footprint(9, 13)
    g = build_town.roof_profile(m, "gabled", 6)
    h = build_town.roof_profile(m, "hipped", 6)
    assert not np.array_equal(g, h)


def test_skillion_is_one_slope():
    m, pad, rows, cols = footprint(9, 13)
    p = build_town.roof_profile(m, "skillion", 6)
    across = p[pad:pad + rows, pad + cols // 2]
    assert len(set(across.tolist())) == 1, (
        "a lean-to should not change across the slope: %s" % across)
    along = p[pad + rows // 2, pad:pad + cols]
    assert along[0] < along[-1], "it should rise steadily one way: %s" % along


def test_a_dome_is_rounder_than_a_pyramid():
    """Both peak in the middle; the dome should be fuller at the edges."""
    m, pad, rows, cols = footprint(11, 11)
    d = build_town.roof_profile(m, "dome", 6)
    p = build_town.roof_profile(m, "pyramidal", 6)
    assert d.sum() > p.sum(), "a dome should hold more volume than a cone"
    assert d.max() == p.max() == 6


@pytest.mark.parametrize("shape", ["gabled", "hipped", "pyramidal", "dome",
                                   "skillion", "gambrel", "mansard", "onion",
                                   "half-hipped", "round"])
def test_every_supported_shape_produces_something(shape):
    m, _, _, _ = footprint()
    p = build_town.roof_profile(m, shape, 5)
    assert p.max() > 0, "%s produced no roof at all" % shape
    assert p.max() <= 5, "%s overshot the peak" % shape


def test_an_unknown_shape_still_builds_a_roof():
    """A tag nobody anticipated must not crash the build."""
    m, _, _, _ = footprint()
    p = build_town.roof_profile(m, "something_nobody_has_thought_of", 5)
    assert p.max() > 0


def test_a_single_cell_footprint_is_handled():
    m = np.zeros((5, 5), dtype=bool)
    m[2, 2] = True
    for shape in ("gabled", "hipped", "dome", "skillion"):
        p = build_town.roof_profile(m, shape, 3)
        assert not p[~m].any()


def test_edge_distance_counts_inwards():
    m = np.zeros((7, 7), dtype=bool)
    m[1:6, 1:6] = True
    d = build_town.edge_distance(m)
    assert d[1, 1] == 1, "a corner is one step in"
    assert d[3, 3] == 3, "the middle of a 5x5 is three steps in"
    assert d[0, 0] == 0, "outside the shape is zero"
