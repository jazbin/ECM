# OpenFOAM–STAR Equivalence

Use for ECM TBM/STAR equivalence analysis.

## Objective

Reproduce the OpenFOAM–ECM operator in STAR. Literal CAD/body equivalence is not required unless geometry prevents operator equivalence.

## Evidence order

Prefer:

1. raw OpenFOAM case / actual STAR evidence;
2. returned STEP/runtime evidence;
3. exact geometry audits;
4. canonical repo analyses;
5. field names/design intent.

Never infer semantics from a TBM field name alone.

## Epistemic rule

Separate:

* observed fact;
* supported interpretation;
* unknown STAR capability;
* geometry requirement.

A STEP topology is not automatically the STAR computational Region topology.

## Geometry-vs-mapping classification

For each mismatch use:

* A — MUST FIX IN TBM: geometry prevents equivalent operator.
* B — REDUCIBLE IN STAR: Region/material/interface mapping can plausibly make it equivalent.
* C — DEPENDS ON S0: actual STAR Region topology/capability is required.
* D — NOT OPERATOR-RELEVANT after valid mapping.

## Campaign rule

Before proposing, modifying, approving, or packaging any Robert/STAR/TBM experiment:

1. Read `docs/equivalence/ECM_EQUIVALENCE_MASTER_MATRIX.md` (139 requirements across GEO/TOP/MAT/IFC/BC/SRC/IC/LUMP/ELEC/DIST/STAR/VAL/RUN families).
2. Read `docs/equivalence/ECM_CAMPAIGN_READINESS_GATE.md` (10-point gate; all points must pass before dispatch).
3. Preserve coverage of all requirement families — no family may lose its last resolution path as a result of any scoping decision.
4. Distinguish the common thermal foundation (Test A) from the LUMP electrical track (OF `couplingMode lumped` ↔ STAR 0D RCR) and the DIST electrical track (OF `couplingMode elementWise` ↔ STAR RCRTable 3D). Both electrical tracks are required.
5. Explicitly check both RADIAL geometry requirements (GEO-001..007, RAD campaign) and AXIAL/END geometry requirements (GEO-009..021, GEO-AX campaign) — they are separate families with separate experiments.
6. An experiment may be removed, merged, or superseded only if every requirement ID it covered either retains coverage from another planned experiment or is already SATISFIED by stronger evidence. Cite the requirement IDs, not just a narrative.

Do not embed the 139 requirements in this skill file. The canonical source is `ECM_EQUIVALENCE_MASTER_MATRIX.md`.

## Efficiency

Read named evidence files first. Do not repeat B-Rep calculations or repo-wide searches when committed reports already contain the needed measurements.

Use direct file reads/grep. Do not spawn subagents unless a truly independent workstream is necessary.

Do not reopen settled hypotheses unless new evidence contradicts them.

Prefer one compact decision table over narrative.

For this project, optimize Robert runs, not understanding undocumented Siemens internals for its own sake.
