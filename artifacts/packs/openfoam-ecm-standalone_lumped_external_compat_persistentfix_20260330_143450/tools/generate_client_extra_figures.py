#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyvista as pv
from matplotlib.collections import PolyCollection


ROOT = Path("/workspace")
OUT = ROOT / "artifacts" / "plots" / "client_report_extra"
OUT.mkdir(parents=True, exist_ok=True)

_AXES = {
    "x": (1, 2, 0, "Y [m]", "Z [m]"),
    "z": (0, 1, 2, "X [m]", "Y [m]"),
}


def _parse_qsum(log_path: Path):
    re_t = re.compile(r"^\s*Time = ([0-9eE+\-.]+)")
    re_q = re.compile(r"^\s*Q_sum_check\s+([0-9eE+\-.]+)\s*W?\s*$")
    t, q = [], []
    ct = None
    for line in log_path.read_text(errors="ignore").splitlines():
        mt = re_t.match(line)
        if mt:
            ct = float(mt.group(1))
            continue
        mq = re_q.match(line)
        if mq and ct is not None:
            t.append(ct)
            q.append(float(mq.group(1)))
    return np.asarray(t), np.asarray(q)


def _nearest_time(reader: pv.OpenFOAMReader, requested: float) -> float:
    return min(reader.time_values, key=lambda t: abs(float(t) - requested))


def _poly_faces(poly: pv.PolyData):
    faces = np.asarray(poly.faces, dtype=np.int64)
    out = []
    i = 0
    while i < len(faces):
        n = int(faces[i])
        if n <= 0:
            break
        out.append(faces[i + 1 : i + 1 + n])
        i += n + 1
    return out


def _read_case(case_dir: Path, time_value: float):
    foam = case_dir / "foam.foam"
    if not foam.exists():
        foam.write_text("")
    reader = pv.OpenFOAMReader(str(foam))
    t = _nearest_time(reader, time_value)
    reader.set_active_time_value(t)
    return reader.read(), t


def _render_allregions(case_dir: Path, time_value: float, normal: str, out_path: Path, title: str):
    data, actual = _read_case(case_dir, time_value)
    axis0, axis1, slice_axis, xlabel, ylabel = _AXES[normal]
    regions = []
    vals_all = []
    for region in ("jellyRoll", "shell", "cap"):
        mesh = data[region]["internalMesh"]
        origin = list(mesh.center)
        origin[slice_axis] = mesh.center[slice_axis]
        sl = mesh.slice(normal=normal, origin=tuple(origin))
        if "T" not in sl.cell_data and "T" in sl.point_data:
            sl = sl.point_data_to_cell_data()
        if sl.n_points == 0 or "T" not in sl.cell_data:
            continue
        regions.append(sl)
        vals_all.extend(np.asarray(sl.cell_data["T"]).reshape(-1).tolist())
    tmin, tmax = min(vals_all), max(vals_all)
    fig, ax = plt.subplots(figsize=(6.2, 4.6), dpi=170)
    for sl in regions:
        pts = np.asarray(sl.points)
        patches = [pts[idx][:, [axis0, axis1]] for idx in _poly_faces(sl)]
        vals = np.asarray(sl.cell_data["T"]).reshape(-1)
        coll = PolyCollection(patches, array=vals, cmap="inferno", edgecolors="none", linewidths=0.0)
        coll.set_clim(tmin, tmax)
        ax.add_collection(coll)
    x_all = np.concatenate([np.asarray(sl.points)[:, axis0] for sl in regions])
    y_all = np.concatenate([np.asarray(sl.points)[:, axis1] for sl in regions])
    ax.set_xlim(float(np.min(x_all)), float(np.max(x_all)))
    ax.set_ylim(float(np.min(y_all)), float(np.max(y_all)))
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(f"{title} | t={actual:.6f} s")
    ax.grid(True, alpha=0.18)
    sm = plt.cm.ScalarMappable(cmap="inferno", norm=plt.Normalize(vmin=tmin, vmax=tmax))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("T [K]")
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _simple_overlay_plot(series, labels, colors, styles, out_path, title, ylabel, xmax=None):
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=170)
    for (x, y), lab, col, ls in zip(series, labels, colors, styles):
        ax.plot(x, y, label=lab, color=col, lw=2.0, ls=ls)
    ax.set_title(title)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(ylabel)
    if xmax is not None:
        ax.set_xlim(0, xmax)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _plot_mapping_compare():
    old_log = ROOT / "artifacts/logs/distributed_solid_run_20260327_163918.log"
    new_log = ROOT / "artifacts/logs/distributed_solid_run_20260328_001212.log"
    to, qo = _parse_qsum(old_log)
    tn, qn = _parse_qsum(new_log)
    _simple_overlay_plot(
        [(to, qo), (tn, qn)],
        ["Assignment map", "Overlap-weighted map"],
        ["#1f77b4", "#d62728"],
        ["-", "--"],
        OUT / "mapping_old_vs_overlap_qsum.png",
        "Distributed 300 s: Assignment vs Overlap-Weighted Mapping",
        "Q_sum_check [W]",
        xmax=300,
    )


