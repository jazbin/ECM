# TBM Structural Comparison

Field-by-field comparison of our working TBM (`hp2170NCA-ECM.tbm` source, before generate script fixes) against the primary known-good reference (`HE18650/he18650spiral1.tbm`). Secondary comparison against the clone template (`GapExample/hp18650Spiral1.tbm`) and the distributed reference (`HP18650/hp18650Spiral-DIST.tbm`) where relevant.

This document focuses on fields that differ or are suspicious, not exhaustive enumeration.

---

## 1. SIMMOD block structure

| | Our source | HE18650 ref | HP18650 template | HP18650-DIST |
|---|---|---|---|---|
| Total SIMMOD blocks | 24 | 9 | ~20+ | ~20+ |
| Block types | Distributed 3D, Distributed, NTGPTable 3D, RCRTable 3D, Lump, Dual, Abuse, NTG3D, RCR 3D, RCR3D TInterp, LumpIDA, NTGP3D, Nelson, Dual 2P, Distributed, Lump 2D, Dist 2D, NTG 1D, BDS_SimpleEquilFit, RCRTinterp 3D, General Electrolyte, LiIon, LiIon\Spiral, BDS_SimpleFormation | General Electrolyte, LiIon, LiIon\Spiral, Distributed, Lump, Dual, Abuse, Distributed 2P | Similar to our source | Similar to our source |

The reviewer should note that HE18650 has far fewer SIMMOD blocks. This means HE18650 has a simplified electrochemical model set. Our TBM (cloned from HP18650 template) has a full set of alternative SIMMOD blocks. The active physics model is determined by what STAR-CCM+ selects based on the study configuration — the additional blocks are not used automatically. No evidence that extra blocks cause import problems, but it is an unconfirmed difference.

---

## 2. `m_bOnly1D` — electrochemical mode flag

The most important flag for 3D distributed operation.

| SIMMOD block position | Our source (before v3 fix) | Our v3 variants | HE18650 ref | HP18650 template | HP18650-DIST |
|---|---|---|---|---|---|
| Block 1 (Distributed 3D / first block) | `1` | `0` | absent | `1` | `1` |
| Block 2 (Distributed) | `1` | `0` | absent | `false` | `1` |
| Block 3 (NTGPTable 3D) | `1` | `0` | absent | `0` | `1` |
| Block 4 (RCRTable 3D) | `1` | `0` | absent | `0` | `1` |

**HE18650 does not contain `m_bOnly1D` at all.** This means the field is absent in the known-good reference. Our TBM (cloned from HP18650 template) inherits this flag from the HP18650 template, where it was set to [1, false, 0, 0].

The HP18650-DIST reference has all = 1, but its import status in 3D mode is unknown.

**Our v3 fix sets all to 0 (more conservative than template [1,false,0,0]).** Whether the first-block value matters (1 vs 0) is unresolved from documentation.

**Risk:** If BDS interprets first-block `m_bOnly1D = 1` as enabling a capability (not just a flag to disable 3D), setting it to 0 may disable something. This is flagged as UNCONFIRMED.

---

## 3. Package block dimensions

| Field | Our source | Correct 2170 | HE18650 ref | Note |
|---|---|---|---|---|
| `Package m_dextDiameter` | 21.09 | 21.09 | 18.58 | Correctly set for 2170 in source |
| `Package m_dextHeight` | 70.02 | 70.02 | 65.0 | Correctly set for 2170 in source |
| `Package m_dintDiameter` | 17.8 | 20.6274 | 17.8 | **Wrong in source** — this is the 18650 can ID, not 2170 |
| `Package m_dintHeight` | 60 | 65.11 | 58.0 | **Wrong in source** — 18650 value retained |
| `Package m_strName` | `18650` | `2170` | `18650` | **Wrong in source** — name not updated |

Note: `m_dintDiameter = 17.8` in the source is the stock 18650 can internal diameter. It was not updated when the external dimensions were set to 2170 values. This is a clear 18650-residual.

---

## 4. Detailed Builder — winding geometry

