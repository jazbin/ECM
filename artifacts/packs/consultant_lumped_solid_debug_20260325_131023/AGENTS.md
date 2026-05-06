# AGENTS.md — Codex tasks for OpenFOAM ECM coupling

## Operating rules

This repo follows `MY_CODEX_BEST_PRACTICES_RULES.txt`. Keep `STATUS.md` and
`docs/ASSUMPTIONS.md` current and record decisions/blockers/changes under
`artifacts/logs/`.
Start a new per-session log file under `artifacts/logs/` for every session (e.g., `session_YYYYMMDD_HHMMSS.log`). Log both the user's inputs and the assistant's responses/actions. Maintain `artifacts/logs/session.log` as a short index pointing to the active session log for quick access.
On each user prompt, append the prompt and the assistant response/actions to `artifacts/logs/chat.log`.
Only allowed test cases are CHT (CHT-related cases only).
All blockMesh cells must be isotropic (same size in x, y, z).
CHT case setup must be based on the simplest applicable OpenFOAM tutorial case.
Validate case setup by comparing against the relevant tutorial configuration before running.
General test-case safeguards live in `docs/TEST_CASE_RULES.md` and must be followed.

## Goal
Implement a robust OpenFOAM ↔ external ECM coupling where:
- OpenFOAM extracts `T[i]` from an active cellZone
- External ECM returns `qVol[i]` (W/m^3) keyed by stable mesh-cell IDs
- OpenFOAM maps `qVol` into a `volScalarField` and (optionally) applies it as a source term

## Terminology (use consistently)

- **Battery cell**: physical electrochemical unit represented by the ECM (single electrical state on the ECM side).
- **Mesh cell**: OpenFOAM finite-volume cell. This coupling exchanges `T_mesh[i]` and `qVol[i]` per *mesh cell* inside a `cellZone`.
- The ECM is **not** one instance per mesh cell. It is one black box per battery cell (or module) and may return a spatial heat distribution over mesh cells.

## Non-goals (for this stage)
- No Star-CCM+ macros
- No Design Studio / BDS
- No advanced co-simulation middleware beyond file I/O + process call
- No multi-physics solver modifications (provide templates; user integrates into target solver)

---

## Task 1 — Buildable functionObject library
**Requirement**
- `libecmCouplingFunctionObjects.so` builds with OpenFOAM v2506 toolchain
- Provides `functionObjects::ecmCoupler` (type `ecmCoupler`) callable from `controlDict`

**Verification**
- `./Allwmake` succeeds
- `foamRun -help functionObjects` (or equivalent) lists the library without runtime errors

---

## Task 2 — Binary IO protocol + atomic handshake
**Requirement**
- OpenFOAM writes `ecm_in.tmp` then renames to `ecm_in.bin`
- External solver writes `ecm_out.tmp` then renames to `ecm_out.bin`
- Header contains: magic, fileType, version, N, time, deltaT, keyMode, nInputs
- Inputs list supports arbitrary name/value electrical inputs

**Verification**
- A Python parser can read both files and validate N/time/deltaT

---

## Task 3 — Serial coupling (baseline)
**Requirement**
- Extract temperatures in `cellZone zone`
- Run external command once per execute
- Read returned q-values keyed by mesh-cell IDs
- Update fields:
  - `ecmQdot` (W/m^3)
  - `ecmST` (K/s) if `outputMode temperatureSource` with constant `rhoCp`

**Verification**
- Example case runs in serial and fields are written every timestep

---

## Task 4 — Parallel coupling (masterGather)
**Requirement**
- Use stable global mesh-cell IDs via `globalIndex`
- Gather (globalID, T) pairs to master
- Run ECM once on master
- Broadcast (globalID, q) pairs to all ranks
- Each rank updates its local cells accordingly

**Verification**
- `decomposePar -force; mpirun -np 2 scalarTransportFoam -parallel` runs and writes fields

---

## Task 5 — Stability controls
**Requirement**
- Under-relaxation for applied q:
  `qApplied = alpha*qNew + (1-alpha)*qOld`
- Basic sanity checks:
  - missing output file → keep previous q, emit warning
  - N mismatch → warning + best-effort map by keys

**Verification**
- Run with ECM temporarily disabled; simulation continues with warnings

---

## Task 6 — Integration templates
**Requirement**
- Provide templates for applying the source term:
  - `fvOptions` codedSource example for scalar `T`
  - Guidance for `he/h/e` source in compressible/CHT solvers

**Verification**
- Example case uses the template and produces non-trivial temperature evolution

---

## Task status (current)
- Task 1: Done (library builds; see `artifacts/logs/build_Allwmake.log`).
- Task 2: Done (binary IO protocol implemented; parser smoke test ran).
- Task 3: Done (serial coupling validated in `cases/scalarTransport_ecm`; see `artifacts/logs/scalarTransport_ecm_serial.log`).
- Task 4: Done (parallel masterGather validated in `cases/scalarTransport_ecm`; see `artifacts/logs/scalarTransport_ecm_parallel.log`).
- Task 5: Done (under-relaxation and sanity checks implemented; added N-mismatch warning).
- Task 6: Done (integration guidance in `docs/INTEGRATION.md` and fvOptions template in example case).
