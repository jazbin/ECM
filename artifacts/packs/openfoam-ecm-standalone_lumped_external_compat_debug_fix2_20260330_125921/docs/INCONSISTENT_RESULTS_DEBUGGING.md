# Inconsistent Results Debugging Framework

This document defines how inconsistent CFD/CHT results are handled in this
workspace.

Its purpose is to prevent expensive solver-code investigations when the real
problem is a cheap case-definition error such as:
- wrong boundary condition on disk
- inherited relaxation or solver settings
- source/reference mismatch
- stale copied case files
- a benchmark that is not physically what its name says it is

## Scope

Use this framework whenever one or more of the following happens:
- a result violates a basic physical expectation
- a validation benchmark disagrees with an analytic reference or dataset
- a code change appears to cause a large regression
- two nominally equivalent cases give materially different outcomes
- a report/plot contradicts the setup description

## Rule 1: Treat The Benchmark Definition As Suspect

Before suspecting solver code, assume the benchmark definition may be wrong.

A benchmark is not defined by its case name or the intent of the script. It is
defined by the files that are actually on disk at run time.

Never say:
- "this is an adiabatic case"

Until the following have been checked in the actual case directory:
- outer thermal BCs
- source terms and magnitudes
- region-level `fvSolution`
- region-level `fvSchemes`
- enabled/disabled coupling/functionObjects

## Rule 2: Always Start With Cheap Checks

These checks are mandatory before any deep debugging:

1. Boundary-condition check
- Read the actual `0/<region>/T` files.
- Confirm that the external walls match the stated benchmark:
  - adiabatic: `zeroGradient`
  - fixed ambient: `fixedValue`

2. Solver-controls check
- Read region `system/<region>/fvSolution`.
- Check:
  - `relaxationFactors`
  - solver type
  - `nNonOrthogonalCorrectors`
  - any region-local overrides that can change physics or convergence behavior

3. Source-term check
- Read the applied source definition.
- Confirm:
  - sign
  - magnitude
  - targeted region/cellZone
  - coupling enabled/disabled state

4. Reference-definition check
- Confirm the analytic or dataset reference corresponds to the exact simulated
  system.
- Example:
  - do not compare to an adiabatic analytic formula if the case has fixed
    external temperature boundaries

5. Run-hygiene check
- Confirm the run is using the intended fresh case state.
- Check for:
  - copied stale `0/` files
  - stale time directories
  - stale postProcessing outputs
  - run scripts that overwrite local edits

These checks are cheap and should usually take minutes, not hours.

6. Execution-path check
- Confirm how the solver was launched:
  - direct shell run
  - harness/helper `_run()` wrapper
  - `Allrun`/`Allrun.pre`
- Record any environment setup performed by the launch path:
  - sourced bashrc files
  - overridden `FOAM_*` variables
  - overridden `PATH` / `LD_LIBRARY_PATH`
- If two nominally equivalent runs disagree, rerun the exact same case once
  directly from the shell and once through the harness path before suspecting
  physics or solver code.

7. Runtime-state check
- Confirm cloned/generated cases are not inheriting runtime artifacts:
  - `ecm_state.json`
  - `ecm_last_good.bin`
  - `artifacts/runtime/*`
  - stale `dynamicCode/`
- If the harness creates working copies, the cleanup rules must be explicit and
  verifiable.

## Rule 3: Use The Isolation Ladder

If the cheap checks pass and the inconsistency remains, debug in this order:

1. Single-region control case
- Remove interfaces.
- Keep the same source and material model if possible.
- Purpose:
  - isolate source insertion and thermo conversion

2. Zero-source control case
- Expected invariant:
  - temperature remains constant

3. Source-only adiabatic control case
- Expected invariant:
  - total stored energy matches injected energy

4. Linear-scaling control case
- Example:
  - 50 W vs 25 W should give a 2x temperature-rise ratio in a linear setup

5. Patch/boundary swap case
- Replace custom boundary conditions with the closest stock OpenFOAM version
- Only after cheaper controls have passed

6. Launch-path comparison
- Run the exact same generated case through:
  - direct shell invocation
  - harness invocation
- If the results diverge, stop and debug the harness/execution path before
  changing model or solver code.

7. Coupling-mode comparison
- explicit vs implicit
- coupled vs uncoupled
- wrapper disabled vs enabled

8. Solver-code inspection
- Only after the case definition and reduced controls are clean

## Rule 4: Track Invariants, Not Just Temperatures

Every inconsistent-result investigation must write down the relevant
conservation or sanity invariant.

Typical invariants:
- Energy:
  - injected `Q * t`
  - stored `sum(m Cp DeltaT)`
- Zero-source equilibrium:
  - no drift
- Symmetry:
  - symmetric setup should remain symmetric
- Linearity:
  - doubling source doubles response in linear problems
- Monotonicity:
  - positive heating should not reduce temperature in adiabatic conditions
- Execution equivalence:
  - direct-run and harness-run results for the same generated case should match
    to numerical tolerance

If no invariant is stated, the debug is underspecified.

## Rule 5: Escalation Criteria

Escalate from "case/setup issue" to "solver/code issue" only if all of the
following are true:

- benchmark definition has been re-read from actual case files
- cheap checks are documented
- at least one reduced control case has been run
- direct-run vs harness-run comparison has been checked when a harness is involved
- the reduced control still fails
- the invariant is clearly stated

If these conditions are not met, do not open a solver-code investigation yet.

## Required Investigation Record

For every inconsistent-result investigation, record:

1. Stated expectation
- What should have happened?

2. Observed result
- What actually happened?

3. Benchmark definition on disk
- Key BCs
- source settings
- solver settings

4. Cheap checks completed
- pass/fail list

5. Reduced control cases run
- case name
- purpose
- outcome

6. Current conclusion
- setup issue
- harness issue
- execution-path issue
- plotting/postprocessing issue
- solver issue
- unresolved

## Common Pitfalls Checklist

These are recurring, high-probability causes and should be checked first:

- Wrong external thermal BC for the named benchmark
- Hidden region-local `fvSolution` overrides
- Under-relaxation present during analytic validation
- Source sign error
- Source applied to wrong field or wrong zone
- Copied case drifting from harness intent
- Harness `_run()` or launch wrapper changing the OpenFOAM environment
- Manual run and harness run using different execution paths
- Generated case identical on disk, but runtime behavior differs due to launch path
- Stale time directories or plots
- Stale runtime state (`ecm_state.json`, `ecm_last_good.bin`, `artifacts/runtime`)
- Comparing against the wrong reference quantity
- Assuming a case is adiabatic/fixed-ambient/lumped/distributed without reading
  the files

## What This Framework Changes

From now on:
- benchmark-definition checks happen before solver-code suspicion
- cheap checks are mandatory, not optional
- single-region and zero-source controls are standard first-line tools
- validation harnesses must actively enforce their benchmark assumptions
- validation harnesses and shared run helpers are treated as part of the
  validated system, not as neutral plumbing
- any harness-based discrepancy must be checked against a direct shell rerun of
  the exact same generated case

## Minimal Example

If an "adiabatic fixed-power" benchmark under-heats:

1. Read `0/shell/T` and `0/cap/T`
2. Read `system/<region>/fvSolution`
3. Confirm the source magnitude and zone
4. Run a one-region adiabatic control
5. Only then investigate multi-region coupling or solver code

This order is mandatory because it is cheaper and more reliable than starting
with solver internals.
