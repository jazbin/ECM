# Siemens Cylindrical TBM Geometry Pattern Findings and E004 Root-Cause Implications

**Date:** 2026-09-11  
**Project:** hp2170NCA STAR-CCM+ distributed RCR TBM  
**Working branch:** `tbm-rcr-modelmap-fix-exec`  
**Current branch state reviewed:** `9262007e5fbe4fa4eb4922e882bd90161626f9c8`  
**Siemens corpus branch / reference commit:** `tbm-siemens-reference-corpus` / `b0be477f19bf16eaff92eafd9f3ba07fb6f3152d`  
**Status:** E004 remains **ACTIVE / UNRESOLVED at STAR runtime**. This document records static evidence, regularities, and the resulting diagnostic priorities. It does **not** claim that any proposed geometry change has been proven in STAR.

---

## 1. Executive conclusion

The strongest pattern found in the available Siemens TBM corpus is a **radial-versus-axial asymmetry** in cylindrical-cell geometry construction:

1. **Exact radial jelly-roll-to-package-ID equality is a normal Siemens pattern.**
   - STAR-install `LiIonSpiral.tbm` uses `Package m_dintDiameter = 17.9 mm` and Detailed Builder `m_dJellyrollThickness_mm = 17.9 mm`.
   - The STAR-install `testTBM.tbm` lineage also exhibits exact radial equality.
   - Multiple BDS cylindrical families exhibit the same relationship, e.g. 17.8/17.8, 18.2/18.2 and 5.9/5.9 mm.
   - Therefore the project target `JR OD = can/package ID = 20.6274 mm` is not, by itself, an abnormal Siemens construction and should **not** be relaxed merely to avoid E004.

2. **The project axial geometry is much more anomalous than its radial geometry.**
   - Project package internal height: `65.11 mm`.
   - Project separator width: `67.11 mm` -> separator exceeds the stated internal height by `2.00 mm`.
   - Project negative-electrode width: `65.11 mm` -> exactly equal to the stated internal height, leaving `0.00 mm` axial margin.
   - Project positive-electrode width: `64.11 mm` -> `1.00 mm` margin.
   - Siemens STAR `validationBattery.tbm` uses a package/layer relationship of approximately `60 / 59 / 57 / 56 mm` for package / separator / negative / positive, producing positive margins of `+1 / +3 / +4 mm`.
   - The August geometry characterization established that the **physical electrode widths drive realized axial winding geometry**, whereas the Detailed Builder `m_dJellyrollWidth_mm` was not observed to drive the realized cylindrical axial length. This materially increases the significance of the `65.11 - 65.11 = 0` relationship.

3. **Separator feed/tail lengths of `0 / 0 mm` remain a second high-priority abnormality.**
   - Siemens cylindrical Detailed Builder examples repeatedly use positive values, commonly `10 / 40 mm` and, in HP18650-style lineages, `10 / 85 mm`.
   - STAR-install `LiIonSpiral.tbm` explicitly uses `m_dSepFeedLength_mm = 10` and `m_dSepTailLength_mm = 85`.
   - These are literal geometry lengths in the builder and therefore remain plausible contributors to a zero-length CAD feature.

The resulting primary E004 hypotheses are:

- **H1 — axial Physical Cell Description / builder incompatibility:** HIGH confidence as a suspect.
- **H2 — separator feed/tail = 0/0:** HIGH confidence as a suspect.
- **H3 — interaction between axial clearance and separator feed/tail:** HIGH confidence as a suspect.

The current diagnostic campaign already contains the correct discriminating cases (`C03`, `C14`, `C15`, `C16`, `C17`, `C12`, `C13`). The recommended runtime sequence is now:

`C00 -> C14 -> C03 -> C15 -> C16 -> C17 -> C12 -> C13`, followed by lower-priority isolations only if needed.

No production TBM should be rewritten speculatively before STAR runtime evidence identifies which branch of this decision tree is real.

---

## 2. Governing engineering objective

The project objective is **model equivalence to the OpenFOAM-ECM reference**, not reconstruction of undocumented manufactured-cell clearances.

