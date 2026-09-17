# BDS (T06) → OpenFOAM Thermal Mapping

**Date:** 2026-09-17
**Guiding rule** (per governing task): at each spatial location, STAR should solve the thermal physics of the OpenFOAM reference material occupying that location — not the BDS/electrical label of the body there.
**Inputs:** `artifacts/equivalence/T06_BDS_TO_OPENFOAM_OVERLAP.csv`, `artifacts/equivalence/T06_CONTACT_GRAPH.csv`, `artifacts/equivalence/THERMAL_CAPACITANCE_AUDIT.csv`, `docs/equivalence/CAN_CAP_REDUCTION_DECISION.md` (EXACT PIECEWISE UNION SUPPORTED for Can/Cap).

| BDS body | Electrical role (per STAR_IMPORT_SELECTION note) | Reference spatial domain(s) | Required ρ | Required c_p | Required K | Required interfaces | Heat-source role | Exact mapping? | STAR capability to test |
|---|---|---|---|---|---|---|---|---|---|
| Mandrel | none documented (likely core support, not in the Core/±Tab electrical minimal set) | 100% JR | 2660.7 | tabulated (980+3·ΔT) | (1.4,1.4,29) cylindrical | ideal to Jellyroll | none (JR is the only heated domain) | **YES** | Can a non-"Core Parts" solid be assigned Core/JellyRoll material in STAR's battery continuum, or does it need to be merged into the Core Part selection? |
| Jellyroll | Core Parts (per STAR_IMPORT note, hosts the distributed electrical mesh) | 100% JR | 2660.7 | tabulated (980+3·ΔT) | (1.4,1.4,29) cylindrical | ideal to Mandrel/Can/Cap-mapped bodies | **yes — full JR heat, uniform per OF `selectionMode all`** | **YES** | Confirm STAR's Core Part can carry an anisotropic cylindrical k tensor matching (1.4,1.4,29), not an isotropic default |
| Can | Thermal package/contact (STAR_IMPORT note item 4) — NOT sufficient alone for electrical closure | **CROSSES JR/Can/Cap/outside** (83.7%/9.7%/3.5%/3.2%) | **piecewise — see below** | piecewise | piecewise | ideal at JR-overlap sub-regions, ideal at Can/Cap boundary (z=65.34mm) | none | **CONDITIONAL** | Does STAR support per-region/per-face material split within one CAD body (piecewise assignment), or does the whole Can body have to carry one material? |
| +Ve Tab Root, +Ve Tab Stem, +Ve Washer, +Ve EndPlate, +Ve Internal-Post | + Tab Parts (electrically required) | 100% OF Cap (top end) | 1447.2 | 500 (const) | (0.01,0.01,0.1) cylindrical | ideal internal continuity (already OF-ideal at all 3 non-bottom interfaces) | none | **YES**, thermally — provided STAR allows a Cap-equivalent (near-insulating, k_z=0.1 W/mK) thermal material on parts that must remain electrically conductive (copper/steel tab & post) | **This is the central Test B/Test C question**: can a part keep its electrical conductor role while its *thermal* conductivity is forced down to 0.1 W/mK axial / 0.01 radial? If STAR ties electrical and thermal material together, this fails and requires option C or D below. |
| -Ve Tab Root | − Tab Parts (electrically required) | 100% OF Can (thin bottom wall) | 8000 | 500 (const) | 16 isotropic | ideal to Can | none | **YES**, thermally, same conditional as above | same electrical/thermal decoupling question |
| -Ve Tab Stem, -Ve Washer, -Ve EndPlate, -Ve Internal-Post | − Tab Parts (electrically required) | **84–100% OUTSIDE all 3 OF domains** (bottom-end hardware OF does not resolve) | **undefined by the OF reference model** — no domain exists there | undefined | undefined | must reduce to the OF JR↔Can-bottom thin-layer contact resistance model, not a solid domain | none | **NO, not as a direct 1:1 volume mapping** | See resolution options below — this is the highest-risk unresolved item |

## Can body — required piecewise split (detail)

Per `CAN_CAP_REDUCTION_DECISION.md` (EXACT PIECEWISE UNION SUPPORTED), the single BDS `Can` solid must be split at z_of = 65.3413mm (JR-aligned) into two material zones if STAR supports piecewise assignment within one body:

