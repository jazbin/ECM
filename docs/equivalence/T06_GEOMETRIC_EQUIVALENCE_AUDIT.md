# T06 BDS Geometry vs OpenFOAM Reference — Geometric Equivalence Audit

**Date:** 2026-09-17
**Geometry:** `T06_TARGET_AXIAL_SURPLUS_2p00.step`, extracted from `in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip` (client-returned, not regenerated).
**Method:** exact B-Rep boolean intersection (pythonOCC/OpenCASCADE `BRepAlgoAPI_Common`), `tools/audit_bds_openfoam_overlap.py`. No voxel/triangulated approximation used for the primary result.
**Raw data:** `artifacts/equivalence/T06_BDS_TO_OPENFOAM_OVERLAP.csv`, `artifacts/equivalence/T06_CONTACT_GRAPH.csv`. Diagnostic figure: `artifacts/equivalence/figures/T06_axial_domain_mapping.png`.

## Finding classification — read this before the rest of the document

T06 (`T06_TARGET_AXIAL_SURPLUS_2p00.step`) was built at the **previous** JR OD
= 19.25mm radial target, not the final JR OD = Can ID = 20.6274mm target
confirmed in `NEXTSESSION` (2026-09-10) and
`tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`. Every finding below falls
into one of two categories, and they must not be conflated:

**TOPOLOGICAL FINDINGS — independent of final radial dimensions, valid now:**
- The BDS `Can` solid is a filled envelope spanning the full cell length
  (Key finding 1), not a thin wall — this is a modelling/export-convention
  fact about how the body was drawn, not a dimension.
- OpenFOAM's Cap domain exists only at the top of the cell; BDS mirrors
  hardware at both ends (Key finding 2) — this is a domain-topology fact.
- The Can→EndPlate→Internal-Post→Washer→Tab Stem→Tab Root→Jellyroll contact
  chain (Key finding 3) — this is a touching/not-touching graph, invariant
  to a uniform radial rescale.
These will still be true, in the same qualitative form, once T06 is rebuilt
at the final 20.6274mm radial target.

**DIMENSIONAL/COVERAGE FINDINGS — invalid until final radial geometry exists:**
- The specific overlap **percentages** in the table below (e.g. Can:
  83.68%/9.67%/3.49%/3.16%) and any volume-coverage/shortfall numbers derived
  from them (e.g. the ~44–84% Can/Cap thermal-mass shortfall reported in
  `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`) are artifacts of comparing a
  19.25mm-JR-OD body against 20.6274mm-JR-OD reference domains. They are
  **expected geometry mismatch**, not evidence that the BDS architecture is
  fundamentally short of thermal mass. Do not use these numbers to drive
  decisions. Re-run `tools/audit_bds_openfoam_overlap.py` against a
  final-dimension T06/T-series or H-series export before trusting any
  coverage percentage.

## Coordinate registration (stated explicitly, not silent)

The STEP file's solid axis is global **Y**; the OpenFOAM case's is global **Z** (cylindrical `coordinateSystem`, axis (0 0 1)). Registration is fixed by aligning the STEP JellyRoll's bottom face (y=0) to the OpenFOAM JellyRoll region's bottom face (z=0.23132mm): `z_of = y_step + 0.23132mm`. This is justified — not fitted — because the STEP Jellyroll/Mandrel axial extent (65.11mm exactly) matches the OpenFOAM JellyRoll region height to 5 significant figures with zero free parameters. No other registration choice reproduces that match. The residual ambiguity this leaves at the Can/Cap ends is discussed below and does not affect the JR-domain conclusions.

## Overlap matrix (13/13 bodies resolved, all EXACT B-Rep booleans, no fallback used)

| BDS body | Volume (mm³) | %JR | %Can | %Cap | %outside | Classification |
|---|---:|---:|---:|---:|---:|---|
| Mandrel | 1840.94 | 100.0 | 0.0 | 0.0 | 0.0 | EXACT_SUBDIVISION_JR |
| Jellyroll | 14509.17 | 100.0 | 0.0 | 0.0 | 0.0 | EXACT_SUBDIVISION_JR |
| Can | 6202.05 | 83.68 | 9.67 | 3.49 | 3.16 | **CROSSES_REFERENCE_DOMAINS** |
| +Ve Tab Root | 0.0071 | 0.0 | 0.0 | 100.0 | 0.0 | EXACT_SUBDIVISION_CAP |
| +Ve Tab Stem | 0.0676 | 0.0 | 0.0 | 100.0 | 0.0 | EXACT_SUBDIVISION_CAP |
| -Ve Tab Root | 0.0061 | 0.0 | 100.0 | 0.0 | 0.0 | EXACT_SUBDIVISION_CAN |
| -Ve Tab Stem | 0.0474 | 0.0 | 15.6 | 0.0 | 84.4 | **OUTSIDE_REFERENCE_GEOMETRY** (mostly) |
| +Ve Washer | 14.94 | 0.0 | 0.0 | 100.0 | 0.0 | EXACT_SUBDIVISION_CAP |
| -Ve Washer | 14.94 | 0.0 | 0.0 | 0.0 | 100.0 | **OUTSIDE_REFERENCE_GEOMETRY** |
| +Ve EndPlate | 20.41 | 0.0 | 0.0 | 100.0 | 0.0 | EXACT_SUBDIVISION_CAP |
| -Ve EndPlate | 20.41 | 0.0 | 0.0 | 0.0 | 100.0 | **OUTSIDE_REFERENCE_GEOMETRY** |
| +Ve Internal-Post | 8.22 | 0.0 | 0.0 | 100.0 | 0.0 | EXACT_SUBDIVISION_CAP |
| -Ve Internal-Post | 8.22 | 0.0 | 0.0 | 0.0 | 100.0 | **OUTSIDE_REFERENCE_GEOMETRY** |

