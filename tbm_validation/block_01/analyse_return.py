#!/usr/bin/env python3
"""
BLOCK 01 — Post-return analysis.

Run after the STAR session has been completed and RETURN/ has been copied back.

Usage:
    python3 analyse_return.py [--return-dir RETURN] [--out-dir analysis_output]
    python3 analyse_return.py --run-tests            # unit tests (no STAR results needed)
    python3 analyse_return.py --regression-test T06_STEP.step  # verify extractor vs T06

Requires: pythonOCC (OCP) — available in the project conda environment.
The same B-Rep tooling used for the T06 audit (step_audit.py) is extended
here to extract all radial and axial dimensions and determine mapping outcomes.

Outputs:
    analysis_output/geometry_summary.csv   -- per-case dimensions
    analysis_output/field_deltas.csv       -- Δ from T06 baseline per case
    analysis_output/mapping_report.txt     -- RAD-A/B/C mapping conclusions
    analysis_output/production_report.txt  -- PROD candidate evaluation
    analysis_output/BLOCK_01_DECISION.txt  -- one of four outcome codes

Regression test (--regression-test):
    Runs extract_step_geometry() against an existing T06 STEP file and verifies:
      JR OD      = 17.880992 mm  (±0.001 mm)
      Can ID     = 18.000000 mm  (±0.001 mm)
      Can OD     ≈ 20.900000 mm  (±0.050 mm)
      radial gap = 0.059504 mm   (±0.005 mm)
      body_count = 13

    T06 STEP location: extracted from
      in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip
      → hp2170NCA.../H04_POS_SURPLUS_2p00.step

Body identification: uses root order (index 1..13) which is confirmed correct for
T06 geometry via T06_GEOMETRIC_EQUIVALENCE_AUDIT.md. STEP PRODUCT name parsing
is a planned future improvement for robustness against different STAR export orders.
"""
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# T06 STEP-confirmed reference values (from T06_GEOMETRIC_EQUIVALENCE_AUDIT.md)
T06_REF = {
    "jellyroll_od_mm":       17.880992,
    "can_id_mm":             18.000000,
    "can_od_mm":             20.900000,
    "can_wall_thickness_mm":  1.450000,
    "jr_can_radial_gap_mm":   0.059504,
}

# Production geometry targets (from OPENFOAM_ECM_EQUIVALENCE_TARGET.md)
PROD_TARGET = {
    "can_od_mm":   21.0900,
    "can_id_mm":   20.6274,
    "jr_od_mm":    20.6274,
    "wall_mm":      0.2313,
    "gap_mm":       0.0000,
}

# Per-quantity tolerances for "changed" detection and target matching (mm)
CHANGE_TOL = 0.05

# Tight per-quantity tolerances for RADIAL_GEOMETRY_CLOSED:
#   A blanket ±0.10 mm is too loose — it would accept ~0.4 mm error in wall thickness.
TOL_CAN_OD  = 0.05   # Can OD must be within ±0.05 mm of 21.09
TOL_CAN_ID  = 0.05   # Can ID must be within ±0.05 mm of 20.6274
TOL_JR_OD   = 0.05   # JR OD must be within ±0.05 mm of 20.6274
TOL_GAP_MAX = 0.03   # radial gap must be ≤ 0.03 mm (essentially zero / contact)
TOL_WALL_MIN = 0.10  # can wall must exceed this (structural sanity check)

# Expected field values for each case (from generate_block.py BLOCK spec)
BLOCK_SPECS = {
    "CTRL_T06_S":       {"m_dintDiameter": 20.9,   "m_dRepCanXY": 18.0,    "m_dJR": 17.9,   "role": "ctrl"},
    "RA_19P0":          {"m_dintDiameter": 19.0,   "m_dRepCanXY": 18.0,    "m_dJR": 17.9,   "role": "rad_a"},
    "RA_20P0":          {"m_dintDiameter": 20.0,   "m_dRepCanXY": 18.0,    "m_dJR": 17.9,   "role": "rad_a"},
    "RA_20P5":          {"m_dintDiameter": 20.5,   "m_dRepCanXY": 18.0,    "m_dJR": 17.9,   "role": "rad_a"},
    "RA_21P09":         {"m_dintDiameter": 21.09,  "m_dRepCanXY": 18.0,    "m_dJR": 17.9,   "role": "rad_a"},
    "RB_19P0":          {"m_dintDiameter": 20.9,   "m_dRepCanXY": 19.0,    "m_dJR": 17.9,   "role": "rad_b"},
    "RB_20P0":          {"m_dintDiameter": 20.9,   "m_dRepCanXY": 20.0,    "m_dJR": 17.9,   "role": "rad_b"},
    "RB_20P6274":       {"m_dintDiameter": 20.9,   "m_dRepCanXY": 20.6274, "m_dJR": 17.9,   "role": "rad_b"},
    "RB_21P0":          {"m_dintDiameter": 20.9,   "m_dRepCanXY": 21.0,    "m_dJR": 17.9,   "role": "rad_b"},
    "CTRL_T06_M":       {"m_dintDiameter": 20.9,   "m_dRepCanXY": 18.0,    "m_dJR": 17.9,   "role": "ctrl"},
    "RC_17P5":          {"m_dintDiameter": 20.9,   "m_dRepCanXY": 18.0,    "m_dJR": 17.5,   "role": "rad_c"},
    "RC_17P0":          {"m_dintDiameter": 20.9,   "m_dRepCanXY": 18.0,    "m_dJR": 17.0,   "role": "rad_c"},
    "RC_16P0":          {"m_dintDiameter": 20.9,   "m_dRepCanXY": 18.0,    "m_dJR": 16.0,   "role": "rad_c"},
    "PROD_A_D1_GAP":    {"m_dintDiameter": 21.09,  "m_dRepCanXY": 20.6274, "m_dJR": 20.519, "role": "prod", "hyp": "A"},
    "PROD_A_D1_SLIM":   {"m_dintDiameter": 21.09,  "m_dRepCanXY": 20.6274, "m_dJR": 20.569, "role": "prod", "hyp": "A"},
    "PROD_A_CONT_LIT":  {"m_dintDiameter": 21.09,  "m_dRepCanXY": 20.6274, "m_dJR": 20.6274,"role": "prod", "hyp": "A"},
    "PROD_A_CONT_COMP": {"m_dintDiameter": 21.09,  "m_dRepCanXY": 20.6274, "m_dJR": 20.6464,"role": "prod", "hyp": "A"},
    "PROD_B_D1":        {"m_dintDiameter": 20.6274,"m_dRepCanXY": 21.09,   "m_dJR": 20.519, "role": "prod", "hyp": "B"},
    "PROD_B_CONT_LIT":  {"m_dintDiameter": 20.6274,"m_dRepCanXY": 21.09,   "m_dJR": 20.6274,"role": "prod", "hyp": "B"},
    "CTRL_T06_E":       {"m_dintDiameter": 20.9,   "m_dRepCanXY": 18.0,    "m_dJR": 17.9,   "role": "ctrl"},
}

