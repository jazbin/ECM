# STAR-CCM+ E004 Campaign Addendum — Axial Recession, Import Selection, and Electrical Completeness

**Date:** 2026-09-10  
**Applies to:** `STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_20260910.md` and `STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_ADDENDUM_20260910.md`  
**Precedence:** this addendum extends those documents. Where this addendum adds tests or tightens interpretation, it takes precedence.

## Objective

Extend the E004 campaign before client runtime testing so that one round of STAR-CCM+ imports can answer three questions:

1. Is the persistent `Electrode Root 1 : Extrusion distance can not be 0` caused by the axial package/electrode/separator geometry rather than the separator feed/tail alone?
2. Can a STAR geometry configuration keep the macroscopic jelly-roll/core as the thermally contacting body while the physical electrode layers are axially recessed?
3. If STAR allows selective TBM object creation during `Create from Tbm`, which imported/generated objects are required for the **distributed 3D RCR electrical model**, and which are only geometric/thermal?

Do not call E004 resolved until a runtime result progresses past E004.

---

# A. Important new static finding: project axial hierarchy differs materially from Siemens STAR reference

Use the immutable Robert-tested failed baseline from commit:

`d74b3283cb5d73e114bc141f3f0d18e7c7ed5463`

Baseline TBM:

`out/hp2170NCA-RCR-distributed-exact-contact-final.tbm`

Baseline SHA-256:

`2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`

The relevant axial fields in the failed project TBM are:

```text
Package m_dintHeight                         = 65.11 mm
SeparatorList1_Separator m_dWidth_mm        = 67.11 mm
-Electrode m_dWidth                         = 65.11 mm
-Electrode m_dCoatingWidth                  = 65.11 mm
-Electrode Collector m_dWidth_mm            = 65.11 mm
+Electrode m_dWidth                         = 64.11 mm
+Electrode m_dCoatingWidth                  = 64.11 mm
+Electrode Collector m_dWidth_mm            = 64.11 mm
Detailed Builder m_dOffsetNegAvg            = 1.0 mm
Detailed Builder m_dOffsetPosAvg            = 0.5 mm
Detailed Builder m_dOffsetSepAvg            = 0.0 mm
```

The Siemens STAR-install `validationBattery.tbm` reference uses:

```text
Package m_dintHeight                         = 60 mm
SeparatorList1_Separator m_dWidth_mm        = 59 mm
-Electrode m_dWidth                         = 57 mm
+Electrode m_dWidth                         = 56 mm
Detailed Builder m_dOffsetNegAvg            = 1.0 mm
Detailed Builder m_dOffsetPosAvg            = 0.5 mm
Detailed Builder m_dOffsetSepAvg            = 0.0 mm
```

Therefore the axial margins are:

| Relation | Project failed baseline | Siemens validationBattery |
|---|---:|---:|
| package internal height − separator width | **−2.00 mm** | **+1.00 mm** |
| package internal height − negative electrode width | **0.00 mm** | **+3.00 mm** |
| package internal height − positive electrode width | +1.00 mm | +4.00 mm |
| separator width − negative electrode width | +2.00 mm | +2.00 mm |
| negative electrode width − positive electrode width | +1.00 mm | +1.00 mm |

This is now a serious E004 hypothesis.

The **nested electrode relationship itself is STAR-like**: separator > negative > positive by exactly 2 mm and 1 mm, with the same 1.0/0.5 mm vertical-alignment offsets as the Siemens reference. The anomalous relation is between those layers and the package internal height:

- project separator is 2 mm *larger* than the nominal package internal height;
- project negative electrode is exactly equal to package internal height;
- Siemens reference has positive clearance around separator and both electrodes.

A zero package-to-negative margin is particularly relevant to an internal CAD error whose reported result is a zero extrusion. A negative package-to-separator margin is also geometrically suspect if `Package m_dintHeight` is consumed as a hard axial cavity limit.

Do **not** conclude that this is the cause. Test it.

Note: the August STEP characterization established that physical electrode widths drive realized jelly-roll axial length, while Detailed Builder `m_dJellyrollWidth_mm` did not. Therefore width changes can alter the generated macroscopic core and must be considered diagnostic only unless subsequently reconciled with the OpenFOAM-equivalent thermal target.

