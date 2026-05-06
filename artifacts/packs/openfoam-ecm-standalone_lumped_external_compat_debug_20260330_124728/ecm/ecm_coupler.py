#!/usr/bin/env python3
import argparse
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

# Real ECM step — located one directory above ecm/ in the workspace root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_HERE)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

try:
    from ecm_step import ecm_step as _ecm_step_fn, build_step_cache as _ecm_build_step_cache
    _ECM_STEP_AVAILABLE = True
except ImportError:
    _ecm_step_fn = None
    _ecm_build_step_cache = None
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
    key_to_temp = {int(k): float(t) for k, t in zip(keys, temps)}
    ecm_to_mesh = mapping["ecm_to_mesh"]

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
    capacity_total = float(cellprops_df["capacity_Ah"].iloc[0]) if not cellprops_df.empty else 9.0

    qvol_ecm = []
    next_states = {}

    for ecm_id, T_K in zip(ecm_ids, ecm_temps_K):
        vol_i = partition_volumes.get(ecm_id, total_vol / max(len(ecm_ids), 1))
        vol_frac = vol_i / total_vol

        # Scale capacity proportional to volume fraction (series current, parallel volume).
        scaled_cellprops = cellprops_df.copy() if not cellprops_df.empty else pd.DataFrame(
            [{"capacity_Ah": 9.0 * vol_frac, "T_ref_degC": 25.0}]
        )
        if not scaled_cellprops.empty:
            scaled_cellprops = scaled_cellprops.copy()
            scaled_cellprops["capacity_Ah"] = capacity_total * vol_frac

        pstate = partition_states.get(str(ecm_id), {})
        q_ah = float(pstate.get("q_ah", 0.0))
        v_rc = np.array(pstate.get("v_rc", [0.0, 0.0]), dtype=float)
        hysteresis = float(pstate.get("hysteresis", 0.0))
        T_degC = T_K - 273.15

        state_next, q_ah_next, outputs = _ecm_step_fn(
            dt_s=dt_s,
            current_a=current_a,
            q_ah=q_ah,
            v_rc=v_rc,
            hysteresis=hysteresis,
            T_cell_degC=T_degC,
            params_df=params_df,
            cellprops_df=scaled_cellprops,
            lookup_cache=lookup_cache,
        )

        q_gen_w = float(outputs.get("Q_GEN", 0.0))
        # Divide by total cell volume (not partition volume) so that the
        # base heat density is uniform across partitions; temperature-driven
        # resistance variation then produces spatial qVol differences.
        qvol_i = q_gen_w / total_vol if total_vol > 1e-20 else 0.0
        qvol_ecm.append(qvol_i)

        next_states[str(ecm_id)] = {
            "q_ah": float(q_ah_next),
            "v_rc": list(state_next.get("V_RC", [0.0, 0.0])),
            "hysteresis": float(state_next.get("H", 0.0)),
        }

    return qvol_ecm, next_states


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
) -> tuple[list[float], dict, dict]:
    """
    Run one whole-cell ECM state and distribute the resulting total heat
    uniformly as a volumetric source over the active volume.
    """
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
    )

    q_total_w = float(outputs.get("Q_GEN", 0.0))
    qvol_uniform = q_total_w / total_vol if total_vol > 1.0e-20 else 0.0
    qvol_ecm = [qvol_uniform for _ in ecm_ids]
    next_state = {
        "q_ah": float(q_ah_next),
        "v_rc": list(state_next.get("V_RC", [0.0, 0.0])),
        "hysteresis": float(state_next.get("H", 0.0)),
    }
    diag = {
        "T_eff_K": float(t_eff_k),
        "Q_total_W": float(q_total_w),
        "qVol_uniform_Wm3": float(qvol_uniform),
        "n_partitions": int(len(ecm_ids)),
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
) -> tuple[dict, float, dict, dict]:
    """Evaluate one ECM branch with scaled capacity and resistance."""
    capacity_ah = max(float(capacity_ah), 1.0e-12)
    t_cell_degc = float(t_cell_k) - 273.15
    temp_shift = t_cell_degc - float(t_ref_degc)

    q_ah_next = float(q_ah) - float(current_a) * float(dt_s) / 3600.0
    q_ah_next = max(0.0, min(q_ah_next, capacity_ah))
    soc = q_ah_next / capacity_ah

    cache = lookup_cache
    ocv_v = float(np.interp(soc, cache["soc"], cache["ocv_v"]))
    r0 = float(np.interp(soc, cache["soc"], cache["r0_ohm"])) * math.exp(-0.030 * temp_shift) * resistance_scale
    r1 = float(np.interp(soc, cache["soc"], cache["r1_ohm"])) * math.exp(-0.015 * temp_shift) * resistance_scale
    r2 = float(np.interp(soc, cache["soc"], cache["r2_ohm"])) * math.exp(-0.010 * temp_shift) * resistance_scale
    tau1 = float(np.interp(soc, cache["soc"], cache["tau1_s"]))
    tau2 = float(np.interp(soc, cache["soc"], cache["tau2_s"]))
    gamma = float(np.interp(soc, cache["soc"], cache["gamma_hyst_v"]))

    r0 = max(1.0e-9, r0)
    r1 = max(1.0e-9, r1)
    r2 = max(1.0e-9, r2)

    v_rc = np.asarray(v_rc, dtype=float)
    a1 = math.exp(-float(dt_s) / tau1)
    a2 = math.exp(-float(dt_s) / tau2)
    v_rc1_next = a1 * float(v_rc[0]) + (1.0 - a1) * r1 * float(current_a)
    v_rc2_next = a2 * float(v_rc[1]) + (1.0 - a2) * r2 * float(current_a)

    if float(current_a) > 1.0e-15:
        h_target = 1.0
    elif float(current_a) < -1.0e-15:
        h_target = -1.0
    else:
        h_target = 0.0
    a_h = math.exp(-float(dt_s) / 5.0)
    h_next = a_h * float(hysteresis) + (1.0 - a_h) * h_target
    h_next = max(-1.0, min(h_next, 1.0))

    v_t = ocv_v - float(current_a) * r0 - v_rc1_next - v_rc2_next - gamma * h_next
    q_gen = (
        float(current_a) ** 2 * r0
        + abs(float(current_a)) * (abs(v_rc1_next) + abs(v_rc2_next))
        + abs(float(current_a)) * gamma * abs(h_next)
    )

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
        "v_intercept": ocv_v - a1 * float(v_rc[0]) - a2 * float(v_rc[1]) - gamma * h_next,
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
    capacity_total = float(cellprops_df["capacity_Ah"].iloc[0]) if not cellprops_df.empty else 9.0
    t_ref_degc = float(cellprops_df["T_ref_degC"].iloc[0]) if not cellprops_df.empty else 25.0

    branch_meta = []
    for ecm_id, t_k in zip(ecm_ids, ecm_temps_k):
        vol_i = float(partition_volumes.get(ecm_id, total_vol / max(len(ecm_ids), 1)))
        vol_frac = max(vol_i / total_vol, 1.0e-12)
        resistance_scale = 1.0 / vol_frac
        pstate = partition_states.get(str(ecm_id), {})
        q_ah = float(pstate.get("q_ah", 0.0))
        v_rc = np.array(pstate.get("v_rc", [0.0, 0.0]), dtype=float)
        hysteresis = float(pstate.get("hysteresis", 0.0))
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
        )
        q_gen_w = float(outputs.get("Q_GEN", 0.0))
        qvol_i = q_gen_w / b["vol_i"] if b["vol_i"] > 1.0e-20 else 0.0
        qvol_ecm.append(qvol_i)
        branch_voltages.append(float(outputs.get("V_T", 0.0)))
        next_states[str(b["ecm_id"])] = {
            "q_ah": float(q_ah_next),
            "v_rc": list(state_next.get("V_RC", [0.0, 0.0])),
            "hysteresis": float(state_next.get("H", 0.0)),
        }

    q_total_w = float(sum(q * b["vol_i"] for q, b in zip(qvol_ecm, branch_meta)))
    diag = {
        "mode": "parallelBranches",
        "Q_total_W": q_total_w,
        "T_eff_K": float(compute_effective_temperature(ecm_ids, ecm_temps_k, partition_volumes)),
        "V_common_V": float(v_common),
        "V_branch_min_V": float(min(branch_voltages)) if branch_voltages else 0.0,
        "V_branch_max_V": float(max(branch_voltages)) if branch_voltages else 0.0,
        "I_branch_min_A": float(min(branch_currents)) if branch_currents else 0.0,
        "I_branch_max_A": float(max(branch_currents)) if branch_currents else 0.0,
        "I_branch_sum_A": float(sum(branch_currents)),
        "n_partitions": int(len(ecm_ids)),
    }
    return qvol_ecm, next_states, diag


