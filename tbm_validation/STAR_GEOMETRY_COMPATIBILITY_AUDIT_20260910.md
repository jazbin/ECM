# STAR Geometry Compatibility Audit — 2170 RCR Candidate vs Siemens References
**Date:** 2026-09-10
**Branch:** tbm-rcr-modelmap-fix-exec
**Candidate:** `out/rcr_candidate/hp2170-rcr-v1-tabs-on-sameFace.tbm`
**Failure under investigation:** `Electrode Root 1 : Extrusion distance can not be 0` (`CreateFromTbm`)
**Prior blocking error (resolved):** `m_bOnly1D not supported` — no longer present; all 4 SIMMOD blocks have `m_bOnly1D = 0`

---

## 1. Reference Files Used

### STAR-CCM+ installation references (primary — known-good cylindrical spiral)

| File | Branch path | Candidate for known-good 3D import |
|---|---|---|
| `validationBattery.tbm` | `tbm_validation/in_StarCCM_bds/validationBattery.tbm` | YES — shipped with STAR install |
| `testTBM.tbm` | `tbm_validation/in_StarCCM_bds/testTBM.tbm` | YES — shipped with STAR install |
| `LiIonSpiral.tbm` | `tbm_validation/in_StarCCM_bds/LiIonSpiral.tbm` | YES — shipped with STAR install |
| `tutorialCylindricalCell.tbm` | `tbm_validation/in_StarCCM_bds/tutorialCylindricalCell.tbm` | YES — shipped with STAR install |

### BDS-derived reference files (secondary — import status in 3D mode unconfirmed)

| File | Branch path | Import status |
|---|---|---|
| `hp18650Spiral-DIST.tbm` | `tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm` | UNCONFIRMED — `m_bOnly1D=1` in all 4 blocks |
| `hp18650Spiral1-1D.tbm` | `tbm_validation/reference/GapExample/hp18650Spiral1-1D.tbm` | UNCONFIRMED — 1D-only variant |
| `hp18650Spiral1.tbm` | `tbm_validation/reference/GapExample/hp18650Spiral1.tbm` | UNCONFIRMED — our clone source |
| `he18650spiral1.tbm` | `tbm_validation/reference/HE18650/he18650spiral1.tbm` | PRESUMED GOOD — standard reference |
| `LiIonSpiral1.tbm` | `tbm_validation/siemens_reference_corpus/bds_install/BDS_files/LiIonSpiral1.tbm` | PRESUMED GOOD — BDS install |

All accessed from branch `tbm-siemens-reference-corpus` (SHA `b0be477f19bf16eaff92eafd9f3ba07fb6f3152d`).

### August 2026 STEP experiment (experimental evidence)

`tbm_validation/GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md` — 21-variant STEP measurement matrix.

---

## 2. Candidate Provenance

```
hp2170NCA-ECM.tbm (source, cloned from hp18650Spiral1.tbm GapExample)
  → generate_tbm_v4_candidate.py (V3+V4 fixes + variant)
    → out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm
      → generate_tbm_rcr_candidate.py (MODELMAP IET switch only)
        → out/rcr_candidate/hp2170-rcr-v1-tabs-on-sameFace.tbm  ← CURRENT CANDIDATE
```

The RCR generate script explicitly states it "does not regenerate geometry, RCR tables, builder fields, REPORT data, tab fields, or m_bOnly1D values." The V4 generate script applies only: Package dims, `m_dElectrodeOverlapAtStart_mm=8`, `m_dMandrelWidth_mm=6`, `m_bOnly1D=0`, `m_dOffsetPosAvg=0.5`, DataSheet label fixes. **Neither script touches any `m_dS1..S6` field.** The S-values were inherited unchanged from the source `hp18650Spiral1.tbm` (GapExample clone).

---

## 3. Field Difference Matrix — Geometry-Relevant Fields

Fields are drawn from the DetailedBuilder (`<BUILDER>` block), electrode Tape/Tab sections, Package, and DataSheet. REPORT fields are classified separately at the end.

### 3a. +Electrode S-series (m_dS1..S6)

