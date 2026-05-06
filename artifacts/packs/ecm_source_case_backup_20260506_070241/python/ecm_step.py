
"""
Single-step ECM API.

Purpose
-------
Advance the electrical ECM state by one timestep while treating cell temperature
as an externally imposed input.

Conventions
-----------
- Positive current = discharge
- Charge throughput q_ah is positive on discharge
- Temperature is NOT integrated internally; it is required as an input

Inputs
------
dt_s : float
    Timestep in seconds.
current_a : float
    Cell current in amps. Positive on discharge, negative on charge.
q_ah : float
    Charge throughput state in Ah. Positive on discharge.
v_rc : array-like, shape (2,)
    RC branch voltages [V_RC1, V_RC2] in volts.
hysteresis : float
    Hysteresis state, typically between -1 and 1.
T_cell_degC : float
    Externally imposed cell temperature in degC.
params_df : pandas.DataFrame
    Parameter lookup table with columns:
    Q_Ah, T_degC, R0_Ohm, R_Ohm_1, R_Ohm_2, C_F_1, C_F_2,
    E_OCV_dch_V, E_OCV_ch_V, gamma, dUdT
cellprops_df : pandas.DataFrame
    Cell properties table with columns:
    Asurf_m2, Qnom_Ah

Optional inputs
---------------
T_amb_degC : float
    Ambient temperature in degC.
h_w_m2k : float
    Convective heat transfer coefficient in W/m2/K.
lambda_Q : float
    Capacity scaling factor for table lookup.
lambda_R : float
    Resistance scaling factor applied to R0 only.

Returns
-------
state_next : dict
    {
        "V_RC": np.ndarray shape (2,),
        "H": float,
        "T_CELL": float,
    }
q_ah_next : float
    Updated charge throughput in Ah.
outputs : dict
    Derived signals and interpolated parameters.
"""

import math
from typing import Dict, Tuple

import numpy as np
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree

PARAM_NAMES = [
    "R0_Ohm",
    "R_Ohm_1",
    "R_Ohm_2",
    "C_F_1",
    "C_F_2",
    "E_OCV_dch_V",
    "E_OCV_ch_V",
    "gamma",
    "dUdT",
]


def _build_lookup_cache(params_df):
    points = params_df[["Q_Ah", "T_degC"]].to_numpy()
    tree = cKDTree(points)
    interpolators = {}
    for name in PARAM_NAMES:
        interpolators[name] = LinearNDInterpolator(
            points,
            params_df[name].to_numpy(),
            fill_value=np.nan,
        )
    return {
        "points": points,
        "tree": tree,
        "interpolators": interpolators,
        "params_df": params_df,
    }


def _lookup(cache, q_ah_lookup: float, T_cell_degC: float, param_name: str) -> float:
    interp = cache["interpolators"][param_name]
    val = interp([q_ah_lookup, T_cell_degC])
    val_arr = np.asarray(val)
    if np.isnan(val_arr).any():
        _, idx = cache["tree"].query([q_ah_lookup, T_cell_degC])
        return float(cache["params_df"][param_name].iloc[idx])
    return float(val_arr.item())


def _get_params(
    cache,
    q_ah: float,
    T_cell_degC: float,
    lambda_Q: float,
    lambda_R: float,
) -> Dict[str, float]:
    q_ah_lookup = q_ah / lambda_Q if lambda_Q > 0.0 else q_ah
    return {
        "R0": _lookup(cache, q_ah_lookup, T_cell_degC, "R0_Ohm") * lambda_R,
        "R1": _lookup(cache, q_ah_lookup, T_cell_degC, "R_Ohm_1"),
        "R2": _lookup(cache, q_ah_lookup, T_cell_degC, "R_Ohm_2"),
        "C1": _lookup(cache, q_ah_lookup, T_cell_degC, "C_F_1"),
        "C2": _lookup(cache, q_ah_lookup, T_cell_degC, "C_F_2"),
        "V_OCV_DCH": _lookup(cache, q_ah_lookup, T_cell_degC, "E_OCV_dch_V"),
        "V_OCV_CH": _lookup(cache, q_ah_lookup, T_cell_degC, "E_OCV_ch_V"),
        "GAMMA": _lookup(cache, q_ah_lookup, T_cell_degC, "gamma"),
        "DUDT": _lookup(cache, q_ah_lookup, T_cell_degC, "dUdT"),
    }


