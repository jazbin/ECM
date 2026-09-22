# TBM Hypothesis Reconciliation Input
**Date:** 2026-09-22
**Purpose:** Structured input for reconciliation with session-history hypotheses.
Differences from prior analysis documents are flagged explicitly.

---

## 1. What this reconstruction agrees with

### Agrees: E004 is a CAD-feature construction failure upstream of geometry selection
Reached at CreateFromTbm; not a post-import geometry repair issue. Confirmed by all R-events.

### Agrees: Physical electrode widths are protected
Reducing electrode widths to create axial clearance is not a production fix. Confirmed by the working T-series (electrode widths 64.11/65.11mm in all T-cases; E004 controlled by tab lengths, not electrode widths).

### Agrees: S3, tab orientation, m_bOnly1D, transport number, and JR/Can radial equality are not E004 causes
All directly refuted by runtime evidence.

### Agrees: Package m_dintHeight isolated change is not the E004 cause
R007 (ROOT_A/ROOT_B both fail) refuted H004-6.

### Agrees: Separator feed/tail H004-5 is still formally open for the production TBM
R006 has not been received. H004-5 is BLOCKED, not REFUTED.

---

## 2. What this reconstruction adds or revises

### NEW CONFIRMED: Tab-electrode surplus threshold (H007)
Prior documents (E004_ELECTRODE_ROOT1_REVERSE_ENGINEERING_20260911.md) proposed package m_dintHeight as the "strongest remaining explanation" and demoted sep/feed-tail. After ROOT_A/ROOT_B failed (R007), the prior document correctly said "escalate to Siemens transplant pair." However, the H/T series results (R008) provide a BETTER explanation than anything in those documents:

**The operative variable is tab_length − electrode_width (the root surplus), not package m_dintHeight.**

This is directly confirmed by R008 H/T results. The prior document correctly identified the D00 REPORT block correlation (tab_length − electrode_width = 9/8mm = REPORT root heights) as a "new high-value clue" but this was written into the README.txt for the 30-case suite before results were received. The R008 results now confirm this hypothesis.

**Revision:** H004-6 (package height) REFUTED; H007 (tab-electrode surplus) SUPPORTED and is now the primary working hypothesis.

### NEW CONFIRMED: F-series radial blocker is a separate, distinct failure (H008)
Prior documents treated all F-series failures as potentially E004-related. R008 shows ALL F-series fail with a DIFFERENT error: "Jellyroll outer diameter is greater than Can inner diameter" / "Can Thickness is -ve." This has NOTHING to do with E004. It is a radial geometry conflict produced specifically by the combination of 2170 electrode widths with the stated Package radial dimensions.

**Prior analysis implication:** F04 (which has SepFeed=10/Tail=85) cannot serve as evidence for or against H004-5. The session log (2026-09-16) correctly noted this: "F04 already has SepFeedLength=10 / SepTailLength=85 and still fails — this rules out H004-5 as the explanation for the F-series failure."

### NEW SUPPORTED: Tab Stem geometric saturation (H009)
Not in any prior document. STEP B-Rep measurements show +Ve Tab Stem top-Y saturates at T06 (2mm surplus). T07 and T08 produce identical geometry despite larger inputs. **This is an independent observation from the STEP analysis, not the runtime pass/fail.** Prior campaign design did not anticipate this.

**Production implication:** Tab lengths need only exceed electrode widths by the minimum clearance threshold (between 0.10mm and 0.70mm, exact value pending NE02). Choosing very large surpluses produces no geometric benefit.

### CONTRADICTION PRESERVED: T01 passes with neg surplus = -0.11mm
Prior analysis predicted that "the Electrode Root derives from tab_length − electrode_width; near-zero or negative values fail." T01 passes with neg = -0.11mm. This is NOT necessarily a contradiction to H007: T01's positive root has +0.89mm surplus, and a combined or max-rule could explain both T01 (max = 0.89mm PASS) and H09 (max = 0mm FAIL) consistently. But the exact formula is unresolved; we do not assert a formula.

### CLARIFICATION: R006 (H004-5 production TBM feed/tail test) remains the most urgent missing data point
This test was built and dispatched 2026-09-10 but the result has never appeared in the STAR_IMPORT_ERROR_DATABASE.csv or any session log. The session log of 2026-09-16 focused on the client_v2 package and did not report on R006 outcome. Either Robert has not run it, or the result was not captured. THIS MUST BE CHASED BEFORE BUILDING NEW PRODUCTION TBMs.

---

## 3. Parameters and subsystems that should now be frozen

Do not queue experiments for these:

| Subsystem | Why frozen |
|---|---|
| Tab enable/orientation | H002 REFUTED by R002–R004 |
| m_bOnly1D fields | H003 REFUTED by R004 (still fix for model correctness) |
| S3 fields | H004-1 REFUTED by R005 |
| Transport number metadata | H004-2 REFUTED by R005 (still fix for model correctness) |
| JR/Can exact radial equality | H004-3 REFUTED by R005 |
| Package m_dintHeight isolated variation | H004-6 REFUTED by R007 |
| Root_A/Root_B style candidates | H004-6 path exhausted |
| F-series radial geometry (without H008 fix) | All blocked by "Can Thickness -ve" until H008 resolved |
| T-series surplus > 2mm | H009: geometry saturates; no information beyond T06 |

---

## 4. Open questions that require new evidence

| Question | Experiment | Urgency |
|---|---|---|
| Does R006 (feed/tail production TBM) pass? | Ask Robert for R006 result | IMMEDIATE |
| What is the minimum combined tab-surplus? | NE02: test ~0.35mm both-surplus case | HIGH |
| Does max-surplus or combined-surplus rule apply? | NE03: test pos=+0.70mm, neg=0mm | HIGH |
| What causes the F-series radial blocker? | NE04: two isolated-variable F-style tests | HIGH |
| Can C12/C13 localize E004 in production Builder? | NE05: run C00, C12, C13 | MEDIUM |

---

## 5. Summary status of all E004 hypotheses

| Hypothesis | Prior status (before R008) | Current status (after R008) |
|---|---|---|
| H001 Mandrel thickness | CONFIRMED | CONFIRMED (unchanged) |
| H002 Tab flags/orientation | REFUTED | REFUTED (unchanged) |
| H003 m_bOnly1D | REFUTED | REFUTED (unchanged) |
| H004-1 S3=0 | REFUTED | REFUTED (unchanged) |
| H004-2 Transport number | REFUTED | REFUTED (unchanged) |
| H004-3 Radial JR/Can | REFUTED | REFUTED (unchanged) |
| H004-5 Sep feed/tail | BLOCKED (R006 pending) | BLOCKED (unchanged; R006 still pending) |
| H004-6 Package m_dintHeight | REFUTED (by R007) | REFUTED (unchanged) |
| H007 Root surplus threshold | OPEN (hypothesis only in README) | SUPPORTED by R008 H/T series |
| H008 F-series radial blocker | Not previously named | CONFIRMED as separate blocker |
| H009 Tab stem saturation | Not previously named | SUPPORTED by STEP measurements |
| H010 T09 anomaly | Not previously named | OPEN (likely consistent with H007) |
| H011 C00–C17 localization | BLOCKED (not run) | BLOCKED (unchanged) |
