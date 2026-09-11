# E004 `Electrode Root 1` Reverse Engineering

## Scope

This note targets one question only: what geometry relationship is most likely to produce STAR-CCM+'s fatal TBM-import error

```text
Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
error: Server Error
```

and which parameters can be changed diagnostically without unnecessarily changing the final production geometry or the distributed RCR model.

The intended production architecture is fixed:

- cell creation by **TBM import only**;
- native **`RCRTable 3D`** distributed electrical model;
- final retained physical solids: **JellyRoll + Can + Cap**;
- JellyRoll/Can radial contact and JellyRoll/Cap axial contact are desired in the final model;
- tab roots, tab stems, washers, posts, mandrel and other generated auxiliary parts may be discarded after successful TBM import, but STAR must first be able to construct them without a fatal CAD error.

This document therefore distinguishes **TBM construction validity** from **final retained geometry**.

---

## Executive conclusion

The targeted review materially narrows E004.

The strongest current explanation is **not** a generic zero-valued tab parameter (`S3`, separator feed/tail, tab offset, mandrel width, etc.). The strongest remaining geometry anomaly is the project's **zero package-to-negative-electrode axial clearance**:

```text
Package m_dintHeight             = 65.11 mm
-Negative electrode/collector W  = 65.11 mm
---------------------------------------------
Total package-minus-negative      =  0.00 mm
```

The negative electrode is the only electrode whose physical axial width exactly consumes the stated package internal height. In the directly audited Siemens cylindrical references, this margin is always positive:

| TBM | Package internal height | Separator width | Negative width | Positive width | Pkg-Sep | Pkg-Neg | Pkg-Pos |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Project R005** | **65.11** | **67.11** | **65.11** | **64.11** | **-2.00** | **0.00** | **+1.00** |
| Siemens HE18650 | 60.00 | 61.30 | 59.30 | 58.30 | -1.30 | **+0.70** | +1.70 |
| STAR `validationBattery.tbm` | 60.00 | 59.00 | 57.00 | 56.00 | +1.00 | **+3.00** | +4.00 |
| Siemens HP18650 | 60.00 | 54.50 | 52.50 | 51.50 | +5.50 | **+7.50** | +8.50 |

The HE18650 counterexample is especially important: it demonstrates that a separator longer than the package internal height is not by itself fatal. What HE retains, and the project does not, is a **positive negative-electrode margin**.

A successful cylindrical STAR model also establishes the physical topology of the generated tab root: each `±Ve Tab Root` touches the **Jellyroll** on one side and its corresponding **Tab Stem** on the other. The root is therefore a bridge solid generated from/near the wound electrode termination; it is not merely metadata. See the successful 13-interface STAR log in the project File Library and `STARCCM_NATIVE_BATTERY_TBM_MANUAL_RevC_20260802.pdf`.

The most defensible mechanism is therefore:

> STAR derives an electrode-root solid whose extrusion requires positive geometric extent between the wound-electrode termination and the external tab/stem construction. With `Package m_dintHeight == negative-electrode width`, the project uniquely permits this available axial construction extent to collapse to exactly zero.

This is a **strong derived-clearance hypothesis**, not a recovered proprietary formula. No public Siemens/CD-adapco source was found that states the internal `Electrode Root 1` extrusion equation or maps the label `Electrode Root 1` to a particular polarity.

The best next runtime discriminator is therefore a **minimal package-height-only sweep from the immutable R005 baseline**, not another change to S3, feed/tail, radial JR diameter, tab orientation, or RCR data.

Recommended first two project candidates:

1. `ROOT_A`: `Package m_dintHeight 65.11 -> 65.21 mm` only. This changes the negative total axial clearance from 0.00 to +0.10 mm while leaving all physical electrode widths, builder fields, JR OD, RCR data, capacity and model map untouched.
2. `ROOT_B`: `Package m_dintHeight 65.11 -> 65.81 mm` only. This gives exactly the HE18650 package/layer margins `-1.30 / +0.70 / +1.70 mm` while preserving the project's physical separator/electrode widths.

These are **diagnostic files only**. A package-height change may alter the final generated Can/Cap-to-JellyRoll axial relationship and therefore cannot automatically be accepted as the production geometry even if it clears E004.

---

## 1. Evidence hierarchy

The reverse engineering uses the following hierarchy.

### 1.1 Runtime evidence: highest weight

Primary runtime record:

- [`STAR_IMPORT_ERROR_DATABASE.md`](STAR_IMPORT_ERROR_DATABASE.md)

