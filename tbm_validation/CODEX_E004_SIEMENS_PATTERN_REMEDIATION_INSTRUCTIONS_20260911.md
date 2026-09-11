# Codex Instructions — E004 Siemens-Pattern Remediation and TBM Hardening

**Date:** 2026-09-11  
**Repo:** `jazbin/ECM`  
**Target branch:** `tbm-rcr-modelmap-fix-exec`  
**Starting branch state:** verify current tip before editing; at handoff it is `9262007e5fbe4fa4eb4922e882bd90161626f9c8`.  
**Runtime state:** `Electrode Root 1 : Extrusion distance can not be 0` remains unresolved.  
**Primary findings:** `tbm_validation/SIEMENS_CYLINDRICAL_TBM_GEOMETRY_PATTERN_FINDINGS_20260911.md`

---

## 0. Objective and non-negotiable rules

Your task is to harden the E004 investigation and prepare the repository so the next STAR runtime result can be converted into the **smallest defensible production fix**.

Do **not** guess a final production geometry and do **not** overwrite the approved exact-contact RCR TBM merely because a Siemens reference uses a different value.

The governing objective is model equivalence to the existing OpenFOAM-ECM reference. Read these first:

1. `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`
2. `tbm_validation/SIEMENS_CYLINDRICAL_TBM_GEOMETRY_PATTERN_FINDINGS_20260911.md`
3. `tbm_validation/STAR_E004_AXIAL_RECESS_IMPORT_AND_ELECTRICAL_ADDENDUM_20260910.md`
4. `tbm_validation/E004_CAMPAIGN_INDEPENDENT_REVIEW_20260911.md`
5. `tbm_validation/STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_20260910.md`
6. `tbm_validation/STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_ADDENDUM_20260910.md`
7. `tbm_validation/STAR_E004_CAMPAIGN_GENERATOR_HANDOFF.md`

The following are protected unless new STAR runtime evidence directly requires a change:

```text
external OD                       21.09 mm
external height                   70.02 mm
package/can ID                    20.6274 mm
radial JR OD                      20.6274 mm
mandrel diameter                  6 mm
active IET                        RCRTable 3D
thermal model                     Distributed
RCR capacity                      5 Ah
RCR temperature sets              288.15 / 298.15 / 308.15 K
RCR SOC grid                      preserve exactly, including -0.08
RCR Vequ/Ro/Rp/tau/entropy data   preserve bit-for-bit where possible
both tabs                         enabled
both tabs                         same-face/top
+Electrode S3                     5 mm
-Electrode S3                     50 mm
Transport Number sets             0
```

Do not globally normalize inactive SIMMOD flags. Only active-block contracts matter unless a runtime importer proves otherwise.

---

## 1. First task — verify the branch and existing campaign before changing anything

The previous review defects were already fixed at commit `9262007e5fbe4fa4eb4922e882bd90161626f9c8`:

- C00/C13 axial metadata is parsed from emitted TBM content rather than inherited defaults.
- C12/C13 interpretation is paired correctly.
- `assert_axial_regression` checks matrix geometry against emitted TBM bytes.
- all 18 campaign TBM SHA-256 values remained unchanged by that metadata fix.

Therefore **do not re-fix those items blindly**.

Before work:

```bash
git status --short
git rev-parse HEAD
git log -5 --oneline
```

If the branch has advanced, review the intervening commits and adapt. Do not reset or discard other agent/user work.

Run the existing campaign generator and tests exactly once before edits and record baseline outputs/hashes.

---

## 2. Build a quantitative Siemens cylindrical-geometry analyzer

The current corpus contains enough information to move from representative examples to quantified regularities. Implement this now.

### 2.1 Source handling

The Siemens corpus is on sibling branch/commit:

```text
branch: tbm-siemens-reference-corpus
commit: b0be477f19bf16eaff92eafd9f3ba07fb6f3152d
```