def _compute_outputs(
    v_rc: np.ndarray,
    hysteresis: float,
    current_a: float,
    q_ah: float,
    T_cell_degC: float,
    cache,
    q_nom_ah: float,
    area_m2: float,
    T_amb_degC: float,
    h_w_m2k: float,
    lambda_Q: float,
    lambda_R: float,
) -> Dict[str, float]:
    params = _get_params(cache, q_ah, T_cell_degC, lambda_Q=lambda_Q, lambda_R=lambda_R)

    v_ocv_avg = 0.5 * (params["V_OCV_CH"] + params["V_OCV_DCH"])
    v_ocv = (
        0.5 * (1.0 + hysteresis) * params["V_OCV_CH"]
        + 0.5 * (1.0 - hysteresis) * params["V_OCV_DCH"]
    )

    v_op = params["R0"] * current_a + v_rc[0] + v_rc[1]
    v_t = v_ocv + v_op

    q_ir = current_a * (v_t - v_ocv)
    q_hys = current_a * (v_ocv - v_ocv_avg)
    t_k = T_cell_degC + 273.15
    q_rev = current_a * t_k * params["DUDT"]
    q_gen = q_ir + q_hys + q_rev

    return {
        "V_RC": v_rc.copy(),
        "T_CELL": float(T_cell_degC),
        "H": float(hysteresis),
        "R0": params["R0"],
        "R1": params["R1"],
        "R2": params["R2"],
        "C1": params["C1"],
        "C2": params["C2"],
        "V_OCV_DCH": params["V_OCV_DCH"],
        "V_OCV_CH": params["V_OCV_CH"],
        "V_OCV_AVG": v_ocv_avg,
        "V_OCV": v_ocv,
        "V_OP": v_op,
        "V_T": v_t,
        "Q_IR": q_ir,
        "Q_HYS": q_hys,
        "Q_REV": q_rev,
        "Q_GEN": q_gen,
        "Q_NOM_AH": float(q_nom_ah),
        "Q_AH": float(q_ah),
    }


def ecm_step(
    dt_s: float,
    current_a: float,
    q_ah: float,
    v_rc,
    hysteresis: float,
    T_cell_degC: float,
    params_df,
    cellprops_df,
    T_amb_degC: float = 25.0,
    h_w_m2k: float = 10.0,
    lambda_Q: float = 1.0,
    lambda_R: float = 1.0,
    lookup_cache=None,
) -> Tuple[dict, float, dict]:
    """
    Advance the ECM electrical state by one timestep.

    Parameters
    ----------
    dt_s, current_a, q_ah, v_rc, hysteresis, T_cell_degC
        See module docstring.
    params_df, cellprops_df
        Lookup and cell property tables.
    T_amb_degC, h_w_m2k, lambda_Q, lambda_R
        Environmental and scaling inputs.
    lookup_cache : dict or None
        Optional precomputed lookup cache created with build_step_cache().
        Reuse this across many calls for faster execution.

    Returns
    -------
    state_next, q_ah_next, outputs
    """
    v_rc = np.asarray(v_rc, dtype=float).reshape(2)
    hysteresis = float(np.clip(hysteresis, -1.0, 1.0))
    q_nom_ah = float(cellprops_df["Qnom_Ah"].iloc[0])
    area_m2 = float(cellprops_df["Asurf_m2"].iloc[0])

    cache = lookup_cache if lookup_cache is not None else _build_lookup_cache(params_df)
    params = _get_params(cache, q_ah, T_cell_degC, lambda_Q=lambda_Q, lambda_R=lambda_R)

    tau1 = params["R1"] * params["C1"]
    tau2 = params["R2"] * params["C2"]

    exp1 = math.exp(-dt_s / tau1) if tau1 > 0.0 else 0.0
    exp2 = math.exp(-dt_s / tau2) if tau2 > 0.0 else 0.0

    v_rc_next = np.empty(2, dtype=float)
    v_rc_next[0] = v_rc[0] * exp1 + current_a * params["R1"] * (1.0 - exp1)
    v_rc_next[1] = v_rc[1] * exp2 + current_a * params["R2"] * (1.0 - exp2)

    i_n = current_a / (3600.0 * q_nom_ah) if q_nom_ah > 0.0 else 0.0
    h_next = hysteresis + dt_s * params["GAMMA"] * abs(i_n) * (np.sign(current_a) - hysteresis)
    h_next = float(np.clip(h_next, -1.0, 1.0))

    q_ah_next = float(q_ah + current_a * dt_s / 3600.0)

    state_next = {
        "V_RC": v_rc_next,
        "H": h_next,
        "T_CELL": float(T_cell_degC),
    }

    outputs = _compute_outputs(
        v_rc=v_rc_next,
        hysteresis=h_next,
        current_a=current_a,
        q_ah=q_ah_next,
        T_cell_degC=T_cell_degC,
        cache=cache,
        q_nom_ah=q_nom_ah,
        area_m2=area_m2,
        T_amb_degC=T_amb_degC,
        h_w_m2k=h_w_m2k,
        lambda_Q=lambda_Q,
        lambda_R=lambda_R,
    )

    return state_next, q_ah_next, outputs


def build_step_cache(params_df) -> dict:
    """Precompute table interpolation objects for reuse across repeated calls."""
    return _build_lookup_cache(params_df)
