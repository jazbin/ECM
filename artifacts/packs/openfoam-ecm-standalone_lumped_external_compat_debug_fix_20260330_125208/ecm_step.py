"""
DUMMY external-schema ecm_step module.

This file follows the external lookup-table contract expected by the
portable package:
  - params.csv columns: Q_Ah, T_degC, R0_Ohm, R_Ohm_1, R_Ohm_2, C_F_1, C_F_2
  - cellprops.csv columns: capacity_Ah, T_ref_degC

Replace this file, params.csv, and cellprops.csv with the real external
implementations. The wrapper/backend contract stays the same.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def build_step_cache(params_df: pd.DataFrame) -> dict:
    """
    Build interpolation arrays from params_df once at startup.

    Expected params_df columns:
        Q_Ah, T_degC, R0_Ohm, R_Ohm_1, R_Ohm_2, C_F_1, C_F_2
    """
    points = params_df[["Q_Ah", "T_degC"]].to_numpy(dtype=float)
    return {
        "points": points,
        "r0_ohm": params_df["R0_Ohm"].to_numpy(dtype=float),
        "r1_ohm": params_df["R_Ohm_1"].to_numpy(dtype=float),
        "r2_ohm": params_df["R_Ohm_2"].to_numpy(dtype=float),
        "c1_f": params_df["C_F_1"].to_numpy(dtype=float),
        "c2_f": params_df["C_F_2"].to_numpy(dtype=float),
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

    # Coulomb counting. Positive current means discharge.
    q_ah_next = float(q_ah) - float(current_a) * float(dt_s) / 3600.0
    q_ah_next = max(0.0, min(q_ah_next, capacity_ah))

    # Use the nearest available (Q_Ah, T_degC) row from the lookup table.
    cache = lookup_cache
    query = np.array([q_ah_next, float(T_cell_degC)], dtype=float)
    distances = np.sum((cache["points"] - query) ** 2, axis=1)
    idx = int(np.argmin(distances))

    r0 = float(cache["r0_ohm"][idx]) * math.exp(-0.020 * temp_shift)
    r1 = float(cache["r1_ohm"][idx]) * math.exp(-0.010 * temp_shift)
    r2 = float(cache["r2_ohm"][idx]) * math.exp(-0.008 * temp_shift)
    c1 = max(float(cache["c1_f"][idx]), 1.0e-9)
    c2 = max(float(cache["c2_f"][idx]), 1.0e-9)

    r0 = max(1.0e-6, r0)
    r1 = max(1.0e-6, r1)
    r2 = max(1.0e-6, r2)
    tau1 = max(r1 * c1, 1.0e-6)
    tau2 = max(r2 * c2, 1.0e-6)

    # RC branch update (discrete-time exact)
    v_rc = np.asarray(v_rc, dtype=float)
    a1 = math.exp(-float(dt_s) / tau1)
    a2 = math.exp(-float(dt_s) / tau2)
    v_rc1_next = a1 * float(v_rc[0]) + (1.0 - a1) * r1 * float(current_a)
    v_rc2_next = a2 * float(v_rc[1]) + (1.0 - a2) * r2 * float(current_a)

    # Keep the dummy hysteresis state simple. The real external module can
    # replace this with its own state law.
    if float(current_a) > 1.0e-15:
        h_target = 1.0
    elif float(current_a) < -1.0e-15:
        h_target = -1.0
    else:
        h_target = 0.0
    a_h = math.exp(-float(dt_s) / 5.0)
    h_next = a_h * float(hysteresis) + (1.0 - a_h) * h_target
    h_next = max(-1.0, min(h_next, 1.0))

    # Use a simple reference-voltage estimate for the dummy implementation.
    soc = q_ah_next / capacity_ah if capacity_ah > 0.0 else 0.0
    ocv_v = 3.0 + 1.2 * (1.0 - soc)
    v_t = ocv_v - float(current_a) * r0 - v_rc1_next - v_rc2_next - 0.002 * h_next

    # Heat generation
    q_gen = (
        float(current_a) ** 2 * r0
        + abs(float(current_a)) * (abs(v_rc1_next) + abs(v_rc2_next))
        + abs(float(current_a)) * 0.002 * abs(h_next)
    )

    state_next = {"V_RC": [v_rc1_next, v_rc2_next], "H": h_next}
    outputs    = {"Q_GEN": q_gen, "V_T": v_t}

    return state_next, q_ah_next, outputs
