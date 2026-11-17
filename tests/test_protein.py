"""PDB files are punch cards, and that is the whole difficulty.

The format is fixed columns, seventy years old, and the fields are not
separated by anything. An atom named "CA" in columns 13-16 is the alpha carbon
that every amino acid has in the middle of it; an atom whose ELEMENT is "CA",
in columns 77-78, is a calcium ion. Split the line on whitespace and those two
become the same thing, and the chain trace grows a spur out to wherever the
calcium happens to be sitting.

So everything here is about reading the right columns, and about the records
that decide what is drawn: HELIX and SHEET, which are not deduced from the
geometry but written down by whoever solved the structure.

No network. The PDB text is inline.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

protein = pytest.importorskip("protein")


# Columns matter, so this is laid out by column and not by eye.
#          1         2         3         4         5         6         7
# 1234567890123456789012345678901234567890123456789012345678901234567890123456789
SAMPLE = """\
TITLE     A SMALL INVENTED PROTEIN
HELIX    1   1 ALA A    2  ALA A    4  1                                   3
SHEET    1   A 2 ALA A   6  ALA A   7  0
ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N
ATOM      2  CA  ALA A   1      11.000  10.000  10.000  1.00  0.00           C
ATOM      3  CA  ALA A   2      14.800  10.000  10.000  1.00  0.00           C
ATOM      4  CA  ALA A   3      18.600  10.000  10.000  1.00  0.00           C
ATOM      5  CA  ALA A   4      22.400  10.000  10.000  1.00  0.00           C
ATOM      6  CA  ALA A   6      26.200  10.000  10.000  1.00  0.00           C
ATOM      7  CA  ALA A   7      30.000  10.000  10.000  1.00  0.00           C
ATOM      8  CA BALA A   8      99.000  99.000  99.000  0.50  0.00           C
ATOM      9  CA  ALA B   1      10.000  20.000  10.000  1.00  0.00           C
ATOM     10  CA  ALA B   2      13.800  20.000  10.000  1.00  0.00           C
HETATM   11 CA    CA A 101      50.000  50.000  50.000  1.00  0.00          CA
HETATM   12  O   HOH A 201      60.000  60.000  60.000  1.00  0.00           O
HETATM   13 FE   HEM A 301      15.000  15.000  15.000  1.00  0.00          FE
END
"""

NMR = """\
MODEL        1
ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C
ENDMDL
MODEL        2
ATOM      2  CA  ALA A   1      50.000  50.000  50.000  1.00  0.00           C
ENDMDL
"""


def _parse(**kw):
    return protein.parse(SAMPLE, **kw)


# ── reading the columns ────────────────────────────────────────────────────

def test_an_alpha_carbon_is_not_a_calcium_ion():
    """The one that would quietly ruin the picture.

    Atom NAME "CA" in columns 13-16 is the alpha carbon of an amino acid.
    ELEMENT "CA" in columns 77-78 is calcium. Both read as "CA" if the line is
    split on spaces, and the calcium then gets threaded into the chain trace.
    """
    atoms, _, _, _ = _parse()
    calciums = [a for a in atoms if a["element"] == "CA"]
    assert len(calciums) == 1
    assert calciums[0]["resname"] == "CA" and calciums[0]["hetatm"]

    chains = protein.backbone(atoms)
    traced = [(a["chain"], a["resseq"]) for ch in chains for a in chains[ch]]
    assert ("A", 101) not in traced, "the calcium ion got into the backbone"


def test_the_title_and_the_coordinates_come_out():
    atoms, _, _, title = _parse()
    assert title == "A SMALL INVENTED PROTEIN"
    first = atoms[0]
    assert first["name"] == "N" and first["element"] == "N"
    assert first["xyz"] == (10.0, 10.0, 10.0)
    assert first["chain"] == "A" and first["resseq"] == 1


def test_helix_and_sheet_ranges_are_inclusive():
    """HELIX 2-4 means 2, 3 and 4 are helix -- not 2 and 3."""
    _, helix, sheet, _ = _parse()
    assert helix == {("A", 2), ("A", 3), ("A", 4)}
    assert sheet == {("A", 6), ("A", 7)}


def test_only_one_conformer_of_a_disordered_side_chain():
    """altLoc B is a second position for the same atom, not another atom."""
    atoms, _, _, _ = _parse()
    assert not any(a["resseq"] == 8 for a in atoms)


def test_water_is_dropped_and_ligands_are_kept():
    atoms, _, _, _ = _parse()
    assert not any(a["resname"] == "HOH" for a in atoms)
    assert any(a["element"] == "FE" for a in atoms), "the heme iron should stay"

    with_water, _, _, _ = _parse(waters=True)
    assert any(a["resname"] == "HOH" for a in with_water)

    no_lig, _, _, _ = _parse(ligands=False)
    assert not any(a["hetatm"] for a in no_lig)


def test_only_the_first_model_of_an_nmr_structure():
    """Twenty poses of one molecule drawn at once is a haystack."""
    atoms, _, _, _ = protein.parse(NMR)
    assert len(atoms) == 1
    assert atoms[0]["xyz"] == (0.0, 0.0, 0.0)


# ── the chain ──────────────────────────────────────────────────────────────

def test_the_backbone_is_split_by_chain_and_in_sequence():
    atoms, _, _, _ = _parse()
    chains = protein.backbone(atoms)
    assert sorted(chains) == ["A", "B"]
    assert [a["resseq"] for a in chains["A"]] == [1, 2, 3, 4, 6, 7]
    assert [a["resseq"] for a in chains["B"]] == [1, 2]


def test_the_chain_is_joined_up_with_no_gaps():
    """Blocks meeting only at an edge read as a broken chain."""
    for a, b in (((0, 0, 0), (5, 3, 2)), ((4, 4, 4), (0, 0, 0)),
                 ((0, 0, 0), (0, 0, 7)), ((2, 2, 2), (2, 2, 2))):
        pts = protein.connected(a, b)
        assert pts[0] == a and pts[-1] == b
        for p, q in zip(pts, pts[1:]):
            assert sum(abs(p[i] - q[i]) for i in range(3)) == 1


def test_a_ball_is_round_and_the_right_size():
    for r in (0.5, 1.6, 3.0, 5.0):
        off = protein.ball(r)
        d = np.sqrt((off ** 2).sum(axis=1))
        assert d.max() <= r + 1.0
        assert (0, 0, 0) in {tuple(p) for p in off}


def test_scaling_keeps_the_shape_and_fills_the_size_asked_for():
    atoms = [{"xyz": (0.0, 0.0, 0.0)}, {"xyz": (10.0, 5.0, 2.0)}]
    grid, scale, shape = protein.to_blocks(atoms, 100)
    assert grid.min() == 0
    assert max(shape) == 101                      # 0..100 inclusive
    # proportions preserved: 10 : 5 : 2 stays 10 : 5 : 2
    span = grid.max(axis=0) - grid.min(axis=0)
    assert span[0] == pytest.approx(2 * span[1], abs=1)
    assert span[1] == pytest.approx(2.5 * span[2], abs=1)


# ── what gets built ────────────────────────────────────────────────────────

def test_a_backbone_is_coloured_by_secondary_structure():
    atoms, helix, sheet, _ = _parse()
    world, palette, scale, n = protein.build_backbone(
        atoms, helix, sheet, size=60, thickness=1.5, colour_by="structure")
    assert n == 8                                  # six in chain A, two in B
    assert set(palette) <= set(protein.STRUCTURE_BLOCKS.values())
    assert "RED_CONCRETE" in palette and "YELLOW_CONCRETE" in palette
    assert int((world != 0).sum()) > 0


def test_spacefill_is_coloured_by_element():
    atoms, _, _, _ = _parse()
    world, palette, scale, n = protein.build_spacefill(
        atoms, size=40, colour_by="element", chains_present=["A", "B"])
    assert n == len(atoms)
    assert protein.ELEMENT_BLOCKS["N"] in palette     # the nitrogen
    assert protein.ELEMENT_BLOCKS["FE"] in palette    # the heme iron


def test_nothing_built_here_falls_down():
    """These hang in mid-air, so a gravity-affected block would rain down."""
    falling = {"SAND", "RED_SAND", "GRAVEL"}
    for name in list(protein.ELEMENT_BLOCKS.values()) + \
            list(protein.STRUCTURE_BLOCKS.values()) + \
            protein.RAINBOW + protein.CHAIN_BLOCKS + [protein.DEFAULT_ELEMENT]:
        assert name not in falling
        assert not name.endswith("_CONCRETE_POWDER"), name


def test_every_element_that_has_a_colour_has_a_radius():
    for element in protein.ELEMENT_BLOCKS:
        assert element in protein.VDW, element