PROD_CASES = [
    "PROD_A_D1_GAP", "PROD_A_D1_SLIM", "PROD_A_CONT_LIT", "PROD_A_CONT_COMP",
    "PROD_B_D1", "PROD_B_CONT_LIT",
]

# ── STEP geometry extractor (requires pythonOCC / OCP) ──────────────────────

BODY_NAMES = [
    "Mandrel", "Jellyroll", "Can",
    "+Ve Tab Root", "+Ve Tab Stem", "-Ve Tab Root", "-Ve Tab Stem",
    "+Ve Washer", "-Ve Washer", "+Ve EndPlate", "-Ve EndPlate",
    "+Ve Internal-Post", "-Ve Internal-Post",
]


def extract_step_geometry(step_path: Path) -> dict:
    """Return a dict of geometry quantities from a STEP file using pythonOCC.

    Body order: uses confirmed root order (index 1..13) matching BODY_NAMES.
    If STAR exports in a different order in future, cross-check via STEP
    PRODUCT name parsing (not yet implemented — see module docstring).
    """
    try:
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        from OCP.BRepGProp import BRepGProp
        from OCP.Bnd import Bnd_Box
        from OCP.GProp import GProp_GProps
        from OCP.GeomAbs import GeomAbs_Cylinder
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS
    except ImportError:
        raise SystemExit(
            "pythonOCC (OCP) not available. "
            "Activate the project conda environment and retry:\n"
            "  /workspace/.conda/envs/pv/bin/python3 analyse_return.py"
        )

    def bbox(s):
        b = Bnd_Box()
        BRepBndLib.AddOptimal_s(s, b, False, True)
        try:
            return list(b.Get())
        except Exception:
            lo, hi = b.CornerMin(), b.CornerMax()
            return [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]

    def cylinder_radii(s, tol=1e-6):
        out = []
        ex = TopExp_Explorer(s, TopAbs_FACE)
        while ex.More():
            f = TopoDS.Face_s(ex.Current())
            a = BRepAdaptor_Surface(f, True)
            if a.GetType() == GeomAbs_Cylinder:
                r = float(a.Cylinder().Radius())
                if not any(abs(r - x) <= tol for x in out):
                    out.append(r)
            ex.Next()
        return sorted(out)

    def min_distance(a, b):
        d = BRepExtrema_DistShapeShape(a, b)
        return float(d.Value()) if d.IsDone() and d.NbSolution() > 0 else None

    rd = STEPControl_Reader()
    if rd.ReadFile(str(step_path)) != IFSelect_RetDone:
        return {"error": f"STEP read failed: {step_path}"}

    nr = rd.TransferRoots()
    ns = rd.NbShapes()
    if nr != 13 or ns != 13:
        return {
            "error": f"Expected 13 bodies, got roots={nr} shapes={ns}",
            "body_count": ns,
        }

    shapes = {n: rd.Shape(i + 1) for i, n in enumerate(BODY_NAMES)}

    jr_radii  = cylinder_radii(shapes["Jellyroll"])
    can_radii = cylinder_radii(shapes["Can"])
    man_radii = cylinder_radii(shapes["Mandrel"])

    jr_od  = 2 * max(jr_radii)  if jr_radii  else None
    can_od = 2 * max(can_radii) if can_radii else None
    # Can ID is the second-largest radius (inner face of the hollow cylinder)
    can_id = 2 * sorted(can_radii)[-2] if len(can_radii) >= 2 else None
    man_od = 2 * max(man_radii) if man_radii else None

    wall_mm = (can_od - can_id) / 2 if can_od and can_id else None
    gap_mm  = (can_id - jr_od)  / 2 if can_id and jr_od  else None

    jr_dist = min_distance(shapes["Jellyroll"], shapes["Can"])

    return {
        "body_count":           ns,
        "jr_od_mm":             jr_od,
        "can_od_mm":            can_od,
        "can_id_mm":            can_id,
        "can_wall_mm":          wall_mm,
        "mandrel_od_mm":        man_od,
        "jr_can_min_dist_mm":   jr_dist,
        "jr_can_radial_gap_mm": gap_mm,
        "error":                None,
    }


