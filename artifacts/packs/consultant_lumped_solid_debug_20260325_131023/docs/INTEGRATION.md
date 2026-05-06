# Integration notes (OpenFOAM)

## Terminology

- **Battery cell**: physical electrochemical unit represented by the ECM (single electrical state on the ECM side).
- **Mesh cell**: OpenFOAM finite-volume cell. Data exchange is performed per mesh cell inside the selected `cellZone`.
- The ECM is **not** instantiated per mesh cell; it is one black box per battery cell (or module). The ECM may accept a temperature vector over mesh cells and return a spatial heat distribution.

## What the functionObject does

`ecmCoupler` runs on `executeControl` (typically `timeStep`):

1. Select coupled mesh cells from a `cellZone` (e.g. `activeZone`)
2. Extract `T_mesh[i]` over mesh cells (or another field) and write `ecm_in.bin`
3. Run external command (e.g. `python3 ecm/ecm_coupler.py`)
4. Read `ecm_out.bin` and map returned `qVol` to coupled cells
5. Update `volScalarField`:
   - `ecmQdot` (W/m^3)
   - optionally `ecmST` (K/s) if `outputMode temperatureSource`

### Lumped mode (single ECM call)
Set:
- `couplingMode lumped`
- `lumpedOutput totalPower` (ECM returns total heat [W]) or `lumpedOutput volumetric` (ECM returns qVol [W/m^3])
- `tEffMode volumeAverage|coreWeighted|sensorEmulation` (optional; default `volumeAverage`)

In lumped mode, OpenFOAM computes a volume-weighted mean temperature for the `cellZone`, writes a single record to `ecm_in.bin`, and applies the returned heat uniformly over the coupled volume. When `lumpedOutput totalPower` is used, the returned total heat is converted to a uniform `qVol` using the total coupled volume.

`tEffMode` options:
- `volumeAverage` (default): use volumeAverage(T) over the coupled zone.
- `coreWeighted`: weight cells by 1/(r+epsilon) relative to `coreAxis` and `coreOrigin`.
- `sensorEmulation`: average over `sensorZone` cellZone if provided; falls back to `volumeAverage`.

Adaptive relaxation (optional):
```
adaptiveRelaxation true;
alphaMin          0.1;
alphaMax          1.0;
alphaIncrease     0.05;
alphaDecrease     0.2;
deltaQThreshold   0;    // disable if 0
deltaTThreshold   0;    // disable if 0
```
When enabled, `alpha_used` is logged each execute step.

Example configuration:
```text
couplingMode   lumped;
lumpedOutput   totalPower; // or volumetric
tEffMode       volumeAverage;
// Optional for coreWeighted:
coreAxis       (0 0 1);
coreOrigin     (0 0 0);
// Optional for sensorEmulation:
sensorZone     sensorZoneName;
// Optional axial distribution for single ECM:
axialProfile   uniform;    // or linear
axialAxis      (0 0 1);
axialOrigin    (0 0 0);
axialBias      0.0;        // -1..1, linear bias along axis
```

Mock ECM helper:
- `ecm/ecm_coupler.py` (binary IO) now uses `ecm/mock_ecm_backend.py`.
- It supports `ECM_LUMPED_OUTPUT=totalPower|volumetric`.
- If using element-wise mode, pass `ECM_ACTIVE_VOLUME=<m^3>` to compute a uniform `qVol`.
- State is persisted in `ECM_STATE_FILE` (default `ecm_state.json`); reset with `ECM_STATE_RESET=1`.
- Backends: `ECM_BACKEND=mock-inproc` (default) or `ECM_BACKEND=vendor-cli` with
  `ECM_VENDOR_EXEC=/path/to/vendor_cli.py`, optional `ECM_VENDOR_WORKDIR`, `ECM_VENDOR_STATE`.

### Element-wise with ECM cell intersections (mapping table)
For non-lumped coupling where ECM elements do not align with mesh cells, use a
mapping table to translate between mesh-cell temperatures and ECM element heat
outputs. The mapping table lives on the ECM side and is consumed by
`ecm/ecm_coupler.py` via `ECM_MAPPING_FILE`.

