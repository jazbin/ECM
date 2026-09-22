# TBM Hypothesis Ledger — Authoritative
**Last updated:** 2026-09-22
**Supersedes:** TBM_HYPOTHESIS_LEDGER_CLAUDE.md (retained as audit evidence)
**Evidence base:** Robert runtime events R001–R008; August 2026 isolated-variable STEP characterization; T-series STEP B-Rep measurements; DELTAS.txt; GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md; reconciliation rounds 1–2.
**Status vocabulary:** CONFIRMED / SUPPORTED / REFUTED / OPEN / BLOCKED / INCONCLUSIVE / SUPERSEDED / DEFERRED

---

## Executive summary

### Frozen — stop perturbing

- Mandrel thickness (E003): resolved, positive in all current TBMs
- Tab enable/orientation flags: refuted for E004
- m_bOnly1D (SIMMOD): refuted for E004; retain for model correctness
- S3 field: refuted for E004
- Transport number metadata: refuted for E004; retain for model correctness
- Package m_dintHeight isolated variation: refuted for E004
- T06 root/tab geometry: confirmed sufficient; use as baseline without modification

### Current primary attack surface

**RADIAL BDS BLACK-BOX MAPPING**

### Current highest-value unknown

Which TBM field independently controls generated Can ID?

### Current production strategy

```
T06 root baseline (both surpluses = +2.00mm, frozen)
→ identify radial field controls via RAD-A/B/C
→ positive-clearance 2170 import (RAD-D1)
→ exact-contact 2170 import (RAD-D2)
→ resume electrothermal equivalence work
```

---

## H001 — E003: Mandrel thickness must be positive

**Status:** CONFIRMED | **Confidence:** HIGH

| | |
|---|---|
| Statement | STAR CreateFromTbm fatally rejects a TBM whose mandrel thickness evaluates to zero or negative. |
| Evidence | R001: all four variants fail with "Mandrel thickness must be positive" before any other error. R002: after mandrel fix, E003 absent in all subsequent runs. |
| Contradictions | None. |
| What is proven | E003 is a distinct gate that precedes E004. Once fixed it stays fixed. |
| What is NOT proven | Which specific field(s) in R001 caused the zero mandrel; whether the fix changed other fields. |
| Production relevance | LOW — resolved. Do not reduce mandrel thickness. |
| Next discriminator | None needed. |

---

## H002 — Tab enable flags and vertical orientation cause E004

**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | Enabling/disabling tabs or switching top/bottom tab orientation resolves E004. |
| Evidence against | R002–R004: E004 survives across all four tab-on/off and standard/same-face permutations. |
| What is NOT proven | Whether tab construction is involved in the root-extrusion path; only the configuration flags are refuted. |
| Production relevance | LOW — do not queue tab-orientation variants. |
| Next discriminator | None. |

---

## H003 — m_bOnly1D flag causes E004

**Status:** REFUTED (for E004) | **Confidence:** HIGH

| | |
|---|---|
| Statement | Incorrect m_bOnly1D values in SIMMOD blocks block distributed 3D construction and produce E004. |
| Evidence against | R004: m_bOnly1D warning cleared; E004 unchanged. |
| What is NOT proven | m_bOnly1D is still required for correct distributed electrothermal solve; its cleanup belongs in the production TBM for model correctness. |
| Production relevance | MEDIUM (model correctness only, not E004). |
| Next discriminator | None for E004. |

---

## H004-1 — +Electrode S3 = 0 causes E004

**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | A zero-valued +Electrode m_dS3 produces a degenerate tab/root geometry triggering E004. |
| Evidence against | R005: S3 changed 0→5mm; E004 unchanged. |
| What is NOT proven | S3 physical role in auxiliary geometry; only E004 causality is refuted. |
| Production relevance | LOW for E004. |
| Next discriminator | None. |

---

## H004-2 — Transport number metadata causes E004

**Status:** REFUTED (for E004) | **Confidence:** HIGH

| | |
|---|---|
| Statement | Incorrect transport number fields prevent import/construction. |
| Evidence against | R005: transport-number cleanup applied; E004 unchanged. |
| What is NOT proven | Transport number is still required for model correctness. |
| Production relevance | MEDIUM (model correctness only). |
| Next discriminator | None for E004. |

---

