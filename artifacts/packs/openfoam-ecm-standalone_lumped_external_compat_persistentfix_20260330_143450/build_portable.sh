#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")" && pwd)"
cd "$repo_root"

if [ -z "${WM_PROJECT_DIR:-}" ]; then
  if [ -f /opt/openfoam/etc/bashrc ]; then
    # shellcheck disable=SC1091
    set +u
    source /opt/openfoam/etc/bashrc
    set -u
  elif [ -f /usr/lib/openfoam/openfoam/etc/bashrc ]; then
    # shellcheck disable=SC1091
    set +u
    source /usr/lib/openfoam/openfoam/etc/bashrc
    set -u
  else
    echo "ERROR: OpenFOAM environment is not loaded and no default bashrc was found." >&2
    echo "Load OpenFOAM v2506 manually, then rerun this script." >&2
    exit 2
  fi
fi

echo "Using WM_PROJECT_DIR=${WM_PROJECT_DIR:-unset}"
echo "Building package-local OpenFOAM components..."

./Allwmake

echo
echo "Build completed."
echo "Expected outputs are under:"
echo "  ${FOAM_USER_APPBIN:-<FOAM_USER_APPBIN not set>}"
echo "  ${FOAM_USER_LIBBIN:-<FOAM_USER_LIBBIN not set>}"