Mapping CSV format (header required):
```text
meshKey,ecmCellId,weight
```
Where:
- `meshKey` is the OpenFOAM key (globalCellId or localCellId, per `keyMode`).
- `ecmCellId` is the ECM element identifier.
- `weight` is the intersection weight (typically intersection volume in m^3).

Algorithm:
1. Aggregate ECM temperatures: `T_ecm = sum(weight * T_mesh) / sum(weight)`.
2. Run ECM on each `ecmCellId` to get `qVol_ecm`.
3. Distribute back to mesh: `qVol_mesh = sum(qVol_ecm * weight) / sum(weight)`.

Example (controlDict command):
```text
couplingMode   elementWise;
ioMode         binary;
command        "ECM_MAPPING_FILE=ecm/mapping_table.csv PYTHONPATH=/workspace python3 ../../ecm/ecm_coupler.py";
```

Synthetic mapping for quick tests (no geometry):
```text
command "ECM_MAPPING_MODE=synthetic ECM_N_ELEMENTS=8 ECM_OVERLAP=0.3 PYTHONPATH=/workspace python3 ../../ecm/ecm_coupler.py";
```
`ECM_OVERLAP` is a relative weight (0..0.49) used to simulate intersecting
elements; it is not a physical volume.

### CLI wrapper (current consultant implementation, lumped-only)
The consultant wrapper is a CLI-driven, lumped single-cell test bench. It does
not accept per-step input files or return per-step output files. To couple it
from OpenFOAM, `ecmCoupler` supports a `cliWrapper` IO mode that:
- reduces the CFD zone to a single temperature (same `tEffMode` as lumped),
- invokes the wrapper once per CFD step using CLI arguments,
- reads the wrapper CSV output to obtain total heat `Q_GEN_W` [W],
- converts total heat to uniform `ecmQdot` over the coupled volume.

Configuration (minimum):
```text
ioMode             cliWrapper;
couplingMode       lumped;
lumpedOutput       totalPower;

// Base command (wrapper script path + python)
wrapperCommand     "python /path/to/fake_coupled.py";

// Wrapper CLI mode and profiles
wrapperMode        single;
wrapperTempMode    coupled;
wrapperTempProfile constant;
wrapperCurrentProfile constant;
wrapperSteps       1;

// CSV output
wrapperWriteCsv    true;
wrapperCsvPrefix   "ecm/wrapper_run";
// Optional: override exact CSV path
// wrapperCsvFile "ecm/wrapper_run_single.csv";

// Temperature conversion (OpenFOAM T in K -> wrapper expects degC)
wrapperTempOffsetC -273.15;

// Initial ECM state (persisted in memory across steps)
currentA       5.0;
qAhInit        0.0;
vRc1Init       0.0;
vRc2Init       0.0;
hysteresisInit 0.0;
// Optional: append extra CLI args (verbatim)
// wrapperExtraArgs "--log ./ecm/wrapper.log";
```

CSV column names expected by default:
`Q_GEN_W`, `q_ah_next`, `V_RC_1`, `V_RC_2`, `H`, `V_T_V`.
Override with:
```text
wrapperHeatColumn       Q_GEN_W;
wrapperQAhColumn        q_ah_next;
wrapperVrc1Column       V_RC_1;
wrapperVrc2Column       V_RC_2;
wrapperHysteresisColumn H;
wrapperVoltageColumn    V_T_V;
```

Notes:
- `cliWrapper` requires `couplingMode lumped` and `wrapperWriteCsv true`.
- The wrapper uses `params.csv` and `cellprops.csv` from its script directory.
- `ecmCoupler` preserves `q_ah`, `V_RC`, and `H` across steps using the CSV
  fields; if those columns are missing, it keeps the previous values.
  Use `wrapperStateReset true` to force reinitialization each call (only if the
  wrapper supports `--state-reset`).

### JSON wrapper (production wrapper, lumped-only)
The JSON wrapper mode uses `ecm_coupling_wrapper.py` to exchange one-step JSON
files per execute. Configure `ioMode jsonWrapper` and provide a command that
invokes the wrapper with `--input`, `--output`, and `--state` arguments.

