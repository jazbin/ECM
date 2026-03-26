"""
DUMMY ecm_step module.

This file has the exact signature expected by EcmStepBackend and the
OpenFOAM coupling wrapper.  Replace this file, params.csv, and
cellprops.csv with the real implementations — no other code changes
are needed.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def build_step_cache(params_df: pd.DataFrame) -> dict:
    """
    Build interpolation arrays from params_df once at startup.

    Expected params_df columns:
        SOC, OCV_V, R0_Ohm, R1_Ohm, R2_Ohm, tau1_s, tau2_s, gamma_hyst_V
    """
    return {
        "soc":         params_df["SOC"].to_numpy(dtype=float),
        "ocv_v":       params_df["OCV_V"].to_numpy(dtype=float),
        "r0_ohm":      params_df["R0_Ohm"].to_numpy(dtype=float),
        "r1_ohm":      params_df["R1_Ohm"].to_numpy(dtype=float),
        "r2_ohm":      params_df["R2_Ohm"].to_numpy(dtype=float),
        "tau1_s":      params_df["tau1_s"].to_numpy(dtype=float),
        "tau2_s":      params_df["tau2_s"].to_numpy(dtype=float),
        "gamma_hyst_v": params_df["gamma_hyst_V"].to_numpy(dtype=float),
    }


def ecm_step(
    *,
    dt_s: float,
    current_a: float,
    q_ah: float,
    v_rc: np.ndarray,
    hysteresis: float,
    T_cell_degC: float,
    params_df: pd.DataFrame,
    cellprops_df: pd.DataFrame,
    lookup_cache: dict,
) -> tuple:
    """
    Advance the ECM by one timestep.

    Parameters
    ----------
    dt_s         : timestep [s]
    current_a    : applied current [A]  (positive = discharge)
    q_ah         : charge removed so far [Ah]
    v_rc         : RC branch voltages, shape (2,) [V]
    hysteresis   : hysteresis state [-1..1]
    T_cell_degC  : cell temperature [°C]
    params_df    : parameter table (unused directly; lookup_cache used instead)
    cellprops_df : cell-level properties (capacity_Ah, T_ref_degC)
    lookup_cache : dict built by build_step_cache(params_df)

    Returns
    -------
    state_next : dict  — keys "V_RC" (list[float, float]), "H" (float)
    q_ah_next  : float
    outputs    : dict  — keys "Q_GEN" (W), "V_T" (V)
    """
    capacity_ah = float(cellprops_df["capacity_Ah"].iloc[0])
    t_ref_degc  = float(cellprops_df["T_ref_degC"].iloc[0])
    temp_shift  = float(T_cell_degC) - t_ref_degc

    # Coulomb counting
    q_ah_next = float(q_ah) - float(current_a) * float(dt_s) / 3600.0
    q_ah_next = max(0.0, min(q_ah_next, capacity_ah))
    soc = q_ah_next / capacity_ah

    # Interpolate SOC-dependent parameters
    cache = lookup_cache
    ocv_v = float(np.interp(soc, cache["soc"], cache["ocv_v"]))
    r0    = float(np.interp(soc, cache["soc"], cache["r0_ohm"])) * math.exp(-0.018 * temp_shift)
    r1    = float(np.interp(soc, cache["soc"], cache["r1_ohm"])) * math.exp(-0.010 * temp_shift)
    r2    = float(np.interp(soc, cache["soc"], cache["r2_ohm"])) * math.exp(-0.006 * temp_shift)
    tau1  = float(np.interp(soc, cache["soc"], cache["tau1_s"]))
    tau2  = float(np.interp(soc, cache["soc"], cache["tau2_s"]))
    gamma = float(np.interp(soc, cache["soc"], cache["gamma_hyst_v"]))

    r0 = max(1.0e-6, r0)
    r1 = max(1.0e-6, r1)
    r2 = max(1.0e-6, r2)

    # RC branch update (discrete-time exact)
    v_rc = np.asarray(v_rc, dtype=float)
    a1 = math.exp(-float(dt_s) / tau1)
    a2 = math.exp(-float(dt_s) / tau2)
    v_rc1_next = a1 * float(v_rc[0]) + (1.0 - a1) * r1 * float(current_a)
    v_rc2_next = a2 * float(v_rc[1]) + (1.0 - a2) * r2 * float(current_a)

    # Hysteresis update
    if float(current_a) > 1.0e-15:
        h_target = 1.0
    elif float(current_a) < -1.0e-15:
        h_target = -1.0
    else:
        h_target = 0.0
    a_h = math.exp(-float(dt_s) / 100.0)
    h_next = a_h * float(hysteresis) + (1.0 - a_h) * h_target
    h_next = max(-1.0, min(h_next, 1.0))

    # Terminal voltage
    v_t = ocv_v - float(current_a) * r0 - v_rc1_next - v_rc2_next - gamma * h_next

    # Heat generation
    q_gen = (
        float(current_a) ** 2 * r0
        + abs(float(current_a)) * (abs(v_rc1_next) + abs(v_rc2_next))
        + abs(float(current_a)) * gamma * abs(h_next)
    )

    state_next = {"V_RC": [v_rc1_next, v_rc2_next], "H": h_next}
    outputs    = {"Q_GEN": q_gen, "V_T": v_t}

    return state_next, q_ah_next, outputs
