#!/bin/bash
set -euo pipefail

case_dir="${1:-}"
solver="${2:-}"

if [ -z "${case_dir}" ] || [ -z "${solver}" ]; then
  echo "Usage: tools/run_passport.sh <case_dir> <solver>"
  exit 1
fi

case_dir="$(cd "${case_dir}" && pwd)"
log_solver="${case_dir}/log.${solver}"
log_checkmesh="${case_dir}/log.checkMesh"

echo "Running checkMesh..."
if [ -f "${case_dir}/system/meshQualityDict" ]; then
  checkMesh -case "${case_dir}" -allTopology -allGeometry -meshQuality > "${log_checkmesh}"
else
  checkMesh -case "${case_dir}" -allTopology -allGeometry > "${log_checkmesh}"
fi

echo "Running solver..."
${solver} -case "${case_dir}" > "${log_solver}" 2>&1

echo "Running foamLog..."
foamLog "${log_solver}" >/dev/null 2>&1 || true

echo "Writing run passport..."
python3 tools/run_passport.py \
  --case "${case_dir}" \
  --log "${log_solver}" \
  --out "${case_dir}/run_passport.json" \
  --timeseries "${case_dir}/metrics_timeseries.csv"

echo "Done."