Configuration (minimum):
```text
ioMode         jsonWrapper;
couplingMode   lumped;
lumpedOutput   totalPower;
inFile         "ecm/ecm_in.json";
outFile        "ecm/ecm_out.json";
command        "PYTHONPATH=/workspace python3 ../../ecm_coupling_wrapper.py --backend mock-inproc --input ecm/ecm_in.json --output ecm/ecm_out.json --state ecm/ecm_state.json";
```

Notes:
- `jsonWrapper` requires `couplingMode lumped`.
- The wrapper persists its state via the `--state` file path.
- `wrapperStateReset`, `qAhInit`, `vRc*Init`, and `hysteresisInit` are sent as
  JSON `reset_state`/`init_state` values.

## Applying the source term in OpenFOAM

You have three common options:

### A) Use `fvOptions` / `codedSource` (no solver changes)
- Add a `codedSource` fvOption that reads `ecmST` (K/s) and adds it to the scalar equation for `T`.
- For compressible solvers, prefer using `ecmQdot` directly as an energy source for `he/h/e`.

A template is provided in the example case.

### B) Use `fvModels` (if your solver stack uses fvModels)
- Implement an `fvModel` that injects `ecmQdot` into the energy equation.

### C) Modify a custom solver
- In your energy equation assembly, add `+ ecmQdot` with appropriate sign and scaling.

## Serial vs parallel

### Serial
- Use `keyMode localCellId` (or leave default `globalCellId` — both work in serial).

### Parallel (`parallelMode masterGather`)
- Recommended.
- Uses `globalIndex` to assign stable global cell IDs.
- Gathers temperatures to master, executes ECM once, broadcasts results.

Lumped mode still uses a single ECM call on the master rank; the averaged temperature and total coupled volume are reduced across ranks.

## Unit conversion

If the external ECM returns `qVol` in W/m^3 but your equation expects a temperature source (K/s), set:

- `outputMode temperatureSource`
- `rhoCp` : volumetric heat capacity [J/m^3/K]

Then:
`ecmST = ecmQdot / rhoCp`

## Process and logging

This repo follows `MY_CODEX_BEST_PRACTICES_RULES.txt`. When integrating or
changing coupling behavior:
- Update `STATUS.md` and `docs/ASSUMPTIONS.md` as needed.
- Record decisions, blockers, and user-visible changes in `artifacts/logs/`.
- Prefer small, reversible changes and verify using `docs/TEST_PLAN.md`.

Coupling IO uses a transactional `stepId` in the binary headers (v2). The ECM is
expected to echo the same `stepId` in `ecm_out.bin`, otherwise OpenFOAM will keep
the previous `ecmQdot` values.

Missing output handling can be tightened for validation:
```
missingOutputLimit  3;          // consecutive missing outputs before action
missingOutputAction warn;       // warn|degraded|fatal
```
If the limit is exceeded and `missingOutputAction` is `degraded`, OpenFOAM will
log degraded mode; if `fatal`, it will abort.

`ecmCoupler` persists the last-good output snapshot for post-mortem analysis and
restart continuity:
```
lastGoodFile "artifacts/runtime/ecm_last_good.bin"; // empty to disable
```
The snapshot stores `stepId`, `time`, `Q_sum_check`, `returnCode`, and
`(key, qVol)` records from the last successful ECM read.

Each execute logs `Q_sum_check` (sum of applied `qVol*V`) for traceability; in
`lumpedOutput totalPower` mode, a mismatch between `Q_sum_check` and `Q_total`
triggers a warning.

## Time-dependent electrical inputs (CSV)

You can drive `electricalInputs` from a CSV file that is evaluated each execute
step. Configure:
```text
electricalInputsMode        csv;   // constant|csv
electricalInputsFile        "ecm/electrical_inputs.csv";
electricalInputsTimeColumn  time;  // header name for time column (seconds)

electricalInputs
{
    current_A 0;  // list of columns to read (defaults used if CSV missing)
    SOC       0;
}
```

CSV format example:
```text
time,current_A,SOC
0.0,5.0,0.60
1.0,5.0,0.60
2.0,2.0,0.58
```

Notes:
- If `electricalInputs` is empty, all CSV columns (except the time column) are used.
- Values are linearly interpolated in time and clamped to the first/last row if
  outside the table range.
