#!/usr/bin/env python3
import argparse
import csv
import io
import json
import math
import os
import struct
import sys
import time
from collections import defaultdict

import numpy as np
import pandas as pd

from ecm_io import (
    Header, read_header, read_inputs, read_records_T,
    write_header, write_inputs, write_records
)
from mock_model import compute_qvol
from mock_ecm_backend import build_step_cache, get_backend

# Real ECM step, flattened into the same python/ runtime directory.
_PYTHON_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_PYTHON_DIR)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

_ANNOUNCED_MAPPINGS = set()
_MAPPING_CACHE = {}
_PARTITION_VOLUMES_CACHE = {}
_TABLE_CACHE = {}
_REGEN_CHECKED = set()  # mapping paths already checked this process

try:
    from ecm_step import (
        ecm_step as _ecm_step_fn,
        build_step_cache as _ecm_build_step_cache,
        _get_params as _ecm_get_params,
        parallel_2rc_step,
        multi_cell_parallel_step,
        multi_cell_equal_current_step,
        soc_to_q_ah,
        q_ah_to_soc,
    )
    _ECM_STEP_AVAILABLE = True
except ImportError:
    _ecm_step_fn = None
    _ecm_build_step_cache = None
    _ecm_get_params = None
    parallel_2rc_step = None
    multi_cell_parallel_step = None
    multi_cell_equal_current_step = None
    soc_to_q_ah = None
    q_ah_to_soc = None
    _ECM_STEP_AVAILABLE = False

def atomic_write(path: str, data_bytes: bytes) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _diagnostics_trace_path() -> str:
    raw = os.environ.get("ECM_TRACE_CSV", "").strip()
    if raw:
        if os.path.isabs(raw):
            return raw
        return os.path.join(_PYTHON_DIR, raw)
    return os.path.join(_PYTHON_DIR, "ecm_runtime_trace.csv")


def _append_trace_row(row: dict) -> None:
    path = _diagnostics_trace_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fieldnames = [
        "time_s",
        "dt_s",
        "mode",
        "current_A",
        "T_eff_K",
        "Q_total_W",
        "Q_IR_W",
        "Q_HYS_W",
        "Q_REV_W",
        "qVol_min_Wm3",
        "qVol_max_Wm3",
        "n_partitions",
        "state_soc",
        "state_q_ah",
        "state_hysteresis",
        "state_v_rc1",
        "state_v_rc2",
        "V_OCV_V",
        "V_OCV_avg_V",
        "V_T_V",
        "V_OP_V",
        "R0_Ohm",
        "R1_Ohm",
        "R2_Ohm",
        "C1_F",
        "C2_F",
        "dUdT_VK",
        "input_activeVolume_m3",
        "input_V_jellyroll_m3",
        "call_every_n",
        "steps_since_ecm",
    ]
    write_header_row = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header_row:
            writer.writeheader()
        writer.writerow({name: row.get(name, "") for name in fieldnames})


def _emit_ecm_diag_line(diag: dict, cell_id: str = "") -> None:
    ordered_keys = [
        "mode",
        "time_s",
        "dt_s",
        "current_A",
        "T_eff_K",
        "Q_total_W",
        "Q_IR_W",
        "Q_HYS_W",
        "Q_REV_W",
        "state_soc",
        "state_q_ah",
        "state_hysteresis",
        "state_v_rc1",
        "state_v_rc2",
        "V_OCV_V",
        "V_OCV_avg_V",
        "V_T_V",
        "V_OP_V",
        "R0_Ohm",
        "R1_Ohm",
        "R2_Ohm",
        "C1_F",
        "C2_F",
        "dUdT_VK",
        "qVol_min_Wm3",
        "qVol_max_Wm3",
        "n_partitions",
        "V_common_V",
        "V_branch_min_V",
        "V_branch_max_V",
        "I_branch_min_A",
        "I_branch_max_A",
        "I_branch_sum_A",
    ]
    parts = []
    for key in ordered_keys:
        if key not in diag:
            continue
        value = diag.get(key, "")
        if value == "":
            continue
        if isinstance(value, float):
            parts.append(f"{key}={value:.9e}")
        else:
            parts.append(f"{key}={value}")
    if parts:
        prefix = f"[ecm_diag] " + (f"cell_id={cell_id} " if cell_id else "")
        sys.stderr.write(prefix + " ".join(parts) + "\n")


def _append_voltage_history(
    state_file: str,
    step_id: int,
    time_s: float,
    dt_s: float,
    current_a: float,
    diag: dict,
    cell_id: str = "",
) -> None:
    out_dir = os.path.dirname(state_file) or "."
    path = os.path.join(out_dir, "voltageHistory.csv")
    header = (
        "time_s,delta_t_s,step_id,current_a,t_eff_k,cell_id,"
        "v_common_v,v_branch_min_v,v_branch_max_v,q_total_w,n_partitions\n"
    )
    row = (
        f"{time_s:.17g},{dt_s:.17g},{step_id},{current_a:.17g},"
        f"{float(diag.get('T_eff_K', 0.0)):.17g},{cell_id},"
        f"{float(diag.get('V_common_V', 0.0)):.17g},"
        f"{float(diag.get('V_branch_min_V', 0.0)):.17g},"
        f"{float(diag.get('V_branch_max_V', 0.0)):.17g},"
        f"{float(diag.get('Q_total_W', 0.0)):.17g},"
        f"{int(diag.get('n_partitions', 0))}\n"
    )
    try:
        exists = os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if not exists or os.path.getsize(path) == 0:
                f.write(header)
            f.write(row)
    except OSError:
        pass


