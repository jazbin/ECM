# Logging and Run Tracking

## Run logs
- Redirect solver output to log files (e.g. `simpleFoam > log.simpleFoam`).
- Store logs in the case directory and copy summaries to `artifacts/logs/`.
- Include OpenFOAM version, git commit, host, and parameters in the log header.

## Run passports (required)
- Every run must emit:
  - `run_passport.json`
  - `metrics_timeseries.csv`
  - `log.<solver>` and `log.checkMesh`
- Use `tools/run_passport.sh <case_dir> <solver>` (or equivalent CI step) to
  run checkMesh, capture logs, and generate the passport.
- The passport schema is defined in `tools/run_passport_schema.json`, and
  thresholds are in `tools/metrics_config.json`.

## Run IDs and manifests
- Assign each run a unique ID (timestamp + short hash).
- Store a manifest file alongside outputs describing inputs and environment.

Template: `tools/run_manifest_template.json`.

## Session and decision logs
- Session logs: `artifacts/logs/session.log`
- Chat log (append every user prompt + assistant response/actions): `artifacts/logs/chat.log`
- Decisions: `artifacts/logs/decision.log`
- Blockers: `artifacts/logs/blockers.log`
- Changes: `artifacts/logs/change.log`
