# Lumped CFD-ECM Forward Validation Plan

## Goal

Validate lumped CFD-ECM coupling with strict forward-only execution and targeted
retest-on-failure behavior.

## Forward-Only Rule

1. Run tests in this order only:
   - Test 1: ECM timestep convergence
   - Test 2: adiabatic energy balance
   - Test 3: mesh independence
   - Test 4: ECM zero-current equilibrium
   - Test 5: ECM fixed-current cadence and smoothness
2. If Test `N` fails:
   - stop at `N`
   - diagnose only `N`
   - patch only the failing path for `N`
   - rerun only `N` until it passes
3. Continue forward to `N+1` only after `N` passes.
4. Backward/stale reruns are allowed only after Test 5 completes.

## Default Settings

- Development diffusion cap: `maxDi = 100`
- Adiabatic analytic controls:
  - `h` relaxation forced to `1.0`
  - outer shell/cap boundaries forced to `zeroGradient`
- ECM tests:
  - persistent path kept enabled
  - explicit per-step ECM cadence forced (`--ecm-call-every-n-steps 1`)

## Pass Criteria

### Test 1: ECM timestep convergence
- Run `dt = 1.0, 0.5, 0.25 s`
- Compare final capacity-weighted `T` and final `Q_sum_check`
- Pass:
  - `|T(0.5)-T(0.25)| <= 0.2 K`
  - `|Q(0.5)-Q(0.25)| <= 0.25 W`

### Test 2: adiabatic energy balance
- Fixed volumetric source, no ECM
- Pass:
  - `|energy error| <= 2%`

### Test 3: mesh independence
- Coarse/medium/fine via block-count variants
- Compare final `Tmax(jellyRoll)`
- Pass:
  - `|Tmax(medium)-Tmax(fine)| <= 0.25 K`

### Test 4: ECM zero-current equilibrium
- ECM enabled, `current_A = 0`
- Pass:
  - `max |Q_sum_check| <= 0.5 W`
  - capacity-weighted temperature drift `<= 0.05 K`

### Test 5: ECM fixed-current cadence/smoothness
- ECM enabled, fixed current, per-step cadence
- Pass:
  - every solver step has `Q_sum_check`
  - no skipped ECM cadence markers (when present in log)
  - second-difference smoothness of `Q_sum_check`:
    `max |d2Q| <= 5 W`

## Deliverables

- Per-test logs under `artifacts/logs/`
- Per-test metrics JSON under
  `artifacts/validation/lumped_forward/<test>/`
- Forward campaign summary JSON and human-readable report

