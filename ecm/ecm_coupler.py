#!/usr/bin/env python3
import json
import os
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


def main():
    in_file = os.environ.get("ECM_IN", "ecm_in.bin")
    out_file = os.environ.get("ECM_OUT", "ecm_out.bin")
    lumped_output = os.environ.get("ECM_LUMPED_OUTPUT", "").strip().lower()
    active_volume = os.environ.get("ECM_ACTIVE_VOLUME", "").strip()
    state_file = os.environ.get("ECM_STATE_FILE", "ecm_state.json")
    state_reset = os.environ.get("ECM_STATE_RESET", "").strip()
    mapping_file = os.environ.get("ECM_MAPPING_FILE", "").strip()
    mapping_mode = os.environ.get("ECM_MAPPING_MODE", "").strip().lower()
    n_elements_raw = os.environ.get("ECM_N_ELEMENTS", "").strip()
    overlap_raw = os.environ.get("ECM_OVERLAP", "").strip()

    backend_name = os.environ.get("ECM_BACKEND", "mock-inproc").strip()
    vendor_exec = os.environ.get("ECM_VENDOR_EXEC", "").strip()
    vendor_workdir = os.environ.get("ECM_VENDOR_WORKDIR", "").strip() or None
    vendor_state = os.environ.get("ECM_VENDOR_STATE", "").strip() or None

    with open(in_file, "rb") as f:
        h = read_header(f)
        if h.fileType != 1:
            raise ValueError(f"Expected input fileType=1, got {h.fileType}")
        inputs = read_inputs(f, h.nInputs)
        keys, temps = read_records_T(f, h.N)

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
            # Subcycling: return cached qVol from last ECM fire.
            cached = state["last_qvol_by_ecmid"]
            qvol_ecm = [cached.get(str(eid), 0.0) for eid in ecm_ids]
            state["steps_since_ecm"] = steps_since_ecm + 1
            try:
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state, sf, indent=2)
            except OSError:
                pass
            sys.stderr.write(
                f"[ecm_coupler] Subcycle skip (step {steps_since_ecm + 1}/{call_every_n}): "
                f"using cached qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
            )
        elif use_real_ecm:
            partition_volumes = compute_partition_volumes(mapping)
            partition_states = state.get("partitions", {})
            current_a = float(inputs.get("current_A", inputs.get("current", 0.0)))
            ecm_lookup_cache = _ecm_build_step_cache(params_df)
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
            state["steps_since_ecm"] = 0
            state["last_ecm_time"] = h.time
            state["last_qvol_by_ecmid"] = {str(eid): qv for eid, qv in zip(ecm_ids, qvol_ecm)}
            try:
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state, sf, indent=2)
            except OSError:
                pass
            sys.stderr.write(
                f"[ecm_coupler] Real ECM: {len(ecm_ids)} partitions, "
                f"dt_ecm={dt_for_ecm:.4f}s, "
                f"qVol=[{min(qvol_ecm):.1f}..{max(qvol_ecm):.1f}] W/m³\n"
            )
        else:
            qvol_ecm = compute_qvol(ecm_ids, ecm_temps, inputs)
            state["steps_since_ecm"] = 0
            state["last_qvol_by_ecmid"] = {str(eid): qv for eid, qv in zip(ecm_ids, qvol_ecm)}
            try:
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state, sf, indent=2)
            except OSError:
                pass

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

    # Build output
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

    import io
    buf = io.BytesIO()
    write_header(buf, out_h)
    write_inputs(buf, {})  # none
    write_records(buf, keys, q_out)

    atomic_write(out_file, buf.getvalue())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"[ecm_coupler] ERROR: {e}\n")
        sys.exit(2)
