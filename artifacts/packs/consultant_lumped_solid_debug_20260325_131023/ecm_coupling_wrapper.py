#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecm_backend import (
    BaseECMBackend,
    ECMBackendError,
    ECMState,
    MockECMBackend,
    MockECMConfig,
    VendorCLIBackend,
)


INPUT_MAGIC = "ECM_COUPLING_INPUT"
OUTPUT_MAGIC = "ECM_COUPLING_OUTPUT"
STATE_MAGIC = "ECM_WRAPPER_STATE"
FORMAT_VERSION = 1


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
    if version_i != FORMAT_VERSION:
        raise WrapperError(
            "STATE_VALIDATION_ERROR",
            f"Unsupported state file version {version_i}. Expected {FORMAT_VERSION}.",
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

    return PersistedState(last_step_id=last_step_id, last_time_s=last_time_s, state=state)


def build_state_payload(persisted: PersistedState) -> dict[str, Any]:
    return {
        "magic": STATE_MAGIC,
        "version": FORMAT_VERSION,
        "last_step_id": int(persisted.last_step_id),
        "last_time_s": float(persisted.last_time_s),
        "state": persisted.state.to_dict(),
    }


def initial_state_from_request_or_args(args: argparse.Namespace, request: StepRequest) -> ECMState:
    if request.init_state is not None:
        return request.init_state

    state = ECMState(
        q_ah=float(args.init_q_ah),
        v_rc=[float(args.init_v_rc[0]), float(args.init_v_rc[1])],
        hysteresis=float(args.init_hysteresis),
    )
    try:
        state.validate()
    except ECMBackendError as exc:
        raise WrapperError("CONFIG_ERROR", f"Invalid initial state from CLI arguments: {exc}", 10) from exc
    return state


def validate_request_against_state(request: StepRequest, persisted: PersistedState | None) -> None:
    if persisted is None:
        return

    if request.step_id <= persisted.last_step_id:
        raise WrapperError(
            "STATE_PROGRESS_ERROR",
            f"Incoming step_id={request.step_id} is not greater than last_step_id={persisted.last_step_id}.",
            3,
        )

    if request.time_s <= persisted.last_time_s:
        raise WrapperError(
            "STATE_PROGRESS_ERROR",
            f"Incoming time_s={request.time_s} is not greater than last_time_s={persisted.last_time_s}.",
            3,
        )

    expected_dt = request.time_s - persisted.last_time_s
    if not math.isclose(expected_dt, request.dt_s, rel_tol=0.0, abs_tol=1.0e-12):
        raise WrapperError(
            "STATE_PROGRESS_ERROR",
            f"Incoming dt_s={request.dt_s} does not match time increment "
            f"time_s-last_time_s={expected_dt}.",
            3,
        )


def build_backend(args: argparse.Namespace) -> BaseECMBackend:
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
            raise WrapperError("CONFIG_ERROR", f"Invalid mock backend configuration: {exc}", 10) from exc
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
        choices=["mock-inproc", "vendor-cli"],
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

    parser.add_argument("--temp-min-degc", type=float, default=-60.0, help="Lower bound for input T_jellyroll_degC.")
    parser.add_argument("--temp-max-degc", type=float, default=150.0, help="Upper bound for input T_jellyroll_degC.")
    parser.add_argument("--vt-min-v", type=float, default=0.0, help="Lower bound for output V_T_V.")
    parser.add_argument("--vt-max-v", type=float, default=10.0, help="Upper bound for output V_T_V.")
    parser.add_argument("--qgen-min-w", type=float, default=None, help="Optional lower bound for output Q_GEN_W.")
    parser.add_argument("--qgen-max-w", type=float, default=None, help="Optional upper bound for output Q_GEN_W.")

    parser.add_argument("--capacity-ah", type=float, default=5.0, help="Mock backend configuration.")
    parser.add_argument("--ocv-min-v", type=float, default=3.0, help="Mock backend configuration.")
    parser.add_argument("--ocv-max-v", type=float, default=4.2, help="Mock backend configuration.")
    parser.add_argument("--r0-ohm", type=float, default=0.012, help="Mock backend configuration.")
    parser.add_argument("--r1-ohm", type=float, default=0.004, help="Mock backend configuration.")
    parser.add_argument("--r2-ohm", type=float, default=0.002, help="Mock backend configuration.")
    parser.add_argument("--tau1-s", type=float, default=8.0, help="Mock backend configuration.")
    parser.add_argument("--tau2-s", type=float, default=40.0, help="Mock backend configuration.")
    parser.add_argument("--hyst-mag-v", type=float, default=0.015, help="Mock backend configuration.")

    parser.add_argument("--verbose", action="store_true", help="Print a short success line to stdout.")
    return parser.parse_args()


def run(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    state_path = Path(args.state)

    request_payload = read_json(input_path)
    request = parse_request(request_payload)
    validate_runtime_bounds(args, request)

    backend = build_backend(args)

    persisted = None if request.reset_state else parse_persisted_state(state_path)
    if not request.reset_state:
        validate_request_against_state(request, persisted)

    state_in = initial_state_from_request_or_args(args, request) if request.reset_state or persisted is None else persisted.state

    try:
        result = backend.step(
            dt_s=request.dt_s,
            current_a=request.current_a,
            t_cell_degc=request.t_jellyroll_degc,
            state=state_in,
        )
    except ECMBackendError as exc:
        raise WrapperError("BACKEND_ERROR", str(exc), 4) from exc
    except OSError as exc:
        raise WrapperError("BACKEND_ERROR", f"Backend OS error: {exc}", 4) from exc

    validate_result(args, result.q_gen_w, result.v_t_v, result.state_next)

    success_output = build_success_output(
        request=request,
        q_gen_w=result.q_gen_w,
        v_t_v=result.v_t_v,
        state_next=result.state_next,
        diagnostics=result.diagnostics,
    )

    next_persisted = PersistedState(
        last_step_id=request.step_id,
        last_time_s=request.time_s,
        state=result.state_next,
    )

    write_json_atomic(output_path, success_output)
    write_json_atomic(state_path, build_state_payload(next_persisted))

    if args.verbose:
        vt_text = "None" if result.v_t_v is None else f"{result.v_t_v:.8f}"
        print(
            f"step_id={request.step_id} "
            f"time_s={request.time_s:.12g} "
            f"dt_s={request.dt_s:.12g} "
            f"T_jellyroll_degC={request.t_jellyroll_degc:.8f} "
            f"current_a={request.current_a:.8f} "
            f"Q_GEN_W={result.q_gen_w:.8f} "
            f"V_T_V={vt_text}"
        )

    return 0


def main() -> None:
    args = parse_args()
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
