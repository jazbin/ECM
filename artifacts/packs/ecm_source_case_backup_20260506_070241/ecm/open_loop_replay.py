#!/usr/bin/env python3
"""Open-loop ECM replay for dt-discrepancy Test 4.

Drives CFD with Q_cell_W(t) taken directly from the validation CSV,
removing closed-loop temperature feedback entirely.

Protocol: identical to ecm_coupling_wrapper.py persistentPipe mode.
  - stdin:  one JSON request per line (ECM_COUPLING_INPUT format v1)
  - stdout: one JSON response per line (ECM_COUPLING_OUTPUT format v1)

The Q_cell_W column is interpolated at the requested time_s.
Temperature input from CFD is accepted but ignored.

After each step, writes q_gen_w_at_last_ecm to --state JSON so that
uniformPowerHeatSource (libecmFvOptions.so) sees the correct heat value.

Usage (persistentPipe from OpenFOAM controlDict):
    python3 /workspace/ecm/open_loop_replay.py \\
        --validation-csv /workspace/projectConstraintsParameters/validationData.csv \\
        --state ecm/ecm_state.json \\
        --pipe-mode
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path


INPUT_MAGIC = "ECM_COUPLING_INPUT"
OUTPUT_MAGIC = "ECM_COUPLING_OUTPUT"
FORMAT_VERSION = 1


def load_validation_csv(path: str, time_col: str, q_col: str) -> tuple[list[float], list[float]]:
    times: list[float] = []
    q_vals: list[float] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            t = row.get(time_col) or row.get('"' + time_col + '"')
            q = row.get(q_col) or row.get('"' + q_col + '"')
            if t is None or q is None:
                continue
            try:
                times.append(float(t))
                q_vals.append(float(q))
            except ValueError:
                continue
    if not times:
        raise RuntimeError(
            f"No data loaded from {path!r} "
            f"(time_col={time_col!r}, q_col={q_col!r}). "
            f"Check column names."
        )
    return times, q_vals


def interpolate(times: list[float], vals: list[float], t: float) -> float:
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    lo, hi = 0, len(times) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if times[mid] <= t:
            lo = mid
        else:
            hi = mid
    span = times[hi] - times[lo]
    if span < 1e-15:
        return vals[lo]
    alpha = (t - times[lo]) / span
    return vals[lo] + alpha * (vals[hi] - vals[lo])


def write_state_json(state_path: str, q_w: float, time_s: float, step_id: int) -> None:
    """Write ecm_state.json in the format expected by uniformPowerHeatSource."""
    payload = {
        "magic": "ECM_WRAPPER_STATE",
        "version": 3,
        "last_step_id": step_id,
        "last_time_s": time_s,
        "last_ecm_call_time_s": time_s,
        "q_gen_w_at_last_ecm": q_w,
        "dq_gen_dt_w_per_s": 0.0,
        "steps_since_last_ecm": 0,
        "state": {
            "soc": 0.5,
            "q_ah": 0.0,
            "v_rc1": 0.0,
            "v_rc2": 0.0,
            "hysteresis": 0.0,
        },
    }
    p = Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, str(p))


def build_response(req: dict, q_w: float) -> dict:
    return {
        "magic": OUTPUT_MAGIC,
        "version": FORMAT_VERSION,
        "status": "ok",
        "step_id": int(req.get("step_id", 0)),
        "time_s": float(req.get("time_s", 0.0)),
        "dt_s": float(req.get("dt_s", 1.0)),
        "electrical_mode": "current",
        "current_a": float(req.get("current_a", 0.0)),
        "T_jellyroll_degC": float(req.get("T_jellyroll_degC", 25.0)),
        "Q_GEN_W": float(q_w),
        "state_summary": {
            "soc": 0.5,
            "q_ah": 0.0,
            "v_rc1": 0.0,
            "v_rc2": 0.0,
            "hysteresis": 0.0,
        },
        "diagnostics": {
            "source": "open_loop_replay",
            "q_from_validation_w": float(q_w),
        },
    }


def build_error(error_code: str, message: str, req: dict | None = None) -> dict:
    out: dict = {
        "magic": OUTPUT_MAGIC,
        "version": FORMAT_VERSION,
        "status": "error",
        "error_code": error_code,
        "message": message,
    }
    if req:
        for key in ("step_id", "time_s", "dt_s"):
            if key in req:
                try:
                    out[key] = float(req[key]) if key != "step_id" else int(req[key])
                except (TypeError, ValueError):
                    pass
    return out


def pipe_loop(args: argparse.Namespace, times: list[float], q_vals: list[float]) -> None:
    sys.stdout.reconfigure(line_buffering=True)
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        req: dict = {}
        try:
            req = json.loads(raw)
            # Accept any request regardless of magic/version for robustness
            time_s = float(req.get("time_s", 0.0))
            step_id = int(req.get("step_id", 0))
            q_w = interpolate(times, q_vals, time_s)
            write_state_json(args.state, q_w, time_s, step_id)
            resp = build_response(req, q_w)
        except Exception as exc:
            resp = build_error("OPEN_LOOP_ERROR", str(exc), req)
        print(json.dumps(resp), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open-loop ECM replay: returns Q(t) from validation CSV without ECM physics."
    )
    parser.add_argument(
        "--validation-csv",
        required=True,
        help="Path to validationData.csv (must contain --time-col and --q-col columns).",
    )
    parser.add_argument(
        "--state",
        required=True,
        help="Path to ecm_state.json. Written each step with q_gen_w_at_last_ecm.",
    )
    parser.add_argument(
        "--pipe-mode",
        action="store_true",
        help="Run persistent pipe server (read JSON from stdin, write to stdout).",
    )
    parser.add_argument(
        "--time-col",
        default="t_ss",
        help="Column name for simulation time in validation CSV (default: t_ss).",
    )
    parser.add_argument(
        "--q-col",
        default="Q_cell_W",
        help="Column name for cell heat generation [W] in validation CSV (default: Q_cell_W).",
    )
    args = parser.parse_args()

    times, q_vals = load_validation_csv(args.validation_csv, args.time_col, args.q_col)
    print(
        f"[open_loop_replay] Loaded {len(times)} points from {args.validation_csv!r}; "
        f"Q range [{min(q_vals):.2f}, {max(q_vals):.2f}] W; "
        f"t range [{times[0]:.1f}, {times[-1]:.1f}] s",
        file=sys.stderr,
        flush=True,
    )

    if not args.pipe_mode:
        print("ERROR: --pipe-mode is required.", file=sys.stderr)
        sys.exit(1)

    pipe_loop(args, times, q_vals)


if __name__ == "__main__":
    main()
