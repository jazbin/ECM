# ECM Campaign Readiness Gate

**Date:** 2026-09-23
**Branch:** claude/openfoam-star-equivalence-2026-09-17
**Purpose:** Every future Robert package (S0, RAD, Test A/B/C/D, GEO-AX, or any follow-on) must pass this gate before dispatch. Purpose is to prevent scope collapse: a package that solves one blocker must not allow other equivalence requirements to fall off the campaign.

**Usage:** Before preparing a package for Robert, work through each of the 10 checks below. Record YES/NO and the supporting evidence. A single NO is a dispatch blocker unless the item is explicitly deferred by prior mutual agreement and that deferral is recorded here.

---

## Gate 1 — Requirement traceability

**Check:** Every deliverable in this package maps to ≥ 1 requirement ID in `ECM_EQUIVALENCE_MASTER_MATRIX.md`. No deliverable is justified only by narrative.

**How to verify:** List the requirement IDs this package addresses in the package README. Check each ID exists in the master matrix.

**Dispatch blocker if:** The package asks Robert to test something with no corresponding requirement ID, or adds a new geometric feature with no requirement justification.

---

## Gate 2 — Orphan-requirement scan

**Check:** No requirement family in the master matrix has regressed from PARTIAL or OPEN to UNSEEN as a side-effect of this package's scope decisions.

**How to verify:** For each GEO/TOP/MAT/IFC/BC/SRC/IC/ELEC/DIST/STAR/VAL/RUN family, confirm the coverage matrix still assigns ≥ 1 future or current experiment. If this package closes a blocker (e.g., S0-B), confirm the downstream requirements (e.g., GEO-007, TOP-001, IFC-001) are picked up by a named subsequent step.

**Dispatch blocker if:** Solving blocker X removes all planned steps that would address a downstream requirement family.

---

## Gate 3 — Contradiction audit

**Check:** No item in `ECM_EQUIVALENCE_CONTRADICTIONS.md` affects the instructions in this package in an unresolved way.

**How to verify:** Cross-check package instructions against C01..C10 and any new contradictions added since last review. Specifically:
- C01 (f_cap): any heat-source instruction in this package uses 0%, not 0.034.
- C02 (Rtherm): any resistance instruction uses R_specific = 6.015×10⁻⁷ m²K/W, not 5.4 K/W.
- C04 (F-series): no instruction states that zero-clearance construction is impossible or that S0-B is the only radial route.
- C06 (S0-B area): if this is an S0 package, Root↔JR interface AREA is requested, not just existence.

**Dispatch blocker if:** Package instructions reference a contradicted or superseded value without explicit override justification.

---

## Gate 4 — S0 prerequisite check

**Check:** If this package requires S0-A, S0-B, S0-C, or S0-D output to interpret results, confirm that S0 has been run and its return has been read and reconciled.

**How to verify:** Check `TBM_HYPOTHESIS_LEDGER.md` and session log for S0 return evidence. If S0 is not yet returned, the package must either (a) be S0 itself, or (b) be a parallel package (e.g., RAD-A/B/C) that does not depend on S0 output for interpretation.

**Dispatch blocker if:** Package depends on S0-B interface topology evidence to interpret results, but S0-B has not been returned.

---

## Gate 5 — Geometry dimension correctness

**Check:** Any TBM in this package uses the correct operative values for the dimensions it intends to test. Protected parameters are not inadvertently changed.

**How to verify:** For every TBM parameter in the package, confirm:
- JR OD target (m_dJellyrollThickness_mm): if being set, confirm target = 20.6274 mm or is an intentional RAD sweep value.
- Can OD (m_dRepCanXDim/YDim): if being set, confirm target = 21.09 mm or intentional sweep.
- Can ID (m_dintDiameter or operative field): if being set, confirm target = 20.6274 mm or intentional sweep.
- Protected parameters (m_bOnly1D=0, m_dAhCell=5.0, m_nRCRParameterSets=3, m_bLumpedEnergyBalance=0, IET=RCRTable 3D, Thermal=Distributed, +m_dS3=5mm, -m_dS3=50mm, Transport=0) are preserved unless this package is specifically testing one of them.
- F-series failure mode check: if JR OD > 0.5 × Can OD (rough sanity), flag for review before sending.

**Dispatch blocker if:** Any protected parameter has been changed without justification, or JR OD >> Can OD in the same TBM.

---

## Gate 6 — Robert deliverable completeness

**Check:** The README_FOR_ROBERT document in this package specifies every measurement or output that future equivalence analysis will need from this run. No critical measurement is left implicit.

**How to verify:** Walk through the relevant requirement IDs for this package and confirm each has a corresponding explicit measurement request in the README. For geometry tests: STEP file + dimension table. For STAR runs: screenshot + volume/interface table. For S0-B specifically: interface area for Root↔JR pairs must be explicitly listed.

