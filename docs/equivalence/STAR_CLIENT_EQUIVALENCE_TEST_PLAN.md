# STAR-CCM+ Client Equivalence Qualification Test Plan

**Date:** 2026-09-17, restructured 2026-09-18.
**Depends on:** `SOURCE_INVENTORY.md`, `OPENFOAM_THERMAL_OPERATOR_INVENTORY.md`, `CAN_CAP_REDUCTION_DECISION.md`, `T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`, `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`, `OPENFOAM_REFERENCE_RESOLUTION_20260918.md`.
**Geometry:** known-good T06 (`T06_TARGET_AXIAL_SURPLUS_2p00.step` / `.tbm`), unchanged.

## Sequencing — read this first

Do **not** open with Test A. Test A presupposes a complicated three-way Can
material split and a bottom-resistance surrogate — both of which may turn out
to be unnecessary, or may not even be things STAR can do, depending on how
STAR's `Create from Tbm` actually treats the 13 overlapping BDS bodies when it
builds Parts and Regions. We proved (via exact B-Rep boolean intersection,
`T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`) that the STEP solids themselves overlap;
we have **not** established that STAR's own Parts→Regions construction
preserves that overlap, resolves it automatically, or exposes it to the user
at all. **Do not assume the returned STEP decomposition is automatically
identical to STAR's final thermal computational decomposition.**

So the first client interaction is the **STAR Capability Gate — S0**, below.
Its answers determine whether Test A's piecewise-mapping machinery is even
necessary, and in what form. Tests A–D remain specified below for when
they're needed, but are explicitly gated behind S0 passing/informing the
approach.

**Workflow constraint (confirmed 2026-09-18): only Robert has STAR-CCM+
access.** Bojan does not have a local STAR install. All S0 evidence must
therefore be gathered from a single self-contained package sent to Robert
and the package/`.sim`/screenshots he returns — see
`artifacts/equivalence/robert_s0/`. No assumption should be made that Bojan
can perform additional STAR-side inspection locally, now or as a followup;
any further STAR-side question must go through another Robert round-trip
package, not local access.

## S0 — STAR Capability Gate

Confirmed already (do not re-ask Robert): STAR's `Create from Tbm` creates a
separate Part and Region for each of the 13 imported BDS bodies.

Four tests, all performed by Robert in one session against the known-good
T06 geometry, unmodified:

- **S0-A — Region geometry / overlap resolution.** Does STAR's computational
  Region geometry retain the overlapping solids present in the exported BDS
  STEP, or does it clip/boolean-resolve them? Evidence: per-Region and (if
  exposed) per-Geometry-Part volumes for at least Can/Jellyroll/Mandrel/
  EndPlates/Internal-Posts, plus one centerline axial section view.
- **S0-B — Region interfaces / contact topology.** What interfaces/contacts
  did STAR actually build between neighbouring Regions along the confirmed
  Can→EndPlate→Post→Washer→TabStem→TabRoot→Jellyroll contact chain
  (`T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`)? Inspected directly in STAR's
  Interfaces tree, not inferred from geometry.
- **S0-C — Two-part thermal capability check.** C.1: Can STAR assign an anisotropic thermal conductivity tensor (independent kr, kθ, kz) in a cylindrical coordinate frame to a solid Region inside a battery model? Required for Jellyroll (MAT-006: kr=1.4, kθ=1.4, kz=29 W/m·K) and Cap-equivalent region (MAT-012: kr=0.01, kθ=0.01, kz=0.1 W/m·K). Checked by inspecting the material model options for the Jellyroll Region — no material change required. C.2 (unchanged): Can a Region (test case: `+Ve Tab Stem`) keep its electrical role (Core/+Tab Parts, valid Battery Cell/Unit Cell Model) while its thermal material is changed independently to an extreme test value?
- **S0-D — Electrical role vs. thermal path suppression.** Building on S0-C: can a Region's thermal *path* be suppressed (low-k, Energy-model exclusion, uncoupled interface, or explicit interface contact resistance) while its electrical role remains intact? Four mechanisms (D1–D4), each checked independently. **Test Region is `−Ve Tab Stem`** (the negative/bottom electrical path) — not `+Ve Tab Stem`. D4 records the exact STAR model name, input units, and quantity type (area-specific resistance, total resistance, conductance per area, or thickness/conductivity pair) for the explicit contact resistance mechanism.