| Field | Our source | Correct 2170 | HE18650 ref | Note |
|---|---|---|---|---|
| `m_dJellyrollThickness_mm` | 19.25 | ~20.627 (can ID) | ~17.9 | **Still wrong** — not fixed by generate script. 1.38 mm gap to can ID. |
| `m_dMandrelThickness_mm` | 6.0 | 6.0 (cell spec) | ~3.0 | Correct for 2170. Differs from 18650 reference (expected). |
| `m_dMandrelWidth_mm` | 0 → (6 via fix) | 6 (= mandrel thickness, cylindrical) | absent | Was 0 in source. Fixed to 6 in generate script. HE18650 template does not have this field. |
| `m_bMandrelFlat` | 0 | 0 (cylindrical) | 0 | Correct. |
| `m_dElectrodeOverlapAtStart_mm` | 0 → (8 via fix) | 8 mm (from Simple Builder) | ~5 | Was 0 in source. Fixed to 8 in generate script. 8 mm is from Simple Builder block in same source file; not confirmed from About-Energy. |
| `m_dElectrodeOverlapAtEnd_mm` | 20 | unknown | ~10 | Not fixed. Deviates from 18650 reference. Not confirmed from cell spec. |
| `m_dSepFeedLength_mm` | 0 | unknown | absent (0) | HE18650 also absent, so 0 may be valid. Unconfirmed. |
| `m_dSepTailLength_mm` | 0 | unknown | absent (0) | Same as above. |

---

## 5. Electrode collector widths (= axial active height)

| Field | Our source | Correct 2170 | HE18650 ref | Note |
|---|---|---|---|---|
| `+Electrode Collector m_dWidth_mm` | 64.11 | 64.11 (from About-Energy) | ~58 | Correct for 2170. |
| `-Electrode Collector m_dWidth_mm` | 65.11 | 65.11 (from About-Energy) | ~59 | Correct for 2170. |

These were updated when the electrochemistry was populated from `python/params.csv`. The values match the About-Energy characterisation data. They differ from 18650 reference as expected.

---

## 6. Tab configuration

| Field | Our source | Target (same-face) | HE18650 ref | Note |
|---|---|---|---|---|
| `m_bNegTab` | 1 | 1 | 1 | |
| `m_bPosTab` | 1 | 1 | 1 | |
| `m_nNegTabVertOrientation` | 1 (bottom) | 0 (top) | 1 (bottom) | **Source has standard (HE18650-matching) orientation; same-face requires 0.** Fixed per-variant by generate script. |
| `m_nPosTabVertOrientation` | 0 (top) | 0 (top) | 0 (top) | Correct. |

The source TBM has `m_nNegTabVertOrientation = 1` (bottom), matching the HE18650 reference. Our target configuration is same-face (both on top), requiring this to be 0. The generate script sets this per variant.

---

## 7. Electrochemical tables

| | Our source | HE18650 ref | Note |
|---|---|---|---|
| RCR temperature sets | 3 (288.15 / 298.15 / 308.15 K) | 3 (different temperatures) | Our temperatures match About-Energy data (15°C / 25°C / 35°C converted to K). |
| R0 range (Set[0]) | 0.00814–0.00862 Ω | different cell | About-Energy values. |
| OCV data | present | present | |
| Chemistry | NCA (2170) | Not NCA | Expected difference. |

The electrochemical content was populated from `python/params.csv` (About-Energy characterisation). It replaced the HP18650 electrochemistry. This is the correct and intended difference.

---

## 8. DataSheet block

| Field | Our source | HE18650 ref | Note |
|---|---|---|---|
| `DataSheet m_dDSHeight` | 65 | 65 | Both have 65 mm. But our 2170 can is 70.02 mm tall. **This is an 18650 residual in our source** — the DataSheet height label field was not updated. It is a label field only (does not drive geometry), but the inconsistency is suspicious. |
| `DataSheet m_dDSDiameter` | 21 | 18 | Our source correctly updated. |

---

## 9. Fields present in template but absent or different in HE18650

The HP18650 template (our clone base) has fields that HE18650 does not. These were inherited by our TBM. Their effect is unverified:

- `m_bOnly1D` — as discussed above
- `m_dMandrelWidth_mm` — absent in HE18650; present in template with value 0
- Various SIMMOD blocks (15 extra types vs HE18650)

These differences are structural consequences of the clone template choice. The template (HP18650) is a more complex TBM than HE18650. It is unclear whether any of these extra fields cause problems in 3D import.