## H004-3 — Physical JR OD = Can ID in generated geometry causes E004

**Status:** OPEN | **Confidence:** LOW

| | |
|---|---|
| Statement | Generated jellyroll OD equal to generated Can ID causes a radial construction failure that manifests as or contributes to E004. |
| Evidence for | Pre-runtime concern about zero-clearance CAD geometry. |
| Evidence against | R005 was designed for JR OD = Can ID contact (project TBM, "exact-contact-final"). However R005 failed with E004 before successfully generating geometry. Therefore it demonstrates that its written field combination does not eliminate E004, but does NOT demonstrate that physical contact was or was not achieved in generated geometry. |
| Critical constraint | R005 NEVER GENERATED GEOMETRY. Any claim about "physical state" in R005 refers to intended field values, not observed generated dimensions. |
| Original refutation scope | The claim "equal numerical values in m_dintDiameter and m_dJellyrollThickness_mm cause E004" is REFUTED by R005. Physical zero-clearance contact in generated geometry remains untested. |
| What is NOT proven | Whether the physical JR-OD-equals-Can-ID state, if actually generated, would cause any import failure. |
| Production relevance | LOW for E004 directly. Relevant for RAD-D2 (exact-contact constructibility test). |
| Next discriminator | RAD-D2: after RAD-D1 passes with positive clearance, attempt JR OD = Can ID and observe whether any new failure appears. |

---

## H004-5 — Separator feed/tail = 0/0 causes E004

**Status:** BLOCKED | **Confidence:** LOW

| | |
|---|---|
| Statement | m_dSepFeedLength_mm = 0 and/or m_dSepTailLength_mm = 0 produces a zero-length CAD feature triggering E004. |
| Evidence for | Pre-runtime: STAR-install TBMs commonly use feed=10/tail=85; project uses 0/0. |
| Evidence against | (a) Siemens HP18650 Detailed Builder uses 0/0 and generates clean 13-solid STEP. (b) HE18650 also uses 0/0 — two verified Siemens counterexamples. (c) F04 has SepFeed=10/Tail=85 and still fails on the radial blocker, not E004 — this shows feed/tail is not sufficient to unblock the F-series, but F-series failure is a separate mechanism (H008). (d) R006 result has not been received. |
| Blocking failure | R006 (production TBM + feed/tail fix, sent 2026-09-10) result not yet received from Robert. |
| What is NOT proven | Whether H004-5 is a co-cause of E004 in the production TBM specifically. |
| Production relevance | LOW-MEDIUM. Retrieve R006 result opportunistically. Do NOT hold the campaign pending R006 — H007-based fix (root surplus) is the higher-confidence path. |
| Next discriminator | R006 result retrieval (passive). |

---

## H004-6 — Zero package-to-negative-electrode axial clearance causes E004

**Status:** REFUTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | Package m_dintHeight = negative_electrode_width (0.00mm axial clearance) drives the electrode-root extrusion distance to zero. |
| Evidence against | R007: ROOT_A (+0.10mm clearance) and ROOT_B (+0.70mm clearance) BOTH fail with identical E004. |
| What is NOT proven | Package m_dintHeight may still influence root geometry in subtle ways; only causality within the tested range is refuted. |
| Production relevance | LOW for E004. Axial margins remain physically relevant for production geometry correctness. |
| Next discriminator | None. |

---

## H007 — Tab-electrode surplus is strongly associated with E004