Full instructions, exact return template, and screenshot checklist are in
`artifacts/equivalence/robert_s0/README_FOR_ROBERT.md`,
`ROBERT_RETURN_TEMPLATE.md`, and `SCREENSHOT_CHECKLIST.md`. The packaged ZIP
for sending to Robert is `out/ROBERT_STAR_S0_QUALIFICATION_20260917.zip`
(contains the README, template, checklist, and the exact known-good T06 TBM
— see `artifacts/equivalence/robert_s0/T06_INPUT_PROVENANCE.md` for its
provenance/SHA256).

Robert is asked only to perform actions, take measurements, make one small
material change (S0-C) and one small thermal-path capability test (S0-D),
and return evidence — not to interpret results, compare against OpenFOAM, or
do any of Test A–D's setup. Interpretation of the returned S0 evidence, and
the decision of which of Test A–D (and in what form) is actually needed,
happens on this side after Robert's package comes back.

**Only after S0's answers come back** do we know whether Test A's Can 3-way
split and Option D bottom-interface surrogate are actually needed, or
whether STAR's own Region construction already does something equivalent
(or something that makes the whole piecewise-mapping question moot).

## Phase 6 note — pure-thermal OpenFOAM reference experiment

A clean, non-stale pure-thermal reference case now exists at
`cases/wedge_2170_thermal_qualification` (cloned from the authoritative
production case, `docs/equivalence/OPENFOAM_REFERENCE_RESOLUTION_20260918.md`):
same 3-region geometry/materials, same near-ideal bottom contact
(R≈1.8mΩ·K/W), 100% Q→JellyRoll heat source (150000 W/m³, uniform, via
`scalarSemiImplicitSource`, no ECM coupling), single continuous run (no
restart chain) with the heat pulse switched off via `timeActivatedFileUpdate`
at t=100s, total duration 300s. This supersedes the earlier
`cases/wedge_2170_constant_heat_rtherm` candidate (that case's
`thicknessLayers=1.804785e-3m` bottom contact was found to be a stale,
abandoned calibration variant, not the production reference — see the
resolution doc). Use its exported CSVs (JR mean/max T, radial/axial probes,
Can/top-end/bottom-end T, total stored energy, total boundary heat loss) as
the Test A/D comparison baseline once Step 0's answers make clear which test
is actually needed.

Common probe definitions (physical coordinates, JR-aligned OpenFOAM z frame, mm): JR centerline z=32.79 (mid-height) r=0; JR outer edge z=32.79 r=10.31; Can outer wall z=32.79 r=10.545; Cap top-center z=70.02 r=0. Use identical (r,z) probe locations in STAR.

## Test A — thermal operator only (gated behind Step 0 — do not run first)

Using the T06 geometry, unmodified:

1. Preserve geometry as-is.
2. Disable/avoid ECM heat generation.
3. Apply the BDS→OpenFOAM thermal material mapping from `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`:
   - Mandrel, Jellyroll → JR properties (ρ=2660.7, c_p tabulated 980+3·ΔT, k=(1.4,1.4,29) cylindrical).
   - +Ve Tab Root/Stem, +Ve Washer, +Ve EndPlate, +Ve Internal-Post → Cap properties (ρ=1447.2, c_p=500, k=(0.01,0.01,0.1) cylindrical).
   - −Ve Tab Root → Can properties (ρ=8000, c_p=500, k=16 isotropic).
   - Can body → **3-way piecewise split** per the mapping doc (JR-equivalent sub-volume / Can-equivalent sub-volume / Cap-equivalent sub-volume at z_of=65.3413mm), if STAR supports it. **If STAR does not support intra-body piecewise material assignment, this is a hard STOP — report the exact restriction and do not substitute a single averaged material (that would silently violate `CAN_CAP_REDUCTION_DECISION.md`'s "no approximate homogenization" finding).**
   - −Ve Tab Stem, −Ve Washer, −Ve EndPlate, −Ve Internal-Post → apply Option D from the mapping doc: explicit interface thermal resistance between Can and Jellyroll at the bottom, sized to reproduce OF's `thicknessLayers=6.015e-7m`/`kappaLayers=1` contact layer, with these bodies' own conductivity suppressed enough that they do not provide a parallel low-resistance shortcut (per the confirmed Can→EndPlate→Post→Washer→TabStem→TabRoot→Jellyroll contact chain in `T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`).
4. Make all internal interfaces within a single mapped-material region ideally coupled (zero resistance), matching the OF reference's 3-of-4 ideal interfaces.
5. Impose the known heat pulse used by the OpenFOAM reference experiment (150000 W/m³ uniform in the JR-mapped volume only — Can/Cap-mapped volumes get zero direct heat, per the confirmed OF heat-source wiring).
6. Impose the same external BCs: h=160 W/m²K, T_amb=298.15K on both the Can-mapped and Cap-mapped exposed outer surfaces.
7. Run transient thermal solve, matching the OF `endTime`/step used in the regenerated reference run.

### Required exports/screenshots
Region tree; Parts tree; continua/material assignments; Multi-Part Solid/component assignments if applicable; interfaces/contact definitions (including the new bottom interface resistance); mesh; temperature scenes; report histories; global energy balance. CSV histories for T_JR_mean(t), T_JR_max(t), the 4 probe locations above, T_can(t), T_end(t) (both ends, to directly test the asymmetry finding), stored thermal energy, boundary heat rejection.

### PASS condition
`STAR response matches OpenFOAM within the agreed model-equivalence tolerance after accounting for OpenFOAM mesh/time-step numerical uncertainty.` No arbitrary tolerance is hard-coded here — the project has not established that number in the repository. Compare full transient response (not just final T), and separately compare the two cell ends (top vs bottom) given the confirmed asymmetric-geometry finding.

If Test A passes, the 13-body geometry has been demonstrated thermally equivalent despite its different CAD decomposition — **conditional on** the Can piecewise-split and bottom-interface-resistance techniques both being available in STAR (open STAR-capability questions, see below).

## Test B — preserve electrical roles with remapped thermal behaviour

Same cell, same thermal mapping as Test A retained. Re-enable native battery/electrical setup (Core Parts = Jellyroll/Mandrel, + Tab Parts = +Ve chain, − Tab Parts = −Ve chain, per `STAR_IMPORT_SELECTION_ELECTRICAL_BEHAVIOR_NOTE_20260910.md`).

**Central question:** can a tab/post/washer/endplate retain its required electrical role (conductor, part of the Tab Parts assignment) while its *thermal* material/interfaces represent the OF-equivalent material at that location (near-insulating Cap material for the top stack, suppressed/resistance-only for the bottom stack)? This is the single most important open STAR-capability question raised by this analysis (identified in `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`).

Capture: Core Parts, + Tab Parts, − Tab Parts, Unit Cell Model, electrical mesh, thermal material/component mapping.

**PASS:** electrical object remains valid; electrical mesh remains valid; thermal material remapping is retained (not silently reverted to native BDS thermal defaults); short native battery solve runs without invalidating the cell.
**FAIL:** document the exact STAR restriction/error and the exact failing body/property relationship.

## Test C — distributed RCR semantics

Only after Test B passes. `IET = RCRTable 3D`, `Thermal = Distributed`, `m_bOnly1D = 0` (per the protected parameters in `NEXTSESSION`). Create a strong JellyRoll temperature gradient (e.g. ~288K at one probe, ~308K at another — matching the project's existing 288.15/298.15/308.15K RCR temperature sets). Apply a pulse/rest current profile (the existing `cases/wedge_2170/constant/electrical_inputs_from_validation.csv` profile is a ready-made candidate — same current history already used in the OF reference, enabling direct Test D comparison later).

Request local SOC, local current, local RCR state, local polarization response, local ecell contribution, local heat — for at least two spatially separated JR locations.

**PASS** requires T_A ≠ T_B **and** electrical_state_A(t) ≠ electrical_state_B(t) **and** q_A(t) ≠ q_B(t) simultaneously, within one physical jellyroll. Differing temperature alone is not sufficient.

## Test D — full coupled comparison

Only after A–C pass. Same I(t) (`electrical_inputs_from_validation.csv`), SOC0, T0=298.15K, thermal BCs as the OpenFOAM–ECM reference. Compare terminal voltage, SOC, total electrical heat, coarse-grained spatial heat, JR mean/max, radial/axial probes, Can/end temperature (both ends), energy balance. At minimum: (1) constant-current case, (2) the pulse/rest case from the CSV already in use.

## Consolidated list of open STAR-specific questions this plan generates

1. Does STAR support intra-body piecewise material assignment (Can body needs 3 zones)?
2. Does STAR support an explicit added interface thermal resistance at a specific internal face (for the bottom Can↔JR contact-resistance reproduction)?
3. Can a part remain in the electrical Core/Tab Parts assignment while carrying non-default (Cap-equivalent, near-insulating) thermal conductivity?
4. Does suppressing/insulating the bottom Internal-Post/Washer/Tab stack (to remove the confirmed metallic shortcut) disturb the required electrical continuity of the − Tab Parts path?

None of these are answerable from the repository alone — they require the actual STAR session, which is the explicit purpose of this test plan.
