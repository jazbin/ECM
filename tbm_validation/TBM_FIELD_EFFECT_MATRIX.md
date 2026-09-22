# TBM Field-Effect Matrix — Authoritative
**Last updated:** 2026-09-22
**Supersedes:** TBM_FIELD_EFFECT_MATRIX_CLAUDE.md (retained as audit evidence)
**Purpose:** Maps TBM input fields → import behavior → generated geometry observable.

Evidence levels:
- CONFIRMED ISOLATED: direct one-variable STEP or runtime test with measurement
- SUPPORTED CORRELATION: consistent with available evidence but not isolated
- OPEN: no direct test performed
- REFUTED: tested; no effect on stated observable
- MASKED: downstream failure prevented reaching observable

---

## Observable 1: E004 — "Electrode Root 1: Extrusion distance can not be 0"

| TBM field | Tested range | Effect on E004 | Evidence level | Event(s) |
|---|---|---|---|---|
| Mandrel thickness | 0 → positive | Upstream E003 gate; resolves E003 first, enabling E004 to appear | CONFIRMED ISOLATED | R001→R002 |
| Tab enable flags (+/-) | enabled ↔ disabled | NO EFFECT | CONFIRMED ISOLATED | R002–R004 |
| Tab vertical orientation | standard ↔ same-face | NO EFFECT | CONFIRMED ISOLATED | R003–R004 |
| m_bOnly1D (SIMMOD) | nonzero → 0 | NO EFFECT on E004 | CONFIRMED ISOLATED | R004 |
| Transport number fields | fixed to 0 | NO EFFECT on E004 | CONFIRMED ISOLATED | R005 |
| +Electrode m_dS3 | 0 → 5mm | NO EFFECT | CONFIRMED ISOLATED | R005 |
| m_dJellyrollThickness_mm (builder) | varied in R005 | NO EFFECT on E004 | CONFIRMED ISOLATED | R005 |
| Package m_dintHeight | +0.10, +0.70mm change | NO EFFECT | CONFIRMED ISOLATED | R007 ROOT_A/B |
| +Electrode Tab m_dLength_mm (pos surplus, working cell) | 0.00 to +2.00mm above electrode | NO EFFECT when neg surplus ≥ +8mm | CONFIRMED ISOLATED | R008-H01–H04 |
| -Electrode Tab m_dLength_mm (neg surplus, working cell) | 0.00 to +2.00mm above electrode | NO EFFECT when pos surplus ≥ +9mm | CONFIRMED ISOLATED | R008-H05–H08 |
| Both tab lengths (combined surplus, working cell) | 0.00mm → FAIL; 0.10mm → FAIL; 0.70mm → PASS; 2.00mm → PASS | STRONG EFFECT: threshold between 0.10mm and 0.70mm per polarity | CONFIRMED ISOLATED | R008-H09–H12 |
| Both tab lengths (combined surplus, target axial stack) | 0.00mm → FAIL; 0.10mm → FAIL; 0.70mm → PASS; 1.00mm → PASS; 2.00mm → PASS; 5.00mm → PASS; +9/+8mm → PASS | STRONG EFFECT: same threshold confirmed in different axial geometry | CONFIRMED ISOLATED | R008-T02–T08 |
| Both tab lengths (asymmetric: pos=+0.89mm, neg=−0.11mm, target axial) | pos positive, neg slightly negative | PASS — coupled rule, not per-polarity positive floor | CONFIRMED ISOLATED | R008-T01 |
| Both tab lengths (large negative: pos=−4.11mm, neg=−5.11mm, target axial) | large negative both | FAIL — fully consistent with H007 threshold | CONFIRMED ISOLATED | R008-T09 |
| m_dSepFeedLength_mm / m_dSepTailLength_mm | 0/0 → 10/85, in production TBM | UNKNOWN (R006 result not received) | BLOCKED | R006 (pending) |
| m_dSepFeedLength_mm change in F-series (F04) | 10 vs. working-default | MASKED — F04 fails on radial blocker before E004 stage | MASKED | R008-F04 |

**Key observational summary for E004:**
- Threshold bracket (per-polarity, symmetric cases): both ≤ 0.10mm → FAIL; both ≥ 0.70mm → PASS
- Asymmetric tolerance: Delta_avg ≥ +0.39mm (T01) → PASS; both large-negative → FAIL
- The exact Siemens formula is UNKNOWN — cannot distinguish Delta_avg, Delta_max, Delta_sum from available data
- Individual per-polarity positive surplus is NOT required; the rule is coupled/joint

---

## Observable 2: Radial blocker — "Can Thickness is -ve"

