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

So the first client interaction is **Step 0 below only** — five direct
capability questions, no case setup required. Their answers determine
whether Test A's piecewise-mapping machinery is even necessary, and in what
form. Tests A–D remain specified below for when they're needed, but are
explicitly gated behind Step 0.

## Step 0 — STAR capability questions (ask this first, nothing else)

1. How does STAR actually treat the overlapping BDS "Can" when `Create from Tbm` creates the battery model?
2. Which of the 13 Parts become actual thermally meshed solid volumes/Regions?
3. Are overlaps boolean-resolved automatically?
4. Can Core/+Tab/−Tab electrical assignments remain intact while thermal material/continuum assignments are changed?
5. Can auxiliary electrical parts be excluded from Energy, or otherwise prevented from creating conductive thermal paths?

No case run is required to answer these — they are about what `Create from
Tbm` does and what the resulting Region/continuum tree looks like, inspectable
directly in STAR's part/region browser. **Only after these are answered** do
we know whether Test A's Can 3-way split and Option D bottom-interface
surrogate are actually needed, or whether STAR's own Region construction
already does something equivalent (or something that makes the whole
piecewise-mapping question moot).

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