def _append_voltage_log(state_file: str, step_id: int, time_s: float, diag: dict) -> None:
    """Write one row to voltageLog.csv — dedicated clean voltage time-history.

    Source: ECM V_common_V (terminal voltage from ECM backend, not a STAR monitor).
    Restart policy: truncate on step_id == 1 (Java always resets stepId to 1 on run start).
    Schema: time_s,v_common_v
    """
    out_dir = os.path.dirname(state_file) or "."
    path = os.path.join(out_dir, "voltageLog.csv")
    mode = "w" if step_id == 1 else "a"
    try:
        with open(path, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write("time_s,v_common_v\n")
            f.write(
                f"{time_s:.17g},"
                f"{float(diag.get('V_common_V', 0.0)):.17g}\n"
            )
    except OSError:
        pass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _should_log_ecm_step(step_id: int) -> bool:
    # Heavy log always logs; otherwise fall back to ECM_LOG_EVERY_N_STEPS cadence.
    if os.environ.get("ECM_HEAVY_LOG", "0").strip() == "1":
        return True
    every = _int_env("ECM_LOG_EVERY_N_STEPS", 0)
    if every <= 0:
        return False
    return step_id % every == 0


def _hlog(msg: str) -> None:
    """Write a heavy-log line to stderr. Only emitted when ECM_HEAVY_LOG=1."""
    if os.environ.get("ECM_HEAVY_LOG", "0").strip() == "1":
        sys.stderr.write(f"[ecm_heavy] {msg}\n")


def _find_runtime_csv(name: str) -> str:
    for d in [_PYTHON_DIR, _WORKSPACE_ROOT]:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return ""


def _load_runtime_tables():
    params_path = _find_runtime_csv("params.csv")
    cellprops_path = _find_runtime_csv("cellprops.csv")
    key = (params_path, cellprops_path)
    cached = _TABLE_CACHE.get(key)
    if cached is not None:
        return cached

    params_df = pd.read_csv(params_path) if params_path else pd.DataFrame()
    cellprops_df = pd.read_csv(cellprops_path) if cellprops_path else pd.DataFrame()
    lookup_cache = build_step_cache(params_df)
    ecm_lookup_cache = _ecm_build_step_cache(params_df) if _ECM_STEP_AVAILABLE else None
    cached = (params_df, cellprops_df, lookup_cache, ecm_lookup_cache)
    _TABLE_CACHE[key] = cached
    return cached


def _load_runtime_tables_for_region(r_idx: int):
    """Load params/cellprops for region r_idx.

    Lookup order for params:
      1. params_r{N}.csv  (per-region override)
      2. params.csv       (shared fallback)

    Same pattern for cellprops_r{N}.csv / cellprops.csv.

    Results are cached by (params_path, cellprops_path) so repeated calls
    within one process are free.
    """
    params_path = (
        _find_runtime_csv(f"params_r{r_idx}.csv")
        or _find_runtime_csv("params.csv")
    )
    cellprops_path = (
        _find_runtime_csv(f"cellprops_r{r_idx}.csv")
        or _find_runtime_csv("cellprops.csv")
    )
    key = (params_path, cellprops_path)
    cached = _TABLE_CACHE.get(key)
    if cached is not None:
        return cached

    params_df = pd.read_csv(params_path) if params_path else pd.DataFrame()
    cellprops_df = pd.read_csv(cellprops_path) if cellprops_path else pd.DataFrame()
    lookup_cache = build_step_cache(params_df)
    ecm_lookup_cache = _ecm_build_step_cache(params_df) if _ECM_STEP_AVAILABLE else None
    cached = (params_df, cellprops_df, lookup_cache, ecm_lookup_cache)
    _TABLE_CACHE[key] = cached

    # Log which files are actually being used (once per unique key).
    sys.stderr.write(
        f"[ecm_coupler] region[{r_idx}] params={params_path or 'none'}  "
        f"cellprops={cellprops_path or 'none'}\n"
    )
    return cached


def _partition_groups(n_items: int, n_groups: int) -> list[tuple[int, int]]:
    """Return [start, stop) slices that split n_items as evenly as possible."""
    return [
        (i * n_items // n_groups, (i + 1) * n_items // n_groups)
        for i in range(n_groups)
    ]


def _pca_cylinder_axis(xs, ys, zs):
    """Detect cylinder axis from centroids via PCA (power iteration, no numpy).

    Returns (center, axis_unit) where center=(cx,cy,cz) and axis_unit is the
    unit vector along the largest-variance direction (the cylinder axis).
    """
    n = len(xs)
    cx = sum(xs) / n
    cy = sum(ys) / n
    cz = sum(zs) / n

    # 3x3 covariance matrix
    cov = [[0.0]*3 for _ in range(3)]
    for i in range(n):
        dx, dy, dz = xs[i] - cx, ys[i] - cy, zs[i] - cz
        cov[0][0] += dx*dx; cov[0][1] += dx*dy; cov[0][2] += dx*dz
        cov[1][0] += dy*dx; cov[1][1] += dy*dy; cov[1][2] += dy*dz
        cov[2][0] += dz*dx; cov[2][1] += dz*dy; cov[2][2] += dz*dz
    for i in range(3):
        for j in range(3):
            cov[i][j] /= n

    # Power iteration for largest eigenvector
    v = [1.0, 0.0, 0.0]
    for _ in range(50):
        w = [sum(cov[i][j]*v[j] for j in range(3)) for i in range(3)]
        nw = math.sqrt(sum(x*x for x in w))
        if nw < 1e-30:
            break
        v = [x/nw for x in w]

    # Consistent orientation: largest-magnitude component positive
    max_idx = max(range(3), key=lambda i: abs(v[i]))
    if v[max_idx] < 0:
        v = [-x for x in v]

    return (cx, cy, cz), tuple(v)


def _read_region_geometry_csv(path):
    """Read ecm_region_geometry.csv → {regionIdx: {"origin":(x,y,z), "axis":(ax,ay,az)}}."""
    result = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ri = int(row["regionIdx"])
            origin = (float(row["origin_x"]), float(row["origin_y"]),
                      float(row["origin_z"]))
            axis = (float(row["axis_x"]), float(row["axis_y"]),
                    float(row["axis_z"]))
            n = math.sqrt(sum(a*a for a in axis))
            if n > 1e-15:
                axis = tuple(a/n for a in axis)
            result[ri] = {"origin": origin, "axis": axis}
    return result


def _maybe_regen_mapping(mapping_path: str) -> None:
    """Regenerate ecm_mapping.csv if ecm_cell_map.csv is newer (or mapping absent).

    Runs at most once per process per mapping path (gated by _REGEN_CHECKED).
    Uses PCA to detect per-region cylinder axis for correct local (axial, radial)
    coordinates.  Optionally reads ecm_region_geometry.csv for STAR-CCM+ coordinate
    system overrides.
    """
    if mapping_path in _REGEN_CHECKED:
        return
    _REGEN_CHECKED.add(mapping_path)

    # Locate cell map (env override or same directory as the mapping file).
    cell_map_path = os.environ.get("ECM_CELL_MAP_CSV", "").strip()
    if not cell_map_path:
        cell_map_path = os.path.join(os.path.dirname(os.path.abspath(mapping_path)),
                                     "ecm_cell_map.csv")
    if not os.path.exists(cell_map_path):
        return  # nothing to regenerate from

    map_mtime = os.path.getmtime(mapping_path) if os.path.exists(mapping_path) else 0.0
    cell_mtime = os.path.getmtime(cell_map_path)
    needs_regen = cell_mtime > map_mtime
    if not needs_regen and os.path.exists(mapping_path):
        # Belt-and-suspenders: if row counts differ the mapping is stale even when
        # mtime looks fine (e.g. lumped mode didn't rewrite cell_map after a re-mesh).
        try:
            with open(cell_map_path) as _f:
                n_cellmap = sum(1 for _ in _f) - 1  # subtract header
            # Count unique meshKey values — overlap-weighted mappings have >1 row per
            # boundary cell, so comparing total rows to cell count is wrong.
            with open(mapping_path, newline="") as _f:
                _rdr = csv.DictReader(_f)
                _key_col = (_rdr.fieldnames or ["meshKey"])[0]
                n_unique_keys = len({row[_key_col] for row in _rdr})
            if n_cellmap != n_unique_keys:
                sys.stderr.write(
                    f"[ecm_coupler] ecm_mapping.csv has {n_unique_keys} unique mesh keys but "
                    f"ecm_cell_map.csv has {n_cellmap} cells — forcing regeneration.\n"
                )
                needs_regen = True
        except OSError:
            pass
    if not needs_regen:
        return  # mapping is up to date

    n_axial = int(os.environ.get("ECM_MAPPING_AXIAL", "6"))
    n_radial = int(os.environ.get("ECM_MAPPING_RADIAL", "3"))
    total_vol = float(os.environ.get("ECM_JELLY_ROLL_VOLUME_M3", "2.36e-5"))

    cell_ids, xs_raw, ys_raw, zs_raw, region_ids = [], [], [], [], []
    with open(cell_map_path, newline="") as f:
        reader = csv.DictReader(f)
        has_region_col = "regionIdx" in (reader.fieldnames or [])
        for row in reader:
            cell_ids.append(int(row["cellId"]))
            xs_raw.append(float(row["x_m"]))
            ys_raw.append(float(row["y_m"]))
            zs_raw.append(float(row["z_m"]))
            region_ids.append(
                int(row["regionIdx"])
                if has_region_col and row.get("regionIdx", "").strip()
                else 0
            )

    n_cells = len(cell_ids)
    n_regions = max(region_ids) + 1
    uniform_weight = total_vol / n_cells

    sys.stderr.write(
        f"[ecm_coupler] ecm_cell_map.csv is newer than ecm_mapping.csv — "
        f"regenerating mapping ({n_regions}×{n_axial}×{n_radial} zones) ...\n"
    )

    # Load optional geometry CSV (from STAR-CCM+ coordinate systems)
    geom_data = {}
    geom_csv = os.path.join(os.path.dirname(os.path.abspath(mapping_path)),
                            "ecm_region_geometry.csv")
    geom_csv_env = os.environ.get("ECM_REGION_GEOMETRY_CSV", "").strip()
    if geom_csv_env:
        geom_csv = geom_csv_env
    if os.path.exists(geom_csv):
        try:
            geom_data = _read_region_geometry_csv(geom_csv)
            sys.stderr.write(
                f"[ecm_coupler] Loaded region geometry from {geom_csv}: "
                f"{len(geom_data)} region(s)\n"
            )
        except Exception as e:
            sys.stderr.write(f"[ecm_coupler] WARN: could not read {geom_csv}: {e}\n")

    # Compute per-region cylinder axis using geometry CSV or PCA fallback.
    region_center = {}
    region_axis = {}
    for r_idx in range(n_regions):
        r_xs = [x for x, ri in zip(xs_raw, region_ids) if ri == r_idx]
        r_ys = [y for y, ri in zip(ys_raw, region_ids) if ri == r_idx]
        r_zs = [z for z, ri in zip(zs_raw, region_ids) if ri == r_idx]
        if not r_xs:
            region_center[r_idx] = (0.0, 0.0, 0.0)
            region_axis[r_idx] = (1.0, 0.0, 0.0)
            continue

        if r_idx in geom_data:
            gd = geom_data[r_idx]
            region_center[r_idx] = gd["origin"]
            region_axis[r_idx] = gd["axis"]
            source = "geometry CSV"
        else:
            center, axis = _pca_cylinder_axis(r_xs, r_ys, r_zs)
            region_center[r_idx] = center
            region_axis[r_idx] = axis
            source = "PCA"

        c = region_center[r_idx]
        a = region_axis[r_idx]
        sys.stderr.write(
            f"[ecm_coupler] Region {r_idx}: {len(r_xs)} cells, "
            f"center=({c[0]:.6f}, {c[1]:.6f}, {c[2]:.6f}), "
            f"axis=({a[0]:.6f}, {a[1]:.6f}, {a[2]:.6f}) [{source}]\n"
        )

    # Build cell records with local (axial, radial) coordinates per region.
    cells = []
    for i in range(n_cells):
        ri = region_ids[i]
        c = region_center[ri]
        a = region_axis[ri]
        dx = xs_raw[i] - c[0]
        dy = ys_raw[i] - c[1]
        dz = zs_raw[i] - c[2]
        ax_proj = dx*a[0] + dy*a[1] + dz*a[2]
        px = dx - ax_proj*a[0]
        py = dy - ax_proj*a[1]
        pz = dz - ax_proj*a[2]
        r = math.sqrt(px*px + py*py + pz*pz)
        cells.append({"cid": cell_ids[i], "x": ax_proj, "r": r, "region": ri})

    # Assign zones per region independently so each cylinder gets its own
    # n_axial × n_radial grid.  Zone IDs: region_offset + axial*n_radial + radial,
    # where region_offset = r_idx * n_axial * n_radial.
    n_total_zones = n_regions * n_axial * n_radial
    zone_counts = [0] * n_total_zones
    rows = []
    for r_idx in range(n_regions):
        r_cells = [c for c in cells if c["region"] == r_idx]
        if not r_cells:
            continue
        zone_offset = r_idx * n_axial * n_radial
        cells_by_x = sorted(r_cells, key=lambda cell: (cell["x"], cell["cid"]))
        axial_groups = _partition_groups(len(r_cells), n_axial)
        axial_slices = [cells_by_x[start:stop] for start, stop in axial_groups]
        for axial_bin, axial_cells in enumerate(axial_slices):
            radial_sorted = sorted(axial_cells, key=lambda cell: (cell["r"], cell["cid"]))
            radial_groups = _partition_groups(len(radial_sorted), n_radial)
            for radial_bin, (start, stop) in enumerate(radial_groups):
                zone_id = zone_offset + axial_bin * n_radial + radial_bin
                band = radial_sorted[start:stop]
                zone_counts[zone_id] = len(band)
                for cell in band:
                    rows.append((cell["cid"], zone_id, uniform_weight))

    tmp_path = mapping_path + ".tmp"
    with open(tmp_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["meshKey", "ecmCellId", "weight"])
        writer.writerows(rows)
    os.replace(tmp_path, mapping_path)

    min_c, max_c = min(zone_counts), max(zone_counts)
    sys.stderr.write(
        f"[ecm_coupler] Mapping regenerated: {n_cells} cells → "
        f"{n_total_zones} zones ({n_regions}×{n_axial}×{n_radial}), "
        f"{min_c}–{max_c} cells/zone\n"
    )

    # Invalidate caches so the fresh file is loaded on next access.
    _MAPPING_CACHE.pop(mapping_path, None)
    _PARTITION_VOLUMES_CACHE.pop(mapping_path, None)


def _get_mapping(mapping_file: str):
    _maybe_regen_mapping(mapping_file)
    cached = _MAPPING_CACHE.get(mapping_file)
    if cached is not None:
        return cached
    mapping = load_mapping_table(mapping_file)
    _MAPPING_CACHE[mapping_file] = mapping
    return mapping


def _get_partition_volumes(mapping_file: str, mapping: dict):
    cached = _PARTITION_VOLUMES_CACHE.get(mapping_file)
    if cached is not None:
        return cached
    vols = compute_partition_volumes(mapping)
    _PARTITION_VOLUMES_CACHE[mapping_file] = vols
    return vols

def _resolve_column(lower_cols: dict, candidates: list[str]) -> str:
    for name in candidates:
        key = name.lower()
        if key in lower_cols:
            return lower_cols[key]
    return ""

def load_mapping_table(path: str) -> dict:
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Mapping table is empty: {path}")

    lower_cols = {str(c).strip().lower(): c for c in df.columns}
    mesh_col = _resolve_column(lower_cols, ["meshkey", "mesh_key", "meshid", "mesh_id", "meshcellid"])
    ecm_col = _resolve_column(lower_cols, ["ecmcellid", "ecm_cell_id", "elementid", "element_id"])
    weight_col = _resolve_column(lower_cols, ["weight", "vol", "volume", "vol_m3", "volume_m3"])

    if not mesh_col or not ecm_col or not weight_col:
        raise ValueError(
            "Mapping table must include columns for meshKey, ecmCellId, weight."
        )

    df = df[[mesh_col, ecm_col, weight_col]].dropna()

    ecm_to_mesh = defaultdict(list)
    mesh_to_ecm = defaultdict(list)

    for mesh_key, ecm_id, weight in df.itertuples(index=False, name=None):
        mesh_key = int(mesh_key)
        ecm_id = int(ecm_id)
        weight = float(weight)
        if weight <= 0.0:
            continue
        ecm_to_mesh[ecm_id].append((mesh_key, weight))
        mesh_to_ecm[mesh_key].append((ecm_id, weight))

    return {
        "ecm_to_mesh": dict(ecm_to_mesh),
        "mesh_to_ecm": dict(mesh_to_ecm),
    }

def aggregate_ecm_temperatures(
    keys: list[int],
    temps: list[float],
    mapping: dict,
) -> tuple[list[int], list[float], dict]:
    ecm_to_mesh = mapping["ecm_to_mesh"]

    # If OpenFOAM already pre-aggregated temperatures per ECM element, consume
    # those records directly rather than applying the mesh->element mapping a
    # second time.
    # Shortcut: only fire when the caller has pre-aggregated *every* ECM partition
    # (OpenFOAM C++ path).  A single lumped key (e.g. key=0) must NOT trigger this
    # even if it happens to match a partition ID in the mapping.
    if (keys and len(keys) == len(ecm_to_mesh) and len(keys) == len(temps)
            and all(int(k) in ecm_to_mesh for k in keys)):
        return (
            [int(k) for k in keys],
            [float(t) for t in temps],
            {"missing_mesh": set()},
        )

    key_to_temp = {int(k): float(t) for k, t in zip(keys, temps)}

    ecm_ids = sorted(ecm_to_mesh.keys())
    ecm_temps = []
    missing_mesh = set()

    for ecm_id in ecm_ids:
        sum_w = 0.0
        sum_wt = 0.0
        for mesh_key, weight in ecm_to_mesh[ecm_id]:
            if mesh_key not in key_to_temp:
                missing_mesh.add(mesh_key)
                continue
            sum_w += weight
            sum_wt += weight * key_to_temp[mesh_key]
        if sum_w <= 0.0:
            ecm_temps.append(float(sum(key_to_temp.values()) / max(len(key_to_temp), 1)))
        else:
            ecm_temps.append(sum_wt / sum_w)

    return ecm_ids, ecm_temps, {"missing_mesh": missing_mesh}

def distribute_qvol_to_mesh(
    keys: list[int],
    ecm_ids: list[int],
    qvol_ecm: list[float],
    mapping: dict,
) -> tuple[list[float], dict]:
    ecm_to_mesh = mapping["ecm_to_mesh"]
    mesh_weight = defaultdict(float)
    mesh_accum = defaultdict(float)
    missing_ecm = set()

    ecm_id_to_qvol = {eid: qv for eid, qv in zip(ecm_ids, qvol_ecm)}

    # If output keys are all ECM element IDs (C++ pre-aggregated input),
    # return element-level qVol directly without reverse-mapping through mesh cells.
    if keys and all(k in ecm_id_to_qvol for k in keys):
        q_out = [ecm_id_to_qvol[k] for k in keys]
        return q_out, {"missing_ecm": missing_ecm, "missing_mesh": []}

    for ecm_id, qvol in zip(ecm_ids, qvol_ecm):
        if ecm_id not in ecm_to_mesh:
            missing_ecm.add(ecm_id)
            continue
        for mesh_key, weight in ecm_to_mesh[ecm_id]:
            mesh_accum[mesh_key] += float(qvol) * weight
            mesh_weight[mesh_key] += weight

    q_out = []
    missing_mesh = []
    for mesh_key in keys:
        w = mesh_weight.get(mesh_key, 0.0)
        if w > 0.0:
            q_out.append(mesh_accum.get(mesh_key, 0.0) / w)
        else:
            q_out.append(0.0)
            missing_mesh.append(mesh_key)

    return q_out, {"missing_ecm": missing_ecm, "missing_mesh": missing_mesh}


def _cellprops_capacity_ah(cellprops_df) -> float:
    if cellprops_df is None or cellprops_df.empty:
        return 9.0
    for col in ("capacity_Ah", "Qnom_Ah"):
        if col in cellprops_df.columns:
            return float(cellprops_df[col].iloc[0])
    return 9.0


def _cellprops_tref_degc(cellprops_df) -> float:
    if cellprops_df is None or cellprops_df.empty:
        return 25.0
    if "T_ref_degC" in cellprops_df.columns:
        return float(cellprops_df["T_ref_degC"].iloc[0])
    return 25.0

def build_synthetic_mapping(
    keys: list[int],
    n_elements: int,
    overlap: float,
) -> dict:
    if n_elements <= 0:
        raise ValueError("Synthetic mapping requires ECM_N_ELEMENTS > 0.")
    overlap = max(0.0, min(float(overlap), 0.49))
    w_primary = 1.0 - overlap
    w_secondary = overlap

    ecm_to_mesh = defaultdict(list)
    mesh_to_ecm = defaultdict(list)

    for idx, mesh_key in enumerate(keys):
        ecm_id = idx % n_elements
        ecm_id2 = (ecm_id + 1) % n_elements
        ecm_to_mesh[ecm_id].append((mesh_key, w_primary))
        mesh_to_ecm[mesh_key].append((ecm_id, w_primary))
        if w_secondary > 0.0:
            ecm_to_mesh[ecm_id2].append((mesh_key, w_secondary))
            mesh_to_ecm[mesh_key].append((ecm_id2, w_secondary))

    return {
        "ecm_to_mesh": dict(ecm_to_mesh),
        "mesh_to_ecm": dict(mesh_to_ecm),
    }

def compute_partition_volumes(mapping: dict) -> dict:
    """Return {ecm_id: total_weight_sum} as a proxy for partition volume [m³]."""
    ecm_to_mesh = mapping["ecm_to_mesh"]
    return {ecm_id: sum(w for _, w in pairs) for ecm_id, pairs in ecm_to_mesh.items()}


def compute_effective_temperature(
    ecm_ids: list[int],
    ecm_temps_k: list[float],
    partition_volumes: dict,
) -> float:
    """Volume-weighted effective temperature for a shared whole-cell ECM state."""
    if not ecm_ids:
        return 0.0
    sum_tv = 0.0
    sum_v = 0.0
    for ecm_id, t_k in zip(ecm_ids, ecm_temps_k):
        vol_i = float(partition_volumes.get(ecm_id, 0.0))
        sum_tv += vol_i * float(t_k)
        sum_v += vol_i
    if sum_v <= 1.0e-20:
        return float(sum(ecm_temps_k) / max(len(ecm_temps_k), 1))
    return sum_tv / sum_v


def compute_effective_temperature_from_mesh(
    keys: list[int],
    temps_k: list[float],
    mapping: dict,
) -> float:
    """
    Direct mesh-level effective temperature for shared-state mode.

    Uses the summed outgoing mapping weights for each mesh cell as a proxy
    for active volume, so the shared ECM state is driven by the same mesh
    population as the distributed source application rather than by a
    partition-average-of-averages.
    """
    mesh_to_ecm = mapping["mesh_to_ecm"]
    sum_tv = 0.0
    sum_v = 0.0
    for key, t_k in zip(keys, temps_k):
        vol_i = sum(float(w) for _, w in mesh_to_ecm.get(int(key), []))
        if vol_i <= 0.0:
            continue
        sum_tv += vol_i * float(t_k)
        sum_v += vol_i
    if sum_v <= 1.0e-20:
        return float(sum(temps_k) / max(len(temps_k), 1))
    return sum_tv / sum_v


def smooth_partition_qvol(
    ecm_ids: list[int],
    qvol_ecm: list[float],
    partition_volumes: dict,
    axial_count: int,
    radial_count: int,
    passes: int,
    blend: float,
) -> list[float]:
    """
    Blend partition heat densities across a logical axial×radial grid.

    The smoothing is conservative at the whole-cell level: after each pass,
    the weighted total heat (sum(qVol_i * vol_i)) is rescaled back to the
    pre-smoothing value.
    """
    if passes <= 0 or blend <= 0.0:
        return list(qvol_ecm)
    if axial_count <= 0 or radial_count <= 0:
        return list(qvol_ecm)
    if axial_count * radial_count != len(ecm_ids):
        sys.stderr.write(
            "[ecm_coupler] WARN: skipping ECM spatial smoothing because "
            f"axial_count*radial_count={axial_count * radial_count} does not match "
            f"nPartitions={len(ecm_ids)}.\n"
        )
        return list(qvol_ecm)

    blend = max(0.0, min(float(blend), 1.0))
    q_map = {int(eid): float(qv) for eid, qv in zip(ecm_ids, qvol_ecm)}
    vol_map = {int(eid): float(partition_volumes.get(eid, 1.0)) for eid in ecm_ids}

    def neighbors(index: int) -> list[int]:
        axial_i = index // radial_count
        radial_i = index % radial_count
        nbrs = []
        if radial_i > 0:
            nbrs.append(index - 1)
        if radial_i + 1 < radial_count:
            nbrs.append(index + 1)
        if axial_i > 0:
            nbrs.append(index - radial_count)
        if axial_i + 1 < axial_count:
            nbrs.append(index + radial_count)
        return nbrs

    for _ in range(int(passes)):
        q_before = dict(q_map)
        total_before = sum(q_before[eid] * vol_map[eid] for eid in ecm_ids)
        q_after = {}

        for grid_idx, eid in enumerate(ecm_ids):
            nbr_ids = [ecm_ids[n_idx] for n_idx in neighbors(grid_idx)]
            if not nbr_ids:
                q_after[eid] = q_before[eid]
                continue
            nbr_avg = sum(q_before[nid] for nid in nbr_ids) / float(len(nbr_ids))
            q_after[eid] = (1.0 - blend) * q_before[eid] + blend * nbr_avg

        total_after = sum(q_after[eid] * vol_map[eid] for eid in ecm_ids)
        if abs(total_after) > 1e-20:
            scale = total_before / total_after
            for eid in q_after:
                q_after[eid] = max(0.0, q_after[eid] * scale)
        else:
            for eid in q_after:
                q_after[eid] = max(0.0, q_after[eid])

        q_map = q_after

    return [q_map[eid] for eid in ecm_ids]


def run_ecm_step_per_partition(
    ecm_ids: list,
    ecm_temps_K: list,
    dt_s: float,
    current_a: float,
    partition_states: dict,
    partition_volumes: dict,
    params_df,
    cellprops_df,
    lookup_cache: dict,
) -> tuple:
    """
    Run real ecm_step for each partition independently.

    Each partition runs the ECM at the full cell current so that irreversible
    and reversible heat both scale linearly with vol_frac.  The full-cell Q_GEN
    is then multiplied by vol_frac to obtain the zone's share of the heat.
    Capacity is kept at the full-cell value so that SOC drains at the correct
    rate (I_full / C_full) in every zone.

    Returns
    -------
    qvol_ecm  : list[float]  W/m³ per partition
    next_states : dict       updated state keyed by ecm_id
    """
    total_vol = sum(partition_volumes.values()) or 1.0
    capacity_total = _cellprops_capacity_ah(cellprops_df)

    qvol_ecm = []
    next_states = {}

    for ecm_id, T_K in zip(ecm_ids, ecm_temps_K):
        vol_i = partition_volumes.get(ecm_id, total_vol / max(len(ecm_ids), 1))
        vol_frac = vol_i / total_vol

        # Use full cell current and capacity so that:
        #   q_ir = I²×R0 and q_rev = I×T×dU/dT both scale correctly by vol_frac
        #   after the output scaling below (Fix 2-B).
        scaled_cellprops = cellprops_df.copy() if not cellprops_df.empty else pd.DataFrame(
            [{"capacity_Ah": capacity_total, "Qnom_Ah": capacity_total, "T_ref_degC": 25.0}]
        )
        if not scaled_cellprops.empty:
            scaled_cellprops = scaled_cellprops.copy()
            scaled_cellprops["capacity_Ah"] = capacity_total
            if "Qnom_Ah" in scaled_cellprops.columns:
                scaled_cellprops["Qnom_Ah"] = capacity_total

        pstate = partition_states.get(str(ecm_id), {})
        q_ah = float(pstate.get("q_ah", 0.0))
        v_rc = np.array(pstate.get("v_rc", [0.0, 0.0]), dtype=float)
        hysteresis = float(pstate.get("hysteresis", 0.0))
        T_degC = T_K - 273.15

        state_next, q_ah_next, outputs = _ecm_step_fn(
            dt_s=dt_s,
            current_a=float(current_a),   # full cell current (not scaled by vol_frac)
            q_ah=q_ah,
            v_rc=v_rc,
            hysteresis=hysteresis,
            T_cell_degC=T_degC,
            params_df=params_df,
            cellprops_df=scaled_cellprops,
            lookup_cache=lookup_cache,
        )

        # Zone heat = full-cell Q_GEN × vol_frac (linear scaling, always positive).
        q_gen_w = float(outputs.get("Q_GEN", 0.0)) * vol_frac
        # Convert zone heat to volumetric source [W/m³].
        qvol_i = q_gen_w / vol_i if vol_i > 1e-20 else 0.0
        qvol_ecm.append(qvol_i)

        next_states[str(ecm_id)] = {
            "q_ah": float(q_ah_next),
            "v_rc": list(state_next.get("V_RC", [0.0, 0.0])),
            "hysteresis": float(state_next.get("H", 0.0)),
        }

    return qvol_ecm, next_states


def run_ecm_step_parallel_2rc(
    ecm_ids: list,
    ecm_temps_k: list,
    dt_s: float,
    current_a: float,
    partition_states: dict,
    partition_volumes: dict,
    params_df,
    cellprops_df,
    lookup_cache: dict,
    total_vol_override: float = 0.0,
) -> tuple:
    """
    Run one step of the parallel-2RC ECM using the client-supplied
    parallel_2rc_step function from ecm_step.py.

    All thermal zones are treated as electrically parallel branches sharing a
    common terminal voltage.  Branch currents are solved analytically from
    per-zone temperature-dependent impedance via KCL/KVL.

    Sign convention follows ecm_step.py demo: positive pack_current_a is
    passed directly from the Java macro (Java positive = discharge).

    total_vol_override : float
        Actual jellyRoll volume [m³].  When the mapping file uses unit weights
        (weight = 1.0 per cell), partition_volumes holds cell counts, not m³.
        Providing the real volume allows correct W/m³ computation.
        If 0.0, the raw partition_volumes sums are used as-is (STAR-CCM+ uses
        actual volumes as weights so this is not needed there).

    Returns
    -------
    qvol_ecm    : list[float]  W/m³ per zone
    next_states : dict         updated state keyed by str(ecm_id)
    diag        : dict         diagnostic quantities
    """
    if parallel_2rc_step is None or soc_to_q_ah is None or q_ah_to_soc is None:
        raise RuntimeError(
            "parallel2rc mode requires parallel_2rc_step, soc_to_q_ah, q_ah_to_soc "
            "from ecm_step.py — import failed"
        )

    n = len(ecm_ids)
    if n == 0:
        return [], {}, {"mode": "parallel2rc", "Q_total_W": 0.0, "n_partitions": 0}

    total_vol_units = sum(partition_volumes.values()) or 1.0
    if total_vol_override > 0.0:
        vol_scale = total_vol_override / total_vol_units
    else:
        vol_scale = 1.0
    total_vol = total_vol_units * vol_scale

    q_nom_full = _cellprops_capacity_ah(cellprops_df)
    q_nom_slice = q_nom_full / float(n)

    # Scale cellprops for n equal parallel slices, matching initialize_parallel_slices.
    scaled_cellprops = cellprops_df.copy()
    for col in ("Qnom_Ah", "mass_g", "Cp_cell_J_K-1", "Asurf_m2"):
        if col in scaled_cellprops.columns:
            scaled_cellprops.loc[:, col] = float(scaled_cellprops[col].iloc[0]) / float(n)

    # Assemble per-slice state arrays (N,) from stored partition_states.
    # Default q_ah = soc_to_q_ah(1.0, q_nom_slice) = 0.0  →  SOC = 1 (full cell).
    q_ah_arr = np.empty(n, dtype=float)
    v_rc_arr = np.zeros((n, 2), dtype=float)
    h_arr = np.zeros(n, dtype=float)
    T_arr = np.array([T_k - 273.15 for T_k in ecm_temps_k], dtype=float)

    for i, ecm_id in enumerate(ecm_ids):
        pstate = partition_states.get(str(ecm_id), {})
        q_ah_arr[i] = float(pstate.get("q_ah", soc_to_q_ah(1.0, q_nom_slice)))
        v_rc_i = pstate.get("v_rc", [0.0, 0.0])
        v_rc_arr[i, 0] = float(v_rc_i[0])
        v_rc_arr[i, 1] = float(v_rc_i[1]) if len(v_rc_i) > 1 else 0.0
        h_arr[i] = float(pstate.get("hysteresis", 0.0))

    # Advance all parallel branches one step.
    # pack_current_a follows the demo sign convention (positive passed directly).
    state_next, q_ah_next, outputs = parallel_2rc_step(
        dt_s=dt_s,
        pack_current_a=float(current_a),
        q_ah=q_ah_arr,
        v_rc=v_rc_arr,
        hysteresis=h_arr,
        T_cell_degC=T_arr,
        params_df=params_df,
        cellprops_df=scaled_cellprops,
        n_parallel=n,
        lookup_cache=lookup_cache,
    )

    # Per-zone heat [W] → volumetric source [W/m³].
    q_gen_arr = np.asarray(outputs["Q_GEN"], dtype=float)   # W per slice
    v_rc_next = state_next["V_RC"]                           # (n, 2)
    h_next = state_next["H"]                                 # (n,)

    qvol_ecm = []
    next_states = {}
    for i, ecm_id in enumerate(ecm_ids):
        vol_i = float(partition_volumes.get(ecm_id, total_vol_units / max(n, 1))) * vol_scale
        qvol_i = max(0.0, float(q_gen_arr[i])) / vol_i if vol_i > 1e-20 else 0.0
        qvol_ecm.append(qvol_i)
        next_states[str(ecm_id)] = {
            "q_ah": float(q_ah_next[i]),
            "v_rc": [float(v_rc_next[i, 0]), float(v_rc_next[i, 1])],
            "hysteresis": float(h_next[i]),
        }

    # Diagnostics.
    q_total = float(np.sum(q_gen_arr))
    soc_arr = np.asarray(outputs.get("SOC", q_ah_to_soc(q_ah_next, q_nom_slice)), dtype=float)
    i_branch = np.asarray(outputs.get("I_BRANCH", np.full(n, current_a / n)), dtype=float)
    v_terminal = float(outputs.get("V_TERMINAL", 0.0))
    diag = {
        "mode": "parallel2rc",
        "Q_total_W": q_total,
        "T_eff_K": float(np.mean(ecm_temps_k)),
        "n_partitions": n,
        "V_common_V": v_terminal,
        "V_branch_min_V": v_terminal,
        "V_branch_max_V": v_terminal,
        "I_BRANCH_min_A": float(np.min(i_branch)),
        "I_BRANCH_max_A": float(np.max(i_branch)),
        "I_branch_sum_A": float(np.sum(i_branch)),
        "SOC_mean": float(np.mean(soc_arr)),
        "SOC_min": float(np.min(soc_arr)),
        "SOC_max": float(np.max(soc_arr)),
        "current_balance_residual": float(outputs.get("CURRENT_BALANCE_RESIDUAL", 0.0)),
    }

    return qvol_ecm, next_states, diag


def run_ecm_step_shared_state(
    ecm_ids: list[int],
    t_eff_k: float,
    dt_s: float,
    current_a: float,
    shared_state: dict,
    partition_volumes: dict,
    params_df,
    cellprops_df,
    lookup_cache: dict,
    total_vol_override: float = 0.0,
    lambda_q: float = 1.0,
    lambda_r0: float = 1.0,
) -> tuple[list[float], dict, dict]:
    """
    Run one whole-cell ECM state and distribute the resulting total heat
    uniformly as a volumetric source over the active volume.
    """
    if total_vol_override > 0.0:
        total_vol = total_vol_override
    else:
        total_vol = sum(partition_volumes.values()) or 1.0

    q_ah = float(shared_state.get("q_ah", 0.0))
    v_rc = np.array(shared_state.get("v_rc", [0.0, 0.0]), dtype=float)
    hysteresis = float(shared_state.get("hysteresis", 0.0))

    state_next, q_ah_next, outputs = _ecm_step_fn(
        dt_s=dt_s,
        current_a=current_a,
        q_ah=q_ah,
        v_rc=v_rc,
        hysteresis=hysteresis,
        T_cell_degC=t_eff_k - 273.15,
        params_df=params_df,
        cellprops_df=cellprops_df,
        lookup_cache=lookup_cache,
        lambda_Q=float(lambda_q),
        lambda_R=float(lambda_r0),
    )

    h_next = float(state_next.get("H", 0.0))
    params = _ecm_get_params(
        lookup_cache,
        q_ah_next,
        t_eff_k - 273.15,
        lambda_Q=float(lambda_q),
        lambda_R=float(lambda_r0),
    )
    v_ocv_avg = 0.5 * (float(params["V_OCV_CH"]) + float(params["V_OCV_DCH"]))
    # In the outer coupling convention, discharge current drives H -> +1,
    # so H=+1 must select the discharge OCV branch.
    v_ocv = (
        0.5 * (1.0 + h_next) * float(params["V_OCV_DCH"])
        + 0.5 * (1.0 - h_next) * float(params["V_OCV_CH"])
    )
    v_op = float(outputs.get("V_OP", 0.0))
    v_t_raw = v_ocv + v_op
    q_ir = current_a * (v_t_raw - v_ocv)
    q_hys = current_a * (v_ocv - v_ocv_avg)
    q_rev = float(outputs.get("Q_REV", 0.0))
    q_total_w = q_ir + q_hys + q_rev
    qvol_uniform = q_total_w / total_vol if total_vol > 1.0e-20 else 0.0
    qvol_ecm = [qvol_uniform for _ in ecm_ids]
    next_state = {
        "q_ah": float(q_ah_next),
        "v_rc": list(state_next.get("V_RC", [0.0, 0.0])),
        "hysteresis": h_next,
    }
    # Keep sharedState terminal voltage consistent with the distributed
    # parallelBranches "common terminal voltage" sign convention used in this repo.
    v_common = v_ocv - v_op
    diag = {
        "mode": "sharedState",
        "T_eff_K": float(t_eff_k),
        "Q_total_W": float(q_total_w),
        "Q_IR_W": float(q_ir),
        "Q_HYS_W": float(q_hys),
        "Q_REV_W": float(q_rev),
        "qVol_uniform_Wm3": float(qvol_uniform),
        "V_common_V": float(v_common),
        "V_branch_min_V": float(v_t_raw),
        "V_branch_max_V": float(v_t_raw),
        "lambda_Q": float(lambda_q),
        "lambda_R0": float(lambda_r0),
        "n_partitions": int(len(ecm_ids)),
        "state_soc": float(q_ah_next / max(float(cellprops_df["Qnom_Ah"].iloc[0]), 1.0e-12)),
        "state_q_ah": float(q_ah_next),
        "state_hysteresis": float(h_next),
        "state_v_rc1": float(next_state["v_rc"][0]) if next_state["v_rc"] else 0.0,
        "state_v_rc2": float(next_state["v_rc"][1]) if len(next_state["v_rc"]) > 1 else 0.0,
        "V_OCV_V": float(v_ocv),
        "V_OCV_avg_V": float(v_ocv_avg),
        "V_T_V": float(v_t_raw),
        "V_OP_V": float(v_op),
        "R0_Ohm": float(params["R0"]) * float(lambda_r0),
        "R1_Ohm": float(params["R1"]),
        "R2_Ohm": float(params["R2"]),
        "C1_F": float(params["C1"]),
        "C2_F": float(params["C2"]),
        "dUdT_VK": float(params["DUDT"]),
    }
    return qvol_ecm, next_state, diag


def _evaluate_ecm_branch(
    *,
    dt_s: float,
    current_a: float,
    q_ah: float,
    v_rc: np.ndarray,
    hysteresis: float,
    t_cell_k: float,
    capacity_ah: float,
    t_ref_degc: float,
    lookup_cache: dict,
    resistance_scale: float,
    lambda_q: float,
    lambda_r0: float,
) -> tuple[dict, float, dict, dict]:
    """Evaluate one ECM branch with scaled capacity and resistance."""
    capacity_ah = max(float(capacity_ah), 1.0e-12)
    t_cell_degc = float(t_cell_k) - 273.15
    temp_shift = t_cell_degc - float(t_ref_degc)

    q_ah_next = float(q_ah) + float(current_a) * float(dt_s) / 3600.0
    q_ah_next = max(0.0, min(q_ah_next, capacity_ah))
    if _ecm_get_params is None:
        raise RuntimeError("parallelBranches requires ecm_step parameter lookup support")

    # Scale branch q_ah back to full-cell coordinates for parameter lookup.
    # q_ah_next tracks branch charge (= total_q_ah / N); the params table is
    # indexed by total-cell Q_Ah, so multiply by resistance_scale (= N = 1/vol_frac).
    params = _ecm_get_params(
        lookup_cache,
        q_ah_next * resistance_scale,
        t_cell_degc,
        lambda_Q=float(lambda_q),
        lambda_R=1.0,
    )

    r0 = max(1.0e-9, float(params["R0"]) * resistance_scale * float(lambda_r0))
    r1 = max(1.0e-9, float(params["R1"]) * resistance_scale)
    r2 = max(1.0e-9, float(params["R2"]) * resistance_scale)
    # Use unscaled R for time constants: tau = R_cell * C_cell.
    # r1/r2 carry resistance_scale (= 1/vol_frac) for voltage correctness,
    # but the physical RC time constant must not be scaled by branch count.
    tau1 = max(float(params["R1"]) * float(params["C1"]), 1.0e-9)
    tau2 = max(float(params["R2"]) * float(params["C2"]), 1.0e-9)
    gamma = float(params["GAMMA"])

    v_rc = np.asarray(v_rc, dtype=float)
    a1 = math.exp(-float(dt_s) / tau1)
    a2 = math.exp(-float(dt_s) / tau2)
    v_rc1_next = a1 * float(v_rc[0]) + (1.0 - a1) * r1 * float(current_a)
    v_rc2_next = a2 * float(v_rc[1]) + (1.0 - a2) * r2 * float(current_a)

    i_n = float(current_a) / (3600.0 * capacity_ah) if capacity_ah > 0.0 else 0.0
    h_next = float(hysteresis) + float(dt_s) * gamma * abs(i_n) * (np.sign(float(current_a)) - float(hysteresis))
    h_next = max(-1.0, min(h_next, 1.0))

    # In the outer coupling convention, discharge current drives H -> +1,
    # so H=+1 must select the discharge OCV branch.
    ocv_v = (
        0.5 * (1.0 + h_next) * float(params["V_OCV_DCH"])
        + 0.5 * (1.0 - h_next) * float(params["V_OCV_CH"])
    )
    v_ocv_avg = 0.5 * (float(params["V_OCV_CH"]) + float(params["V_OCV_DCH"]))
    v_t = ocv_v + r0 * float(current_a) + v_rc1_next + v_rc2_next
    t_k = t_cell_degc + 273.15
    q_ir = float(current_a) * (v_t - ocv_v)
    q_hys = float(current_a) * (ocv_v - v_ocv_avg)
    q_rev = float(current_a) * t_k * float(params["DUDT"])
    q_gen = q_ir + q_hys + q_rev

    state_next = {"V_RC": [v_rc1_next, v_rc2_next], "H": h_next}
    outputs = {"Q_GEN": q_gen, "V_T": v_t}
    linear = {
        "ocv_v": ocv_v,
        "r0": r0,
        "r1": r1,
        "r2": r2,
        "a1": a1,
        "a2": a2,
        "gamma": gamma,
        "h_next": h_next,
        "v_intercept": ocv_v - a1 * float(v_rc[0]) - a2 * float(v_rc[1]),
        "r_eff": r0 + (1.0 - a1) * r1 + (1.0 - a2) * r2,
    }
    return state_next, q_ah_next, outputs, linear


def run_ecm_step_parallel_branches(
    ecm_ids: list[int],
    ecm_temps_k: list[float],
    dt_s: float,
    current_a: float,
    partition_states: dict,
    partition_volumes: dict,
    cellprops_df,
    lookup_cache: dict,
    global_state_defaults: dict | None = None,
    lambda_q: float = 1.0,
    lambda_r0: float = 1.0,
    shared_soc: bool = False,
) -> tuple[list[float], dict, dict]:
    """
    Parallel-branch distributed ECM.

    Each partition is a branch with:
    - capacity scaled by partition volume fraction
    - resistances scaled inversely with partition volume fraction
    - common terminal voltage across branches
    - branch currents summing to the applied current
    """
    total_vol = sum(partition_volumes.values()) or 1.0
    capacity_total = _cellprops_capacity_ah(cellprops_df)
    t_ref_degc = _cellprops_tref_degc(cellprops_df)

    branch_meta = []
    for ecm_id, t_k in zip(ecm_ids, ecm_temps_k):
        vol_i = float(partition_volumes.get(ecm_id, total_vol / max(len(ecm_ids), 1)))
        vol_frac = max(vol_i / total_vol, 1.0e-12)
        resistance_scale = 1.0 / vol_frac
        pstate = partition_states.get(str(ecm_id), {})
        if pstate:
            q_ah = float(pstate.get("q_ah", 0.0))
            v_rc = np.array(pstate.get("v_rc", [0.0, 0.0]), dtype=float)
            hysteresis = float(pstate.get("hysteresis", 0.0))
        else:
            defaults = global_state_defaults or {}
            q_ah = float(defaults.get("q_ah", 0.0)) * vol_frac
            v_rc = np.array(defaults.get("v_rc", [0.0, 0.0]), dtype=float)
            hysteresis = float(defaults.get("hysteresis", 0.0))
        _, _, _, linear = _evaluate_ecm_branch(
            dt_s=dt_s,
            current_a=0.0 if abs(current_a) <= 1.0e-15 else current_a,
            q_ah=q_ah,
            v_rc=v_rc,
            hysteresis=hysteresis,
            t_cell_k=t_k,
            capacity_ah=capacity_total * vol_frac,
            t_ref_degc=t_ref_degc,
            lookup_cache=lookup_cache,
            resistance_scale=resistance_scale,
            lambda_q=lambda_q,
            lambda_r0=lambda_r0,
        )
        branch_meta.append(
            {
                "ecm_id": int(ecm_id),
                "t_k": float(t_k),
                "vol_i": vol_i,
                "vol_frac": vol_frac,
                "capacity_ah": capacity_total * vol_frac,
                "q_ah": q_ah,
                "v_rc": v_rc,
                "hysteresis": hysteresis,
                "resistance_scale": resistance_scale,
                "linear": linear,
            }
        )

    if abs(current_a) <= 1.0e-15:
        branch_currents = [0.0 for _ in branch_meta]
        v_common = float(np.mean([b["linear"]["v_intercept"] for b in branch_meta])) if branch_meta else 0.0
    else:
        sign = 1.0 if current_a > 0.0 else -1.0

        def current_sum(v_common: float) -> tuple[float, list[float]]:
            currents = []
            for b in branch_meta:
                e_i = b["linear"]["v_intercept"]
                r_i = max(float(b["linear"]["r_eff"]), 1.0e-12)
                i_i = (e_i - v_common) / r_i
                if sign > 0.0:
                    i_i = max(0.0, i_i)
                else:
                    i_i = min(0.0, i_i)
                currents.append(float(i_i))
            return float(sum(currents)), currents

        e_vals = [b["linear"]["v_intercept"] for b in branch_meta]
        r_vals = [max(float(b["linear"]["r_eff"]), 1.0e-12) for b in branch_meta]
        v_hi = max(e_vals) + abs(current_a) * max(r_vals)
        v_lo = min(e_vals) - abs(current_a) * max(r_vals)
        sum_lo, currents_lo = current_sum(v_lo)
        sum_hi, currents_hi = current_sum(v_hi)
        for _ in range(20):
            if sum_lo >= current_a >= sum_hi or sum_hi >= current_a >= sum_lo:
                break
            span = max(r_vals) * max(abs(current_a), 1.0)
            v_lo -= span
            v_hi += span
            sum_lo, currents_lo = current_sum(v_lo)
            sum_hi, currents_hi = current_sum(v_hi)
        branch_currents = currents_lo
        v_common = v_lo
        for _ in range(50):
            v_mid = 0.5 * (v_lo + v_hi)
            sum_mid, currents_mid = current_sum(v_mid)
            if abs(sum_mid - current_a) <= max(1.0e-9, 1.0e-8 * abs(current_a)):
                branch_currents = currents_mid
                v_common = v_mid
                break
            if sign > 0.0:
                if sum_mid > current_a:
                    v_lo = v_mid
                else:
                    v_hi = v_mid
            else:
                if sum_mid > current_a:
                    v_lo = v_mid
                else:
                    v_hi = v_mid
            branch_currents = currents_mid
            v_common = v_mid

    qvol_ecm = []
    next_states = {}
    branch_voltages = []
    q_ah_next_list = []
    for b, i_i in zip(branch_meta, branch_currents):
        state_next, q_ah_next, outputs, _ = _evaluate_ecm_branch(
            dt_s=dt_s,
            current_a=i_i,
            q_ah=b["q_ah"],
            v_rc=b["v_rc"],
            hysteresis=b["hysteresis"],
            t_cell_k=b["t_k"],
            capacity_ah=b["capacity_ah"],
            t_ref_degc=t_ref_degc,
            lookup_cache=lookup_cache,
            resistance_scale=b["resistance_scale"],
            lambda_q=lambda_q,
            lambda_r0=lambda_r0,
        )
        q_gen_w = float(outputs.get("Q_GEN", 0.0))
        qvol_i = q_gen_w / b["vol_i"] if b["vol_i"] > 1.0e-20 else 0.0
        qvol_ecm.append(qvol_i)
        branch_voltages.append(float(outputs.get("V_T", 0.0)))
        q_ah_next_list.append(float(q_ah_next))
        next_states[str(b["ecm_id"])] = {
            "q_ah": float(q_ah_next),
            "v_rc": list(state_next.get("V_RC", [0.0, 0.0])),
            "hysteresis": float(state_next.get("H", 0.0)),
        }

    # Shared-SOC variant: enforce global charge conservation by distributing
    # q_ah proportionally to zone volume fractions. v_rc and hysteresis remain
    # per-zone (local polarisation history is spatially distributed).
    # Correct formula: q_ah_cell = sum(q_ah_zone_i) [since sum(vol_frac_i)=1],
    # then q_ah_zone_i = q_ah_cell * vol_frac_i, so all zones see the same SOC:
    # q_ah_zone_i / (capacity_total * vol_frac_i) = q_ah_cell / capacity_total.
    # Arithmetic mean would be wrong for non-uniform zone volumes.
    if shared_soc:
        q_ah_cell_new = sum(q_ah_next_list) if q_ah_next_list else 0.0
        q_ah_cell_new = max(0.0, min(q_ah_cell_new, capacity_total))
        for b in branch_meta:
            next_states[str(b["ecm_id"])]["q_ah"] = q_ah_cell_new * b["vol_frac"]

    q_total_w = float(sum(q * b["vol_i"] for q, b in zip(qvol_ecm, branch_meta)))
    diag = {
        "mode": "parallelBranchesSharedSOC" if shared_soc else "parallelBranches",
        "Q_total_W": q_total_w,
        "T_eff_K": float(compute_effective_temperature(ecm_ids, ecm_temps_k, partition_volumes)),
        "V_common_V": float(v_common),
        "V_branch_min_V": float(min(branch_voltages)) if branch_voltages else 0.0,
        "V_branch_max_V": float(max(branch_voltages)) if branch_voltages else 0.0,
        "I_branch_min_A": float(min(branch_currents)) if branch_currents else 0.0,
        "I_branch_max_A": float(max(branch_currents)) if branch_currents else 0.0,
        "I_branch_sum_A": float(sum(branch_currents)),
        "lambda_Q": float(lambda_q),
        "lambda_R0": float(lambda_r0),
        "n_partitions": int(len(ecm_ids)),
    }
    return qvol_ecm, next_states, diag


def run_ecm_step_multi_cell_parallel(
    ecm_ids: list[int],
    ecm_temps_k: list[float],
    dt_s: float,
    current_a: float,
    mc_state: dict,
    partition_volumes: dict,
    params_df,
    cellprops_df,
    lookup_cache: dict,
    total_vol_override: float = 0.0,
    M: int = 1,
) -> tuple:
    """
    Run one step of the multi-cell parallel ECM using multi_cell_parallel_step.

    M physically independent battery cells, each divided into n_parallel spatial
    zones. All zones within a cell share one SOC; zone temperatures drive local
    heat generation. All M × n_parallel calculations happen in a single vectorised
    call — no Python loop over cells.

    Zone ordering: zones 0 … n_parallel-1 belong to cell 0,
                   zones n_parallel … 2*n_parallel-1 belong to cell 1, etc.
    Controlled by env ECM_N_CELLS (default 1).

    Parameters
    ----------
    ecm_ids           : list of ECM zone IDs (length M * n_parallel)
    ecm_temps_k       : zone temperatures [K] (same order as ecm_ids)
    dt_s              : timestep [s]
    current_a         : discharge current [A] (positive = discharge), same for all cells
    mc_state          : persistent state dict (loaded/saved via ecm_state.json)
    partition_volumes : dict ecm_id → volume [m³] or weight
    params_df         : ECM parameter lookup table
    cellprops_df      : cell property table
    lookup_cache      : precomputed parameter cache
    total_vol_override: total jellyRoll volume [m³] (from V_jellyroll_m3 input); if >0
                        overrides sum of partition_volumes for W→W/m³ conversion
    M                 : number of independent battery cells

    Returns
    -------
    qvol_ecm   : list[float]  per-zone volumetric heat source [W/m³], length M*n_parallel
    next_mc_state : dict      updated state (q_ah, v_rc, hysteresis as nested lists)
    diag       : dict         diagnostic quantities
    """
    if multi_cell_parallel_step is None:
        raise RuntimeError(
            "multi_cell_parallel mode requires multi_cell_parallel_step from "
            "ecm_step.py — import failed"
        )

    n_total = len(ecm_ids)
    if n_total == 0:
        return [], {}, {"mode": "multi_cell_parallel", "Q_total_W": 0.0}
    if n_total % M != 0:
        raise ValueError(
            f"multi_cell_parallel: total zones ({n_total}) must be divisible by M={M}"
        )
    n_parallel = n_total // M

    # --- volume scaling (same logic as parallel2rc) ---
    total_vol_units = sum(partition_volumes.values()) or float(n_total)
    if total_vol_override > 0.0:
        vol_scale = total_vol_override / total_vol_units
    else:
        vol_scale = 1.0

    # --- capacity & q_nom per slice ---
    q_nom_full = float(cellprops_df["Qnom_Ah"].iloc[0]) if "Qnom_Ah" in cellprops_df.columns else 5.0
    q_nom_slice = q_nom_full / float(n_parallel)

    # --- restore or initialise state ---
    if "q_ah" in mc_state:
        q_ah = np.array(mc_state["q_ah"], dtype=float).reshape(M, n_parallel)
        v_rc = np.array(mc_state["v_rc"], dtype=float).reshape(M, n_parallel, 2)
        h_arr = np.array(mc_state["hysteresis"], dtype=float).reshape(M, n_parallel)
    else:
        soc_init = float(mc_state.get("soc_init", 1.0))
        q_ah = np.full((M, n_parallel), soc_to_q_ah(soc_init, q_nom_slice), dtype=float)
        v_rc = np.zeros((M, n_parallel, 2), dtype=float)
        h_arr = np.zeros((M, n_parallel), dtype=float)

    # --- temperature matrix (M, n_parallel) ---
    T_degC = (np.array(ecm_temps_k, dtype=float) - 273.15).reshape(M, n_parallel)

    # --- scale cellprops per slice ---
    scaled_cp = cellprops_df.copy()
    for col in ("Qnom_Ah", "mass_g", "Cp_cell_J_K-1", "Asurf_m2"):
        if col in scaled_cp.columns:
            scaled_cp.loc[:, col] = float(scaled_cp[col].iloc[0]) / float(n_parallel)

    # --- advance one step ---
    state_next, q_ah_next, outputs = multi_cell_parallel_step(
        dt_s=dt_s,
        pack_current_a=float(current_a),   # broadcast to all M cells
        q_ah=q_ah,
        v_rc=v_rc,
        hysteresis=h_arr,
        T_cell_degC=T_degC,
        params_df=params_df,
        cellprops_df=scaled_cp,
        n_parallel=n_parallel,
        M=M,
        lookup_cache=lookup_cache,
    )

    # --- enforce per-cell shared SOC: average q_ah across zones within each cell ---
    # All zones of the same physical cell share one SOC; per-zone differences
    # accumulate only due to numerical splitting. Reset them to the cell mean.
    q_ah_cell_mean = np.mean(q_ah_next, axis=1, keepdims=True)   # (M, 1)
    q_ah_next = np.broadcast_to(q_ah_cell_mean, (M, n_parallel)).copy()

    # --- Q_GEN (M, n_parallel) ---
    q_gen_mn = np.asarray(outputs["Q_GEN"], dtype=float)  # (M, n_parallel)

    # --- normalise total Q per cell to lumped reference ---
    Q_ref_per_cell = np.zeros(M, dtype=float)
    if _ecm_step_fn is not None:
        v_rc_mc = np.asarray(state_next["V_RC"], dtype=float)  # (M, n_parallel, 2)
        h_mc    = np.asarray(state_next["H"],    dtype=float)  # (M, n_parallel)
        for m in range(M):
            T_avg_m    = float(np.mean(T_degC[m, :]))
            q_ah_lump  = float(np.mean(q_ah_next[m, :])) * n_parallel  # full-cell units
            v_rc_lump  = np.mean(v_rc_mc[m], axis=0)                   # (2,) zone mean
            h_lump     = float(np.mean(h_mc[m]))
            _, _, out_lump = _ecm_step_fn(
                dt_s=dt_s,
                current_a=float(current_a),
                q_ah=q_ah_lump,
                v_rc=v_rc_lump,
                hysteresis=h_lump,
                T_cell_degC=T_avg_m,
                params_df=params_df,
                cellprops_df=cellprops_df,   # full cell, NOT scaled
                lookup_cache=lookup_cache,
            )
            Q_ref_per_cell[m] = float(out_lump["Q_GEN"])

        for m in range(M):
            Q_raw_m = float(np.sum(q_gen_mn[m, :]))
            Q_ref_m = Q_ref_per_cell[m]
            if Q_raw_m > 1e-10 and Q_ref_m > 0.0:
                q_gen_mn[m, :] *= Q_ref_m / Q_raw_m

    q_gen_flat = q_gen_mn.flatten()                        # (M*n_parallel,)

    qvol_ecm = []
    for i, ecm_id in enumerate(ecm_ids):
        vol_i = float(partition_volumes.get(ecm_id, total_vol_units / max(n_total, 1))) * vol_scale
        qvol_i = max(0.0, float(q_gen_flat[i])) / vol_i if vol_i > 1e-20 else 0.0
        qvol_ecm.append(qvol_i)

    # --- build next state (JSON-serialisable nested lists) ---
    next_mc_state = {
        "q_ah": q_ah_next.tolist(),
        "v_rc": state_next["V_RC"].tolist(),
        "hysteresis": state_next["H"].tolist(),
        "soc_init": float(mc_state.get("soc_init", 1.0)),
    }

    # --- diagnostics ---
    q_total = float(np.sum(q_gen_mn))
    soc_mn = np.asarray(outputs.get("SOC", q_ah_next / q_nom_slice), dtype=float)   # (M, n)
    v_ocv_mn = np.asarray(outputs.get("V_OCV_DCH", outputs.get("V_OCV", np.zeros((M, n_parallel)))), dtype=float)
    v_op_mn  = np.asarray(outputs.get("V_OP", np.zeros((M, n_parallel))), dtype=float)
    v_phys_mn = v_ocv_mn - v_op_mn          # (M, n_parallel)
    v_terminal_per_cell = np.mean(v_phys_mn, axis=1)   # (M,) — per-cell mean terminal V
    i_branch_mn = np.asarray(outputs.get("I_BRANCH", np.full((M, n_parallel), current_a / n_parallel)), dtype=float)

    diag = {
        "mode": "multi_cell_parallel",
        "M_cells": M,
        "n_parallel": n_parallel,
        "n_partitions": n_total,
        "Q_total_W": q_total,
        "Q_ref_W": float(np.sum(Q_ref_per_cell)),
        "T_eff_K": float(np.mean(ecm_temps_k)),
        "T_zone_min_K": float(np.min(ecm_temps_k)),
        "T_zone_max_K": float(np.max(ecm_temps_k)),
        "V_common_V": float(np.mean(v_terminal_per_cell)),
        "V_branch_min_V": float(np.min(v_phys_mn)),
        "V_branch_max_V": float(np.max(v_phys_mn)),
        "SOC_mean": float(np.mean(soc_mn)),
        "SOC_min": float(np.min(soc_mn)),
        "SOC_max": float(np.max(soc_mn)),
        "SOC_per_cell": [float(np.mean(soc_mn[m])) for m in range(M)],
        "I_branch_sum_A": float(np.sum(i_branch_mn)),
    }

    return qvol_ecm, next_mc_state, diag


def run_ecm_step_multi_cell_equal_current(
    ecm_ids: list[int],
    ecm_temps_k: list[float],
    dt_s: float,
    current_a: float,
    mc_state: dict,
    partition_volumes: dict,
    params_df,
    cellprops_df,
    lookup_cache: dict,
    total_vol_override: float = 0.0,
    M: int = 1,
) -> tuple:
    """
    Run one step of the multi-cell equal-current ECM using multi_cell_equal_current_step.

    Like multi_cell_parallel but distributes current equally to all zones (not via KCL).
    Each zone gets I_branch = I_total / n_parallel regardless of R0 or temperature.
    """
    if multi_cell_equal_current_step is None:
        raise RuntimeError(
            "multi_cell_equal_current mode requires multi_cell_equal_current_step from "
            "ecm_step.py — import failed"
        )

    n_total = len(ecm_ids)
    if n_total == 0:
        return [], {}, {"mode": "multi_cell_equal_current", "Q_total_W": 0.0}
    if n_total % M != 0:
        raise ValueError(
            f"multi_cell_equal_current: total zones ({n_total}) must be divisible by M={M}"
        )
    n_parallel = n_total // M

    total_vol_units = sum(partition_volumes.values()) or float(n_total)
    if total_vol_override > 0.0:
        vol_scale = total_vol_override / total_vol_units
    else:
        vol_scale = 1.0

    q_nom_full = float(cellprops_df["Qnom_Ah"].iloc[0]) if "Qnom_Ah" in cellprops_df.columns else 5.0
    q_nom_slice = q_nom_full / float(n_parallel)

    if "q_ah" in mc_state:
        q_ah = np.array(mc_state["q_ah"], dtype=float).reshape(M, n_parallel)
        v_rc = np.array(mc_state["v_rc"], dtype=float).reshape(M, n_parallel, 2)
        h_arr = np.array(mc_state["hysteresis"], dtype=float).reshape(M, n_parallel)
    else:
        soc_init = float(mc_state.get("soc_init", 1.0))
        q_ah = np.full((M, n_parallel), soc_to_q_ah(soc_init, q_nom_slice), dtype=float)
        v_rc = np.zeros((M, n_parallel, 2), dtype=float)
        h_arr = np.zeros((M, n_parallel), dtype=float)

    T_degC = (np.array(ecm_temps_k, dtype=float) - 273.15).reshape(M, n_parallel)

    scaled_cp = cellprops_df.copy()
    for col in ("Qnom_Ah", "mass_g", "Cp_cell_J_K-1", "Asurf_m2"):
        if col in scaled_cp.columns:
            scaled_cp.loc[:, col] = float(scaled_cp[col].iloc[0]) / float(n_parallel)

    state_next, q_ah_next, outputs = multi_cell_equal_current_step(
        dt_s=dt_s,
        pack_current_a=float(current_a),
        q_ah=q_ah,
        v_rc=v_rc,
        hysteresis=h_arr,
        T_cell_degC=T_degC,
        params_df=params_df,
        cellprops_df=scaled_cp,
        n_parallel=n_parallel,
        M=M,
        lookup_cache=lookup_cache,
    )

    q_ah_cell_mean = np.mean(q_ah_next, axis=1, keepdims=True)
    q_ah_next = np.broadcast_to(q_ah_cell_mean, (M, n_parallel)).copy()

    q_gen_mn = np.asarray(outputs["Q_GEN"], dtype=float)
    q_gen_flat = q_gen_mn.flatten()

    qvol_ecm = []
    for i, ecm_id in enumerate(ecm_ids):
        vol_i = float(partition_volumes.get(ecm_id, total_vol_units / max(n_total, 1))) * vol_scale
        qvol_i = max(0.0, float(q_gen_flat[i])) / vol_i if vol_i > 1e-20 else 0.0
        qvol_ecm.append(qvol_i)

    next_mc_state = {
        "q_ah": q_ah_next.tolist(),
        "v_rc": state_next["V_RC"].tolist(),
        "hysteresis": state_next["H"].tolist(),
        "soc_init": float(mc_state.get("soc_init", 1.0)),
    }

    q_total = float(np.sum(q_gen_mn))
    soc_mn = np.asarray(outputs.get("SOC", q_ah_next / q_nom_slice), dtype=float)
    v_ocv_mn = np.asarray(outputs.get("V_OCV_DCH", outputs.get("V_OCV", np.zeros((M, n_parallel)))), dtype=float)
    v_op_mn  = np.asarray(outputs.get("V_OP", np.zeros((M, n_parallel))), dtype=float)
    v_phys_mn = v_ocv_mn - v_op_mn
    v_terminal_per_cell = np.mean(v_phys_mn, axis=1)
    i_branch_mn = np.asarray(outputs.get("I_BRANCH", np.full((M, n_parallel), current_a / n_parallel)), dtype=float)

    diag = {
        "mode": "multi_cell_equal_current",
        "M_cells": M,
        "n_parallel": n_parallel,
        "n_partitions": n_total,
        "Q_total_W": q_total,
        "T_eff_K": float(np.mean(ecm_temps_k)),
        "T_zone_min_K": float(np.min(ecm_temps_k)),
        "T_zone_max_K": float(np.max(ecm_temps_k)),
        "V_common_V": float(np.mean(v_terminal_per_cell)),
        "V_branch_min_V": float(np.min(v_phys_mn)),
        "V_branch_max_V": float(np.max(v_phys_mn)),
        "SOC_mean": float(np.mean(soc_mn)),
        "SOC_min": float(np.min(soc_mn)),
        "SOC_max": float(np.max(soc_mn)),
        "SOC_per_cell": [float(np.mean(soc_mn[m])) for m in range(M)],
        "I_branch_sum_A": float(np.sum(i_branch_mn)),
    }

    return qvol_ecm, next_mc_state, diag


def compute_q_out(h, inputs, keys, temps):
    cell_id = os.environ.get("ECM_CELL_ID", "").strip()
    lumped_output = os.environ.get("ECM_LUMPED_OUTPUT", "").strip().lower()
    active_volume = os.environ.get("ECM_ACTIVE_VOLUME", "").strip()
    state_file = os.environ.get("ECM_STATE_FILE", "ecm_state.json")
    state_reset = os.environ.get("ECM_STATE_RESET", "").strip()
    mapping_file = os.environ.get("ECM_MAPPING_FILE", "").strip()
    mapping_mode = os.environ.get("ECM_MAPPING_MODE", "").strip().lower()
    n_elements_raw = os.environ.get("ECM_N_ELEMENTS", "").strip()
    overlap_raw = os.environ.get("ECM_OVERLAP", "").strip()
    smooth_passes = int(os.environ.get("ECM_Q_SMOOTH_PASSES", "0").strip() or "0")
    smooth_blend = float(os.environ.get("ECM_Q_SMOOTH_BLEND", "0.0").strip() or "0.0")
    smooth_axial = int(os.environ.get("ECM_GRID_AXIAL", "0").strip() or "0")
    smooth_radial = int(os.environ.get("ECM_GRID_RADIAL", "0").strip() or "0")
    distributed_mode = os.environ.get("ECM_DISTRIBUTED_ELECTRICAL_MODE", "sharedState").strip().lower()
    lambda_q_default = _float_env("ECM_LAMBDA_Q", 1.0)
    lambda_r0_default = _float_env("ECM_LAMBDA_R0", 1.0)

    backend_name = os.environ.get("ECM_BACKEND", "mock-inproc").strip()
    vendor_exec = os.environ.get("ECM_VENDOR_EXEC", "").strip()
    vendor_workdir = os.environ.get("ECM_VENDOR_WORKDIR", "").strip() or None
    vendor_state = os.environ.get("ECM_VENDOR_STATE", "").strip() or None

    if lumped_output == "totalpower":
        inputs["lumpedOutput"] = 1.0
    elif lumped_output == "volumetric":
        inputs["lumpedOutput"] = 0.0

    if active_volume:
        try:
            inputs["activeVolume"] = float(active_volume)
        except ValueError:
            raise ValueError(f"Invalid ECM_ACTIVE_VOLUME: {active_volume}")

    lambda_q = float(inputs.get("lambda_Q", inputs.get("lambdaQ", lambda_q_default)))
    lambda_r0 = float(inputs.get("lambda_R0", inputs.get("lambdaR0", lambda_r0_default)))

    # Load params/cellprops (cached across calls in persistent-pipe mode).
    params_df, cellprops_df, lookup_cache, ecm_lookup_cache = _load_runtime_tables()

    backend = get_backend(
        backend_name=backend_name,
        params_df=params_df,
        cellprops_df=cellprops_df,
        lookup_cache=lookup_cache,
        vendor_executable=vendor_exec or None,
        vendor_working_dir=vendor_workdir,
        vendor_state_file=vendor_state,
    )

    mapping = None
    if mapping_file:
        if os.path.exists(mapping_file):
            mapping = _get_mapping(mapping_file)
            if mapping_file not in _ANNOUNCED_MAPPINGS:
                sys.stderr.write(f"[ecm_coupler] Using mapping table: {mapping_file}\n")
                _ANNOUNCED_MAPPINGS.add(mapping_file)
        else:
            mapping_mode = mapping_mode or "synthetic"

    if mapping is None and mapping_mode == "synthetic":
        if not n_elements_raw:
            raise ValueError("ECM_MAPPING_MODE=synthetic requires ECM_N_ELEMENTS.")
        n_elements = int(n_elements_raw)
        overlap = float(overlap_raw) if overlap_raw else 0.3
        mapping = build_synthetic_mapping(keys, n_elements, overlap)
        sys.stderr.write(
            f"[ecm_coupler] Using synthetic mapping: n_elements={n_elements}, overlap={overlap}\n"
        )

    # Call-interval subcycling: ECM_CALL_EVERY_N_STEPS=N fires every N CFD steps.
    # 0 (default) = call every step (legacy behaviour).
    call_every_n = int(os.environ.get("ECM_CALL_EVERY_N_STEPS", "0").strip() or "0")
    interp_mode = os.environ.get("ECM_INTERP_MODE", "linear").strip().lower()

    # State handling
    reset_flag = False
    if state_reset:
        reset_flag = state_reset.lower() in ("1", "true", "yes", "y")
    if float(inputs.get("stateReset", 0.0)) >= 0.5:
        reset_flag = True

    q_nom_ah = _cellprops_capacity_ah(cellprops_df)

    def _first_input_value(*names: str, default: float = 0.0) -> float:
        for name in names:
            if name in inputs:
                try:
                    return float(inputs[name])
                except (TypeError, ValueError):
                    continue
        return float(default)

    def state_defaults():
        q_ah_default = _first_input_value("q_ah_init", "init_q_ah", "q_ah", default=0.0)
        if ("q_ah_init" not in inputs) and ("init_q_ah" not in inputs):
            soc_default = _first_input_value("soc_init", "init_soc", "soc", default=float("nan"))
            if math.isfinite(soc_default) and q_nom_ah > 0.0:
                q_ah_default = max(0.0, min(q_nom_ah, (1.0 - soc_default) * q_nom_ah))
        return {
            "q_ah": float(q_ah_default),
            "v_rc": [
                _first_input_value("v_rc1_init", "init_v_rc1", "v_rc1", default=0.0),
                _first_input_value("v_rc2_init", "init_v_rc2", "v_rc2", default=0.0),
            ],
            "hysteresis": _first_input_value("hysteresis_init", "init_hysteresis", "hysteresis", default=0.0),
        }

    default_state = state_defaults()

    if reset_flag or not os.path.exists(state_file):
        state = state_defaults()
    else:
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            state = state_defaults()

    # Determine whether to fire ECM this step or return cached qVol.
    steps_since_ecm = int(state.get("steps_since_ecm", call_every_n))  # default → fire on first call
    should_fire_ecm = (call_every_n <= 0) or reset_flag or (steps_since_ecm >= call_every_n - 1)

    # Timing policy:
    # - no subcycling (call_every_n <= 0): ECM fires every CFD step, so use the incoming
    #   CFD deltaT directly and ignore any persisted last_ecm_time drift.
    # - subcycling (call_every_n > 0): advance ECM by the total elapsed time since the last
    #   real ECM fire, with a restart/rewind sanity guard.
    last_ecm_time_raw = state.get("last_ecm_time", None)
    has_last_ecm_time = last_ecm_time_raw is not None
    last_ecm_time = float(last_ecm_time_raw) if has_last_ecm_time else (h.time - h.deltaT)
    if call_every_n <= 0:
        dt_for_ecm = h.deltaT
        if has_last_ecm_time:
            dt_drift = abs((h.time - last_ecm_time) - h.deltaT)
            if dt_drift > max(1.0e-9, 10.0 * abs(h.deltaT)):
                sys.stderr.write(
                    "[ecm_coupler] WARN: ignoring persisted last_ecm_time drift in every-step mode: "
                    f"time={h.time:.6f}s last_ecm_time={last_ecm_time:.6f}s "
                    f"deltaT={h.deltaT:.6f}s drift={dt_drift:.6f}s\n"
                )
    else:
        is_first_ecm_call = not has_last_ecm_time
        dt_for_ecm = h.deltaT if is_first_ecm_call else (h.time - last_ecm_time)
        if not is_first_ecm_call and dt_for_ecm <= 0.0:
            sys.stderr.write(
                "[ecm_coupler] WARN: non-positive dt_ecm from persisted state; resetting timing: "
                f"time={h.time:.6f}s last_ecm_time={last_ecm_time:.6f}s "
                f"deltaT={h.deltaT:.6f}s dt_ecm={dt_for_ecm:.6f}s\n"
            )
            dt_for_ecm = h.deltaT
            state.pop("last_ecm_time", None)
            state.pop("prev_ecm_time", None)

    if len(temps) == 0:
        raise ValueError("No temperature records found in ECM input.")

    step_id_for_log = int(getattr(h, "stepId", 0))
    _hlog(
        f"step={step_id_for_log} t={h.time:.6f}s dt={h.deltaT:.6f}s "
        f"n_mesh_cells={len(keys)} T_mesh=[{min(temps):.3f}..{max(temps):.3f}] K "
        f"current_A={inputs.get('current_A', inputs.get('current', 'n/a'))}"
    )

    _t0 = time.perf_counter()
    q_out = []
    if mapping is not None:
        ecm_ids, ecm_temps, mapping_info = aggregate_ecm_temperatures(keys, temps, mapping)
        _hlog(
            f"aggregate done: {len(ecm_ids)} zones in {(time.perf_counter()-_t0)*1e3:.2f} ms | "
            f"T_zone=[{min(ecm_temps):.3f}..{max(ecm_temps):.3f}] K  "
            f"T_zone_mean={sum(ecm_temps)/len(ecm_temps):.3f} K"
        )
        if len(ecm_ids) <= 30:
            for _zi, (_eid, _tz) in enumerate(zip(ecm_ids, ecm_temps)):
                _hlog(f"  zone[{_zi}] id={_eid} T={_tz:.4f} K")
        if mapping_info["missing_mesh"]:
            sys.stderr.write(
                f"[ecm_coupler] WARN: {len(mapping_info['missing_mesh'])} mesh keys in "
                "mapping not present in input; ignoring.\n"
            )

        use_real_ecm = _ECM_STEP_AVAILABLE and os.environ.get("ECM_USE_REAL_STEP", "1").strip() not in ("0", "false", "no")

        if not should_fire_ecm and "last_qvol_by_ecmid" in state:
            # Subcycling: use linear extrapolation from last two ECM fires when available.
            if interp_mode == "linear" and "dqdt_by_ecmid" in state and "last_ecm_time" in state:
                last_ecm_time = float(state.get("last_ecm_time", h.time - h.deltaT))
                dt_since_ecm = max(0.0, h.time - last_ecm_time)
                cached = state["last_qvol_by_ecmid"]
                dqdt = state.get("dqdt_by_ecmid", {})
                qvol_ecm = []
                for eid in ecm_ids:
                    q_last = float(cached.get(str(eid), 0.0))
                    dq_dt = float(dqdt.get(str(eid), 0.0))
                    q_now = q_last + dq_dt * dt_since_ecm
                    qvol_ecm.append(max(0.0, q_now))
                sys.stderr.write(
                    f"[ecm_coupler] Subcycle interp (step {steps_since_ecm + 1}/{call_every_n}): "
                    f"dt_since_ecm={dt_since_ecm:.4f}s, "
                    f"qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
                )
            else:
                # Subcycling: return cached qVol from last ECM fire.
                cached = state["last_qvol_by_ecmid"]
                qvol_ecm = [cached.get(str(eid), 0.0) for eid in ecm_ids]
                sys.stderr.write(
                    f"[ecm_coupler] Subcycle skip (step {steps_since_ecm + 1}/{call_every_n}): "
                    f"using cached qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
                )
            state["steps_since_ecm"] = steps_since_ecm + 1
            try:
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state, sf, indent=2)
            except OSError:
                pass
        elif use_real_ecm:
            _t_ecm_start = time.perf_counter()
            partition_volumes = _get_partition_volumes(mapping_file, mapping)
            current_a = float(inputs.get("current_A", inputs.get("current", 0.0)))
            t_min_k = inputs.get("T_min_K", None)
            t_max_k = inputs.get("T_max_K", None)
            if t_min_k is not None or t_max_k is not None:
                clipped = []
                for t_k in ecm_temps:
                    if t_min_k is not None:
                        t_k = max(float(t_min_k), t_k)
                    if t_max_k is not None:
                        t_k = min(float(t_max_k), t_k)
                    clipped.append(t_k)
                ecm_temps = clipped

            if distributed_mode == "partitionstates":
                partition_states = state.get("partitions", {})
                qvol_ecm, next_partition_states = run_ecm_step_per_partition(
                    ecm_ids=ecm_ids,
                    ecm_temps_K=ecm_temps,
                    dt_s=dt_for_ecm,
                    current_a=current_a,
                    partition_states=partition_states,
                    partition_volumes=partition_volumes,
                    params_df=params_df,
                    cellprops_df=cellprops_df,
                    lookup_cache=ecm_lookup_cache,
                )
                state["partitions"] = next_partition_states
                diag = {
                    "mode": "partitionStates",
                    "Q_total_W": float(sum(q * partition_volumes.get(eid, 0.0) for eid, q in zip(ecm_ids, qvol_ecm))),
                    "T_eff_K": float(compute_effective_temperature(ecm_ids, ecm_temps, partition_volumes)),
                    "n_partitions": int(len(ecm_ids)),
                }
                state.pop("q_ah", None)
                state.pop("v_rc", None)
                state.pop("hysteresis", None)
            elif distributed_mode in ("parallelbranches", "parallelbranchessharedsoc"):
                n_regions = int(os.environ.get("ECM_N_REGIONS", "1").strip() or "1")
                partition_states = state.get("partitions", {})
                if n_regions <= 1:
                    # Single-region: existing code path — no change
                    qvol_ecm, next_partition_states, diag = run_ecm_step_parallel_branches(
                        ecm_ids=ecm_ids,
                        ecm_temps_k=ecm_temps,
                        dt_s=dt_for_ecm,
                        current_a=current_a,
                        partition_states=partition_states,
                        partition_volumes=partition_volumes,
                        cellprops_df=cellprops_df,
                        lookup_cache=ecm_lookup_cache,
                        global_state_defaults=default_state,
                        lambda_q=lambda_q,
                        lambda_r0=lambda_r0,
                        shared_soc=(distributed_mode == "parallelbranchessharedsoc"),
                    )
                    state["partitions"] = next_partition_states
                else:
                    # Multi-region: N independent ECM runs, one per region.
                    # Each cell is electrically independent → full current each.
                    # Per-region overrides:
                    #   params_r{N}.csv / cellprops_r{N}.csv  — electrical properties
                    #   ECM_CURRENT_R{N} env var              — applied current [A]
                    n_total = len(ecm_ids)
                    n_per_region = n_total // n_regions
                    all_qvol = []
                    combined_next_states = {}
                    combined_diag = {
                        "mode": "parallelBranchesSharedSOC_multiRegion",
                        "n_regions": n_regions,
                        "Q_total_W": 0.0,
                        "regions": [],
                    }
                    sys.stderr.write(
                        f"[ECM-MR] multi-region dispatch: n_regions={n_regions} "
                        f"I_pack={current_a:.3f} A  "
                        f"n_total_zones={n_total}  n_per_region={n_per_region}\n"
                    )
                    for r in range(n_regions):
                        r_ids = ecm_ids[r * n_per_region : (r + 1) * n_per_region]
                        r_temps = ecm_temps[r * n_per_region : (r + 1) * n_per_region]
                        r_id_set = set(r_ids)
                        r_pst = {k: v for k, v in partition_states.items() if k in r_id_set}
                        r_pvol = {k: v for k, v in partition_volumes.items() if k in r_id_set}
                        r_vol_total = sum(r_pvol.values()) if r_pvol else 0.0
                        r_T_mean = sum(r_temps) / len(r_temps) if r_temps else 0.0

                        # Per-region current: ECM_CURRENT_R{N} overrides shared current_a.
                        r_current_env = os.environ.get(f"ECM_CURRENT_R{r}", "").strip()
                        r_current = float(r_current_env) if r_current_env else current_a

                        # Per-region electrical tables: params_r{N}.csv / cellprops_r{N}.csv.
                        r_params_df, r_cellprops_df, _r_lc, r_ecm_lc = \
                            _load_runtime_tables_for_region(r)

                        sys.stderr.write(
                            f"[ECM-MR]   region[{r}]: {len(r_ids)} zones  "
                            f"T_mean={r_T_mean:.4f} K  vol={r_vol_total:.6e} m3  "
                            f"I={r_current:.3f} A\n"
                        )
                        r_qvol, r_next, r_diag = run_ecm_step_parallel_branches(
                            ecm_ids=r_ids,
                            ecm_temps_k=r_temps,
                            dt_s=dt_for_ecm,
                            current_a=r_current,
                            partition_states=r_pst,
                            partition_volumes=r_pvol,
                            cellprops_df=r_cellprops_df,
                            lookup_cache=r_ecm_lc,
                            global_state_defaults=default_state,
                            lambda_q=lambda_q,
                            lambda_r0=lambda_r0,
                            shared_soc=(distributed_mode == "parallelbranchessharedsoc"),
                        )
                        r_Q = r_diag.get("Q_total_W", 0.0)
                        r_qvol_arr = list(r_qvol) if r_qvol else []
                        sys.stderr.write(
                            f"[ECM-MR]   region[{r}] result: Q={r_Q:.4f} W  "
                            f"qVol_min={min(r_qvol_arr):.4e}  qVol_max={max(r_qvol_arr):.4e}  "
                            f"V_common={r_diag.get('V_common_V','n/a')} V  "
                            f"I_branch_sum={r_diag.get('I_branch_sum_A','n/a')} A\n"
                        )
                        all_qvol.extend(r_qvol)
                        combined_next_states.update(r_next)
                        combined_diag["Q_total_W"] += r_Q
                        combined_diag["regions"].append(r_diag)
                    qvol_ecm = all_qvol
                    next_partition_states = combined_next_states
                    diag = combined_diag
                    state["partitions"] = next_partition_states
                    sys.stderr.write(
                        f"[ECM-MR] combined: Q_total={combined_diag['Q_total_W']:.4f} W  "
                        f"qVol_min={min(qvol_ecm):.4e}  qVol_max={max(qvol_ecm):.4e}\n"
                    )
                state.pop("q_ah", None)
                state.pop("v_rc", None)
                state.pop("hysteresis", None)
            elif distributed_mode == "parallel2rc":
                partition_states = state.get("partitions", {})
                qvol_ecm, next_partition_states, diag = run_ecm_step_parallel_2rc(
                    ecm_ids=ecm_ids,
                    ecm_temps_k=ecm_temps,
                    dt_s=dt_for_ecm,
                    current_a=current_a,
                    partition_states=partition_states,
                    partition_volumes=partition_volumes,
                    params_df=params_df,
                    cellprops_df=cellprops_df,
                    lookup_cache=ecm_lookup_cache,
                )
                state["partitions"] = next_partition_states
                state.pop("q_ah", None)
                state.pop("v_rc", None)
                state.pop("hysteresis", None)
            elif distributed_mode == "multi_cell_parallel":
                n_cells = int(os.environ.get("ECM_N_CELLS", "1").strip() or "1")
                mc_state_stored = state.get("mc_parallel", {"soc_init": 1.0})
                qvol_ecm, next_mc_state, diag = run_ecm_step_multi_cell_parallel(
                    ecm_ids=ecm_ids,
                    ecm_temps_k=ecm_temps,
                    dt_s=dt_for_ecm,
                    current_a=current_a,
                    mc_state=mc_state_stored,
                    partition_volumes=partition_volumes,
                    params_df=params_df,
                    cellprops_df=cellprops_df,
                    lookup_cache=ecm_lookup_cache,
                    total_vol_override=float(inputs.get("V_jellyroll_m3", 0.0)),
                    M=n_cells,
                )
                state["mc_parallel"] = next_mc_state
                state.pop("q_ah", None)
                state.pop("v_rc", None)
                state.pop("hysteresis", None)
                state.pop("partitions", None)
            elif distributed_mode == "multi_cell_equal_current":
                n_cells = int(os.environ.get("ECM_N_CELLS", "1").strip() or "1")
                mc_state_stored = state.get("mc_equal_current", {"soc_init": 1.0})
                qvol_ecm, next_mc_state, diag = run_ecm_step_multi_cell_equal_current(
                    ecm_ids=ecm_ids,
                    ecm_temps_k=ecm_temps,
                    dt_s=dt_for_ecm,
                    current_a=current_a,
                    mc_state=mc_state_stored,
                    partition_volumes=partition_volumes,
                    params_df=params_df,
                    cellprops_df=cellprops_df,
                    lookup_cache=ecm_lookup_cache,
                    total_vol_override=float(inputs.get("V_jellyroll_m3", 0.0)),
                    M=n_cells,
                )
                state["mc_equal_current"] = next_mc_state
                state.pop("q_ah", None)
                state.pop("v_rc", None)
                state.pop("hysteresis", None)
                state.pop("partitions", None)
            else:
                shared_state = {
                    "q_ah": float(state.get("q_ah", default_state["q_ah"])),
                    "v_rc": list(state.get("v_rc", default_state["v_rc"])),
                    "hysteresis": float(state.get("hysteresis", default_state["hysteresis"])),
                }
                t_eff_k = float(inputs.get("T_eff_K", compute_effective_temperature_from_mesh(keys, temps, mapping)))
                qvol_ecm, next_state, diag = run_ecm_step_shared_state(
                    ecm_ids=ecm_ids,
                    t_eff_k=t_eff_k,
                    dt_s=dt_for_ecm,
                    current_a=current_a,
                    shared_state=shared_state,
                    partition_volumes=partition_volumes,
                    params_df=params_df,
                    cellprops_df=cellprops_df,
                    lookup_cache=ecm_lookup_cache,
                    total_vol_override=float(inputs.get("V_jellyroll_m3", 0.0)),
                    lambda_q=lambda_q,
                    lambda_r0=lambda_r0,
                )
                state["q_ah"] = float(next_state["q_ah"])
                state["v_rc"] = list(next_state["v_rc"])
                state["hysteresis"] = float(next_state["hysteresis"])
                state.pop("partitions", None)

            state["steps_since_ecm"] = 0
            prev_time = float(state.get("last_ecm_time", 0.0))
            prev_qvol = state.get("last_qvol_by_ecmid", {})
            if interp_mode == "linear" and prev_time > 0.0 and h.time > prev_time:
                dt_interp = h.time - prev_time
                dqdt_by_ecmid = {}
                for eid, qv in zip(ecm_ids, qvol_ecm):
                    q_prev = float(prev_qvol.get(str(eid), qv))
                    dqdt_by_ecmid[str(eid)] = (float(qv) - q_prev) / dt_interp
                state["dqdt_by_ecmid"] = dqdt_by_ecmid
            else:
                state.pop("dqdt_by_ecmid", None)
            state["prev_ecm_time"] = prev_time
            state["prev_qvol_by_ecmid"] = prev_qvol
            state["last_ecm_time"] = h.time
            state["last_qvol_by_ecmid"] = {str(eid): qv for eid, qv in zip(ecm_ids, qvol_ecm)}
            try:
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state, sf, indent=2)
            except OSError:
                pass
            _ecm_elapsed_ms = (time.perf_counter() - _t_ecm_start) * 1e3
            if _should_log_ecm_step(int(getattr(h, "stepId", 0))):
                cell_tag = f"[cell {cell_id}] " if cell_id else ""
                sys.stderr.write(
                    f"[ecm_coupler] {cell_tag}Real ECM ({diag.get('mode', 'sharedState')}): "
                    f"{len(ecm_ids)} partitions, dt_ecm={dt_for_ecm:.4f}s, "
                    f"T_eff={float(diag.get('T_eff_K', 0.0)):.3f} K, "
                    f"Q_total={float(diag.get('Q_total_W', 0.0)):.6f} W, "
                    f"qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
                )
            _hlog(
                f"ECM dispatch done: {_ecm_elapsed_ms:.2f} ms | "
                f"mode={diag.get('mode','?')} n={len(ecm_ids)} "
                f"Q_total={float(diag.get('Q_total_W',0)):.4f} W "
                f"SOC={diag.get('SOC_mean', diag.get('state_soc','?'))} "
                f"V_common={diag.get('V_common_V','n/a')} V"
            )
            if qvol_ecm and len(ecm_ids) <= 30:
                for _zi, (_eid, _qv) in enumerate(zip(ecm_ids, qvol_ecm)):
                    _hlog(f"  zone[{_zi}] id={_eid} qVol={_qv:.4e} W/m³")
            elif qvol_ecm:
                _hlog(
                    f"  qVol summary: min={min(qvol_ecm):.4e} max={max(qvol_ecm):.4e} "
                    f"mean={sum(qvol_ecm)/len(qvol_ecm):.4e} W/m³"
                )
            # Log per-region breakdown for multi-region mode
            region_diags = diag.get("regions")
            if region_diags:
                for ri, rd in enumerate(region_diags):
                    rd_Q = rd.get("Q_total_W", 0.0)
                    rd_Vc = rd.get("V_common_V", "n/a")
                    rd_Isum = rd.get("I_branch_sum_A", "n/a")
                    rd_np = rd.get("n_partitions", "?")
                    rd_soc = rd.get("SOC_mean", rd.get("state_soc", "?"))
                    _hlog(
                        f"  region[{ri}]: Q={rd_Q:.4f} W  V_common={rd_Vc} V  "
                        f"I_branch_sum={rd_Isum} A  n_partitions={rd_np}  SOC={rd_soc}"
                    )
                    sys.stderr.write(
                        f"[ECM-MR-step] region[{ri}]: Q={rd_Q:.4f} W  "
                        f"V_common={rd_Vc} V  I_sum={rd_Isum} A  np={rd_np}\n"
                    )
            # Log per-cell SOC/voltage for multi-cell modes
            soc_per_cell = diag.get("SOC_per_cell")
            if soc_per_cell:
                _hlog(f"  SOC_per_cell: {[f'{s:.4f}' for s in soc_per_cell]}")
            # Build per-region Q summary for the diag line
            _diag_extra = {}
            _region_diags = diag.get("regions")
            if _region_diags:
                for _ri, _rd in enumerate(_region_diags):
                    _diag_extra[f"Q_region{_ri}_W"] = float(_rd.get("Q_total_W", 0.0))
                    _diag_extra[f"V_common_region{_ri}_V"] = _rd.get("V_common_V", "n/a")
                    _diag_extra[f"I_sum_region{_ri}_A"] = _rd.get("I_branch_sum_A", "n/a")
                _diag_extra["current_per_region_A"] = float(diag.get("current_per_region_A", current_a))
            _emit_ecm_diag_line(
                {
                    **diag,
                    **_diag_extra,
                    "time_s": float(h.time),
                    "dt_s": float(dt_for_ecm),
                    "current_A": float(current_a),
                    "qVol_min_Wm3": float(min(qvol_ecm)) if qvol_ecm else 0.0,
                    "qVol_max_Wm3": float(max(qvol_ecm)) if qvol_ecm else 0.0,
                    "input_activeVolume_m3": float(inputs.get("activeVolume", 0.0)),
                    "input_V_jellyroll_m3": float(inputs.get("V_jellyroll_m3", 0.0)),
                    "call_every_n": int(call_every_n),
                    "steps_since_ecm": int(state.get("steps_since_ecm", 0)),
                },
                cell_id=cell_id,
            )
            _append_trace_row(
                {
                    **diag,
                    **_diag_extra,
                    "time_s": float(h.time),
                    "dt_s": float(dt_for_ecm),
                    "current_A": float(current_a),
                    "qVol_min_Wm3": float(min(qvol_ecm)) if qvol_ecm else 0.0,
                    "qVol_max_Wm3": float(max(qvol_ecm)) if qvol_ecm else 0.0,
                    "input_activeVolume_m3": float(inputs.get("activeVolume", 0.0)),
                    "input_V_jellyroll_m3": float(inputs.get("V_jellyroll_m3", 0.0)),
                    "call_every_n": int(call_every_n),
                    "steps_since_ecm": int(state.get("steps_since_ecm", 0)),
                }
            )
            _append_voltage_history(
                state_file=state_file,
                step_id=int(getattr(h, "stepId", 0)),
                time_s=float(h.time),
                dt_s=float(dt_for_ecm),
                current_a=current_a,
                diag=diag,
                cell_id=cell_id,
            )
            _append_voltage_log(
                state_file=state_file,
                step_id=int(getattr(h, "stepId", 0)),
                time_s=float(h.time),
                diag=diag,
            )
        else:
            qvol_ecm = compute_qvol(ecm_ids, ecm_temps, inputs)
            state["steps_since_ecm"] = 0
            prev_time = float(state.get("last_ecm_time", 0.0))
            prev_qvol = state.get("last_qvol_by_ecmid", {})
            if interp_mode == "linear" and prev_time > 0.0 and h.time > prev_time:
                dt_interp = h.time - prev_time
                dqdt_by_ecmid = {}
                for eid, qv in zip(ecm_ids, qvol_ecm):
                    q_prev = float(prev_qvol.get(str(eid), qv))
                    dqdt_by_ecmid[str(eid)] = (float(qv) - q_prev) / dt_interp
                state["dqdt_by_ecmid"] = dqdt_by_ecmid
            else:
                state.pop("dqdt_by_ecmid", None)
            state["prev_ecm_time"] = prev_time
            state["prev_qvol_by_ecmid"] = prev_qvol
            state["last_ecm_time"] = h.time
            state["last_qvol_by_ecmid"] = {str(eid): qv for eid, qv in zip(ecm_ids, qvol_ecm)}
            try:
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state, sf, indent=2)
            except OSError:
                pass

        if smooth_passes > 0 and smooth_blend > 0.0:
            partition_volumes = _get_partition_volumes(mapping_file, mapping)
            qvol_ecm = smooth_partition_qvol(
                ecm_ids=ecm_ids,
                qvol_ecm=qvol_ecm,
                partition_volumes=partition_volumes,
                axial_count=smooth_axial,
                radial_count=smooth_radial,
                passes=smooth_passes,
                blend=smooth_blend,
            )
            sys.stderr.write(
                f"[ecm_coupler] Applied partition smoothing: passes={smooth_passes}, "
                f"blend={smooth_blend:.3f}, grid={smooth_axial}x{smooth_radial}, "
                f"qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
            )

        q_out, dist_info = distribute_qvol_to_mesh(keys, ecm_ids, qvol_ecm, mapping)
        if dist_info["missing_mesh"]:
            sys.stderr.write(
                f"[ecm_coupler] WARN: {len(dist_info['missing_mesh'])} mesh keys had no "
                "mapping weights; writing 0.0 qVol for those cells.\n"
            )
        # distribute_qvol_to_mesh returns qVol [W/m³] per mesh cell (uniform within
        # each partition).  The binary ecm_out.bin protocol sends W/m³ directly.
        # Java writes these values straight to the injection CSV without any further
        # per-cell volume division (matches the OpenFOAM approach: one uniform
        # W/m³ value per partition, no hotspots from cell-size variation).
    else:
        # Lumped model uses a single representative temperature (degC).
        if len(temps) > 1:
            sys.stderr.write(
                "[ecm_coupler] WARN: lumped ECM backend received multiple temperatures; "
                "using simple average.\n"
            )
        t_avg_k = float(sum(temps) / float(len(temps)))
        t_min_k = inputs.get("T_min_K", None)
        t_max_k = inputs.get("T_max_K", None)
        if t_min_k is not None:
            t_avg_k = max(float(t_min_k), t_avg_k)
        if t_max_k is not None:
            t_avg_k = min(float(t_max_k), t_avg_k)

        current_a = float(inputs.get("current_A", inputs.get("current", 0.0)))
        use_real_ecm = _ECM_STEP_AVAILABLE and os.environ.get(
            "ECM_USE_REAL_STEP", "1"
        ).strip() not in ("0", "false", "no")

        if use_real_ecm:
            shared_state = {
                "q_ah": float(state.get("q_ah", default_state["q_ah"])),
                "v_rc": list(state.get("v_rc", default_state["v_rc"])),
                "hysteresis": float(state.get("hysteresis", default_state["hysteresis"])),
            }
            active_vol = float(inputs.get("activeVolume", 0.0)) if "activeVolume" in inputs else 0.0
            qvol_ecm, next_state, diag = run_ecm_step_shared_state(
                ecm_ids=[0],
                t_eff_k=t_avg_k,
                dt_s=dt_for_ecm,
                current_a=current_a,
                shared_state=shared_state,
                partition_volumes={0: active_vol if active_vol > 0.0 else 1.0},
                params_df=params_df,
                cellprops_df=cellprops_df,
                lookup_cache=ecm_lookup_cache,
                total_vol_override=active_vol,
                lambda_q=lambda_q,
                lambda_r0=lambda_r0,
            )
            state["q_ah"] = float(next_state["q_ah"])
            state["v_rc"] = list(next_state["v_rc"])
            state["hysteresis"] = float(next_state["hysteresis"])
            try:
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
            except OSError:
                pass
            q_gen_w = float(diag.get("Q_total_W", 0.0))
            if _should_log_ecm_step(int(getattr(h, "stepId", 0))):
                sys.stderr.write(
                    f"[ecm_coupler] Real ECM (lumped): dt_ecm={dt_for_ecm:.4f}s, "
                    f"T_eff={t_avg_k:.3f} K, Q_total={q_gen_w:.6f} W\n"
                )
            _emit_ecm_diag_line(
                {
                    **diag,
                    "time_s": float(h.time),
                    "dt_s": float(dt_for_ecm),
                    "current_A": float(current_a),
                    "qVol_min_Wm3": float(min(qvol_ecm)) if qvol_ecm else 0.0,
                    "qVol_max_Wm3": float(max(qvol_ecm)) if qvol_ecm else 0.0,
                    "input_activeVolume_m3": float(inputs.get("activeVolume", 0.0)),
                    "input_V_jellyroll_m3": float(inputs.get("V_jellyroll_m3", 0.0)),
                    "call_every_n": int(call_every_n),
                    "steps_since_ecm": int(state.get("steps_since_ecm", 0)),
                }
            )
            _append_trace_row(
                {
                    **diag,
                    "time_s": float(h.time),
                    "dt_s": float(dt_for_ecm),
                    "current_A": float(current_a),
                    "qVol_min_Wm3": float(min(qvol_ecm)) if qvol_ecm else 0.0,
                    "qVol_max_Wm3": float(max(qvol_ecm)) if qvol_ecm else 0.0,
                    "input_activeVolume_m3": float(inputs.get("activeVolume", 0.0)),
                    "input_V_jellyroll_m3": float(inputs.get("V_jellyroll_m3", 0.0)),
                    "call_every_n": int(call_every_n),
                    "steps_since_ecm": int(state.get("steps_since_ecm", 0)),
                }
            )
            _append_voltage_history(
                state_file=state_file,
                step_id=int(getattr(h, "stepId", 0)),
                time_s=float(h.time),
                dt_s=float(dt_for_ecm),
                current_a=current_a,
                diag=diag,
            )
            _append_voltage_log(
                state_file=state_file,
                step_id=int(getattr(h, "stepId", 0)),
                time_s=float(h.time),
                diag=diag,
            )
        else:
            t_cell_c = t_avg_k - 273.15
            resp = backend.step(
                dt_s=float(h.deltaT),
                current_a=current_a,
                q_ah=float(state.get("q_ah", 0.0)),
                v_rc=np.array(state.get("v_rc", [0.0, 0.0]), dtype=float),
                hysteresis=float(state.get("hysteresis", 0.0)),
                T_cell_degC=t_cell_c,
            )

            # Persist state for next step.
            next_state = {
                "q_ah": float(resp.q_ah_next),
                "v_rc": list(resp.state_next.get("V_RC", [0.0, 0.0])),
                "hysteresis": float(resp.state_next.get("H", 0.0)),
            }
            try:
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(next_state, f, indent=2)
            except OSError:
                pass

            q_gen_w = float(resp.outputs.get("Q_GEN", 0.0))

        # Output total power [W] per record.
        # Lumped (N=1): single record = Q_GEN [W].
        # elementWise (N>1): distribute by R0(T[i]) weighting.
        #   Heat ∝ I²·R0(T[i]); cooler cells have higher R0 → more Joule heat.
        #   Java per-cell injection requires INJECTION_MODE=csvReload.
        if len(keys) == 1:
            q_out = [q_gen_w]
        else:
            n_cells = max(len(keys), 1)
            t_mean_k = sum(temps) / n_cells
            q_ah_cur = float(state.get("q_ah", default_state["q_ah"]))
            if _ecm_get_params is not None and ecm_lookup_cache is not None:
                try:
                    weights = [
                        max(1e-12, float(_ecm_get_params(
                            ecm_lookup_cache, q_ah_cur, T_k - 273.15,
                            lambda_Q=lambda_q, lambda_R=lambda_r0
                        )["R0"]))
                        for T_k in temps
                    ]
                    total_w = sum(weights) or 1.0
                    q_out = [q_gen_w * w / total_w for w in weights]
                    dist_label = "R0-weighted"
                except Exception as _e:
                    sys.stderr.write(
                        f"[ecm_coupler] WARN: R0-weighted distribution failed ({_e}); using uniform\n"
                    )
                    q_out = [q_gen_w / n_cells for _ in keys]
                    dist_label = "uniform (fallback)"
            else:
                q_out = [q_gen_w / n_cells for _ in keys]
                dist_label = "uniform (no param lookup)"
            q_min = min(q_out)
            q_max = max(q_out)
            sys.stderr.write(
                f"[ecm_coupler] elementWise: N={n_cells} cells, "
                f"T_mean={t_mean_k:.3f} K, "
                f"Q_GEN={q_gen_w:.6f} W, "
                f"q=[{q_min:.4e}..{q_max:.4e}] W ({dist_label})\n"
            )

    return q_out


