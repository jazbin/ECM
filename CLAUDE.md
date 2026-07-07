# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session memory

Project memory lives in **`/workspace/MEMORY.md`** (this repo, not the global ~/.claude store).
At the start of each session: read `/workspace/MEMORY.md` for context.
At session close: update `/workspace/MEMORY.md` with stable new facts.

## STAR-CCM+ plugin code reference

**`starccm_plugin/CODE_SUMMARY.md`** is the authoritative quick-reference for
`EcmCouplerMacro.java`. It lists every class, method, constant, and line number.

Rules:
- **Before reading `EcmCouplerMacro.java` directly**, consult `CODE_SUMMARY.md` first.
  Use it to find the exact line range needed, then read only that section.
- **After any code change** to `EcmCouplerMacro.java`, update `CODE_SUMMARY.md` to
  reflect the new line numbers, method signatures, and behaviour.
- When syncing copies (see "Files that must stay in sync" in CODE_SUMMARY.md),
  `CODE_SUMMARY.md` itself does not need to be duplicated — one copy is enough.

## Project overview

OpenFOAM ↔ ECM (External Electrochemical Model) coupling framework for battery thermal simulation. Implements timestep-level weak two-way coupling:
- OpenFOAM extracts `T_mesh[i]` from a `cellZone`
- An external ECM returns `qVol[i]` (W/m³) keyed by stable mesh-cell IDs
- OpenFOAM applies the heat via `ecmQdot` (W/m³) and optionally `ecmST` (K/s) fields

The coupling is an OpenFOAM **functionObject** (`ecmCoupler`) that lives in `src/ecmCouplingFunctionObjects/`. The Python ECM mock and binary I/O protocol live in `ecm/`.

## Build

Requires OpenFOAM v2506 toolchain (`wmake`).

```bash
./Allwmake          # builds all three targets below
```

Targets:
- `lib/libecmCouplingFunctionObjects.so` — main functionObject
- `lib/libecmPatchFields.so` — custom patch fields
- `bin/chtMultiRegionSolidFoam` — modified CHT solver (solids-only implicit coupling guard)

Each target can be rebuilt individually:
```bash
wmake libso src/ecmCouplingFunctionObjects
wmake libso src/ecmPatchFields
wmake src/chtMultiRegionSolidFoam
```

## Running cases

```bash
# Serial end-to-end smoke test
cd cases/scalarTransport_ecm && ./Allrun

# CHT example
cd cases/chtMultiRegionSimpleFoam_ecm && ./Allrun

# Parallel (masterGather mode)
cd cases/scalarTransport_ecm && ./Allrun -parallel

# Validated battery cell cases
cd cases/lumped && ./Allrun            # CHT multi-region (jellyRoll/shell/cap + ambient)
cd cases/lumped_solid && ./Allrun      # solids-only (no ambient fluid region)
```

Python backend requirements (for ECM mock):
```bash
pip install numpy pandas
```

## Run report generation

```bash
python3 tools/generate_lumped_report.py --case cases/lumped
```

## Architecture

### C++ coupling core (`src/ecmCouplingFunctionObjects/`)

`ecmCoupler` is a standard OpenFOAM functionObject declared in `controlDict`. On each `executeControl` event it:
1. Selects coupled cells from `zoneName` cellZone
2. Gathers temperatures (respecting `parallelMode masterGather` using `globalIndex`)
3. Writes `ecm_in.bin` (atomic: write `.tmp`, rename)
4. Runs the external command (`command` dict entry)
5. Reads `ecm_out.bin` and maps returned `qVol` onto `ecmQdot`

Key header: `src/ecmCouplingFunctionObjects/ecmCoupler/ecmCoupler.H`

Important modes (configured in `controlDict` functionObject dict):
| Key | Values | Notes |
|-----|--------|-------|
| `couplingMode` | `lumped`, `elementWise` | lumped = single ECM call, volume-avg T |
| `ioMode` | `binary`, `cliWrapper`, `jsonWrapper` | binary is primary; jsonWrapper uses `ecm_coupling_wrapper.py` |
| `parallelMode` | `serialOnly`, `masterGather` | masterGather required for parallel runs |
| `outputMode` | `volumetricHeat`, `temperatureSource` | temperatureSource divides by `rhoCp` |
| `lumpedOutput` | `totalPower`, `volumetric` | how ECM returns heat in lumped mode |
| `tEffMode` | `volumeAverage`, `coreWeighted`, `sensorEmulation` | how effective T is computed for ECM |