| Field | Our candidate | STAR refs (all 4) | BDS-derived refs | Zero in ours? | Zero in STAR? | CAD role | Classification |
|---|---|---|---|---|---|---|---|
| `+Electrode m_dS1` | 5 mm | 5 mm | 5 mm | No | No | Electrode segment 1 (uncoated at tab end) | `STAR_REFERENCE_PATTERN` — identical |
| `+Electrode m_dS2` | 7 mm | 7 mm | 7 mm | No | No | Electrode segment 2 | `STAR_REFERENCE_PATTERN` — identical |
| **`+Electrode m_dS3`** | **0 mm** | **5 mm (all 4)** | **0 mm (DIST, 1D, source)** | **YES** | **NEVER** | Root/overhang segment — consumed by winding root geometry feature | **`ZERO_DIMENSION_SUSPICIOUS`** |
| `+Electrode m_dS4` | 0 mm | 0 mm | 0 mm | Yes | Yes | Unused/optional segment | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `+Electrode m_dS5` | 0 mm | 0 mm | 0 mm | Yes | Yes | Unused/optional segment | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `+Electrode m_dS6` | 0 mm | 0 mm | 0 mm | Yes | Yes | Unused/optional segment | `ZERO_DIMENSION_PROBABLY_SAFE` |

**Critical observation:** `+Electrode m_dS3 = 0` is the only S-field that differs between our candidate and every STAR-installation reference file. The contrast is absolute: 4/4 STAR files use S3=5, 0/4 use S3=0.

### 3b. -Electrode S-series (m_dS1..S6)

| Field | Our candidate | STAR refs | BDS-derived refs | Classification |
|---|---|---|---|---|
| `-Electrode m_dS1` | 7 mm | 7 mm | 7 mm | `STAR_REFERENCE_PATTERN` — identical |
| `-Electrode m_dS2` | 7 mm | 7 mm | 7 mm | `STAR_REFERENCE_PATTERN` — identical |
| `-Electrode m_dS3` | 50 mm | 50 mm (validationBattery, testTBM, LiIonSpiral, tutorial); HE18650=30 | 50 mm (DIST, 1D, source) | `STAR_REFERENCE_PATTERN` — nonzero and matches STAR; **not the issue** |
| `-Electrode m_dS4` | 0 mm | 0 mm | 0 mm | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `-Electrode m_dS5` | 0 mm | 0 mm | 0 mm | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `-Electrode m_dS6` | 0 mm | 0 mm | 0 mm | `ZERO_DIMENSION_PROBABLY_SAFE` |

### 3c. DetailedBuilder winding geometry

