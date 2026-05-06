#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING


class ECMBackendError(RuntimeError):
    pass


def _is_finite_scalar(value: float) -> bool:
    return math.isfinite(float(value))


def _clamp(value: float, lo: float, hi: float) -> float:
    return float(min(max(float(value), float(lo)), float(hi)))


@dataclass
class ECMState:
    q_ah: float
    v_rc: list[float]
    hysteresis: float

    def validate(self) -> None:
        if not _is_finite_scalar(self.q_ah):
            raise ECMBackendError(f"Invalid q_ah: {self.q_ah}")
        if not isinstance(self.v_rc, list) or len(self.v_rc) != 2:
            raise ECMBackendError(f"Expected v_rc to be a list of length 2, got: {self.v_rc}")
        if not all(_is_finite_scalar(x) for x in self.v_rc):
            raise ECMBackendError(f"Invalid v_rc entries: {self.v_rc}")
        if not _is_finite_scalar(self.hysteresis):
            raise ECMBackendError(f"Invalid hysteresis: {self.hysteresis}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "q_ah": float(self.q_ah),
            "v_rc": [float(self.v_rc[0]), float(self.v_rc[1])],
            "hysteresis": float(self.hysteresis),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ECMState":
        if not isinstance(payload, dict):
            raise ECMBackendError(f"State payload must be a dict, got: {type(payload).__name__}")
        state = cls(
            q_ah=float(payload["q_ah"]),
            v_rc=[float(x) for x in payload["v_rc"]],
            hysteresis=float(payload["hysteresis"]),
        )
        state.validate()
        return state


@dataclass
class ECMStepResult:
    state_next: ECMState
    q_gen_w: float
    v_t_v: float | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.state_next.validate()
        if not _is_finite_scalar(self.q_gen_w):
            raise ECMBackendError(f"Invalid q_gen_w: {self.q_gen_w}")
        if self.v_t_v is not None and not _is_finite_scalar(self.v_t_v):
            raise ECMBackendError(f"Invalid v_t_v: {self.v_t_v}")
        if not isinstance(self.diagnostics, dict):
            raise ECMBackendError("diagnostics must be a dict")

    def to_vendor_response(self) -> dict[str, Any]:
        self.validate()
        payload = {
            "magic": "ECM_STEP_OUTPUT",
            "version": 1,
            "status": "ok",
            "state_next": self.state_next.to_dict(),
            "Q_GEN_W": float(self.q_gen_w),
            "diagnostics": self.diagnostics,
        }
        if self.v_t_v is not None:
            payload["V_T_V"] = float(self.v_t_v)
        return payload


class BaseECMBackend(ABC):
    @abstractmethod
    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        t_cell_degc: float,
        state: ECMState,
    ) -> ECMStepResult:
        raise NotImplementedError


@dataclass
class MockECMConfig:
    capacity_ah: float = 5.0
    ocv_min_v: float = 3.0
    ocv_max_v: float = 4.2
    r0_ohm: float = 0.012
    r1_ohm: float = 0.004
    r2_ohm: float = 0.002
    tau1_s: float = 8.0
    tau2_s: float = 40.0
    hyst_mag_v: float = 0.015

    def validate(self) -> None:
        if self.capacity_ah <= 0.0:
            raise ECMBackendError("capacity_ah must be > 0")
        if self.tau1_s <= 0.0 or self.tau2_s <= 0.0:
            raise ECMBackendError("tau1_s and tau2_s must be > 0")
        if self.ocv_max_v <= self.ocv_min_v:
            raise ECMBackendError("ocv_max_v must be > ocv_min_v")
        if self.r0_ohm <= 0.0 or self.r1_ohm <= 0.0 or self.r2_ohm <= 0.0:
            raise ECMBackendError("All resistances must be > 0")
        if self.hyst_mag_v < 0.0:
            raise ECMBackendError("hyst_mag_v must be >= 0")