**Status:** SUPPORTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | Near-zero or negative tab-electrode surpluses on both polarities are strongly associated with E004 failure. Sufficient combined surplus on both polarities is strongly associated with clean import. |
| Evidence for | R008 H/T series results (exhaustive): H01 (pos=0, neg=+8mm) PASS; H05 (pos=+9mm, neg=0) PASS; H09 (both=0) FAIL; H10 (both=+0.10mm) FAIL; H11 (both=+0.70mm) PASS; T01 (pos=+0.89mm, neg=−0.11mm) PASS; T02 (both=0) FAIL; T03 (both=+0.10mm) FAIL; T04 (both=+0.70mm) PASS; T09 (pos=−4.11mm, neg=−5.11mm) FAIL. |
| T01 note | pos=+0.89mm, neg=−0.11mm → PASS. A small negative surplus on one polarity is tolerated when the other has sufficient positive surplus. This demonstrates the rule is coupled/joint, not a strict per-polarity positive floor. |
| T09 note | Large negative surpluses on both polarities (−4.11/−5.11mm) fail. This is fully consistent with H007; no separate mechanism is required for T09. |
| Empirical bracket | Both-surplus bracket: both ≤ 0.10mm → FAIL; both ≥ 0.70mm → PASS. Asymmetric: Delta_avg ≥ +0.39mm (T01) → PASS. |
| What is NOT proven | (a) The exact Siemens internal formula: whether STAR uses Delta_avg, Delta_max, Delta_sum, or another function. (b) Whether "Electrode Root 1" corresponds to positive or negative. (c) Whether the threshold is a CAD-kernel epsilon or an explicit field-value gate. |
| What is proven | Claim (a) SUPPORTED: root construction outcome depends jointly on both surplus quantities. Claim (b) SUPPORTED: the two polarities are coupled — single-polarity zero surplus is tolerated, joint near-zero fails. Claim (c) NOT PROVEN: STAR directly equates root extrusion to any specific algebraic function of the individual deltas. |
| Contradictions | None. |
| Production relevance | HIGH — this hypothesis defines the tab-length fix. T06 (both surpluses = +2.00mm) is the confirmed PASS baseline and the frozen root configuration. |
| Next discriminator | None needed before RAD campaign — T06 surplus is sufficient. Threshold localization (exact midpoint between 0.10mm and 0.70mm) has low engineering value because T06 (+2.00mm) is on the STEP saturation plateau and is robust. |

---

## H008a — F-series radial blocker is a separate failure from E004

**Status:** CONFIRMED | **Confidence:** HIGH

| | |
|---|---|
| Statement | All F-series TBMs fail with "Can Thickness is -ve" — a radial geometry conflict distinct from E004 ("Electrode Root 1: Extrusion distance can not be 0"). These are different STAR error messages from different construction stages. |
| Evidence | R008: ALL nine F-series cases (F01–F09) fail with the Can-thickness error. H/T-series (different radial geometry) do not exhibit this error. F04 (SepFeed=10/Tail=85) still fails — feed/tail does not suppress the radial blocker. F09 (synchronized volumes) still fails. |
| Contradictions | None. |
| What is proven | The radial blocker is a necessary pre-condition that must be resolved before any E004 behavior in full-2170-geometry TBMs can be assessed. |
| Production relevance | CRITICAL — prerequisite for all production TBM testing. |
| Next discriminator | RAD-B/C (map m_dRepCanXDim → Can OD and m_dJellyrollThickness_mm → JR OD). RAD-D1 tests the corrected combination. |

---

## H008b — F-series radial blocker caused by m_dRepCanXDim not updated from D00 baseline

**Status:** SUPPORTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | F-series TBMs inherited D00's m_dRepCanXDim/YDim = 18mm while setting m_dJellyrollThickness_mm = 20.6274mm. Under the supported mapping (m_dRepCanXDim → Can OD), this gives Can OD ≈ 18mm against JR OD ≈ 20.6274mm, producing the fatal geometry conflict. |
| Evidence | DELTAS.txt (F-series): no m_dRepCanXDim change in any F-series delta — F-series inherited D00 REPORT block. T06 REPORT block (read directly): m_dRepCanXDim = 18mm, m_dRepCanYDim = 18mm. August 2026 isolated-variable characterization: m_dRepCanXDim → Can OD (SUPPORTED). Failure chain: JR OD (20.6274mm) >> Can OD (18mm) → STAR clamps Can ID = 20.6274mm → Can thickness = (18 − 20.6274)/2 < 0 → "Can Thickness is -ve". |
| Contradictions | None. |
| What is NOT proven | That m_dRepCanXDim is definitively the Can-OD control — this is supported from the August characterization but awaits RAD-B confirmation. |
| Production relevance | HIGH — the fix is to set m_dRepCanXDim/YDim = 21.09mm (matched to production Can OD target) before attempting F-series radial geometry. |
| Next discriminator | RAD-B: vary m_dRepCanXDim/YDim only and measure Can OD in STEP. |

---

## H008c — Electrode widths drive wound JR OD and cause F-series radial inflation

**Status:** OPEN | **Confidence:** LOW

