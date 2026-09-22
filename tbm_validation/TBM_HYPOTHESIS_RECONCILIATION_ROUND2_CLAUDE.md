# TBM Hypothesis Reconciliation — Round 2 Response
**Date:** 2026-09-22
**Status:** Final reconciliation before canonicalization. Five epistemic issues resolved.
**Key correction:** Round-1 radial field mapping error acknowledged — m_dRepCanXDim → Can OD (not Can ID). Evidence source: GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md.
**Files modified by this round:** This document only. Canonical ledger not yet revised.

---

## Remaining reconciliation

| Issue | Position | Corrected statement/status |
|---|---|---|
| **1. R005 physical state language** | **AGREE** | R005 failed with E004 and never generated geometry. The claim "R005 physical state was JR OD 20.6274 < Can ID 21.09mm" was too strong: those are TBM input intentions interpreted through a mapping inferred from other cases, not observed generated dimensions. **Corrected:** R005 establishes only that its field combination (m_dintDiameter = m_dJellyrollThickness_mm = 20.6274mm, m_dRepCanXDim = 21.09mm) does not eliminate E004. Whether the intended JR OD = Can ID contact state would have been realized in generated geometry is unknown, because construction never completed. |
| **2. H007 causal language** | **AGREE** | "E004 is caused by insufficient combined tab-electrode surplus" asserts STAR's internal rule, which has not been proven. We observe a strong correlation across H/T cases but cannot distinguish competing derived quantities (Delta_avg, Delta_max, Delta_sum) on the sparse dataset, and do not know the internal formula. **Corrected:** All occurrences of "is caused by" should read "is strongly associated with." The known-facts entry should use observational language (see Canonical Facts below). |
| **3. Radial mapping — SUPPORTED not CONFIRMED + correction of round-1 error** | **AGREE — and a round-1 error must be acknowledged** | Round 1 stated m_dRepCanXDim → Can ID. This conflicts with the existing repository evidence. `GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md` (line 19) states: "REPORT can diameter **apparently drove can OD** in the tested matrix." That characterization ran isolated one-variable STEP tests (m_dJellyrollThickness_mm confirmed as JR OD driver from multiple isolated points; m_dRepCanXDim observed to track Can OD). My round-1 inversion (m_dRepCanXDim → Can ID) was wrong. The correct assignment, at SUPPORTED/HIGH, is: m_dRepCanXDim → Can OD; m_dJellyrollThickness_mm → JR OD (stronger: confirmed from August isolated tests); m_dintDiameter → unknown/Can ID (untested in August matrix, inferred only from naming and "exact-contact-final" design intent). The F-series failure chain is consistent with m_dRepCanXDim → Can OD: inherited D00 value 18mm → Can OD ≈ 18mm; m_dJellyrollThickness_mm = 20.6274mm → JR OD = 20.6274mm >> Can OD → STAR clamps Can ID = 20.6274mm → Can thickness = (18 − 20.6274)/2 < 0 → fatal. RAD-A, -B, -C exist to convert these supported correlations into isolated causal mappings. |
| **4. T06 exact baseline fields** | See specification section | |
| **5. RAD-D split into D1/D2** | **AGREE** | A small-positive-clearance control before the exact-contact test is better campaign design and adds one discriminating data point at low cost. Specification below. |

---

## Canonical facts safe to freeze

1. E004 is preceded and gated by E003 (mandrel thickness). Once E003 is absent, E004 appears as the next runtime failure in all R-events where downstream construction is attempted.
2. Tabs disabled, tab orientation, m_bOnly1D values, S3 field, and transport number metadata each leave E004 unchanged across dedicated R-events (R002–R005). These fields are frozen.
3. Package m_dintHeight isolated change of +0.10mm and +0.70mm (ROOT_A/ROOT_B in R007) leaves E004 unchanged. This path is frozen.
4. All 9 F-series cases fail with "Can Thickness is -ve", not with E004. This is a separate, distinct runtime failure from E004, confirmed across R008-F01–F09 with no exception.
5. H/T series runtime results: H01–H08 (single-polarity surplus only) all PASS; H09 (both surplus = 0.00mm) FAIL; H10 (both = 0.10mm) FAIL; H11 (both = 0.70mm) PASS; T02 (both = 0.00mm) FAIL; T03 (both = 0.10mm) FAIL; T04 (both = 0.70mm) PASS. These are the raw runtime observations on which H007 rests.
6. T01 passes with pos surplus = +0.89mm, neg surplus = −0.11mm. This demonstrates tolerance to a small negative surplus on one polarity when the other is sufficiently positive.
7. T09 (pos surplus = −4.11mm, neg = −5.11mm) fails. This is fully consistent with H007 and requires no separate mechanism.
8. STEP B-Rep measurements from T01–T08 show +Ve Tab Stem top-Y saturates at T06 (both surplus = 2.00mm): T06 = T07 = T08 = 66.275mm. This is a measured CAD fact from untessellated STEP solids, not a visual estimate.
9. m_dJellyrollThickness_mm drives realized JR diameter in STAR's CreateFromTbm. Confirmed from August 2026 isolated-variable matrix (17.0, 17.3, 17.6mm inputs → 17.009, 17.303, 17.562mm realized outputs; 18.2mm failed against 18mm can). Discretization deviation below 0.25mm across tested range.
10. A requested JR diameter exceeding Can diameter causes a fatal geometry conflict (established in August 2026 characterization and consistent with F-series failure pattern).