class MockECMBackend(BaseECMBackend):
    def __init__(self, config: MockECMConfig | None = None) -> None:
        self.config = config if config is not None else MockECMConfig()
        self.config.validate()

    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        t_cell_degc: float,
        state: ECMState,
    ) -> ECMStepResult:
        if dt_s <= 0.0:
            raise ECMBackendError("dt_s must be > 0")

        state.validate()
        current_a = float(current_a)
        t_cell_degc = float(t_cell_degc)

        if not _is_finite_scalar(current_a):
            raise ECMBackendError(f"Invalid current_a: {current_a}")
        if not _is_finite_scalar(t_cell_degc):
            raise ECMBackendError(f"Invalid t_cell_degc: {t_cell_degc}")

        cfg = self.config

        q_ah_next = state.q_ah - current_a * dt_s / 3600.0
        q_ah_next = _clamp(q_ah_next, 0.0, cfg.capacity_ah)

        soc = _clamp(q_ah_next / cfg.capacity_ah, 0.0, 1.0)
        temp_shift = t_cell_degc - 25.0

        ocv_span = cfg.ocv_max_v - cfg.ocv_min_v
        ocv_v = (
            cfg.ocv_min_v
            + ocv_span * (0.08 + 0.92 * soc)
            + 0.015 * math.tanh((soc - 0.5) / 0.18)
            + 0.0006 * temp_shift
        )

        r0_ohm = max(1.0e-6, cfg.r0_ohm * math.exp(-0.018 * temp_shift))
        r1_ohm = max(1.0e-6, cfg.r1_ohm * math.exp(-0.010 * temp_shift))
        r2_ohm = max(1.0e-6, cfg.r2_ohm * math.exp(-0.006 * temp_shift))

        a1 = math.exp(-dt_s / cfg.tau1_s)
        a2 = math.exp(-dt_s / cfg.tau2_s)

        v_rc1_next = a1 * state.v_rc[0] + (1.0 - a1) * r1_ohm * current_a
        v_rc2_next = a2 * state.v_rc[1] + (1.0 - a2) * r2_ohm * current_a

        if current_a > 1.0e-15:
            h_target = 1.0
        elif current_a < -1.0e-15:
            h_target = -1.0
        else:
            h_target = 0.0

        a_h = math.exp(-dt_s / 100.0)
        hysteresis_next = a_h * state.hysteresis + (1.0 - a_h) * h_target
        hysteresis_next = _clamp(hysteresis_next, -1.0, 1.0)

        v_t_v = ocv_v - current_a * r0_ohm - v_rc1_next - v_rc2_next - cfg.hyst_mag_v * hysteresis_next

        q_ohmic_w = (current_a * current_a) * r0_ohm
        q_rc_w = abs(current_a) * (abs(v_rc1_next) + abs(v_rc2_next))
        q_hyst_w = abs(current_a) * cfg.hyst_mag_v * abs(hysteresis_next)
        q_temp_w = 0.002 * abs(current_a) * abs(temp_shift) / 25.0
        q_gen_w = q_ohmic_w + q_rc_w + q_hyst_w + q_temp_w

        result = ECMStepResult(
            state_next=ECMState(
                q_ah=float(q_ah_next),
                v_rc=[float(v_rc1_next), float(v_rc2_next)],
                hysteresis=float(hysteresis_next),
            ),
            q_gen_w=float(q_gen_w),
            v_t_v=float(v_t_v),
            diagnostics={
                "SOC": float(soc),
                "OCV_V": float(ocv_v),
                "R0_OHM": float(r0_ohm),
                "R1_OHM": float(r1_ohm),
                "R2_OHM": float(r2_ohm),
            },
        )
        result.validate()
        return result


