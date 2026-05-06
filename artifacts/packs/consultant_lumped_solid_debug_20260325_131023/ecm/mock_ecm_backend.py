#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ECMResponse:
    state_next: Dict[str, Any]
    q_ah_next: float
    outputs: Dict[str, Any]


class BaseECMBackend(ABC):
    @abstractmethod
    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        q_ah: float,
        v_rc: np.ndarray,
        hysteresis: float,
        T_cell_degC: float,
    ) -> ECMResponse:
        raise NotImplementedError


def build_step_cache(params_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Lightweight cache builder kept for compatibility with the original wrapper.
    The mock backend can use these values when available, but it also works with
    completely empty dataframes.
    """
    cache: Dict[str, Any] = {}

    if params_df is None or params_df.empty:
        return cache

    lower_cols = {str(c).strip().lower(): c for c in params_df.columns}

    def get_scalar_from_table(candidates: list[str], default: Optional[float]) -> Optional[float]:
        for name in candidates:
            if name in lower_cols:
                raw = params_df[lower_cols[name]].dropna()
                if len(raw) > 0:
                    try:
                        return float(raw.iloc[0])
                    except (TypeError, ValueError):
                        pass
        return default

    cache["capacity_ah"] = get_scalar_from_table(
        ["capacity_ah", "nominal_capacity_ah", "cell_capacity_ah"],
        None,
    )
    cache["ocv_min_v"] = get_scalar_from_table(["ocv_min_v", "vmin_ocv", "ocv0_v"], None)
    cache["ocv_max_v"] = get_scalar_from_table(["ocv_max_v", "vmax_ocv"], None)
    cache["r0_ohm"] = get_scalar_from_table(["r0_ohm", "r_ohm", "resistance_ohm"], None)
    cache["r1_ohm"] = get_scalar_from_table(["r1_ohm"], None)
    cache["r2_ohm"] = get_scalar_from_table(["r2_ohm"], None)
    cache["tau1_s"] = get_scalar_from_table(["tau1_s", "rc1_tau_s"], None)
    cache["tau2_s"] = get_scalar_from_table(["tau2_s", "rc2_tau_s"], None)
    cache["hyst_mag_v"] = get_scalar_from_table(["hyst_mag_v", "mh_v", "m_h_v"], None)

    return cache


class MockECMBackend(BaseECMBackend):
    """
    Simple, stable, NDA-safe ECM stand-in.

    It preserves the important contract:
      - inputs: dt_s, current_a, q_ah, v_rc[2], hysteresis, T_cell_degC
      - outputs: state_next["V_RC"], state_next["H"], q_ah_next,
                 outputs["Q_GEN"], outputs["V_T"]

    Positive current is treated as discharge.
    """

    def __init__(
        self,
        *,
        params_df: Optional[pd.DataFrame] = None,
        cellprops_df: Optional[pd.DataFrame] = None,
        lookup_cache: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.params_df = params_df if params_df is not None else pd.DataFrame()
        self.cellprops_df = cellprops_df if cellprops_df is not None else pd.DataFrame()
        self.lookup_cache = lookup_cache if lookup_cache is not None else {}

        self.capacity_ah = self._pick_scalar(
            self.lookup_cache.get("capacity_ah"),
            self._from_cellprops(["capacity_ah", "nominal_capacity_ah", "cell_capacity_ah"]),
            5.0,
        )
        self.ocv_min_v = self._pick_scalar(
            self.lookup_cache.get("ocv_min_v"),
            self._from_cellprops(["ocv_min_v", "voltage_min_v"]),
            3.00,
        )
        self.ocv_max_v = self._pick_scalar(
            self.lookup_cache.get("ocv_max_v"),
            self._from_cellprops(["ocv_max_v", "voltage_max_v"]),
            4.20,
        )
        self.r0_ref_ohm = self._pick_scalar(
            self.lookup_cache.get("r0_ohm"),
            self._from_cellprops(["r0_ohm", "resistance_ohm"]),
            0.012,
        )
        self.r1_ref_ohm = self._pick_scalar(self.lookup_cache.get("r1_ohm"), None, 0.0040)
        self.r2_ref_ohm = self._pick_scalar(self.lookup_cache.get("r2_ohm"), None, 0.0020)
        self.tau1_s = self._pick_scalar(self.lookup_cache.get("tau1_s"), None, 8.0)
        self.tau2_s = self._pick_scalar(self.lookup_cache.get("tau2_s"), None, 40.0)
        self.hyst_mag_v = self._pick_scalar(self.lookup_cache.get("hyst_mag_v"), None, 0.015)

        if self.capacity_ah <= 0.0:
            raise ValueError("MockECMBackend capacity must be > 0.")
        if self.tau1_s <= 0.0 or self.tau2_s <= 0.0:
            raise ValueError("MockECMBackend tau constants must be > 0.")

    @staticmethod
    def _pick_scalar(*values: Optional[float]) -> float:
        for value in values:
            if value is None:
                continue
            value_f = float(value)
            if np.isfinite(value_f):
                return value_f
        raise ValueError("No valid scalar value available.")

    def _from_cellprops(self, candidates: list[str]) -> Optional[float]:
        if self.cellprops_df is None or self.cellprops_df.empty:
            return None

        lower_cols = {str(c).strip().lower(): c for c in self.cellprops_df.columns}
        for name in candidates:
            key = name.lower()
            if key in lower_cols:
                raw = self.cellprops_df[lower_cols[key]].dropna()
                if len(raw) > 0:
                    try:
                        return float(raw.iloc[0])
                    except (TypeError, ValueError):
                        pass
        return None

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return float(min(max(value, lo, hi) if False else max(value, lo), hi))

    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        q_ah: float,
        v_rc: np.ndarray,
        hysteresis: float,
        T_cell_degC: float,
    ) -> ECMResponse:
        if dt_s <= 0.0:
            raise ValueError("dt_s must be > 0.")
        v_rc_arr = np.array(v_rc, dtype=float).reshape(-1)
        if v_rc_arr.shape != (2,):
            raise ValueError(f"Expected v_rc shape (2,), got {v_rc_arr.shape}.")

        current_a = float(current_a)
        q_ah = float(q_ah)
        hysteresis = float(hysteresis)
        T_cell_degC = float(T_cell_degC)

        q_ah_next = q_ah - current_a * dt_s / 3600.0
        q_ah_next = self._clamp(q_ah_next, 0.0, self.capacity_ah)

        soc = q_ah_next / self.capacity_ah
        soc = self._clamp(soc, 0.0, 1.0)

        temp_shift = T_cell_degC - 25.0
        ocv_span = self.ocv_max_v - self.ocv_min_v
        ocv_v = (
            self.ocv_min_v
            + ocv_span * (0.08 + 0.92 * soc)
            + 0.015 * math.tanh((soc - 0.5) / 0.18)
            + 0.0006 * temp_shift
        )

        temp_factor = math.exp(-0.018 * temp_shift)
        r0_ohm = max(1.0e-5, self.r0_ref_ohm * temp_factor)
        r1_ohm = max(1.0e-5, self.r1_ref_ohm * math.exp(-0.010 * temp_shift))
        r2_ohm = max(1.0e-5, self.r2_ref_ohm * math.exp(-0.006 * temp_shift))

        a1 = math.exp(-dt_s / self.tau1_s)
        a2 = math.exp(-dt_s / self.tau2_s)
        v_rc_1 = a1 * v_rc_arr[0] + (1.0 - a1) * r1_ohm * current_a
        v_rc_2 = a2 * v_rc_arr[1] + (1.0 - a2) * r2_ohm * current_a

        if abs(current_a) > 1.0e-12:
            h_target = 1.0 if current_a > 0.0 else -1.0
        else:
            h_target = 0.0

        a_h = math.exp(-dt_s / 100.0)
        hysteresis_next = a_h * hysteresis + (1.0 - a_h) * h_target
        hysteresis_next = self._clamp(hysteresis_next, -1.0, 1.0)

        vt_v = ocv_v - current_a * r0_ohm - v_rc_1 - v_rc_2 - self.hyst_mag_v * hysteresis_next

        q_ohmic_w = (current_a ** 2) * r0_ohm
        q_rc_w = abs(current_a) * (abs(v_rc_1) + abs(v_rc_2))
        q_hyst_w = abs(current_a) * self.hyst_mag_v * abs(hysteresis_next)
        q_temp_w = 0.002 * abs(current_a) * abs(temp_shift) / 25.0
        q_gen_w = q_ohmic_w + q_rc_w + q_hyst_w + q_temp_w

        outputs = {
            "Q_GEN": float(q_gen_w),
            "V_T": float(vt_v),
            "SOC": float(soc),
            "OCV": float(ocv_v),
            "R0_OHM": float(r0_ohm),
        }
        state_next = {
            "V_RC": [float(v_rc_1), float(v_rc_2)],
            "H": float(hysteresis_next),
        }
        return ECMResponse(state_next=state_next, q_ah_next=float(q_ah_next), outputs=outputs)


class VendorCLIBackend(BaseECMBackend):
    """
    Thin bridge to an external executable that the wrapper can call without
    importing vendor source into the workspace.

    Expected executable contract:
      python vendor_ecm_cli.py --input request.json --output response.json

    Request JSON:
    {
      "magic": "ECM_STEP_INPUT",
      "version": 1,
      "dt_s": ...,
      "current_a": ...,
      "q_ah": ...,
      "v_rc": [v1, v2],
      "hysteresis": ...,
      "T_cell_degC": ...
    }

    Response JSON:
    {
      "magic": "ECM_STEP_OUTPUT",
      "version": 1,
      "status": "ok",
      "state_next": {"V_RC": [...], "H": ...},
      "q_ah": ...,
      "outputs": {"Q_GEN": ..., "V_T": ...}
    }
    """

    def __init__(
        self,
        *,
        executable: str,
        working_dir: Optional[str] = None,
        timeout_s: float = 30.0,
        state_file: Optional[str] = None,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> None:
        if not executable:
            raise ValueError("VendorCLIBackend requires a non-empty executable path.")
        self.executable = str(executable)
        self.working_dir = str(working_dir) if working_dir else None
        self.timeout_s = float(timeout_s)
        self.state_file = str(state_file) if state_file else None
        self.env_overrides = dict(env_overrides) if env_overrides else {}

    def step(
        self,
        *,
        dt_s: float,
        current_a: float,
        q_ah: float,
        v_rc: np.ndarray,
        hysteresis: float,
        T_cell_degC: float,
    ) -> ECMResponse:
        request = {
            "magic": "ECM_STEP_INPUT",
            "version": 1,
            "dt_s": float(dt_s),
            "current_a": float(current_a),
            "q_ah": float(q_ah),
            "v_rc": [float(x) for x in np.array(v_rc, dtype=float).reshape(-1).tolist()],
            "hysteresis": float(hysteresis),
            "T_cell_degC": float(T_cell_degC),
        }

        run_env = os.environ.copy()
        run_env.update(self.env_overrides)

        with tempfile.TemporaryDirectory(prefix="vendor_ecm_call_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            input_path = tmpdir_path / "ecm_step_input.json"
            output_path = tmpdir_path / "ecm_step_output.json"

            with open(input_path, "w", encoding="utf-8") as f:
                json.dump(request, f, indent=2)

            cmd = [self.executable, "--input", str(input_path), "--output", str(output_path)]
            if self.state_file:
                cmd.extend(["--state", self.state_file])

            completed = subprocess.run(
                cmd,
                cwd=self.working_dir,
                env=run_env,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )

            if completed.returncode != 0:
                raise RuntimeError(
                    "Vendor CLI backend failed.\n"
                    f"Executable: {self.executable}\n"
                    f"Return code: {completed.returncode}\n"
                    f"STDOUT:\n{completed.stdout}\n"
                    f"STDERR:\n{completed.stderr}"
                )

            if not output_path.exists():
                raise RuntimeError(
                    f"Vendor CLI backend did not produce expected output file: {output_path}"
                )

            with open(output_path, "r", encoding="utf-8") as f:
                response = json.load(f)

        if response.get("magic") != "ECM_STEP_OUTPUT":
            raise RuntimeError(f"Unexpected vendor response magic: {response.get('magic')}")
        if int(response.get("version", -1)) != 1:
            raise RuntimeError(f"Unexpected vendor response version: {response.get('version')}")
        if response.get("status") != "ok":
            raise RuntimeError(
                f"Vendor CLI backend returned non-ok status: {response.get('status')} "
                f"message={response.get('message')}"
            )

        state_next = response.get("state_next")
        outputs = response.get("outputs")
        q_ah_next = response.get("q_ah")

        if not isinstance(state_next, dict):
            raise RuntimeError("Vendor response missing dict state_next.")
        if not isinstance(outputs, dict):
            raise RuntimeError("Vendor response missing dict outputs.")
        if q_ah_next is None:
            raise RuntimeError("Vendor response missing q_ah.")

        return ECMResponse(
            state_next=state_next,
            q_ah_next=float(q_ah_next),
            outputs=outputs,
        )


def get_backend(
    *,
    backend_name: str,
    params_df: Optional[pd.DataFrame] = None,
    cellprops_df: Optional[pd.DataFrame] = None,
    lookup_cache: Optional[Dict[str, Any]] = None,
    vendor_executable: Optional[str] = None,
    vendor_working_dir: Optional[str] = None,
    vendor_timeout_s: float = 30.0,
    vendor_state_file: Optional[str] = None,
    vendor_env_overrides: Optional[Dict[str, str]] = None,
) -> BaseECMBackend:
    name = str(backend_name).strip().lower()

    if name == "mock-inproc":
        return MockECMBackend(
            params_df=params_df,
            cellprops_df=cellprops_df,
            lookup_cache=lookup_cache,
        )

    if name == "vendor-cli":
        if not vendor_executable:
            raise ValueError("--vendor-exec is required for backend=vendor-cli.")
        return VendorCLIBackend(
            executable=vendor_executable,
            working_dir=vendor_working_dir,
            timeout_s=vendor_timeout_s,
            state_file=vendor_state_file,
            env_overrides=vendor_env_overrides,
        )

    raise ValueError(f"Unsupported backend_name: {backend_name}")