**Dispatch blocker if:** A requirement ID is covered by this package but the README does not ask Robert to measure the corresponding quantity.

---

## Gate 7 — Dependency ordering

**Check:** All upstream dependencies for this package are either satisfied or explicitly deferred with justification.

**How to verify:** For each requirement ID in this package, check `ECM_EQUIVALENCE_MASTER_MATRIX.md` `Dep` column. Confirm each dependency is either SATISFIED or is being handled in a parallel package.

**Dispatch blocker if:** A critical dependency (e.g., RAD-A needed before RAD-D2; S0-B needed before Test A's interface mapping) has not been met and is not in parallel.

---

## Gate 8 — No stale evidence as a basis

**Check:** The package design decisions are not based on claims flagged as stale or superseded in the contradictions document or in any canonical ledger.

**How to verify:** Specifically check:
- `NEXTSESSION` file: was it written before Sep-16 Robert return? If so, verify each "next step" it names is still current.
- Coverage percentages from `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`: not being cited as equivalence evidence.
- `TBM_HYPOTHESIS_LEDGER.md`: any hypothesis used as a design input is not REJECTED or SUPERSEDED.
- F-series failure: no document in the package states zero-clearance is impossible.

**Dispatch blocker if:** A package design decision rests on a superseded or contradicted claim.

---

## Gate 9 — Equivalence test plan consistency

**Check:** This package does not reduce, remove, or weaken any planned step in `STAR_CLIENT_EQUIVALENCE_TEST_PLAN.md` or the RAD campaign in `TBM_NEXT_EXPERIMENTS.md` without explicit replacement.

**How to verify:** After preparing this package, list any changes to the test plan or experiment plan it implies. For each change, confirm there is a named replacement step that covers the same requirement IDs. A "we don't need that test anymore" decision requires an evidence-backed justification referencing a specific requirement ID, not just a narrative.

**Dispatch blocker if:** A planned test (Test A/B/C/D, RAD-A..D2, S0-A..D, GEO-AX) is being skipped with no equivalent coverage of its requirement IDs.

---

## Gate 10a — Two-track coverage (lumped + distributed)

**Check:** Any package that addresses electrical equivalence must explicitly specify which track it covers: LUMP (OF `couplingMode lumped` ↔ STAR 0D RCR) or DIST (OF `couplingMode elementWise` ↔ STAR RCRTable 3D). No package may be described as covering "ECM equivalence" without stating the track.

**How to verify:**
- If this package's scope touches ELEC/LUMP/DIST/VAL requirements, confirm it names the relevant track(s).
- If addressing only one track, confirm the other track has a named future step.
- Do not cite `wedge_2170` as the distributed reference — it is `couplingMode lumped`. The distributed reference is `validation_distributed_paramset_21p09x70p02` (`couplingMode elementWise`, 18 partitions).
- Do not describe STAR distributed RCR as an enhancement over a lumped OF baseline. Both tracks are independent requirements.

**Dispatch blocker if:** Package claims to validate "ECM equivalence" without specifying which track, or misidentifies wedge_2170 as the distributed reference.

---

## Gate 10 — Hypothesis ledger consistency

**Check:** Any hypothesis in `TBM_HYPOTHESIS_LEDGER.md` that this package's results will affect has a clear expected-outcome statement written down before dispatch. After Robert returns, the update to the ledger is planned (not retroactive rationalization).

**How to verify:** For each hypothesis relevant to this package (e.g., H004-3 for RAD-D2; RMAP-3 for RAD-A; S0-B gap-tolerance for the S0 package), write its expected outcome in the package README or a pre-dispatch note. When Robert returns, update the ledger first before designing the next package.

**Dispatch blocker if:** This package will generate evidence that could confirm or refute a critical hypothesis, but no pre-dispatch expected-outcome is recorded.

---

## Quick-reference checklist (paste into each package README)

```
ECM Campaign Readiness Gate — package: <NAME> — date: <DATE>

[ ] Gate 1: All deliverables mapped to requirement IDs: <IDs>
[ ] Gate 2: No requirement family orphaned by this package's scope
[ ] Gate 3: No contradiction in C01-C10 affects these instructions
[ ] Gate 4: S0 prerequisite: [ ] not needed / [ ] satisfied (evidence: ___)
[ ] Gate 5: Protected parameters verified; no JR OD >> Can OD
[ ] Gate 6: All required measurements explicitly listed in README
[ ] Gate 7: All upstream dependencies satisfied or parallel
[ ] Gate 8: No stale/superseded claim used as design input
[ ] Gate 9: No test plan step weakened without replacement
[ ] Gate 10a: If electrical reqs in scope — track specified (LUMP / DIST / both); wedge_2170 not cited as distributed reference
[ ] Gate 10: Pre-dispatch expected outcomes recorded for affected hypotheses

Blockers: <none / list>
Approved by: <initials> <date>
```
