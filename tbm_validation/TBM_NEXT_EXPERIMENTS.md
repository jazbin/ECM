# TBM Next Experiments — Authoritative
**Last updated:** 2026-09-22
**Supersedes:** TBM_NEXT_EXPERIMENTS_CLAUDE.md (retained as audit evidence)

---

## Campaign discipline

Every future TBM sent to Robert must specify:

```
Hypothesis IDs tested:
Frozen baseline:
Changed field(s):
  Field name:
  Block:
  Old value:
  New value:
Predicted observable:
Falsifier:
Required STAR output:
Required STEP measurement (if PASS):
```

No broad multi-variable campaign unless explicitly justified by an internal contradiction that cannot be resolved by one-factor tests.

---

## Current campaign: RAD — Radial field identification

**Purpose:** Establish isolated causal mappings between TBM fields and generated Can OD, Can ID, and JR OD before attempting the production geometry. T06 is the frozen baseline for all RAD tests.

### T06 baseline (frozen for all RAD tests)

| Field | Block | Value |
|---|---|---|
| Package m_dextDiameter | pcd | 21mm |
| Package m_dintDiameter | pcd | 20.9mm |
| m_dJellyrollThickness_mm | Detailed Builder | 17.9mm |
| m_dRepCanXDim | REPORT | 18mm |
| m_dRepCanYDim | REPORT | 18mm |
| +Electrode m_dWidth | pcd | 64.11mm |
| -Electrode m_dWidth | pcd | 65.11mm |
| +Electrode Tab m_dLength_mm | pcd | 66.11mm (+2.00mm surplus) |
| -Electrode Tab m_dLength_mm | pcd | 67.11mm (+2.00mm surplus) |
| Package m_dintHeight | pcd | 65.11mm |

STEP measurements available from T06 (exact B-Rep, committed audit 2026-09-17):
- JR OD = 17.880992 mm
- Can ID = 18.000000 mm
- Can OD = 20.900 mm (approximate; from STEP bounding-box analysis)
- JR axial height = 65.11 mm (EXACT match to OpenFOAM target)
- +Ve Tab Stem top-Y = 66.275 mm
- Can↔JR radial gap = 0.059504 mm (half-space)

RAD-A/B/C will establish the operative field→geometry mappings, not these first measurements.

---

### RAD-A — Isolate Package m_dintDiameter

```
Hypothesis IDs tested: RMAP-3 (m_dintDiameter → Can ID?)
Frozen baseline: T06
Changed field: Package m_dintDiameter (pcd block)
  Old value: 20.9mm
  New value: 19.0mm
All other radial fields unchanged: m_dextDiameter=21, m_dJellyrollThickness_mm=17.9,
  m_dRepCanXDim=18, m_dRepCanYDim=18
Primary question: which generated radial quantity (Can ID, Can OD, or neither) is
  controlled by Package m_dintDiameter?
  — Do NOT pre-assume the answer is Can ID; current evidence is ambiguous.
Falsifier: no radial change in STEP → m_dintDiameter not a direct geometry driver
Required BDS result: BDS generation PASS/FAIL; return STEP file if PASS
Post-return automated analysis (our side): Can OD, Can ID, JR OD from exact B-Rep
```

**Interpretation matrix:**
- Can ID shifts toward 19mm, Can OD unchanged: m_dintDiameter → Can ID (supports RMAP-3)
- Can OD shifts toward 19mm, Can ID unchanged: m_dintDiameter → Can OD (revises RMAP-2 and RMAP-3)
- Both change: coupled geometry; investigate
- Neither changes: m_dintDiameter not a direct geometry driver
- Generation fails: report exact BDS error message

---

### RAD-B — Isolate m_dRepCanXDim / m_dRepCanYDim

```
Hypothesis IDs tested: RMAP-2 (m_dRepCanXDim/YDim → Can OD?)
Frozen baseline: T06
Changed fields: m_dRepCanXDim AND m_dRepCanYDim (REPORT block)
  — both must change together: circular cross-section requires X = Y = diameter;
    independent change would assert an elliptical can, physically incoherent
  Old values: 18mm / 18mm
  New values: 19mm / 19mm
All other radial fields unchanged: m_dextDiameter=21, m_dintDiameter=20.9,
  m_dJellyrollThickness_mm=17.9
Predicted observable (if RMAP-2 true): Can OD ≈ 19mm in STEP; JR OD unchanged ≈ 17.9mm
Predicted observable (if REPORT regenerated at import): no change in Can OD
  — STAR overwrites REPORT block; another field (m_dextDiameter or m_dintDiameter) drives Can OD
Falsifier: Can OD unchanged → m_dRepCanXDim/YDim are not the operative Can OD control
Required BDS result: BDS generation PASS/FAIL; return STEP file if PASS
Post-return automated analysis (our side): Can OD, Can ID, JR OD from exact B-Rep
```

