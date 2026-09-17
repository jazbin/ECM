# STAR-CCM+ Client Equivalence Qualification Test Plan

**Date:** 2026-09-17
**Depends on:** `SOURCE_INVENTORY.md`, `OPENFOAM_THERMAL_OPERATOR_INVENTORY.md`, `CAN_CAP_REDUCTION_DECISION.md`, `T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`, `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`.
**Geometry:** known-good T06 (`T06_TARGET_AXIAL_SURPLUS_2p00.step` / `.tbm`), unchanged.

This is requested as **one structured client interaction** (Robert), run in STAR-CCM+ against the T06 import, covering Tests A–D in order — do not proceed to a later test until the prior one passes.

## Phase 6 note — pure-thermal OpenFOAM reference experiment

A candidate case already exists in-repo: `cases/wedge_2170_constant_heat_rtherm` — same 3-region geometry/materials as the production reference, constant volumetric heat source (150000 W/m³, uniform in JellyRoll, via `scalarSemiImplicitSource`, no ECM coupling) — structurally exactly what Phase 6 asks for. However:

- Its base-contact resistance (`thicknessLayers=1.804785e-3 m`) differs from the current production case's near-ideal value (`6.015e-7 m`), so it is not a same-topology drop-in; it represents an intentionally-resistive bottom contact, useful as a secondary sensitivity case but not the primary "ideal contact" reference.
- The existing `postProcessing/jellyRoll_rotated/jellyRollMeanT` result files for this case and for the production `wedge_2170` case are byte-identical despite the different configurations — indicating stale/copied data. **Neither is used here as validated transient evidence.**

**Recommended action (not executed this run — flagged as the exact next step, not fabricated):** re-run `cases/wedge_2170_constant_heat_rtherm` (or a clone with `thicknessLayers` restored to the production value `6.015e-7m` for topology parity) fresh, confirm `postProcessing` is regenerated (not stale), and use its `T_JR_mean(t)`, `T_JR_max(t)` histories plus the same probes in STAR as the Test A comparison baseline. Exact commands:

```bash
cd cases/wedge_2170_constant_heat_rtherm
rm -rf postProcessing 100 200 300 400 500 processor*   # keep 0/, constant/, system/, ecm/
./Allrun   # or the OpenFOAM run command already used in this case (see run.log for the prior invocation)
```

Common probe definitions (physical coordinates, JR-aligned OpenFOAM z frame, mm): JR centerline z=32.79 (mid-height) r=0; JR outer edge z=32.79 r=10.31; Can outer wall z=32.79 r=10.545; Cap top-center z=70.02 r=0. Use identical (r,z) probe locations in STAR.

## Test A — thermal operator only

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