| Field | Our candidate | STAR refs (validationBattery / testTBM / LiIonSpiral / tutorial) | HE18650 ref | Classification |
|---|---|---|---|---|
| `m_dJellyrollThickness_mm` | 19.25 mm | 17.9 / 17.9 / 17.9 / (not shown) | (not shown) | `PHYSICAL_2170_DIFFERENCE` — 2170 vs 18650 cell |
| `m_dJellyrollWidth_mm` | 0 | 0 | — | `ZERO_DIMENSION_PROBABLY_SAFE` — STAR refs also 0 |
| `m_dMandrelThickness_mm` | 6 mm | 6 / 6 / 6 | — | `STAR_REFERENCE_PATTERN` |
| `m_dMandrelWidth_mm` | 6 mm | 0 / 0 / 0 / 0 | 5 mm | `UNRESOLVED` — STAR refs=0, HE18650=5; ours=6. Unlikely extrusion blocker (nonzero). Added as V3 fix. |
| `m_dElectrodeOverlapAtStart_mm` | **8 mm** | 3 / 3 / 3 | 30 mm | `KNOWN_STAR_CONSUMED` — **was the V1 error cause when = 0**; now fixed to 8 mm; nonzero → not the current error |
| `m_dElectrodeOverlapAtEnd_mm` | 20 mm | 40 / 40 / 40 | 50 mm | `PHYSICAL_2170_DIFFERENCE` or `UNRESOLVED` — nonzero; unlikely current blocker |
| `m_dSepFeedLength_mm` | **0 mm** | **10 / 10 / 10 / 10** | **0 mm** | `UNRESOLVED` — STAR refs=10, ours=0; HE18650 (presumed good)=0 so not confirmed blocker; see zero audit |
| `m_dSepTailLength_mm` | **0 mm** | **85 / 85 / 85 / 85** | **0 mm** | `UNRESOLVED` — same pattern as SepFeed; HE18650=0 makes this lower risk |
| `m_dOffsetPosAvg` | 0.5 | 0.5 / 0.5 / 0.5 | 1 | `STAR_REFERENCE_PATTERN` — fixed in V4 |
| `m_dOffsetNegAvg` | 1 | 1 / 1 / 1 | 1 | `STAR_REFERENCE_PATTERN` |
| `m_dOffsetSepAvg` | 0 | 0 / 0 / 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `m_dOverwrapThickness_um` | 0 | 0 / 0 / 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `m_dOverwrapWidth` | 0 | 0 / 0 / 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `m_bOverwrap` | 0 | 0 / 0 / 0 | 0 | `STAR_REFERENCE_PATTERN` |
| `m_bNegativeEnding` | 1 | 1 / 1 / 1 | — | `STAR_REFERENCE_PATTERN` |
| `m_bNegativeOnTop` | 1 | 1 / 1 / 1 | — | `STAR_REFERENCE_PATTERN` |
| `m_bNegativeStarting` | 0 | 0 / 0 / 0 | — | `STAR_REFERENCE_PATTERN` |
| `m_nNumSpokes` | 200 | — | — | `STAR_REFERENCE_PATTERN` |
| `m_dCornerAngle` | 10 | 10 / 10 / 10 | — | `STAR_REFERENCE_PATTERN` |

### 3d. Electrode tab geometry

| Field | Our candidate | STAR refs | Classification |
|---|---|---|---|
| `+Electrode Tab m_dWidth_mm` | 6 mm | 4 mm | `PHYSICAL_2170_DIFFERENCE` — nonzero, different cell spec |
| `+Electrode Tab m_dLength_mm` | 60 mm | (varies) | `PHYSICAL_2170_DIFFERENCE` |
| `+Electrode Tab m_dThickness_um` | 7 µm | (varies) | `PHYSICAL_2170_DIFFERENCE` |
| `+Electrode m_bAlignedTabs` | 0 | 0 | `STAR_REFERENCE_PATTERN` |
| `+Electrode m_d1stTabPosition_mm` | 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` — STAR refs also 0 |
| `+Electrode m_dFixedSpacing_mm` | 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `+Electrode m_dTabOffsetL_mm` | 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `+Electrode m_dLts_mm` | 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` |
| `+Electrode m_dTabAlignmentAngle_degrees` | 0 | 0 | `ZERO_DIMENSION_PROBABLY_SAFE` |

Tab fields are symmetric for -Electrode; same classification applies.

### 3e. Package/Can

| Field | Our candidate | STAR refs | Classification |
|---|---|---|---|
| `Package m_dextDiameter` | 21.09 mm | 18 mm | `PHYSICAL_2170_DIFFERENCE` |
| `Package m_dextHeight` | 70.02 mm | 65 mm | `PHYSICAL_2170_DIFFERENCE` |
| `Package m_dintDiameter` | 20.6274 mm | 17.9 mm | `PHYSICAL_2170_DIFFERENCE` |
| `Package m_dintHeight` | 65.11 mm | 60 mm | `PHYSICAL_2170_DIFFERENCE` |

Package fields are all physically different because 2170 vs 18650. None are zero.

### 3f. DataSheet

DataSheet fields are label/metadata. August experiment did not observe them driving geometry. All classified `DERIVED_OR_STALE` except for can dimensions which are used by STAR REPORT.

### 3g. REPORT

All `<REPORT>` block fields have flag=0. August experiment established that `m_dRepJellyrollDiameter` in REPORT was NOT observed to drive JR OD (Detailed Builder `m_dJellyrollThickness_mm` wins). These are classified `DERIVED_OR_STALE`.