# ── result loader ─────────────────────────────────────────────────────────────

def load_results(return_dir: Path) -> dict[str, dict]:
    """
    Load all results from the RETURN/ folder.
    Returns {case_id: {status, geometry, error_text}}.
    """
    results = {}
    for case_id in BLOCK_SPECS:
        case_dir = return_dir / case_id
        step_files = list(case_dir.glob("*.step")) + list(case_dir.glob("*.stp")) if case_dir.exists() else []
        error_file = case_dir / "ERROR.txt" if case_dir.exists() else None

        if step_files:
            step = step_files[0]
            geo  = extract_step_geometry(step)
            results[case_id] = {
                "status":    "PASS",
                "step_file": str(step),
                "geometry":  geo,
                "error_text": None,
            }
        elif error_file and error_file.exists():
            txt = error_file.read_text(encoding="utf-8", errors="replace").strip()
            results[case_id] = {
                "status":    "FAIL",
                "step_file": None,
                "geometry":  None,
                "error_text": txt,
            }
        else:
            results[case_id] = {
                "status":    "MISSING",
                "step_file": None,
                "geometry":  None,
                "error_text": None,
            }
    return results


# ── mapping analysis ─────────────────────────────────────────────────────────

def analyse_rad_a(results: dict) -> dict:
    """
    Determine what Package m_dintDiameter controls.
    Returns {"controls": "Can_OD" | "Can_ID" | "Neither" | "AMBIGUOUS", "points": [...]}
    """
    base = results.get("CTRL_T06_S", {}).get("geometry") or {}
    base_od = base.get("can_od_mm")
    base_id = base.get("can_id_mm")

    cases = ["RA_19P0", "RA_20P0", "RA_20P5", "RA_21P09"]
    points = []
    od_responses = []
    id_responses = []

    for cid in cases:
        spec  = BLOCK_SPECS[cid]
        r     = results.get(cid, {})
        geo   = r.get("geometry") or {}
        dint  = spec["m_dintDiameter"]

        od = geo.get("can_od_mm")
        id_ = geo.get("can_id_mm")

        if r.get("status") == "FAIL":
            error = r.get("error_text", "")
            points.append({
                "case": cid, "m_dintDiameter": dint,
                "result": "FAIL", "error": error[:120],
                "can_od": None, "can_id": None,
                "delta_od": None, "delta_id": None,
            })
            # "Can Thickness is -ve" when m_dint > current Can OD confirms m_dint → Can ID
            if base_od and dint > base_od and "thickness" in (error or "").lower():
                id_responses.append(True)
            continue

        if r.get("status") != "PASS" or od is None or id_ is None:
            points.append({"case": cid, "m_dintDiameter": dint, "result": "MISSING"})
            continue

        delta_od = od - (base_od or 0)
        delta_id = id_ - (base_id or 0)
        expected_delta = dint - 20.9

        od_tracks = abs(delta_od - expected_delta) < CHANGE_TOL
        id_tracks = abs(delta_id - expected_delta) < CHANGE_TOL
        od_changed = abs(delta_od) > CHANGE_TOL
        id_changed = abs(delta_id) > CHANGE_TOL

        od_responses.append(od_tracks and od_changed)
        id_responses.append(id_tracks and id_changed)

        points.append({
            "case": cid, "m_dintDiameter": dint,
            "result": "PASS",
            "can_od": od, "can_id": id_,
            "delta_od": delta_od, "delta_id": delta_id,
            "expected_delta": expected_delta,
            "od_tracks_dint": od_tracks,
            "id_tracks_dint": id_tracks,
        })

    od_votes = sum(1 for x in od_responses if x)
    id_votes = sum(1 for x in id_responses if x)

    if od_votes >= 2 and id_votes < 1:
        controls = "Can_OD"
    elif id_votes >= 2 and od_votes < 1:
        controls = "Can_ID"
    elif od_votes == 0 and id_votes == 0:
        controls = "Neither_or_insufficient_data"
    else:
        controls = "AMBIGUOUS"

    return {"controls": controls, "points": points,
            "od_votes": od_votes, "id_votes": id_votes}


