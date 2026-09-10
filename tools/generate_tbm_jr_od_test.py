#!/usr/bin/env python3
"""Generate two JR OD test variants from the frozen V3 RCR preflight TBM.

Purpose
-------
The OpenFOAM-ECM wedge_2170 mesh has jelly roll OD = can ID = 20.6274 mm
(measured from cases/wedge_2170/constant/jellyRoll_rotated/polyMesh/points,
max radial coordinate = 0.010314 m × 2 = 20.6274 mm). There is no gap in
the OpenFOAM model — JR outer surface and can inner surface are the same face.

The V3 TBM has m_dJellyrollThickness_mm = 19.25 mm, leaving a 1.3774 mm
diametral gap vs the 20.6274 mm can ID. This produces a non-zero annular gap
region in STAR-CCM+ geometry that has no equivalent in the OpenFOAM model.

The August 2026 characterization (in/TBM_STARCCM_Complete_Geometry_Characterization
_20260814_RESULTS.zip) established that STAR enforces a feasibility guard: if the
requested JR OD >= can ID, geometry creation fails. The realised OD tracks the
Detailed Builder input to within ±0.1 mm (monotonic, tested 17.0–17.9 mm range).

Two variants resolve this:

  Variant A — safe (20.55 mm)
    Input 0.077 mm below can ID. Winding discretisation deviation seen in
    the August characterisation was consistently ≤ +0.01 mm, so realised OD
    should be approximately 20.55 mm, well within the 20.6274 mm can ID.
    Creates a very thin (~0.04–0.08 mm) annular gap between JR and can.

  Variant B — perfect contact (20.6274 mm)
    Input equal to can ID. If STAR's winding discretisation rounds down
    (as observed in most August test cases), the realised OD will be ≤ 20.6274 mm
    and STAR will create a near-zero or zero-gap geometry — equivalent to the
    OpenFOAM shared face. If STAR rounds up, geometry creation will fail.

Robert's job: run Create from Tbm on both. For whichever succeeds, export a
STEP and measure the realised JR OD. This determines the safe production value.

Only m_dJellyrollThickness_mm is changed. All other fields, RCR data, MODELMAP,
tabs, electrode geometry, package dimensions, and electrochemistry are unchanged
from V3.

Base: out/rcr_candidate/hp2170-rcr-v3-star-preflight-tabs-on-sameFace.tbm
Base SHA-256: 91cb8f8a2069c308db8dd910a695a2e7bbf55cca509330df004fa8ce82f638d4
Output: out/jr_od_test/
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

BASE = Path("out/rcr_candidate/hp2170-rcr-v3-star-preflight-tabs-on-sameFace.tbm")
BASE_SHA256 = "91cb8f8a2069c308db8dd910a695a2e7bbf55cca509330df004fa8ce82f638d4"
OUTD = Path("out/jr_od_test")

# Can ID for this cell (Package m_dintDiameter in TBM = 21.09 - 2×0.2313 = 20.6274 mm)
CAN_ID_MM = 20.6274

VARIANTS = [
    {
        "name": "safe_20p55",
        "jr_od_mm": 20.55,
        "label": "safe",
        "description": (
            "JR OD = 20.55 mm (0.077 mm below can ID 20.6274 mm). "
            "Winding discretisation should keep realised OD safely within can. "
            "Creates a very thin annular gap."
        ),
    },
    {
        "name": "perfect_contact_20p6274",
        "jr_od_mm": CAN_ID_MM,
        "label": "perfect-contact",
        "description": (
            f"JR OD = {CAN_ID_MM} mm = can ID exactly. "
            "Equivalent to OpenFOAM-ECM wedge_2170 geometry (shared face, no gap). "
            "May fail if STAR winding discretisation rounds up. "
            "If it succeeds, STEP export will show zero or near-zero annular gap."
        ),
    },
]

FIELD = "m_dJellyrollThickness_mm"
CURRENT_VALUE = "19.25"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sub_first(content: bytes, field: str, new_val: str) -> tuple[bytes, bool]:
    pattern = rb'(?m)^([ \t]*' + re.escape(field).encode() + rb'\s*=\s*)([^\t\r\n!]*)'
    new_content, n = re.subn(pattern, rb'\g<1>' + new_val.encode(), content, count=1)
    return new_content, n > 0


def main() -> None:
    if not BASE.exists():
        sys.exit(f"ERROR: base TBM not found: {BASE}")

    raw = BASE.read_bytes()
    actual_sha = sha256_bytes(raw)
    if actual_sha != BASE_SHA256:
        sys.exit(
            f"ERROR: base TBM SHA mismatch\n"
            f"  expected: {BASE_SHA256}\n"
            f"  actual:   {actual_sha}"
        )

    # Confirm current JR OD in base
    m = re.search(rb'(?m)^[ \t]*m_dJellyrollThickness_mm\s*=\s*([^\t\r\n!]*)', raw)
    if not m or m.group(1).strip().decode() != CURRENT_VALUE:
        sys.exit(
            f"ERROR: unexpected {FIELD} in base: {m.group(1) if m else 'not found'!r}\n"
            f"  expected: {CURRENT_VALUE}"
        )

    OUTD.mkdir(parents=True, exist_ok=True)

    print(f"Base:      {BASE}")
    print(f"Base SHA:  {actual_sha}")
    print(f"Base JR OD: {CURRENT_VALUE} mm  (current V3 value)")
    print(f"Can ID:    {CAN_ID_MM} mm")
    print(f"Output:    {OUTD}/")
    print()

    for v in VARIANTS:
        new_val = str(v["jr_od_mm"])
        content, hit = sub_first(raw, FIELD, new_val)
        if not hit:
            print(f"ERROR: field {FIELD} not found in base — cannot generate {v['name']}")
            continue

        # Verify exactly one line changed
        before_lines = raw.splitlines()
        after_lines = content.splitlines()
        diffs = [(i+1, a, b) for i, (a, b) in enumerate(zip(before_lines, after_lines)) if a != b]
        if len(before_lines) != len(after_lines) or len(diffs) != 1:
            sys.exit(f"ERROR: unexpected diff count for {v['name']}: {len(diffs)} changes, "
                     f"line delta {len(after_lines)-len(before_lines)}")
        line_no, before, after = diffs[0]
        if FIELD.encode() not in before or CURRENT_VALUE.encode() not in before:
            sys.exit(f"ERROR: unexpected changed line: {before!r}")

        out_path = OUTD / f"hp2170-jr-{v['name']}.tbm"
        out_path.write_bytes(content)
        out_sha = sha256_bytes(content)

        gap = CAN_ID_MM - v["jr_od_mm"]
        print(f"Variant: {v['name']}  [{v['label']}]")
        print(f"  {v['description']}")
        print(f"  {FIELD}: {CURRENT_VALUE} → {new_val} mm  (gap to can ID: {gap:.4f} mm)")
        print(f"  Changed line {line_no}:")
        print(f"    - {before.decode(errors='replace').strip()}")
        print(f"    + {after.decode(errors='replace').strip()}")
        print(f"  Output:  {out_path}")
        print(f"  SHA-256: {out_sha}")
        print()

    print("=" * 70)
    print("ROBERT'S TEST INSTRUCTIONS:")
    print()
    print("Run 'Batteries > Battery Cell > Create from Tbm' on each file.")
    print()
    print("Variant A — hp2170-jr-safe_20p55.tbm (safe, 20.55 mm input)")
    print("  Expected: geometry creates successfully.")
    print("  Please export a STEP and measure the JR outer diameter.")
    print("  Expected realised OD: approximately 20.5–20.6 mm.")
    print()
    print("Variant B — hp2170-jr-perfect_contact_20p6274.tbm (perfect contact, 20.6274 mm input)")
    print("  Possible outcomes:")
    print("    SUCCESS: geometry creates. Export STEP and measure JR outer diameter.")
    print("             We expect near-zero or zero gap between JR outer face and can inner face.")
    print("    FAILURE: STAR reports a geometry feasibility error (JR exceeds can inner wall).")
    print("             If so, report the exact error message.")
    print()
    print("All RCR data, electrochemistry, MODELMAP, tabs, and package dims are unchanged from V3.")


if __name__ == "__main__":
    main()
