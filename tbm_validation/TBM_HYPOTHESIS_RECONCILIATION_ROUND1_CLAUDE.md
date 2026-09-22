# TBM Hypothesis Reconciliation — Round 1 Response
**Date:** 2026-09-22
**Status:** Independent reconstruction reconciled against second-reviewer challenge.
**Files updated by this round:** This document only. Canonical ledger (TBM_HYPOTHESIS_LEDGER_CLAUDE.md) not yet revised.

---

## Reconciliation table

| Issue | Position | Strongest evidence | Revised hypothesis/status | Campaign consequence |
|---|---|---|---|---|
| **1. H008 causal explanation** | **AGREE** | F-series DELTAS.txt has no `m_dRepCanXDim` change → F-series inherited D00 Can ID (~18mm). With m_dJellyrollThickness_mm = 20.6274mm (JR OD >> 18mm), STAR clamps Can ID = JR OD = 20.6274mm; if m_dintDiameter → Can OD = 20.6274mm then Can thickness = 0 → fatal. R008-F01–F09 all fail this way. My original "electrode widths inflate wound JR OD" mechanism was an unsupported inference. | **Split as proposed:** H008a CONFIRMED (separate radial blocker). H008b SUPPORTED (wrong field assignment — m_dRepCanXDim not updated for F-series). H008c OPEN (electrode-width winding-diameter contribution not independently tested). | Drop NE04's electrode-width isolation. Replace with RAD-A/B/C/D. |
| **2. H004-3 exact-contact refutation scope** | **AGREE** | In R005: m_dJellyrollThickness_mm = 20.6274mm (JR OD), but project TBM has m_dRepCanXDim = 21.09mm (Can ID per new mapping). Physical state was JR OD 20.6274 < Can ID 21.09 — not zero clearance. R005 only proves "equal numerical values in m_dintDiameter and m_dJellyrollThickness_mm does not cause E004." Physical JR OD = Can ID was never tested. | **Revise H004-3:** Refutation holds only for "equal values in those two TBM fields cause E004." Physical generated Can ID == generated JR OD remains **OPEN**. | Physical zero-clearance contact tested implicitly in RAD-D. |
| **3. H007 wording — direct extrusion equality** | **AGREE** | D00 REPORT block correlation is from a stale REPORT field, not a runtime measurement. STEP Tab Stem top-Y: T01=65.557mm; pos surplus = +0.89mm; electrode = 64.11mm; generated extent exceeds electrode by 1.447mm ≠ 0.89mm input. H01/H05 show single-polarity coupling. | **Revise H007 to three claims:** (a) SUPPORTED: root construction depends on surplus quantities jointly. (b) SUPPORTED: positive and negative sides are coupled. (c) NOT PROVEN: STAR equates each root extrusion to its individual Delta. | Wording only; no experiment change. |
| **4. Threshold wording** | **AGREE** | Symmetric: both ≤ 0.10mm → FAIL; both ≥ 0.70mm → PASS. T01 asymmetric: Delta_avg = +0.39mm → PASS. Three distinct claims requiring separation. | **(1) Symmetric per-side bracket:** [0.10 FAIL, 0.70 PASS]. **(2) Empirical combined-metric separator:** Delta_avg ≤ 0.10 → FAIL; Delta_avg ≥ 0.39 → PASS (T01 tightens lower bound). **(3) Actual Siemens formula:** UNKNOWN. | No experiment change. |
| **5. H010 T09 anomaly** | **AGREE — SUPERSEDED** | T09: Delta_avg = (−4.11 + −5.11)/2 = −4.61mm. Unambiguously fails under Delta_avg ≥ 0.39 pass criterion. No separate mechanism required. Session log called it "anomalous" before the threshold was understood. | **H010: SUPERSEDED by H007.** | Remove from open question list. |
| **6. H011 C00-C17 relevance** | **AGREE — DEFER** | H/T series established root surplus as the operative variable. C12/C13 unique remaining information: whether a Builder field other than surplus is also blocking, discovered only if production TBM fails after both fixes applied. That is contingency, not primary path. | **H011: DEFERRED** — run only if NE06 fails for an unexplained reason after both root-surplus and radial fixes are applied. | Remove from primary campaign queue. |
| **7. R006 information value** | **PARTLY AGREE** | HP/HE references show feed/tail=0/0 is compatible with clean construction. H007 explains E004 better than H004-5. R006 result costs nothing to retrieve but would only formally close H004-5 without materially changing the production path. | **R006 should NOT control the campaign.** Retrieve result opportunistically. NE04/RAD addresses the more important open blocker. | Downgrade R006 from "IMMEDIATE" to "retrieve passively." |
| **8. NE02 exact threshold — engineering value** | **AGREE** | T06 (both surplus = +2mm) is on the STEP saturation plateau (T06=T07=T08 top-Y identical). For production, choosing ≥2mm surplus is robust. Exact threshold location (0.25 vs 0.35 vs 0.45mm) has low value when radial field identification is the critical blocker. | **Remove NE02 from priority queue.** Freeze T06 as root-surplus baseline. | Free Robert run slot for RAD campaign. |
| **9. NE03 max vs average discrimination** | **AGREE — REMOVE** | NE03 proposed pos=+0.70mm, neg=0mm: gives max=0.70, avg=0.35, sum=0.70. Both max≥0.70 and avg≥0.35 predict PASS, so NE03 cannot discriminate the two rules. The only claim it rejects — strict per-polarity positive threshold — is already rejected by H01/H05. | **Remove NE03.** | Free run slot. |
| **10. RAD-A/B/C/D vs NE04** | **AGREE — REPLACE** | My NE04 conflated radial field change with electrode-width change. RAD-A/B/C/D (one field at a time from T06 baseline with STEP per run) directly resolves the black-box mapping with minimal confounders, then RAD-D targets production values. | **Replace NE04 with RAD-A/B/C/D using T06 as baseline.** | Radial mapping confirmed before production attempt. |

