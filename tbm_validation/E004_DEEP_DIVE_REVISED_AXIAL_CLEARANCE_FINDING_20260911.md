# E004 Deep-Dive — Revised Axial-Clearance Finding

**Date:** 2026-09-11  
**Project:** hp2170 NCA STAR-CCM+ distributed RCR TBM  
**Branch:** `tbm-rcr-modelmap-fix-exec`  
**Status:** Static/repository finding only. `E004` remains runtime-unresolved until STAR progresses past the error.

---

## 1. Executive finding

A second deep review of the Siemens TBM corpus materially changes the previous E004 hypothesis ranking.

The strongest remaining geometry hypothesis is now **not** that separator feed/tail values of `0/0 mm` are inherently invalid, and it is **not** that the separator may never exceed the package internal height.

The strongest project-specific anomaly is:

```text
Package m_dintHeight = 65.11 mm
-Electrode m_dWidth = 65.11 mm
```

which gives:

```text
Package internal height - negative electrode width = 0.00 mm
```

The runtime error is:

```text
Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
```

There is no public Siemens documentation exposing the internal CAD formula for `Electrode Root 1`, so the equality above is **not proof** that STAR literally computes the extrusion as `PackageHeight - NegativeWidth`. However, after eliminating other hypotheses and comparing against Siemens references, the zero negative-electrode axial margin is now the highest-value controlled test.

A second important finding is provenance-related: `Package m_dintHeight = 65.11 mm` was not obtained from an independent measurement of the STAR/BDS package cavity. The project assigned the package internal height from the 2170 jelly-roll / negative-collector active height. That modelling substitution therefore created the exact zero margin.

---

## 2. Why the previous feed/tail hypothesis is downgraded

Earlier work ranked:

```text
m_dSepFeedLength_mm = 0
m_dSepTailLength_mm = 0
```

as a leading E004 suspect because STAR-facing examples such as `LiIonSpiral.tbm` use positive values such as `10/85 mm`.

The broader Siemens corpus contains direct counterexamples.

### Siemens HE18650

The HE18650 Detailed Builder uses:

```text
m_dSepFeedLength_mm = 0
m_dSepTailLength_mm = 0
```

while retaining a normal cylindrical Detailed Builder configuration.

### Siemens HP18650

The stock `hp18650Spiral-DIST.tbm` Detailed Builder uses:

```text
m_dSepFeedLength_mm = 0
m_dSepTailLength_mm = 0
m_dElectrodeOverlapAtStart_mm = 0
m_dOffsetPosAvg = 1e-06
m_dMandrelWidth_mm = 0
```

and its `<DEFAULT BUILDER>` selects `Detailed Builder`.

The August 2026 geometry-characterization campaign used the stock HP18650 lineage and generated successful STEP geometry for the vast majority of controlled variants, establishing that these zero-valued Detailed Builder fields are not universal STAR geometry blockers.

### Revised interpretation

`feed/tail = 0/0` remains a legitimate compatibility probe because other Siemens lineages use positive values, but it is no longer defensible to describe nonzero separator feed/tail as a general requirement for successful cylindrical geometry construction.

Therefore:

```text
H004 feed/tail-alone hypothesis: DOWNGRADED
```

---

## 3. Why separator overhang above package internal height is not inherently invalid

The failed project baseline has:

```text
Package m_dintHeight = 65.11 mm
Separator width      = 67.11 mm
Negative width       = 65.11 mm
Positive width       = 64.11 mm
```

so:

```text
Package - Separator = -2.00 mm
Package - Negative  =  0.00 mm
Package - Positive  = +1.00 mm
```

The Siemens STAR validation reference uses:

```text
60 / 59 / 57 / 56 mm
```

for package / separator / negative / positive, giving:

```text
+1 / +3 / +4 mm
```

That initially suggested that positive clearance around every layer might be structurally required.

The Siemens HE18650 reference disproves that generalization:

```text
Package internal height = 60.0 mm
Separator width         = 61.3 mm
Negative width          = 59.3 mm
Positive width          = 58.3 mm
```

which gives:

```text
Package - Separator = -1.30 mm
Package - Negative  = +0.70 mm
Package - Positive  = +1.70 mm
```

Therefore a separator wider than the package internal height is not, by itself, an invalid Siemens cylindrical-cell pattern.

The more specific distinction is that the Siemens case preserves **positive electrode construction margins**, while the project makes the negative electrode exactly equal to the package internal height.

---

## 4. The layer hierarchy itself is normal

The project uses:

```text
Separator - Negative = 2.00 mm
Negative  - Positive = 1.00 mm
```

This hierarchy is preserved in Siemens references and is consistent with cylindrical-cell manufacturing practice: separator wider than the negative electrode, and negative electrode wider than the positive electrode.

Therefore the project should not shrink physical electrode widths merely to normalize the TBM unless STAR runtime evidence proves this is necessary.

This is especially important because STAR's RCR workflows can use active area when constructing absolute equivalent-circuit quantities. Changing physical electrode dimensions is therefore not necessarily a geometry-only change.

---

## 5. Why the zero negative-electrode margin is now the leading hypothesis

### 5.1 Runtime negative evidence

`E004` survived all of the following controlled changes:

- tabs enabled versus disabled;
- standard versus same-face tab orientation;
- `m_bOnly1D` cleanup;
- Detailed Builder start overlap corrected from zero;
- positive-electrode `m_dS3` corrected to a nonzero value;
- explicit `Transport Number sets = 0`;
- radial JR diameter changed from the earlier undersized value to exact package/can-ID equality.

These are therefore eliminated or strongly downgraded as sole causes.

### 5.2 Physical widths are actually consumed by STAR geometry generation

The August STEP characterization established that physical electrode widths drive the realized jelly-roll axial geometry, while Detailed Builder `m_dJellyrollWidth_mm` was not observed to control the realized cylindrical axial extent.

Therefore the equality:

```text
Package m_dintHeight == -Electrode m_dWidth
```

is not a coincidence between inactive metadata fields; both belong to geometry definitions consumed by the generated cell.

### 5.3 The equality was introduced by our translation choice

The project context records:

```text
Jelly-roll active height = 65.11 mm
```

from the OpenFOAM/reference-cell negative collector width.

The TBM translation then set:

```text
Package m_dintHeight = 65.11 mm
```

The reference data did not independently establish that the free internal BDS construction cavity is exactly 65.11 mm. Consequently, package-internal height and active negative-electrode height were made identical by the translation process.

This distinction matters because STAR/BDS may use the package internal height as a geometric construction envelope while the OpenFOAM value represents the macroscopic active jelly-roll height.

---

## 6. Highest-value next test: HE18650-equivalent axial margins

A better first axial test than immediately increasing package internal height to `68.11 mm` is:

```text
Package m_dintHeight: 65.11 -> 65.81 mm
```

while leaving all physical layer widths unchanged:

```text
Separator = 67.11 mm
Negative  = 65.11 mm
Positive  = 64.11 mm
```

The resulting margins are:

```text
65.81 - 67.11 = -1.30 mm
65.81 - 65.11 = +0.70 mm
65.81 - 64.11 = +1.70 mm
```

These exactly reproduce the Siemens HE18650 package-relative axial margins:

```text
Package - Separator = -1.30 mm
Package - Negative  = +0.70 mm
Package - Positive  = +1.70 mm
```

while preserving the project electrode and separator widths.

Recommended diagnostic filename:

```text
C18_AXIAL_CAVITY65p81_HE_MARGIN.tbm
```

### Interpretation

- **C18 PASS while baseline fails:** very strong evidence that zero negative-electrode/package margin is the E004 construction degeneracy.
- **C18 FAIL but C14 (`68.11 mm`) PASS:** merely making the negative margin nonzero is insufficient; STAR requires a larger axial construction envelope.
- **C18 and C14 FAIL while a Siemens control passes:** investigate broader PCD/Builder/model coupling rather than continuing scalar geometry guesses.

