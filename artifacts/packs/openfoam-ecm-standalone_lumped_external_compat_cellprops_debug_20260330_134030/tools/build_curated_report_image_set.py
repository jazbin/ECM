#!/usr/bin/env python3
from __future__ import annotations

import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyvista as pv
from matplotlib.collections import PolyCollection


ROOT = Path("/workspace")
DEST = ROOT / "artifacts" / "plots" / "report_image_set_20260328"

AXES = {
    "x": (1, 2, 0, "Y [m]", "Z [m]"),
    "z": (0, 1, 2, "X [m]", "Y [m]"),
}


def _nearest_time(reader: pv.OpenFOAMReader, requested: float) -> float:
    return min(reader.time_values, key=lambda t: abs(float(t) - requested))


def _read_case(case_dir: Path, time_value: float):
    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")
    reader = pv.OpenFOAMReader(str(foam_path))
    actual_time = _nearest_time(reader, time_value)
    reader.set_active_time_value(actual_time)
    return reader.read(), actual_time


def _poly_faces(poly: pv.PolyData) -> list[np.ndarray]:
    faces = np.asarray(poly.faces, dtype=np.int64)
    out: list[np.ndarray] = []
    i = 0
    while i < len(faces):
        n = int(faces[i])
        if n <= 0:
            break
        out.append(faces[i + 1 : i + 1 + n])
        i += n + 1
    return out


def _slice_metric(poly: pv.PolyData, field: str) -> float:
    if poly.n_points == 0:
        return -1.0
    if field not in poly.cell_data and field in poly.point_data:
        poly = poly.point_data_to_cell_data()
    if field not in poly.cell_data or poly.n_cells == 0:
        return -1.0
    vals = np.asarray(poly.cell_data[field]).reshape(-1)
    if vals.size == 0:
        return -1.0
    nonzero = np.count_nonzero(np.abs(vals) > 1.0e-14)
    spread = float(np.std(vals))
    vmax = float(np.max(np.abs(vals)))
    return nonzero + 1000.0 * spread + 0.01 * vmax


def _best_slice_origin(mesh, field: str, normal: str) -> tuple[float, float, float]:
    axis0, axis1, slice_axis, _, _ = AXES[normal]
    bounds = mesh.bounds
    axis_min = bounds[2 * slice_axis]
    axis_max = bounds[2 * slice_axis + 1]
    center = list(mesh.center)
    best_origin = tuple(center)
    best_metric = -1.0
    for frac in np.linspace(0.15, 0.85, 25):
        pos = axis_min + frac * (axis_max - axis_min)
        origin = center.copy()
        origin[slice_axis] = pos
        sl = mesh.slice(normal=normal, origin=tuple(origin))
        metric = _slice_metric(sl, field)
        if metric > best_metric:
            best_metric = metric
            best_origin = tuple(origin)
    return best_origin