---

# B. Add four axial-clearance/recession variants to the campaign

Append C14–C17 to whatever C00–C13 package Claude has already generated. Do not regenerate C00–C13 unless necessary for deterministic packaging or matrix consistency.

Every new project TBM must be generated independently from the immutable failed baseline at commit `d74b328...`, never from another variant and never from the currently edited branch-tip copy.

## C14 — enlarge only the package internal axial cavity

Filename:

`C14_AXIAL_CAVITY68p11.tbm`

Only delta:

```text
Package m_dintHeight: 65.11 -> 68.11
```

Why `68.11`:

```text
68.11 - separator(67.11) = +1.00 mm
68.11 - negative(65.11) = +3.00 mm
68.11 - positive(64.11) = +4.00 mm
```

These are exactly the Siemens `validationBattery.tbm` axial clearance margins while retaining all project electrode/separator widths unchanged.

Purpose:

- isolates whether the package-internal axial constraint is causing the root feature to collapse;
- preserves electrode dimensions and therefore perturbs the electrochemical geometry less than shrinking electrodes;
- deliberately introduces a CAD clearance and is **diagnostic only**, not the final OpenFOAM-equivalent thermal target.

Do not update external height, RCR data, DataSheet, REPORT or stored volume fields in this variant. This must remain a one-field diagnostic delta unless STAR static validation proves the file impossible to parse.

## C15 — package axial clearance + leading feed/tail fix

Filename:

`C15_AXIAL_CAVITY68p11_FEED10_TAIL85.tbm`

Only deltas:

```text
Package m_dintHeight:       65.11 -> 68.11
m_dSepFeedLength_mm:         0    -> 10
m_dSepTailLength_mm:         0    -> 85
```

Purpose:

Tests the two strongest currently independent geometry hypotheses together:

- separator feed/tail zero lengths;
- zero/negative axial package clearance.

If C03 fails but C15 passes, axial package clearance participates in E004. If C14 passes by itself, feed/tail are not required to clear E004 under this geometry.

## C16 — explicit recessed-layer hierarchy inside the original 65.11 mm cavity

Filename:

`C16_RECESSED_LAYERS_FIXED_CAVITY.tbm`

Keep:

```text
Package m_dintHeight = 65.11
m_dOffsetNegAvg = 1.0
m_dOffsetPosAvg = 0.5
m_dOffsetSepAvg = 0.0
```

Change the physical axial layer widths by exactly −3.00 mm each so that the original package cavity obtains the same Siemens clearance hierarchy:

```text
SeparatorList1_Separator m_dWidth_mm: 67.11 -> 64.11

-Electrode m_dWidth:                      65.11 -> 62.11
-Electrode m_dCoatingWidth:               65.11 -> 62.11
-Electrode Collector m_dWidth_mm:         65.11 -> 62.11

+Electrode m_dWidth:                      64.11 -> 61.11
+Electrode m_dCoatingWidth:               64.11 -> 61.11
+Electrode Collector m_dWidth_mm:         64.11 -> 61.11
```

Resulting margins:

```text
package - separator = 1.00 mm
package - negative  = 3.00 mm
package - positive  = 4.00 mm
separator - negative = 2.00 mm
negative - positive  = 1.00 mm
```

Purpose:

- explicit electrode/separator recession test;
- keeps the original package internal height unchanged;
- tests whether E004 is caused by layer ends reaching/exceeding the package axial cavity.

**Critical restriction:** this is a geometry diagnostic, not a production electrochemical candidate. Physical electrode widths can alter active area, current-density mapping, realized jelly-roll/core axial extent, and potentially the effective conversion/use of area-normalized RCR quantities. Do not use C16 for electrical equivalence assessment.

Do not change tape widths, tab widths, tab lengths, S1–S6, RCR data, capacity, model map, radial geometry, or external package height.

## C17 — recessed-layer hierarchy + leading feed/tail fix

Filename:

`C17_RECESSED_LAYERS_FEED10_TAIL85.tbm`

Use all C16 width deltas plus:

```text
m_dSepFeedLength_mm: 0 -> 10
m_dSepTailLength_mm: 0 -> 85
```