E004 has survived all of the following:

- positive/negative tabs enabled versus disabled;
- standard versus same-face tab vertical orientation;
- `m_bOnly1D` cleanup;
- Detailed Builder start overlap changed from 0 to 8 mm;
- `+Electrode m_dS3` changed from 0 to 5 mm;
- explicit `Transport Number sets = 0`;
- JR OD changed from 19.25 mm to exact package-ID contact at 20.6274 mm.

These are runtime-pruned explanations and should not be recycled as leading single-variable tests.

### 1.2 Verified generated geometry

The project has a client-generated stock HP18650 STEP corresponding to the Siemens stock TBM. The analysis recorded in the File Library document `starccm_tbm_winding_geometry_questions.md` found 13 named solids and zero pairwise boolean-intersection volume. This provides a known geometry-clean counterexample for several zero-valued fields in the Detailed Builder.

A separate successful STAR run recorded all 13 conformal interfaces, including:

```text
-Ve Tab Root / Jellyroll
-Ve Tab Root / -Ve Tab Stem
+Ve Tab Root / Jellyroll
+Ve Tab Root / +Ve Tab Stem
```

This directly establishes the root's generated topology: a root is a solid bridge between the jellyroll and the stem. The same successful run tolerated a few zero-area faces on the positive root/stem *after construction*, which distinguishes a minor downstream face degeneracy from the fatal upstream E004 condition: E004 prevents the root extrusion feature from being created at all.

### 1.3 STAR-install / Siemens TBM corpus

Relevant local sources include:

- [`in_StarCCM_bds/validationBattery.tbm`](in_StarCCM_bds/validationBattery.tbm)
- `reference/HP18650/hp18650Spiral-DIST.tbm` on `tbm-siemens-reference-corpus`
- `reference/HE18650/he18650spiral1.tbm` on `tbm-siemens-reference-corpus`
- STAR-install `LiIonSpiral.tbm`, `testTBM.tbm`, and tutorial/validation lineages documented in [`SIEMENS_CYLINDRICAL_TBM_GEOMETRY_PATTERN_FINDINGS_20260911.md`](SIEMENS_CYLINDRICAL_TBM_GEOMETRY_PATTERN_FINDINGS_20260911.md)

### 1.4 Public original/near-original documentation

The most useful external source found is the U.S. DOE FY2011 Energy Storage R&D report, section III.E.4, by the CD-adapco/Battery Design team. It explicitly shows the BDS electrode parameterization used as the host for spiral-cell STAR development. Figure III-176 labels `L_tab`, `W_tab`, `W_tape`, `S1`, `S2`, `S3`, `S4`, `S5`, `L`, `W`, coating thickness and foil thickness. The report states that automatic 3D spiral-cell geometry creation in STAR-CCM+ was being developed from setup-file data.

Source:
- U.S. DOE, *FY 2011 Annual Progress Report for Energy Storage R&D*, III.E.4, pp. around Fig. III-176/177: https://www1.eere.energy.gov/vehiclesandfuels/pdfs/es_11/3_adv_battery.pdf

A later publication reproduces BDS Detailed Builder screens showing `Negative wrt Separator`, `Positive wrt Negative`, vertical tab orientation, separator feed/tail, electrode overlap and mandrel/JR geometry. This supports interpreting the stored offsets as **relative layer alignment**, not package headroom.

Source:
- International Journal of Environmental Sciences, BDS workflow screenshots, 2025/2026 indexed copy: https://theaspd.com/index.php/ijes/article/download/1204/920

Siemens' current product description also confirms that BDS separately parameterizes electrodes, tabs, current collectors and package geometry and exports them through the TBM into STAR-CCM+:
- Siemens, *Simcenter Battery Design Studio*: https://blogs.sw.siemens.com/en-US/simcenter/simcenter-battery-design-studio/

No authoritative public source was found for the exact error string `Electrode Root 1 : Extrusion distance can not be 0` or for STAR's internal formula producing that extrusion distance.

---

## 2. What `Electrode Root` can be inferred to mean geometrically

The successful STAR interface graph is more informative than the name alone:

```text
Jellyroll <-> ±Ve Tab Root <-> ±Ve Tab Stem <-> ±Ve Washer
                                               |
                                         ±Ve Internal Post
                                               |
                                           ±Ve EndPlate
```

For the root itself, only two required interfaces matter:

```text
Jellyroll <-> Tab Root <-> Tab Stem
```

