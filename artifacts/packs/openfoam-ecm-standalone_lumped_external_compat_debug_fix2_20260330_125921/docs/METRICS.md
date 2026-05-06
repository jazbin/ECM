# Run-Time Metrics and Balance Checks

This document defines the canonical metrics and thresholds used for run
passports. Every new feature or coupling change must update these thresholds
and the run-passport schema.

## Run passport outputs
- `run_passport.json`: machine-readable summary (schema in `tools/run_passport_schema.json`).
- `metrics_timeseries.csv`: long-form time series (time, metric_name, value).
- Raw logs: `log.<solver>` and `log.checkMesh`.

## Global metrics (all cases)
- `log_scan.fatal_or_nan`: hard fail if any of {`FOAM FATAL`, `Floating point exception`, `nan`, `inf`} appear.
- `residuals.max_initial`: record max initial residual per equation.
- `continuity.global_abs_max`: max absolute global continuity error (if present).
- `courant.max`: max Courant number (if present).
- `temperature.min` / `temperature.max`: min/max T across regions (from `fieldMinMax`).

## Energy balance metrics (thermal cases)
- `energy.solid.E`: total stored energy in solid (J).
- `energy.solid.dEdt`: time derivative (J/s).
- `energy.solid.Qsrc`: volumetric source sum (W).
- `energy.solid.QfluxOut`: net conductive flux out (W).
- `energy.solid.residual`: `dEdt - (Qsrc - QfluxOut)` (W).

## Coupling metrics (ECM ↔ OF)
- `coupling.Q_sum_check`: solver-reported total applied power (W).
- `coupling.Q_integral`: `volIntegrate(solid) of ecmQdot` (W).
- `coupling.power_mismatch_rel`: `abs(Q_sum_check - Q_integral)/max(abs(Q_sum_check), eps)`.
- `coupling.interface_flux_sum`: `sum(solid_to_fluid) of wallHeatFlux` (W).

## Thresholds by case
Thresholds are defined in `tools/metrics_config.json`. Update these when
physics or mesh changes.

### cases/chtMultiRegionSimpleFoam_ecm
- `temperature.min >= 200 K`
- `temperature.max <= 400 K`
- `continuity.global_abs_max <= 1e-6`
- `courant.max <= 5`
- `energy.solid.residual_rel <= 0.05` (steady-state tolerance)
- `coupling.power_mismatch_rel <= 0.05`

### cases/scalarTransport_ecm
- `temperature.min >= 200 K`
- `temperature.max <= 400 K`
- `courant.max <= 5`
- `coupling.power_mismatch_rel <= 0.05`

## CI hard-fail rules
- Any `log_scan.fatal_or_nan` true.
- `checkMesh` reports failed mesh quality.
- Any metric exceeds its threshold in `tools/metrics_config.json`.