The required reference-equivalent behavior is:

- can/package ID target = `20.6274 mm`;
- jelly-roll radial OD target = `20.6274 mm`;
- intended radial condition = ideal/shared contact;
- ideal thermal contact at the corresponding OpenFOAM reference interfaces;
- no intentional air layer or contact resistance introduced merely because it appears physically realistic;
- any finite CAD clearance required only to satisfy STAR geometry construction is a **numerical topology workaround**, not a physical-gap model;
- if such a workaround is necessary, STAR thermal coupling must subsequently be configured so the effective thermal path remains equivalent to the OpenFOAM ideal-contact condition.

A critical distinction follows from this objective:

> **Macroscopic jelly-roll/end-cap ideal contact does not require the physical negative-electrode sheet in the TBM to terminate exactly on the cap/cavity plane.**

STAR may require positive construction margin for electrode roots, separator extensions, tabs or other intermediate CAD features while the homogenized/effective thermal model still reproduces the OpenFOAM end-contact condition. Literal physical-sheet coincidence and macroscopic thermal-contact equivalence are different requirements and must not be conflated.

See also:

- `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`
- `tbm_validation/STAR_E004_AXIAL_RECESS_IMPORT_AND_ELECTRICAL_ADDENDUM_20260910.md`

---

## 3. Evidence hierarchy used in this review

Not every Siemens TBM has equal value for predicting STAR import behavior. The evidence was weighted as follows.

### Tier 1 — STAR-install TBMs

Highest static relevance because these files ship in or are directly associated with the STAR-side installation and therefore represent geometry/model combinations expected to be consumed by STAR.

Key files:

- `tbm_validation/siemens_reference_corpus/star_install/StarCCM_bds/LiIonSpiral.tbm`
- `tbm_validation/siemens_reference_corpus/star_install/testedVersion/testTBM.tbm`

### Tier 2 — STAR sample/validation/tutorial TBMs

High relevance because these are STAR-facing example or validation assets.

Key files include:

- `tbm_validation/siemens_reference_corpus/sample_projects/StarCCM_bds/validation/validation/validationBattery.tbm`
- `tbm_validation/siemens_reference_corpus/tutorials/StarCCM_bds/tutorialCylindricalCell.tbm`

### Tier 3 — BDS project TBMs

Useful for identifying **Detailed Builder conventions and common geometry relationships**, but not all such files are guaranteed to have been imported through the same STAR path/version as the current project.

Representative families include:

- `BDS_files/_Projects/CompareChem/*`
- `BDS_files/_Projects/GapExample/hp18650Spiral1-1D.tbm`
- `BDS_files/_Projects/HP18650/*`
- `BDS_files/_Projects/HE18650/*`

### Tier 4 — REPORT values / stale generated summaries

Lowest weight for construction logic. REPORT fields are known to become stale when the upstream TBM is manually edited. They are useful as historical clues but cannot override Physical Cell Description, Package or active Detailed Builder fields.

---

## 4. Project failure state relevant to E004

STAR repeatedly reaches geometry creation and fails with:

```text
Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
error: Server Error
```

The failure survived previous fixes to unrelated or upstream issues, including:

- correcting the active IET MODELMAP to `RCRTable 3D`;
- correcting `+Electrode m_dS3` from `0` to `5 mm`;
- adding explicit `Transport Number sets = 0`;
- restoring exact radial JR/package-ID equality to the OpenFOAM-equivalent target;
- preserving the validated RCR payload and active distributed thermal mapping.

The current project geometry relevant to the axial failure is:

| Field | Project value |
|---|---:|
| Package internal height | 65.11 mm |
| Separator width | 67.11 mm |
| Negative-electrode width | 65.11 mm |
| Positive-electrode width | 64.11 mm |
| Negative offset | 1.0 mm |
| Positive offset | 0.5 mm |
| Separator offset | 0.0 mm |
| Separator feed | 0 mm |
| Separator tail | 0 mm |

The corresponding simple package-minus-layer margins are:

| Relation | Project margin |
|---|---:|
| `intHeight - separator` | **-2.00 mm** |
| `intHeight - negative` | **0.00 mm** |
| `intHeight - positive` | **+1.00 mm** |

