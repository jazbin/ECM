# Acceptance tests

## Development validation gate: lumped CHT

For routine development on the lumped solver/ECM path, the default validation
gate is intentionally small and fast:

1. Time-step independence
- Run the lumped ECM-enabled case at three fixed time steps.
- Compare final `Q_sum_check` and final capacity-weighted temperature.

2. Energy balance
- Run the corrected adiabatic fixed-power control case.
- Verify stored thermal energy matches injected energy.

3. Mesh independence
- Run the corrected adiabatic fixed-power control case on coarse/medium/fine
  isotropic meshes.
- Compare final capacity-weighted temperature and convergence toward the
  analytic solution.

These three checks are the default development gate because they are standard,
cheap, and high-value.

## Extended pre-release sanity suite

These are recommended before major releases or after substantial solver/model
changes, but they are not required for every development iteration:
- zero-source equilibrium at multiple initial temperatures
- source scaling over more than two power levels
- symmetry/invariance checks for symmetric setups
- interface continuity checks (temperature jump and flux mismatch)
- boundary-condition limiting cases (very high/very low external `h`)
- material-parameter sensitivity checks (`rho`, `Cp`, `k`)

## Verification ladder and artifacts

Run tests bottom-up (static checks, build/smoke, short cases, then parallel) and
capture outputs in `artifacts/` when possible. Update `STATUS.md` with pass/fail
and log user-visible changes in `artifacts/logs/change.log`.

All acceptance tests must produce a run passport:
- `run_passport.json`
- `metrics_timeseries.csv`
- `log.<solver>` and `log.checkMesh`

Use `tools/run_passport.sh <case_dir> <solver>` or equivalent CI steps.

## Test 1 — Serial end-to-end
- Build library: `./Allwmake`
- Run: `cd cases/scalarTransport_ecm; ./Allrun`
- Verify:
  - `postProcessing` or time directories include `ecmQdot` and `ecmST`
  - Temperature field changes over time (non-zero source)
  - Run passport metrics pass thresholds in `tools/metrics_config.json`

## Test 2 — Parallel masterGather
- `cd cases/scalarTransport_ecm`
- `./Allrun -parallel`
- Verify:
  - consistent `ecmQdot` pattern across decomposed domains
  - no multiple ECM invocations per rank (only master calls external process)

## Test 3 — CHT case (chtMultiRegionSimpleFoam)
- `cd cases/chtMultiRegionSimpleFoam_ecm`
- `./Allrun`
- Verify:
  - `solid` region writes `ecmQdot` and `ecmST`
  - temperature field changes over time in the solid region
  - energy balance and coupling metrics pass the run passport thresholds

## Test 4 — CHT case parallel (masterGather)
- `cd cases/chtMultiRegionSimpleFoam_ecm`
- `./Allrun -parallel`
- Verify:
  - `solid` region fields written in latest time
  - no multiple ECM invocations per rank (only master calls external process)

## Test 5 — Missing ECM output
- Temporarily rename `ecm/ecm_coupler.py` to break execution
- Run one timestep
- Verify:
  - OpenFOAM warns and continues
  - `ecmQdot` remains from previous values (or zero on first step)

## Test 5b — Missing output limit
- Set `missingOutputLimit 2;` and `missingOutputAction degraded;`
- Break ECM output for two consecutive steps
- Verify:
  - warning indicates degraded mode after the limit
  - simulation continues with previous `ecmQdot`
- Repeat with `missingOutputAction fatal;` and confirm abort on the limit

## Test 6 — Key mismatch
- Modify external script to drop one key
- Verify:
  - warning about missing key
  - other keys still mapped correctly

## Test 6b — StepId mismatch
- Modify external script to return a mismatched `stepId`
- Verify:
  - warning about stepId mismatch
  - `ecmQdot` remains at previous values

## Test 7 — Lumped coupling mode
- Update a case to set:
  - `couplingMode lumped`
  - `lumpedOutput volumetric` (with the mock ECM)
- Run a few steps
- Verify:
  - `ecmQdot` is uniform over the coupled region
  - `ecmST` updates consistently
  - only a single record is written to `ecm_in.bin`/`ecm_out.bin`

## Test 7b — Lumped mode temperature selection
- Set `tEffMode coreWeighted` and `tEffMode sensorEmulation`
- Verify:
  - warnings appear if `sensorZone` is missing
  - `ecm_in.bin` contains a single temperature per step
  - changes in `tEffMode` affect the logged `Q_sum_check` trends

## Test 7c — Adaptive relaxation
- Set `adaptiveRelaxation true` and provide `alphaMin/alphaMax` and thresholds.
- Verify:
  - `alpha_used` is logged each execute step
  - `alpha_used` decreases on large `deltaT` or `deltaQ`

## Test 7d — Axial heat distribution (single ECM)
- Set `axialProfile linear` with `axialBias` != 0.
- Verify:
  - `ecmQdot` varies along the axial direction
  - `Q_sum_check` remains consistent with `Q_total`

## Test 8 — ECM voltage response validation (external ECM)
- For each temperature setpoint (10, 20, 30, 40, 50, 60 C), hold the CFD domain at a constant temperature boundary.
- Run the ECM with a defined current profile and compare returned voltage against the reference dataset.
- Verify:
  - voltage error is within the acceptance tolerance across all setpoints
  - the ECM state is advanced once per CFD timestep (no skipped/duplicated steps)

## Test 9 — Dataset validation: TU Berlin 21700 (internal + surface T)
- Source: `externalInputs/datasets/berlin_2026_bitstream_ae2d5a48.zip`
- Map:
  - Use measured current profile as ECM electrical input(s).
  - Use measured internal temperature to drive ECM thermal state (lumped mode) or as uniform T over the coupled zone.
  - Compare simulated surface temperature to measured surface T.
- Tooling:
  - `tools/validation/tu_berlin_validate.py` (compare sim vs measured CSV)
- Verify:
  - voltage RMSE <= 0.05 V (target 0.02-0.05 V)
  - surface temperature error <= 2 C at moderate C-rates
  - integrated heat vs. temperature rise consistent within ~5%

## Test 10 — Dataset validation: Khan et al. high-power (OSF)
- Source: `externalInputs/datasets/khan_2025_osf_Dataset_Molicell_P42A.zip`
- Map:
  - Use chamber temperature (5/25/40 C) as boundary.
  - Use current pulses and discharges for ECM electrical inputs.
  - Compare simulated surface temperature to Aux_Temperature.
- Verify:
  - voltage error <= 0.05 V across C-rates
  - peak surface temperature error <= 2 C
  - energy balance within ~5%

## Test 11 — Dataset validation: Stanford (Mendeley Data)
- Source: `externalInputs/datasets/stanford_2021_mendeley/`
- Map:
  - Use discharge profiles at 0.2-4 C as ECM electrical inputs.
  - Use ambient temperature for boundary condition (25-40 C).
  - Compare simulated surface temperature to measured skin T.
- Verify:
  - voltage error <= 0.05 V
  - surface temperature error <= 3 C