def analyse_rad_b(results: dict) -> dict:
    """Determine what m_dRepCanX/Y controls."""
    base = results.get("CTRL_T06_S", {}).get("geometry") or {}
    base_od = base.get("can_od_mm")
    base_id = base.get("can_id_mm")

    cases = ["RB_19P0", "RB_20P0", "RB_20P6274"]
    canary = results.get("RB_21P0", {})
    points = []
    od_responses = []
    id_responses = []
    null_responses = []

    for cid in cases:
        spec  = BLOCK_SPECS[cid]
        r     = results.get(cid, {})
        geo   = r.get("geometry") or {}
        rep   = spec["m_dRepCanXY"]

        od  = geo.get("can_od_mm")
        id_ = geo.get("can_id_mm")

        if r.get("status") != "PASS" or od is None:
            points.append({"case": cid, "m_dRepCanXY": rep, "result": r.get("status","MISSING")})
            continue

        delta_od = od - (base_od or 0)
        delta_id = id_ - (base_id or 0) if id_ else None
        expected_delta = rep - 18.0

        od_tracks  = abs(delta_od - expected_delta) < CHANGE_TOL
        id_tracks  = delta_id is not None and abs(delta_id - expected_delta) < CHANGE_TOL
        od_changed = abs(delta_od) > CHANGE_TOL
        id_changed = delta_id is not None and abs(delta_id) > CHANGE_TOL
        null       = not od_changed and (delta_id is None or not id_changed)

        od_responses.append(od_tracks and od_changed)
        id_responses.append(id_tracks and id_changed)
        null_responses.append(null)

        points.append({
            "case": cid, "m_dRepCanXY": rep, "result": "PASS",
            "can_od": od, "can_id": id_,
            "delta_od": delta_od, "delta_id": delta_id,
            "expected_delta": expected_delta,
            "od_tracks_rep": od_tracks,
            "id_tracks_rep": id_tracks,
        })

    # Canary analysis
    canary_confirms_hypa = False
    if canary.get("status") == "FAIL":
        err = canary.get("error_text", "")
        if "thickness" in err.lower() or "negative" in err.lower():
            canary_confirms_hypa = True

    od_votes  = sum(1 for x in od_responses if x)
    id_votes  = sum(1 for x in id_responses if x)
    null_vote = sum(1 for x in null_responses if x)

    if id_votes >= 2 or (id_votes >= 1 and canary_confirms_hypa):
        controls = "Can_ID"
    elif od_votes >= 2:
        controls = "Can_OD"
    elif null_vote >= 2:
        controls = "Overwritten_by_STAR_no_effect"
    else:
        controls = "AMBIGUOUS"

    return {
        "controls": controls,
        "points": points,
        "canary_RB_21P0": {"status": canary.get("status"), "confirms_hypa": canary_confirms_hypa},
        "od_votes": od_votes, "id_votes": id_votes,
    }


def analyse_rad_c(results: dict) -> dict:
    """Establish m_dJellyrollThickness_mm → JR OD transfer function."""
    base = results.get("CTRL_T06_S", {}).get("geometry") or {}
    base_jr = base.get("jr_od_mm")

    cases = ["RC_17P5", "RC_17P0", "RC_16P0"]
    points = []
    confirmed = False
    offsets = []

    for cid in cases:
        spec = BLOCK_SPECS[cid]
        r    = results.get(cid, {})
        geo  = r.get("geometry") or {}
        req  = spec["m_dJR"]
        jr   = geo.get("jr_od_mm")

        if r.get("status") != "PASS" or jr is None:
            points.append({"case": cid, "m_dJR_requested": req, "result": r.get("status","MISSING")})
            continue

        offset    = req - jr
        delta_jr  = jr - (base_jr or T06_REF["jellyroll_od_mm"])
        exp_delta = req - 17.9

        tracks = abs(delta_jr - exp_delta) < CHANGE_TOL
        offsets.append(offset)

        points.append({
            "case": cid, "m_dJR_requested": req, "result": "PASS",
            "jr_od_realized": jr,
            "offset_req_minus_realized": offset,
            "delta_jr": delta_jr, "expected_delta": exp_delta,
            "tracks": tracks,
        })
        if tracks:
            confirmed = True

    mean_offset = sum(offsets) / len(offsets) if offsets else None

    return {
        "confirmed": confirmed,
        "mean_offset_mm": mean_offset,
        "points": points,
        "note": (
            "Use mean_offset to predict m_dJR for production target: "
            f"m_dJR = target_jr_od + {mean_offset:.4f}" if mean_offset else ""
        ),
    }


# ── production evaluation ─────────────────────────────────────────────────────

def _is_geometry_closed(e: dict) -> bool:
    """
    True if this production eval meets ALL RADIAL_GEOMETRY_CLOSED criteria:
      - status PASS
      - 13-body topology
      - Can OD within TOL_CAN_OD of 21.09 mm
      - Can ID within TOL_CAN_ID of 20.6274 mm
      - JR OD within TOL_JR_OD of 20.6274 mm
      - can wall > TOL_WALL_MIN (positive structural wall)
      - radial gap >= 0 and <= TOL_GAP_MAX (contact or near-contact; never negative)
    """
    if e.get("status") != "PASS":
        return False
    if e.get("body_count") != 13:
        return False
    can_od = e.get("can_od_mm")
    can_id = e.get("can_id_mm")
    jr_od  = e.get("jr_od_mm")
    wall   = e.get("can_wall_mm")
    gap    = e.get("jr_can_gap_mm")
    if any(v is None for v in [can_od, can_id, jr_od, wall, gap]):
        return False
    return (
        abs(can_od - PROD_TARGET["can_od_mm"]) < TOL_CAN_OD and
        abs(can_id - PROD_TARGET["can_id_mm"]) < TOL_CAN_ID and
        abs(jr_od  - PROD_TARGET["jr_od_mm"])  < TOL_JR_OD  and
        wall > TOL_WALL_MIN and
        0 <= gap <= TOL_GAP_MAX
    )