The literal zero in `65.11 - 65.11` is especially noteworthy because the runtime error is itself a zero extrusion distance on an electrode-root feature. This does **not** prove the internal STAR formula is a direct subtraction of those two fields, but it is a strong geometric correlation and merits priority testing.

---

## 5. Strong Siemens regularity: exact radial equality is normal

The most important radial finding is that exact equality of Detailed Builder JR diameter and package internal diameter is not inherently invalid.

In STAR-install `LiIonSpiral.tbm`:

```text
Package m_dintDiameter = 17.9
m_dJellyrollThickness_mm = 17.9
```

The same file also has:

```text
m_dJellyrollWidth_mm = 0
m_dMandrelThickness_mm = 6
m_dMandrelWidth_mm = 0
m_dOffsetNegAvg = 1
m_dOffsetPosAvg = 0.5
m_dOffsetSepAvg = 0
m_dSepFeedLength_mm = 10
m_dSepTailLength_mm = 85
m_nNumSpokes = 200
```

This is a particularly valuable reference because its radial construction is very close to the HP18650 lineage from which the project TBM evolved.

Other Siemens BDS cylindrical families contain exact equality at other diameters, including examples with `17.8 / 17.8`, `18.2 / 18.2`, and `5.9 / 5.9` for Detailed Builder JR diameter versus package internal diameter.

### Implication

The August observation that a requested `18.2 mm` JR failed against an `18.0 mm` can must not be generalized into a requirement for positive radial clearance. The evidence distinguishes:

- **JR > package ID:** demonstrably capable of failing;
- **JR = package ID:** demonstrably present in Siemens reference TBMs.

Therefore:

```text
REFERENCE RADIAL TARGET = 20.6274 mm
STAR E004 RESPONSE      = do not relax this target without direct runtime evidence
```

---

## 6. Strong Siemens regularity: positive axial construction room

The project axial relationship is significantly less Siemens-like.

The already-audited STAR `validationBattery.tbm` comparison gives:

| Quantity | Project | Siemens validationBattery |
|---|---:|---:|
| Package internal height | 65.11 | 60 |
| Separator width | 67.11 | 59 |
| Negative width | 65.11 | 57 |
| Positive width | 64.11 | 56 |
| Package - separator | **-2** | **+1** |
| Package - negative | **0** | **+3** |
| Package - positive | **+1** | **+4** |

At the same time, both geometries preserve the same nested layer hierarchy:

```text
separator - negative = 2 mm
negative - positive  = 1 mm
```

That distinction is important. The internal ordering of separator/negative/positive is not the unusual part; the unusual part is the **placement of that nested stack relative to the package axial envelope**.

The Siemens corpus also contains many cylindrical REPORT values around a 59 mm jelly-roll height with a 60 mm package internal height. REPORT fields are lower-trust than input geometry fields, but the recurring pattern is directionally consistent with the higher-trust validationBattery geometry: the winding structure is typically constructed with positive axial room rather than by forcing a physical electrode exactly onto the package end plane.

### Interaction with August geometry characterization

The August STEP campaign established that physical electrode widths are consumed by the generated geometry and drive the realized axial extent, while Detailed Builder `m_dJellyrollWidth_mm` did not show the same control over the realized cylindrical axial geometry.

Consequently:

- `m_dJellyrollWidth_mm = 0` should **not** be treated as a zero-height error candidate merely because its value is zero;
- the physical separator/electrode/collector widths deserve much higher weight;
- package-vs-physical-layer margins are a meaningful E004 diagnostic space.

---

## 7. Strong Siemens regularity: positive separator feed/tail

Across representative cylindrical Siemens Detailed Builder lineages, separator feed and tail are positive geometry lengths.

Common families include:

```text
Feed = 10 mm
Tail = 40 mm
```

and HP18650-style families include:

```text
Feed = 10 mm
Tail = 85 mm
```

STAR-install `LiIonSpiral.tbm` explicitly uses `10 / 85 mm`.

The project uses:

```text
m_dSepFeedLength_mm = 0
m_dSepTailLength_mm = 0
```