Purpose:

Maximum axial-recession rescue test while retaining the original 65.11 mm package internal height.

Interpretation against C03/C14/C15/C16 identifies whether feed/tail and axial layer clearance act independently or interact.

---

# C. Why negative geometry distances are NOT part of this campaign

Do not introduce arbitrary negative values into any field named as a length, extrusion, feed, tail, S-distance, overlap, width, thickness or package dimension.

The desired physical idea is **recession/setback**, not negative CAD extrusion.

Use positive nested dimensions and STAR-supported alignment offsets to create recession. A negative value is only acceptable later if a Siemens reference or STAR documentation explicitly establishes that the specific field is a signed offset and defines the sign convention.

---

# D. Import-selection experiment — exploit STAR's selectable TBM import objects

STAR's `Create from Tbm` workflow presents an `Import Battery Options` dialog with selectable objects. Historical STAR tutorial instructions explicitly say to make sure **all objects are selected** for the normal cylindrical-cell workflow. Therefore selective import is real but must be treated as a diagnostic/alternative workflow until we understand the consequences.

Do not guess the exact checkbox/object names because they may differ by STAR version.

## D1. Capture the import-options schema first

Before Robert performs the project campaign, ask him for **one screenshot of the complete `Import Battery Options` dialog** after selecting a TBM, with all selectable object names visible.

Record those exact UI labels in:

`tbm_validation/STAR_IMPORT_OBJECT_SCHEMA_RUNTIME.md`

This screenshot/object list becomes runtime evidence. Do not translate or normalize names in the canonical record.

If one screenshot cannot show all objects, ask for enough screenshots to cover the full list.

## D2. Standard campaign imports remain ALL OBJECTS selected

For C00–C17, the primary result must use **all import objects selected**, matching the documented normal workflow.

Do not mix selective-import results into the main Cxx PASS/FAIL matrix.

Selective imports get separate IDs `Ixx` below.

## D3. Selective-import diagnostic matrix

After the exact object list is known, create the smallest set of subset tests that maps these conceptual groups if STAR exposes them separately:

```text
CELL/MODEL DATA
CORE / JELLYROLL
POSITIVE TAB / TERMINAL
NEGATIVE TAB / TERMINAL
PACKAGE / CAN
CAP / END PLATE
DETAILED ELECTRODE / ROOT GEOMETRY (if separately selectable)
OTHER OPTIONAL GEOMETRY
```

Use the exact STAR labels from Robert's dialog.

Recommended tests:

### I00 — all objects

Normal reference import. This is identical in selection to the main campaign.

### I01 — model/data only, geometry deselected, IF the dialog allows this

Purpose: prove whether the TBM cell/RCR data can be ingested without invoking the failing geometry feature.

Expected diagnostic value:

- if model/data import succeeds, E004 is cleanly isolated to geometry generation rather than RCR-table parsing;
- this does **not** prove a usable distributed 3D battery simulation.

### I02 — core/jellyroll + both electrical terminal/tab objects, omit package/can/cap if allowed

Purpose: test the minimum geometry likely required for the distributed 3D electrical core.

After import, inspect and record the Battery Cell / Battery Module Cell properties listed in section F.

### I03 — core/jellyroll + both electrical terminal/tab objects + can/cap

Purpose: candidate **minimal electrothermal geometry topology** if STAR permits it. This is the subset closest to the project objective:

- homogenized jelly-roll/core carries distributed battery behavior;
- positive and negative terminal paths remain available;
- can/cap remain for thermal coupling;
- unnecessary detailed electrode/root solids are omitted only if STAR exposes them independently.

Do not call this production-valid until the electrical-completeness checks pass.

### I04 — can/cap + jellyroll/core, intentionally omit electrical tab/root objects if allowed

Purpose: **geometry-only diagnostic** for the user's desired contact topology.

Do not use I04 for a production electrical simulation. If positive/negative current-entry parts are absent, the distributed 3D electrical current path is likely incomplete even if the RCR model node exists.

### I05 — toggle the object associated with the failing Electrode Root 1, if STAR exposes such an object separately

Once the UI schema is known, perform a one-object omission test against an otherwise all-selected import.