---

## Evidence basis for H008 revision (key repository facts)

`CURRENT_TBM_FIELD_AUDIT.md` line 127: `m_dRepCanXDim = 21.09mm` in project TBM, marked "YES (Level-C, documented)" consumed by STAR.

`DELTAS.txt` (F-series): no `m_dRepCanXDim` change listed in any F-series delta → F-series inherited D00's value (~18mm, per STEP Can ID measurement).

Failure chain for F-series:
```
m_dJellyrollThickness_mm = 20.6274mm  →  JR OD ≈ 20.6274mm
Inherited m_dRepCanXDim  = ~18mm      →  Can ID ≈ 18mm
JR OD >> Can ID  →  STAR warning; sets Can ID = JR OD = 20.6274mm
m_dintDiameter   = 20.6274mm          →  Can OD ≈ 20.6274mm
Can thickness = (20.6274 - 20.6274)/2 ≈ 0  →  "Can Thickness is -ve"
```

The electrode-width explanation (H008c) is not directly supported by any runtime experiment. It remains OPEN until RAD campaign provides STEP evidence for the production TBM geometry.

---

## Evidence basis for H004-3 revision

R005 physical state (under new radial mapping):
```
m_dJellyrollThickness_mm = 20.6274mm  →  JR OD ≈ 20.6274mm
m_dRepCanXDim (project TBM) = 21.09mm →  Can ID ≈ 21.09mm
Physical JR-to-Can gap ≈ (21.09 - 20.6274)/2 = 0.23mm  (not zero-clearance)
```
R005 only refutes: "equal numerical values in m_dintDiameter and m_dJellyrollThickness_mm cause E004." The physical zero-clearance hypothesis (generated JR OD = generated Can ID → E004) was never reached in any runtime event.

---

## Revised top 5 known facts

1. E004 is caused by insufficient combined tab-electrode surplus. Symmetric bracket: both ≤ 0.10mm fails; both ≥ 0.70mm passes. T01 (Delta_avg = +0.39mm) passes, tightening the empirical lower bound.
2. Tab Stem STEP geometry saturates at ~2mm surplus input: T06=T07=T08 top-Y = 66.275mm. Generated root extent ≠ input Delta.
3. F-series radial failure is caused by inheriting D00's m_dRepCanXDim (~18mm) while m_dJellyrollThickness_mm was set to 20.6274mm (JR OD >> Can ID). Not caused by electrode widths (H008c remains OPEN).
4. Radial field mapping from D00-based STEP: Package m_dintDiameter → Can OD; m_dRepCanXDim/YDim → Can ID; m_dJellyrollThickness_mm → JR OD. This mapping was not understood at the time of R005; RAD campaign must confirm it holds for the production TBM path.
5. R005 never achieved physical JR OD = Can ID. Project TBM m_dRepCanXDim = 21.09mm → Can ID ≈ 21.09mm in R005. H004-3 refutation covers only equal field values, not the physical zero-clearance state.

---

## Revised top 5 open questions

1. Does the radial field mapping (m_dintDiameter → Can OD; m_dRepCanXDim → Can ID; m_dJellyrollThickness_mm → JR OD) hold for the production TBM geometry, or only for D00-based cells? RAD-A/B/C answer this.
2. What are the correct m_dRepCanXDim/YDim and m_dJellyrollThickness_mm values to achieve physical Can ID = JR OD = 20.6274mm in the production 2170 cell?
3. Does R006 (SepFeed/Tail fix in production TBM) clear E004? Formally unresolved but low campaign priority.
4. Does the combined production TBM (≥2mm root surplus + corrected radial fields + project Builder/PCD) import successfully and produce the desired JR/Can/Cap contact topology?
5. The exact STAR formula for root extrusion distance (max, avg, sum of surplus quantities) remains unknown. Not blocking production at 2mm surplus; relevant only if a tighter margin becomes necessary.

---

## Revised next-experiment priority

| Rank | Experiment | Action |
|---|---|---|
| 1 | RAD-A | From T06 baseline: vary Package m_dintDiameter only; STEP export; measure Can OD, Can ID, JR OD |
| 2 | RAD-B | From T06 baseline: vary m_dRepCanXDim/YDim only; STEP export; identify Can ID mapping |
| 3 | RAD-C | From T06 baseline: vary m_dJellyrollThickness_mm only; STEP export; identify JR OD mapping |
| 4 | RAD-D | Combine RAD-A/B/C findings: target Can OD = physical can OD; Can ID = 20.6274mm; JR OD ≤ 20.6274mm; import + STEP |
| 5 | NE06 | After RAD-D passes: production TBM (F08-equivalent + project Builder + ≥2mm surplus + RAD-D radial fields); STEP for JR/Can/Cap contact verification |

Retrieve R006 result passively. Do not run C00-C17 unless NE06 fails for an unexplained reason.