---

## Canonical supported hypotheses

**H007 — Tab-electrode surplus controls E004 (SUPPORTED / HIGH)**
Observational form: Near-zero or negative tab-electrode surpluses on both polarities are strongly associated with E004 failure. Sufficient combined surplus on both polarities is strongly associated with clean import. Empirical bracket from H/T series: both surpluses ≤ 0.10mm → FAIL; both ≥ 0.70mm → PASS; Delta_avg ≥ +0.39mm (T01 asymmetric case) → PASS. Three separate claims: (a) SUPPORTED: root construction depends jointly on both surplus quantities; (b) SUPPORTED: the two polarities are coupled; (c) NOT PROVEN: STAR directly equates root extrusion to any specific algebraic function of the individual deltas.

**H008a — F-series radial blocker is a separate failure from E004 (CONFIRMED)**
All 9 F-series cases fail with "Can Thickness is -ve," not E004. Confirmed across R008-F01–F09.

**H008b — F-series radial failure caused by m_dRepCanXDim not updated from D00 baseline (SUPPORTED)**
F-series DELTAS.txt has no m_dRepCanXDim change → F-series inherits D00's m_dRepCanXDim = 18mm. Under the August 2026 mapping (m_dRepCanXDim → Can OD), this gives Can OD ≈ 18mm. F-series sets m_dJellyrollThickness_mm = 20.6274mm → JR OD ≈ 20.6274mm >> Can OD → fatal. Awaits RAD-B confirmation.

**H008c — Electrode widths contribute to wound JR OD (OPEN)**
Not ruled in or out by any runtime or STEP evidence.

**H009 — Tab Stem STEP geometry saturates at ~2mm surplus input (SUPPORTED)**
From measured B-Rep bounding boxes on untessellated STEP solids. Generated root extent ≠ input Delta value (T01: input surplus = +0.89mm, Tab Stem top-Y = 65.557mm, electrode = 64.11mm, generated extent above electrode = 1.447mm ≠ 0.89mm input).

**Radial field mapping (SUPPORTED / HIGH — not CONFIRMED):**
- m_dJellyrollThickness_mm → JR OD: strongest support (August isolated tests, monotonic, < 0.25mm deviation); consistent with D00 REPORT (m_dRepJellyrollDiameter = 17.881mm ≈ 17.9mm input).
- m_dRepCanXDim → Can OD: August characterization "apparently drove can OD" from that matrix; consistent with D00 REPORT value (18mm for ~18mm can); Level-C documented as consumed by STAR.
- m_dintDiameter → Can ID: inferred from naming and R005 "exact-contact-final" design intent only; not tested in August matrix; OPEN pending RAD-A.
- m_dextDiameter → package outer form factor (not Can OD): consistent with D00 having m_dextDiameter = 21mm while m_dRepCanXDim = 18mm.

**H004-3 — Physical JR OD = Can ID causes E004 (OPEN)**
R005 never generated geometry. Under the revised mapping, R005 intended JR OD = Can ID = 20.6274mm but this state was never reached. The original refutation holds for "equal values in m_dintDiameter and m_dJellyrollThickness_mm cause E004." Whether the physical generated contact state would contribute to E004 remains open; testable only after radial geometry is correct (RAD-D2).

---

## Radial experiment specification

### T06 confirmed baseline values

| Field | Block | Value | Notes |
|---|---|---|---|
| Package m_dextDiameter | pcd | 21mm | Unchanged from D00 |
| Package m_dintDiameter | pcd | 20.9mm | Unchanged from D00 |
| m_dJellyrollThickness_mm | builder | 17.9mm | Unchanged from D00 |
| m_dRepCanXDim | REPORT | 18mm | Read directly from T06 file |
| m_dRepCanYDim | REPORT | 18mm | Read directly from T06 file |
| +Electrode m_dWidth | pcd | 64.11mm | T-series axial stack |
| -Electrode m_dWidth | pcd | 65.11mm | T-series axial stack |
| +Electrode Tab m_dLength_mm | pcd | 66.11mm | Surplus = +2.00mm (saturation plateau) |
| -Electrode Tab m_dLength_mm | pcd | 67.11mm | Surplus = +2.00mm (saturation plateau) |
| Package m_dintHeight | pcd | 65.11mm | Target axial stack height |