def _meets_radial_dims(e: dict) -> bool:
    """True if Can OD and Can ID are within tolerance (JR not required)."""
    if e.get("status") != "PASS":
        return False
    can_od = e.get("can_od_mm")
    can_id = e.get("can_id_mm")
    wall   = e.get("can_wall_mm")
    if can_od is None or can_id is None or wall is None:
        return False
    return (
        abs(can_od - PROD_TARGET["can_od_mm"]) < TOL_CAN_OD and
        abs(can_id - PROD_TARGET["can_id_mm"]) < TOL_CAN_ID and
        wall > TOL_WALL_MIN
    )


def analyse_production(results: dict, rad_a: dict, rad_b: dict) -> list[dict]:
    """Evaluate all PROD candidates."""
    evals = []

    for cid in PROD_CASES:
        spec = BLOCK_SPECS[cid]
        r    = results.get(cid, {})
        geo  = r.get("geometry") or {}

        can_od = geo.get("can_od_mm")
        can_id = geo.get("can_id_mm")
        jr_od  = geo.get("jr_od_mm")
        wall   = geo.get("can_wall_mm")
        gap    = geo.get("jr_can_radial_gap_mm")
        bc     = geo.get("body_count")

        od_err = abs(can_od - PROD_TARGET["can_od_mm"]) if can_od is not None else None
        id_err = abs(can_id - PROD_TARGET["can_id_mm"]) if can_id is not None else None
        jr_err = abs(jr_od  - PROD_TARGET["jr_od_mm"])  if jr_od  is not None else None

        flat = {
            "case_id":       cid,
            "hypothesis":    spec.get("hyp", "?"),
            "status":        r.get("status", "MISSING"),
            "body_count":    bc,
            "can_od_mm":     can_od,
            "can_id_mm":     can_id,
            "jr_od_mm":      jr_od,
            "can_wall_mm":   wall,
            "jr_can_gap_mm": gap,
            "can_od_error":  od_err,
            "can_id_error":  id_err,
            "jr_od_error":   jr_err,
            "error_text":    r.get("error_text"),
        }
        flat["geometry_closed"] = _is_geometry_closed(flat)
        flat["radial_dims_ok"]  = _meets_radial_dims(flat)
        evals.append(flat)
    return evals


# ── decision ─────────────────────────────────────────────────────────────────

def decide(rad_a: dict, rad_b: dict, rad_c: dict, prod_evals: list) -> str:
    """
    Classify the block outcome into one of four codes.

    RADIAL_GEOMETRY_CLOSED
        At least one PROD candidate PASS with: Can OD≈21.09 (±0.05), Can ID≈20.6274 (±0.05),
        JR OD≈20.6274 (±0.05), wall>0.10 mm, gap in [0, 0.03] mm, 13 bodies.
        No further STAR block needed for radial geometry closure.

    RADIAL_MAPPING_CLOSED_FINE_TUNE_REQUIRED
        Mappings known (RAD-A/B/C all confirmed) but no PROD candidate reached full
        geometry_closed. At least one has the correct Can OD and Can ID (radial_dims_ok).
        Fine-tune m_dJR value in BLOCK 02.

    RADIAL_MAPPING_AMBIGUOUS
        RAD-A or RAD-B outcome unclear (insufficient data or contradictory results).
        Cannot compute correct production field values without re-running diagnostics.

    RADIAL_CONSTRUCTION_BOUNDARY_REQUIRES_BLOCK_02
        Mappings confirmed but no PROD candidate passed at all (all failed or wrong geometry).
        Need BLOCK 02 to find constructible JR OD range.
    """
    mapping_a_ok = rad_a["controls"] in ("Can_OD", "Can_ID")
    mapping_b_ok = rad_b["controls"] in ("Can_OD", "Can_ID", "Overwritten_by_STAR_no_effect")
    mapping_c_ok = rad_c["confirmed"]

    any_closed   = any(e["geometry_closed"] for e in prod_evals)
    any_dims_ok  = any(e["radial_dims_ok"]  for e in prod_evals)
    any_pass     = any(e["status"] == "PASS" for e in prod_evals)

    if any_closed:
        return "RADIAL_GEOMETRY_CLOSED"
    elif mapping_a_ok and mapping_b_ok and mapping_c_ok and any_dims_ok:
        return "RADIAL_MAPPING_CLOSED_FINE_TUNE_REQUIRED"
    elif not mapping_a_ok or not mapping_b_ok:
        return "RADIAL_MAPPING_AMBIGUOUS"
    else:
        return "RADIAL_CONSTRUCTION_BOUNDARY_REQUIRES_BLOCK_02"


# ── unit tests ────────────────────────────────────────────────────────────────

def _make_geo(can_od, can_id, jr_od, body_count=13):
    """Build a synthetic flat-eval geometry dict for unit testing.
    Keys match those in the production eval dicts built by analyse_production().
    """
    wall = (can_od - can_id) / 2 if can_od and can_id else None
    gap  = (can_id - jr_od)  / 2 if can_id and jr_od  else None
    return {
        "body_count": body_count,
        "can_od_mm": can_od, "can_id_mm": can_id, "jr_od_mm": jr_od,
        "can_wall_mm": wall, "jr_can_gap_mm": gap,
    }


def _make_rad(controls="Can_OD", confirmed=True):
    return {
        "rad_a": {"controls": controls, "od_votes": 3, "id_votes": 0, "points": []},
        "rad_b": {"controls": "Can_ID", "od_votes": 0, "id_votes": 3, "points": [],
                  "canary_RB_21P0": {"status": "FAIL", "confirms_hypa": True}},
        "rad_c": {"confirmed": confirmed, "mean_offset_mm": -0.019, "points": []},
    }