Thus the root is the transition from the wound current-collector/electrode structure to the external stem. It must have finite extent in whatever extrusion direction the CAD template uses.

The fatal feature name `Electrode Root 1` is an internal CAD-feature name; it is not the final imported part name. We cannot prove from public documentation whether `Root 1` is positive or negative. However, the project geometry uniquely singles out the negative side because the negative electrode alone has zero total package axial margin.

This makes a negative-root interpretation strongly consistent with the error, but it must remain an inference until a runtime discriminator or STAR feature-level diagnostic identifies the polarity.

---

## 3. Why `S3` is no longer a credible primary explanation

The earlier geometry audit treated `+Electrode m_dS3 = 0` as suspicious because STAR-install references commonly use `5 mm` and because `S3` is dimensional. That was a reasonable pre-runtime hypothesis.

It is now substantially pruned for two independent reasons.

### 3.1 Runtime proof of insufficiency

R005 retained E004 after `+Electrode m_dS3` was changed from 0 to 5 mm. See:

- [`RCR_V1_TO_V2_S3_GEOMETRY_DELTA_20260910.md`](RCR_V1_TO_V2_S3_GEOMETRY_DELTA_20260910.md)
- [`STAR_IMPORT_ERROR_DATABASE.md`](STAR_IMPORT_ERROR_DATABASE.md)

Therefore `+S3=0` is not the sole cause.

### 3.2 BDS geometry semantics

The DOE/Battery Design parameter diagram places `S1...S5` on the **flat electrode/tab/tape geometry**, together with `L_tab`, `W_tab`, `W_tape`, electrode length/width, coating and foil thickness. These are electrode-layout spacings. They are not the package cavity height or a documented root-to-cap clearance.

Consequently S3 can influence where/what material is available around a tab attachment, but there is no evidence that it directly supplies the CAD root's axial extrusion distance. The runtime result is consistent with that interpretation.

### Conclusion for S-fields

Do not send more `S1...S6` perturbations to Robert before testing axial clearance. They remain auxiliary-geometry variables, but causal support for E004 is now low.

---

## 4. Why separator feed/tail `0/0` is also demoted

The project Detailed Builder uses:

```text
m_dSepFeedLength_mm = 0
m_dSepTailLength_mm = 0
```

STAR-install lineages often use positive values such as `10/85`, so this initially looked like an obvious zero-extrusion candidate.

However the Siemens stock HP18650 Detailed Builder uses **0/0** and produced the verified-clean 13-solid STEP. The HE18650 reference also carries 0/0. Therefore feed/tail zero is demonstrably compatible with a valid cylindrical construction in Siemens/BDS geometry.

Feed/tail may still participate in a version-specific interaction, but it no longer explains E004 well as a universal or primary root-extrusion rule.

Existing C01/C02/C03 remain useful only after the root-clearance discriminator if needed; they should not be the first tests.

---

## 5. The important distinction: layer nesting versus package clearance

The project layer widths are internally coherent:

```text
Separator = 67.11 mm
Negative  = 65.11 mm
Positive  = 64.11 mm

Separator - Negative = 2.00 mm
Negative  - Positive = 1.00 mm
```

The Detailed Builder alignment is:

```text
Negative wrt Separator = 1.0 mm
Positive wrt Negative  = 0.5 mm
```

Public STAR/BDS descriptions define these as relative offsets between layer edges. A 1 mm negative-vs-separator offset with a 2 mm width difference is exactly consistent with a centered separator overhang of 1 mm on each side. Likewise, a 0.5 mm positive-vs-negative offset with a 1 mm width difference is exactly consistent with 0.5 mm negative overhang on each side.

So there is no evidence that the **electrode stack itself** is misaligned. The problem appears when this coherent nested stack is placed inside the package axial construction envelope:

```text
Package internal height = 65.11 mm
Negative width          = 65.11 mm
```

If the winding stack is registered centrally or otherwise uses the negative physical edge as a root construction reference, the negative side has no free package-side axial extent.

### Derived side clearances

If the package registration is symmetric about the stack—consistent with the centered layer nesting, though the exact package-origin formula is not publicly documented—the total negative margins imply the following per-side headroom:

| TBM | Total `Hpkg - Wneg` | Approx. per side if centered |
|---|---:|---:|
| Project | **0.00 mm** | **0.00 mm** |
| HE18650 | +0.70 mm | +0.35 mm |
| validationBattery | +3.00 mm | +1.50 mm |
| HP18650 | +7.50 mm | +3.75 mm |

