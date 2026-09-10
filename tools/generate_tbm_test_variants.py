#!/usr/bin/env python3
"""
Generate four TBM test variants to identify what STAR-CCM+ 'Create from Tbm' generates
under different tab/orientation combinations.

Source: out/hp2170NCA-ECM.tbm
Output: out/test/hp2170-test-v{1..4}-*.tbm

All variants share:
  - Mandrel kept at source value (6 mm) — BDS rejects thickness = 0
  - Package dims corrected for 2170 (same as production simplified TBM)

The 2x2 matrix isolates two unknowns:

  Variant  | Tabs     | Neg orientation       | Key question answered
  ---------|----------|-----------------------|--------------------------------------------
  variant_1 | ON       | Standard (neg=bottom) | Reference: full component list, can-bottom?
  variant_2 | OFF      | Standard (neg=bottom) | How does suppressing tabs affect generated components?
  variant_3 | ON       | Same-face (neg=top)   | How does same-face tab placement affect generated components?
  variant_4 | OFF      | Same-face (neg=top)   | How does tab-off same-face affect generated components?

Rob's checklist for each import (Create from Tbm -> Assign Parts to Regions):
  1. List all generated parts/regions (JellyRoll, Can, EndPlate_neg?, EndPlate_pos?, other?)
  2. Is the Can body open (tube only) or closed (tube + bottom face)?
  3. Is there a separate region at the bottom in variant_1/variant_2?
  4. Does that bottom region differ between variant_2 and variant_1?
  5. How do generated components differ between variant_1 and variant_3?
  6. What topology is generated for variant_4?
"""

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SRC  = Path("out/hp2170NCA-ECM.tbm")
OUTD = Path("out/test")

_CAN_WALL_MM   = 0.2313
_CAN_OD_MM     = 21.09
_JR_HEIGHT_MM  = 65.11


@dataclass
class Variant:
    name: str
    tabs_on: bool
    same_face: bool   # True = neg tab on top (same as pos); False = neg tab on bottom (standard)
    description: str
    key_question: str


VARIANTS = [
    Variant(
        name="v1-tabs-on-standard",
        tabs_on=True,
        same_face=False,
        description="Tabs ON, standard orientation (neg=bottom, pos=top)",
        key_question="Reference geometry: what components exist? Is Can body open or closed at bottom?",
    ),
    Variant(
        name="v2-tabs-off-standard",
        tabs_on=False,
        same_face=False,
        description="Tabs OFF, standard orientation (neg=bottom, pos=top)",
        key_question="Does suppressing tabs remove EndPlate_neg at the bottom?",
    ),
    Variant(
        name="v3-tabs-on-sameFace",
        tabs_on=True,
        same_face=True,
        description="Tabs ON, same-face orientation (neg=top, pos=top)",
        key_question="Does same-face orientation move EndPlate_neg from bottom to top?",
    ),
    Variant(
        name="v4-tabs-off-sameFace",
        tabs_on=False,
        same_face=True,
        description="Tabs OFF, same-face orientation (neg=top, pos=top) — TARGET CONFIG",
        key_question="Is the bottom face clean (no EndPlate)? Is there anything at the top?",
    ),
]


def sub_all(content: bytes, field: str, new_val) -> tuple[bytes, int]:
    pattern = (r'(' + re.escape(field) + r'\s*=\s*)([^\t\r\n!]*)(\s*!.*)?')
    replacement = rf'\g<1>{new_val}'
    new_content, n = re.subn(pattern.encode('latin-1'),
                              replacement.encode('latin-1'),
                              content)
    return new_content, n


def sub_first(content: bytes, field: str, new_val) -> tuple[bytes, bool]:
    pattern = (r'(' + re.escape(field) + r'\s*=\s*)([^\t\r\n!]*)(\s*!.*)?')
    replacement = rf'\g<1>{new_val}'
    new_content, n = re.subn(pattern.encode('latin-1'),
                              replacement.encode('latin-1'),
                              content, count=1)
    return new_content, n > 0