def run_file_mode():
    in_file = os.environ.get("ECM_IN", "ecm_in.bin")
    out_file = os.environ.get("ECM_OUT", "ecm_out.bin")

    with open(in_file, "rb") as f:
        h = read_header(f)
        if h.fileType != 1:
            raise ValueError(f"Expected input fileType=1, got {h.fileType}")
        inputs = read_inputs(f, h.nInputs)
        keys, temps = read_records_T(f, h.N)

    q_out = compute_q_out(h, inputs, keys, temps)

    out_h = Header(
        magic=b"ECMIOv1\x00",
        fileType=2,
        version=2,
        N=len(keys),
        time=h.time,
        deltaT=h.deltaT,
        keyMode=h.keyMode,
        nInputs=0,
        stepId=h.stepId,
    )

    buf = io.BytesIO()
    write_header(buf, out_h)
    write_inputs(buf, {})  # none
    write_records(buf, keys, q_out)

    atomic_write(out_file, buf.getvalue())


def run_pipe_mode():
    sys.stdout.reconfigure(line_buffering=True)

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue

        try:
            req = json.loads(raw)
            if req.get("magic") != "ECM_ELEMENTWISE_PIPE":
                raise ValueError("Invalid pipe request magic")
            if int(req.get("version", 0)) != 1:
                raise ValueError("Unsupported pipe request version")

            step_id = int(req["step_id"])
            time_s = float(req["time_s"])
            dt_s = float(req["dt_s"])
            key_mode = int(req.get("key_mode", 0))
            inputs = {str(k): float(v) for k, v in dict(req.get("electrical_inputs", {})).items()}
            records = req.get("records", [])
            keys = [int(rec[0]) for rec in records]
            temps = [float(rec[1]) for rec in records]

            h = Header(
                magic=b"ECMIOv1\x00",
                fileType=1,
                version=2,
                N=len(keys),
                time=time_s,
                deltaT=dt_s,
                keyMode=key_mode,
                nInputs=len(inputs),
                stepId=step_id,
            )

            q_out = compute_q_out(h, inputs, keys, temps)
            resp = {
                "status": "ok",
                "step_id": step_id,
                "records": [[int(k), float(q)] for k, q in zip(keys, q_out)],
            }
        except Exception as e:
            resp = {"status": "error", "message": str(e)}

        print(json.dumps(resp, separators=(",", ":")), flush=True)