def test_unit() -> bool:
    """Unit tests for the four decision outcome codes. Returns True if all pass."""
    ok = True

    # ── Test 1: RADIAL_GEOMETRY_CLOSED ───────────────────────────────────────
    # Contact candidate PASS with all targets hit
    geo_closed = _make_geo(21.09, 20.6274, 20.6274)  # gap=0, wall=0.2313
    e_closed = {
        "case_id": "PROD_A_CONT_COMP", "hypothesis": "A", "status": "PASS",
        **geo_closed,
        "can_od_error": 0.0, "can_id_error": 0.0, "jr_od_error": 0.0, "error_text": None,
    }
    e_closed["geometry_closed"] = _is_geometry_closed(e_closed)
    e_closed["radial_dims_ok"]  = _meets_radial_dims(e_closed)
    maps = _make_rad()
    result = decide(maps["rad_a"], maps["rad_b"], maps["rad_c"], [e_closed])
    passed = (result == "RADIAL_GEOMETRY_CLOSED") and e_closed["geometry_closed"]
    print(f"  Test 1 RADIAL_GEOMETRY_CLOSED: {'PASS' if passed else 'FAIL'} (got {result!r}, closed={e_closed['geometry_closed']})")
    ok = ok and passed

    # ── Test 2: RADIAL_MAPPING_CLOSED_FINE_TUNE_REQUIRED ─────────────────────
    # Can OD + Can ID correct but JR OD too far from target
    geo_dims_ok = _make_geo(21.09, 20.6274, 20.50)  # gap≈0.064mm, JR err=0.127
    e_dims = {
        "case_id": "PROD_A_D1_GAP", "hypothesis": "A", "status": "PASS",
        **geo_dims_ok,
        "can_od_error": 0.0, "can_id_error": 0.0,
        "jr_od_error": abs(20.50 - PROD_TARGET["jr_od_mm"]),
        "error_text": None,
    }
    e_dims["geometry_closed"] = _is_geometry_closed(e_dims)
    e_dims["radial_dims_ok"]  = _meets_radial_dims(e_dims)
    result = decide(maps["rad_a"], maps["rad_b"], maps["rad_c"], [e_dims])
    passed = (result == "RADIAL_MAPPING_CLOSED_FINE_TUNE_REQUIRED") and not e_dims["geometry_closed"] and e_dims["radial_dims_ok"]
    print(f"  Test 2 RADIAL_MAPPING_CLOSED_FINE_TUNE_REQUIRED: {'PASS' if passed else 'FAIL'} (got {result!r})")
    ok = ok and passed

    # ── Test 3: RADIAL_MAPPING_AMBIGUOUS ─────────────────────────────────────
    # RAD-A result ambiguous
    maps_ambig = _make_rad(controls="AMBIGUOUS")
    e_fail = {
        "case_id": "PROD_A_D1_GAP", "hypothesis": "A", "status": "FAIL",
        "body_count": None, "can_od_mm": None, "can_id_mm": None, "jr_od_mm": None,
        "can_wall_mm": None, "jr_can_gap_mm": None,
        "can_od_error": None, "can_id_error": None, "jr_od_error": None,
        "error_text": "Can Thickness is -ve",
        "geometry_closed": False, "radial_dims_ok": False,
    }
    result = decide(maps_ambig["rad_a"], maps_ambig["rad_b"], maps_ambig["rad_c"], [e_fail])
    passed = result == "RADIAL_MAPPING_AMBIGUOUS"
    print(f"  Test 3 RADIAL_MAPPING_AMBIGUOUS: {'PASS' if passed else 'FAIL'} (got {result!r})")
    ok = ok and passed

    # ── Test 4: RADIAL_CONSTRUCTION_BOUNDARY_REQUIRES_BLOCK_02 ───────────────
    # Mappings confirmed but all PROD cases failed
    maps_ok = _make_rad(controls="Can_OD")
    result = decide(maps_ok["rad_a"], maps_ok["rad_b"], maps_ok["rad_c"], [e_fail])
    passed = result == "RADIAL_CONSTRUCTION_BOUNDARY_REQUIRES_BLOCK_02"
    print(f"  Test 4 RADIAL_CONSTRUCTION_BOUNDARY_REQUIRES_BLOCK_02: {'PASS' if passed else 'FAIL'} (got {result!r})")
    ok = ok and passed

    # ── Test 5: _is_geometry_closed edge cases ────────────────────────────────
    # Negative gap (JR > Can ID) must not pass
    geo_neg = _make_geo(21.09, 20.6274, 20.700)  # gap = (20.6274-20.700)/2 < 0
    e_neg = {"status": "PASS", **geo_neg, "body_count": 13}
    assert not _is_geometry_closed(e_neg), "Negative gap must fail geometry_closed"

    # Gap slightly above tolerance must not pass
    geo_large_gap = _make_geo(21.09, 20.6274, 20.564)  # gap = (20.6274-20.564)/2 ≈ 0.032 > TOL_GAP_MAX=0.03
    e_large = {"status": "PASS", **geo_large_gap, "body_count": 13}
    assert not _is_geometry_closed(e_large), "Gap above TOL_GAP_MAX must fail geometry_closed"

    # 12-body topology must not pass
    geo_12 = _make_geo(21.09, 20.6274, 20.6274)
    e_12 = {"status": "PASS", **geo_12, "body_count": 12}
    assert not _is_geometry_closed(e_12), "12-body must fail geometry_closed"

    print(f"  Test 5 _is_geometry_closed edge cases: PASS")

    print(f"\n{'ALL UNIT TESTS PASSED' if ok else 'UNIT TEST FAILURES DETECTED'}")
    return ok


