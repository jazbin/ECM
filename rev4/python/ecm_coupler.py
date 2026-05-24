#!/usr/bin/env python3
import argparse
import csv
import io
import json
import math
import os
import struct
import sys
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
        "T_zone_min_K",
        "T_zone_max_K",
        "Q_total_W",
        "Q_ref_W",
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
    if cell_id:
        parts.append(f"cell_id={cell_id}")
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
        sys.stderr.write("[ecm_diag] " + " ".join(parts) + "\n")


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
    every = _int_env("ECM_LOG_EVERY_N_STEPS", 0)
    if every <= 0:
        return False
    return step_id % every == 0


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


def _get_mapping(mapping_file: str):
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
    if keys and len(keys) == len(temps) and all(int(k) in ecm_to_mesh for k in keys):
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

    Each partition has its own (q_ah, V_RC, H) state.  The capacity is scaled
    by the partition's volume fraction so that the total q_ah across partitions
    equals the whole-cell Coulomb count.

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
        current_i = float(current_a) * float(vol_frac)

        # Scale capacity proportional to volume fraction (series current, parallel volume).
        scaled_cellprops = cellprops_df.copy() if not cellprops_df.empty else pd.DataFrame(
            [{"capacity_Ah": 9.0 * vol_frac, "Qnom_Ah": 9.0 * vol_frac, "T_ref_degC": 25.0}]
        )
        if not scaled_cellprops.empty:
            scaled_cellprops = scaled_cellprops.copy()
            scaled_cellprops["capacity_Ah"] = capacity_total * vol_frac
            if "Qnom_Ah" in scaled_cellprops.columns:
                scaled_cellprops["Qnom_Ah"] = capacity_total * vol_frac

        pstate = partition_states.get(str(ecm_id), {})
        q_ah = float(pstate.get("q_ah", 0.0))
        v_rc = np.array(pstate.get("v_rc", [0.0, 0.0]), dtype=float)
        hysteresis = float(pstate.get("hysteresis", 0.0))
        T_degC = T_K - 273.15

        state_next, q_ah_next, outputs = _ecm_step_fn(
            dt_s=dt_s,
            current_a=current_i,
            q_ah=q_ah,
            v_rc=v_rc,
            hysteresis=hysteresis,
            T_cell_degC=T_degC,
            params_df=params_df,
            cellprops_df=scaled_cellprops,
            lookup_cache=lookup_cache,
        )

        q_gen_w = float(outputs.get("Q_GEN", 0.0))
        # Convert each partition's generated power to a true local volumetric
        # source so integrating qVol over the partition recovers q_gen_w.
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

    All thermal zones share a common terminal voltage; branch currents are
    determined by per-zone temperature-dependent impedance via KCL/KVL.

    Sign convention follows ecm_step.py demo: positive pack_current_a is
    passed directly (positive = discharge in caller convention).

    total_vol_override : float
        Actual jellyRoll volume [m³].  When the mapping file uses unit weights
        (weight = 1.0 per cell), partition_volumes holds cell counts, not m³.
        Providing the real volume allows correct W/m³ computation.
        If 0.0, the raw partition_volumes sums are used as-is.

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

    # partition_volumes may hold cell counts (weight=1.0) or actual m³ (weight=volume).
    # Scale to actual m³ when total_vol_override is provided.
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
    # Ensure Qnom_Ah is present (parallel_2rc_step requires it).
    if "Qnom_Ah" not in scaled_cellprops.columns:
        scaled_cellprops = scaled_cellprops.copy()
        scaled_cellprops["Qnom_Ah"] = q_nom_slice

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
    # V_TERMINAL from parallel_2rc_step = V_OCV + V_OP (internal representation).
    # Physical terminal voltage = V_OCV - V_OP.  Compute per branch then take
    # mean/min/max so the stored value matches the lumped convention (V_OCV_DCH - V_OP).
    v_ocv_arr = np.asarray(outputs.get("V_OCV_DCH", outputs.get("V_OCV", np.zeros(n))), dtype=float)
    v_op_arr  = np.asarray(outputs.get("V_OP", np.zeros(n)), dtype=float)
    v_actual_branches = v_ocv_arr - v_op_arr   # physical terminal voltage per branch
    diag = {
        "mode": "parallel2rc",
        "Q_total_W": q_total,
        "T_eff_K": float(np.mean(ecm_temps_k)),
        "n_partitions": n,
        "V_common_V": float(np.mean(v_actual_branches)),
        "V_branch_min_V": float(np.min(v_actual_branches)),
        "V_branch_max_V": float(np.max(v_actual_branches)),
        "I_BRANCH_min_A": float(np.min(i_branch)),
        "I_BRANCH_max_A": float(np.max(i_branch)),
        "I_branch_sum_A": float(np.sum(i_branch)),
        "SOC_mean": float(np.mean(soc_arr)),
        "SOC_min": float(np.min(soc_arr)),
        "SOC_max": float(np.max(soc_arr)),
        "current_balance_residual": float(outputs.get("CURRENT_BALANCE_RESIDUAL", 0.0)),
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
    # The parallel KCL model redistributes current to low-R0 (hot) zones, which
    # lowers the effective parallel resistance below R0(T_avg).  This causes the
    # distributed total Q to be ~5–10% lower than a lumped call at T_avg.
    # Fix: rescale per-zone Q values so the per-cell total matches a single
    # ecm_step call at T_avg (full cell capacity, same SOC & current).
    # State evolution (SOC, RC, hysteresis) is kept from multi_cell_parallel_step.
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
    # Physical terminal voltage per zone = V_OCV_DCH - V_OP
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
    This eliminates the KCL feedback loop that causes heat redistribution toward hot zones.

    M physically independent battery cells, each divided into n_parallel spatial zones.
    All zones within a cell share one SOC; zone temperatures drive local heat generation.
    All M × n_parallel calculations happen in a single vectorised call.

    Parameters
    ----------
    (Same as run_ecm_step_multi_cell_parallel)

    Returns
    -------
    qvol_ecm   : list[float]  per-zone volumetric heat source [W/m³], length M*n_parallel
    next_mc_state : dict      updated state (q_ah, v_rc, hysteresis as nested lists)
    diag       : dict         diagnostic quantities
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

    # --- advance one step (equal-current distribution) ---
    state_next, q_ah_next, outputs = multi_cell_equal_current_step(
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
    q_ah_cell_mean = np.mean(q_ah_next, axis=1, keepdims=True)   # (M, 1)
    q_ah_next = np.broadcast_to(q_ah_cell_mean, (M, n_parallel)).copy()

    # --- Q_GEN (M, n_parallel) ---
    q_gen_mn = np.asarray(outputs["Q_GEN"], dtype=float)  # (M, n_parallel)

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


def compute_q_out(h, inputs, keys, temps):
    # Cell ID for multi-battery setups (empty string = single cell or no tagging)
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

    q_out = []
    if mapping is not None:
        ecm_ids, ecm_temps, mapping_info = aggregate_ecm_temperatures(keys, temps, mapping)
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
                partition_states = state.get("partitions", {})
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
                    total_vol_override=float(inputs.get("V_jellyroll_m3", 0.0)),
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
            cell_id_prefix = f"[cell {cell_id}] " if cell_id else ""
            if _should_log_ecm_step(int(getattr(h, "stepId", 0))):
                sys.stderr.write(
                    f"[ecm_coupler] {cell_id_prefix}Real ECM ({diag.get('mode', 'sharedState')}): "
                    f"{len(ecm_ids)} partitions, dt_ecm={dt_for_ecm:.4f}s, "
                    f"T_eff={float(diag.get('T_eff_K', 0.0)):.3f} K, "
                    f"Q_total={float(diag.get('Q_total_W', 0.0)):.6f} W, "
                    f"qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
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
                },
                cell_id=cell_id,
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
                cell_id=cell_id,
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
            cell_id_prefix = f"[cell {cell_id}] " if cell_id else ""
            if _should_log_ecm_step(int(getattr(h, "stepId", 0))):
                sys.stderr.write(
                    f"[ecm_coupler] {cell_id_prefix}Real ECM (lumped): dt_ecm={dt_for_ecm:.4f}s, "
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
                },
                cell_id=cell_id,
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
                cell_id=cell_id,
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

        # For lumped coupling, output total power as single record.
        if len(keys) == 1:
            q_out = [q_gen_w]
        else:
            active_vol = inputs.get("activeVolume", None)
            if active_vol is None or float(active_vol) <= 0.0:
                sys.stderr.write(
                    "[ecm_coupler] WARN: multiple keys provided but no activeVolume; "
                    "writing zero qVol. Use couplingMode=lumped or provide activeVolume.\n"
                )
                q_out = [0.0 for _ in keys]
            else:
                qvol = q_gen_w / float(active_vol)
                q_out = [qvol for _ in keys]

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