Do **not** merge that branch wholesale into `tbm-rcr-modelmap-fix-exec`.

Read required files using one of these controlled approaches:

- `git show b0be477f19bf16eaff92eafd9f3ba07fb6f3152d:<path>`;
- a temporary detached worktree;
- a temporary extraction directory outside tracked output.

Do not duplicate 179 corpus TBMs into the active branch unless absolutely necessary.

### 2.2 New tool

Create something equivalent to:

```text
tools/analyze_siemens_cylindrical_geometry_patterns.py
```

The script must be deterministic and must parse the TBM text directly rather than relying only on stale REPORT values.

For every TBM considered, extract at minimum:

```text
source_class
source_path
content_sha256
tbmfileversion
cell geometry/type classification
Package m_dextDiameter
Package m_dintDiameter
Package m_dextHeight
Package m_dintHeight
Detailed Builder m_dJellyrollThickness_mm
Detailed Builder m_dJellyrollWidth_mm
Detailed Builder m_dMandrelThickness_mm
Detailed Builder m_dMandrelWidth_mm
Detailed Builder m_dElectrodeOverlapAtStart_mm
Detailed Builder m_dElectrodeOverlapAtEnd_mm
Detailed Builder m_dOffsetNegAvg
Detailed Builder m_dOffsetPosAvg
Detailed Builder m_dOffsetSepAvg
Detailed Builder m_dSepFeedLength_mm
Detailed Builder m_dSepTailLength_mm
Detailed Builder m_nNumSpokes
Detailed Builder tab-enable and vertical-orientation fields
separator physical width
negative electrode physical width
negative coating/collector width(s), where represented
positive electrode physical width
positive coating/collector width(s), where represented
```

Also derive:

```text
radial_delta = builder_JR_OD - package_intDiameter
margin_sep   = package_intHeight - separator_width
margin_neg   = package_intHeight - negative_width
margin_pos   = package_intHeight - positive_width
sep_minus_neg
neg_minus_pos
feed_tail_both_zero
```

### 2.3 Classification

Separate evidence into at least these groups:

1. `STAR_INSTALL`
2. `STAR_SAMPLE_VALIDATION_TUTORIAL`
3. `BDS_PROJECT`
4. `OTHER_OR_UNCLASSIFIED`

Do not mix pouch/prismatic constructions into cylindrical statistics. Classify cylindrical files conservatively using TBM geometry/type markers plus the presence/meaning of the Detailed Builder fields. If uncertain, mark `UNCLASSIFIED` rather than guessing.

### 2.4 Deduplication

The corpus inventory contains duplicates. Frequency statistics must be based on **unique content SHA-256**, not raw path count.

Retain path aliases for traceability, but count each unique TBM only once in distribution summaries.

### 2.5 Outputs

Add generated, human-reviewable outputs under e.g.:

```text
tbm_validation/siemens_geometry_analysis/SIEMENS_CYLINDRICAL_GEOMETRY_MATRIX.csv
tbm_validation/siemens_geometry_analysis/SIEMENS_CYLINDRICAL_GEOMETRY_STATISTICS.md
```

The Markdown report must report, separately by evidence class:

- number of unique TBMs included;
- number excluded and why;
- frequencies/distributions of exact radial equality, positive/zero/negative radial delta;
- frequencies/distributions of package-minus-separator/negative/positive axial margins;
- frequencies of zero feed, zero tail and both zero;
- common feed/tail pairs;
- common overlap start/end pairs;
- common offset triples;
- frequencies of JR width zero;
- frequencies of round-mandrel width zero;
- clear list of outliers that resemble the project geometry.

Do not state universal invariants when fields are missing or source populations are small. Make denominator explicit for every percentage.

---

## 3. Harden `validate_tbm.py` around the geometry patterns — WARN first, not FAIL

Add geometry diagnostics so future hand-edited TBMs cannot silently reproduce the same suspicious relationships.