| TBM field | Tested range | Effect | Evidence level | Event(s) |
|---|---|---|---|---|
| m_dRepCanXDim (REPORT) | ~18mm (D00 baseline, unchanged in F-series) | When unchanged at 18mm while m_dJellyrollThickness_mm = 20.6274mm: Can OD ≈ 18mm < JR OD ≈ 20.6274mm → fatal | SUPPORTED CORRELATION | R008-F01–F09; August 2026 characterization |
| m_dJellyrollThickness_mm (builder) | 17.9 → 20.6274mm (in F-series) | JR OD ≈ 20.6274mm >> Can OD ≈ 18mm → fatal | CONFIRMED ISOLATED (JR OD control) + SUPPORTED (F-series failure) | GEOMETRY_CHARACTERIZATION_20260831; R008-F01–F09 |
| Electrode widths (+/-) | 56/57mm (working) → 64.11/65.11mm (2170, F-series) | Potential independent contribution to wound JR OD | OPEN — not isolated | F-series confound |
| Package m_dintDiameter | 20.9 → 20.6274mm (F-series) | Possible role in Can ID determination; confounded with m_dJellyrollThickness_mm in F-series | OPEN | F-series confound |
| Package m_dextDiameter | 21 → 21.09mm (F-series) | Package outer form factor — role in Can geometry requires RAD-A test | OPEN | — |
| SepFeedLength (F04: 0→10) | different from other F-series | NO EFFECT on radial blocker — F04 fails identically | CONFIRMED | R008-F04 |
| Synchronized volumes (F09) | applied | NO EFFECT on radial blocker — F09 fails identically | CONFIRMED | R008-F09 |

---

## Observable 3: Radial geometry — generated Can OD, Can ID, JR OD from STEP

These observables have NOT been directly measured from any T-series STEP export. The values below are the supported mapping; RAD-A/B/C will establish them by isolated measurement.

| TBM field | Inferred role | Evidence level | RAD experiment to confirm |
|---|---|---|---|
| m_dJellyrollThickness_mm (Detailed Builder) | JR OD | CONFIRMED ISOLATED (August 2026, multiple isolated points) | RAD-C (verify on T06-baseline geometry) |
| m_dRepCanXDim / m_dRepCanYDim (REPORT, both together) | Can OD | SUPPORTED (August 2026 "apparently drove Can OD") | RAD-B |
| m_dintDiameter (pcd Package) | Can ID — OPEN | OPEN — not tested in August matrix | RAD-A |
| m_dextDiameter (pcd Package) | Package outer form factor — role in Can geometry unclear | OPEN | Implicit in RAD-A/B results |
| m_dRepJellyrollDiameter (REPORT) | NO OBSERVED EFFECT on geometry — Builder wins in conflicts | CONFIRMED from August characterization | — |

**Note on REPORT block fields:** The REPORT block is pre-computed by a prior BDS session. STAR may regenerate or overwrite it at import. m_dRepCanXDim is Level-C documented as consumed; whether STAR overwrites it with a recomputed value or uses the stored value is itself tested by RAD-B (null result = overwritten; proportional change = consumed as stored).

---

## Observable 4: Generated +Ve Tab Stem top-Y (STEP B-Rep bounding box)

| TBM input | Range tested | Measured top-Y | Evidence level |
|---|---|---|---|
| Both surpluses = +0.89/−0.11mm (T01) | asymmetric, just above pass threshold | 65.557mm | CONFIRMED ISOLATED (B-Rep) |
| Both surpluses = +0.70mm (T04) | minimum symmetric pass | 65.812mm | CONFIRMED ISOLATED (B-Rep) |
| Both surpluses = +1.00mm (T05) | intermediate | 66.112mm | CONFIRMED ISOLATED (B-Rep) |
| Both surpluses = +2.00mm (T06) | saturation onset | 66.275mm | CONFIRMED ISOLATED (B-Rep) |
| Both surpluses = +5.00mm (T07) | above saturation | 66.275mm | CONFIRMED ISOLATED (B-Rep) |
| Both surpluses = +9/+8mm (T08) | well above saturation | 66.275mm | CONFIRMED ISOLATED (B-Rep) |

Note: The generated root extent above the electrode (66.275 − 64.11 = 2.165mm at T06) does not equal the input surplus (+2.00mm). The conversion is not 1:1.

---

## Fields not yet tested / pending

| TBM field | Reason not tested | Hypothesis | Experiment |
|---|---|---|---|
| m_dSepFeedLength_mm / m_dSepTailLength_mm | R006 pending | H004-5 | R006 retrieval |
| C00–C17 Builder/PCD transplants | Campaign not run | H011 | DEFERRED |
| m_dintDiameter (isolated) | RAD-A not run | RMAP-3 (Can ID) | RAD-A |
| m_dRepCanXDim/YDim (isolated, T06-baseline) | RAD-B not run | RMAP-2 (Can OD) | RAD-B |
| m_dJellyrollThickness_mm (isolated, T06-baseline) | RAD-C not run | RMAP-1 (JR OD extension) | RAD-C |
| Production combined radial + T06 surplus | RAD-D not run | Full import viability | RAD-D1, RAD-D2 |