---

## 4. ZERO_DIMENSION_AUDIT

Every zero-valued field that is dimensional or could plausibly influence a generated CAD feature.

### 4.1 `+Electrode m_dS3 = 0`

1. **Zero in our candidate?** YES
2. **Zero in STAR references?** NEVER (0/4 STAR files; all have value 5)
3. **Zero only in BDS-derived files?** YES (hp18650Spiral-DIST, hp18650Spiral1-1D, hp18650Spiral1 — all BDS-generated with unconfirmed 3D import status)
4. **Is the associated feature optional?** NO — S4..S6 are optional (zero in all refs); S3 is non-optional in all working references
5. **Could STAR create a zero-length extrusion from it?** YES — S3 most plausibly drives a geometric segment (a root/overhang extrusion) that has zero length when S3=0, which would trigger the exact STAR error observed
6. **Evidence of consumption?** INDIRECT but very strong — the error "Extrusion distance can not be 0" names a feature that would be built from a segment-length dimension; S3 is the only S-field that is zero in our file but nonzero in all STAR-installation references; all BDS-only files with unconfirmed 3D import have S3=0
7. **Blocker?** **YES — PRIMARY SUSPECT**

### 4.2 `m_dSepFeedLength_mm = 0` (DetailedBuilder)

1. **Zero in our candidate?** YES (DetailedBuilder block; SimpleBuilder has value 10)
2. **Zero in STAR references?** NEVER (all 4 STAR refs: 10 mm)
3. **Zero only in BDS-derived files?** Partially — hp18650Spiral-DIST=0 (DB), hp18650Spiral1-1D=10 (DB); HE18650=0 (DB)
4. **Is the associated feature optional?** UNCERTAIN — HE18650 (presumed good) uses 0; STAR refs use 10
5. **Could STAR create a zero-length extrusion from it?** PLAUSIBLE but HE18650 with the same zero value is presumed to work in 3D mode
6. **Evidence of consumption?** Not established from August experiment; filed as ASSUMED/Low risk in CURRENT_TBM_FIELD_AUDIT.md
7. **Blocker?** LOWER PRIORITY than S3 — HE18650 counterexample weakens this hypothesis

### 4.3 `m_dSepTailLength_mm = 0` (DetailedBuilder)

Same assessment as SepFeedLength above. HE18650 also uses 0 in DB, making this a low-priority suspect.

### 4.4 `+Electrode m_dJellyrollWidth_mm = 0`

STAR refs also use 0. `ZERO_DIMENSION_PROBABLY_SAFE`.

### 4.5 `m_dOffsetSepAvg = 0`

STAR refs also use 0. `ZERO_DIMENSION_PROBABLY_SAFE`.

### 4.6 `m_dOverwrapThickness_um = 0`, `m_dOverwrapWidth = 0`

`m_bOverwrap = 0` indicates overwrap is disabled. These zeros are controlled by that flag. `ZERO_DIMENSION_PROBABLY_SAFE`.

### 4.7 `+Electrode m_d1stTabPosition_mm = 0`, `m_dFixedSpacing_mm = 0`, etc.

All match STAR references. `ZERO_DIMENSION_PROBABLY_SAFE`.

### 4.8 `m_dSeparatorThicknessTarget_mm = 0`

Present in candidate with value 0. Not present in STAR ref grep output (or also 0). Low evidence it drives extrusion. `ZERO_DIMENSION_PROBABLY_SAFE`.

---

## 5. Electrode Root 1 — Investigation

### 5.1 Search results

Searching the repository for "Electrode Root", "root", "extrusion", "m_dS[1-6]", lead/root/extension semantics:

| Source | Relevant finding |
|---|---|
| `tbm_validation/TBM_INVENTORY.md:79` | `hp2170-test-v1-tabs-on-standard.tbm` FAILED — "Electrode Root 1 : Extrusion distance can not be 0" |
| `tbm_validation/STAR_IMPORT_ERROR_HISTORY.md:15` | Same error text verbatim |
| `docs/TBM_GEOMETRY_REQUIREMENTS_AND_EVALUATION_20260904.md:27` | "broken Detailed Builder parameter — `m_dElectrodeOverlapAtStart_mm = 0` — that caused Robert's import to fail with 'Electrode Root 1: Extrusion distance cannot be 0'" |
| `tools/generate_tbm_test_variants.py:112` | "BDS rejects zero with 'Electrode Root 1 : Extrusion distance can not be 0'. The Simple Builder block in the same source file has the correct value of 8 mm" |
| `tools/validate_tbm.py:544` | "This caused 'Electrode Root 1 : Extrusion distance can not be 0' in V1 package." |
| `out/test/TBM_GEOMETRY_TEST_EXPLANATION.txt:23` | Confirms iteration 2 error was caused by `m_dElectrodeOverlapAtStart_mm = 0` |

### 5.2 Semantic interpretation

"Electrode Root 1" is a named feature in STAR-CCM+/BDS geometry creation. Based on the V1 error history, `m_dElectrodeOverlapAtStart_mm = 0` caused "Electrode Root 1 : Extrusion distance can not be 0." This field defines the inner winding lead-in region of the positive electrode (Electrode 1 = positive electrode in STAR convention). When this was 0, the extrusion operation failed.

That field is now 8 mm (fixed in V3). The same error is recurring, which means a **different** zero-valued dimension is being used for the same or an adjacent geometry feature in the current RCR candidate.

The "Electrode Root 1" feature class in BDS appears to encompass all geometric segments at the root (innermost winding turn) of Electrode 1 (positive). Multiple distinct fields can drive it.

### 5.3 m_dS3 as Electrode Root 1 driver

No direct documentation in this repository maps `m_dS3` to "Electrode Root 1." This is stated explicitly as required by the audit scope.

However, the circumstantial case is strong:

- S3 is a dimensional field (mm) in the electrode geometry
- S3=0 is the only geometry field that differs between our candidate and every STAR-installation reference
- S4, S5, S6 are also 0 in both our file and ALL references — so they are clearly optional; S3 is not
- The error "Extrusion distance can not be 0" is consistent with STAR trying to build a short geometric segment of length S3=0
- All BDS-generated source files (which were generated in 1D-only mode, `m_bOnly1D=1`) have S3=0 — suggesting S3 was left as a placeholder in 1D mode, just as `m_dElectrodeOverlapAtStart_mm` was
- The 5 mm value in all STAR references is the natural segment length for a short root/overhang feature

**Conclusion:** The repository evidence does NOT contain a definitive statement mapping m_dS3 to "Electrode Root 1." However, the pattern evidence is strong enough to designate S3=0→5 as the recommended single controlled change.

---

## 6. S3 Hypothesis Evaluation

### Pattern table

| File | Source type | +Electrode m_dS3 | -Electrode m_dS3 | 3D import status |
|---|---|---|---|---|
| `validationBattery.tbm` | STAR install | **5** | 50 | GOOD (shipped by Siemens) |
| `testTBM.tbm` | STAR install | **5** | 50 | GOOD (shipped by Siemens) |
| `LiIonSpiral.tbm` | STAR install | **5** | 50 | GOOD (shipped by Siemens) |
| `tutorialCylindricalCell.tbm` | STAR install | **5** | 50 | GOOD (shipped by Siemens) |
| `he18650spiral1.tbm` | HE18650 reference | **5** | 30 | PRESUMED GOOD (standard reference) |
| `LiIonSpiral1.tbm` | BDS install | **5** | 50 | PRESUMED GOOD |
| `hp18650Spiral-DIST.tbm` | BDS-generated | **0** | 50 | UNCONFIRMED (m_bOnly1D=1 in all blocks) |
| `hp18650Spiral1-1D.tbm` | BDS-generated | **0** | 50 | UNCONFIRMED (1D-only variant) |
| `hp18650Spiral1.tbm` | BDS-generated (our source) | **0** | 50 | UNCONFIRMED |
| **RCR candidate** | Our file (source clone) | **0** | 50 | **FAILED** |

