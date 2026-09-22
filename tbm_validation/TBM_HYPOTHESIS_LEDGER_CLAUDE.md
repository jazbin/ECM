# TBM Hypothesis Ledger — Independent Reconstruction
**Date:** 2026-09-22
**Method:** Derived from Robert runtime events R001–R008 and STEP geometry evidence.
**Evidence priority:** Robert runtime results > STEP geometry > TBM field values > documentation analysis.

---

## H001 — E003: Mandrel thickness must be positive
**Status:** CONFIRMED | **Confidence:** HIGH

| | |
|---|---|
| Statement | STAR CreateFromTbm fatally rejects a TBM whose mandrel thickness field evaluates to zero or negative. |
| Evidence for | R001: all four variants fail with "Mandrel thickness must be positive" before any other error. R002: after mandrel fix, E003 absent in all subsequent runs. |
| Evidence against | None. |
| Confounders | None. |
| What it does not prove | Which exact TBM field(s) controlled the mandrel thickness in R001. Whether the fix also changed other fields. |
| Production relevance | LOW — resolved. Current TBMs have positive mandrel thickness. Do not reduce mandrel thickness speculatively. |

---

## H002 — Tab enable flags and vertical orientation cause E004
**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | Enabling/disabling tabs or switching top/bottom tab orientation resolves E004. |
| Evidence for | None post-runtime. |
| Evidence against | R002–R004: E004 survives across all four tab-on/off and standard/same-face permutations. |
| What it does not prove | Does not rule out tabs being involved in the construction path — only rules out these configuration flags as controls. |
| Production relevance | LOW — do not queue more tab-orientation variants before addressing root cause. |

---

## H003 — m_bOnly1D flag causes E004
**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | Incorrect m_bOnly1D values in SIMMOD blocks block distributed 3D construction and produce E004. |
| Evidence for | Pre-runtime concern based on field mismatch vs Siemens references. |
| Evidence against | R004: m_bOnly1D warning cleared; E004 unchanged. |
| What it does not prove | Does not rule out m_bOnly1D being required for a valid distributed solve; it is still required for model correctness, just not the E004 cause. |
| Production relevance | MEDIUM — m_bOnly1D cleanup should remain in the production TBM for model correctness; it simply does not fix E004. |

---

## H004-1 — +Electrode S3 = 0 causes E004
**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | A zero-valued +Electrode m_dS3 produces a degenerate tab/root geometry feature. |
| Evidence for | Pre-runtime: S3=0 anomalous vs Siemens references. DOE/BDS parameter diagram places S1–S5 as electrode layout spacings adjacent to tabs. |
| Evidence against | R005: +S3 changed 0→5 mm; E004 unchanged. |
| What it does not prove | S3 is still uncharacterized physically; changing it may affect auxiliary geometry. The refutation covers only E004 causality. |
| Production relevance | LOW — do not send more S3-only variants. Causal support for E004 is exhausted. |

---

## H004-2 — Transport number metadata causes E004
**Status:** REFUTED (causal claim) | **Confidence:** HIGH

| | |
|---|---|
| Statement | Incorrect transport number fields prevent import/construction. |
| Evidence against | R005: transport-number cleanup applied; E004 unchanged. |
| Production relevance | MEDIUM — transport number cleanup still required for model correctness, not for E004. |

---

## H004-3 — Exact radial JR/Can contact (JR OD = Can ID) causes E004
**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | Setting JR outer diameter equal to Package inner diameter causes a radial geometry failure that becomes E004. |
| Evidence for | Pre-runtime concern about zero-clearance CAD. |
| Evidence against | R005: JR OD set to exact can-ID contact (20.6274mm); E004 unchanged. Siemens STAR-install TBMs use exact JR/package-ID equality (LiIonSpiral.tbm: both = 17.9mm) and import cleanly. |
| What it does not prove | Does not address the DIFFERENT radial failure in F-series (H008). The F-series "Can Thickness is -ve" involves STAR computing a wound JR OD that exceeds the stated Package ID — a separate mechanism. |
| Production relevance | LOW for E004. HIGH for F-series (see H008). |