def _render_single_mesh_slice(mesh, field: str, normal: str, origin: tuple[float, float, float], out_path: Path, title: str) -> None:
    axis0, axis1, _, xlabel, ylabel = AXES[normal]
    sl = mesh.slice(normal=normal, origin=origin)
    if field not in sl.cell_data and field in sl.point_data:
        sl = sl.point_data_to_cell_data()
    pts = np.asarray(sl.points)
    polys = _poly_faces(sl)
    patches = [pts[idx][:, [axis0, axis1]] for idx in polys]
    vals = np.asarray(sl.cell_data[field]).reshape(-1)
    fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=180)
    coll = PolyCollection(patches, array=vals, cmap="inferno", edgecolors="none", linewidths=0.0)
    ax.add_collection(coll)
    ax.set_xlim(float(np.min(pts[:, axis0])), float(np.max(pts[:, axis0])))
    ax.set_ylim(float(np.min(pts[:, axis1])), float(np.max(pts[:, axis1])))
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.18)
    cb = fig.colorbar(coll, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(field)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _render_allregion_temperature(case_dir: Path, time_value: float, normal: str, out_path: Path, title: str) -> None:
    data, actual_time = _read_case(case_dir, time_value)
    temp_mesh = data["jellyRoll"]["internalMesh"]
    if normal == "x":
        origin = tuple(temp_mesh.center)
    else:
        origin = _best_slice_origin(temp_mesh, "T", normal)

    axis0, axis1, _, xlabel, ylabel = AXES[normal]
    slices = []
    vals_all = []
    for region in ("jellyRoll", "shell", "cap"):
        mesh = data[region]["internalMesh"]
        sl = mesh.slice(normal=normal, origin=origin)
        if "T" not in sl.cell_data and "T" in sl.point_data:
            sl = sl.point_data_to_cell_data()
        if sl.n_points == 0 or "T" not in sl.cell_data:
            continue
        slices.append(sl)
        vals_all.extend(np.asarray(sl.cell_data["T"]).reshape(-1).tolist())

    tmin, tmax = min(vals_all), max(vals_all)
    fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=180)
    for sl in slices:
        pts = np.asarray(sl.points)
        polys = _poly_faces(sl)
        patches = [pts[idx][:, [axis0, axis1]] for idx in polys]
        vals = np.asarray(sl.cell_data["T"]).reshape(-1)
        coll = PolyCollection(patches, array=vals, cmap="inferno", edgecolors="none", linewidths=0.0)
        coll.set_clim(tmin, tmax)
        ax.add_collection(coll)
    x_all = np.concatenate([np.asarray(sl.points)[:, axis0] for sl in slices])
    y_all = np.concatenate([np.asarray(sl.points)[:, axis1] for sl in slices])
    ax.set_xlim(float(np.min(x_all)), float(np.max(x_all)))
    ax.set_ylim(float(np.min(y_all)), float(np.max(y_all)))
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(f"{title} | t={actual_time:.6f} s")
    ax.grid(True, alpha=0.18)
    sm = plt.cm.ScalarMappable(cmap="inferno", norm=plt.Normalize(vmin=tmin, vmax=tmax))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("T [K]")
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _parse_qsum(log_path: Path):
    import re

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


def _plot_q_overlay(a_log: Path, b_log: Path, out_path: Path, title: str, xmax: float | None = None):
    ta, qa = _parse_qsum(a_log)
    tb, qb = _parse_qsum(b_log)
    fig, ax = plt.subplots(figsize=(7.4, 3.9), dpi=180)
    ax.plot(ta, qa, color="#1f77b4", lw=2.0, label="Lumped")
    ax.plot(tb, qb, color="#d62728", lw=2.0, ls="--", label="Distributed")
    ax.set_title(title)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Q_sum_check [W]")
    if xmax is not None:
        ax.set_xlim(0, xmax)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _copy(src: Path, dst: Path):
    shutil.copy2(src, dst)