class VendorCLIBackend(BaseECMBackend):  # noqa: E302
    """
    Stateless bridge to an external executable.

    Expected executable contract:

      vendor_binary --input request.json --output response.json

    Request JSON:
    {
      "magic": "ECM_STEP_INPUT",
      "version": 1,
      "dt_s": ...,
      "current_a": ...,
      "T_cell_degC": ...,
      "state": {
        "q_ah": ...,
        "v_rc": [v1, v2],
        "hysteresis": ...
      }
    }

    Response JSON:
    {
      "magic": "ECM_STEP_OUTPUT",
      "version": 1,
      "status": "ok",
      "state_next": {
        "q_ah": ...,
        "v_rc": [v1, v2],
        "hysteresis": ...
      },
      "Q_GEN_W": ...,
      "V_T_V": ...,
      "diagnostics": {...}
    }
    """

    def __init__(
        self,
        *,
        executable: str,
        timeout_s: float = 30.0,
        working_dir: str | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        if not executable:
            raise ECMBackendError("VendorCLIBackend requires a non-empty executable path")
        self.executable = str(executable)
        self.timeout_s = float(timeout_s)
        self.working_dir = str(working_dir) if working_dir else None
        self.env_overrides = dict(env_overrides) if env_overrides else {}

    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        t_cell_degc: float,
        state: ECMState,
    ) -> ECMStepResult:
        state.validate()

        request_payload = {
            "magic": "ECM_STEP_INPUT",
            "version": 1,
            "dt_s": float(dt_s),
            "current_a": float(current_a),
            "T_cell_degC": float(t_cell_degc),
            "state": state.to_dict(),
        }

        run_env = os.environ.copy()
        run_env.update(self.env_overrides)

        with tempfile.TemporaryDirectory(prefix="ecm_vendor_call_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            input_path = tmpdir_path / "request.json"
            output_path = tmpdir_path / "response.json"

            with open(input_path, "w", encoding="utf-8") as f:
                json.dump(request_payload, f, indent=2)

            completed = subprocess.run(
                [self.executable, "--input", str(input_path), "--output", str(output_path)],
                cwd=self.working_dir,
                env=run_env,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )

            if completed.returncode != 0:
                raise ECMBackendError(
                    "Vendor executable failed.\n"
                    f"Executable: {self.executable}\n"
                    f"Return code: {completed.returncode}\n"
                    f"STDOUT:\n{completed.stdout}\n"
                    f"STDERR:\n{completed.stderr}"
                )

            if not output_path.exists():
                raise ECMBackendError(
                    f"Vendor executable did not produce expected output file: {output_path}"
                )

            with open(output_path, "r", encoding="utf-8") as f:
                response_payload = json.load(f)

        return self._parse_response(response_payload)

    @staticmethod
    def _parse_response(payload: dict[str, Any]) -> ECMStepResult:  # noqa: E301
        if not isinstance(payload, dict):
            raise ECMBackendError("Vendor response must be a JSON object")
        if payload.get("magic") != "ECM_STEP_OUTPUT":
            raise ECMBackendError(f"Unexpected vendor response magic: {payload.get('magic')}")
        if int(payload.get("version", -1)) != 1:
            raise ECMBackendError(f"Unexpected vendor response version: {payload.get('version')}")
        if payload.get("status") != "ok":
            raise ECMBackendError(
                f"Vendor response returned status={payload.get('status')} "
                f"message={payload.get('message')}"
            )

        state_next = ECMState.from_dict(payload["state_next"])
        q_gen_w = float(payload["Q_GEN_W"])
        v_t_v = None if "V_T_V" not in payload else float(payload["V_T_V"])
        diagnostics = payload.get("diagnostics", {})

        result = ECMStepResult(
            state_next=state_next,
            q_gen_w=q_gen_w,
            v_t_v=v_t_v,
            diagnostics=diagnostics,
        )
        result.validate()
        return result


class PersistentSocketBackend(BaseECMBackend):
    """
    Send ECM step requests to a running ecm_daemon.py over a Unix domain socket.

    Eliminates per-call process spawn + module import overhead (~45 ms/call).
    The daemon loads all modules once at startup; each call costs only the IPC
    round-trip (~1-3 ms) plus the ECM computation itself (~2 ms).
    """

    def __init__(self, socket_path: str, timeout_s: float = 5.0) -> None:
        self.socket_path = str(socket_path)
        self.timeout_s = float(timeout_s)

    def ping(self) -> bool:
        """Return True if the daemon is alive and responding."""
        try:
            resp = self._call(json.dumps({"ping": True}))
            return json.loads(resp).get("pong") is True
        except Exception:  # noqa: BLE001
            return False

    def _call(self, request_line: str) -> str:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout_s)
        try:
            sock.connect(self.socket_path)
            sock.sendall((request_line + "\n").encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ECMBackendError("Daemon closed connection without response")
                buf += chunk
            return buf.split(b"\n", 1)[0].decode("utf-8")
        finally:
            sock.close()

    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        t_cell_degc: float,
        state: ECMState,
    ) -> ECMStepResult:
        state.validate()
        req = json.dumps({
            "dt_s":        float(dt_s),
            "current_a":   float(current_a),
            "t_cell_degc": float(t_cell_degc),
            "state":       state.to_dict(),
        })
        try:
            raw = self._call(req)
        except ECMBackendError:
            raise
        except Exception as exc:
            raise ECMBackendError(f"Socket error communicating with ECM daemon: {exc}") from exc

        try:
            resp = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ECMBackendError(f"Invalid JSON from ECM daemon: {exc}") from exc

        if resp.get("status") != "ok":
            raise ECMBackendError(f"ECM daemon error: {resp.get('message', resp)}")

        state_next = ECMState.from_dict(resp["state_next"])
        q_gen_w    = float(resp["q_gen_w"])
        v_t_v      = float(resp["v_t_v"]) if "v_t_v" in resp else None
        diagnostics = resp.get("diagnostics", {})

        result = ECMStepResult(
            state_next=state_next,
            q_gen_w=q_gen_w,
            v_t_v=v_t_v,
            diagnostics=diagnostics,
        )
        result.validate()
        return result