- **z_of < 65.3413mm** (lower 92% of the body by length, containing the 9.67%-by-volume true Can-domain material plus the 83.7% that geometrically coincides with JR — see below): Can properties (ρ=8000, c_p=500, k=16 isotropic) for the true Can-domain sub-volume; **the JR-overlapping sub-volume within this same solid must NOT get Can properties** — it must get JR properties, because OpenFOAM treats that space as JellyRoll, not steel. This means the Can solid cannot be assigned a single material even within the Can-side split; it needs a **second** internal split isolating the JR-coincident portion.
- **z_of ≥ 65.3413mm** (top 8%): Cap properties (ρ=1447.2, c_p=500, k=(0.01,0.01,0.1)).
- **z_of < 0mm** (bottom hardware region, 3.2% by volume + the associated bottom EndPlate/Washer/Post/Tab bodies): no OF domain exists here at all — see resolution options below.

In practice this means the BDS `Can` body alone requires **three** distinct thermal zones to be an exact mapping (JR-equivalent, Can-equivalent, undefined/bottom-region), not one and not two. This is a materially harder STAR ask than a simple two-material piecewise union and must be tested explicitly (Test A in the qualification plan).

## Resolution options for the bottom-end ("outside-reference") bodies

The governing task defines six possible resolution categories (A–F). Applied here:

- **Option A (thermally split the BDS body at the OF domain boundary)**: not applicable in the same way as the Can body — there is no OF domain to split into on the bottom end; splitting doesn't create a target.
- **Option B (piecewise material within one body)**: not applicable for the same reason.
- **Option C (electrical geometry retained but thermally suppressed)**: plausible — assign the bottom Tab Stem/Washer/EndPlate/Internal-Post bodies a thermal material designed to reproduce the *aggregate* effect of OF's single thin resistive layer (i.e., make the whole stack behave, in bulk axial resistance, like the OF `thicknessLayers=6.015e-7m` contact layer) while leaving their electrical role untouched. This requires computing an equivalent lumped resistance for the stack and is the most promising option, but is a **derived approximation**, not an exact mapping, and must be labeled as such.
- **Option D (equivalent contact/interface treatment)**: closely related to C — insert an explicit interface thermal resistance between Can and Jellyroll at the bottom equal to OF's contact resistance, and suppress/insulate the intervening hardware (Internal-Post, Washer, Tab) so they do not provide a parallel low-resistance path. This directly targets Key Finding 3 in the geometric audit (the confirmed Can→EndPlate→Post→Washer→TabStem→TabRoot→Jellyroll contact chain).
- **Option E (different BDS geometry)**: not pursued this run (governing task says not to regenerate client geometry unnecessarily).
- **Option F (approximate reduced-order calibration)**: fallback if C/D cannot be validated in STAR.

**Recommendation for the client test plan: attempt D first** (explicit interface resistance + suppression of the metallic bottom shortcut), since it directly targets the confirmed conduction-chain finding, is the closest in spirit to "no artificial geometry change," and is testable as a bounded STAR configuration question rather than a curve-fit.

## Volume-coverage caveat (from the capacitance audit)

`THERMAL_CAPACITANCE_AUDIT.csv` shows the OF Can and Cap domains are only 56.1% and 15.9% covered by any BDS solid material at all (not merely misassigned — genuinely unfilled/void in the BDS CAD at those locations). This is independent of the material-mapping question above: even with perfect piecewise assignment, the *mapped* thermal capacitance in the Can/Cap regions will undershoot the OF reference by ~44% and ~84% respectively unless this geometric void is separately addressed (e.g. confirming the correct radial/axial clearances per `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`, which this project has already been actively chasing via the JR-OD test pair in `NEXTSESSION`). This finding reinforces rather than duplicates that existing JR-OD work — it shows the same class of gap also affects the Can/Cap-side geometry, which had not previously been checked by exact B-Rep volume comparison against the OF reference.

## Overall answer: can an exact thermal mapping be constructed?

**CONDITIONAL.** JellyRoll (Mandrel+Jellyroll, 100% exact) and the top/+Ve hardware (100% exact subdivision of Cap) map exactly today. The Can body requires a 3-way piecewise split (untested in STAR). The bottom/−Ve hardware has no OF-domain target at all and requires an approximation (Option D recommended) rather than an exact reduction. Additionally, ~44–84% of the OF Can/Cap thermal mass is not represented by any BDS solid, a separate geometric-coverage gap that must be closed (or explicitly compensated) independent of material assignment.
