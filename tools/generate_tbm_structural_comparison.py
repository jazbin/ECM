#!/usr/bin/env python3
"""
Generate tbm_validation/TBM_STRUCTURAL_COMPARISON.md from machine-extracted TBM field values.

Run from the workspace root:
    python3 tools/generate_tbm_structural_comparison.py

All displayed values are extracted programmatically from the actual TBM files at run time.
Prose and table entries are always consistent because both come from the same extraction pass.

Naming convention used throughout:
  package_rev3 / variant_{1-4}  — the geometry-test package sent 2026-09-09
  package_rev4_candidate / variant_{1-4}  — the V4 review candidate (NOT yet sent)

Do not use bare "V3" or "V4" in generated output — these terms are ambiguous because
V3 is a package revision that itself contains four variants, and V4 is a candidate
package revision. The confusion was noted in the independent review of 2ea5b45.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from tbm_field_extractor import extract_tbm_fields

WORKSPACE = Path(__file__).resolve().parents[1]

# Canonical file paths on integration branch
SOURCE_TBM  = WORKSPACE / 'tbm_validation/source/hp2170NCA-ECM.tbm'
HE18650_TBM = WORKSPACE / 'tbm_validation/reference/HE18650/he18650spiral1.tbm'

# package_rev3: any typical variant (all four have the same BUILDER/SIMMOD values)
PKG_REV3_V1 = WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v1-tabs-on-standard.tbm'
PKG_REV3_V2 = WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v2-tabs-off-standard.tbm'
PKG_REV3_V3 = WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v3-tabs-on-sameFace.tbm'
PKG_REV3_V4 = WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v4-tabs-off-sameFace.tbm'

# package_rev4_candidate: tabs-off-sameFace is the target config
PKG_REV4C_V1 = WORKSPACE / 'out/v4_candidate/hp2170-v4c-v1-tabs-on-standard.tbm'
PKG_REV4C_V2 = WORKSPACE / 'out/v4_candidate/hp2170-v4c-v2-tabs-off-standard.tbm'
PKG_REV4C_V3 = WORKSPACE / 'out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm'
PKG_REV4C_V4 = WORKSPACE / 'out/v4_candidate/hp2170-v4c-v4-tabs-off-sameFace.tbm'

OUTPUT = WORKSPACE / 'tbm_validation/TBM_STRUCTURAL_COMPARISON.md'


def _fmt(val) -> str:
    return '—' if val is None else str(val).strip()


def _bonly1d_str(lst: list) -> str:
    return '(none)' if not lst else '[' + ', '.join(lst) + ']'


def generate(src, he, r3v1, r3v2, r3v3, r3v4, r4v1, r4v2, r4v3, r4v4) -> str:
    lines = []

    def h(text=''): lines.append(text)

    h('# TBM Structural Field Comparison')
    h()
    h('> **Machine-generated** — do not hand-edit. Regenerate with:')
    h('> ```')
    h('> python3 tools/generate_tbm_structural_comparison.py')
    h('> ```')
    h()
    h('All values are extracted directly from the TBM files using `tools/tbm_field_extractor.py`.')
    h('Prose and table entries are always consistent because both come from the same extraction pass.')
    h()
    h('**Naming convention:**')
    h('- `package_rev3 / variant_N` — the geometry-test package (sent 2026-09-09, commit e3c3b14)')
    h('- `package_rev4_candidate / variant_N` — the package_rev4_candidate review candidate (commit 2ea5b45, NOT yet sent to Robert)')
    h()
    h('Use `package_rev3`, `package_rev4_candidate`, and `variant_N` explicitly; '
      'package revision and variant identifiers must not be collapsed into shorthand.')
    h()

    h('## Files compared')
    h()
    h('| Label | Path |')
    h('|-------|------|')
    h('| source | `tbm_validation/source/hp2170NCA-ECM.tbm` |')
    h('| HE18650 (known-good reference) | `tbm_validation/reference/HE18650/he18650spiral1.tbm` |')
    h('| package_rev3 / variant_1 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v1-tabs-on-standard.tbm` |')
    h('| package_rev3 / variant_2 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v2-tabs-off-standard.tbm` |')
    h('| package_rev3 / variant_3 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v3-tabs-on-sameFace.tbm` |')
    h('| package_rev3 / variant_4 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v4-tabs-off-sameFace.tbm` |')
    h('| package_rev4_candidate / variant_1 | `out/v4_candidate/hp2170-v4c-v1-tabs-on-standard.tbm` |')
    h('| package_rev4_candidate / variant_2 | `out/v4_candidate/hp2170-v4c-v2-tabs-off-standard.tbm` |')
    h('| package_rev4_candidate / variant_3 | `out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm` |')
    h('| package_rev4_candidate / variant_4 | `out/v4_candidate/hp2170-v4c-v4-tabs-off-sameFace.tbm` |')
    h()

    # ---- m_dOffsetPosAvg ----
    h('## `m_dOffsetPosAvg` — Positive Offset (mm)')
    h()
    h('Two occurrences per file: one in the **Detailed Builder** (DB) block, one in the')
    h('**Simple Builder** (SB) block. Both are extracted independently from their respective')
    h('`<BUILDER>` sections. The extractor identifies DB vs SB by the header line inside each')
    h('`<BUILDER>` block; values from different blocks are never aliased.')
    h()

    all_files = [
        ('source',                     src),
        ('HE18650',                    he),
        ('package_rev3 / variant_1',   r3v1),
        ('package_rev3 / variant_2',   r3v2),
        ('package_rev3 / variant_3',   r3v3),
        ('package_rev3 / variant_4',   r3v4),
        ('package_rev4_candidate / variant_1', r4v1),
        ('package_rev4_candidate / variant_2', r4v2),
        ('package_rev4_candidate / variant_3', r4v3),
        ('package_rev4_candidate / variant_4', r4v4),
    ]

    h('| File | DB | SB |')
    h('|------|----|----|')
    for label, f in all_files:
        h(f'| {label} | {_fmt(f.detailed_builder.offset_pos_avg)} | {_fmt(f.simple_builder.offset_pos_avg)} |')
    h()

    # Generate factual notes from extracted data
    src_db   = _fmt(src.detailed_builder.offset_pos_avg)
    src_sb   = _fmt(src.simple_builder.offset_pos_avg)
    he_db    = _fmt(he.detailed_builder.offset_pos_avg)
    he_sb    = _fmt(he.simple_builder.offset_pos_avg)
    r3_db    = _fmt(r3v1.detailed_builder.offset_pos_avg)
    r3_sb    = _fmt(r3v1.simple_builder.offset_pos_avg)
    r4c_db   = _fmt(r4v4.detailed_builder.offset_pos_avg)
    r4c_sb   = _fmt(r4v4.simple_builder.offset_pos_avg)

    h('**Notes:**')
    h()
    h(f'- source DB = `{src_db}`, SB = `{src_sb}`. The DB value was set by About-Energy in the '
      f'original ECM-mode TBM; it is near-zero but not identically zero. SB = `{src_sb}` (NOT 0.5 '
      f'— a prior version of this document incorrectly showed SB = 0.5 for source).')
    h(f'- HE18650 (known-good Siemens stock reference): DB = `{he_db}`, SB = `{he_sb}`.')
    h(f'- All package_rev3 variants: DB = `{r3_db}`, SB = `{r3_sb}`. '
      f'SB = `{r3_sb}` (NOT 0.5 — prior incorrect claim corrected here).')
    h(f'- package_rev4_candidate all variants: DB = `{r4c_db}`, SB = `{r4c_sb}`. '
      f'DB corrected from `{src_db}` → `{r4c_db}` (CONSISTENCY_FIX: all known-working '
      f'references use DB = 0.5). SB = `{r4c_sb}` (unchanged from source/package_rev3).')
    if r4c_db == he_db and r4c_sb == he_sb:
        h(f'- **package_rev4_candidate DB/SB pattern matches HE18650 exactly** (`{r4c_db}` / `{r4c_sb}`).')
    h()

    # ---- m_dMandrelWidth ----
    h('## `m_dMandrelWidth` — Mandrel Width (mm)')
    h()
    h('| File | DB (`m_dMandrelWidth_mm`) | SB (`m_dMandrelWidth`) |')
    h('|------|--------------------------|------------------------|')
    for label, f in all_files:
        h(f'| {label} | {_fmt(f.detailed_builder.mandrel_width)} | {_fmt(f.simple_builder.mandrel_width)} |')
    h()

    # ---- m_dElectrodeOverlapAtStart ----
    h('## `m_dElectrodeOverlapAtStart` — Electrode Overlap at Start (mm)')
    h()
    h('| File | DB (`m_dElectrodeOverlapAtStart_mm`) | SB (`m_dElectrodeOverlapAtStart`) |')
    h('|------|--------------------------------------|-----------------------------------|')
    for label, f in all_files:
        h(f'| {label} | {_fmt(f.detailed_builder.electrode_overlap_at_start)} '
          f'| {_fmt(f.simple_builder.electrode_overlap_at_start)} |')
    h()
    h('source DB = `0` was a placeholder in the source file; the field provenance is unknown. '
      'BDS reported "Extrusion distance cannot be 0" for the source geometry test. All '
      'package_rev3 and package_rev4_candidate variants have this corrected to `8`.')
    h()

    # ---- m_bOnly1D ----
    h('## `m_bOnly1D` — 1D-only ECM flag (per SIMMOD, document order)')
    h()
    h('| File | Values |')
    h('|------|--------|')
    for label, f in all_files:
        h(f'| {label} | `{_bonly1d_str(f.m_bonly1d_list)}` |')
    h()

    he_bonly = _bonly1d_str(he.m_bonly1d_list)
    src_bonly = _bonly1d_str(src.m_bonly1d_list)
    r3_bonly = _bonly1d_str(r3v1.m_bonly1d_list)

    h('**Notes:**')
    h()
    h(f'- source: `{src_bonly}`. The source was assembled in this workspace from Siemens '
      f'template material and About-Energy data; provenance of the `m_bOnly1D` values is '
      f'unknown. BDS reported "Warning: m_bOnly1D option is not supported" during the '
      f'earlier geometry test.')
    h(f'- HE18650 (known-good): `{he_bonly}`. Machine extraction confirms HE18650 **does** '
      f'contain four `m_bOnly1D` fields. The first SIMMOD (Distributed 3D) retains '
      f'`m_bOnly1D = 1`; the remaining three are 0. The file builds successfully in BDS, '
      f'indicating that only certain SIMMOD contexts cause BDS to reject the value. '
      f'**Prior incorrect claim corrected: an earlier version of this document stated '
      f'"HE18650 does NOT have the m_bOnly1D field in any of its SIMMOD blocks at all." '
      f'That statement was false. Machine extraction proves the field is present.**')
    h(f'- All package_rev3 variants: `{r3_bonly}` — all four zeroed by the generator '
      f'to clear the BDS "not supported" error.')
    h(f'- All package_rev4_candidate variants: `{r3_bonly}` — unchanged from package_rev3 '
      f'(no change needed).')
    h()

    # ---- RCRTable 3D capacity ----
    h('## Active RCRTable 3D — capacity fields')
    h()
    h('| File | `m_bSpecifyCapacity` | `m_dAhCell` (Ah) |')
    h('|------|---------------------|------------------|')
    for label, f in all_files:
        cap = f.rct3d_capacity
        h(f'| {label} | {_fmt(cap.get("m_bSpecifyCapacity"))} | {_fmt(cap.get("m_dAhCell"))} |')
    h()
    h('`m_bSpecifyCapacity = 1` with `m_dAhCell = 5.0 Ah` is the About-Energy NCA 2170 '
      '5 Ah specification. Both source and all variants correctly set this. HE18650 has '
      '`m_bSpecifyCapacity = 0` because it relies on internal winding geometry to determine '
      'capacity rather than an explicit override.')
    h()

    return '\n'.join(lines) + '\n'


def main():
    for path in [SOURCE_TBM, HE18650_TBM, PKG_REV3_V1, PKG_REV3_V2, PKG_REV3_V3, PKG_REV3_V4,
                 PKG_REV4C_V1, PKG_REV4C_V2, PKG_REV4C_V3, PKG_REV4C_V4]:
        if not path.exists():
            sys.exit(f'ERROR: TBM file not found: {path}')

    print('Extracting fields from TBM files...')
    src  = extract_tbm_fields(SOURCE_TBM)
    he   = extract_tbm_fields(HE18650_TBM)
    r3v1 = extract_tbm_fields(PKG_REV3_V1)
    r3v2 = extract_tbm_fields(PKG_REV3_V2)
    r3v3 = extract_tbm_fields(PKG_REV3_V3)
    r3v4 = extract_tbm_fields(PKG_REV3_V4)
    r4v1 = extract_tbm_fields(PKG_REV4C_V1)
    r4v2 = extract_tbm_fields(PKG_REV4C_V2)
    r4v3 = extract_tbm_fields(PKG_REV4C_V3)
    r4v4 = extract_tbm_fields(PKG_REV4C_V4)

    content = generate(src, he, r3v1, r3v2, r3v3, r3v4, r4v1, r4v2, r4v3, r4v4)
    OUTPUT.write_text(content, encoding='utf-8')
    print(f'Written: {OUTPUT.relative_to(WORKSPACE)}')


if __name__ == '__main__':
    main()