If omitting one object alone clears E004, that object becomes directly associated with the failing construction path. This is high-value evidence even if that omission is not acceptable for production.

---

# E. Separate electrical-data control: import the RCR tables without 3D geometry

This is a high-value control and should be performed once in STAR independently of `Create from Tbm`.

STAR documentation for a User Defined Battery Cell provides a workflow:

1. Create a **User Defined Battery Cell**.
2. Select the **RCR Model**.
3. Under the RCR equivalent-circuit model, use **Extract RCR Parameters from TBM File**.
4. Select the exact failed project TBM (`2c89d2d9...`).
5. Record whether STAR creates the expected RCR parameter tables and any warnings/errors.

Expected project result if the RCR section is valid:

```text
3 temperature-condition RCR parameter tables
288.15 K
298.15 K
308.15 K
```

Record this as:

`E00_RCR_DATA_ONLY_IMPORT`

This test bypasses the 3D cylindrical CAD builder. Therefore:

- E00 PASS strongly separates **RCR numerical-data import** from **Create from Tbm geometry failure**;
- E00 FAIL indicates an electrical/model-data issue that the geometry campaign does not address;
- E00 PASS does not prove correct distributed 3D spatial mapping or terminal connectivity.

If the UI exposes imported RCR values, capture enough evidence to confirm table count, temperatures and the presence of Ro/Rp/tau data. Do not ask Robert to validate every number manually.

---

# F. Electrical-completeness audit after ANY selective import that creates a cell

The presence of a Battery Cell node or RCR tables alone is not sufficient evidence that a distributed 3D simulation can run correctly.

STAR 3D cylindrical RCR cells expose an electrical mesh and the module maps geometry into three electrically important part classes:

```text
Core Parts
+ Tab Parts
- Tab Parts
```

For any I02/I03-style selective import, record the following before treating it as electrically usable:

## Battery Cell properties

```text
Unit Cell Model
Specified Electrical Mesh Dimensions
Actual Electrical Mesh Dimensions
Number of Spokes
Positive Post Parts (if present/used)
Negative Post Parts (if present/used)
```

Expected:

- Unit Cell Model identifies the intended RCR/3D model;
- electrical mesh dimensions exist and Actual Electrical Mesh Dimensions are non-empty/valid;
- Number of Spokes is valid;
- absence of optional external post parts is acceptable only if the cell's own terminal/tab route is otherwise complete.

## Battery Module Cell properties after assigning/generating parts

Record:

```text
Core Parts
+ Tab Parts
- Tab Parts
Battery Cell
```

For a usable distributed electrical cell, the minimum working assumption is:

```text
Core Parts      = populated with the jellyroll/core region(s)
+ Tab Parts     = populated with the positive electrical current-entry/current-exit part(s)
- Tab Parts     = populated with the negative electrical current-entry/current-exit part(s)
Battery Cell    = intended imported RCR cell
```

If Core Parts or either tab polarity is empty, classify:

`ELECTRICAL_COMPLETENESS = FAIL_OR_UNCONFIRMED`

Do not promote such a geometry to production even if CAD creation succeeds.

## Why this matters

STAR's battery module electrical topology is not just a scalar RCR object floating independently of geometry. The distributed 3D cell uses an electrical mesh over the cell/core and associates positive and negative tab parts with the module cell. Current/heat reports and connector-ohmic-heating setup reference the jellyroll/core and terminal interfaces.

Therefore:

- **can/cap/jellyroll only** can be a useful geometry/thermal diagnostic but is not enough evidence for a valid distributed electrical model;
- **jellyroll/core + positive tab + negative tab** is the likely minimum electrical geometry;
- **jellyroll/core + both tabs + can/cap** is the preferred minimal topology to test for the project's electrothermal objective if STAR allows the detailed electrode/root geometry to be omitted independently.

Can/cap are primarily required here for thermal conduction/contact and package representation; they do not substitute for the positive/negative electrical terminal assignments.

---

# G. Production interpretation: what to do if a recessed/clearance geometry imports

A diagnostic import PASS is not automatically the final geometry.

## If C14/C15 pass and fixed-cavity variants fail

