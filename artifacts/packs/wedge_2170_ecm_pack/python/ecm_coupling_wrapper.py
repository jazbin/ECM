#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ecm_backend import (
    BaseECMBackend,
    ECMBackendError,
    ECMState,
    EcmStepBackend,
    MockECMBackend,
    MockECMConfig,
    PersistentSocketBackend,
    VendorCLIBackend,
)


INPUT_MAGIC = "ECM_COUPLING_INPUT"
OUTPUT_MAGIC = "ECM_COUPLING_OUTPUT"
STATE_MAGIC = "ECM_WRAPPER_STATE"
FORMAT_VERSION = 1


def _diagnostic_log_path(args: argparse.Namespace | None) -> Path | None:
    env_path = os.environ.get("ECM_WRAPPER_DIAGNOSTIC_LOG", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    if args is None:
        return None
    try:
        state_path = Path(args.state).resolve()
    except Exception:
        return None
    return state_path.parent / "ecm_wrapper_diagnostic.log"


def _log_diagnostic(args: argparse.Namespace | None, message: str) -> None:
    path = _diagnostic_log_path(args)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


class WrapperError(RuntimeError):
    def __init__(self, error_code: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.exit_code = exit_code
        self.message = message


@dataclass
class StepRequest:
    step_id: int
    time_s: float
    dt_s: float
    electrical_mode: str
    current_a: float
    t_jellyroll_degc: float
    reset_state: bool
    init_state: ECMState | None = None


@dataclass
class PersistedState:
    last_step_id: int
    last_time_s: float
    state: ECMState
    # Call-interval interpolation fields (state format v2)
    last_ecm_call_time_s: float = 0.0
    q_gen_w_at_last_ecm: float = 0.0
    dq_gen_dt_w_per_s: float = 0.0
    # Iteration-based gating (state format v3)
    steps_since_last_ecm: int = 0


def parse_key_value_pairs(items: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise WrapperError(
                "CONFIG_ERROR",
                f"Invalid --vendor-env entry '{item}'. Expected KEY=VALUE format.",
                10,
            )
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise WrapperError(
                "CONFIG_ERROR",
                f"Invalid --vendor-env entry '{item}'. Empty key is not allowed.",
                10,
            )
        out[key] = value
    return out


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tf:
        tmp_name = tf.name
        json.dump(payload, tf, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
    os.replace(tmp_name, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError as exc:
        raise WrapperError("INPUT_READ_ERROR", f"Input file not found: {path}", 2) from exc
    except json.JSONDecodeError as exc:
        raise WrapperError("INPUT_PARSE_ERROR", f"Invalid JSON in input file {path}: {exc}", 2) from exc
    except OSError as exc:
        raise WrapperError("INPUT_READ_ERROR", f"Failed to read input file {path}: {exc}", 2) from exc

    if not isinstance(payload, dict):
        raise WrapperError("INPUT_PARSE_ERROR", "Input JSON must be a JSON object", 2)
    return payload


def validate_finite_scalar(name: str, value: Any) -> float:
    try:
        value_f = float(value)
    except (TypeError, ValueError) as exc:
        raise WrapperError("INPUT_VALIDATION_ERROR", f"{name} must be numeric, got {value}", 2) from exc
    if not math.isfinite(value_f):
        raise WrapperError("INPUT_VALIDATION_ERROR", f"{name} must be finite, got {value_f}", 2)
    return value_f


def parse_request(payload: dict[str, Any]) -> StepRequest:
    if payload.get("magic") != INPUT_MAGIC:
        raise WrapperError(
            "INPUT_VALIDATION_ERROR",
            f"Invalid input magic. Expected '{INPUT_MAGIC}', got '{payload.get('magic')}'",
            2,
        )

    version = payload.get("version")
    try:
        version_i = int(version)
    except (TypeError, ValueError) as exc:
        raise WrapperError("INPUT_VALIDATION_ERROR", f"Invalid input version: {version}", 2) from exc
    if version_i != FORMAT_VERSION:
        raise WrapperError(
            "INPUT_VALIDATION_ERROR",
            f"Unsupported input version {version_i}. Expected {FORMAT_VERSION}.",
            2,
        )

    try:
        step_id = int(payload["step_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WrapperError("INPUT_VALIDATION_ERROR", "step_id must be an integer", 2) from exc
    if step_id < 0:
        raise WrapperError("INPUT_VALIDATION_ERROR", "step_id must be >= 0", 2)

    time_s = validate_finite_scalar("time_s", payload.get("time_s"))
    dt_s = validate_finite_scalar("dt_s", payload.get("dt_s"))
    if dt_s <= 0.0:
        raise WrapperError("INPUT_VALIDATION_ERROR", "dt_s must be > 0", 2)

    electrical_mode = payload.get("electrical_mode")
    if electrical_mode != "current":
        raise WrapperError(
            "INPUT_VALIDATION_ERROR",
            f"Only electrical_mode='current' is supported in lumped v1. Got '{electrical_mode}'.",
            2,
        )

    current_a = validate_finite_scalar("current_a", payload.get("current_a"))
    t_jellyroll_degc = validate_finite_scalar("T_jellyroll_degC", payload.get("T_jellyroll_degC"))

    reset_state = bool(payload.get("reset_state", False))

    init_state = None
    if payload.get("init_state") is not None:
        try:
            init_state = ECMState.from_dict(payload["init_state"])
        except (KeyError, TypeError, ValueError, ECMBackendError) as exc:
            raise WrapperError("INPUT_VALIDATION_ERROR", f"Invalid init_state: {exc}", 2) from exc

    return StepRequest(
        step_id=step_id,
        time_s=time_s,
        dt_s=dt_s,
        electrical_mode=electrical_mode,
        current_a=current_a,
        t_jellyroll_degc=t_jellyroll_degc,
        reset_state=reset_state,
        init_state=init_state,
    )


def parse_persisted_state(path: Path) -> PersistedState | None:
    if not path.exists():
        return None

    payload = read_json(path)

    if payload.get("magic") != STATE_MAGIC:
        raise WrapperError(
            "STATE_VALIDATION_ERROR",
            f"Invalid state file magic in {path}. Expected '{STATE_MAGIC}'.",
            3,
        )

    version = payload.get("version")
    try:
        version_i = int(version)
    except (TypeError, ValueError) as exc:
        raise WrapperError("STATE_VALIDATION_ERROR", f"Invalid state file version: {version}", 3) from exc
    if version_i not in (1, 2, 3):
        raise WrapperError(
            "STATE_VALIDATION_ERROR",
            f"Unsupported state file version {version_i}. Expected 1, 2, or 3.",
            3,
        )

    try:
        last_step_id = int(payload["last_step_id"])
        last_time_s = float(payload["last_time_s"])
        state = ECMState.from_dict(payload["state"])
    except (KeyError, TypeError, ValueError, ECMBackendError) as exc:
        raise WrapperError("STATE_VALIDATION_ERROR", f"Invalid state file contents: {exc}", 3) from exc

    if not math.isfinite(last_time_s):
        raise WrapperError("STATE_VALIDATION_ERROR", f"Invalid last_time_s in {path}: {last_time_s}", 3)

    # v2 interpolation fields; default to "treat next call as first ECM fire" for v1 state files
    last_ecm_call_time_s = float(payload.get("last_ecm_call_time_s", last_time_s))
    q_gen_w_at_last_ecm  = float(payload.get("q_gen_w_at_last_ecm", 0.0))
    dq_gen_dt_w_per_s    = float(payload.get("dq_gen_dt_w_per_s", 0.0))
    # v3 iteration-based gating; default 0 so next step triggers a fire on v1/v2 state files
    steps_since_last_ecm = int(payload.get("steps_since_last_ecm", 0))

    return PersistedState(
        last_step_id=last_step_id,
        last_time_s=last_time_s,
        state=state,
        last_ecm_call_time_s=last_ecm_call_time_s,
        q_gen_w_at_last_ecm=q_gen_w_at_last_ecm,
        dq_gen_dt_w_per_s=dq_gen_dt_w_per_s,
        steps_since_last_ecm=steps_since_last_ecm,
    )


def build_state_payload(persisted: PersistedState) -> dict[str, Any]:
    return {
        "magic": STATE_MAGIC,
        "version": 3,
        "last_step_id": int(persisted.last_step_id),
        "last_time_s": float(persisted.last_time_s),
        "state": persisted.state.to_dict(),
        "last_ecm_call_time_s":  float(persisted.last_ecm_call_time_s),
        "q_gen_w_at_last_ecm":   float(persisted.q_gen_w_at_last_ecm),
        "dq_gen_dt_w_per_s":     float(persisted.dq_gen_dt_w_per_s),
        "steps_since_last_ecm":  int(persisted.steps_since_last_ecm),
    }


def _read_init_state_from_csv(csv_path: str, args: argparse.Namespace) -> ECMState | None:
    """
    Read initial ECM state from the first data row of the electrical-inputs CSV.

    Recognised columns (all optional; falls back to CLI args for missing ones):
      init_q_ah      — initial charge throughput [Ah] (positive = discharged)
      init_soc       — initial SOC [0-1]; converted via Qnom_Ah from cellprops.csv
      init_v_rc1     — initial RC1 branch voltage [V]
      init_v_rc2     — initial RC2 branch voltage [V]
      init_hysteresis — initial hysteresis state [-1..1]
    """
    import csv as _csv
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            row = next(reader, None)
    except OSError:
        return None

    if row is None:
        return None

    # Strip whitespace and quotes from column names and values
    row = {k.strip().strip('"').strip("'").lower(): v.strip().strip('"').strip("'")
           for k, v in row.items() if k is not None}

    def _float(key: str, default: float) -> float:
        val = row.get(key, "").strip()
        if not val:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    q_ah = float(args.init_q_ah)
    if "init_q_ah" in row and row["init_q_ah"].strip():
        q_ah = _float("init_q_ah", q_ah)
    elif "init_soc" in row and row["init_soc"].strip():
        # Convert SOC → q_ah using Qnom from cellprops if available
        soc = _float("init_soc", float("nan"))
        if math.isfinite(soc):
            try:
                import pandas as pd
                cellprops_path = getattr(args, "ecm_step_cellprops", None)
                if cellprops_path:
                    cp = pd.read_csv(cellprops_path)
                    for col in ("Qnom_Ah", "capacity_Ah"):
                        if col in cp.columns:
                            qnom = float(cp[col].iloc[0])
                            q_ah = max(0.0, (1.0 - soc) * qnom)
                            break
            except Exception:
                pass

    v_rc1 = _float("init_v_rc1", float(args.init_v_rc[0]))
    v_rc2 = _float("init_v_rc2", float(args.init_v_rc[1]))
    hyst  = _float("init_hysteresis", float(args.init_hysteresis))

    return ECMState(q_ah=q_ah, v_rc=[v_rc1, v_rc2], hysteresis=hyst)


def initial_state_from_request_or_args(args: argparse.Namespace, request: StepRequest) -> ECMState:
    if request.init_state is not None:
        return request.init_state

    # Try reading initial state from electrical-inputs CSV if --init-from-csv was given
    csv_state = None
    init_csv = getattr(args, "init_from_csv", None)
    if init_csv:
        try:
            csv_state = _read_init_state_from_csv(init_csv, args)
        except Exception as exc:
            _log_diagnostic(args, f"init-from-csv read failed (using CLI defaults): {exc}")

    if csv_state is not None:
        state = csv_state
    else:
        state = ECMState(
            q_ah=float(args.init_q_ah),
            v_rc=[float(args.init_v_rc[0]), float(args.init_v_rc[1])],
            hysteresis=float(args.init_hysteresis),
        )
    try:
        state.validate()
    except ECMBackendError as exc:
        raise WrapperError("CONFIG_ERROR", f"Invalid initial state: {exc}", 10) from exc
    return state


def progress_violation_message(request: StepRequest, persisted: PersistedState) -> str | None:
    if request.step_id <= persisted.last_step_id:
        return (
            f"Incoming step_id={request.step_id} is not greater than "
            f"last_step_id={persisted.last_step_id}."
        )

    if request.time_s <= persisted.last_time_s:
        return (
            f"Incoming time_s={request.time_s} is not greater than "
            f"last_time_s={persisted.last_time_s}."
        )

    expected_dt = request.time_s - persisted.last_time_s
    if not math.isclose(expected_dt, request.dt_s, rel_tol=0.0, abs_tol=1.0e-12):
        return (
            f"Incoming dt_s={request.dt_s} does not match time increment "
            f"time_s-last_time_s={expected_dt}."
        )

    return None


def _resolve_socket_path(args: argparse.Namespace) -> str:
    if args.ecm_socket:
        return str(Path(args.ecm_socket).resolve())
    return str(Path(args.state).resolve().parent / "ecm_daemon.sock")


def _ensure_daemon_running(args: argparse.Namespace, sock_path: str) -> None:
    """Start ecm_daemon.py in the background if it is not already listening."""
    import socket as _socket
    import subprocess as _subprocess
    import time

    pid_path = str(Path(sock_path).with_suffix(".pid"))

    # Quick liveness check — try to ping the daemon
    probe = PersistentSocketBackend(sock_path, timeout_s=1.0)
    if probe.ping():
        _log_diagnostic(args, f"persistent daemon already responding on socket={sock_path}")
        return  # already running

    # Not responding — launch it
    daemon_script = Path(__file__).resolve().parent / "ecm_daemon.py"
    diag_path = _diagnostic_log_path(args)
    cmd = [
        sys.executable, str(daemon_script),
        "--socket", sock_path,
        "--pid",    pid_path,
        "--backend", args.backend,
        "--ecm-step-params",    str(args.ecm_step_params),
        "--ecm-step-cellprops", str(args.ecm_step_cellprops),
    ]
    if args.ecm_step_module:
        cmd += ["--ecm-step-module", str(args.ecm_step_module)]

    _log_diagnostic(
        args,
        "starting persistent daemon "
        f"script={daemon_script} socket={sock_path} pid_file={pid_path} "
        f"backend={args.backend} params={args.ecm_step_params} "
        f"cellprops={args.ecm_step_cellprops} module={args.ecm_step_module or 'default'} "
        f"python={sys.executable}",
    )
    diag_stream = None
    if diag_path is not None:
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        diag_stream = open(diag_path, "a", encoding="utf-8")

    _subprocess.Popen(
        cmd,
        stdout=diag_stream if diag_stream is not None else _subprocess.DEVNULL,
        stderr=diag_stream if diag_stream is not None else _subprocess.DEVNULL,
        start_new_session=True,  # detach from OpenFOAM process group
    )
    if diag_stream is not None:
        diag_stream.close()

    # Wait up to 10 seconds for daemon to become ready
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        time.sleep(0.1)
        if probe.ping():
            _log_diagnostic(args, f"persistent daemon is ready on socket={sock_path}")
            return

    _log_diagnostic(args, f"persistent daemon failed to become ready on socket={sock_path}")
    raise WrapperError(
        "DAEMON_START_ERROR",
        f"ECM daemon did not become ready within 10 s (socket={sock_path}). "
        "Check that ecm_daemon.py, params.csv, and cellprops.csv are accessible.",
        11,
    )


def build_backend(args: argparse.Namespace) -> BaseECMBackend:
    _log_diagnostic(
        args,
        "build_backend begin "
        f"backend={args.backend} persistent_ecm={args.persistent_ecm} "
        f"module={args.ecm_step_module or 'default'} "
        f"params={args.ecm_step_params} cellprops={args.ecm_step_cellprops} "
        f"cwd={Path.cwd()} python={sys.executable}",
    )
    if args.backend == "mock-inproc":
        config = MockECMConfig(
            capacity_ah=float(args.capacity_ah),
            ocv_min_v=float(args.ocv_min_v),
            ocv_max_v=float(args.ocv_max_v),
            r0_ohm=float(args.r0_ohm),
            r1_ohm=float(args.r1_ohm),
            r2_ohm=float(args.r2_ohm),
            tau1_s=float(args.tau1_s),
            tau2_s=float(args.tau2_s),
            hyst_mag_v=float(args.hyst_mag_v),
        )
        try:
            config.validate()
        except ECMBackendError as exc:
            _log_diagnostic(args, f"mock-inproc config validation failed: {exc}")
            raise WrapperError("CONFIG_ERROR", f"Invalid mock backend configuration: {exc}", 10) from exc
        _log_diagnostic(args, "build_backend success backend=mock-inproc")
        return MockECMBackend(config)

    if args.backend == "vendor-cli":
        if not args.vendor_exec:
            raise WrapperError(
                "CONFIG_ERROR",
                "--vendor-exec is required for --backend vendor-cli",
                10,
            )
        env_overrides = parse_key_value_pairs(args.vendor_env)
        return VendorCLIBackend(
            executable=args.vendor_exec,
            timeout_s=float(args.vendor_timeout_s),
            working_dir=args.vendor_working_dir,
            env_overrides=env_overrides,
        )

    if args.backend == "ecm-step":
        if args.persistent_ecm:
            sock_path = _resolve_socket_path(args)
            _ensure_daemon_running(args, sock_path)
            _log_diagnostic(args, f"build_backend success backend=ecm-step persistent socket={sock_path}")
            return PersistentSocketBackend(sock_path)
        try:
            backend = EcmStepBackend(
                params_path=args.ecm_step_params,
                cellprops_path=args.ecm_step_cellprops,
                ecm_step_module_path=args.ecm_step_module,
            )
        except ECMBackendError as exc:
            _log_diagnostic(args, f"build_backend failed backend=ecm-step error={exc}")
            _log_diagnostic(args, traceback.format_exc().rstrip())
            raise
        _log_diagnostic(args, "build_backend success backend=ecm-step in-process")
        return backend

    if args.backend == "mock-inproc":
        if args.persistent_ecm:
            sock_path = _resolve_socket_path(args)
            _ensure_daemon_running(args, sock_path)
            return PersistentSocketBackend(sock_path)

    raise WrapperError("CONFIG_ERROR", f"Unsupported backend '{args.backend}'", 10)


def validate_runtime_bounds(args: argparse.Namespace, request: StepRequest) -> None:
    tmin = float(args.temp_min_degc)
    tmax = float(args.temp_max_degc)
    if request.t_jellyroll_degc < tmin or request.t_jellyroll_degc > tmax:
        raise WrapperError(
            "INPUT_VALIDATION_ERROR",
            f"T_jellyroll_degC={request.t_jellyroll_degc} is outside bounds [{tmin}, {tmax}]",
            2,
        )


def validate_result(args: argparse.Namespace, result_q_gen_w: float, result_v_t_v: float | None, next_state: ECMState) -> None:
    if not math.isfinite(result_q_gen_w):
        raise WrapperError("OUTPUT_VALIDATION_ERROR", f"Q_GEN_W is not finite: {result_q_gen_w}", 5)

    if args.qgen_min_w is not None and result_q_gen_w < float(args.qgen_min_w):
        raise WrapperError(
            "OUTPUT_VALIDATION_ERROR",
            f"Q_GEN_W={result_q_gen_w} is below qgen_min_w={args.qgen_min_w}",
            5,
        )

    if args.qgen_max_w is not None and result_q_gen_w > float(args.qgen_max_w):
        raise WrapperError(
            "OUTPUT_VALIDATION_ERROR",
            f"Q_GEN_W={result_q_gen_w} is above qgen_max_w={args.qgen_max_w}",
            5,
        )

    if result_v_t_v is not None:
        if not math.isfinite(result_v_t_v):
            raise WrapperError("OUTPUT_VALIDATION_ERROR", f"V_T_V is not finite: {result_v_t_v}", 5)
        if args.vt_min_v is not None and result_v_t_v < float(args.vt_min_v):
            raise WrapperError(
                "OUTPUT_VALIDATION_ERROR",
                f"V_T_V={result_v_t_v} is below vt_min_v={args.vt_min_v}",
                5,
            )
        if args.vt_max_v is not None and result_v_t_v > float(args.vt_max_v):
            raise WrapperError(
                "OUTPUT_VALIDATION_ERROR",
                f"V_T_V={result_v_t_v} is above vt_max_v={args.vt_max_v}",
                5,
            )

    try:
        next_state.validate()
    except ECMBackendError as exc:
        raise WrapperError("OUTPUT_VALIDATION_ERROR", f"Invalid state_next: {exc}", 5) from exc


def _trim_csv_history_to_time(path: Path, cutoff_s: float) -> tuple[int, int]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        return (0, 0)

    header = rows[0]
    time_idx = None
    for i, name in enumerate(header):
        if name.strip().lower() in ("time_s", "time", "t_s"):
            time_idx = i
            break
    if time_idx is None:
        return (len(rows) - 1, 0)

    kept = [header]
    removed = 0
    tol = 1e-12
    for row in rows[1:]:
        if time_idx >= len(row):
            kept.append(row)
            continue
        try:
            t_val = float(row[time_idx])
        except (TypeError, ValueError):
            kept.append(row)
            continue
        if t_val <= cutoff_s + tol:
            kept.append(row)
        else:
            removed += 1

    if removed > 0:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tf:
            w = csv.writer(tf)
            w.writerows(kept)
            tf.flush()
            os.fsync(tf.fileno())
            tmp_name = tf.name
        os.replace(tmp_name, path)

    return (len(rows) - 1, removed)


def cleanup_rewind_artifacts(args: argparse.Namespace, cutoff_s: float) -> None:
    state_dir = Path(args.state).resolve().parent
    removed_files: list[str] = []

    for name in ("ecm_in.json", "ecm_out.json", "ecm_in.bin", "ecm_out.bin", "ecm_in.tmp", "ecm_out.tmp"):
        p = state_dir / name
        if not p.exists():
            continue
        try:
            p.unlink()
            removed_files.append(name)
        except OSError as exc:
            _log_diagnostic(args, f"rewind cleanup: failed to remove {p}: {exc}")

    trimmed_summaries: list[str] = []
    for csv_file in sorted(state_dir.glob("ecm_wrapper*.csv")):
        try:
            total, removed = _trim_csv_history_to_time(csv_file, cutoff_s)
        except OSError as exc:
            _log_diagnostic(args, f"rewind cleanup: failed to trim {csv_file}: {exc}")
            continue
        if removed > 0:
            trimmed_summaries.append(f"{csv_file.name} removed={removed}/{total}")

    if removed_files or trimmed_summaries:
        _log_diagnostic(
            args,
            (
                f"rewind cleanup at time_s={cutoff_s:.12g}: "
                f"removed_files={removed_files} "
                f"trimmed_csv={trimmed_summaries}"
            ),
        )


def build_success_output(
    request: StepRequest,
    q_gen_w: float,
    v_t_v: float | None,
    state_next: ECMState,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "magic": OUTPUT_MAGIC,
        "version": FORMAT_VERSION,
        "status": "ok",
        "step_id": int(request.step_id),
        "time_s": float(request.time_s),
        "dt_s": float(request.dt_s),
        "electrical_mode": request.electrical_mode,
        "current_a": float(request.current_a),
        "T_jellyroll_degC": float(request.t_jellyroll_degc),
        "Q_GEN_W": float(q_gen_w),
        "state_summary": state_next.to_dict(),
        "diagnostics": diagnostics,
    }
    if v_t_v is not None:
        payload["V_T_V"] = float(v_t_v)
    return payload


def build_error_output(
    error_code: str,
    message: str,
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "magic": OUTPUT_MAGIC,
        "version": FORMAT_VERSION,
        "status": "error",
        "error_code": error_code,
        "message": message,
    }

    if isinstance(request_payload, dict):
        if "step_id" in request_payload:
            try:
                payload["step_id"] = int(request_payload["step_id"])
            except (TypeError, ValueError):
                pass
        if "time_s" in request_payload:
            try:
                payload["time_s"] = float(request_payload["time_s"])
            except (TypeError, ValueError):
                pass
        if "dt_s" in request_payload:
            try:
                payload["dt_s"] = float(request_payload["dt_s"])
            except (TypeError, ValueError):
                pass

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Production one-step lumped ECM coupling wrapper for OpenFOAM battery CHT coupling. "
            "Input is one representative jelly-roll temperature and one current value. "
            "Output is one total heat generation value and optional electrical diagnostics."
        )
    )

    parser.add_argument("--input", required=True, help="Path to wrapper input JSON.")
    parser.add_argument("--output", required=True, help="Path to wrapper output JSON.")
    parser.add_argument("--state", required=True, help="Path to persistent wrapper state JSON.")

    parser.add_argument(
        "--backend",
        choices=["mock-inproc", "vendor-cli", "ecm-step"],
        default="mock-inproc",
        help="Backend selection.",
    )

    parser.add_argument("--vendor-exec", default=None, help="Executable path for backend=vendor-cli.")
    parser.add_argument("--vendor-working-dir", default=None, help="Optional working directory for backend=vendor-cli.")
    parser.add_argument("--vendor-timeout-s", type=float, default=30.0, help="Timeout for backend=vendor-cli.")
    parser.add_argument(
        "--vendor-env",
        nargs="*",
        default=None,
        help="Optional KEY=VALUE entries forwarded to backend=vendor-cli.",
    )

    parser.add_argument("--init-q-ah", type=float, default=0.20, help="Default initial q_ah if no state file exists.")
    parser.add_argument("--init-hysteresis", type=float, default=0.0, help="Default initial hysteresis if no state file exists.")
    parser.add_argument(
        "--init-v-rc",
        type=float,
        nargs=2,
        default=[0.0, 0.0],
        metavar=("VRC1", "VRC2"),
        help="Default initial RC branch voltages if no state file exists.",
    )
    parser.add_argument(
        "--init-from-csv",
        default=None,
        help=(
            "Path to the electrical-inputs CSV file. "
            "When provided, the wrapper reads initial ECM state from optional columns "
            "in the first data row: init_q_ah (or init_soc), init_v_rc1, init_v_rc2, "
            "init_hysteresis. Overrides --init-q-ah / --init-v-rc / --init-hysteresis "
            "when the columns are present. init_soc is converted via Qnom_Ah from "
            "cellprops.csv; ignored if both init_q_ah and init_soc are absent."
        ),
    )

    parser.add_argument("--temp-min-degc", type=float, default=-60.0, help="Lower bound for input T_jellyroll_degC.")
    parser.add_argument("--temp-max-degc", type=float, default=150.0, help="Upper bound for input T_jellyroll_degC.")
    parser.add_argument("--vt-min-v", type=float, default=0.0, help="Lower bound for output V_T_V.")
    parser.add_argument("--vt-max-v", type=float, default=10.0, help="Upper bound for output V_T_V.")
    parser.add_argument("--qgen-min-w", type=float, default=None, help="Optional lower bound for output Q_GEN_W.")
    parser.add_argument("--qgen-max-w", type=float, default=None, help="Optional upper bound for output Q_GEN_W.")

    # ecm-step backend
    _here = Path(__file__).resolve().parent
    parser.add_argument(
        "--ecm-step-module",
        default=None,
        help="Path to ecm_step.py (default: ecm_step.py next to this script).",
    )
    parser.add_argument(
        "--ecm-step-params",
        default=str(_here / "params.csv"),
        help="Path to params.csv for ecm-step backend.",
    )
    parser.add_argument(
        "--ecm-step-cellprops",
        default=str(_here / "cellprops.csv"),
        help="Path to cellprops.csv for ecm-step backend.",
    )

    # ECM call gating
    parser.add_argument(
        "--ecm-call-every-n-steps",
        type=int,
        default=0,
        dest="ecm_call_every_n_steps",
        help=(
            "Fire ECM every N CFD timesteps (iteration-based gating). "
            "Takes priority over --ecm-call-interval when N > 0. "
            "Recommended for adaptive-dt simulations where simulation-time gating "
            "is unpredictable. Default 0 = use --ecm-call-interval instead."
        ),
    )
    parser.add_argument(
        "--ecm-call-interval",
        type=float,
        default=0.5,
        help=(
            "Minimum simulation-time interval [s] between actual ECM calls. "
            "Between calls Q is extrapolated with a first-order hold. "
            "Set to 0 to call every CFD step (legacy behaviour). "
            "Default 0.5 s ≈ tau1/2 for 4680 NCA."
        ),
    )
    parser.add_argument(
        "--ecm-q-deriv-clamp",
        type=float,
        default=10.0,
        help="Max absolute dQ/dt [W/s] used in first-order-hold interpolation. Prevents runaway extrapolation.",
    )

    parser.add_argument("--capacity-ah", type=float, default=9.0, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--ocv-min-v", type=float, default=2.7, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--ocv-max-v", type=float, default=4.2, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--r0-ohm", type=float, default=0.007, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--r1-ohm", type=float, default=0.0027, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--r2-ohm", type=float, default=0.0015, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--tau1-s", type=float, default=1.0, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--tau2-s", type=float, default=45.0, help="Mock backend configuration (4680 NCA).")
    parser.add_argument("--hyst-mag-v", type=float, default=0.003, help="Mock backend configuration (4680 NCA).")

    # Persistent daemon mode
    parser.add_argument(
        "--persistent-ecm",
        action="store_true",
        help=(
            "Use a persistent ecm_daemon.py process instead of spawning a new process "
            "for each call. Eliminates ~45 ms/call Python startup overhead. "
            "Daemon is auto-started on first invocation and stays alive between calls. "
            "Only supported with --backend ecm-step or mock-inproc."
        ),
    )
    parser.add_argument(
        "--ecm-socket",
        default=None,
        help=(
            "Path to the Unix domain socket for the persistent ECM daemon. "
            "Default: <state_file_dir>/ecm_daemon.sock"
        ),
    )

    parser.add_argument(
        "--pipe-mode",
        action="store_true",
        help=(
            "Run as a persistent process: read JSON requests line-by-line from stdin, "
            "write JSON responses to stdout. Used with ioMode=persistentPipe in the "
            "OpenFOAM function object. Eliminates per-call Python startup overhead."
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Print a short success line to stdout.")
    parser.add_argument(
        "--on-restart-rewind",
        choices=["reset", "error"],
        default="reset",
        help=(
            "Action when incoming step/time are behind persisted ECM state (typical OpenFOAM restart "
            "from latest written folder while solver previously advanced further): "
            "'reset' discards persisted state and re-initializes from init_state/CLI defaults; "
            "'error' keeps strict monotonic behavior."
        ),
    )
    return parser.parse_args()


def run(args: argparse.Namespace, backend: BaseECMBackend | None = None) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    state_path = Path(args.state)

    request_payload = read_json(input_path)
    request = parse_request(request_payload)
    validate_runtime_bounds(args, request)

    if backend is None:
        backend = build_backend(args)

    persisted = None if request.reset_state else parse_persisted_state(state_path)
    auto_reset = False
    rewind_note = None
    if not request.reset_state and persisted is not None:
        violation = progress_violation_message(request, persisted)
        if violation is not None:
            if args.on_restart_rewind == "reset":
                auto_reset = True
                rewind_note = (
                    "Detected restart rewind relative to persisted ECM state; "
                    "resetting wrapper state for this step. "
                    f"Reason: {violation}"
                )
                _log_diagnostic(args, rewind_note)
                cleanup_rewind_artifacts(args, request.time_s)
                persisted = None
            else:
                raise WrapperError("STATE_PROGRESS_ERROR", violation, 3)

    effective_reset = request.reset_state or auto_reset
    state_in = (
        initial_state_from_request_or_args(args, request)
        if effective_reset or persisted is None
        else persisted.state
    )

    # ── ECM call gating ───────────────────────────────────────────────────────
    # Two modes (mutually exclusive; iteration-based takes priority):
    #
    #  Iteration-based (--ecm-call-every-n-steps N > 0):
    #    Fire after every N CFD timesteps regardless of simulation-time increment.
    #    Robust under adaptive dt — N steps always means exactly N solver iterations.
    #
    #  Time-based (--ecm-call-interval T, default):
    #    Fire when accumulated simulation time since last fire >= T seconds.
    #    May fire more/less frequently under large dt swings.
    #
    # Between fires Q is extrapolated with a first-order hold using the
    # derivative estimated from the last two ECM calls.  The ECM itself
    # receives the full accumulated simulation-time dt so its RC integrators
    # stay correct.
    is_first_call = (effective_reset or persisted is None)
    dt_since_ecm  = 0.0 if is_first_call else (request.time_s - persisted.last_ecm_call_time_s)

    call_every_n    = int(args.ecm_call_every_n_steps)
    call_interval_s = float(args.ecm_call_interval)

    if call_every_n > 0:
        # Iteration-based gating: fire every N steps → gaps of exactly N between fires
        # (steps_since counts steps elapsed since last fire; fire when it reaches N-1)
        steps_since = 0 if is_first_call else persisted.steps_since_last_ecm
        ecm_fired   = is_first_call or (steps_since >= call_every_n - 1)
    else:
        # Time-based gating (legacy / default)
        ecm_fired = is_first_call or (dt_since_ecm >= call_interval_s)

    if ecm_fired:
        dt_for_ecm = request.dt_s if is_first_call else dt_since_ecm
        try:
            result = backend.step(
                dt_s=dt_for_ecm,
                current_a=request.current_a,
                t_cell_degc=request.t_jellyroll_degc,
                state=state_in,
            )
        except ECMBackendError as exc:
            raise WrapperError("BACKEND_ERROR", str(exc), 4) from exc
        except OSError as exc:
            raise WrapperError("BACKEND_ERROR", f"Backend OS error: {exc}", 4) from exc

        validate_result(args, result.q_gen_w, result.v_t_v, result.state_next)

        # Estimate dQ/dt from last two ECM fires for use in next interpolation window
        if not is_first_call and dt_since_ecm > 0.0:
            raw_deriv = (result.q_gen_w - persisted.q_gen_w_at_last_ecm) / dt_since_ecm
            clamp = float(args.ecm_q_deriv_clamp)
            new_dq_dt = max(-clamp, min(clamp, raw_deriv))
        else:
            new_dq_dt = 0.0

        q_gen_w    = result.q_gen_w
        state_next = result.state_next
        v_t_v      = result.v_t_v
        diagnostics = result.diagnostics

    else:
        # First-order hold: Q(t) = Q_ecm + dQ/dt * Δt_since_ecm
        q_gen_w = persisted.q_gen_w_at_last_ecm + persisted.dq_gen_dt_w_per_s * dt_since_ecm
        q_gen_w = max(0.0, q_gen_w)   # heat generation is non-negative

        if not math.isfinite(q_gen_w):
            raise WrapperError("OUTPUT_VALIDATION_ERROR", f"Interpolated Q_GEN_W is not finite: {q_gen_w}", 5)

        new_dq_dt  = persisted.dq_gen_dt_w_per_s
        state_next = persisted.state
        v_t_v      = None   # terminal voltage not available between ECM fires
        diagnostics = {"ecm_interpolated": True, "dt_since_ecm_s": dt_since_ecm}
    # ─────────────────────────────────────────────────────────────────────────

    if rewind_note is not None:
        diagnostics = dict(diagnostics)
        diagnostics["wrapper_state_reinitialized"] = True
        diagnostics["wrapper_state_reinitialized_reason"] = rewind_note

    success_output = build_success_output(
        request=request,
        q_gen_w=q_gen_w,
        v_t_v=v_t_v,
        state_next=state_next,
        diagnostics=diagnostics,
    )

    next_persisted = PersistedState(
        last_step_id=request.step_id,
        last_time_s=request.time_s,
        state=state_next,
        last_ecm_call_time_s=request.time_s if ecm_fired else persisted.last_ecm_call_time_s,
        q_gen_w_at_last_ecm=q_gen_w if ecm_fired else persisted.q_gen_w_at_last_ecm,
        dq_gen_dt_w_per_s=new_dq_dt,
        steps_since_last_ecm=0 if ecm_fired else (0 if is_first_call else persisted.steps_since_last_ecm + 1),
    )

    write_json_atomic(output_path, success_output)
    write_json_atomic(state_path, build_state_payload(next_persisted))

    if args.verbose:
        vt_text   = "None" if v_t_v is None else f"{v_t_v:.8f}"
        fire_flag = "" if ecm_fired else f" [interp dt_ecm={dt_since_ecm:.3f}s dQ/dt={new_dq_dt:.4f}]"
        print(
            f"step_id={request.step_id} "
            f"time_s={request.time_s:.12g} "
            f"dt_s={request.dt_s:.12g} "
            f"T_jellyroll_degC={request.t_jellyroll_degc:.8f} "
            f"current_a={request.current_a:.8f} "
            f"Q_GEN_W={q_gen_w:.8f} "
            f"V_T_V={vt_text}"
            f"{fire_flag}"
        )

    return 0


def pipe_mode_loop(args: argparse.Namespace) -> None:
    """Persistent pipe server: stdin -> process -> stdout.

    The OpenFOAM function object keeps this process alive for the entire
    simulation. Modules load once; per-call cost is just the ECM computation.
    """
    import sys as _sys
    import tempfile as _tmp

    # Build backend once -- loads numpy, pandas, ecm_step.py here
    _log_diagnostic(args, "pipe_mode_loop starting")
    backend = build_backend(args)

    # Unbuffered stdout so C++ reader gets each response immediately
    _sys.stdout.reconfigure(line_buffering=True)

    state_path = Path(args.state)

    for line in _sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            _log_diagnostic(
                args,
                "pipe request "
                f"step_id={req.get('step_id')} time_s={req.get('time_s')} "
                f"dt_s={req.get('dt_s')} current_a={req.get('current_a')} "
                f"T_jellyroll_degC={req.get('t_jellyroll_degC')}",
            )
        except Exception:
            _log_diagnostic(args, f"pipe request could not be summarised raw={line[:500]}")

        # Write request to temp file, run(), read response from temp file
        with _tmp.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf_in:
            tf_in.write(line)
            tf_in_path = Path(tf_in.name)
        tf_out_path = tf_in_path.with_suffix(".out.json")

        saved_input  = args.input
        saved_output = args.output
        args.input  = str(tf_in_path)
        args.output = str(tf_out_path)
        try:
            try:
                run(args, backend=backend)
            except SystemExit:
                pass
            except WrapperError as exc:
                _log_diagnostic(args, f"pipe request wrapper error code={exc.error_code} message={exc.message}")
                write_json_atomic(tf_out_path, build_error_output(exc.error_code, exc.message))
            except Exception as exc:  # noqa: BLE001
                _log_diagnostic(args, f"pipe request unhandled error: {exc}")
                _log_diagnostic(args, traceback.format_exc().rstrip())
                write_json_atomic(tf_out_path, build_error_output("UNHANDLED_ERROR", str(exc)))

            if tf_out_path.exists():
                resp = tf_out_path.read_text(encoding="utf-8").replace("\n", " ").replace("\r", "")
                _log_diagnostic(args, f"pipe response {resp[:500]}")
                print(resp, flush=True)
            else:
                _log_diagnostic(args, "pipe response missing output file")
                print('{"status":"error","error_code":"NO_OUTPUT","message":"wrapper produced no output"}', flush=True)
        finally:
            args.input  = saved_input
            args.output = saved_output
            tf_in_path.unlink(missing_ok=True)
            tf_out_path.unlink(missing_ok=True)


def main() -> None:
    args = parse_args()

    if args.pipe_mode:
        pipe_mode_loop(args)
        return

    request_payload_for_error: dict[str, Any] | None = None
    output_path = Path(args.output)

    try:
        request_payload_for_error = read_json(Path(args.input))
        exit_code = run(args)
        raise SystemExit(exit_code)
    except WrapperError as exc:
        error_payload = build_error_output(exc.error_code, exc.message, request_payload_for_error)
        try:
            write_json_atomic(output_path, error_payload)
        except Exception as write_exc:
            print(f"Failed to write error output to {output_path}: {write_exc}", file=sys.stderr)
        print(f"{exc.error_code}: {exc.message}", file=sys.stderr)
        raise SystemExit(exc.exit_code)
    except Exception as exc:
        error_payload = build_error_output("UNHANDLED_ERROR", str(exc), request_payload_for_error)
        try:
            write_json_atomic(output_path, error_payload)
        except Exception as write_exc:
            print(f"Failed to write error output to {output_path}: {write_exc}", file=sys.stderr)
        print(f"UNHANDLED_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(99)


if __name__ == "__main__":
    main()