---

## H004-4 / H004-5 — Separator feed/tail = 0/0 causes E004
**Status:** BLOCKED | **Confidence:** LOW–MEDIUM

| | |
|---|---|
| Statement | m_dSepFeedLength_mm = 0 and/or m_dSepTailLength_mm = 0 produces a zero-length CAD feature triggering E004. |
| Evidence for | Pre-runtime: STAR-install TBMs commonly use feed=10/tail=85; project uses 0/0. |
| Evidence against | (a) Siemens HP18650 Detailed Builder uses 0/0 and generates clean 13-solid STEP. (b) HE18650 also uses 0/0. These are verified Siemens counterexamples. (c) F04 (full 2170, SepFeed=10/Tail=85) still fails — but on the radial blocker, not E004. (d) R006 (production TBM + feed/tail fix) result is pending. |
| Blocking failure | H004-5 cannot be tested in the F-series because all F-series fail earlier on the radial blocker (H008). R006 result has not been received. |
| Minimum discriminator | R006 result: production TBM + SepFeed/Tail=10/85 run by Robert. |
| Production relevance | MEDIUM — if R006 passes, feed/tail is the fix for the production TBM. If R006 fails, demote to LOW (but F04-series still blocked separately). |

---

## H004-6 — Zero package-to-negative-electrode axial clearance causes E004
**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | Package m_dintHeight = negative_electrode_width (0.00mm clearance) drives the electrode-root extrusion distance to zero. |
| Evidence for | Static geometry audit: project is the only TBM in the Siemens corpus with pkg-neg = 0.00mm. HE18650 has pkg-neg = +0.70mm; validationBattery has +3.00mm; HP18650 has +7.50mm. |
| Evidence against | R007: ROOT_A (pkg m_dintHeight +0.10mm, pkg-neg=+0.10mm) and ROOT_B (m_dintHeight +0.70mm, pkg-neg=+0.70mm) BOTH fail with identical E004. |
| What it does not prove | Does not prove package m_dintHeight is entirely irrelevant to root geometry; only proves it is not the primary causal variable for E004 within the tested range. |
| Production relevance | LOW for E004. The axial-layer margins are still important for physical geometry correctness (separate from import validity). |

---

## H007 — Root extrusion requires a minimum combined tab-electrode surplus
**Status:** SUPPORTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | STAR derives each electrode-root extrusion distance from tab_length − electrode_width. A single-polarity zero or small surplus is tolerated when the other polarity has a large surplus, but when both surpluses are near-zero or negative, E004 triggers. |
| Evidence for | R008 H/T series: H01 (pos=0, neg=+8) PASS; H05 (pos=+9, neg=0) PASS; H09 (both=0) FAIL; H10 (both=+0.10) FAIL; H11 (both=+0.70) PASS; T01 (pos=+0.89, neg=-0.11) PASS; T02 (both=0) FAIL; T03 (both=+0.10) FAIL; T04 (both=+0.70) PASS; T09 (pos=-4.11, neg=-5.11) FAIL. D00 REPORT block confirms: STAR stores root height = tab_length − electrode_width (+9mm/+8mm for working cell). |
| Evidence against | T01 passes despite neg surplus = -0.11mm; this weakens any strict per-polarity positive-surplus rule. |
| Confounders | H-series uses working-cell geometry (60mm pkg height, 56/57mm electrodes); T-series uses target axial stack (65.11mm pkg, 64.11/65.11mm electrodes). The threshold observation is consistent across both geometry contexts, supporting a per-TBM but not geometry-specific threshold. |
| Threshold bounds | Both-surplus threshold is between 0.10mm and 0.70mm (per polarity). T01 shows asymmetry is tolerable when the larger root covers for the smaller. |
| What it does not prove | (a) The exact STAR-internal formula (whether STAR sums, averages, or takes the max/min of the two surpluses). (b) Whether "Electrode Root 1" is always positive, always negative, or the first-constructed. (c) Whether the threshold is a CAD-kernel epsilon or a field-value check. |
| Alternative explanatory quantities | Δ+ (pos surplus), Δ- (neg surplus), Δavg = (Δ+ + Δ-)/2, Δsum = Δ+ + Δ-, Δmin = min(Δ+, Δ-), Δmax = max(Δ+, Δ-). Current data is consistent with Δavg or Δmax threshold between 0.10mm and 0.70mm. Cannot distinguish from available data. |
| Minimum discriminator | Test both-surplus at ~0.35mm (T-series midpoint: tabs at 64.46/65.46mm) to bound the threshold. Separately test pos=+0.70mm, neg=0mm (target axial stack) to determine if asymmetric surplus is sufficient. |
| Production relevance | HIGH — this hypothesis defines the tab-length fix required for the production TBM. Target: both tab lengths > electrode widths by at least 0.70mm (or the midpoint once confirmed). |