# ── regression test ──────────────────────────────────────────────────────────

def regression_test_t06(step_path: Path) -> bool:
    """
    Run extract_step_geometry against the T06 STEP file and verify expected values.
    Expected (from T06_GEOMETRIC_EQUIVALENCE_AUDIT.md):
      JR OD      = 17.880992 mm  (±0.001 mm)
      Can ID     = 18.000000 mm  (±0.001 mm)
      Can OD     ≈ 20.900000 mm  (±0.050 mm)
      radial gap = 0.059504 mm   (±0.005 mm)
      body_count = 13
    """
    print(f"Regression test: {step_path}")
    geo = extract_step_geometry(step_path)
    if geo.get("error"):
        print(f"  ERROR: {geo['error']}")
        return False

    checks = [
        ("body_count",           geo.get("body_count"),           13,         0.0),
        ("jr_od_mm",             geo.get("jr_od_mm"),             17.880992,  0.001),
        ("can_id_mm",            geo.get("can_id_mm"),            18.000000,  0.001),
        ("can_od_mm",            geo.get("can_od_mm"),            20.900000,  0.050),
        ("jr_can_radial_gap_mm", geo.get("jr_can_radial_gap_mm"),  0.059504,  0.005),
    ]
    all_ok = True
    for name, got, expected, tol in checks:
        if got is None:
            print(f"  FAIL {name}: None (expected {expected})")
            all_ok = False
            continue
        diff = abs(got - expected)
        ok = diff <= tol
        print(f"  {'PASS' if ok else 'FAIL'} {name}: got {got:.6f}, expected {expected:.6f} ± {tol}  (diff={diff:.6f})")
        if not ok:
            all_ok = False

    print(f"\nRegression test: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


# ── writers ──────────────────────────────────────────────────────────────────

def write_geometry_csv(results: dict, out_dir: Path) -> None:
    rows = []
    for cid, r in results.items():
        g = r.get("geometry") or {}
        rows.append({
            "case_id":          cid,
            "status":           r["status"],
            "body_count":       g.get("body_count"),
            "jr_od_mm":         g.get("jr_od_mm"),
            "can_od_mm":        g.get("can_od_mm"),
            "can_id_mm":        g.get("can_id_mm"),
            "can_wall_mm":      g.get("can_wall_mm"),
            "mandrel_od_mm":    g.get("mandrel_od_mm"),
            "jr_can_gap_mm":    g.get("jr_can_radial_gap_mm"),
            "jr_can_dist_mm":   g.get("jr_can_min_dist_mm"),
            "geometry_error":   g.get("error"),
            "star_error":       r.get("error_text", "")[:120] if r.get("error_text") else "",
        })
    path = out_dir / "geometry_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"Geometry summary → {path}")


def write_field_deltas_csv(results: dict, out_dir: Path) -> None:
    base_geo = (results.get("CTRL_T06_S") or {}).get("geometry") or {}
    keys = ["jr_od_mm", "can_od_mm", "can_id_mm", "can_wall_mm", "jr_can_radial_gap_mm"]
    rows = []
    for cid, r in results.items():
        g = r.get("geometry") or {}
        row = {"case_id": cid, "status": r["status"]}
        for k in keys:
            v = g.get(k)
            b = base_geo.get(k)
            row[k]               = v
            row[f"delta_{k}"]    = (v - b) if v is not None and b is not None else None
        rows.append(row)
    path = out_dir / "field_deltas.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"Field deltas → {path}")


def write_mapping_report(rad_a, rad_b, rad_c, out_dir: Path) -> None:
    lines = [
        "BLOCK 01 — Mapping Report",
        "=" * 60,
        "",
        "RAD-A: Package m_dintDiameter → ?",
        f"  Conclusion: {rad_a['controls']}",
        f"  OD-tracking votes: {rad_a['od_votes']}  ID-tracking votes: {rad_a['id_votes']}",
    ]
    for p in rad_a["points"]:
        lines.append(f"  {p['case']:15s} m_dint={p.get('m_dintDiameter','?'):6}  "
                     f"Can OD={p.get('can_od','?')}  Can ID={p.get('can_id','?')}  "
                     f"result={p.get('result','?')}")
    lines += [
        "",
        "RAD-B: m_dRepCanXDim/YDim → ?",
        f"  Conclusion: {rad_b['controls']}",
        f"  OD-tracking votes: {rad_b['od_votes']}  ID-tracking votes: {rad_b['id_votes']}",
        f"  Canary RB_21P0: {rad_b['canary_RB_21P0']}",
    ]
    for p in rad_b["points"]:
        lines.append(f"  {p['case']:15s} m_dRepXY={p.get('m_dRepCanXY','?'):8}  "
                     f"Can OD={p.get('can_od','?')}  Can ID={p.get('can_id','?')}  "
                     f"result={p.get('result','?')}")
    lines += [
        "",
        "RAD-C: m_dJellyrollThickness_mm → JR OD",
        f"  Confirmed: {rad_c['confirmed']}",
        f"  Mean request→realize offset: {rad_c['mean_offset_mm']}",
    ]
    for p in rad_c["points"]:
        lines.append(f"  {p['case']:15s} requested={p.get('m_dJR_requested','?'):6}  "
                     f"realized={p.get('jr_od_realized','?')}  "
                     f"offset={p.get('offset_req_minus_realized','?')}  "
                     f"tracks={p.get('tracks','?')}")
    path = out_dir / "mapping_report.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Mapping report → {path}")