Because these are literal construction lengths rather than metadata, `0/0` remains a plausible route to a degenerate root/start/end feature.

### What can and cannot be concluded

Observed:

- positive feed/tail is a strong Siemens convention in the relevant cylindrical references inspected;
- `0/0` is atypical relative to those references;
- E004 is a zero-length CAD feature failure.

Not yet proven:

- that either feed or tail is directly used in the failing `Electrode Root 1` extrusion;
- that changing only feed/tail clears E004.

That is why `C03` is required rather than silently changing the production TBM.

---

## 8. Other Detailed Builder fields: regularity and suspicion ranking

### `m_dJellyrollWidth_mm = 0` — very low suspicion

A zero Detailed Builder JR width occurs repeatedly in cylindrical Siemens files, including STAR-install references. The August STEP campaign also did not observe it as the controlling realized axial dimension.

**Conclusion:** do not change it simply because it is zero.

### `m_dMandrelWidth_mm = 6` — low suspicion for E004

A round cylindrical mandrel commonly uses `m_dMandrelWidth_mm = 0` in Siemens references, including STAR-install `LiIonSpiral.tbm`. The project currently carries a nonzero `6 mm` width together with a `6 mm` mandrel diameter.

This is unusual enough to retain as a compatibility variable, but it is not a good first explanation for an **electrode-root extrusion** failure.

**Conclusion:** keep in later isolation tests; do not make it the first production change.

### Offsets `1 / 0.5 / 0` — low suspicion

The project negative/positive/separator offset pattern is directly represented in Siemens cylindrical references. Other references use positive offset `1`, and some historical Siemens files even contain effectively zero positive offsets.

**Conclusion:** the current offsets are within the Siemens family and should not be normalized speculatively.

### `m_nNumSpokes = 200` — very low suspicion

`200` is a recurring Siemens Detailed Builder value.

### Electrode overlap start/end — low/medium suspicion

Siemens files show broad variation, including combinations around:

- `5 / 50`
- `10 / 30`
- `12 / 40`
- `8 / 30`
- `3 / 40`

The project `8 / 20` has a comparatively short end overlap, so it remains an outlier worth later testing, but overlap is clearly a design variable rather than a fixed structural invariant.

**Conclusion:** do not prioritize it above axial margin or feed/tail.

### Tabs — low suspicion for E004 after previous isolation

Both-tabs-enabled configurations are common. Project same-face/top placement is a project requirement confirmed from client data and should remain protected unless a dedicated tab diagnostic proves causality.

---

## 9. Revised E004 hypothesis ranking

The following is the current engineering ranking, based on runtime history, August geometry characterization, and Siemens corpus regularities.

| Rank | Hypothesis | Assessment | Reason |
|---|---|---|---|
| 1 | Axial PCD / physical-layer compatibility | **HIGH** | Project has `-2/0/+1 mm` margins versus Siemens positive margins; physical widths drive realized axial geometry; literal zero aligns with zero-extrusion failure wording. |
| 2 | Separator feed/tail `0/0` | **HIGH** | Relevant Siemens cylindrical builders use positive lengths; fields directly describe construction geometry. |
| 3 | Axial-margin × feed/tail interaction | **HIGH** | CAD builder may require both a valid axial envelope and nonzero separator lead/trail geometry. |
| 4 | Other Detailed Builder interaction | **MEDIUM** | C12 can transplant a known Siemens builder while preserving project PCD. |
| 5 | PCD/Builder cross-interaction | **MEDIUM** | C13 tests Siemens PCD plus Siemens builder and must be interpreted jointly with C12. |
| 6 | Electrode overlap end = 20 | **LOW/MEDIUM** | Lower than many Siemens examples but nonzero and clearly variable. |
| 7 | Mandrel width = 6 | **LOW** | Unusual for round cylindrical references, but poor direct match to electrode-root failure. |
| 8 | JR width = 0 | **VERY LOW** | Recurrent Siemens cylindrical convention and not observed as controlling axial extent. |

This table is a prioritization of **hypotheses**, not a proof of cause.

---

