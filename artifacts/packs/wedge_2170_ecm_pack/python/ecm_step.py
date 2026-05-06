"""
ECM step module — full API implementation.

Supports the external lookup-table schema:
  params.csv columns:
    Q_Ah, T_degC, R0_Ohm, R_Ohm_1, R_Ohm_2, C_F_1, C_F_2,
    E_OCV_dch_V, E_OCV_ch_V, gamma, dUdT

  cellprops.csv columns:
    Qnom_Ah (or capacity_Ah), Asurf_m2, T_ref_degC

Replace params.csv and cellprops.csv with real cell data — no code changes needed.

Conventions
-----------
- Positive current = discharge
- Charge throughput q_ah is positive on discharge
- Temperature is NOT integrated internally; it is required as an input
- Q_GEN includes Joule heating and entropic heating (dUdT term)
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator


def build_step_cache(params_df: pd.DataFrame) -> dict:
    """
    Build interpolation tables from params_df once at startup.

    Expected columns: Q_Ah, T_degC, R0_Ohm, R_Ohm_1, R_Ohm_2, C_F_1, C_F_2,
                      E_OCV_dch_V, E_OCV_ch_V, gamma, dUdT
    """
    pts = params_df[["Q_Ah", "T_degC"]].to_numpy(dtype=float)

    def _interp(col: str):
        vals = params_df[col].to_numpy(dtype=float)
        lin  = LinearNDInterpolator(pts, vals, fill_value=float("nan"))
        near = NearestNDInterpolator(pts, vals)
        def _lookup(q, t):
            v = float(lin(q, t))
            return v if math.isfinite(v) else float(near(q, t))
        return _lookup

    return {
        "R0":      _interp("R0_Ohm"),
        "R1":      _interp("R_Ohm_1"),
        "R2":      _interp("R_Ohm_2"),
        "C1":      _interp("C_F_1"),
        "C2":      _interp("C_F_2"),
        "OCV_dch": _interp("E_OCV_dch_V"),
        "OCV_ch":  _interp("E_OCV_ch_V"),
        "gamma":   _interp("gamma"),
        "dUdT":    _interp("dUdT"),
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
    q_ah         : charge removed so far [Ah]  (positive = discharge)
    v_rc         : RC branch voltages, shape (2,) [V]
    hysteresis   : hysteresis state [-1..1]
    T_cell_degC  : externally imposed cell temperature [deg C]
    params_df    : parameter table (passed through; cache is used for lookups)
    cellprops_df : cell properties -- Qnom_Ah (or capacity_Ah), Asurf_m2
    lookup_cache : dict built by build_step_cache(params_df)

    Returns
    -------
    state_next : dict  -- keys "V_RC" (2-element list), "H" (float), "T_CELL" (float)
    q_ah_next  : float
    outputs    : dict  -- keys "Q_GEN" (W), "V_T" (V), plus diagnostics
    """
    # Cell capacity
    for col in ("Qnom_Ah", "capacity_Ah"):
        if col in cellprops_df.columns:
            Qnom = float(cellprops_df[col].iloc[0])
            break
    else:
        raise ValueError("cellprops_df missing Qnom_Ah / capacity_Ah column")

    I     = float(current_a)
    T     = float(T_cell_degC)
    dt    = float(dt_s)
    q_now = float(q_ah)

    # Coulomb counting (positive I = discharge = q grows)
    q_ah_next = q_now + I * dt / 3600.0
    q_ah_next = max(0.0, min(q_ah_next, Qnom))
    q_mid = 0.5 * (q_now + q_ah_next)

    # Parameter lookup at (q_mid, T)
    cache = lookup_cache
    r0  = max(1e-9, cache["R0"](q_mid, T))
    r1  = max(1e-9, cache["R1"](q_mid, T))
    r2  = max(1e-9, cache["R2"](q_mid, T))
    c1  = max(1e-9, cache["C1"](q_mid, T))
    c2  = max(1e-9, cache["C2"](q_mid, T))
    ocv_dch = float(cache["OCV_dch"](q_mid, T))
    ocv_ch  = float(cache["OCV_ch"](q_mid, T))
    gamma   = max(0.0, float(cache["gamma"](q_mid, T)))
    dUdT    = float(cache["dUdT"](q_mid, T))

    # RC branch update (discrete-time exact)
    tau1 = max(r1 * c1, 1e-9)
    tau2 = max(r2 * c2, 1e-9)
    a1   = math.exp(-dt / tau1)
    a2   = math.exp(-dt / tau2)

    v_rc  = np.asarray(v_rc, dtype=float)
    v_rc1 = a1 * v_rc[0] + (1.0 - a1) * r1 * I
    v_rc2 = a2 * v_rc[1] + (1.0 - a2) * r2 * I

    # Hysteresis: exponential approach driven by charge throughput
    # dH/dq_ah = gamma * (sign(I) - H)  =>  H_next = H*exp(-gamma*dq) + sign*(1-exp)
    if abs(I) > 1e-12:
        sign_I = 1.0 if I > 0 else -1.0
        dq     = gamma * abs(I) * dt / 3600.0
        a_h    = math.exp(-dq)
        H_next = a_h * float(hysteresis) + sign_I * (1.0 - a_h)
    else:
        H_next = float(hysteresis)
    H_next = max(-1.0, min(1.0, H_next))

    # OCV with hysteresis blending: H=+1 full discharge, H=-1 full charge
    h_blend = 0.5 * (1.0 + H_next)
    ocv_v   = h_blend * ocv_dch + (1.0 - h_blend) * ocv_ch

    # Terminal voltage
    v_t = ocv_v - I * r0 - v_rc1 - v_rc2

    # Heat generation
    q_joule   = I**2 * r0 + abs(I) * (abs(v_rc1) + abs(v_rc2))
    T_K       = T + 273.15
    q_entropy = -I * T_K * dUdT      # exothermic on discharge when dUdT < 0
    q_gen     = q_joule + q_entropy

    state_next = {
        "V_RC":   [float(v_rc1), float(v_rc2)],
        "H":      float(H_next),
        "T_CELL": float(T),
    }
    outputs = {
        "Q_GEN":     float(q_gen),
        "V_T":       float(v_t),
        "Q_JOULE":   float(q_joule),
        "Q_ENTROPY": float(q_entropy),
        "OCV_V":     float(ocv_v),
        "SOC":       float(1.0 - q_ah_next / Qnom) if Qnom > 0 else float("nan"),
    }

    return state_next, float(q_ah_next), outputs