STEP measurements from T06: +Ve Tab Stem top-Y = 66.275mm (measured). Can OD, Can ID, JR OD: **not previously measured**. RAD-A/B/C will provide these for the first time.

---

### RAD-A: Isolate Package m_dintDiameter

| Parameter | Value |
|---|---|
| Baseline | T06 (all fields above) |
| Field changed | Package m_dintDiameter (pcd block) |
| Old value | 20.9mm |
| New value | 20.5mm |
| Unchanged radial fields | m_dextDiameter = 21mm; m_dJellyrollThickness_mm = 17.9mm; m_dRepCanXDim = 18mm; m_dRepCanYDim = 18mm |
| Measurement required | STEP export; measure Can OD, Can ID, JR OD from B-Rep bounding boxes on Jellyroll and Can solids |
| Hypothesis discriminated | Whether m_dintDiameter → Can ID. If Can ID changes proportionally with m_dintDiameter, the mapping is confirmed. If Can ID is unchanged, m_dintDiameter has no observable role in this geometry class and another field controls Can ID. |

---

### RAD-B: Isolate m_dRepCanXDim / m_dRepCanYDim

| Parameter | Value |
|---|---|
| Baseline | T06 |
| Field(s) changed | m_dRepCanXDim and m_dRepCanYDim together (one logical parameter: circular cross-section requires X = Y = diameter; changing one without the other asserts an elliptical can, which is physically incoherent for a cylindrical cell) |
| Old value | 18mm / 18mm |
| New value | 19mm / 19mm |
| Unchanged radial fields | m_dextDiameter = 21mm; m_dintDiameter = 20.9mm; m_dJellyrollThickness_mm = 17.9mm |
| Measurement required | STEP export; measure Can OD; confirm JR OD unchanged at ≈17.9mm |
| Hypothesis discriminated | Whether m_dRepCanXDim/YDim → Can OD as the August 2026 characterization supported. Pass: Can OD ≈ 19mm, JR OD ≈ 17.9mm. Null result (no Can OD change) is also informative: means STAR regenerates the REPORT block at import and m_dextDiameter or m_dintDiameter is the operative Can OD control. |

---

### RAD-C: Isolate m_dJellyrollThickness_mm

| Parameter | Value |
|---|---|
| Baseline | T06 |
| Field changed | m_dJellyrollThickness_mm (Detailed Builder) |
| Old value | 17.9mm |
| New value | 17.5mm (decrease; safely below Can OD ≈ 18mm, avoids triggering radial blocker) |
| Unchanged radial fields | m_dextDiameter = 21mm; m_dintDiameter = 20.9mm; m_dRepCanXDim = 18mm; m_dRepCanYDim = 18mm |
| Measurement required | STEP export; measure JR OD; confirm Can OD unchanged |
| Hypothesis discriminated | Whether m_dJellyrollThickness_mm → JR OD extends to the T06-baseline geometry class. August characterization confirmed this on a different cell matrix; RAD-C verifies the mapping holds before production RAD-D depends on it. |

---

### RAD-D1 and RAD-D2 (conditional on RAD-A/B/C results)

Field values to be filled in after RAD-A/B/C establish the actual mapping. Structure:

| | RAD-D1 | RAD-D2 |
|---|---|---|
| Purpose | Production target with small positive JR/Can clearance | Production target with exact JR OD = Can ID contact |
| Goal Can OD | 21.09mm | 21.09mm |
| Goal Can ID | 20.6274mm | 20.6274mm |
| Goal JR OD | ~20.50mm (~0.06mm radial clearance from Can ID) | 20.6274mm (= Can ID, exact contact) |
| Surplus | ≥ +2.00mm both polarities (T06-proven) | ≥ +2.00mm both polarities |
| Measurement required | STEP: Can OD, Can ID, JR OD; confirm no radial blocker; confirm E004 absent | STEP: same; check whether exact contact creates any construction failure |
| Hypothesis discriminated | Whether combined production geometry (corrected radial + valid surplus) imports and generates correctly | Whether exact JR OD = Can ID specifically causes failure (H004-3 physical state) |
| Sequencing | Run first, after RAD-A/B/C | Run only if RAD-D1 passes |

**Failure-mode logic:**
- RAD-D1 fails despite correct radial mapping and valid surplus → triggers H011 (C00–C17 Builder localization).
- RAD-D1 passes, RAD-D2 fails → H004-3 physical contact is relevant to production path; must be resolved before NE06 (production qualification).
- RAD-D2 passes → proceed to NE06 (full production TBM including project Builder/PCD + STEP for JR/Can/Cap contact topology verification).