def _plot_zero_and_fixed_zoom():
    lz = ROOT / "artifacts/logs/validation_lumped_fw_ecm_zero_20260327_201034.log"
    dz = ROOT / "artifacts/logs/validation_distributed_fw_ecm_zero_20260327_211414.log"
    lc = ROOT / "artifacts/logs/validation_lumped_fw_ecm_current_20260327_201050.log"
    dc = ROOT / "artifacts/logs/validation_distributed_fw_ecm_current_20260327_224059.log"
    for name, a, b, title in [
        ("zero_30s", lz, dz, "Zero-Current Comparison"),
        ("fixed_30s", lc, dc, "Fixed-Current Comparison"),
    ]:
        ta, qa = _parse_qsum(a)
        tb, qb = _parse_qsum(b)
        _simple_overlay_plot([(ta, qa), (tb, qb)], ["Lumped", "Distributed"], ["#1f77b4", "#d62728"], ["-", "--"], OUT / f"{name}.png", title, "Q_sum_check [W]", xmax=30)
        _simple_overlay_plot([(ta, qa), (tb, qb)], ["Lumped", "Distributed"], ["#1f77b4", "#d62728"], ["-", "--"], OUT / f"{name}_zoom5.png", f"{title} (First 5 s)", "Q_sum_check [W]", xmax=5)


def _plot_validation_bars():
    l = {
        "timestep": json.loads(sorted((ROOT / "artifacts/validation/lumped_forward/timestep").glob("metrics_*.json"))[-1].read_text()),
        "energy": json.loads(sorted((ROOT / "artifacts/validation/lumped_forward/energy").glob("metrics_*.json"))[-1].read_text()),
        "mesh": json.loads(sorted((ROOT / "artifacts/validation/lumped_forward/mesh").glob("metrics_*.json"))[-1].read_text()),
    }
    d = {
        "timestep": json.loads(sorted((ROOT / "artifacts/validation/distributed_forward/timestep").glob("metrics_*.json"))[-1].read_text()),
        "energy": json.loads(sorted((ROOT / "artifacts/validation/distributed_forward/energy").glob("metrics_*.json"))[-1].read_text()),
        "mesh": json.loads(sorted((ROOT / "artifacts/validation/distributed_forward/mesh").glob("metrics_*.json"))[-1].read_text()),
    }
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6), dpi=170)
    cats = ["Lumped", "Distributed"]
    axes[0].bar(cats, [l["timestep"]["delta_T_05_vs_025_K"], d["timestep"]["delta_T_025_vs_0125_K"]], color=["#1f77b4", "#d62728"])
    axes[0].set_title("Timestep ΔT Gate [K]")
    axes[1].bar(cats, [abs(l["energy"]["energy_error_percent"]), abs(d["energy"]["energy_error_percent"])], color=["#1f77b4", "#d62728"])
    axes[1].set_title("|Energy Error| [%]")
    axes[2].bar(cats, [l["mesh"]["delta_Tmax_medium_vs_fine_K"], d["mesh"]["delta_Tmax_medium_vs_fine_K"]], color=["#1f77b4", "#d62728"])
    axes[2].set_title("Mesh ΔTmax Gate [K]")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "validation_gate_bars.png", bbox_inches="tight")
    plt.close(fig)