def apply_common_fixes(content: bytes) -> tuple[bytes, list[str]]:
    """Fixes applied to all variants: 2170 Package dims + Detailed Builder geometry.

    Mandrel thickness is kept at the source value (6 mm). BDS rejects
    m_dMandrelThickness = 0 with "Mandrel thickness must be positive".

    m_dElectrodeOverlapAtStart_mm was 0 in the source Detailed Builder (a placeholder
    left by AboutEnergy because the TBM was generated in m_bOnly1D=1 mode). BDS rejects
    zero with "Electrode Root 1 : Extrusion distance can not be 0". The Simple Builder
    block in the same source file has the correct value of 8 mm; we copy it here.

    m_bOnly1D = 1 throughout the source TBM (AboutEnergy generated it in 1D-only ECM mode).
    BDS emits "Warning: m_bOnly1D option is not supported" for each occurrence and then
    fails to complete the 3D geometry creation. All working Siemens reference TBMs use 0
    (or omit the field entirely). Set to 0 everywhere.
    """
    log = []

    din = round(_CAN_OD_MM - 2.0 * _CAN_WALL_MM, 4)
    for field, val, note in [
        ('Package m_dintDiameter',         din,          f'can ID = {_CAN_OD_MM} - 2x{_CAN_WALL_MM} mm'),
        ('Package m_dintHeight',           _JR_HEIGHT_MM, 'jellyroll height'),
        ('Package m_strName',              '2170',        'cell format'),
        ('m_dElectrodeOverlapAtStart_mm',  8,             'copied from Simple Builder; Detailed Builder had 0 (placeholder)'),
        ('m_dMandrelWidth_mm',             6,             'set equal to m_dMandrelThickness_mm; HE18650 ref has width=thickness for cylindrical mandrel'),
        ('+Electrode m_dS3',              5,             'STAR cylindrical refs all use 5; source had 0 (1D-mode placeholder); 0 triggers "Electrode Root 1: Extrusion distance can not be 0"'),
    ]:
        content, hit = sub_first(content, field, val)
        if hit:
            log.append(f"  {field} → {val}  ({note})")
        else:
            print(f"  WARNING: field not found — {field}")

    # Fix m_bOnly1D: source TBM has 1 (1D-only ECM mode); BDS says "not supported"
    # and fails to create 3D geometry. Set to 0 in all 4 UnitCellModel sections.
    content, n = sub_all(content, 'm_bOnly1D', 0)
    log.append(f"  m_bOnly1D → 0  ({n} occurrences; source had 1 = 1D-only ECM mode, not supported by BDS 3D builder)")

    return content, log


def apply_variant(content: bytes, v: Variant) -> tuple[bytes, list[str]]:
    log = []
    tab_val = 1 if v.tabs_on else 0
    for field in ('m_bNegTab', 'm_bPosTab'):
        content, n = sub_all(content, field, tab_val)
        log.append(f"  {field} → {tab_val} ({n} occurrences)")

    neg_orient = 0 if v.same_face else 1
    content, n = sub_all(content, 'm_nNegTabVertOrientation', neg_orient)
    log.append(f"  m_nNegTabVertOrientation → {neg_orient} ({n} occurrences)  "
               f"({'top=same-face' if v.same_face else 'bottom=standard'})")

    # pos orientation stays at 0 (top) in all variants — confirm it's set
    content, n = sub_all(content, 'm_nPosTabVertOrientation', 0)
    log.append(f"  m_nPosTabVertOrientation → 0 ({n} occurrences)  (top, unchanged)")

    return content, log


def main() -> None:
    if not SRC.exists():
        sys.exit(f"ERROR: source file not found: {SRC}")

    OUTD.mkdir(parents=True, exist_ok=True)
    raw = SRC.read_bytes()

    print(f"Source: {SRC}")
    print(f"Output: {OUTD}/\n")
    print("=" * 70)

    for v in VARIANTS:
        content = raw

        content, common_log = apply_common_fixes(content)
        content, variant_log = apply_variant(content, v)

        out_path = OUTD / f"hp2170-test-{v.name}.tbm"
        out_path.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()

        print(f"\n{v.name.upper()}")
        print(f"  {v.description}")
        print(f"  Key question: {v.key_question}")
        print(f"  File:    {out_path}")
        print(f"  SHA-256: {sha}")
        print("  Changes:")
        for line in common_log + variant_log:
            print(line)

    print("\n" + "=" * 70)
    print("\nROB'S IMPORT CHECKLIST (run for each variant in order variant_1→variant_4):")
    print("  File > Create from Tbm  →  select the variant .tbm")
    print("  Battery Module > Assign Parts to Regions")
    print("  For each variant record:")
    print("    a) Full list of generated parts/regions (names + approximate geometry)")
    print("    b) Is the Can body a closed cylinder (with bottom face) or open tube?")
    print("    c) Is there a separate part at the BOTTOM of the cell? (EndPlate_neg?)")
    print("    d) Is there a separate part at the TOP of the cell? (EndPlate_pos?)")
    print("    e) Any unexpected parts (washers, posts, etc.)?")
    print()
    print("  Record the observed parts and topology for each variant; no one-to-one STAR/OpenFOAM")
    print("  topology is a production requirement without Siemens-model evidence.")


if __name__ == '__main__':
    main()