### Binary I/O protocol (`ecm/ecm_io.py`, `docs/IO_FORMAT.md`)

- **v1 header**: 44 bytes — magic `ECMIOv1\0`, fileType, version, N, time, deltaT, keyMode, nInputs
- **v2 header**: 52 bytes — v1 + uint64 `stepId` for transaction tracking
- Each record: `int32 key` + `double T` (input) or `double qVol` (output)
- Atomic write contract: write to `*.tmp`, then `rename()` to `*.bin`
- `keyMode 0` = globalCellId (recommended; works in parallel); `keyMode 1` = localCellId (serial only)

The C++ side echoes `stepId` back; if the ECM returns a mismatched `stepId`, the previous `ecmQdot` is kept.

### Python ECM mock (`ecm/`)

- `ecm/ecm_coupler.py` — orchestrator; reads `ecm_in.bin`, calls mock backend, writes `ecm_out.bin`
- `ecm/ecm_io.py` — binary protocol parser/writer
- `ecm/mock_ecm_backend.py` — stateful mock battery thermal model
- `ecm_coupling_wrapper.py` — JSON wrapper (for `ioMode jsonWrapper`)
- `ecm_backend.py` — backend abstraction (`mock-inproc` or `vendor-cli`)

ECM state persists in `ecm_state.json`. Reset with `ECM_STATE_RESET=1`.

### Modified CHT solver (`src/chtMultiRegionSolidFoam/`)

Fork of OpenFOAM `chtMultiRegionFoam`. Key additions:
- **Forced-explicit fallback**: when `allowImplicitSolidsOnly false` (default), solid-solid implicit coupling is replaced with explicit to prevent `fvMatrixAssembly` undershoot
- **`implicitClampTMin`**: optional clamp guarding against undershoot if implicit coupling is enabled
- **`debugImplicitCoupling`**: instrumentation flag for debugging interface temperatures

### Case geometry (`cases/lumped`, `cases/lumped_solid`)

3D cylindrical jelly-roll battery cell (2170 geometry, `cellFull_2170.stl`):
- Regions: `jellyRoll` (active zone), `shell`, `cap`, `ambient` (fluid, CHT only)
- Mesh: snappyHexMesh + `splitMeshRegions`; blockMesh cells must be isotropic (same x/y/z size, 1 mm target)
- ECM coupled zone: `jellyRoll` cellZone
- Boundary: `externalWall` fixed at 313.15 K; solid-solid interfaces use `compressible::turbulentTemperatureTwoPhaseRadCoupledMixed`

## Key constraints

- **All blockMesh cells must be isotropic** (same size in x, y, z) — enforced by AGENTS.md
- **Only CHT-related test cases are allowed** under `cases/`
- **Do not touch**: `AGENTS.md`, `MY_CODEX_BEST_PRACTICES_RULES.txt`, `.codex/`
- **Source term sign**: use `-= ecmQdot * V` to add heat (positive ECM output = heat generation)
- **Parallel**: always use `parallelMode masterGather` with `keyMode 0` (globalCellId); never `keyMode 1` with `-parallel`
- **Solids-only implicit coupling**: known undershoot issue — use `useImplicit false` (explicit) unless investigating
- **File paths in STAR-CCM+ FileTables and any config written by Java/Python must be RELATIVE paths** (relative to the project/sim root). Never call `getAbsolutePath()`, `toAbsolutePath()`, or construct an absolute path string when setting a table file reference. Absolute paths break portability and overwrite user-configured paths in the `.sim` file. **Any exception requires explicit double-confirmation from the user before proceeding.**

## Operating rules

- **Every plot file saved to `artifacts/plots/` must be traceable to its generating script.**
  Immediately after saving a plot, append one line to `artifacts/plots/PLOT_REGISTRY.md`:
  `| <filename> | <tools/script_name.py> | <one-line description> |`
  If the registry does not exist, create it with a header row first.

- Update `STATUS.md` and `docs/ASSUMPTIONS.md` for any significant change
- Record decisions in `artifacts/logs/decision.log`, blockers in `artifacts/logs/blockers.log`
- Append each prompt + response to `artifacts/logs/chat.log`
- Create per-session log under `artifacts/logs/session_YYYYMMDD_HHMMSS.log`
- All acceptance tests must produce `run_passport.json` and `metrics_timeseries.csv` (see `docs/TEST_PLAN.md`)