This is not proof that STAR literally computes `(Hpkg-Wneg)/2`; it is the geometric quantity that best discriminates the failed project from all directly audited known-good examples.

---

## 6. Why the runtime history fits the zero-negative-clearance mechanism

### Tabs enabled versus disabled

E004 survived both. This tells us that the TBM builder's internal geometry construction/validation is not bypassed merely by the project tab-enable variant. It does **not** prove the failed feature is unrelated to tabs; the error itself names an electrode root.

### Standard versus same-face tab orientation

E004 survived both. If the negative electrode has zero package headroom on both axial ends, changing which end the negative root is oriented toward does not create room. Thus orientation-insensitivity is consistent with the zero-margin mechanism.

### `+S3: 0 -> 5`

No effect. This is consistent with S3 being a flat electrode/tab-layout spacing rather than the missing package-to-root extrusion extent.

### Exact radial JR contact

Changing JR OD to the package ID did not change E004. Siemens references themselves use exact JR/package-ID equality, so the failure is not well explained by radial geometry.

### `m_bOnly1D` / transport-number cleanup

Those changes affect model/import compatibility, not the geometric axial root extent. Their failure to move E004 is expected under the clearance mechanism.

---

## 7. Parameter impact map: which fields are safe to touch?

The production objective makes this classification more useful than a generic list of zeros.

### Class A — mostly auxiliary geometry; low current causal support

These can generally be altered without intentionally changing the gross retained Can/JellyRoll/Cap dimensions, but the evidence does **not** currently support them as primary E004 controls:

- `+/- Electrode m_dS1...m_dS6`
- tab length/width/thickness
- tape length/width/thickness
- tab offset
- tab alignment angle
- tab vertical orientation
- tab enable flags

`+S3` and tab orientation are already runtime-pruned as sole causes.

### Class B — winding/internal construction variables; not gross package dimensions but not free

- separator feed/tail
- start/end electrode overlap
- mandrel dimensions
- Detailed Builder offsets

These can change winding-start/end topology or internal distributed geometry. They should not be treated as harmless placeholders. Feed/tail 0/0 and several other zeros also have Siemens counterexamples.

### Class C — retained JellyRoll/electrical geometry; protected

- physical separator width
- physical positive/negative electrode/collector/coating widths
- radial `m_dJellyrollThickness_mm`

August STEP characterization shows physical electrode widths drive realized axial winding extent. Changing them changes the retained JellyRoll geometry and potentially active-area/electrical interpretation. These are poor production fixes.

### Class D — package/cap construction; likely root-relevant but production-impacting

- `Package m_dintHeight`
- package/endplate geometry controlling final axial envelope

This class contains the strongest current E004 discriminator, but a passing value cannot automatically be used in production because the final retained JellyRoll/Cap contact requirement must be rechecked.

### Key negative result

At present, **no exposed TBM field has been identified that is both:**

1. strongly supported as the direct controller of `Electrode Root 1` extrusion distance; and
2. strictly auxiliary-only with no plausible effect on distributed winding construction or retained Can/JellyRoll/Cap geometry.

That is why the minimal package-height perturbation is now the cleanest diagnostic despite being a production-impacting field.

---

## 8. Proposed root-specific runtime campaign

Do not send the entire C00-C17 matrix first. Use the existing failed R005 as the zero-clearance baseline and add two package-height-only discriminators.

### Baseline — already failed

```text
R005
Package m_dintHeight = 65.11
Separator width      = 67.11
Negative width       = 65.11
Positive width       = 64.11
Margins               -2.00 / 0.00 / +1.00
Result                 E004
```

No need to ask Robert to rerun this unless a control is desired.

### ROOT_A — minimal positive negative-electrode clearance

Change one field only:

```text
Package m_dintHeight: 65.11 -> 65.21 mm
```

Everything else remains byte/semantically identical to immutable R005.

Resulting total margins:

```text
Pkg - separator = -1.90 mm
Pkg - negative  = +0.10 mm
Pkg - positive  = +1.10 mm
```

Purpose: determine whether the exact zero itself is the trigger. `0.10 mm` is preferred to an extremely small epsilon because it remains a deliberately small perturbation while reducing the risk that CAD/model tolerance obscures the sign change.

Interpretation:

- **PASS:** very strong evidence that the zero negative margin, or a derived quantity that changes sign with it, drives E004.
- **FAIL:** does not kill the hypothesis; STAR may need a finite construction threshold larger than 0.10 mm or another coupled clearance.