def _accepted_timing_figure(out_path: Path):
    t = np.arange(0, 8, 1.0)
    ecm_fire = np.ones_like(t)
    raw = np.array([102, 98, 95, 92, 89, 87, 85, 83], dtype=float)
    alpha = 0.5
    applied = np.zeros_like(raw)
    applied[0] = raw[0]
    for i in range(1, len(raw)):
        applied[i] = alpha * raw[i] + (1.0 - alpha) * applied[i - 1]

    fig, axes = plt.subplots(3, 1, figsize=(8.2, 6.7), dpi=180, sharex=True)
    axes[0].step(t, np.ones_like(t), where="post", color="#6baed6", lw=2.0)
    axes[0].scatter(t, np.ones_like(t), color="#d62728", s=24, zorder=3)
    axes[0].set_yticks([])
    axes[0].set_title("A. Accepted validation cadence: ECM fires every CFD step")
    for tt in t:
        axes[0].axvline(tt, color="#bdbdbd", lw=0.5, alpha=0.5)

    axes[1].plot(t, raw, color="#2ca25f", lw=2.0, marker="o")
    axes[1].set_ylabel("Raw ECM output")
    axes[1].set_title("B. No skipped updates in the accepted validation configuration")
    axes[1].grid(True, alpha=0.25)

    axes[2].plot(t, raw, color="#9e9e9e", lw=1.5, marker="o", label="Raw ECM output")
    axes[2].plot(t, applied, color="#7f2704", lw=2.0, label="Applied source after relaxation")
    axes[2].set_ylabel("Applied source")
    axes[2].set_xlabel("CFD step / time index")
    axes[2].set_title("C. OpenFOAM-side smoothing still available via source relaxation")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(frameon=False, fontsize=8)
    fig.suptitle("Accepted Time-Stepping Behavior in the Current Validated Configuration", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _make_overlap_heat_fields():
    case_dir = ROOT / "cases" / "distributed_solid_overlap"
    mapping = ROOT / "cases" / "distributed_solid" / "ecm" / "mapping_table_axial6_radial3_2170mesh_overlap.csv"
    data, actual_time = _read_case(case_dir, 299.88382302871543)
    mesh = data["jellyRoll"]["internalMesh"]
    mesh_vol = np.asarray(mesh.compute_cell_sizes(length=False, area=False, volume=True).cell_data["Volume"]).reshape(-1)
    qvol = np.asarray(mesh.cell_data["ecmQdot"]).reshape(-1)
    cell_power = qvol * mesh_vol
    mapping_df = pd.read_csv(mapping)
    cell_weight_sum = mapping_df.groupby("meshKey")["weight"].sum()

    zone_power = {}
    zone_vol = {}
    for ecm_id, g in mapping_df.groupby("ecmCellId"):
        idx = g["meshKey"].to_numpy(dtype=int)
        w = g["weight"].to_numpy(dtype=float)
        zone_power[int(ecm_id)] = float(np.sum(cell_power[idx] * w) / np.sum(w))
        zone_vol[int(ecm_id)] = float(np.sum(w))

    row_idx = mapping_df.groupby("meshKey")["weight"].idxmax().to_numpy(dtype=int)
    owner = mapping_df.loc[row_idx, ["meshKey", "ecmCellId"]].sort_values("meshKey")
    zone_field = np.zeros(mesh.n_cells, dtype=float)
    zone_field[owner["meshKey"].to_numpy(dtype=int)] = owner["ecmCellId"].map(zone_power).to_numpy(dtype=float)

    mesh_zone = mesh.copy()
    mesh_zone.cell_data["zoneHeat_W"] = zone_field
    mesh_cell = mesh.copy()
    mesh_cell.cell_data["cellHeat_W"] = cell_power

    # longitudinal slices
    origin_x = tuple(mesh.center)
    _render_single_mesh_slice(mesh_zone, "zoneHeat_W", "x", origin_x, DEST / "13_overlap_mapping_heat_per_ecm_zone_W.png", f"Overlap mapping heat per ECM zone [W] | t={actual_time:.6f} s")
    _render_single_mesh_slice(mesh_cell, "cellHeat_W", "x", origin_x, DEST / "14_overlap_mapping_heat_per_cfd_cell_W.png", f"Overlap mapping heat per CFD cell [W] | t={actual_time:.6f} s")

    # support-aware cross sections
    origin_z_zone = _best_slice_origin(mesh_zone, "zoneHeat_W", "z")
    origin_z_cell = _best_slice_origin(mesh_cell, "cellHeat_W", "z")
    _render_single_mesh_slice(mesh_zone, "zoneHeat_W", "z", origin_z_zone, DEST / "28_overlap_mapping_heat_per_ecm_zone_W_cross.png", f"Overlap mapping heat per ECM zone [W] | support-aware cross-section | t={actual_time:.6f} s")
    _render_single_mesh_slice(mesh_cell, "cellHeat_W", "z", origin_z_cell, DEST / "29_overlap_mapping_heat_per_cfd_cell_W_cross.png", f"Overlap mapping heat per CFD cell [W] | support-aware cross-section | t={actual_time:.6f} s")

    # zone volume and heat-share bars
    z_ids = sorted(zone_power.keys())
    vols = np.array([zone_vol[i] for i in z_ids], dtype=float)
    heat = np.array([zone_power[i] for i in z_ids], dtype=float)

    fig, ax = plt.subplots(figsize=(8.0, 3.6), dpi=180)
    ax.bar(z_ids, vols * 1e9, color="#6baed6")
    ax.set_xlabel("ECM zone ID")
    ax.set_ylabel("Mapped zone volume [mm³]")
    ax.set_title("Overlap-weighted mapping: ECM zone volumes")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DEST / "30_overlap_mapping_zone_volumes.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 3.6), dpi=180)
    share = heat / max(np.sum(heat), 1.0e-30)
    ax.bar(z_ids, share, color="#fd8d3c")
    ax.set_xlabel("ECM zone ID")
    ax.set_ylabel("Heat share [-]")
    ax.set_title("Overlap-weighted mapping: ECM zone heat-share distribution")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DEST / "31_overlap_mapping_zone_heat_share.png", bbox_inches="tight")
    plt.close(fig)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for p in DEST.iterdir():
        if p.is_file():
            p.unlink()

    # copy stable externally useful figures
    _copy(ROOT / "artifacts/plots/client_report_full/architecture_20260328_005701.png", DEST / "01_architecture_workflow.png")
    _copy(ROOT / "artifacts/plots/client_report_full/model_concept_20260328_005701.png", DEST / "02_model_concept_lumped_vs_distributed.png")
    _copy(ROOT / "artifacts/plots/client_report_full/validation_summary_20260328_005701.png", DEST / "03_validation_summary_metrics.png")
    _copy(ROOT / "artifacts/plots/client_report_full/energy_balance_20260328_005701.png", DEST / "06_energy_balance_comparison.png")
    _copy(ROOT / "artifacts/plots/client_report_full/runtime_20260328_005701.png", DEST / "11_runtime_comparison.png")
    _copy(ROOT / "artifacts/plots/client_report_extra/validation_gate_bars.png", DEST / "21_validation_gate_bars.png")
    _copy(ROOT / "artifacts/plots/client_report_extra/mapping_old_vs_overlap_qsum.png", DEST / "15_assignment_vs_overlap_mapping_qsum.png")

    # accepted timing figure replaces earlier subcycling-emphasis figure
    _accepted_timing_figure(DEST / "12_timestep_and_interpolation_logic.png")

    # accepted comparison plots
    lumped_zero = ROOT / "artifacts/logs/validation_lumped_fw_ecm_zero_20260327_201034.log"
    dist_zero = ROOT / "artifacts/logs/validation_distributed_fw_ecm_zero_20260327_211414.log"
    lumped_fixed = ROOT / "artifacts/logs/validation_lumped_fw_ecm_current_20260327_201050.log"
    dist_fixed = ROOT / "artifacts/logs/validation_distributed_fw_ecm_current_20260327_224059.log"
    _plot_q_overlay(lumped_zero, dist_zero, DEST / "04_zero_current_comparison_30s.png", "Zero-current comparison", 30)
    _plot_q_overlay(lumped_fixed, dist_fixed, DEST / "05_fixed_current_comparison_30s.png", "Fixed-current comparison", 30)
    _plot_q_overlay(lumped_zero, dist_zero, DEST / "19_zero_current_comparison_first5s.png", "Zero-current comparison (first 5 s)", 5)
    _plot_q_overlay(lumped_fixed, dist_fixed, DEST / "20_fixed_current_comparison_first5s.png", "Fixed-current comparison (first 5 s)", 5)

    # support-aware temperature sections
    _render_allregion_temperature(ROOT / "cases/validation_lumped_fw_ecm_current", 30.0, "x", DEST / "07_lumped_allregions_longitudinal_30s.png", "Lumped all-region longitudinal section")
    _render_allregion_temperature(ROOT / "cases/validation_distributed_fw_ecm_current", 30.0, "x", DEST / "08_distributed_allregions_longitudinal_30s.png", "Distributed all-region longitudinal section")
    _render_allregion_temperature(ROOT / "cases/validation_lumped_fw_ecm_current", 30.0, "z", DEST / "09_lumped_allregions_cross_section_30s.png", "Lumped all-region cross-section")
    _render_allregion_temperature(ROOT / "cases/validation_distributed_fw_ecm_current", 30.0, "z", DEST / "10_distributed_allregions_cross_section_30s.png", "Distributed all-region cross-section")
    _render_allregion_temperature(ROOT / "cases/validation_lumped_fw_ecm_current", 10.0, "x", DEST / "22_lumped_allregions_longitudinal_10s.png", "Lumped all-region longitudinal section")
    _render_allregion_temperature(ROOT / "cases/validation_distributed_fw_ecm_current", 10.0, "x", DEST / "23_distributed_allregions_longitudinal_10s.png", "Distributed all-region longitudinal section")
    _render_allregion_temperature(ROOT / "cases/validation_lumped_fw_ecm_current", 10.0, "z", DEST / "24_lumped_allregions_cross_section_10s.png", "Lumped all-region cross-section")
    _render_allregion_temperature(ROOT / "cases/validation_distributed_fw_ecm_current", 10.0, "z", DEST / "25_distributed_allregions_cross_section_10s.png", "Distributed all-region cross-section")
    _render_allregion_temperature(ROOT / "cases/distributed_solid_overlap", 299.88382302871543, "x", DEST / "26_overlap_case_allregions_longitudinal_300s.png", "Overlap case all-region longitudinal section")
    _render_allregion_temperature(ROOT / "cases/distributed_solid_overlap", 299.88382302871543, "z", DEST / "27_overlap_case_allregions_cross_section_300s.png", "Overlap case all-region cross-section")

    # mapping figures
    _make_overlap_heat_fields()

    # keep technical support views
    _copy(ROOT / "artifacts/plots/client_report_full/weight_low_20260328_005701.png", DEST / "16_weight_support_zone00.png")
    _copy(ROOT / "artifacts/plots/client_report_full/weight_mid_20260328_005701.png", DEST / "17_weight_support_zone08.png")
    _copy(ROOT / "artifacts/plots/client_report_full/weight_high_20260328_005701.png", DEST / "18_weight_support_zone17.png")

    manifest = DEST / "MANIFEST.md"
    manifest.write_text(
        """# Report Image Set

This folder contains the curated image set currently intended for report assembly.

## Main body candidates

- `01_architecture_workflow.png`
- `02_model_concept_lumped_vs_distributed.png`
- `03_validation_summary_metrics.png`
- `04_zero_current_comparison_30s.png`
- `05_fixed_current_comparison_30s.png`
- `06_energy_balance_comparison.png`
- `07_lumped_allregions_longitudinal_30s.png`
- `08_distributed_allregions_longitudinal_30s.png`
- `09_lumped_allregions_cross_section_30s.png`
- `10_distributed_allregions_cross_section_30s.png`
- `11_runtime_comparison.png`
- `12_timestep_and_interpolation_logic.png`
- `13_overlap_mapping_heat_per_ecm_zone_W.png`
- `14_overlap_mapping_heat_per_cfd_cell_W.png`
- `28_overlap_mapping_heat_per_ecm_zone_W_cross.png`
- `29_overlap_mapping_heat_per_cfd_cell_W_cross.png`
- `30_overlap_mapping_zone_volumes.png`
- `31_overlap_mapping_zone_heat_share.png`

## Appendix / technical figures

- `15_assignment_vs_overlap_mapping_qsum.png`
- `16_weight_support_zone00.png`
- `17_weight_support_zone08.png`
- `18_weight_support_zone17.png`
- `19_zero_current_comparison_first5s.png`
- `20_fixed_current_comparison_first5s.png`
- `21_validation_gate_bars.png`
- `22_lumped_allregions_longitudinal_10s.png`
- `23_distributed_allregions_longitudinal_10s.png`
- `24_lumped_allregions_cross_section_10s.png`
- `25_distributed_allregions_cross_section_10s.png`
- `26_overlap_case_allregions_longitudinal_300s.png`
- `27_overlap_case_allregions_cross_section_300s.png`

## Notes

- Cross-sections are now generated with support/variation-aware plane selection for the field being shown rather than by fixed geometric center alone.
- The time-stepping figure is now centered on the accepted validated configuration: ECM fire at every CFD step, with optional relaxation on the applied field.
- The overlap mapping visuals now include applied heat in `W`, plus zone-volume and zone-heat-share summaries.
""",
        encoding="utf-8",
    )
    print(DEST)


if __name__ == "__main__":
    main()
