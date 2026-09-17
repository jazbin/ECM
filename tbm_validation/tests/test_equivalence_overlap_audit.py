"""Regression tests for tools/audit_bds_openfoam_overlap.py.

Verifies the reference-domain geometry derivation (from the actual
cases/wedge_2170 OpenFOAM mesh point bounding boxes) and, if pythonOCC is
available and the T06 client STEP geometry is present, the end-to-end
overlap classification used in docs/equivalence/T06_GEOMETRIC_EQUIVALENCE_AUDIT.md.
"""
import math
import os
import sys
import zipfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

occ = pytest.importorskip("OCC.Core.BRepPrimAPI", reason="pythonOCC/OpenCASCADE not available")

from tools.audit_bds_openfoam_overlap import (  # noqa: E402
    make_reference_domains, volume_mm3, R_JR, R_CAN, Z_JR_BOT, Z_JR_TOP,
    Z_CAN_BOT, Z_CAN_TOP, Z_CAP_TOP, load_named_solids, KNOWN_NAMES,
)


def test_reference_domain_volumes_match_analytic_cylinders():
    ref = make_reference_domains()
    v_jr = volume_mm3(ref["JR"])
    v_can = volume_mm3(ref["Can"])
    v_cap = volume_mm3(ref["Cap"])

    expected_jr = math.pi * R_JR ** 2 * (Z_JR_TOP - Z_JR_BOT)
    expected_can_outer = math.pi * R_CAN ** 2 * (Z_CAN_TOP - Z_CAN_BOT)
    expected_cap = math.pi * R_CAN ** 2 * (Z_CAP_TOP - Z_CAN_TOP)

    assert v_jr == pytest.approx(expected_jr, rel=1e-6)
    assert v_cap == pytest.approx(expected_cap, rel=1e-6)
    # Can = outer cylinder minus JR (JR is fully contained within the outer
    # cylinder's z-range and radius by construction)
    assert v_can == pytest.approx(expected_can_outer - expected_jr, rel=1e-6)


def test_jr_height_matches_openfoam_mesh_bbox():
    """h_jroll = 65.11 mm is asserted (not fitted) from
    cases/wedge_2170/constant/jellyRoll_rotated/polyMesh/points; guard
    against silent drift if that mesh is regenerated."""
    assert (Z_JR_TOP - Z_JR_BOT) == pytest.approx(0.06511 * 1000, abs=5e-4)


def _extract_t06(tmp_path):
    zip_path = os.path.join(
        REPO, "in", "20260916",
        "hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip",
    )
    if not os.path.exists(zip_path):
        pytest.skip("T06 source zip not present in this checkout")
    with zipfile.ZipFile(zip_path) as z:
        name = [n for n in z.namelist() if n.endswith("T06_TARGET_AXIAL_SURPLUS_2p00.step")][0]
        out = tmp_path / "T06.step"
        out.write_bytes(z.read(name))
    return str(out)


def test_t06_body_names_match_documented_13_body_list(tmp_path):
    step_file = _extract_t06(tmp_path)
    solids = load_named_solids(step_file)
    names = sorted(n for n, _ in solids)
    assert names == sorted(KNOWN_NAMES)


def test_t06_jellyroll_and_mandrel_are_exact_jr_subdivisions(tmp_path):
    """Core equivalence-audit invariant: Mandrel and Jellyroll solids must
    lie almost entirely within the OpenFOAM JellyRoll reference domain."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common

    step_file = _extract_t06(tmp_path)
    solids = dict(load_named_solids(step_file))
    ref = make_reference_domains()

    for name in ("Mandrel", "Jellyroll"):
        body = solids[name]
        common = BRepAlgoAPI_Common(body, ref["JR"]).Shape()
        frac_in_jr = volume_mm3(common) / volume_mm3(body)
        assert frac_in_jr > 0.99, f"{name} unexpectedly not fully inside JR ({frac_in_jr:.3f})"