### ROOT_B / C18 — HE-pattern clearance

Change one field only:

```text
Package m_dintHeight: 65.11 -> 65.81 mm
```

Resulting margins:

```text
Pkg - separator = -1.30 mm
Pkg - negative  = +0.70 mm
Pkg - positive  = +1.70 mm
```

These exactly reproduce the HE18650 package-to-layer margins while preserving all project layer widths.

Interpretation:

- **ROOT_A FAIL, ROOT_B PASS:** the issue is not merely a floating-point zero; a finite positive construction distance/tolerance is required. This strongly localizes E004 to package/layer axial construction.
- **ROOT_A PASS, ROOT_B PASS:** the zero itself is effectively isolated.
- **ROOT_A FAIL, ROOT_B FAIL:** the zero-negative-margin hypothesis is materially weakened. Escalate to the existing `C12/C13` Siemens Builder/PCD transplant pair instead of random single-field edits.

### Optional stronger control — existing C14

`C14_AXIAL_CAVITY68p11.tbm` gives the STAR validation-style margins `+1/+3/+4`. It is useful if ROOT_B fails and a stronger axial-clearance test is still justified, but it is less surgical and more likely to move the final retained cap relationship.

---

## 9. Why C12/C13 are the correct escalation after root-clearance failure

If ROOT_A and ROOT_B both retain E004, further random tweaks to individual zeros have poor information value.

Use the existing transplant pair:

- **C12:** Siemens Detailed Builder transplanted into the project PCD/model context.
- **C13:** Siemens PCD + Siemens Builder transplanted into the project model context.

Interpretation:

- C12 PASS → project Detailed Builder content/derived construction is strongly implicated.
- C12 FAIL + C13 PASS → project PCD or PCD–Builder interaction is implicated.
- C12 PASS + C13 PASS → project Detailed Builder is dominant.
- C12 FAIL + C13 FAIL while a Siemens control passes → blocker survives Siemens geometry transplants in project context; inspect non-transplanted geometry/model coupling.

This yields much more information than cycling through S-fields, tab dimensions, mandrel width or other weak suspects.

---

## 10. Production consequence: import success is not yet the final geometry solution

The final model must retain only:

```text
JellyRoll
Can
Cap
```

and those three are intended to be in direct contact.

A package-height increase is therefore a **diagnostic construction workaround**, not automatically a production solution. If `ROOT_A`, `ROOT_B` or C14 clears E004, the generated geometry must be inspected before adopting the TBM:

1. retain/import the JellyRoll, Can and desired Cap/EndPlate only;
2. measure JellyRoll axial extent;
3. measure Cap/EndPlate location;
4. verify JellyRoll–Cap contact rather than merely successful CAD generation;
5. verify JR OD–Can ID radial contact remains the intended exact-contact topology;
6. verify the imported Battery Cell remains `RCRTable 3D`, distributed, with the expected electrical mesh/spokes;
7. only then decide whether the successful clearance can be converted into a production TBM or whether a post-import Cap placement/contact treatment is needed.

This distinction is central: **E004 diagnosis and final JellyRoll/Can/Cap contact are separate gates.**

---

## 11. What is now low-value work

Do not prioritize the following before the root-clearance discriminator:

- another `+S3` variant;
- changing JR diameter away from the 20.6274 mm exact-contact target;
- another tab-on/off or top/bottom permutation;
- changing `m_bOnly1D` again;
- changing transport-number metadata;
- treating `m_dJellyrollWidth_mm = 0` as an axial-height bug;
- assuming separator feed/tail 0/0 is invalid merely because STAR-install controls use positive values;
- shrinking physical electrode widths as a production fix.

The runtime history and Siemens counterexamples have already reduced the expected information value of these tests.

---

## 12. Confidence statement

### High confidence

- E004 is a geometry-feature construction failure reached during `CreateFromTbm`, before the later generated-part selection stage.
- `Tab Root` is a distinct generated bridge solid between Jellyroll and Tab Stem in successful STAR cylindrical geometry.
- `+S3=0` is not the sole cause because E004 persists with `+S3=5`.
- exact radial JR/package-ID equality is not the cause; E004 persists at equality and Siemens uses equality in stock cylindrical TBMs.
- separator feed/tail 0/0 is not universally invalid; Siemens HP/HE counterexamples exist.
- physical electrode widths are consumed by generated axial geometry; they should be protected from speculative production edits.

### Moderate-to-high confidence as an engineering diagnosis

