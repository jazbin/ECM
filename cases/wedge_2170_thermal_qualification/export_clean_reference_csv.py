#!/usr/bin/env python3
"""Compile the pure-thermal qualification run's function-object outputs into
one clean reference CSV: time, JR mean/max T, JR radial/axial probes, Can T,
top-end T, bottom-end T, total stored energy, total boundary heat loss.

rho_region taken from constant/<region>/thermophysicalProperties (constant,
uniform per region): JR=2660.7, Can=8000, Cap=1447.2 kg/m3.

Boundary heat loss is derived from energy-conservation closure
(Q_in_cumulative - stored_energy), NOT from directly integrating the
wallHeatFlux function object. The two were cross-checked and found
inconsistent by a factor of ~8 (wallHeatFlux integral over the 100-300s
relaxation window: -656J; energy-balance-implied loss over the same window:
+80.5J, matching a rho*Cp*V*deltaT hand calculation to ~1%). The stored-
energy/enthalpy-integral route is independently validated against a hand
calculation at multiple points in the run and is the one reported here;
the raw wallHeatFlux discrepancy is unresolved and should not be trusted
without further investigation of the externalWallHeatFluxTemperature BC's
flux reconstruction.
"""
import csv
import re
from pathlib import Path

CASE = Path(__file__).parent
PP = CASE / "postProcessing"
RHO = {"jellyRoll_rotated": 2660.7, "shell_rotated": 8000.0, "cap_rotated": 1447.2}


def read_dat(path):
    """Return {time: value} from a volFieldValue.dat (single-column) file."""
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        t, v = line.split()
        out[float(t)] = float(v)
    return out


def read_probe(path, index):
    """Return {time: value} for probe column `index` from a probes/T file."""
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split()
        t = float(parts[0])
        out[t] = float(parts[1 + index])
    return out


jr_mean = read_dat(PP / "jellyRoll_rotated/jellyRollMeanT/0/volFieldValue.dat")
jr_max = read_dat(PP / "jellyRoll_rotated/jellyRollMaxT/0/volFieldValue.dat")
can_mean = read_dat(PP / "shell_rotated/canMeanT/0/volFieldValue.dat")
cap_mean = read_dat(PP / "cap_rotated/capMeanT/0/volFieldValue.dat")

jr_h = read_dat(PP / "jellyRoll_rotated/jellyRollHIntegral/0/volFieldValue.dat")
can_h = read_dat(PP / "shell_rotated/canHIntegral/0/volFieldValue.dat")
cap_h = read_dat(PP / "cap_rotated/capHIntegral/0/volFieldValue.dat")

can_loss_raw = read_dat(PP / "shell_rotated/canBoundaryHeatLoss/0/surfaceFieldValue.dat")
cap_loss_raw = read_dat(PP / "cap_rotated/capBoundaryHeatLoss/0/surfaceFieldValue.dat")

Q_IN_W_per_m3 = 150000.0
JR_ZONE_VOLUME_m3 = 2.1647991e-05  # printed by fvOptions at case start
PULSE_END_S = 100.0
Q_IN_TOTAL_W = Q_IN_W_per_m3 * JR_ZONE_VOLUME_m3

# jrProbes: 0=centerline mid-height, 1=near-outer-edge mid-height (radial),
# 2=near-bottom (axial), 3=near-top (axial)
jr_probe_centerline = read_probe(PP / "jrProbes/jellyRoll_rotated/0/T", 0)
jr_probe_radial = read_probe(PP / "jrProbes/jellyRoll_rotated/0/T", 1)
jr_probe_axial_bottom = read_probe(PP / "jrProbes/jellyRoll_rotated/0/T", 2)
jr_probe_axial_top = read_probe(PP / "jrProbes/jellyRoll_rotated/0/T", 3)

# canProbes: 0=outer wall mid-height, 1=bottom-end
can_probe_wall = read_probe(PP / "canProbes/shell_rotated/0/T", 0)
bottom_end_T = read_probe(PP / "canProbes/shell_rotated/0/T", 1)

# capProbes: 0=top-center (top-end temperature)
top_end_T = read_probe(PP / "capProbes/cap_rotated/0/T", 0)

times = sorted(jr_mean.keys())
t0 = times[0]
e0 = (
    RHO["jellyRoll_rotated"] * jr_h[t0]
    + RHO["shell_rotated"] * can_h[t0]
    + RHO["cap_rotated"] * cap_h[t0]
)

rows = []
for t in times:
    stored_energy_J = (
        RHO["jellyRoll_rotated"] * jr_h[t]
        + RHO["shell_rotated"] * can_h[t]
        + RHO["cap_rotated"] * cap_h[t]
    ) - e0
    q_in_cumulative_J = Q_IN_TOTAL_W * min(t, PULSE_END_S)
    # Energy-conservation closure: what must have left via the boundary,
    # given the (independently validated) stored-energy trace above.
    boundary_heat_loss_J_cumulative = q_in_cumulative_J - stored_energy_J
    # Raw wallHeatFlux areaIntegrate, instantaneous W -- diagnostic only,
    # inconsistent with conservation by ~8x, see module docstring.
    wallheatflux_raw_W_DIAGNOSTIC_ONLY = can_loss_raw[t] + cap_loss_raw[t]
    rows.append(
        {
            "time_s": t,
            "JR_mean_T_K": jr_mean[t],
            "JR_max_T_K": jr_max[t],
            "JR_probe_centerline_T_K": jr_probe_centerline.get(t, ""),
            "JR_probe_radial_edge_T_K": jr_probe_radial.get(t, ""),
            "JR_probe_axial_bottom_T_K": jr_probe_axial_bottom.get(t, ""),
            "JR_probe_axial_top_T_K": jr_probe_axial_top.get(t, ""),
            "Can_mean_T_K": can_mean[t],
            "Can_wall_probe_T_K": can_probe_wall.get(t, ""),
            "top_end_T_K": top_end_T.get(t, ""),
            "bottom_end_T_K": bottom_end_T.get(t, ""),
            "total_stored_energy_J_rel_t0": stored_energy_J,
            "total_boundary_heat_loss_J_cumulative": boundary_heat_loss_J_cumulative,
            "wallheatflux_raw_W_DIAGNOSTIC_ONLY": wallheatflux_raw_W_DIAGNOSTIC_ONLY,
        }
    )

out_path = CASE / "reference_thermal_transient.csv"
with open(out_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {out_path} ({len(rows)} rows, t={times[0]}..{times[-1]}s)")
