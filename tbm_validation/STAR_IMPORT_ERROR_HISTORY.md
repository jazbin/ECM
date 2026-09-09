# STAR-CCM+ Import Error History

Every known STAR-CCM+ import failure, in chronological order. All errors were reported by Robert (end client) who runs STAR-CCM+ with the Battery Design Studio (BDS) plugin. The import operation is "File > Create from Tbm".

Reproducing these errors requires STAR-CCM+ + BDS. We cannot reproduce them in this environment.

---

## Error 1 — "Extrusion distance can not be 0" — v1 package (2026-09-04)

**Package:** v1 (`tbm_geometry_test_20260904.zip`)
**Affected TBMs:** All 4 variants (SHA listed in TBM_INVENTORY.md, v1 section)
**Error text (verbatim, from Robert's log):** `Electrode Root 1 : Extrusion distance can not be 0`
**Stage:** BDS 3D geometry builder, during "Create from Tbm"
**How reported:** Robert reported "Same error for all four cases"

**Diagnosis:** `m_dElectrodeOverlapAtStart_mm = 0` in the Detailed Builder block. This field controls the initial electrode extension length (the "extrusion" of the spiral wind start). Setting it to 0 leaves BDS with no valid winding start geometry.

**Root cause:** The source TBM `hp2170NCA-ECM.tbm` had this field at 0 in the Detailed Builder block. The corresponding field in the Simple Builder block (`m_dElectrodeOverlapAtStart`, no `_mm` suffix) was 8 mm, but the Detailed Builder block was apparently not populated when the source TBM was built. The difference in field name (`_mm` suffix vs none) means a global regex replace on the name without the suffix does not reach the Detailed Builder occurrence.

**Fix applied:** `apply_common_fixes()` in `generate_tbm_test_variants.py` now sets `m_dElectrodeOverlapAtStart_mm = 8` (using the `sub_first()` function which targets the Detailed Builder occurrence). Value 8 was copied from the Simple Builder block; it has not been independently confirmed from About-Energy cell spec data.

**Also fixed in same release:** `m_dMandrelWidth_mm = 0 → 6` (mandrel width set equal to mandrel thickness for cylindrical mandrel).

**Confirmed fixed in v2:** Yes — Robert did not report this error for the v2 package.

---

## Error 2 — "m_bOnly1D option is not supported" — v2 package (2026-09-07)

**Package:** v2 (`tbm_geometry_test_20260907.zip`)
**Affected TBMs:** All 4 variants (SHA listed in TBM_INVENTORY.md, v2 section)
**Error text (verbatim, from Robert's log):**
```
Warning: m_bOnly1D option is not supported
Warning: m_bOnly1D option is not supported
```
(Two occurrences — corresponding to two of the four SIMMOD blocks where `m_bOnly1D = 1`)

**Stage:** BDS processing during "Create from Tbm". After these two warnings the operation failed to complete 3D geometry creation.

**How reported:** Robert reported "Same error for all four cases I'm afraid" with the log showing two warning lines repeated.

**Diagnosis:** `m_bOnly1D = 1` in the SIMMOD blocks instructs BDS to treat the cell as a 1D-only electrochemical model. BDS's 3D distributed geometry builder cannot use a 1D-only electrochemical model and explicitly emits a "not supported" warning and aborts. The source TBM had `m_bOnly1D = 1` in all 4 SIMMOD blocks where this flag appears (`Distributed 3D`, `Distributed`, `NTGPTable 3D`, `RCRTable 3D`).

**Origin of wrong value:** The source TBM was cloned from the Siemens stock `hp18650Spiral1.tbm` template. In that template, `m_bOnly1D` has the pattern [1, false, 0, 0] — first block = 1, rest = 0/false. Somewhere in the creation of `hp2170NCA-ECM.tbm`, all four values became 1. Whether this happened during the initial BDS-assisted creation session or was inherited from a different template is not reconstructed. The DIST reference (`hp18650Spiral-DIST.tbm`) also has all 4 = 1, but its 3D import status is unknown.

**Fix applied:** `apply_common_fixes()` now calls `sub_all(content, 'm_bOnly1D', 0)` which sets ALL occurrences to 0. This is more conservative than the HE18650 template pattern [1, 0, 0, 0] (first block = 1). The reasoning: setting all to 0 is unambiguously 3D-compatible; setting first to 1 follows the template but its effect is unconfirmed. If STAR-CCM+ requires first=1 for some capability, this fix may need to be revised to [1, 0, 0, 0].

**Confirmed fixed in v3:** PENDING — Robert has not yet reported results for v3.

**Ambiguity note:** The correct pattern ([0,0,0,0] vs [1,0,0,0] vs [1,1,0,0]) is not confirmed from Siemens documentation. The HE18650 pattern [1,0,0,0] is used by a known-working reference but we do not know what setting first=1 enables or disables. This is flagged as UNCONFIRMED in `CURRENT_TBM_FIELD_AUDIT.md`.

---

## Errors not yet encountered (but known risks)

These are not confirmed errors — they are predicted based on still-open field issues:

| Risk | Field | Current value | Impact if wrong |
|---|---|---|---|
| JellyRoll-Can gap | `m_dJellyrollThickness_mm` | 19.25 mm (1.38 mm gap to can ID) | BDS may generate JellyRoll that doesn't contact the Can inner surface. Unknown if this causes an error or just wrong geometry. |
| Capacity wrong | `m_bSpecifyCapacity = 0` | Capacity derived from geometry | If JR geometry dims are not all correct for 2170, derived capacity will be wrong without error. |
| Separator lengths | `m_dSepFeedLength_mm = 0`, `m_dSepTailLength_mm = 0` | 0 | Unknown effect. HE18650 also has 0 (field absent). May be correct for cylindrical mandrel. |
| Electrode overlap at end | `m_dElectrodeOverlapAtEnd_mm = 20` | 20 mm | Not confirmed from cell spec. If wrong, winding end geometry will be incorrect. |
| DataSheet height | `DataSheet m_dDSHeight = 65` | 65 mm | Label field only — does not drive geometry. But inconsistency with can height (70.02) is suspicious. |