def _plot_timestep_interpolation_logic():
    t = np.arange(0, 10, 1.0)
    fire_t = np.array([0.0, 3.0, 6.0, 9.0])
    fire_q = np.array([100.0, 80.0, 70.0, 55.0])

    hold = np.zeros_like(t, dtype=float)
    extrap = np.zeros_like(t, dtype=float)
    hold[:] = fire_q[0]
    extrap[:] = fire_q[0]
    for i, tt in enumerate(t):
        last_idx = np.searchsorted(fire_t, tt, side="right") - 1
        last_idx = max(last_idx, 0)
        hold[i] = fire_q[last_idx]
        if last_idx == 0:
            extrap[i] = fire_q[0]
        else:
            dt_fire = fire_t[last_idx] - fire_t[last_idx - 1]
            slope = (fire_q[last_idx] - fire_q[last_idx - 1]) / dt_fire
            extrap[i] = max(0.0, fire_q[last_idx] + slope * (tt - fire_t[last_idx]))

    temporal_avg = fire_q.copy()
    temporal_avg[1:] = 0.5 * (fire_q[1:] + fire_q[:-1])
    applied = np.zeros_like(t, dtype=float)
    alpha = 0.5
    applied[0] = temporal_avg[0]
    fire_map = {int(ft): val for ft, val in zip(fire_t, temporal_avg)}
    for i in range(1, len(t)):
        q_new = fire_map.get(int(t[i]), applied[i - 1])
        applied[i] = alpha * q_new + (1.0 - alpha) * applied[i - 1]

    fig, axes = plt.subplots(3, 1, figsize=(8.0, 7.6), dpi=170, sharex=True)

    axes[0].step(t, np.ones_like(t), where="post", color="#6baed6", lw=2.0)
    axes[0].scatter(fire_t, np.ones_like(fire_t), color="#d62728", zorder=3, label="Real ECM fires")
    for tt in t:
        axes[0].axvline(tt, color="#bbbbbb", lw=0.5, alpha=0.5)
    axes[0].set_yticks([])
    axes[0].set_title("A. CFD step cadence and real ECM fire cadence (`ECM_CALL_EVERY_N_STEPS = 3`)")
    axes[0].legend(frameon=False, loc="upper right")

    axes[1].plot(t, hold, color="#3182bd", lw=2.0, label="Subcycle hold")
    axes[1].plot(t, extrap, color="#e6550d", lw=2.0, ls="--", label="Subcycle linear extrapolation")
    axes[1].scatter(fire_t, fire_q, color="black", s=18, zorder=4, label="Real ECM outputs")
    axes[1].set_ylabel("qVol / Q proxy")
    axes[1].set_title("B. ECM-side subcycle behavior from `ecm_coupler.py`")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(frameon=False, ncol=3, fontsize=8)

    axes[2].plot(fire_t, fire_q, color="#9e9e9e", lw=1.5, marker="o", label="Raw ECM outputs")
    axes[2].plot(fire_t, temporal_avg, color="#2ca25f", lw=2.0, marker="s", label="`temporalInterpolation linear`")
    axes[2].plot(t, applied, color="#7f2704", lw=2.0, label="Applied field after relaxation")
    axes[2].set_ylabel("Applied source proxy")
    axes[2].set_xlabel("CFD time / step index")
    axes[2].set_title("C. OpenFOAM-side averaging and relaxation before field update")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle("Implemented Multi-Rate Coupling Logic: Time Stepping, Reconstruction, and Applied Source Smoothing", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / "timestep_interpolation_logic.png", bbox_inches="tight")
    plt.close(fig)


def main():
    _plot_zero_and_fixed_zoom()
    _plot_mapping_compare()
    _plot_validation_bars()
    _plot_timestep_interpolation_logic()

    cases = [
        ("lumped_fw", ROOT / "cases/validation_lumped_fw_ecm_current", 10.0, "Lumped current case"),
        ("lumped_fw", ROOT / "cases/validation_lumped_fw_ecm_current", 30.0, "Lumped current case"),
        ("distributed_fw", ROOT / "cases/validation_distributed_fw_ecm_current", 10.0, "Distributed current case"),
        ("distributed_fw", ROOT / "cases/validation_distributed_fw_ecm_current", 30.0, "Distributed current case"),
        ("overlap_300s", ROOT / "cases/distributed_solid_overlap", 299.88382302871543, "Distributed overlap case"),
    ]
    for stem, case, t, title in cases:
        for normal in ("x", "z"):
            _render_allregions(case, t, normal, OUT / f"{stem}_t{int(round(t))}_{normal}.png", f"{title} all-region section")

    print(OUT)


if __name__ == "__main__":
    main()