- the project's zero package-to-negative-electrode axial margin is the strongest remaining root-specific anomaly.
- a derived root extrusion based on available axial headroom explains more of the runtime evidence than the previously tested S3/feed-tail/tab hypotheses.

### Not proven

- the exact internal extrusion equation;
- whether `Electrode Root 1` is positive or negative;
- whether STAR uses total clearance, per-side clearance, end-specific clearance, or another derived construction distance;
- the minimum positive distance required by the current STAR version;
- whether a package-height clearance that clears E004 will preserve the desired final JellyRoll–Cap contact without a later geometry adjustment.

---

## 13. Recommended next action

Generate exactly two new TBMs from immutable R005, with **one field changed in each**:

```text
ROOT_A_PACKAGE65p21.tbm  : Package m_dintHeight = 65.21
ROOT_B_PACKAGE65p81.tbm  : Package m_dintHeight = 65.81
```

Freeze all of the following:

```text
IET = RCRTable 3D
Thermal = Distributed
RCR tables / OCV / capacity
physical separator/electrode widths
JR OD = 20.6274
Can ID = 20.6274
offsets 1 / 0.5 / 0
start/end overlap 8 / 20
separator feed/tail 0 / 0
+S3 = 5
-S3 = 50
tab configuration
all remaining model-map fields
```

This is the highest-information, lowest-confounding runtime experiment currently available.

---

## Sources

### Project / repository evidence

1. [`STAR_IMPORT_ERROR_DATABASE.md`](STAR_IMPORT_ERROR_DATABASE.md) — canonical STAR runtime history and pruned E004 hypotheses.
2. [`GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md`](GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md) — August isolated TBM/STEP geometry campaign.
3. [`RCR_V1_TO_V2_S3_GEOMETRY_DELTA_20260910.md`](RCR_V1_TO_V2_S3_GEOMETRY_DELTA_20260910.md) — exact S3-only delta and later runtime context.
4. [`STAR_GEOMETRY_COMPATIBILITY_AUDIT_20260910.md`](STAR_GEOMETRY_COMPATIBILITY_AUDIT_20260910.md) — broad field audit; some hypothesis ranking superseded by later counterexamples/runtime.
5. [`SIEMENS_CYLINDRICAL_TBM_GEOMETRY_PATTERN_FINDINGS_20260911.md`](SIEMENS_CYLINDRICAL_TBM_GEOMETRY_PATTERN_FINDINGS_20260911.md) — corpus comparison; feed/tail ranking superseded by verified HP/HE counterexamples discussed here.
6. [`in_StarCCM_bds/validationBattery.tbm`](in_StarCCM_bds/validationBattery.tbm) — STAR validation reference.
7. `reference/HP18650/hp18650Spiral-DIST.tbm` on branch `tbm-siemens-reference-corpus` — stock Siemens Detailed Builder and PCD.
8. `reference/HE18650/he18650spiral1.tbm` on branch `tbm-siemens-reference-corpus` — important separator-overheight / positive-negative-margin counterexample.
9. `starccm_tbm_winding_geometry_questions.md` in the ChatGPT File Library — verified-clean stock HP18650 STEP characterization.
10. July successful STAR cylindrical run log in the ChatGPT File Library — 13/13 conformal interfaces including both Tab Root–Jellyroll and Tab Root–Tab Stem connections.

### External sources

11. U.S. Department of Energy, *FY 2011 Annual Progress Report for Energy Storage R&D*, section III.E.4, CD-adapco/Battery Design LLC; Figures III-176 and III-177. https://www1.eere.energy.gov/vehiclesandfuels/pdfs/es_11/3_adv_battery.pdf
12. Siemens, *Simcenter Battery Design Studio* overview: https://blogs.sw.siemens.com/en-US/simcenter/simcenter-battery-design-studio/
13. International Journal of Environmental Sciences, publication reproducing BDS Detailed Builder/Vertical Alignment screens: https://theaspd.com/index.php/ijes/article/download/1204/920
14. STAR-CCM+ documentation mirror, stacked-cell offset semantics (`Negative wrt separator`, `Positive wrt negative`): https://www.topcfd.cn/Ebook/STARCCMP/GUID-7C17692F-C6DF-4F12-85F7-A7F6FD476898.html

---

**Status:** E004 remains **ACTIVE / UNRESOLVED** pending STAR runtime testing. This report deliberately does not promote the zero-negative-clearance hypothesis to confirmed root cause without a passing/failing runtime discriminator.
