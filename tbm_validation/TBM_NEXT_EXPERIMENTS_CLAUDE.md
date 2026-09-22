# TBM Next Experiments — Ranked by Information Value
**Date:** 2026-09-22
**Principle:** Smallest experiment that distinguishes competing open hypotheses.

---

## NE01 — Close R006 (H004-5: feed/tail fix for production TBM)
**Priority:** IMMEDIATE — result is already built and pending
**Hypotheses tested:** H004-5
**Frozen baseline:** hp2170NCA-RCR-distributed-exact-contact-final.tbm (SHA 2c89d2d9)
**Perturbation:** m_dSepFeedLength_mm 0→10; m_dSepTailLength_mm 0→85 (already sent to Robert 2026-09-10)
**Prediction under H004-5 true:** PASS (E004 clears)
**Prediction under H004-5 false:** FAIL E004
**Falsifier:** Fail result → H004-5 demoted to LOW for E004; H007 remains primary
**Pass result action:** Verify feed/tail fix is compatible with production geometry; proceed to F-series with H008 fix
**Required Robert output:** import result (PASS or E004 error text)
**Why high value:** No new TBM needed; result already waiting. Closes the only remaining E004 fix candidate for the production TBM that does not require changing tab lengths.

---

## NE02 — H007 threshold midpoint (combined surplus ~0.35mm in target axial stack)
**Priority:** HIGH — narrows the minimum viable tab-length fix
**Hypotheses tested:** H007 threshold bounds
**Frozen baseline:** D00 + target axial stack geometry (from T-series baseline)
**Perturbation:** Both tab lengths set so both surpluses = +0.35mm (pos tab = 64.46mm; neg tab = 65.46mm)
**Prediction under threshold < 0.35mm:** PASS
**Prediction under threshold > 0.35mm:** FAIL E004
**Falsifier:** PASS → threshold ≤ 0.35mm; FAIL → threshold between 0.35mm and 0.70mm
**Required Robert output:** import result only; no STEP required
**Why high value:** Bisects the [0.10, 0.70mm] interval; saves one full run compared to a linear sweep.

---

## NE03 — Asymmetric surplus test (pos=+0.70mm, neg=0mm in target axial stack)
**Priority:** HIGH — distinguishes whether max-surplus or combined-surplus drives the threshold
**Hypotheses tested:** H007 (which polarity matters?)
**Perturbation:** pos tab = electrode_pos_width + 0.70mm; neg tab = electrode_neg_width exactly
**Prediction if max(Δ+, Δ-) rules:** PASS (max = 0.70mm)
**Prediction if Δavg rules with threshold ~0.35mm:** PASS (avg = 0.35mm)
**Prediction if strict per-polarity threshold:** FAIL (neg = 0mm)
**Falsifier:** FAIL → strict per-polarity rule, neg cannot be zero; PASS → max or combined threshold applies
**Required Robert output:** import result only
**Why high value:** Directly tests whether the single-polarity-zero tolerance (observed in H01/H05) carries over to the target axial stack.

---

## NE04 — H008 radial blocker diagnosis: enlarge Package OD for F-series
**Priority:** HIGH — prerequisite for production TBM qualification
**Hypotheses tested:** H008 (what does STAR compute for wound JR OD given 2170 electrode widths?)
**Approach:** Start from D00 (working control geometry). Step 1: replace only Package m_dintDiameter and m_dJellyrollThickness_mm with 20.6274mm (don't change electrode widths). If this alone causes "Can Thickness -ve," then the issue is the builder m_dJellyrollThickness_mm interpretation, not the electrode widths. Step 2: restore Package dimensions to D00 values but use 2170 electrode widths (64.11/65.11mm). If this fails, STAR's wound JR OD computation depends on electrode widths.
**Required Robert output:** import result for each step; no STEP required
**Why high value:** Isolates whether the radial conflict is from the Package dimension change or the electrode width change. Dictates whether the fix is in Package geometry or in m_dJellyrollThickness_mm.

---

## NE05 — C12 + C13 Detailed Builder transplant (E004 localization in production TBM)
**Priority:** MEDIUM — valuable if NE01 (R006) fails and H007 fix requires new TBM
**Hypotheses tested:** H011 (which TBM section drives E004?)
**Cases to run:** C00 (environment control), C12 (Siemens Detailed Builder inside project PCD), C13 (Siemens PCD + Builder inside project context)
**Interpretation matrix:** See CAMPAIGN_MATRIX.md for the already-written paired interpretation
**Required Robert output:** PASS/FAIL for C00, C12, C13
**Why medium priority:** The H/T surplus sweep already identified the root mechanism (H007). C12/C13 would confirm which Builder fields embody the surplus constraint, but this may not be needed if NE01 resolves the production TBM via feed/tail or NE02/NE03 confirm the tab-length fix.

---

## NE06 — Production TBM with H007 fix + H008 fix combined
**Priority:** HIGH but sequentially dependent on NE04 resolution
**Hypotheses tested:** Production import viability
**Approach:** Once H008 is understood (NE04), build F04-equivalent with corrected radial dimensions AND tab lengths set to minimum passing surplus (from NE01/NE02/NE03). Request STEP export if import passes.
**Required Robert output:** Import result. If PASS: STEP for JellyRoll/Can/Cap contact verification.
**Why high value:** This is the production qualification test. All other NE experiments are prerequisites.

---

## NE07 — I05: Import with Electrode Root object omitted (one-object omission)
**Priority:** LOW–MEDIUM
**Hypotheses tested:** Whether E004 is directly tied to one importable object
**Approach:** Run a passing TBM (e.g., T06 or H11) through "Create from TBM" with all objects selected EXCEPT the object associated with Electrode Root 1. Determine if omitting that object clears construction of the failing feature.
**Prerequisite:** Robert must provide the exact object-list names from the Import Battery Options dialog before this test can be specified precisely.
**Required Robert output:** Object list screenshot, then import result with that object excluded.
**Why lower priority:** The H/T series already confirmed the root-surplus mechanism; object-level omission is diagnostic detail unless other experiments stall.

---

## Experiment priority order

| Rank | Experiment | Action required |
|---|---|---|
| 1 | NE01 | Ask Robert for R006 result immediately |
| 2 | NE02 | Build and send T-series midpoint case (~0.35mm surplus) |
| 3 | NE04 | Build two isolated-variable F-style tests (package-only change vs electrode-width-only change) |
| 4 | NE03 | Build asymmetric-surplus T-case (pos=+0.70mm, neg=0mm) |
| 5 | NE06 | After NE04 resolved: build production TBM with both fixes |
| 6 | NE05 | C12/C13 campaign if NE01 fails and production path is unclear |
| 7 | NE07 | Object-omission test; requires object-list from Robert first |

---

## What NOT to test next

These have been directly ruled out; further experiments have negative expected information value:

- Another S3 variant
- Another JR diameter away from 20.6274mm target
- Another tab-on/off permutation
- Another m_bOnly1D variant
- Package m_dintHeight isolated changes (ROOT_A/ROOT_B pattern)
- Separator feed/tail variants IN THE F-SERIES (blocked by H008; test in production TBM via NE01 instead)
