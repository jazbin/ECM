#!/usr/bin/env python3
import sys
from typing import Dict, List

def compute_qvol(keys: List[int], temps_K: List[float], inputs: Dict[str, float]) -> List[float]:
    """
    Mock black-box ECM heat model.

    Returns volumetric heat generation qVol [W/m^3] per coupled CFD *mesh cell*.

Notes:
- This mock uses the same global electrical inputs (e.g. I, SOC) for all mesh cells and does not create independent electrical states per mesh cell.
- In production, the ECM represents a *battery cell* (or module) with a single electrical state; spatial variation is handled by distributing heat over mesh cells.

    Replace this function by calling your real ECM implementation.
    """
    I = float(inputs.get("I", 0.0))       # current [A] (example)
    SOC = float(inputs.get("SOC", 0.5))   # state-of-charge [0..1] (example)
    lumped_total_power = float(inputs.get("lumpedOutput", 0.0)) >= 0.5
    active_volume = inputs.get("activeVolume", None)  # [m^3] optional

    t_min_k = inputs.get("T_min_K", None)
    t_max_k = inputs.get("T_max_K", None)
    q_min = inputs.get("qVolMin", None)
    q_max = inputs.get("qVolMax", None)

    # Simple synthetic model:
    # - baseline heat
    # - I^2 contribution
    # - temperature dependence
    # - SOC modulation
    q0 = 2.0e4            # W/m^3 baseline
    kI = 5.0e2            # W/m^3 per A^2
    kT = 1.0e3            # W/m^3 per K
    kSOC = 5.0e3          # W/m^3 amplitude

    q = []
    for T in temps_K:
        T_use = T
        if t_min_k is not None:
            T_use = max(float(t_min_k), T_use)
        if t_max_k is not None:
            T_use = min(float(t_max_k), T_use)
        dT = (T_use - 298.15)
        q_cell = q0 + kI*(I*I) + kT*dT + kSOC*(SOC - 0.5)
        if q_min is not None:
            q_cell = max(float(q_min), q_cell)
        if q_max is not None:
            q_cell = min(float(q_max), q_cell)
        q.append(q_cell)

    if lumped_total_power:
        if len(keys) != 1:
            sys.stderr.write(
                "[mock_model] WARN: lumpedOutput requested but multiple keys provided; "
                "returning volumetric qVol per key.\n"
            )
            return q

        if active_volume is None:
            sys.stderr.write(
                "[mock_model] WARN: lumpedOutput requested without activeVolume; "
                "returning volumetric qVol.\n"
            )
            return q

        q_mean = sum(q) / float(len(q))
        return [q_mean * float(active_volume)]

    return q
