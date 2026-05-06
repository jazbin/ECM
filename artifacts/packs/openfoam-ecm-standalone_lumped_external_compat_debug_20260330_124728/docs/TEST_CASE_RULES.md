# Test Case Rules

These rules govern how test cases are prepared, modified, and run in this workspace.

## Mesh and Geometry Changes
- If a run script (e.g., `Allrun.pre`) calls `blockMesh`, any prior mesh transforms
  (e.g., `transformPoints -allRegions`) will be overwritten.
- If you need to scale or modify geometry, choose one of these approaches:
  - Edit `system/blockMeshDict` and regenerate the mesh, OR
  - Skip mesh regeneration in the run script after a one-time build.
- Always verify the active mesh extents before running a case after a geometry change.

## Tutorial Alignment
- Base each new CHT case on the simplest applicable OpenFOAM tutorial configuration.
- Before running, compare region setup, solver settings, and BC application to the
  reference tutorial and confirm any intentional deviations.

## Run Hygiene
- Ensure run scripts do not silently override requested changes (e.g., mesh rebuilds).
- Keep logs of key setup decisions and any deviations from tutorial patterns.
- Unless explicitly instructed otherwise, never start a new solver run until any previous solver processes are stopped.
- For any inconsistent or surprising result, follow `docs/INCONSISTENT_RESULTS_DEBUGGING.md` before escalating to solver-code debugging.
- If a case is launched through a shared helper or harness, the direct shell run of the exact generated case is the mandatory tie-breaker when results look inconsistent.
- After each test run, produce a complete assessment (stability, coupling behavior, key metrics, and any anomalies) and log it.
- After each test run, generate a PDF report using the project report template and record the report path in the assessment log.
- If `ecmCoupler` is configured, do not run the case unless the coupling library is present and loadable (fail fast).
- For `cases/lumped_solid`, always record interface temperature diagnostics (area-averaged `T` on jellyRoll↔shell and jellyRoll↔cap patches) each run.