## 10. Runtime campaign and decision logic

The current E004 campaign already contains the correct high-information cases. After the metadata/interpretation correction at `9262007`, the recommended order is:

```text
C00  Siemens control
C14  project TBM with package internal height 65.11 -> 68.11 only
C03  project TBM with separator feed/tail 0/0 -> 10/85 only
C15  C14 + feed/tail 10/85
C16  project cavity retained at 65.11; physical layer widths recessed by 3 mm
C17  C16 + feed/tail 10/85
C12  Siemens Detailed Builder transplanted into project PCD
C13  Siemens PCD + Siemens Detailed Builder
```

### Interpretation matrix

#### C00

- **PASS:** Siemens control is valid in the client's STAR import path; campaign is interpretable.
- **FAIL:** stop interpreting the remaining geometry cases as causal evidence. First resolve STAR version/import-path/environment mismatch.

#### C14 versus C03

- `C14 PASS`, `C03 FAIL`: axial package/layer margin is the leading cause.
- `C03 PASS`, `C14 FAIL`: separator feed/tail is the leading cause.
- both PASS: both are independently capable of avoiding the failing construction; choose the lower-impact production route after geometry/electrical comparison.
- both FAIL: move immediately to interaction/transplant cases.

#### C15

- `C14 FAIL`, `C03 FAIL`, `C15 PASS`: strong evidence for an interaction between axial margin and separator feed/tail.
- `C14 PASS`, `C15 PASS`: feed/tail is not required once axial room exists.
- `C03 PASS`, `C15 PASS`: extra axial room is not required once separator feed/tail is valid.

#### C16/C17

These reproduce Siemens-like package-minus-layer margins by changing physical layer widths rather than package internal height.

- If C16 behaves like C14, the decisive factor is likely the **relative axial margin**, not the specific field used to create it.
- If C16 passes while C14 fails, STAR may specifically require the physical layer extents to be recessed rather than merely increasing package internal height.
- If only C17 passes, both physical-layer recession and feed/tail are implicated.

Because C16/C17 change physical electrode/collector widths, they are **diagnostics only** until active area, electrical mapping, thermal geometry and OpenFOAM equivalence are revalidated.

#### C12/C13 paired interpretation

The branch already corrected an earlier over-strong interpretation. The valid logic is:

- `C12 PASS`: strongly localizes E004 to project Detailed Builder / derived builder construction under the project PCD.
- `C12 FAIL + C13 PASS`: project PCD or PCD-Builder interaction is implicated; Siemens Builder alone is insufficient.
- `C12 PASS + C13 PASS`: project Detailed Builder remains the dominant suspect.
- `C12 PASS + C13 FAIL`: anomalous cross-interaction; treat separately rather than drawing a simple localization conclusion.
- `C12 FAIL + C13 FAIL` while `C00 PASS`: geometry transplant alone does not eliminate the fault; investigate model/geometry coupling or non-transplanted sections.

---

## 11. Consequences for the production geometry strategy

### Do not abandon exact radial contact

There is now positive Siemens evidence that exact radial equality is supported as a construction pattern. The production target remains:

```text
Package internal diameter = 20.6274 mm
Detailed Builder JR diameter = 20.6274 mm
```

A smaller JR should only be used as a controlled diagnostic or as a proven STAR CAD workaround with explicit restoration of reference-equivalent thermal coupling.

### Axial CAD clearance may be numerical, not physical

If runtime proves that STAR requires positive axial construction room, the preferred first production remedy is the one that preserves the project physical electrode data with the least disturbance.

For example, if `C14` passes, increasing only the package **internal** height to create Siemens-like construction room is preferable to immediately shrinking physical electrode widths, because shrinking physical widths changes the geometry that August tests showed STAR actually consumes.

However, such an internal-height change must not silently alter the intended OpenFOAM thermal contact. After successful import, generated geometry must be inspected and the thermal interface/contact treatment must explicitly recover the ideal-contact reference behavior.

### Separator feed/tail is potentially lower impact

If `C03` alone passes, `10/85 mm` is an attractive remediation because it changes separator lead/trail construction rather than active electrode dimensions. It still requires geometry inspection, but it is less likely to perturb active area/electrical response than changing physical electrode widths.

