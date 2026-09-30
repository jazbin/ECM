#!/usr/bin/env python3
"""
BLOCK 01 — TBM generator and manifest builder.

Compresses the established RAD-A / RAD-B / RAD-C dependency chain into a single
short POD block that can be executed continuously on the separate STAR machine.
All TBMs derive from the frozen T06 baseline by patching exactly one logical group
of fields at a time.

Run:
    python3 generate_block.py [--out-dir cases]
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import re
import shutil
from pathlib import Path

HERE   = Path(__file__).resolve().parent   # /workspace/tbm_validation/block_01
REPO   = HERE.parents[1]                  # /workspace
T06_SRC = REPO / "artifacts/equivalence/robert_s0/input/T06_TARGET_AXIAL_SURPLUS_2p00.tbm"
T06_SHA_EXPECTED = "433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71"

# ── helpers ──────────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def patch_field(text: str, field_name: str, new_value: str | float) -> str:
    """
    Replace the numeric value of *field_name* while preserving every other
    character on the line (tabs, flags, comment text).

    Handles both TBM comment styles:
      KEY \\t=\\t17.9\\t!\\t\\t!\\tComment
      KEY \\t=\\t18\\t0\\t\\t! Comment
    """
    escaped = re.escape(field_name)
    rx = re.compile(
        rf"^(\s*{escaped}\s*=\s*)([-\d.]+)([^\r\n]*)$",
        re.MULTILINE,
    )
    matches = list(rx.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            f"patch_field: expected exactly 1 match for {field_name!r}, "
            f"got {len(matches)}"
        )
    return rx.sub(
        lambda m: f"{m.group(1)}{new_value}{m.group(3)}",
        text,
        count=1,
    )


# ── block definition ─────────────────────────────────────────────────────────

# Run-order position: 01 … 20 (sortable)
# case_id   : short ID used for STEP filename and results folder
# family    : CTRL / RAD_A / RAD_B / RAD_C / PROD
# patches   : dict of {field_name: new_value}  (empty = T06 copy)
# expected  : PASS / FAIL_CAN_THICKNESS / UNKNOWN
# hyp       : mapping hypothesis tested (free text)
# notes     : scientific rationale
#
# NOTE — Package m_dextDiameter in PROD cases:
# T06 has m_dextDiameter=21 (package external diameter); production target is 21.09 mm.
# All PROD cases set m_dextDiameter=21.09 for two reasons:
#   1. Physical correctness: the package external diameter SHOULD match the production cell OD.
#   2. Insurance: if m_dextDiameter is the actual Can OD driver (HypD), we get the right geometry.
# Evidence strongly favours HypA (m_dintDiameter→Can OD, exact T06 match); m_dextDiameter=21
# is 0.1 mm off from T06 Can OD=20.9, making HypD far less plausible. Changing m_dextDiameter
# in PROD cases is therefore a deliberate correctness measure, not an experiment. It is listed
# in patches so the isolation audit tracks it explicitly.

BLOCK = [
    # ── CONTROLS ──────────────────────────────────────────────────────────────
    {
        "pos": "01", "case_id": "CTRL_T06_S", "family": "CTRL",
        "patches": {},
        "expected": "PASS",
        "hyp": "—",
        "notes": "T06 frozen baseline at block start; verifies STAR session state",
    },

    # ── RAD-A: probe Package m_dintDiameter ───────────────────────────────
    # T06 state: m_dintDiameter=20.9 → generated Can OD ≈ 20.90 mm (exact match).
    # Causal question: does m_dintDiameter drive Can OD, Can ID, or neither?
    # Safety: m_dRepCanXDim stays 18 so generated Can ID stays ≈18 mm;
    #         m_dJellyrollThickness stays 17.9 so JR OD stays ≈17.88 mm.
    #         All downward steps keep Can OD >> Can ID. Upward step at 21.09
    #         is safe under HypA (Can OD 21.09, Can ID still 18 → wall 1.545 mm)
    #         and informative under HypB (if m_dint → Can ID: 21.09 > 20.9 → fatal).
    {
        "pos": "02", "case_id": "RA_19P0", "family": "RAD_A",
        "patches": {"Package m_dintDiameter": "19.0"},
        "expected": "PASS",
        "hyp": "RMAP-3 / HypA: m_dintDiameter → Can OD (large Δ = −1.9 mm)",
        "notes": "Large downward step; establishes transfer direction and magnitude",
    },
    {
        "pos": "03", "case_id": "RA_20P0", "family": "RAD_A",
        "patches": {"Package m_dintDiameter": "20.0"},
        "expected": "PASS",
        "hyp": "RMAP-3 / HypA: m_dintDiameter → Can OD (Δ = −0.9 mm)",
        "notes": "Medium step; second calibration point for slope",
    },
    {
        "pos": "04", "case_id": "RA_20P5", "family": "RAD_A",
        "patches": {"Package m_dintDiameter": "20.5"},
        "expected": "PASS",
        "hyp": "RMAP-3 / HypA: m_dintDiameter → Can OD (Δ = −0.4 mm)",
        "notes": "Small step close to T06; tightens transfer coefficient",
    },
    {
        "pos": "05", "case_id": "RA_21P09", "family": "RAD_A",
        "patches": {"Package m_dintDiameter": "21.09"},
        "expected": "PASS",
        "hyp": "RMAP-3 / HypA: m_dintDiameter → Can OD (Δ = +0.19 mm = production Can OD target)",
        "notes": (
            "m_dintDiameter set to production Can OD target (21.09 mm). "
            "PASS → production Can OD achievable; also serves as isolated Can-OD probe. "
            "FAIL 'Can Thickness is -ve' would instead confirm HypB (m_dint → Can ID > current Can OD)."
        ),
    },

    # ── RAD-B: probe m_dRepCanXDim / m_dRepCanYDim ───────────────────────
    # T06 state: m_dRepCanX/Y = 18 → generated Can ID = 18.000 mm (exact match).
    # Causal question: does changing m_dRepCanX/Y drive Can OD, Can ID, or is
    # the REPORT block regenerated/overwritten by STAR at import?
    # Safety: all upward steps keep JR OD (≈17.88) << new Can ID >> current Can OD (≈20.9).
    #         RB_21P0 deliberately exceeds current Can OD to act as a canary:
    #         FAIL → confirms HypA (m_dRepCanX/Y → Can ID, 21 > Can OD ≈ 20.9).
    #         PASS → m_dRepCanX/Y drives Can OD or is ignored (REPORT overwritten).
    {
        "pos": "06", "case_id": "RB_19P0", "family": "RAD_B",
        "patches": {"m_dRepCanXDim": "19.0", "m_dRepCanYDim": "19.0"},
        "expected": "PASS",
        "hyp": "RMAP-2 / HypA: m_dRepCanX/Y → Can ID (Δ = +1 mm)",
        "notes": "Upward step; establishes whether Can ID or Can OD responds",
    },
    {
        "pos": "07", "case_id": "RB_20P0", "family": "RAD_B",
        "patches": {"m_dRepCanXDim": "20.0", "m_dRepCanYDim": "20.0"},
        "expected": "PASS",
        "hyp": "RMAP-2 / HypA: m_dRepCanX/Y → Can ID (Δ = +2 mm)",
        "notes": "Larger upward step; second calibration point for slope",
    },
    {
        "pos": "08", "case_id": "RB_20P6274", "family": "RAD_B",
        "patches": {"m_dRepCanXDim": "20.6274", "m_dRepCanYDim": "20.6274"},
        "expected": "PASS",
        "hyp": "RMAP-2 / HypA: m_dRepCanX/Y = production Can ID target (20.6274 mm)",
        "notes": (
            "Production Can ID target value in isolation (m_dintDiameter still T06=20.9). "
            "PASS → Can ID 20.6274 achievable; wall = (20.9−20.6274)/2 = 0.136 mm (thin but positive). "
            "FAIL 'Can Thickness is -ve' → 20.6274 > actual Can OD (unexpected)."
        ),
    },
    {
        "pos": "09", "case_id": "RB_21P0", "family": "RAD_B",
        "patches": {"m_dRepCanXDim": "21.0", "m_dRepCanYDim": "21.0"},
        "expected": "FAIL_CAN_THICKNESS",
        "hyp": "Canary: expected FAIL under HypA (m_dRepCanX/Y → Can ID = 21 > Can OD ≈ 20.9)",
        "notes": (
            "Deliberately exceeds T06 Can OD ≈ 20.9 mm. "
            "FAIL 'Can Thickness is -ve' confirms m_dRepCanX/Y → Can ID (HypA). "
            "PASS (any geometry) would indicate m_dRepCanX/Y → Can OD or ignored."
        ),
    },

    # ── MID-BLOCK CONTROL ─────────────────────────────────────────────────
    {
        "pos": "10", "case_id": "CTRL_T06_M", "family": "CTRL",
        "patches": {},
        "expected": "PASS",
        "hyp": "—",
        "notes": "Mid-block T06 repeat; detects persistent-state contamination in STAR session",
    },

    # ── RAD-C: probe m_dJellyrollThickness_mm ────────────────────────────
    # T06 state: m_dJellyrollThickness=17.9 → realized JR OD = 17.880992 mm (offset −0.019 mm).
    # August 2026 characterization confirmed this mapping on a different geometry class.
    # Purpose: verify mapping holds on T06 class and calibrate the offset for production range.
    # Safety: all downward steps move JR OD away from Can ID (18 mm). Cannot test upward
    # without also raising Can ID (that is done in PROD cases below).
    {
        "pos": "11", "case_id": "RC_17P5", "family": "RAD_C",
        "patches": {"m_dJellyrollThickness_mm": "17.5"},
        "expected": "PASS",
        "hyp": "RMAP-1: m_dJellyrollThickness_mm → JR OD (T06 class, Δ = −0.4 mm)",
        "notes": "Confirms RMAP-1 holds on T06 geometry class; first slope point",
    },
    {
        "pos": "12", "case_id": "RC_17P0", "family": "RAD_C",
        "patches": {"m_dJellyrollThickness_mm": "17.0"},
        "expected": "PASS",
        "hyp": "RMAP-1: m_dJellyrollThickness_mm → JR OD (Δ = −0.9 mm)",
        "notes": "Second slope point; wider range for confident linear fit",
    },
    {
        "pos": "13", "case_id": "RC_16P0", "family": "RAD_C",
        "patches": {"m_dJellyrollThickness_mm": "16.0"},
        "expected": "PASS",
        "hyp": "RMAP-1: m_dJellyrollThickness_mm → JR OD (Δ = −1.9 mm)",
        "notes": "Widest range in RAD-C family; confirms linearity over >1 mm span",
    },

    # ── PRODUCTION CANDIDATES — HypA branch ──────────────────────────────
    # HypA: m_dintDiameter → Can OD (1:1), m_dRepCanX/Y → Can ID (1:1),
    #       m_dJellyrollThickness_mm → JR OD (1:1, offset ≈ −0.019 mm).
    # Target: Can OD=21.09, Can ID=20.6274, JR OD=20.6274 (ideal contact).
    # m_dextDiameter set to 21.09 in all PROD cases (see block-level note above).
    #
    # Safety: Can OD (21.09) > Can ID (20.6274) → wall = 0.2313 mm. ✓
    #         JR OD ≤ Can ID for all cases (positive or zero clearance). ✓
    #         Tab surplus unchanged at +2.00 mm / +2.00 mm (T06 frozen). ✓
    {
        "pos": "14", "case_id": "PROD_A_D1_GAP", "family": "PROD",
        "patches": {
            "Package m_dextDiameter": "21.09",
            "Package m_dintDiameter": "21.09",
            "m_dRepCanXDim": "20.6274",
            "m_dRepCanYDim": "20.6274",
            "m_dJellyrollThickness_mm": "20.519",
        },
        "expected": "PASS",
        "hyp": (
            "HypA full production: Can OD=21.09 (m_dint=21.09), "
            "Can ID=20.6274 (m_dRepXY=20.6274), JR OD≈20.500 (m_dJR=20.519); "
            "radial clearance ≈ 0.064 mm (similar to T06 0.060 mm)"
        ),
        "notes": (
            "RAD-D1 primary candidate. Positive clearance comparable to T06 baseline. "
            "Expected PASS; geometry closest to T06 clearance magnitude."
        ),
    },
    {
        "pos": "15", "case_id": "PROD_A_D1_SLIM", "family": "PROD",
        "patches": {
            "Package m_dextDiameter": "21.09",
            "Package m_dintDiameter": "21.09",
            "m_dRepCanXDim": "20.6274",
            "m_dRepCanYDim": "20.6274",
            "m_dJellyrollThickness_mm": "20.569",
        },
        "expected": "PASS",
        "hyp": (
            "HypA full production: JR OD≈20.550 (m_dJR=20.569); "
            "radial clearance ≈ 0.039 mm"
        ),
        "notes": (
            "RAD-D1 slim-clearance candidate. Tests whether smaller but still "
            "positive clearance builds successfully."
        ),
    },
    {
        "pos": "16", "case_id": "PROD_A_CONT_LIT", "family": "PROD",
        "patches": {
            "Package m_dextDiameter": "21.09",
            "Package m_dintDiameter": "21.09",
            "m_dRepCanXDim": "20.6274",
            "m_dRepCanYDim": "20.6274",
            "m_dJellyrollThickness_mm": "20.6274",
        },
        "expected": "UNKNOWN",
        "hyp": (
            "HypA contact LITERAL: m_dJR=20.6274 (= Can ID target, no offset correction); "
            "realized JR OD ≈ 20.608 (offset ≈ −0.019 mm); gap ≈ 0.010 mm"
        ),
        "notes": (
            "H004-3 near-contact test with literal target value. "
            "PASS → JR OD ≈ Can ID achievable without exact compensation. "
            "FAIL 'Can Thickness is -ve' → unexpectedly, JR OD > Can ID even without compensation."
        ),
    },
    {
        "pos": "17", "case_id": "PROD_A_CONT_COMP", "family": "PROD",
        "patches": {
            "Package m_dextDiameter": "21.09",
            "Package m_dintDiameter": "21.09",
            "m_dRepCanXDim": "20.6274",
            "m_dRepCanYDim": "20.6274",
            "m_dJellyrollThickness_mm": "20.6464",
        },
        "expected": "UNKNOWN",
        "hyp": (
            "HypA contact COMPENSATED: m_dJR=20.6464 (= target 20.6274 + offset +0.019 mm); "
            "realized JR OD ≈ 20.6274 → gap = 0 mm (H004-3 test)"
        ),
        "notes": (
            "RAD-D2: H004-3 exact-contact constructibility test. "
            "PASS → preferred production geometry (JR OD = Can ID = 20.6274) achievable. "
            "FAIL → locates upper JR OD construction boundary; PROD_A_D1_GAP or SLIM becomes target."
        ),
    },

    # ── PRODUCTION CANDIDATES — HypB branch ──────────────────────────────
    # HypB (alternative): m_dRepCanX/Y → Can OD, m_dintDiameter → Can ID.
    # T06 numerical evidence DOES NOT support a 1:1 mapping under HypB
    # (m_dRepCanXDim=18 ≠ T06 Can OD=20.9; m_dintDiameter=20.9 ≠ T06 Can ID=18.0).
    # However, if the REPORT block values are authoritative inputs (not derived),
    # HypB production candidates set them to the correct production values directly.
    # Under HypA: both cases FAIL 'Can Thickness is -ve' (m_dRepXY=21.09 → Can ID=21.09
    #             > Can OD from m_dint=20.6274 → negative wall). That FAIL is diagnostic.
    # Under HypB: both cases PASS with Can OD=21.09, Can ID=20.6274, JR OD as specified.
    # Including these avoids a second POD block if HypB turns out correct.
    {
        "pos": "18", "case_id": "PROD_B_D1", "family": "PROD",
        "patches": {
            "Package m_dextDiameter": "21.09",
            "Package m_dintDiameter": "20.6274",
            "m_dRepCanXDim": "21.09",
            "m_dRepCanYDim": "21.09",
            "m_dJellyrollThickness_mm": "20.519",
        },
        "expected": "UNKNOWN",
        "hyp": (
            "HypB positive-clearance: Can OD=21.09 (m_dRepXY=21.09), Can ID=20.6274 (m_dint=20.6274), "
            "JR OD≈20.500 (m_dJR=20.519); gap≈0.064 mm. "
            "Under HypA: FAIL 'Can Thickness is -ve' (Can ID=21.09 > Can OD=20.6274)"
        ),
        "notes": (
            "HypB RAD-D1 candidate. PASS → HypB confirmed, production geometry achievable. "
            "FAIL 'Can Thickness is -ve' → additional HypA confirmation."
        ),
    },
    {
        "pos": "19", "case_id": "PROD_B_CONT_LIT", "family": "PROD",
        "patches": {
            "Package m_dextDiameter": "21.09",
            "Package m_dintDiameter": "20.6274",
            "m_dRepCanXDim": "21.09",
            "m_dRepCanYDim": "21.09",
            "m_dJellyrollThickness_mm": "20.6274",
        },
        "expected": "UNKNOWN",
        "hyp": (
            "HypB contact LITERAL: m_dJR=20.6274 (literal target, no offset correction); "
            "realized JR OD≈20.608; gap≈0.010 mm. Under HypA: FAIL."
        ),
        "notes": (
            "HypB H004-3 near-contact test. PASS → HypB contact geometry obtainable. "
            "FAIL 'Can Thickness is -ve' → HypA confirmed again."
        ),
    },

    # ── END CONTROL ───────────────────────────────────────────────────────
    {
        "pos": "20", "case_id": "CTRL_T06_E", "family": "CTRL",
        "patches": {},
        "expected": "PASS",
        "hyp": "—",
        "notes": "T06 baseline at block end; detects drift or state mutation during session",
    },
]


# ── generation ───────────────────────────────────────────────────────────────

def generate(out_dir: Path) -> list[dict]:
    """Generate all TBMs into out_dir; return list of manifest rows."""
    if not T06_SRC.exists():
        raise FileNotFoundError(T06_SRC)
    actual_sha = sha256(T06_SRC)
    if actual_sha != T06_SHA_EXPECTED:
        raise RuntimeError(
            f"T06 baseline SHA mismatch.\n"
            f"  Expected: {T06_SHA_EXPECTED}\n"
            f"  Got:      {actual_sha}\n"
            "Do not proceed with a modified baseline."
        )
    t06_text = T06_SRC.read_text(encoding="latin-1")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for spec in BLOCK:
        pos      = spec["pos"]
        case_id  = spec["case_id"]
        patches  = spec["patches"]

        # Apply patches to T06 baseline
        text = t06_text
        changed_fields = {}
        for field, new_val in patches.items():
            # Record old value before patching
            rx = re.compile(
                rf"^(\s*{re.escape(field)}\s*=\s*)([-\d.]+)([^\r\n]*)$",
                re.MULTILINE,
            )
            ms = list(rx.finditer(text))
            if len(ms) != 1:
                raise RuntimeError(
                    f"Case {case_id}: field {field!r} matched {len(ms)} times."
                )
            old_val = ms[0].group(2)
            changed_fields[field] = {"old": old_val, "new": str(new_val)}
            text = patch_field(text, field, str(new_val))

        # Write TBM
        tbm_name = f"{pos}_{case_id}.tbm"
        tbm_path = out_dir / tbm_name
        tbm_path.write_text(text, encoding="latin-1")

        # Verify all unchanged fields still match T06
        for field in [
            "Package m_dintDiameter", "Package m_dextDiameter",
            "m_dJellyrollThickness_mm", "m_dRepCanXDim", "m_dRepCanYDim",
            "m_dMandrelThickness_mm", "Package m_dextHeight", "Package m_dintHeight",
            r"+Electrode Tab m_dLength_mm", r"-Electrode Tab m_dLength_mm",
        ]:
            if field in patches:
                continue
            rx = re.compile(
                rf"^(\s*{re.escape(field)}\s*=\s*)([-\d.]+)([^\r\n]*)$",
                re.MULTILINE,
            )
            ms_new = list(rx.finditer(text))
            ms_old = list(rx.finditer(t06_text))
            if not ms_new or not ms_old:
                continue
            if ms_new[0].group(2) != ms_old[0].group(2):
                raise RuntimeError(
                    f"ISOLATION VIOLATION in {case_id}: "
                    f"field {field!r} changed from {ms_old[0].group(2)!r} "
                    f"to {ms_new[0].group(2)!r} without being in patches."
                )

        # Build manifest row
        row = {
            "run_pos":        pos,
            "case_id":        case_id,
            "family":         spec["family"],
            "tbm_file":       tbm_name,
            "baseline_sha256": T06_SHA_EXPECTED,
            "tbm_sha256":     sha256(tbm_path),
            "changed_fields": "; ".join(
                f"{k}: {v['old']}→{v['new']}"
                for k, v in changed_fields.items()
            ) if changed_fields else "—",
            "expected":       spec["expected"],
            "hyp":            spec["hyp"],
            "notes":          spec["notes"],
        }
        rows.append(row)
        print(f"  {pos} {case_id:25s}  {row['tbm_sha256'][:16]}…  "
              f"changed={len(patches)} field(s)")

    return rows


def write_manifest(rows: list[dict], out_dir: Path) -> None:
    path = out_dir.parent / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Manifest → {path}")


def write_run_order(rows: list[dict], out_dir: Path) -> None:
    path = out_dir.parent / "RUN_ORDER.txt"
    lines = [
        "BLOCK 01 — Run Order",
        f"Total cases: {len(rows)}",
        "Estimated time: {:.0f}–{:.0f} min at 10–20 s/case".format(
            len(rows) * 10 / 60, len(rows) * 20 / 60),
        "",
        f"{'Pos':<4} {'Case ID':<25} {'Expected':<20} {'Changed field(s)':<65} {'TBM SHA256 prefix'}",
        "-" * 130,
    ]
    for r in rows:
        lines.append(
            f"{r['run_pos']:<4} {r['case_id']:<25} {r['expected']:<20} "
            f"{r['changed_fields']:<65} {r['tbm_sha256'][:16]}…"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Run order → {path}")


def write_results_template(rows: list[dict], out_dir: Path) -> None:
    path = out_dir.parent / "RESULTS_TEMPLATE.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "run_pos", "case_id", "expected",
            "actual_result",           # PASS / FAIL / TIMEOUT / SKIP
            "star_error_exact_text",   # leave blank if PASS
            "step_file_name",          # exact filename of exported STEP if PASS
            "operator_notes",
        ])
        for r in rows:
            w.writerow([
                r["run_pos"], r["case_id"], r["expected"],
                "", "", "", "",
            ])
    print(f"Results template → {path}")


def write_isolation_audit(rows: list[dict], out_dir: Path) -> None:
    """Verify each TBM changes exactly the intended fields and nothing else."""
    t06_text = T06_SRC.read_text(encoding="latin-1")
    audit_fields = [
        "Package m_dextDiameter",
        "Package m_dintDiameter",
        "m_dJellyrollThickness_mm",
        "m_dRepCanXDim",
        "m_dRepCanYDim",
        "m_dMandrelThickness_mm",
        "Package m_dextHeight",
        "Package m_dintHeight",
        "+Electrode Tab m_dLength_mm",
        "-Electrode Tab m_dLength_mm",
        "m_dSepFeedLength_mm",
        "m_dSepTailLength_mm",
        "m_dElectrodeOverlapAtEnd_mm",
        "+Electrode m_dWidth",
        "-Electrode m_dWidth",
    ]

    def get_vals(text):
        out = {}
        for f in audit_fields:
            rx = re.compile(
                rf"^(\s*{re.escape(f)}\s*=\s*)([-\d.]+)([^\r\n]*)$",
                re.MULTILINE,
            )
            ms = rx.findall(text)
            out[f] = ms[0][1] if len(ms) == 1 else f"MULTI({len(ms)})"
        return out

    t06_vals = get_vals(t06_text)
    audit_rows = []
    all_ok = True

    for spec in BLOCK:
        tbm_path = out_dir / f"{spec['pos']}_{spec['case_id']}.tbm"
        if not tbm_path.exists():
            audit_rows.append({
                "case_id": spec["case_id"],
                "field": "—",
                "status": "ERROR: TBM NOT GENERATED",
                "t06_value": "—",
                "actual_value": "—",
                "expected_value": "—",
            })
            all_ok = False
            continue

        tbm_vals = get_vals(tbm_path.read_text(encoding="latin-1"))
        for f in audit_fields:
            t06_v  = t06_vals.get(f, "?")
            tbm_v  = tbm_vals.get(f, "?")
            exp_v  = str(spec["patches"].get(f, t06_v))

            if f in spec["patches"]:
                # Should have changed
                ok = (tbm_v == exp_v)
                status = "CHANGED_OK" if ok else f"CHANGE_WRONG(got {tbm_v!r})"
            else:
                # Should NOT have changed
                ok = (tbm_v == t06_v)
                status = "UNCHANGED_OK" if ok else f"UNINTENDED_CHANGE({t06_v!r}→{tbm_v!r})"

            if not ok:
                all_ok = False

            audit_rows.append({
                "case_id":        spec["case_id"],
                "field":          f,
                "status":         status,
                "t06_value":      t06_v,
                "actual_value":   tbm_v,
                "expected_value": exp_v,
            })

    path = out_dir.parent / "ISOLATION_AUDIT.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["case_id", "field", "status",
                           "t06_value", "actual_value", "expected_value"]
        )
        w.writeheader()
        w.writerows(audit_rows)

    violations = [r for r in audit_rows if "WRONG" in r["status"] or "UNINTENDED" in r["status"] or "ERROR" in r["status"]]
    if violations:
        print(f"ISOLATION AUDIT — FAILED ({len(violations)} violations):")
        for v in violations:
            print(f"  {v['case_id']}: {v['field']} — {v['status']}")
        raise SystemExit("Isolation audit failed. Do not dispatch this block.")
    else:
        print(f"Isolation audit → PASS ({len(audit_rows)} checks, 0 violations) → {path}")
    return all_ok


def create_return_skeleton(base_dir: Path, rows: list[dict]) -> None:
    """Create empty RETURN/ folder structure for STAR operator to fill."""
    ret = base_dir / "RETURN"
    ret.mkdir(exist_ok=True)
    readme = (
        "RETURN folder — STAR operator: copy results here.\n\n"
        "For each PASS case:\n"
        "  RETURN/<case_id>/<case_id>.step\n\n"
        "For each FAIL case:\n"
        "  RETURN/<case_id>/ERROR.txt  (exact STAR error text)\n\n"
        "Do not add any other files. Do not rename STEP files.\n"
    )
    (ret / "README.txt").write_text(readme, encoding="utf-8")
    for r in rows:
        cdir = ret / r["case_id"]
        cdir.mkdir(exist_ok=True)
    print(f"RETURN skeleton → {ret}/  ({len(rows)} case folders)")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate BLOCK 01 TBMs")
    ap.add_argument("--out-dir", type=Path,
                    default=HERE / "cases",
                    help="Directory for generated TBM files")
    args = ap.parse_args()

    print(f"Generating BLOCK 01 ({len(BLOCK)} cases) from T06 baseline…")
    rows = generate(args.out_dir)
    write_manifest(rows, args.out_dir)
    write_run_order(rows, args.out_dir)
    write_results_template(rows, args.out_dir)
    write_isolation_audit(rows, args.out_dir)
    create_return_skeleton(args.out_dir.parent, rows)
    print(f"\nDone — {len(rows)} TBMs in {args.out_dir}")


if __name__ == "__main__":
    main()