---

## H008 — F-series radial geometry blocker: STAR-computed JR OD exceeds package Can ID
**Status:** CONFIRMED (as separate blocker) | **Confidence:** HIGH

| | |
|---|---|
| Statement | When 2170 electrode widths are used in the full F-series geometry, STAR's internal winding computation produces a jellyroll outer diameter that exceeds the stated Package m_dintDiameter (Can inner diameter). STAR then sets Can ID = JR OD and computes Can thickness = (Package OD − new Can ID)/2, which goes negative, producing a fatal error. |
| Evidence for | R008: ALL nine F-series TBMs fail with "Jellyroll outer diameter is greater than Can inner diameter. Can inner diameter set to JR outer diameter." followed by "Can Thickness is -ve". F04 has SepFeed=10/Tail=85 and still fails → not a feed/tail issue. F09 has synchronized volumes and still fails. The H/T-series (smaller working-cell or target-axial-only geometry, not full radial change) do not exhibit this error. |
| Evidence against | None directly. The specific computation STAR uses for JR OD from wound electrode geometry is not publicly documented. |
| Confounders | The F-series simultaneously changes Package m_dintDiameter (20.9→20.6274) and m_dJellyrollThickness_mm (17.9→20.6274). The smaller Can ID could also trigger this. |
| What it does not prove | Whether the fix is in Package m_dextDiameter, m_dintDiameter, m_dJellyrollThickness_mm, or in the electrode widths themselves. Whether a larger package external diameter would accommodate the 2170 electrode set. |
| Minimum discriminator | Test F04 with Package m_dextDiameter enlarged to accommodate STAR's computed JR OD (requires knowing or guessing STAR's winding-geometry formula). Alternative: run T-series equivalent with full radial geometry but working-cell electrode widths (isolate radial change from electrode-width change). |
| Production relevance | CRITICAL — this blocker prevents any full-2170-geometry TBM from being tested. Resolving H008 is a prerequisite for the production TBM qualification campaign. |

---

## H009 — Tab Stem geometric saturation above ~2mm surplus
**Status:** SUPPORTED | **Confidence:** HIGH (from STEP measurements)

| | |
|---|---|
| Statement | The generated +Ve Tab Stem bounding-box top-Y reaches a maximum at approximately 2mm tab-electrode surplus input; larger inputs (5mm, +9/+8mm) produce identical STEP geometry. |
| Evidence for | STEP B-Rep measurement: T06 (2mm) top-Y = 66.275mm; T07 (5mm) = 66.275mm; T08 (+9/+8mm) = 66.275mm. Visual render confirms visually indistinguishable panels in fixed-scale comparison. T01→T04→T05→T06 show monotonic increase confirming the saturation is at T06 specifically. |
| Evidence against | None from STEP data. |
| What it does not prove | (a) The saturation is NOT related to the package cavity height (if a formula constrains root extent by package geometry). (b) Whether the STAR electrical/thermal mesh is also saturated. (c) Whether the negative root saturates at the same surplus value. |
| Production relevance | MEDIUM — any production tab length choice > electrode_width + ~2mm produces geometrically identical output. No value in choosing very large surpluses. The minimum sufficient surplus (for E004 clearance, between 0.10mm and 0.70mm) is likely well below the saturation value. |