---

## 7. Revised E004 hypothesis ranking

| Rank | Hypothesis | Current assessment |
|---|---|---|
| 1 | `Package m_dintHeight == negative-electrode width` / zero negative axial construction margin | **HIGH** |
| 2 | Larger package axial construction envelope required beyond merely positive negative-electrode margin | **HIGH-MODERATE** |
| 3 | Physical Cell Description / Detailed Builder interaction | **MODERATE** |
| 4 | Separator feed/tail `0/0` contributes in this project/model context | **LOW-MODERATE** |
| 5 | Electrode overlap end / other secondary Detailed Builder differences | **LOW-MODERATE** |
| 6 | Tab enablement/orientation | **LOW / runtime-pruned** |
| 7 | Exact radial JR/package-ID equality | **VERY LOW / Siemens reference-supported** |
| 8 | `m_bOnly1D`, transport-number metadata, RCR payload as direct cause of E004 | **VERY LOW / runtime-pruned** |

These are engineering priors, not measured probabilities.

---

## 8. Recommended compact runtime campaign

Before another large test matrix, use a compact discriminating set:

1. untouched Siemens STAR `validationBattery.tbm` — environment/import-path control;
2. untouched Siemens `hp18650Spiral-DIST.tbm` — high-value control for zero feed/tail and other zero Detailed Builder fields;
3. `C18_AXIAL_CAVITY65p81_HE_MARGIN.tbm` — package height only, 65.81 mm;
4. `C14_AXIAL_CAVITY68p11.tbm` — package height only, 68.11 mm;
5. `C03_FEED10_TAIL85.tbm` — feed/tail only;
6. `C19_AXIAL_CAVITY65p81_FEED10_TAIL85.tbm` — C18 plus feed/tail;
7. `C15_AXIAL_CAVITY68p11_FEED10_TAIL85.tbm` — C14 plus feed/tail.

If all project cases fail while both Siemens controls pass, stop scalar tweaking and move to the Siemens Detailed-Builder / Physical-Cell-Description transplant tests (`C12` / `C13`) with the paired interpretation already documented in `E004_CAMPAIGN_INDEPENDENT_REVIEW_20260911.md`.

---

## 9. Production-model implication

This finding does **not** establish that the final production STAR model should contain a physical 0.70 mm or 3.00 mm air gap at the jelly-roll ends.

The governing objective remains OpenFOAM-ECM equivalence. STAR may need positive construction room to build electrode/root geometry while the final homogenized jelly-roll, can and cap are configured with the intended ideal macroscopic thermal contact.

Therefore distinguish:

```text
TBM physical-sheet construction dimensions
```

from:

```text
final macroscopic JellyRoll / Can / Cap geometry and thermal-contact topology
```

They are not necessarily the same geometric abstraction.

This distinction is now central to the next stage of the project.

---

## 10. Evidence files

Primary repository evidence used in this finding:

- `tbm_validation/GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md`
- `tbm_validation/STAR_IMPORT_ERROR_DATABASE.md`
- `tbm_validation/SIEMENS_CYLINDRICAL_TBM_GEOMETRY_PATTERN_FINDINGS_20260911.md`
- `tbm_validation/E004_CAMPAIGN_INDEPENDENT_REVIEW_20260911.md`
- `tbm_validation/reference/HE18650/he18650spiral1.tbm`
- `tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm`
- `tbm_validation/in_StarCCM_bds/validationBattery.tbm`
- `STARCCM_TBM_PROJECT_CONTEXT.md`
- Siemens reference corpus on branch `tbm-siemens-reference-corpus`

---

## 11. Evidence standard

Do not mark E004 resolved from this document.

Resolution still requires STAR runtime evidence that either:

1. `Create from Tbm` completes successfully; or
2. STAR progresses to a different downstream condition and the prior `Electrode Root 1 : Extrusion distance can not be 0` error is absent.
