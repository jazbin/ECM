#!/bin/bash
# Run lumped_solid + distributed_solid from clean state and generate comparison PDF.
#
# Usage:
#   ./run_comparison.sh
#
# Both ECM state files are reset automatically (equivalent to --reset-ecm).
# Logs are written to:
#   cases/lumped_solid/log.run_clean
#   cases/distributed_solid/log.run_clean
# Report is written to:
#   artifacts/reports/comparison_report.pdf

set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"
LUMPED="$WORKSPACE/cases/lumped_solid"
DIST="$WORKSPACE/cases/distributed_solid"
REPORT_SCRIPT="$WORKSPACE/tools/generate_comparison_report.py"

echo "=== ECM Lumped vs Distributed comparison run ==="
echo "Workspace: $WORKSPACE"
echo

# ── 1. Reset ECM state files ────────────────────────────────────────────────
echo "[1/4] Resetting ECM state files..."
rm -f "$LUMPED/ecm/ecm_state.json" "$LUMPED/ecm/ecm_last_good.bin"
rm -f "$DIST/ecm/ecm_state.json"
echo "      Done."

# ── 2. Run lumped_solid ──────────────────────────────────────────────────────
echo "[2/4] Running lumped_solid (endTime=30s)..."
"$LUMPED/Allrun" 2>&1 | tail -1   # prints "Run log: /path/to/log"

# Copy latest artifacts log to fixed name in case dir for the report script.
latest_lumped=$(ls -t "$WORKSPACE/artifacts/logs"/lumped_run_*.log 2>/dev/null | head -1)
if [ -z "$latest_lumped" ]; then
  echo "ERROR: lumped run log not found." >&2; exit 1
fi
cp "$latest_lumped" "$LUMPED/log.run_clean"
echo "      Log: $LUMPED/log.run_clean"

# ── 3. Run distributed_solid ─────────────────────────────────────────────────
echo "[3/4] Running distributed_solid (endTime=30s)..."
"$DIST/Allrun" 2>&1 | tail -1

latest_dist=$(ls -t "$WORKSPACE/artifacts/logs"/distributed_solid_run_*.log 2>/dev/null | head -1)
if [ -z "$latest_dist" ]; then
  echo "ERROR: distributed run log not found." >&2; exit 1
fi
cp "$latest_dist" "$DIST/log.run_clean"
echo "      Log: $DIST/log.run_clean"

# ── 4. Generate comparison PDF ───────────────────────────────────────────────
echo "[4/4] Generating comparison report..."
mkdir -p "$WORKSPACE/artifacts/reports"
python3 "$REPORT_SCRIPT"
echo "      Report: $WORKSPACE/artifacts/reports/comparison_report.pdf"

echo
echo "=== Done ==="