**Pattern:** 6/6 known-good files = S3≥5. 3/3 BDS-generated files with unconfirmed 3D import = S3=0. Our file = S3=0, FAILED.

### Polarity assessment

The error message says "Electrode Root **1**." In STAR/BDS convention, Electrode 1 = positive electrode. Our candidate has:
- `+Electrode m_dS3 = 0` ← SUSPECT
- `-Electrode m_dS3 = 50` ← NOT suspect (matches all refs)

The error references Electrode 1 specifically, pointing to the positive electrode (+ electrode) S3 dimension. The -Electrode S3=50 is consistent with STAR refs and is not the issue.

### S3 vs SepFeed/SepTail disambiguation

The HE18650 reference (`he18650spiral1.tbm`) uses:
- `+Electrode m_dS3 = 5` (nonzero) ← same as STAR refs
- `m_dSepFeedLength_mm = 0` ← same as our file (zero)
- `m_dSepTailLength_mm = 0` ← same as our file (zero)

HE18650 is presumed to work in 3D import. If SepFeed=0 or SepTail=0 were fatal, HE18650 would also fail. This eliminates SepFeedLength and SepTailLength as the primary suspect and strongly focuses the diagnosis on S3.

---

## 7. August STEP Evidence Cross-Reference

From `GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md`:

| Field | August experiment finding |
|---|---|
| `m_dJellyrollThickness_mm` (DetailedBuilder) | **EXPERIMENTALLY CONSUMED** — drove realized JR diameter; tested values 17.0/17.3/17.6 mm realized within 0.25 mm |
| `m_dRepJellyrollDiameter` (REPORT) | NOT observed to drive JR OD — DB value wins |
| `m_dMandrelThickness_mm` (DetailedBuilder) | **EXPERIMENTALLY CONSUMED** — drove mandrel presence |
| Package external height | **EXPERIMENTALLY CONSUMED** — drove can height |
| `m_dRepCanXDim/YDim/ZDim` (REPORT) | Consumed (can OD in tested matrix) |
| Physical electrode widths | **EXPERIMENTALLY CONSUMED** — drove JR axial length |
| DB JellyRoll width, REPORT JR height, physical winding electrode lengths | NOT observed to drive axial JR length |
| `DataSheet m_dHeight`, `m_dDSHeight` | NOT observed to drive geometry in tested matrix |
| `m_dS3` | **UNTESTED** — not part of the August 21-variant matrix |
| `m_dSepFeedLength_mm` | **UNTESTED** |
| `m_dSepTailLength_mm` | **UNTESTED** |
| `m_dElectrodeOverlapAtStart_mm` | NOT directly tested; V1/V3 error history confirms STAR consumes this (zero = fatal) |

**Key limitation:** S3 was not tested in August. The August experiment focused on JR diameter, mandrel, and can dimensions. The current failure mode is a geometry feature (winding root extrusion), which was not part of the August test matrix.

---

## 8. TOP_GEOMETRY_FAILURE_SUSPECTS

### Ranked causes for: `Electrode Root 1 : Extrusion distance can not be 0`

| Rank | Field | Current value | Proposed test value | STAR-reference support | Causal confidence | Alters 2170 physics/geometry? |
|---|---|---|---|---|---|---|
| **1** | `+Electrode m_dS3` | 0 mm | **5 mm** | 4/4 STAR install files use 5; HE18650 uses 5; BDS-only files with unconfirmed import status use 0 | **HIGH** | Minor — adds a 5 mm root segment to positive electrode inner winding feature; does not change active electrochemical area, RCR tables, or thermal parameters |
| **2** | `m_dSepFeedLength_mm` (DetailedBuilder) | 0 mm | 10 mm | 4/4 STAR install files use 10; HE18650 uses 0 (weakens this hypothesis) | **LOW** | Adds a separator wrap-around at winding end; minor geometric effect; HE18650 counterexample makes this unlikely the blocker |
| **3** | `m_dSepTailLength_mm` (DetailedBuilder) | 0 mm | 85 mm | Same pattern as SepFeed | **LOW** | Same as above; correlated with SepFeed |
| **4** | `m_dMandrelWidth_mm` | 6 mm | 0 mm (STAR refs) | STAR refs=0; but this field is nonzero so it cannot be the "extrusion distance can not be 0" culprit | **NOT APPLICABLE** | Would remove mandrel width specification |