For cylindrical Detailed Builder cases, add diagnostics equivalent to:

```text
AXIAL_MARGIN_SEPARATOR_NEGATIVE
    package_intHeight - separator_width < 0

AXIAL_MARGIN_NEG_NONPOSITIVE
    package_intHeight - negative_width <= 0

AXIAL_MARGIN_POS_NONPOSITIVE
    package_intHeight - positive_width <= 0

SEPARATOR_FEED_TAIL_BOTH_ZERO
    feed == 0 and tail == 0

RADIAL_JR_EXCEEDS_PACKAGE_ID
    JR_OD > package_ID

RADIAL_JR_EQUALS_PACKAGE_ID
    JR_OD == package_ID
```

Important severity rules:

- separator overrun / nonpositive electrode margin: initially `WARN`, with the actual calculated margin in the message;
- separator feed/tail both zero: initially `WARN`;
- JR exceeding package ID: `WARN` or existing geometry failure severity according to current validator architecture;
- exact JR/package-ID equality: **INFO/PASS**, not warning or failure; the Siemens corpus demonstrates this can be intentional;
- `m_dJellyrollWidth_mm = 0`: never fail solely on zero for cylindrical geometry;
- `m_dMandrelWidth_mm = 0`: never fail solely on zero for a round cylindrical mandrel.

Only promote a new warning to `FAIL` after either:

1. STAR runtime proves it is an importer requirement; or
2. the quantitative corpus analysis demonstrates an unambiguous structural invariant with adequate sample size.

Add focused unit/regression tests for each diagnostic.

---

## 4. Verify the existing E004 diagnostic TBMs semantically

Do not generate a second redundant campaign. The current `C00-C17` campaign already contains the important cases.

Write or extend a semantic-diff test that starts from the project baseline and verifies each relevant variant changes **only** its intended fields.

At minimum assert:

### C03 — separator feed/tail only

```text
m_dSepFeedLength_mm: 0 -> 10
m_dSepTailLength_mm: 0 -> 85
```

No active electrode width, package height, radial geometry, RCR data, MODELMAP or tab field may change.

### C14 — package axial clearance only

```text
Package m_dintHeight: 65.11 -> 68.11
```

Target margins become:

```text
separator +1 mm
negative  +3 mm
positive  +4 mm
```

No physical layer width changes.

### C15

Exactly `C14 + C03`; nothing else.

### C16 — physical-layer recession diagnostic

Keep package internal height `65.11 mm`; reduce all relevant physical layer-width representations consistently by `3 mm` so the intended package-minus-layer margins become `+1/+3/+4 mm`.

Expected principal widths:

```text
separator 67.11 -> 64.11
negative  65.11 -> 62.11
positive  64.11 -> 61.11
```

Where the TBM has redundant physical width representations for coating/current collector/electrode, verify the generator updates the complete coupled set intended by the existing addendum. Do not leave inconsistent duplicates.

### C17

Exactly `C16 + C03`; nothing else.

### C12/C13

Retain the corrected paired interpretation from commit `9262007`. Add tests preventing regression to the old “C13 pass alone proves builder cause” wording.

---

## 5. Update campaign execution priority without changing campaign TBMs

Update documentation/README ordering so the client or operator runs the highest-information tests first:

```text
1. C00  Siemens control
2. C14  axial package margin only
3. C03  separator feed/tail only
4. C15  axial margin + feed/tail
5. C16  physical-layer recession only
6. C17  recession + feed/tail
7. C12  Siemens Detailed Builder under project PCD
8. C13  Siemens PCD + Detailed Builder
9. remaining isolation cases only if the above do not localize E004
```

Do not alter the TBM bytes simply to reorder the package. If re-zipping changes archive hash, document that only packaging/order changed and list individual TBM SHA-256 values.

---

## 6. Runtime decision tree — this determines the actual production fix