---

## 12. Fields that must remain protected during E004 remediation

Unless STAR runtime evidence directly implicates one of these fields, E004 work must preserve:

- external OD `21.09 mm`;
- external height `70.02 mm`;
- package/can ID `20.6274 mm`;
- radial JR OD `20.6274 mm`;
- mandrel diameter `6 mm`;
- active IET = `RCRTable 3D`;
- thermal model = `Distributed`;
- RCR nominal capacity = `5 Ah`;
- all three RCR temperature sets `288.15 / 298.15 / 308.15 K`;
- RCR SOC grid including intentional `-0.08` extrapolation point;
- all RCR `Vequ`, `Ro`, `Rp`, `tau`, entropy/OCV data and indexing;
- both tabs enabled and same-face/top as required by client information;
- `+Electrode S3 = 5 mm`;
- `-Electrode S3 = 50 mm`;
- `Transport Number sets = 0`;
- active-block `m_bOnly1D`/lumped-energy settings already validated for the RCR route.

Do **not** globally normalize duplicate field names across inactive SIMMODs. Field validity is model-specific.

---

## 13. Static analysis gap still worth closing

The Siemens corpus matrix is broad, but the next useful analysis is a **deduplicated, cylindrical, geometry-specific statistical extraction** that treats STAR-facing references separately from BDS-only references.

For every unique cylindrical TBM, extract at minimum:

```text
source class / path / SHA256
package extDiameter / intDiameter / extHeight / intHeight
Detailed Builder JR diameter / JR width
mandrel diameter / mandrel width
separator feed / tail
start / end overlap
offsets neg / pos / sep
spokes
tab enable/orientation
separator physical width
negative electrode/coating/collector widths
positive electrode/coating/collector widths
derived package-minus-layer margins
derived JR_OD - package_ID delta
```

Statistics must be reported separately for:

1. STAR-install / STAR-facing references;
2. STAR sample/tutorial/validation references;
3. BDS project references.

Duplicate files must be deduplicated by content hash before frequency claims are made. Until that analysis is complete, statements such as “all Siemens cylindrical TBMs do X” should be avoided. The present document intentionally uses wording such as “recurring,” “representative,” and “strong convention” except where a specific reference is named.

---

## 14. Static validator implications

The project validator should eventually detect the geometry relationships that this investigation exposed, but initially as **diagnostic warnings**, not universal hard failures.

Recommended static diagnostics for cylindrical Detailed Builder TBMs:

- warn when `package intHeight - negative physical width <= 0`;
- warn when separator physical width exceeds package intHeight;
- warn when both separator feed and tail are zero;
- report package-minus-separator/negative/positive margins explicitly;
- report JR diameter minus package internal diameter and distinguish `> 0`, `= 0`, `< 0` rather than enforcing positive radial clearance;
- recognize `m_dJellyrollWidth_mm = 0` and round-mandrel `m_dMandrelWidth_mm = 0` as patterns that may be valid, not automatic errors.

Any promotion from WARN to FAIL should require runtime evidence or a sufficiently strong quantified Siemens invariant.

---

## 15. Current engineering judgement

At this point the most defensible statement is:

> **The project TBM is statically coherent in its RCR/model mapping, but its axial CAD construction is substantially less Siemens-like than its radial construction. Exact radial JR/package-ID equality is supported by Siemens references; the leading unresolved E004 suspects are zero/nonpositive axial package-to-layer margins, zero separator feed/tail, or their interaction.**

Accordingly:

- keep exact radial `20.6274 / 20.6274` as the reference target;
- do not “fix” `m_dJellyrollWidth_mm = 0` just because it is zero;
- do not make broad geometry edits to the production TBM;
- run the high-information E004 cases in the order defined above;
- use the first passing minimal delta to determine the production remediation path;
- after any successful CAD workaround, verify generated topology and explicitly restore OpenFOAM-equivalent thermal/electrical behavior before release.

**E004 remains runtime-unresolved until a client STAR import provides the discriminating evidence.**
