#!/usr/bin/env python3
"""
Generate package_rev4_candidate TBM variants (do NOT send to Robert without review).

This script extends the package_rev3 generation with evidence-based corrections identified
in the independent review of commit e3c3b14. V3 variants in
tbm_validation/variants/v3_package_20260909/ are not modified.

Source: tbm_validation/source/hp2170NCA-ECM.tbm
Output: out/v4_candidate/hp2170-v4c-*.tbm

package_rev4_candidate adds the following corrections on top of all package_rev3 fixes:

  Change                | Field                        | Classification      | Evidence
  ----------------------|------------------------------|---------------------|--------------------------------------
  1e-06 → 0.5           | m_dOffsetPosAvg (DB)         | CONSISTENCY_FIX     | HE18650, HP18650-templ, Tutorial = 0.5
  HPCell → hp2170NCA    | DataSheet m_strName          | CONSISTENCY_FIX     | label field; STAR consumption unconfirmed
  HPCell → hp2170NCA    | DataSheet m_strDSName        | CONSISTENCY_FIX     | label field
  65 → 70.02            | DataSheet m_dHeight          | CONSISTENCY_FIX     | 65 = HP18650 residual; 2170 = 70.02 mm
  65 → 70.02            | DataSheet m_dDSHeight        | CONSISTENCY_FIX     | same
  1.1 → 5.0             | DataSheet m_dCapacity        | CONSISTENCY_FIX     | 1.1 = HP18650 residual; 2170 = 5 Ah
  0.9 → 5.0             | DataSheet m_dDSCapacity      | CONSISTENCY_FIX     | same

NOT changed (still UNRESOLVED or intentional):

  m_dJellyrollThickness_mm = 19.25     UNRESOLVED_ASSUMPTION — JR OD gap, correct value unknown
  m_bOnly1D = 0 (all blocks)           Already correct in package_rev3
  SOC min = -0.08                       INTENTIONAL — extrapolation point per translate script
  m_dElectrodeOverlapAtEnd_mm = 20     UNRESOLVED — lower than refs, value not confirmed
  m_dElectrodeOverlapAtStart_mm = 8    ASSUMED — matches HP18650-templ; not confirmed from AE

STATIC_PASS note: do NOT claim STATIC_PASS for V4 if any check depends on a known
parser ambiguity. As of 2026-09-09, the following WARNs will still be present in V4:
  - jr_od: JellyRoll-can gap 1.38 mm (UNRESOLVED)
  - m_dOnly1D_dist3d: INFO (Distributed 3D block value ambiguous — references disagree)
  - rcr_soc_range: INFO (SOC -0.08 intentional; STAR tolerance unconfirmed)
  - report_jr_diameter / report_jr_height / report_capacity: WARN (stale REPORT values)
"""

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Source: source TBM (not out/hp2170NCA-ECM.tbm — the out/ directory doesn't exist in this repo)
SRC  = Path("tbm_validation/source/hp2170NCA-ECM.tbm")
OUTD = Path("out/v4_candidate")

_CAN_WALL_MM   = 0.2313
_CAN_OD_MM     = 21.09
_JR_HEIGHT_MM  = 65.11


@dataclass
class Variant:
    name: str
    tabs_on: bool
    same_face: bool
    description: str


VARIANTS = [
    Variant("v4c-v1-tabs-on-standard",  True,  False, "V4c: Tabs ON, standard orientation"),
    Variant("v4c-v2-tabs-off-standard", False, False, "V4c: Tabs OFF, standard orientation"),
    Variant("v4c-v3-tabs-on-sameFace",  True,  True,  "V4c: Tabs ON, same-face orientation"),
    Variant("v4c-v4-tabs-off-sameFace", False, True,  "V4c: Tabs OFF, same-face (TARGET CONFIG)"),
]


def sub_all(content: bytes, field: str, new_val) -> tuple[bytes, int]:
    pattern = r'(' + re.escape(field) + r'\s*=\s*)([^\t\r\n!]*)(\s*!.*)?'
    replacement = rf'\g<1>{new_val}'
    new_content, n = re.subn(pattern.encode('latin-1'),
                              replacement.encode('latin-1'),
                              content)
    return new_content, n


def sub_first(content: bytes, field: str, new_val) -> tuple[bytes, bool]:
    pattern = r'(' + re.escape(field) + r'\s*=\s*)([^\t\r\n!]*)(\s*!.*)?'
    replacement = rf'\g<1>{new_val}'
    new_content, n = re.subn(pattern.encode('latin-1'),
                              replacement.encode('latin-1'),
                              content, count=1)
    return new_content, n > 0


def apply_v3_fixes(content: bytes) -> tuple[bytes, list[str]]:
    """Fixes shared with V3 — do not change without updating V3 documentation."""
    log = ["[V3 fixes]"]
    din = round(_CAN_OD_MM - 2.0 * _CAN_WALL_MM, 4)
    for field, val, note in [
        ('Package m_dintDiameter',        din,          f'can ID = {_CAN_OD_MM} - 2x{_CAN_WALL_MM}'),
        ('Package m_dintHeight',          _JR_HEIGHT_MM, 'jellyroll active height'),
        ('Package m_strName',             '2170',        'cell format label'),
        ('m_dElectrodeOverlapAtStart_mm', 8,             'copied from Simple Builder (source had 0)'),
        ('m_dMandrelWidth_mm',            6,             'set equal to mandrel thickness (cylindrical)'),
    ]:
        content, hit = sub_first(content, field, val)
        if hit:
            log.append(f"  {field} → {val}  ({note})")
        else:
            print(f"  WARNING: V3 field not found — {field}")

    content, n = sub_all(content, 'm_bOnly1D', 0)
    log.append(f"  m_bOnly1D → 0  ({n} occurrences; source had 1 = 1D-only mode)")
    return content, log


def apply_v4_fixes(content: bytes) -> tuple[bytes, list[str]]:
    """V4-specific corrections — evidence-based, labelled by classification."""
    log = ["[V4 corrections]"]

    # CONSISTENCY_FIX: m_dOffsetPosAvg Detailed Builder 1e-06 → 0.5
    # Evidence: HE18650, HP18650-template, LiIonSpiral, Tutorial all use 0.5.
    # HP18650-DIST uses 1e-06 (same as our source) but its import status is unconfirmed.
    # Simple Builder remains 0 in source and package_rev3; only Detailed Builder changes.
    content, hit = sub_first(content, 'm_dOffsetPosAvg', '0.5')
    if hit:
        log.append("  m_dOffsetPosAvg (first/DB occurrence) → 0.5  "
                   "(CONSISTENCY_FIX: was 1e-06, all working refs use 0.5)")
    else:
        print("  WARNING: m_dOffsetPosAvg not found")

    # CONSISTENCY_FIX: DataSheet label fields — HP18650 stock residuals
    for field, val, note in [
        ('DataSheet m_strName',    'hp2170NCA',  'CONSISTENCY_FIX: was HPCell (HP18650 label)'),
        ('DataSheet m_strDSName',  'hp2170NCA',  'CONSISTENCY_FIX: same'),
        ('DataSheet m_dHeight',    '70.02',      'CONSISTENCY_FIX: was 65 (HP18650 can height); 2170 = 70.02 mm'),
        ('DataSheet m_dDSHeight',  '70.02',      'CONSISTENCY_FIX: same'),
        ('DataSheet m_dCapacity',  '5.0',        'CONSISTENCY_FIX: was 1.1 (HP18650 capacity); 2170 = 5 Ah'),
        ('DataSheet m_dDSCapacity','5.0',        'CONSISTENCY_FIX: was 0.9 (HP18650 DS capacity)'),
    ]:
        content, hit = sub_first(content, field, val)
        if hit:
            log.append(f"  {field} → {val}  ({note})")
        else:
            print(f"  WARNING: DataSheet field not found — {field}")

    return content, log


def apply_variant(content: bytes, v: Variant) -> tuple[bytes, list[str]]:
    log = [f"[Variant: {v.name}]"]
    tab_val = 1 if v.tabs_on else 0
    for field in ('m_bNegTab', 'm_bPosTab'):
        content, n = sub_all(content, field, tab_val)
        log.append(f"  {field} → {tab_val} ({n} occurrences)")

    neg_orient = 0 if v.same_face else 1
    content, n = sub_all(content, 'm_nNegTabVertOrientation', neg_orient)
    log.append(f"  m_nNegTabVertOrientation → {neg_orient}")

    content, n = sub_all(content, 'm_nPosTabVertOrientation', 0)
    log.append(f"  m_nPosTabVertOrientation → 0")
    return content, log


def main() -> None:
    if not SRC.exists():
        sys.exit(f"ERROR: source file not found: {SRC}\nRun from repo root directory.")

    OUTD.mkdir(parents=True, exist_ok=True)
    raw = SRC.read_bytes()
    src_sha = hashlib.sha256(raw).hexdigest()

    print(f"Source: {SRC}")
    print(f"Source SHA-256: {src_sha}")
    print(f"Output: {OUTD}/\n")
    print("=" * 70)

    for v in VARIANTS:
        content = raw
        content, v3_log = apply_v3_fixes(content)
        content, v4_log = apply_v4_fixes(content)
        content, var_log = apply_variant(content, v)

        out_path = OUTD / f"hp2170-{v.name}.tbm"
        out_path.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()

        print(f"\nVariant: {v.name}")
        print(f"  Output: {out_path}")
        print(f"  SHA-256: {sha}")
        print(f"  Description: {v.description}")
        for line in v3_log + v4_log + var_log:
            if not line.startswith("["):
                print(f"  {line.strip()}")

    print("\n" + "=" * 70)
    print("V4 candidate generation complete.")
    print("Run validate_tbm.py --batch out/v4_candidate/ to check static findings.")
    print("Do NOT send these to Robert without reviewing the V4_DELTA_REPORT.md and validator output.")


if __name__ == "__main__":
    main()