STAR likely requires positive axial clearance between the detailed winding geometry and package cavity. Then:

1. retain a small STAR-compatible CAD clearance in the generated geometry;
2. restore the OpenFOAM-equivalent **ideal thermal contact** using STAR contact/interface treatment rather than filling the clearance with a physical air gap;
3. verify that the selected electrical core/tab parts remain correct;
4. validate integrated electrothermal response against the OpenFOAM–ECM reference.

The numerical CAD clearance is then a topology workaround, not a physical model assumption.

## If C16/C17 pass

Do not adopt the reduced electrode widths directly. They modify physical active geometry.

Use the result only to establish that axial layer/package coincidence was causing E004. Then search for a STAR-compatible way to preserve project electrical active dimensions while introducing only the minimum CAD/end clearance necessary for topology.

C14 is preferable to C16 as a production starting point because it preserves electrode/separator widths.

## If I03 succeeds while all-object Create from Tbm fails

This may provide a cleaner architecture: use only the geometry objects required for the homogenized core, both electrical terminals and thermal can/cap, while suppressing an unnecessary detailed CAD feature.

Before adopting it, pass the Section F electrical-completeness audit and then run a one-cell electrical/thermal parity check.

---

# H. Update campaign matrices and runtime result format

Extend `CAMPAIGN_MATRIX.csv` / `.md` with C14–C17 and at minimum these columns:

```text
package_int_height_mm
separator_width_mm
negative_width_mm
positive_width_mm
package_minus_separator_mm
package_minus_negative_mm
package_minus_positive_mm
```

Add a separate selective-import matrix:

`IMPORT_SELECTION_MATRIX.csv`

with columns:

```text
id
tbm_id
exact_import_object_selection
cell_node_created
geometry_created
e004_present
new_error_text
unit_cell_model
electrical_mesh_present
core_parts_populated
positive_tab_parts_populated
negative_tab_parts_populated
electrical_completeness
notes
```

Add `E00_RCR_DATA_ONLY_IMPORT` to the README as a separate optional but strongly recommended diagnostic, not as a Cxx geometry test.

Robert's compact result format should become:

```text
C00: PASS / exact error
...
C17: PASS / exact error

E00 RCR-data-only import: PASS / exact error

Import-options screenshot: attached
```

Selective Ixx results can be run only after the import-options object list is known; do not burden Robert with guessed checkbox instructions.

---

# I. Recommended priority order for the newly added tests

Do not make Robert run all new variants before high-information tests. Integrate the following early in the existing runtime order:

```text
C00          Siemens environment control
C03          feed+tail leading hypothesis
C14          axial cavity clearance only
C15          axial cavity + feed/tail
C16          recessed layers fixed cavity
C17          recessed layers + feed/tail
C10/C12/C13 broad rescue controls
remaining isolation variants
```

Also request the Import Battery Options screenshot at the start.

The data-only RCR control E00 can be performed at any convenient point because it does not depend on geometry success.

---

# J. Completion requirements for Claude

Claude must:

1. incorporate C14–C17 into the existing deterministic campaign generator rather than hand-editing final TBMs;
2. source all new variants from the immutable Robert-tested baseline at `d74b328...`;
3. assert exact field delta counts;
4. preserve protected RCR/model data in every C14–C17 variant;
5. update campaign CSV/Markdown matrices and README;
6. add the import-selection and E00 instructions without inventing STAR UI object names;
7. run validator/static checks on all new files;
8. compute SHA-256 for all new files and final ZIP;
9. push all generated files, scripts and documentation;
10. report whether the generated axial margins exactly match those specified here;
11. do **not** call any new variant electrically equivalent simply because it imports;
12. do **not** declare E004 resolved before Robert's runtime results.

Final completion report must state:

```text
branch
commit
campaign ZIP path + SHA-256
C14 SHA + exact deltas + margins
C15 SHA + exact deltas + margins
C16 SHA + exact deltas + margins
C17 SHA + exact deltas + margins
protected RCR-data parity result
validator result for each new variant
README updated: yes/no
IMPORT_SELECTION_MATRIX created: yes/no
E00 instructions included: yes/no
E004 status: ACTIVE / UNRESOLVED
```