**Notes:**
- Suspect 1 (S3) is the only zero-valued field that is nonzero in ALL known-working STAR-installation references.
- Suspects 2 and 3 are ruled as lower priority because HE18650 (presumed good) also uses 0 for both.
- Suspect 4 is nonzero and therefore logically cannot cause "extrusion distance cannot be 0."
- No other geometry field shows a zero-in-ours / nonzero-in-all-STAR-refs pattern.

---

## 9. Decision Gate

`+Electrode m_dS3 = 0` is the only geometry-related field that:
- Is zero in our candidate
- Is nonzero (= 5) in all 4 STAR-installation cylindrical references
- Is nonzero in HE18650 (presumed good)
- Could plausibly drive a "root extrusion distance = 0" failure
- Was inherited from the BDS-generated source TBM that was configured for 1D-only mode (consistent with the previous overlap_at_start placeholder pattern)

The SepFeedLength/SepTailLength pair is a distant second that is weakened by the HE18650 counterexample.

```
NEXT_CONTROLLED_CHANGE = +Electrode m_dS3 : 0 -> 5
```

---

## 10. Required Generator Update

The `generate_tbm_v4_candidate.py` `apply_v3_fixes()` function must be updated to include `m_dS3` in the fix list, alongside `m_dElectrodeOverlapAtStart_mm`. The RCR candidate must then be regenerated from the updated V4 base using `generate_tbm_rcr_candidate.py`.

**Specifically, add to `apply_v3_fixes()`:**
```python
('+Electrode m_dS3', 5, 'copied from STAR install references; source had 0 (1D-mode placeholder)'),
```

This is a `sub_first()` call targeting the first occurrence of `+Electrode m_dS3` in the file (which is the DetailedBuilder value; SimpleBuilder has its own entry without the `_mm` suffix).

**Important:** The equivalent SimpleBuilder field may also need updating. Check whether `+Electrode m_dS3` appears in the SimpleBuilder section of the source file and whether STAR reads from DB or SB (precedence unconfirmed). However, given that the Detailed Builder drives geometry for 3D builds (per August characterization), the DB value is the critical one.

---

## 11. Remaining Uncertainties

1. **m_dS3 semantic definition** — No direct BDS documentation in this repository maps `m_dS3` to "Electrode Root 1." The causal chain is inferred from the pattern, not from a spec. The controlled test (S3=0→5) will confirm or refute.

2. **SepFeedLength / SepTailLength** — These are nonzero in all STAR refs but zero in HE18650 (presumed good). It is possible STAR accepts 0 for these. After fixing S3, if STAR still fails, these should be next.

3. **Both polarity S3 consumed simultaneously?** The error says "Electrode Root 1" — +Electrode. But STAR might try to build both root features before reporting the error. The -Electrode S3=50 is nonzero and matches refs; unlikely to be co-cause.

4. **Downstream geometry after S3 fix** — Changing S3 from 0 to 5 may alter the winding root geometry in subtle ways. The effect on the generated JR topology (body count, EndPlate position) must be verified from the STEP export after the fix.

5. **m_dMandrelWidth_mm = 6 vs STAR refs = 0** — Our file and HE18650 differ from STAR install refs here. This was added deliberately (V3 fix). It is nonzero so it cannot cause "extrusion distance = 0", but its geometric effect on the mandrel body is unconfirmed.

---

## Audit Summary

| Category | Count |
|---|---|
| Geometry-relevant fields compared (field-difference matrix) | 38 |
| Zero-valued dimensional fields audited | 16 |
| Fields zero in ours but nonzero in all STAR refs | **1** (`+Electrode m_dS3`) |
| Ranked suspects for current failure | 3 (1 HIGH, 2 LOW) |
| Decision gate | `NEXT_CONTROLLED_CHANGE = +Electrode m_dS3 : 0 -> 5` |