def compute_q_out(h, inputs, keys, temps):
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

    # Load params/cellprops — check ecm/ dir first, then workspace root.
    here = os.path.dirname(os.path.abspath(__file__))
    def _find_csv(name):
        for d in [here, _WORKSPACE_ROOT]:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        return None
    params_path = _find_csv("params.csv")
    cellprops_path = _find_csv("cellprops.csv")
    params_df = pd.read_csv(params_path) if params_path else pd.DataFrame()
    cellprops_df = pd.read_csv(cellprops_path) if cellprops_path else pd.DataFrame()
    lookup_cache = build_step_cache(params_df)

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
            mapping = load_mapping_table(mapping_file)
            sys.stderr.write(f"[ecm_coupler] Using mapping table: {mapping_file}\n")
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

    def state_defaults():
        return {
            "q_ah": float(inputs.get("q_ah_init", inputs.get("q_ah", 0.0))),
            "v_rc": [
                float(inputs.get("v_rc1_init", inputs.get("v_rc1", 0.0))),
                float(inputs.get("v_rc2_init", inputs.get("v_rc2", 0.0))),
            ],
            "hysteresis": float(inputs.get("hysteresis_init", inputs.get("hysteresis", 0.0))),
        }

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

    # Accumulated dt since last ECM fire — mirrors lumped wrapper's dt_since_ecm logic.
    # When subcycling (call_every_n > 1), the RC circuit must advance by the TOTAL elapsed
    # time since the last real ECM call, not just the current CFD step dt.
    last_ecm_time = float(state.get("last_ecm_time", h.time - h.deltaT))
    is_first_ecm_call = not state.get("last_ecm_time")
    dt_for_ecm = h.deltaT if is_first_ecm_call else (h.time - last_ecm_time)

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
            partition_volumes = compute_partition_volumes(mapping)
            current_a = float(inputs.get("current_A", inputs.get("current", 0.0)))
            ecm_lookup_cache = _ecm_build_step_cache(params_df)
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
            elif distributed_mode == "parallelbranches":
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
                )
                state["partitions"] = next_partition_states
                state.pop("q_ah", None)
                state.pop("v_rc", None)
                state.pop("hysteresis", None)
            else:
                shared_state = {
                    "q_ah": float(state.get("q_ah", state_defaults()["q_ah"])),
                    "v_rc": list(state.get("v_rc", state_defaults()["v_rc"])),
                    "hysteresis": float(state.get("hysteresis", state_defaults()["hysteresis"])),
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
            sys.stderr.write(
                f"[ecm_coupler] Real ECM ({diag.get('mode', 'sharedState')}): "
                f"{len(ecm_ids)} partitions, dt_ecm={dt_for_ecm:.4f}s, "
                f"T_eff={float(diag.get('T_eff_K', 0.0)):.3f} K, "
                f"Q_total={float(diag.get('Q_total_W', 0.0)):.6f} W, "
                f"qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
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
            partition_volumes = compute_partition_volumes(mapping)
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
        t_cell_c = t_avg_k - 273.15

        current_a = float(inputs.get("current_A", inputs.get("current", 0.0)))

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

    while True:
        size_raw = stdin.read(8)
        if not size_raw:
            break
        if len(size_raw) != 8:
            raise ValueError("Truncated binary pipe frame header")

        (size,) = struct.unpack("<Q", size_raw)
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
        sys.stderr.write(f"[ecm_coupler] ERROR: {e}\n")
        sys.exit(2)