**Note:** A null result (no geometry change) from RAD-B is itself highly informative — it would require revisiting RMAP-2 and promoting m_dextDiameter or m_dintDiameter as the Can OD candidate.

---

### RAD-C — Isolate m_dJellyrollThickness_mm

```
Hypothesis IDs tested: RMAP-1 on T06-baseline geometry (August characterization
  used different cell class; verify mapping holds here before RAD-D depends on it)
Frozen baseline: T06
Changed field: m_dJellyrollThickness_mm (Detailed Builder block)
  Old value: 17.9mm
  New value: 17.5mm
  (decrease — safely below current generated Can ID = 18.000 mm; avoids radial blocker)
All other radial fields unchanged
Predicted observable: JR OD ≈ 17.5mm in STEP; Can OD and Can ID unchanged
Falsifier: JR OD unchanged → m_dJellyrollThickness_mm does not directly control
  JR OD on this geometry class (would require re-examining August finding)
Required BDS result: BDS generation PASS/FAIL; return STEP file if PASS
Post-return automated analysis (our side): JR OD, Can OD, Can ID from exact B-Rep
```

---

### RAD-D1 — Production geometry, positive clearance

**Prerequisite:** RAD-A, RAD-B, RAD-C all completed.

Do NOT pre-fill TBM field values until RAD-A/B/C establish the mapping. The target geometry is:

```
Goal Can OD = 21.09mm
Goal Can ID = 20.6274mm
Goal JR OD ≈ 20.50mm  (positive radial clearance ≈ 0.06mm from Can ID)
Root surplus: both = +2.00mm (T06 baseline — frozen)
```

```
Hypothesis IDs tested: production geometry viability with positive clearance
Baseline: T06 with radial fields set per RAD-A/B/C mapping
Changed fields: all radial fields set to achieve production geometry
  (specific field→value mapping filled in after RAD-A/B/C)
Predicted observable: import PASS; 13-body STEP with Can OD=21.09,
  Can ID=20.6274, JR OD≈20.50
Falsifier: FAIL with any error → note exact error; triggers contingency
Required STAR output: import result + error message if FAIL
Required STEP measurement (if PASS):
  - Can OD
  - Can ID
  - JR OD
  - Body count and body names (confirm 13-body topology retained)
```

---

### RAD-D2 — Production geometry, exact JR/Can contact

**Prerequisite:** RAD-D1 PASS.

```
Goal Can OD = 21.09mm
Goal Can ID = 20.6274mm
Goal JR OD = 20.6274mm  (= Can ID, exact contact)
Root surplus: both = +2.00mm (T06 baseline)
```

```
Hypothesis IDs tested: H004-3 (physical zero-clearance contact constructibility)
Baseline: RAD-D1 TBM (successful production geometry)
Changed field: only the JR OD driver (m_dJellyrollThickness_mm or equivalent per RMAP-1)
  Old value: RAD-D1 value (≈20.50mm target)
  New value: 20.6274mm (= Can ID)
Predicted observable (H004-3 OPEN → construction succeeds): import PASS;
  STEP confirms JR OD = Can ID = 20.6274mm with zero radial clearance
Falsifier: FAIL with geometry error → physical contact causes construction failure;
  production geometry must use JR OD < Can ID
Required STAR output: import result + error message if FAIL
Required STEP measurement (if PASS):
  - Can OD, Can ID, JR OD (verify values and confirm zero clearance)
```

---

## Passive retrieval (not campaign-blocking)

**R006:** Production TBM with SepFeed=10/SepTail=85 — sent to Robert 2026-09-10, result not received. Ask Robert for the result opportunistically. Do NOT hold the RAD campaign pending R006.

---

## Contingency (only if RAD-D1 fails unexpectedly)

**H011 — C00/C12/C13 Builder localization:**
- C00: run Siemens HP18650 in Robert's environment (environment control)
- C12: Siemens Detailed Builder inside project PCD
- C13: Siemens PCD + Builder inside project model context
- Do not build or run these until RAD-D1 produces an unexplained failure.

---

## Deferred / low value

| Experiment | Reason deferred |
|---|---|
| Exact E004 threshold localization (midpoint ~0.35mm) | T06 (+2mm) is robust; threshold location does not change production fix |
| Asymmetric surplus discrimination (max vs avg formula) | Does not change production fix; T06 covers any plausible formula |
| Additional S3 variants | H004-1 REFUTED |
| Additional tab-orientation variants | H002 REFUTED |
| Additional m_bOnly1D variants | H003 REFUTED |
| Package m_dintHeight isolated variants | H004-6 REFUTED |
| T-series surplus > 2mm | H009 saturation; no new information |

---

## What NOT to send Robert

- Another tab-on/off permutation
- Another S3 variant
- Another m_bOnly1D variant
- Another Package m_dintHeight isolated change
- F-series cases without first fixing m_dRepCanXDim/YDim
- Any TBM that changes more than one radial field at a time before RAD-A/B/C are complete