## Useful paths

| Path | Purpose |
|------|---------|
| `docs/INTEGRATION.md` | Full configuration reference for `ecmCoupler` |
| `docs/IO_FORMAT.md` | Binary protocol spec |
| `docs/TEST_PLAN.md` | Acceptance test ladder (Tests 1–11) |
| `docs/TEST_CASE_RULES.md` | Case setup safeguards |
| `artifacts/logs/` | Build, run, session, decision, and chat logs |
| `artifacts/reports/` | Generated PDF run reports |
| `tools/generate_lumped_report.py` | Report generation |
| `tools/run_passport.sh` | Run passport generation |

---

## Document Generation Requirements — Controlled Final PDF Deliverables

These requirements apply to every generated client-facing document, technical report, proposal, memo, calculation note, CFD/FEM report, engineering assessment, or other professional deliverable.

### 1. Final deliverable format

Unless the user explicitly instructs otherwise, all final client deliverables must be prepared as controlled PDF reports.

Do not generate, offer, or deliver editable/source/working document files as default deliverables. This includes, but is not limited to:

- DOCX / Word files
- ODT / LibreOffice Writer files
- LaTeX source files
- Markdown source files intended as the client deliverable
- Editable spreadsheets
- Native CAD files
- Native CFD/FEM project files
- Post-processing source files
- Scripts, notebooks, templates, or intermediate working files

Editable/source/working files may only be included if they are explicitly listed as separate paid deliverables by the user.

### 2. Document-control section placement

Do not place the full document-control disclaimer at the beginning of the document.

The beginning of the document should remain clean and client-facing:
- title page
- executive summary
- introduction
- main technical content

The full document-control and verification statement must be placed at the end of the document, preferably as the final appendix or final section.

Recommended section title:

```text
Appendix [X]. Document Control and Verification
```

or, if appendices are not used:

```text
Document Control and Verification
```

### 3. Required document-control block

Every final controlled PDF report must include the following block at the end of the document, with placeholders filled in:

```text
Document Control and Verification

Document title: [Report Title]
Project: [Project Name]
Client: [Client Name]
Prepared by: Bojan Vidović
Issue date: [YYYY-MM-DD]
Revision: Rev A
Deliverable format: Controlled PDF report

This PDF is the controlled final issued report. The consultant is responsible only for this issued PDF version. Any modified, extracted, translated, reformatted, or edited version is not an authorized consultant-issued report unless reviewed and reissued by the consultant.

Document verification:
Filename: [filename.pdf]
SHA-256 checksum: [hash]

Any modification to the PDF file changes the checksum. Only the PDF matching the checksum above should be treated as the consultant-issued version.
```

### 4. Required footer

Every final report should include a short footer on each page, unless the user explicitly requests no footer:

```text
Controlled PDF Report — Rev A — [YYYY-MM-DD] — Bojan Vidović
```

If the document has multiple revisions, update the revision field consistently:

- Rev A
- Rev B
- Rev C

### 5. SHA-256 checksum requirement

For every final PDF, calculate and include a SHA-256 checksum.

On Linux/Ubuntu, use:

```bash
sha256sum [filename.pdf]
```

The checksum must appear in:

1. the final document-control section at the end of the report;
2. the delivery message to the client.

### 6. Standard delivery message

When preparing the client delivery message, include this text:

```text
Hi [Client Name],

I am submitting the final controlled PDF report for this milestone.

For document-control purposes:

Filename: [filename.pdf]
Revision: Rev A
Issue date: [YYYY-MM-DD]
SHA-256 checksum: [hash]

The document-control and verification statement is included at the end of the report.

Thank you.
```

### 7. Source-file boundary

Do not describe DOCX, Word, LaTeX, Markdown, CAD, CFD, FEM, spreadsheet, script, or other editable files as included unless the user explicitly states that these files are part of the paid scope.

Use this wording when needed:

```text
Editable/source/working files are not included unless explicitly listed as separate paid deliverables.
```

For offers/proposals, include this deliverables clause:

```text
Final deliverable:
Controlled PDF technical report.

Editable/source/working files, including DOCX, CAD files, CFD cases, scripts, spreadsheets, and native post-processing files, are not included unless explicitly listed as separate paid deliverables.
```