---

## H010 — T09 anomaly: large negative surpluses trigger E004 even in target-axial-stack geometry
**Status:** OPEN | **Confidence:** MEDIUM

| | |
|---|---|
| Statement | T09 uses 60mm tabs on the target axial stack (electrode widths 64.11/65.11mm), giving surpluses of -4.11/-5.11mm. It fails with E004 despite the surpluses not being "near zero." This is the same surplus condition as R005 (production TBM with 60mm tabs). |
| Evidence for | R008-T09: FAIL E004. R005: FAIL E004 (same tab/electrode combination, different geometry context). |
| Evidence against | T01 passes with neg surplus = -0.11mm, showing very small negative surplus is acceptable when positive surplus is positive (+0.89mm). T09's failure could simply be H007 (combined large-negative surpluses), not a distinct anomaly. |
| Confounders | T09 has pos surplus = -4.11mm AND neg surplus = -5.11mm — both significantly negative. Under H007 (combined threshold), this should fail, and it does. The T09 anomaly may not be a separate hypothesis at all — it may be consistent with H007. |
| What it does not prove | Whether there is a distinct construction path triggered by large negative surplus vs near-zero surplus. |
| Production relevance | MEDIUM — T09 confirms that the R005 tab/electrode geometry is definitely failing under the same root-surplus mechanism. No additional testing needed for T09 specifically. |

---

## H011 — C00-C17 campaign results (production TBM localization)
**Status:** BLOCKED | **Confidence:** N/A

| | |
|---|---|
| Statement | The C00–C17 Detailed Builder and PCD transplant campaign (generated 2026-09-10) localizes E004 to specific TBM sections: project Detailed Builder, project PCD, or their interaction. |
| Evidence for | Pending — all runtime result columns in CAMPAIGN_MATRIX.csv are blank. |
| Evidence against | Pending. |
| Blocking failure | C00–C17 never sent to Robert (or results not returned). The H/T/F surrogate campaign was prioritized. |
| Minimum discriminator | Run C00 (environment control), C12 (Siemens Detailed Builder inside project PCD), C13 (Siemens PCD + Builder inside project model context). |
| Production relevance | HIGH — if C12 passes (Siemens Builder), the path to production TBM is to identify which Detailed Builder fields drive E004 within the project Builder. If C12 fails, the PCD geometry is implicated. |

---

## Summary table

| ID | Status | Confidence | Production relevance |
|---|---|---|---|
| H001 | CONFIRMED | HIGH | LOW (resolved) |
| H002 | REFUTED | HIGH | LOW |
| H003 | REFUTED | HIGH | MEDIUM (model correctness, not E004) |
| H004-1 | REFUTED | HIGH | LOW |
| H004-2 | REFUTED | HIGH | MEDIUM (model correctness) |
| H004-3 | REFUTED | HIGH | LOW for E004; HIGH for H008 distinction |
| H004-5 | BLOCKED | LOW–MEDIUM | HIGH (pending R006) |
| H004-6 | REFUTED | HIGH | LOW |
| H007 | SUPPORTED | HIGH | HIGH — defines tab-length fix |
| H008 | CONFIRMED (separate blocker) | HIGH | CRITICAL — prerequisite for production |
| H009 | SUPPORTED | HIGH | MEDIUM (saturation ceiling) |
| H010 | OPEN | MEDIUM | MEDIUM (consistent with H007) |
| H011 | BLOCKED | N/A | HIGH (localization campaign) |
