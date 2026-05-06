#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
stamp="$(date -u +%Y%m%d_%H%M%S)"
pkg_name="openfoam-ecm-portable_${stamp}"
out_root="$repo_root/artifacts/packs"
pkg_root="$out_root/$pkg_name"

mkdir -p "$out_root"
rm -rf "$pkg_root"
mkdir -p "$pkg_root"

copy_file() {
  local src="$1"
  local dst="$pkg_root/$1"
  mkdir -p "$(dirname "$dst")"
  cp -a "$repo_root/$src" "$dst"
}

copy_dir() {
  local src="$1"
  mkdir -p "$(dirname "$pkg_root/$src")"
  cp -a "$repo_root/$src" "$pkg_root/$src"
}

copy_file "Allwmake"
copy_file "build_portable.sh"
copy_file "README.md"
copy_file "PORTABLE_PACKAGE_README.md"
copy_file "LICENSE"
copy_file "cellprops.csv"
copy_file "params.csv"
copy_file "ecm_backend.py"
copy_file "ecm_coupling_wrapper.py"
copy_file "ecm_daemon.py"
copy_file "ecm_step.py"

copy_dir "src"
copy_dir "ecm"
copy_dir "docs"
copy_dir "tools"
copy_dir "cases/lumped_solid"
copy_dir "cases/distributed_solid"

# Drop repository- and machine-specific noise from the export.
find "$pkg_root" -type d \( -name __pycache__ -o -name .git \) -prune -exec rm -rf {} +
find "$pkg_root/ecm" -maxdepth 1 -type f \( -name 'ecm_in.*' -o -name 'ecm_out.*' \) -delete
find "$pkg_root/src" -type d -path '*/Make/linux*' -prune -exec rm -rf {} +
find "$pkg_root/src" -type f \( -name '*.o' -o -name '*.dep' \) -delete
find "$pkg_root/src" -type d -name lnInclude -prune -exec rm -rf {} +

for case_name in lumped_solid distributed_solid; do
  case_dir="$pkg_root/cases/$case_name"

  find "$case_dir" -maxdepth 1 -type d \
    -regextype posix-extended \
    -regex '.*/[0-9]+(\.[0-9]+)?' \
    -exec rm -rf {} +
  rm -rf \
    "$case_dir/postProcessing" \
    "$case_dir/VTK" \
    "$case_dir/plots_temp" \
    "$case_dir/artifacts" \
    "$case_dir/dynamicCode"
  rm -rf \
    "$case_dir/constant/polyMesh" \
    "$case_dir/constant/mesh_with_ambient" \
    "$case_dir/constant/extendedFeatureEdgeMesh" \
    "$case_dir/constant/cellFull.eMesh" \
    "$case_dir/constant/cellFull.extendedFeatureEdgeMesh" \
    "$case_dir/constant/cellFull_m.eMesh" \
    "$case_dir/constant/cellFull_m.extendedFeatureEdgeMesh" \
    "$case_dir/constant/cellFull_mm.eMesh"
  find "$case_dir/constant" -mindepth 2 -maxdepth 2 -type d -name polyMesh -prune -exec rm -rf {} +
  find "$case_dir" -maxdepth 1 \( -type f -o -type d \) \( -name 'log.*' -o -name '*.analyzed' -o -name '*.foam' \) -exec rm -rf {} +
  find "$case_dir/constant" -type d -name 'polyMesh.stale_*' -prune -exec rm -rf {} +
  find "$case_dir/constant" -type f \( -name '*.bak_*' -o -name '*.bak' \) -delete

  if [ -d "$case_dir/ecm" ]; then
    find "$case_dir/ecm" -maxdepth 1 -type f \
      \( -name 'ecm_state.json' -o -name 'ecm_last_good.bin' -o -name 'ecm_in.*' -o -name 'ecm_out.*' -o -name 'ecm_daemon.pid' -o -name 'ecm_daemon.sock' \) \
      -delete
    find "$case_dir/ecm" -maxdepth 1 -type s -delete
  fi
done

# Drop large docs and transient helper files that are not needed to run the package.
rm -rf "$pkg_root/docs"/artifacts 2>/dev/null || true
rm -rf "$pkg_root/docs/literature" 2>/dev/null || true
rm -f "$pkg_root/tools/_pv_slices_tmp.py"

tarball="$out_root/${pkg_name}.tar.gz"
tar -czf "$tarball" -C "$out_root" "$pkg_name"

printf '%s\n%s\n' "$pkg_root" "$tarball"