class EcmStepBackend(BaseECMBackend):
    """
    Backend that delegates each CFD timestep to ecm_step() loaded from a
    Python module (default: ecm_step.py co-located with this file).

    Swap ecm_step.py, params.csv, and cellprops.csv for the real
    implementations — no other code changes are needed.

    Expected module exports
    -----------------------
    build_step_cache(params_df) -> lookup_cache
    ecm_step(*, dt_s, current_a, q_ah, v_rc, hysteresis, T_cell_degC,
             params_df, cellprops_df, lookup_cache) -> (state_next, q_ah_next, outputs)

    state_next keys : "V_RC" (2-element list/array), "H" (float)
    outputs keys    : "Q_GEN" (float, W, required), "V_T" (float, V, optional)
    """

    def __init__(
        self,
        *,
        params_path: str,
        cellprops_path: str,
        ecm_step_module_path: str | None = None,
    ) -> None:
        import importlib.util
        import pandas as pd

        if ecm_step_module_path is None:
            module_path = Path(__file__).resolve().parent / "ecm_step.py"
        else:
            module_path = Path(ecm_step_module_path).resolve()

        if not module_path.exists():
            raise ECMBackendError(f"ecm_step module not found: {module_path}")

        spec = importlib.util.spec_from_file_location("ecm_step", module_path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise ECMBackendError(
                f"Failed to load ecm_step module from {module_path}: {exc}"
            ) from exc

        for name in ("ecm_step", "build_step_cache"):
            if not hasattr(module, name):
                raise ECMBackendError(
                    f"Module {module_path} does not export '{name}'"
                )

        try:
            params_df = pd.read_csv(params_path)
        except Exception as exc:
            raise ECMBackendError(
                f"Failed to load params from {params_path}: {exc}"
            ) from exc

        try:
            cellprops_df = pd.read_csv(cellprops_path)
        except Exception as exc:
            raise ECMBackendError(
                f"Failed to load cellprops from {cellprops_path}: {exc}"
            ) from exc

        try:
            lookup_cache = module.build_step_cache(params_df)
        except Exception as exc:
            raise ECMBackendError(f"build_step_cache failed: {exc}") from exc

        self._ecm_step_fn = module.ecm_step
        self._params_df = params_df
        self._cellprops_df = cellprops_df
        self._lookup_cache = lookup_cache

    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        t_cell_degc: float,
        state: ECMState,
    ) -> ECMStepResult:
        import numpy as np

        state.validate()

        try:
            state_next_raw, q_ah_next, outputs = self._ecm_step_fn(
                dt_s=float(dt_s),
                current_a=float(current_a),
                q_ah=state.q_ah,
                v_rc=np.array(state.v_rc, dtype=float),
                hysteresis=state.hysteresis,
                T_cell_degC=float(t_cell_degc),
                params_df=self._params_df,
                cellprops_df=self._cellprops_df,
                lookup_cache=self._lookup_cache,
            )
        except ECMBackendError:
            raise
        except Exception as exc:
            raise ECMBackendError(f"ecm_step raised an error: {exc}") from exc

        try:
            v_rc_out = list(state_next_raw["V_RC"])
            if len(v_rc_out) != 2:
                raise ECMBackendError(
                    f"V_RC must have 2 elements, got {len(v_rc_out)}"
                )
            h_out = float(state_next_raw["H"])
            q_gen_w = float(outputs["Q_GEN"])
        except (KeyError, TypeError) as exc:
            raise ECMBackendError(
                f"Invalid ecm_step output structure: {exc}"
            ) from exc

        v_t_v = float(outputs["V_T"]) if "V_T" in outputs else None

        result = ECMStepResult(
            state_next=ECMState(
                q_ah=float(q_ah_next),
                v_rc=[float(v_rc_out[0]), float(v_rc_out[1])],
                hysteresis=h_out,
            ),
            q_gen_w=q_gen_w,
            v_t_v=v_t_v,
            diagnostics={},
        )
        result.validate()
        return result