def write_production_report(prod_evals: list, out_dir: Path) -> None:
    lines = [
        "BLOCK 01 — Production Candidate Evaluation",
        "=" * 60,
        f"Target: Can OD={PROD_TARGET['can_od_mm']}  Can ID={PROD_TARGET['can_id_mm']}  "
        f"JR OD={PROD_TARGET['jr_od_mm']}  wall={PROD_TARGET['wall_mm']}  gap=0",
        f"Tolerances: Can OD/ID/JR ±{TOL_CAN_OD} mm, wall>{TOL_WALL_MIN} mm, gap in [0, {TOL_GAP_MAX}] mm",
        "",
    ]
    for e in prod_evals:
        closed_flag = " ← GEOMETRY_CLOSED" if e["geometry_closed"] else ""
        dims_flag   = " ← dims_ok" if e["radial_dims_ok"] and not e["geometry_closed"] else ""
        lines.append(
            f"{e['case_id']:25s} hyp={e['hypothesis']}  {e['status']:8s}  "
            f"Can OD={e['can_od_mm']}  Can ID={e['can_id_mm']}  "
            f"JR OD={e['jr_od_mm']}  gap={e['jr_can_gap_mm']}"
            f"{closed_flag}{dims_flag}"
        )
        if e.get("error_text"):
            lines.append(f"  ERROR: {e['error_text'][:100]}")
    path = out_dir / "production_report.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Production report → {path}")


def write_decision(decision: str, out_dir: Path) -> None:
    path = out_dir / "BLOCK_01_DECISION.txt"
    path.write_text(decision + "\n", encoding="utf-8")
    print(f"Decision → {path}  [{decision}]")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Analyse BLOCK 01 returned results")
    ap.add_argument("--return-dir", type=Path, default=HERE / "RETURN",
                    help="Path to returned RETURN/ folder")
    ap.add_argument("--out-dir", type=Path, default=HERE / "analysis_output",
                    help="Directory for analysis outputs")
    ap.add_argument("--run-tests", action="store_true",
                    help="Run unit tests (no STAR results needed)")
    ap.add_argument("--regression-test", type=Path, metavar="T06_STEP",
                    help="Run regression test against provided T06 STEP file")
    args = ap.parse_args()

    if args.run_tests:
        print("Running unit tests…")
        ok = test_unit()
        sys.exit(0 if ok else 1)

    if args.regression_test:
        ok = regression_test_t06(args.regression_test)
        sys.exit(0 if ok else 1)

    if not args.return_dir.exists():
        raise SystemExit(f"RETURN directory not found: {args.return_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading results from {args.return_dir}…")
    results = load_results(args.return_dir)

    n_pass    = sum(1 for r in results.values() if r["status"] == "PASS")
    n_fail    = sum(1 for r in results.values() if r["status"] == "FAIL")
    n_missing = sum(1 for r in results.values() if r["status"] == "MISSING")
    print(f"  PASS={n_pass}  FAIL={n_fail}  MISSING={n_missing}")

    print("Analysing RAD mappings…")
    rad_a = analyse_rad_a(results)
    rad_b = analyse_rad_b(results)
    rad_c = analyse_rad_c(results)
    prod  = analyse_production(results, rad_a, rad_b)
    decision = decide(rad_a, rad_b, rad_c, prod)

    write_geometry_csv(results, args.out_dir)
    write_field_deltas_csv(results, args.out_dir)
    write_mapping_report(rad_a, rad_b, rad_c, args.out_dir)
    write_production_report(prod, args.out_dir)
    write_decision(decision, args.out_dir)

    print()
    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  BLOCK 01 DECISION: {decision:<26}║")
    print(f"╚══════════════════════════════════════════════╝")
    print()
    print("RAD-A (m_dintDiameter)  →", rad_a["controls"])
    print("RAD-B (m_dRepCanX/Y)    →", rad_b["controls"])
    print("RAD-C (m_dJR)           →  JR OD confirmed:", rad_c["confirmed"])
    print()
    closed_cases = [e for e in prod if e["geometry_closed"]]
    if closed_cases:
        print("CASES WITH GEOMETRY_CLOSED:")
        for e in closed_cases:
            print(f"  {e['case_id']}  gap={e['jr_can_gap_mm']}  wall={e['can_wall_mm']}")
    else:
        dims_ok = [e for e in prod if e["radial_dims_ok"]]
        if dims_ok:
            print("Cases with correct Can OD + Can ID (JR fine-tune needed):")
            for e in dims_ok:
                print(f"  {e['case_id']}  Can OD={e['can_od_mm']}  Can ID={e['can_id_mm']}  JR OD={e['jr_od_mm']}")
        else:
            print("No production candidate passed with correct radial dimensions.")
    print()
    print("Analysis outputs →", args.out_dir)


if __name__ == "__main__":
    main()
