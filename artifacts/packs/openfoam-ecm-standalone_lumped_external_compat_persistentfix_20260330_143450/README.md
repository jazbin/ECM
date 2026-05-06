# OpenFOAM ↔ ECM (black-box) temperature → heat coupling (Codex package)

This package implements timestep-level **weak two-way coupling** for OpenFOAM:

- OpenFOAM provides temperature data `T_mesh[i]` over an **active cellZone** (these are CFD *mesh cells*)
- External ECM executable (black box) is assumed to represent a *battery cell* (or module) and returns a **volumetric heat source** `qVol[i]` (W/m^3) keyed by *mesh-cell* IDs
- OpenFOAM writes the returned field as a `volScalarField` and can apply it as a source term (via `fvOptions` template)

The coupling is implemented as an OpenFOAM **functionObject** (`ecmCoupler`) compiled into:
`libecmCouplingFunctionObjects.so`

The external ECM side is represented by a Python mock (`ecm/ecm_coupler.py`) that reads/writes the binary protocol.

## Terminology (important)

- **Battery cell**: the physical electrochemical unit with a single electrical state (SOC/RC/hysteresis) handled inside the ECM.
- **Mesh cell**: an OpenFOAM finite-volume control volume. This package exchanges data per *mesh cell* inside a selected `cellZone`.
- The ECM is **not** instantiated per mesh cell. The ECM is *one black box per battery cell (or module)* and may accept a temperature vector and return a spatial heat distribution over mesh cells.

## What you get

- `src/` : OpenFOAM functionObject implementation (C++)
- `cases/` : minimal example case (`scalarTransportFoam`) demonstrating the pipeline
- `ecm/` : external mock ECM executable (Python) + binary IO parser
- `docs/` : IO protocol, integration contract, acceptance tests
- `AGENTS.md` : Codex task plan for iterative development

## Coupling level

This is **weak two-way coupling** (explicit/staggered) executed once per timestep:
`T -> ECM -> q -> thermal step`.

Upgrade to strong coupling (sub-iterations per timestep) only if you observe oscillations/divergence.

## Build

From the package root:

```bash
./Allwmake
```

This builds `libecmCouplingFunctionObjects.so`.

## Run the example

```bash
cd cases/scalarTransport_ecm
./Allrun
```

The example:
- builds a simple block mesh
- runs `scalarTransportFoam`
- calls the ECM coupler each timestep
- writes `ecmQdot` (W/m^3) and `ecmST` (K/s) fields

## Run the CHT example

```bash
cd cases/chtMultiRegionSimpleFoam_ecm
./Allrun
```

The CHT example:
- builds a two-region block mesh and splits regions
- runs `chtMultiRegionSimpleFoam`
- applies the ECM heat source in the solid region

## Notes / assumptions

- **Serial works out of the box.**
- For **parallel**, `parallelMode masterGather` is provided:
  it assigns stable **global mesh-cell IDs** using `globalIndex`, gathers temperatures to master,
  runs ECM once, broadcasts `q` back, and maps to local cells.
- The example uses a template `fvOptions` codedSource to apply `ecmST` to the `T` equation.
  For real solvers (compressible / CHT), you may instead apply `ecmQdot` to `he`/`h`/`e`
  or convert to an equivalent source as appropriate.

See `docs/INTEGRATION.md` for the recommended contract and mapping strategy.

## Reporting

Use `tools/generate_lumped_report.py` to produce the default project run report
template (summary + Tavg/Q_sum_check/section plots). The script supports any
case via `--case` and names outputs using the case directory by default.

## Operating rules and logs

This workspace follows the process in `MY_CODEX_BEST_PRACTICES_RULES.txt`.

- Current work state: `STATUS.md` and `TODO.md`
- Assumptions register: `docs/ASSUMPTIONS.md`
- Logs: `artifacts/logs/session.log`, `artifacts/logs/decision.log`,
  `artifacts/logs/blockers.log`, `artifacts/logs/change.log`

## Project governance

- Contributing guide: `CONTRIBUTING.md`
- License: `LICENSE`
- Changelog: `CHANGELOG.md`
- Best practices: `docs/OPENFOAM_BEST_PRACTICES.md`