## Key finding 1 — the BDS "Can" solid is not the OpenFOAM Can

The single BDS `Can` solid is a *filled envelope* spanning the entire cell length (z_of ≈ −2.21mm to +67.79mm), not a thin wall. Boolean intersection shows 83.7% of its volume physically coincides with the JellyRoll interior (because the Can solid, as exported, is a solid bounding shell that the Jellyroll/Mandrel sit inside, not a hollowed wall — a common BDS/Battery-Design-Studio export convention for the outer housing). Only 9.7% of Can's volume lands in the OpenFOAM Can domain and 3.5% in Cap; 3.2% falls entirely outside all three reference domains (below OpenFOAM's z=0 origin — see Key finding 2). **A literal "assign Can properties to the whole BDS Can body" mapping would put steel/Can thermal properties (ρ=8000, k=16 isotropic) into 83.7% of what OpenFOAM treats as anisotropic JellyRoll (k_z=29, k_r=1.4) — a severe, easily-missed error.** This body requires piecewise material assignment (see `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`), consistent with the `EXACT PIECEWISE UNION SUPPORTED` finding in `CAN_CAP_REDUCTION_DECISION.md`.

## Key finding 2 — OpenFOAM's Cap domain is asymmetric; BDS's hardware is symmetric

OpenFOAM has a Cap domain (4.68mm tall, full radius) **only at the top** of the cell (z 65.34–70.02mm); the bottom of the cell has no equivalent domain — just a thin (0.23mm) Can-material wall with a small explicit contact resistance. BDS/T06, by contrast, mirrors identical hardware (Tab Root/Stem, Washer, EndPlate, Internal-Post) at **both** ends of the cell (this is required for a real two-terminal battery). Under the JR-anchored registration, the entire "−Ve" (bottom) hardware stack falls at z_of < 0mm — i.e. **entirely outside all three OpenFOAM reference domains** (`OUTSIDE_REFERENCE_GEOMETRY`, confirmed for Washer, EndPlate, Internal-Post; Tab Root/Stem are 84–100% outside too, with small Can-domain slivers). The "+Ve" (top) hardware stack maps cleanly into OpenFOAM's Cap domain (`EXACT_SUBDIVISION_CAP`, 100% for 4 of 5 top bodies).

This is a geometry/topology mismatch, not a units or registration error: OpenFOAM's reference model genuinely does not resolve a physical bottom-end structure — it approximates the whole bottom-end thermal path with a single thin resistive contact layer between Can and JellyRoll. BDS resolves real bottom-end hardware volume there. **Reproducing the OpenFOAM operator in STAR therefore requires assigning the bottom-end BDS hardware (Internal-Post, Washer, EndPlate, Tab Root/Stem, and the corresponding fraction of Can) properties/interfaces that reduce it to the OpenFOAM near-ideal thin-layer approximation — not top-mirrored Cap properties.**

## Key finding 3 — a real conduction shortcut exists in the contact graph

From `T06_CONTACT_GRAPH.csv` (pairwise min B-Rep distance, `touching` = distance ≤ 0.001mm):

```
Can  --touching-->  EndPlate  --touching-->  Internal-Post  --touching-->  Washer  --touching-->  Tab Stem  --touching-->  Tab Root  --touching-->  Jellyroll
```

confirmed at both ends (all six "touching" links present for both +Ve and −Ve chains). This is exactly the high-risk pattern the governing task asked to check for: a **metallic, high-conductivity path from the externally-cooled Can surface straight into the JellyRoll**, bypassing the OpenFOAM reference's only bottom-path resistance (the thin `thicknessLayers` contact layer at JR↔Can-bottom) entirely, and bypassing the fact that OpenFOAM has *no* physical bottom-end domain at all. If this chain retains realistic BDS materials (e.g. copper tab/post, high k), it will conduct heat between Can-exterior and JellyroLl far faster than the OpenFOAM reference at the bottom end, and via a structure (posts/washers/endplate) OpenFOAM does not represent axially at the top either — the Cap domain there has k_z=0.1 W/mK (near-insulating), not metallic.

## Classification summary

- **Harmless subdivisions** (single dominant OF domain, ≥99%): Mandrel, Jellyroll (→JR); −Ve Tab Root (→Can); +Ve Tab Root/Stem, +Ve Washer/EndPlate/Internal-Post (→Cap). 7 of 13 bodies.
- **Cross-domain**: Can (1 body) — spans JR/Can/Cap/outside simultaneously.
- **Outside-reference / problematic thermal-shortcut bodies**: −Ve Tab Stem, −Ve Washer, −Ve EndPlate, −Ve Internal-Post (4 bodies) — all in the bottom-end region OpenFOAM does not resolve, and all sit on the confirmed Can→JellyRoll metallic contact chain.

Full detail: `artifacts/equivalence/T06_BDS_TO_OPENFOAM_OVERLAP.csv`, `artifacts/equivalence/T06_CONTACT_GRAPH.csv`, `artifacts/equivalence/figures/T06_axial_domain_mapping.png`.