| | |
|---|---|
| Statement | The 2170 electrode widths (64.11/65.11mm vs. working-cell 56/57mm) cause STAR's internal winding computation to produce a larger wound JR OD independent of m_dJellyrollThickness_mm. |
| Evidence for | Pre-analysis inference: F-series simultaneously changed electrode widths and radial Package/Builder fields; electrode width is the most obvious difference between working-cell and 2170-cell TBMs. |
| Evidence against | August 2026 characterization established that m_dJellyrollThickness_mm drives realized JR OD (Builder field takes precedence over physical winding and REPORT values). If Builder m_dJellyrollThickness_mm directly controls JR OD, electrode widths may not independently inflate JR OD. |
| Contradictions | H008b and H008c are not mutually exclusive; both could contribute. |
| What is NOT proven | Either way. No isolated electrode-width variation with STEP measurement has been performed. |
| Production relevance | LOW-MEDIUM — if H008c is false, updating m_dRepCanXDim/YDim and m_dJellyrollThickness_mm corrects F-series. If true, electrode widths must also be accounted for. RAD campaign will reveal this. |
| Next discriminator | RAD-C (vary m_dJellyrollThickness_mm only from T06 baseline with T-series electrode widths, observe JR OD). If JR OD tracks m_dJellyrollThickness_mm faithfully, electrode widths are not independently driving JR OD. |

---

## H009 — Tab Stem geometric saturation above ~2mm surplus

**Status:** SUPPORTED | **Confidence:** HIGH

| | |
|---|---|
| Statement | The generated +Ve Tab Stem bounding-box top-Y (axial, mm) reaches a maximum at approximately 2mm tab-electrode surplus input. Inputs above this (5mm, +9/+8mm) produce geometrically identical STEP output. |
| Evidence | STEP B-Rep measurements on untessellated T-series solids: T01 = 65.557mm; T04 = 65.812mm; T05 = 66.112mm; T06 = 66.275mm; T07 = 66.275mm; T08 = 66.275mm. Exact numeric equality at T06/T07/T08. Fixed-scale visual render confirms visually indistinguishable T06/T07/T08 panels. |
| Note | Generated Tab Stem extent (66.275mm from electrode base at 64.11mm = +2.165mm above electrode) does not equal the input surplus (+2.00mm). The relationship between input surplus and generated root extent is not 1:1 — the exact formula is unknown. |
| What is NOT proven | (a) Negative root saturation value. (b) Whether STAR electrical/thermal mesh is also saturated. (c) The cause of saturation (package cavity constraint vs. internal formula clamp). |
| Production relevance | MEDIUM — no engineering benefit to tab lengths more than ~2mm above electrode width. Use T06-level surplus for production. |
| Next discriminator | None needed. |

---

## H010 — T09 requires a separate mechanism beyond H007

**Status:** SUPERSEDED | **Confidence:** HIGH

| | |
|---|---|
| Statement | T09 (pos=−4.11mm, neg=−5.11mm) fails for a reason beyond H007. |
| Superseded by | H007. Delta_avg for T09 = −4.61mm, well below the ≥+0.39mm pass threshold. T09 is fully consistent with H007 and requires no independent explanation. Session log labeled it "anomalous" before H007 was understood; that label no longer applies. |
| Production relevance | None. |

---

## H011 — C00–C17 campaign: Builder/PCD localization

**Status:** DEFERRED | **Confidence:** N/A

| | |
|---|---|
| Statement | The C00–C17 Detailed Builder and PCD transplant campaign localizes E004 to specific TBM sections. |
| Current status | Campaign not run. CAMPAIGN_MATRIX.csv runtime columns blank. |
| Deferral reason | H007 provides a higher-confidence production fix path (root surplus). C00–C17 is a contingency for diagnosing unexplained failure after H007 and radial fixes are applied. |
| Trigger condition | Run only if RAD-D1 (production geometry with valid surplus + corrected radial fields) fails for an unexplained reason. |
| Minimum run | C00 (environment control), C12 (Siemens Detailed Builder + project PCD), C13 (Siemens PCD + Builder + project context). |
| Production relevance | CONTINGENCY ONLY. |

---

## Radial mapping hypotheses

These are not historical hypotheses but are the current primary open questions driving the RAD campaign.