def run_pipe_binary():
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    max_frame_size = 64 * 1024 * 1024

    while True:
        size_raw = stdin.read(8)
        if not size_raw:
            break
        if len(size_raw) != 8:
            raise ValueError("Truncated binary pipe frame header")

        (size,) = struct.unpack("<Q", size_raw)
        if size > max_frame_size:
            raise ValueError(
                f"Binary pipe frame too large: {size} bytes "
                f"(header={size_raw.hex()}, limit={max_frame_size})"
            )
        payload = stdin.read(size)
        if len(payload) != size:
            raise ValueError("Truncated binary pipe payload")

        with io.BytesIO(payload) as f:
            h = read_header(f)
            if h.fileType != 1:
                raise ValueError(f"Expected input fileType=1, got {h.fileType}")
            inputs = read_inputs(f, h.nInputs)
            keys, temps = read_records_T(f, h.N)

        q_out = compute_q_out(h, inputs, keys, temps)

        out_h = Header(
            magic=b"ECMIOv1\x00",
            fileType=2,
            version=2,
            N=len(keys),
            time=h.time,
            deltaT=h.deltaT,
            keyMode=h.keyMode,
            nInputs=0,
            stepId=h.stepId,
        )
        buf = io.BytesIO()
        write_header(buf, out_h)
        write_inputs(buf, {})
        write_records(buf, keys, q_out)
        out_payload = buf.getvalue()
        stdout.write(struct.pack("<Q", len(out_payload)))
        stdout.write(out_payload)
        stdout.flush()


def parse_args():
    parser = argparse.ArgumentParser(description="ECM coupler backend")
    parser.add_argument("--pipe-mode", action="store_true")
    parser.add_argument("--pipe-binary", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()
        if args.pipe_binary:
            run_pipe_binary()
        elif args.pipe_mode:
            run_pipe_mode()
        else:
            run_file_mode()
    except Exception as e:
        msg = str(e).strip()
        if not msg:
            msg = f"{type(e).__name__}()"
        sys.stderr.write(f"[ecm_coupler] ERROR: {msg}\n")
        sys.exit(2)