Codex cannot infer the final production change from static data alone. Once Robert returns STAR results, apply exactly the following logic.

### Case A — `C14 PASS`, `C03 FAIL`

Interpretation: positive axial package/layer construction margin is the leading cause.

Production-remediation direction:

1. Prefer the **package-internal-height workaround** before shrinking physical electrode widths, because it preserves the physical layer dimensions already used by the reference/electrical model.
2. Start from the exact-contact production baseline and change only the minimum axial package field proven necessary.
3. Do not change external height.
4. Preserve radial `20.6274/20.6274` equality.
5. Import/generate geometry and inspect the axial bodies/interfaces.
6. If the CAD workaround creates a finite axial gap to the cap/end surface, explicitly restore the OpenFOAM ideal-contact thermal path using STAR contact/interface treatment. The CAD gap is numerical, not physical.
7. Recheck integrated thermal resistance/heat path before calling the model equivalent.

Do not declare production release from import PASS alone.

### Case B — `C03 PASS`, `C14 FAIL`

Interpretation: separator lead/trail geometry is the leading cause.

Production-remediation direction:

1. Apply the proven feed/tail values to the exact-contact baseline, initially `10/85 mm` because this is the HP18650/STAR reference pattern used by C03.
2. Preserve package height and all physical electrode widths.
3. Verify generated separator geometry does not change active electrode area or electrical mapping.
4. Re-run static validator and protected-field/RCR hash checks.
5. Prefer this route over axial PCD changes if geometry/electrical outputs remain equivalent.

### Case C — `C14 FAIL`, `C03 FAIL`, `C15 PASS`

Interpretation: interaction between axial room and separator feed/tail.

Production-remediation direction:

- apply both proven changes as a candidate;
- then perform the same topology/contact inspection required in Case A;
- verify separator geometry as in Case B;
- do not simplify back to one change without a runtime test proving that simplification.

### Case D — `C16 PASS` while `C14 FAIL`

Interpretation: merely enlarging package internal height is insufficient; STAR appears to care about the physical layer extents/recession.

This is higher risk because physical widths are consumed by geometry/electrochemical construction.

Required before production approval:

1. identify every field tied to separator/negative/positive physical width;
2. prove no inconsistent duplicate remains;
3. quantify change in active area, current collector geometry, tab placement, heat source volume and any derived conductivity/thermal path;
4. determine whether active electrical quantities must be recomputed or explicitly overridden;
5. compare integrated current/voltage/heat generation against the OpenFOAM-ECM reference;
6. restore ideal thermal end contact if recession creates a geometric gap.

Do not silently adopt C16/C17 geometry as “the final cell.”

### Case E — `C12 PASS`

Interpretation: Siemens Detailed Builder alone clears E004 under project PCD; project Detailed Builder / derived builder construction is strongly implicated.

Action:

- diff project Detailed Builder against transplanted Siemens builder field-by-field;
- rank deltas by the Siemens-pattern findings;
- minimize changes in this order: axial-effecting builder fields / feed-tail first, overlap next, mandrel width later;
- use new single-delta candidates only if the existing Cxx cases do not already isolate the responsible field.

### Case F — `C12 FAIL + C13 PASS`

Interpretation: project PCD or PCD-Builder interaction is required to reproduce the failure.

Action:

- focus on package/layer axial relations and other PCD geometry consumed by the builder;
- do not blame a single Detailed Builder field solely from C13.

### Case G — `C00 FAIL`

Stop. Do not interpret C03/C14/etc. Resolve STAR version/import path/reference compatibility first.

---

## 7. Production-candidate generation rules after localization

Once a runtime case identifies the minimum successful delta, generate a **new candidate file** rather than editing the historical final TBM in place.

Suggested naming:

```text
out/rcr_candidate/hp2170-rcr-e004-remediation-<cause>-v1.tbm
```

Every candidate must have:

- exact source baseline SHA-256 recorded;
- exact candidate SHA-256 recorded;
- machine-readable semantic diff;
- protected-field manifest;
- RCR-payload hash/equality result;
- validator output;
- explicit statement of whether it is `DIAGNOSTIC`, `RUNTIME_IMPORT_PASS`, or `PRODUCTION_EQUIVALENCE_CANDIDATE`.

Do not use the word `FINAL` until STAR import, geometry inspection, electrical completeness and reference-equivalence checks all pass.

---

## 8. Required tests

Add/retain tests covering all of the following:

1. balanced TBM structural tags;
2. no duplicate MODELMAP selections;
3. unique selected active SIMMODs;
4. no unintended duplicate keys in selected blocks;
5. all numeric RCR values finite;
6. RCR set count/index completeness;
7. RCR source payload unchanged across geometry-only diagnostics;
8. capacity remains `5 Ah`;
9. temperature sets remain exactly `288.15/298.15/308.15 K`;
10. SOC grid remains exactly unchanged including `-0.08`;
11. tab enable/orientation remains project-correct;
12. `+S3=5`, `-S3=50`, Transport Number sets=0;
13. radial equality remains `20.6274 - 20.6274 = 0` in project-equivalence candidates;
14. campaign matrix geometry values are parsed from emitted TBMs and equal actual bytes;
15. each Cxx semantic diff matches its contract;
16. deterministic generated outputs and SHA manifest;
17. new Siemens analyzer deduplicates by content SHA before statistics;
18. validator recognizes exact radial equality as valid/informational rather than requiring a positive gap.

Run the focused suite plus the existing full TBM validator/regression suite before commit.

---

## 9. Deliverables for this Codex pass

Complete as much as possible without STAR runtime access. The expected deliverables are:

```text
tools/analyze_siemens_cylindrical_geometry_patterns.py

tbm_validation/siemens_geometry_analysis/
  SIEMENS_CYLINDRICAL_GEOMETRY_MATRIX.csv
  SIEMENS_CYLINDRICAL_GEOMETRY_STATISTICS.md

validator updates in tools/validate_tbm.py
focused tests for the new geometry diagnostics
semantic-diff/regression tests for C03/C14/C15/C16/C17/C12/C13
campaign documentation updated with the revised priority order
```

If the quantitative corpus result contradicts any statement in the findings document, **do not force the data to fit the document**. Update the finding with the measured result and explain the contradiction.

Do not create speculative production changes merely to have another TBM artifact.

---

## 10. Commit / handoff requirements

Use one or more focused commits. In the final handoff report provide:

```text
BRANCH
HEAD SHA
FILES CHANGED
TESTS RUN + PASS/FAIL COUNTS
SIEMENS UNIQUE CYLINDRICAL SAMPLE COUNTS BY SOURCE CLASS
KEY QUANTITATIVE REGULARITIES
VALIDATOR WARNINGS ADDED
CAMPAIGN SEMANTIC-DIFF STATUS
ANY CHANGE TO INDIVIDUAL C00-C17 TBM SHA256 VALUES
ANY CHANGE TO ZIP SHA256
OPEN ITEMS THAT REQUIRE ROBERT/STAR RUNTIME
```

Push all generated CSV/Markdown evidence needed for independent review, but do not commit temporary worktrees, caches, extracted full Siemens corpus copies, build directories, or unrelated files.

### Final state wording

Until STAR proves otherwise, end with:

```text
E004_RUNTIME_STATUS = ACTIVE / UNRESOLVED
STATIC_PATTERN_ANALYSIS = COMPLETE or INCOMPLETE
PRODUCTION_TBM_CHANGED = NO
NEXT_RUNTIME_PRIORITY = C00 -> C14 -> C03 -> C15 -> C16 -> C17 -> C12 -> C13
```

If a runtime PASS is later supplied, update status precisely. Do not convert a static inference into a runtime claim.