### RMAP-1 — m_dJellyrollThickness_mm → realized JR OD

**Status:** CONFIRMED | **Confidence:** HIGH

| | |
|---|---|
| Evidence | August 2026 isolated-variable matrix (21 variants, one-field-at-a-time). Inputs 17.0, 17.3, 17.6mm realized as 17.009, 17.303, 17.562mm in STEP (B-Rep bounding box). Monotonic, < 0.25mm discretization deviation. Builder field "won" over REPORT JR diameter and physical winding-length values in conflicts. 18.2mm failed because it exceeded the 18.0mm can in that test model. |
| Limitation | Confirmed for the August test cell geometry. RAD-C verifies the same mapping holds for T06-baseline geometry before depending on it for production. |
| What is NOT proven | Exact conversion slope (close to 1:1 but small offset observed). |

### RMAP-2 — m_dRepCanXDim/YDim → generated Can OD

**Status:** SUPPORTED | **Confidence:** HIGH

| | |
|---|---|
| Evidence | August 2026 characterization: "REPORT can diameter apparently drove can OD in the tested matrix" (isolated observation). D00 REPORT block: m_dRepCanXDim = 18mm consistent with D00 being an ~18mm-can cell. Level-C documentation (CURRENT_TBM_FIELD_AUDIT.md): m_dRepCanXDim consumed by STAR (YES). |
| Limitation | "Apparently" — the August characterization used one cell geometry class. RAD-B tests whether the mapping holds for T06-baseline. A null result from RAD-B (no Can OD change) would mean STAR regenerates the REPORT block and m_dRepCanXDim is not the operative field. |
| What is NOT proven | Whether m_dRepCanXDim or m_dextDiameter or some interaction determines Can OD in the production TBM geometry class. |
| Next discriminator | RAD-B. |

### RMAP-3 — m_dintDiameter → generated Can ID

**Status:** OPEN | **Confidence:** LOW

| | |
|---|---|
| Evidence for | R005 TBM was designed as "exact-contact-final" with m_dintDiameter = m_dJellyrollThickness_mm = 20.6274mm, consistent with intended JR OD = Can ID. Naming convention: "int" = internal. |
| Evidence against | August 2026 characterization did not test m_dintDiameter as an isolated variable. No STEP measurement of Can ID from any T-series case exists. |
| Constraints | R005 never generated geometry — cannot prove the intended physical state was achieved. Cannot infer Can ID from R005 STEP (none exists). |
| What is NOT proven | That m_dintDiameter independently controls Can ID in generated geometry. It may be overridden by m_dRepCanXDim or computed from m_dextDiameter and a wall-thickness formula. |
| Next discriminator | RAD-A: vary m_dintDiameter only from T06 baseline (20.9 → 20.5mm) and measure Can ID in STEP. |

---

## Summary table

| ID | Status | Confidence | Production relevance |
|---|---|---|---|
| H001 | CONFIRMED | HIGH | LOW (resolved) |
| H002 | REFUTED | HIGH | LOW |
| H003 | REFUTED (for E004) | HIGH | MEDIUM (model correctness) |
| H004-1 | REFUTED | HIGH | LOW |
| H004-2 | REFUTED (for E004) | HIGH | MEDIUM (model correctness) |
| H004-3 | OPEN | LOW | LOW (E004); relevant for RAD-D2 |
| H004-5 | BLOCKED | LOW | LOW (retrieve R006 passively) |
| H004-6 | REFUTED | HIGH | LOW |
| H007 | SUPPORTED | HIGH | HIGH — defines tab-length fix |
| H008a | CONFIRMED (separate blocker) | HIGH | CRITICAL |
| H008b | SUPPORTED | HIGH | HIGH (F-series fix) |
| H008c | OPEN | LOW | LOW-MEDIUM |
| H009 | SUPPORTED | HIGH | MEDIUM (saturation ceiling) |
| H010 | SUPERSEDED (by H007) | HIGH | NONE |
| H011 | DEFERRED | N/A | CONTINGENCY only |
| RMAP-1 | CONFIRMED | HIGH | CRITICAL (JR OD control) |
| RMAP-2 | SUPPORTED | HIGH | CRITICAL (Can OD control) |
| RMAP-3 | OPEN | LOW | CRITICAL (Can ID control) |
