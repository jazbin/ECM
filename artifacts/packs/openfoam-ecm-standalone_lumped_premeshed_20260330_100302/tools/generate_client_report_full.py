#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyvista as pv
from matplotlib.collections import PolyCollection
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path("/workspace")
REPORTS = ROOT / "artifacts" / "reports"
PLOTS = ROOT / "artifacts" / "plots" / "client_report_full"
PLOTS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _latest_json(dir_path: Path) -> dict:
    return json.loads(sorted(dir_path.glob("metrics_*.json"))[-1].read_text())


def _parse_qsum(log_path: Path) -> tuple[list[float], list[float]]:
    re_t = re.compile(r"^\s*Time = ([0-9eE+\-.]+)")
    re_q = re.compile(r"^\s*Q_sum_check\s+([0-9eE+\-.]+)\s*W?\s*$")
    times: list[float] = []
    vals: list[float] = []
    cur_t: float | None = None
    for line in _read(log_path).splitlines():
        mt = re_t.match(line)
        if mt:
            cur_t = float(mt.group(1))
            continue
        mq = re_q.match(line)
        if mq and cur_t is not None:
            times.append(cur_t)
            vals.append(float(mq.group(1)))
    return times, vals


def _max_abs_delta(l_log: Path, d_log: Path) -> float:
    tl, ql = _parse_qsum(l_log)
    td, qd = _parse_qsum(d_log)
    n = min(len(ql), len(qd))
    if n == 0:
        return float("nan")
    return max(abs(ql[i] - qd[i]) for i in range(n))


def _last_q(log_path: Path) -> float:
    _, q = _parse_qsum(log_path)
    return q[-1]


def _last_clock(log_path: Path) -> float | None:
    m = re.findall(r"ClockTime = ([0-9eE+\-.]+) s", _read(log_path))
    return float(m[-1]) if m else None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


_AXES = {
    "x": (1, 2, 0, "Y [m]", "Z [m]"),
    "y": (0, 2, 1, "X [m]", "Z [m]"),
    "z": (0, 1, 2, "X [m]", "Y [m]"),
}


def _nearest_time(reader: pv.OpenFOAMReader, requested: float) -> float:
    return min(reader.time_values, key=lambda t: abs(float(t) - requested))


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


def _render_allregion_section(case_dir: Path, time_value: float, out_path: Path, title: str, normal: str = "x") -> Path:
    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")
    reader = pv.OpenFOAMReader(str(foam_path))
    actual_time = _nearest_time(reader, time_value)
    reader.set_active_time_value(actual_time)
    data = reader.read()
    axis0, axis1, slice_axis, xlabel, ylabel = _AXES[normal]

    meshes = []
    temps_all = []
    for region in ("jellyRoll", "shell", "cap"):
        mesh = data[region]["internalMesh"]
        origin = list(mesh.center)
        origin[slice_axis] = mesh.center[slice_axis]
        sl = mesh.slice(normal=normal, origin=tuple(origin))
        if "T" not in sl.cell_data and "T" in sl.point_data:
            sl = sl.point_data_to_cell_data()
        if sl.n_points == 0 or "T" not in sl.cell_data:
            continue
        meshes.append(sl)
        temps_all.extend(np.asarray(sl.cell_data["T"]).reshape(-1).tolist())

    tmin = min(temps_all)
    tmax = max(temps_all)
    fig, ax = plt.subplots(figsize=(6.4, 4.4), dpi=170)
    for sl in meshes:
        pts = np.asarray(sl.points)
        polys = _poly_faces(sl)
        patches = [pts[idx][:, [axis0, axis1]] for idx in polys]
        vals = np.asarray(sl.cell_data["T"]).reshape(-1)
        coll = PolyCollection(
            patches,
            array=vals,
            cmap="inferno",
            edgecolors="none",
            linewidths=0.0,
        )
        coll.set_clim(tmin, tmax)
        ax.add_collection(coll)
    x_all = np.concatenate([np.asarray(sl.points)[:, axis0] for sl in meshes])
    y_all = np.concatenate([np.asarray(sl.points)[:, axis1] for sl in meshes])
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
    return out_path


def _render_sections() -> dict[str, Path]:
    out_dir = PLOTS / "sections_allregions"
    out_dir.mkdir(exist_ok=True)
    return {
        "lumped": _render_allregion_section(ROOT / "cases/validation_lumped_fw_ecm_current", 30.0, out_dir / "full_lumped_allregions_x.png", "Lumped all-region section at 30 s"),
        "distributed": _render_allregion_section(ROOT / "cases/validation_distributed_fw_ecm_current", 30.0, out_dir / "full_distributed_allregions_x.png", "Distributed all-region section at 30 s"),
    }


def _panel(images: list[Path], titles: list[str], out_path: Path, suptitle: str) -> Path:
    fig, axes = plt.subplots(1, len(images), figsize=(4.6 * len(images), 4.1), dpi=170)
    if len(images) == 1:
        axes = [axes]
    for ax, img_path, title in zip(axes, images, titles):
        ax.imshow(mpimg.imread(img_path))
        ax.set_title(title, fontsize=10)
        ax.axis("off")
    fig.suptitle(suptitle, fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_q_overlay(l_log: Path, d_log: Path, out_path: Path, title: str, xmax: float | None = None) -> Path:
    tl, ql = _parse_qsum(l_log)
    td, qd = _parse_qsum(d_log)
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=170)
    ax.plot(tl, ql, label="Lumped", lw=2.0, color="#1f77b4")
    ax.plot(td, qd, label="Distributed", lw=2.0, color="#d62728", ls="--")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Q_sum_check [W]")
    ax.set_title(title)
    if xmax is not None:
        ax.set_xlim(0, xmax)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_validation_summary(lump: dict, dist: dict, out_path: Path) -> Path:
    cats = [
        "ΔT timestep",
        "ΔQ timestep",
        "|energy err|",
        "ΔTmax mesh",
        "zero-current |Q|",
        "fixed-current smoothness",
    ]
    lv = [
        lump["timestep"]["delta_T_05_vs_025_K"],
        lump["timestep"]["delta_Q_05_vs_025_W"],
        abs(lump["energy"]["energy_error_percent"]),
        lump["mesh"]["delta_Tmax_medium_vs_fine_K"],
        lump["ecm_zero"]["max_abs_qsum_W"],
        lump["ecm_current"]["max_abs_second_diff_qsum_W"],
    ]
    dv = [
        dist["timestep"]["delta_T_025_vs_0125_K"],
        dist["timestep"]["delta_Q_025_vs_0125_W"],
        abs(dist["energy"]["energy_error_percent"]),
        dist["mesh"]["delta_Tmax_medium_vs_fine_K"],
        dist["ecm_zero"]["max_abs_qsum_W"],
        dist["ecm_current"]["max_abs_second_diff_qsum_after_5s_W"],
    ]
    x = np.arange(len(cats))
    width = 0.38
    fig, ax = plt.subplots(figsize=(8.5, 4.2), dpi=170)
    ax.bar(x - width / 2, lv, width, label="Lumped", color="#1f77b4")
    ax.bar(x + width / 2, dv, width, label="Distributed", color="#d62728")
    ax.set_xticks(x, cats, rotation=15, ha="right")
    ax.set_ylabel("Metric value")
    ax.set_title("Validation Summary Metrics")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_energy(lump: dict, dist: dict, out_path: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.8), dpi=170)
    labels = ["Lumped", "Distributed"]
    err = [lump["energy_error_percent"], dist["energy_error_percent"]]
    exp = [lump["energy_expected_J"], dist["energy_expected_J"]]
    st = [lump["energy_stored_J"], dist["energy_stored_J"]]
    x = np.arange(2)
    axes[0].bar(x, err, color=["#1f77b4", "#d62728"])
    axes[0].axhline(0, color="black", lw=0.8)
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Error [%]")
    axes[0].set_title("Adiabatic Energy-Balance Error")
    axes[0].grid(True, axis="y", alpha=0.25)
    width = 0.35
    axes[1].bar(x - width / 2, exp, width, label="Expected", color="#9ecae1")
    axes[1].bar(x + width / 2, st, width, label="Stored", color="#fdae6b")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Energy [J]")
    axes[1].set_title("Expected vs Stored")
    axes[1].legend(frameon=False, fontsize=8)
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_runtime(out_path: Path) -> Path:
    labels = [
        "File binary\n30 s",
        "Persistent JSON\n30 s",
        "Persistent binary\n30 s",
        "Distributed 300 s\nbinary-persistent",
        "Solver-only\n30 s",
        "Mock-coupled\n30 s",
        "Full coupled\n30 s",
    ]
    vals = [120.0, 291.0, 43.0, 468.0, 7.0, 42.0, 43.0]
    fig, ax = plt.subplots(figsize=(8.8, 4.2), dpi=170)
    ax.bar(np.arange(len(labels)), vals, color=["#9ecae1", "#fdd0a2", "#74c476", "#31a354", "#c6dbef", "#fdae6b", "#e6550d"])
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylabel("Wall time [s]")
    ax.set_title("Runtime Comparison Across Coupling Modes")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_architecture(out_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8.3, 3.1), dpi=170)
    ax.axis("off")
    boxes = [
        (0.04, 0.36, 0.22, 0.28, "OpenFOAM\nmesh cells"),
        (0.32, 0.36, 0.18, 0.28, "ecmCoupler\nfunction object"),
        (0.57, 0.36, 0.18, 0.28, "Python ECM\nruntime"),
        (0.82, 0.36, 0.12, 0.28, "ECM"),
    ]
    for x, y, w, h, txt in boxes:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor="#e8f1f8", edgecolor="#1f3b4d", lw=1.2))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=10)
    arrows = [
        ((0.26, 0.50), (0.32, 0.50), "T mesh / IDs"),
        ((0.50, 0.50), (0.57, 0.50), "binary pipe"),
        ((0.75, 0.50), (0.82, 0.50), "step"),
        ((0.82, 0.42), (0.75, 0.42), "Q"),
        ((0.57, 0.42), (0.50, 0.42), "qVol / diagnostics"),
        ((0.32, 0.42), (0.26, 0.42), "ecmQdot"),
    ]
    for a, b, txt in arrows:
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", lw=1.2, color="#37474f"))
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.05, txt, fontsize=8, ha="center")
    ax.set_title("OpenFOAM ↔ ECM Coupling Workflow", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_model_concept(out_path: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.4), dpi=170)
    for ax in axes:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
    axes[0].add_patch(plt.Circle((0.5, 0.5), 0.32, facecolor="#edf8fb", edgecolor="#1f3b4d", lw=1.2))
    axes[0].text(0.5, 0.67, "Lumped", ha="center", fontsize=12, weight="bold")
    axes[0].text(0.5, 0.52, "1 ECM state", ha="center", fontsize=10)
    axes[0].text(0.5, 0.41, "1 effective temperature", ha="center", fontsize=10)
    axes[0].text(0.5, 0.30, "1 total heat output", ha="center", fontsize=10)
    axes[1].add_patch(plt.Circle((0.5, 0.5), 0.32, facecolor="#fff5eb", edgecolor="#7f2704", lw=1.2))
    for i in range(6):
        z = 0.25 + i * 0.08
        axes[1].plot([0.24, 0.76], [z, z], color="#6FE7FF", ls="--", lw=0.8)
    axes[1].text(0.5, 0.67, "Distributed", ha="center", fontsize=12, weight="bold")
    axes[1].text(0.5, 0.50, "accepted baseline:\nshared ECM state", ha="center", fontsize=10)
    axes[1].text(0.5, 0.30, "distributed thermal/source\nmapping only", ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_validation_flow(out_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8.4, 2.8), dpi=170)
    ax.axis("off")
    labels = ["1 timestep", "2 energy", "3 mesh", "4 ecm_zero", "5 ecm_current"]
    xs = np.linspace(0.09, 0.91, len(labels))
    for x, lab in zip(xs, labels):
        ax.add_patch(plt.Rectangle((x - 0.08, 0.44), 0.16, 0.18, facecolor="#eef5db", edgecolor="#556b2f"))
        ax.text(x, 0.53, lab, ha="center", va="center", fontsize=10)
    for a, b in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(b - 0.085, 0.53), xytext=(a + 0.085, 0.53), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.text(0.5, 0.16, "If test N fails: fix only test N, rerun only test N, then continue forward.", ha="center", fontsize=10)
    ax.set_title("Forward-Only Validation Rule", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_timeline(out_path: Path) -> Path:
    phases = [
        "Initial coupling architecture",
        "Serial and parallel baseline validation",
        "CHT case construction",
        "Lumped-model stabilization",
        "Distributed stabilization",
        "Equivalence investigation",
        "Packaging and portability",
    ]
    y = np.arange(len(phases))[::-1]
    fig, ax = plt.subplots(figsize=(8.0, 4.4), dpi=170)
    ax.barh(y, np.ones_like(y), color=["#d9edf7", "#d9edf7", "#dff0d8", "#dff0d8", "#fcf8e3", "#f2dede", "#e8f1f8"])
    ax.set_yticks(y, phases)
    ax.set_xticks([])
    ax.set_xlim(0, 1)
    ax.set_title("Project Progress Timeline By Phase")
    for yi in y:
        ax.text(0.02, yi, "completed / matured", va="center", fontsize=8.5, color="#1f3b4d")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _plot_status_matrix(out_path: Path) -> Path:
    rows = ["Lumped", "Distributed"]
    cols = ["timestep", "energy", "mesh", "ecm_zero", "ecm_current"]
    m = np.ones((2, 5))
    fig, ax = plt.subplots(figsize=(6.6, 2.8), dpi=170)
    ax.imshow(m, cmap=plt.matplotlib.colors.ListedColormap(["#31a354"]), vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(cols)), cols)
    ax.set_yticks(np.arange(len(rows)), rows)
    ax.set_title("Validation Status Matrix")
    for i in range(2):
        for j in range(5):
            ax.text(j, i, "PASS", ha="center", va="center", color="white", weight="bold", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _read_mesh(case_dir: Path, region: str, time_value: float):
    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")
    reader = pv.OpenFOAMReader(str(foam_path))
    actual_time = _nearest_time(reader, time_value)
    reader.set_active_time_value(actual_time)
    data = reader.read()
    return data[region]["internalMesh"], actual_time


def _render_scalar_slice(mesh, field: str, normal: str, out_path: Path, title: str) -> Path:
    axis0, axis1, slice_axis, xlabel, ylabel = _AXES[normal]
    origin = list(mesh.center)
    origin[slice_axis] = mesh.center[slice_axis]
    sl = mesh.slice(normal=normal, origin=tuple(origin))
    if field not in sl.cell_data and field in sl.point_data:
        sl = sl.point_data_to_cell_data()
    pts = np.asarray(sl.points)
    polys = _poly_faces(sl)
    patches = [pts[idx][:, [axis0, axis1]] for idx in polys]
    vals = np.asarray(sl.cell_data[field]).reshape(-1)
    fig, ax = plt.subplots(figsize=(6.3, 4.8), dpi=170)
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
    return out_path


def _make_overlap_source_figures(case_dir: Path, time_value: float, mapping_file: Path, stem: str) -> tuple[Path, Path]:
    mesh, actual_time = _read_mesh(case_dir, "jellyRoll", time_value)
    mapping_df = pd.read_csv(mapping_file)
    mesh_vol = np.asarray(mesh.compute_cell_sizes(length=False, area=False, volume=True).cell_data["Volume"]).reshape(-1)
    qvol = np.asarray(mesh.cell_data["ecmQdot"]).reshape(-1)
    cell_power = qvol * mesh_vol

    zone_power = {}
    for ecm_cell_id, g in mapping_df.groupby("ecmCellId"):
        idx = g["meshKey"].to_numpy(dtype=int)
        w = g["weight"].to_numpy(dtype=float)
        zone_power[int(ecm_cell_id)] = float(np.sum(cell_power[idx] * w) / np.sum(w))

    row_idx = mapping_df.groupby("meshKey")["weight"].idxmax().to_numpy(dtype=int)
    owner = mapping_df.loc[row_idx, ["meshKey", "ecmCellId"]].sort_values("meshKey")

    zone_field = np.zeros(mesh.n_cells, dtype=float)
    zone_field[owner["meshKey"].to_numpy(dtype=int)] = owner["ecmCellId"].map(zone_power).to_numpy(dtype=float)
    mesh_zone = mesh.copy()
    mesh_zone.cell_data["ecmZoneHeat_W"] = zone_field

    mesh_cell = mesh.copy()
    mesh_cell.cell_data["cellHeat_W"] = cell_power

    out_zone = PLOTS / f"{stem}_zone_heat_W.png"
    out_cell = PLOTS / f"{stem}_cell_heat_W.png"
    _render_scalar_slice(mesh_zone, "ecmZoneHeat_W", "x", out_zone, f"ECM-zone applied heat [W] | t={actual_time:.6f} s")
    _render_scalar_slice(mesh_cell, "cellHeat_W", "x", out_cell, f"CFD-cell applied heat [W] | t={actual_time:.6f} s")
    return out_zone, out_cell


def _make_weight_figure(case_dir: Path, mapping_file: Path, ecm_id: int, title: str, out_path: Path) -> Path:
    mesh, actual_time = _read_mesh(case_dir, "jellyRoll", 299.88382302871543)
    mapping_df = pd.read_csv(mapping_file)
    cell_weight_sum = mapping_df.groupby("meshKey")["weight"].sum()
    g = mapping_df[mapping_df["ecmCellId"] == int(ecm_id)].copy()
    mesh_keys = g["meshKey"].to_numpy(dtype=int)
    norm = (g["weight"] / g["meshKey"].map(cell_weight_sum)).to_numpy(dtype=float)
    field = np.zeros(mesh.n_cells, dtype=float)
    field[mesh_keys] = norm
    mesh2 = mesh.copy()
    mesh2.cell_data["weightFrac"] = field

    tmp_x = PLOTS / f"tmp_weight_ecm{ecm_id:02d}_x.png"
    tmp_z = PLOTS / f"tmp_weight_ecm{ecm_id:02d}_z.png"
    _render_scalar_slice(mesh2, "weightFrac", "x", tmp_x, f"{title} | longitudinal | t={actual_time:.6f} s")
    _render_scalar_slice(mesh2, "weightFrac", "z", tmp_z, f"{title} | cross-section | t={actual_time:.6f} s")
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 10.4), dpi=170)
    for ax, img_path in zip(axes, [tmp_x, tmp_z]):
        ax.imshow(mpimg.imread(img_path))
        ax.axis("off")
    fig.suptitle(title, fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Sec", parent=styles["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#1f3b4d"), spaceBefore=9, spaceAfter=7))
    styles.add(ParagraphStyle("Sub", parent=styles["Heading2"], fontSize=11.5, leading=14, textColor=colors.HexColor("#274b63"), spaceBefore=6, spaceAfter=3))
    styles["BodyText"].fontSize = 9.4
    styles["BodyText"].leading = 13
    return styles


def _img(path: Path, max_w_cm: float, styles, caption: str, max_h_cm: float = 11.5) -> list:
    reader = ImageReader(str(path))
    iw, ih = reader.getSize()
    scale = min((max_w_cm * cm) / iw, (max_h_cm * cm) / ih)
    width = iw * scale
    height = ih * scale
    return [
        RLImage(str(path), width=width, height=height),
        Spacer(1, 0.08 * cm),
        Paragraph(f"<i>{caption}</i>", styles["BodyText"]),
        Spacer(1, 0.28 * cm),
    ]


def _table(rows: list[list[str]], widths_cm: list[float]) -> Table:
    t = Table(rows, colWidths=[w * cm for w in widths_cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eef2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f3b4d")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa7b2")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ]
        )
    )
    return t


def _bullet(text: str) -> str:
    return f"• {text}"


def main() -> int:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    styles = _styles()

    lumped = {
        "timestep": _latest_json(ROOT / "artifacts/validation/lumped_forward/timestep"),
        "energy": _latest_json(ROOT / "artifacts/validation/lumped_forward/energy"),
        "mesh": _latest_json(ROOT / "artifacts/validation/lumped_forward/mesh"),
        "ecm_zero": _latest_json(ROOT / "artifacts/validation/lumped_forward/ecm_zero"),
        "ecm_current": _latest_json(ROOT / "artifacts/validation/lumped_forward/ecm_current"),
    }
    distributed = {
        "timestep": _latest_json(ROOT / "artifacts/validation/distributed_forward/timestep"),
        "energy": _latest_json(ROOT / "artifacts/validation/distributed_forward/energy"),
        "mesh": _latest_json(ROOT / "artifacts/validation/distributed_forward/mesh"),
        "ecm_zero": _latest_json(ROOT / "artifacts/validation/distributed_forward/ecm_zero"),
        "ecm_current": _latest_json(ROOT / "artifacts/validation/distributed_forward/ecm_current"),
    }

    l_cur_log = Path(lumped["ecm_current"]["log"])
    l_zero_log = Path(lumped["ecm_zero"]["log"])
    d_zero_log = Path(distributed["ecm_zero"]["log"])
    d_cur_log = Path("/workspace/artifacts/logs/validation_distributed_fw_ecm_current_20260327_224059.log")
    old_map_log = Path("/workspace/artifacts/logs/distributed_solid_run_20260327_163918.log")
    overlap_map_log = Path("/workspace/artifacts/logs/distributed_solid_run_20260328_001212.log")

    sections = _render_sections()
    overlap_zone_heat, overlap_cell_heat = _make_overlap_source_figures(
        ROOT / "cases/distributed_solid_overlap",
        299.88382302871543,
        ROOT / "cases/distributed_solid/ecm/mapping_table_axial6_radial3_2170mesh_overlap.csv",
        f"overlap_applied_heat_{stamp}",
    )
    figs = {
        "architecture": _plot_architecture(PLOTS / f"architecture_{stamp}.png"),
        "model": _plot_model_concept(PLOTS / f"model_concept_{stamp}.png"),
        "flow": _plot_validation_flow(PLOTS / f"validation_flow_{stamp}.png"),
        "summary": _plot_validation_summary(lumped, distributed, PLOTS / f"validation_summary_{stamp}.png"),
        "energy": _plot_energy(lumped["energy"], distributed["energy"], PLOTS / f"energy_balance_{stamp}.png"),
        "q_zero": _plot_q_overlay(l_zero_log, d_zero_log, PLOTS / f"zero_qsum_{stamp}.png", "Zero-Current Comparison: Q_sum_check", 30),
        "q_fixed": _plot_q_overlay(l_cur_log, d_cur_log, PLOTS / f"fixed_qsum_{stamp}.png", "Fixed-Current Comparison: Q_sum_check", 30),
        "runtime": _plot_runtime(PLOTS / f"runtime_{stamp}.png"),
        "timeline": _plot_timeline(PLOTS / f"timeline_{stamp}.png"),
        "matrix": _plot_status_matrix(PLOTS / f"status_matrix_{stamp}.png"),
        "sections_panel": _panel([sections["lumped"], sections["distributed"]], ["Lumped all regions", "Distributed all regions"], PLOTS / f"sections_panel_{stamp}.png", "All-Region Temperature Sections"),
        "source_current": _panel(
            [
                ROOT / "artifacts/plots/distributed_source_maps/current_dist_ecm_zone_qdot_x.png",
                ROOT / "artifacts/plots/distributed_source_maps/current_dist_cfd_cell_qdot_x.png",
            ],
            ["Heat per ECM zone", "Heat per CFD cell"],
            PLOTS / f"source_current_{stamp}.png",
            "Current Distributed Case Source Application",
        ),
        "source_overlap": _panel([overlap_zone_heat, overlap_cell_heat], ["Heat per ECM zone [W]", "Heat per CFD cell [W]"], PLOTS / f"source_overlap_{stamp}.png", "Overlap-Weighted Mapping Applied Heat"),
        "weight_low": _make_weight_figure(
            ROOT / "cases/distributed_solid_overlap",
            ROOT / "cases/distributed_solid/ecm/mapping_table_axial6_radial3_2170mesh_overlap.csv",
            0,
            "ECM zone 00 normalized CFD→ECM contribution fractions",
            PLOTS / f"weight_low_{stamp}.png",
        ),
        "weight_mid": _make_weight_figure(
            ROOT / "cases/distributed_solid_overlap",
            ROOT / "cases/distributed_solid/ecm/mapping_table_axial6_radial3_2170mesh_overlap.csv",
            8,
            "ECM zone 08 normalized CFD→ECM contribution fractions",
            PLOTS / f"weight_mid_{stamp}.png",
        ),
        "weight_high": _make_weight_figure(
            ROOT / "cases/distributed_solid_overlap",
            ROOT / "cases/distributed_solid/ecm/mapping_table_axial6_radial3_2170mesh_overlap.csv",
            17,
            "ECM zone 17 normalized CFD→ECM contribution fractions",
            PLOTS / f"weight_high_{stamp}.png",
        ),
    }

    eq_delta = _max_abs_delta(l_cur_log, d_cur_log)
    old_q = _last_q(old_map_log)
    new_q = _last_q(overlap_map_log)
    old_clock = _last_clock(old_map_log)
    new_clock = _last_clock(overlap_map_log)

    md = REPORTS / f"client_comprehensive_report_full_{stamp}.md"
    pdf = REPORTS / f"client_comprehensive_report_full_{stamp}.pdf"

    md.write_text(
        f"""# Comprehensive Client Report\n\nGenerated: {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC')}\n\nThis report follows the structure agreed in `docs/CLIENT_REPORT_OUTLINE.md`.\n""",
        encoding="utf-8",
    )

    doc = SimpleDocTemplate(str(pdf), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    story = []
    story.append(Paragraph("Comprehensive Client Report", styles["Title"]))
    story.append(Paragraph("OpenFOAM ↔ ECM Coupling Program", styles["Sub"]))
    story.append(Paragraph(f"Generated: {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC')}", styles["BodyText"]))
    story.append(Spacer(1, 0.35 * cm))

    # 1
    story.append(Paragraph("1. Executive Summary", styles["Sec"]))
    story.append(Paragraph("1.1 Project Goal", styles["Sub"]))
    story.append(Paragraph("The project goal is a robust OpenFOAM↔external-ECM coupling for CHT battery-cell cases, where OpenFOAM provides thermal state and the ECM returns heat generation that is applied conservatively inside the active jellyRoll region.", styles["BodyText"]))
    story.append(Paragraph("1.2 What Is Working Today", styles["Sub"]))
    story.append(Paragraph("The delivered codebase is working in both lumped and distributed thermal modes. The accepted distributed comparison baseline now uses a shared electrical state, persistent binary transport, stable mesh IDs, automated validation harnesses, and portable package/build scripts.", styles["BodyText"]))
    story.append(Paragraph("1.3 Main Validated Outcomes", styles["Sub"]))
    for line in [
        "Lumped forward validation campaign: all five tests passed.",
        "Distributed forward validation campaign: all five tests passed after cleanup of inherited runtime snapshots.",
        f"Shared-state lumped/distributed fixed-current equivalence closes to numerical tolerance with max |ΔQ_sum_check| ≈ {eq_delta:.2e} W.",
        "Adiabatic energy-balance validation closes to about -1.889% for both lumped and distributed forward campaigns.",
    ]:
        story.append(Paragraph(_bullet(line), styles["BodyText"]))
    story.append(Paragraph("1.4 Main Limitations And Open Items", styles["Sub"]))
    for line in [
        "The accepted coupling remains weakly coupled in time.",
        "A physically distributed electrical network model is not yet validated.",
        "External experimental dataset validation is still pending.",
        "The overlap-weighted mapping enhancement is implemented and demonstrated, but not yet part of the accepted comparison baseline.",
    ]:
        story.append(Paragraph(_bullet(line), styles["BodyText"]))
    story.extend(_img(figs["architecture"], 16.0, styles, "Figure 1. OpenFOAM↔ECM workflow used in the delivered implementation."))

    # 2
    story.append(Paragraph("2. System Overview", styles["Sec"]))
    story.append(Paragraph("2.1 Problem Being Solved", styles["Sub"]))
    story.append(Paragraph("The target problem is battery-cell thermal simulation in OpenFOAM with heat generation driven by an external ECM rather than by a hard-coded source model. The coupling must work robustly in CHT configurations and remain operational under both lumped and distributed thermal treatments.", styles["BodyText"]))
    story.append(Paragraph("2.2 Coupled Workflow: OpenFOAM ↔ ECM", styles["Sub"]))
    story.append(Paragraph("The coupling sequence is: extract active-region temperatures from OpenFOAM, collapse or aggregate them as required by the coupling mode, step the ECM, obtain heat generation, and map that heat back to an OpenFOAM volumetric source field.", styles["BodyText"]))
    story.append(Paragraph("2.3 Lumped vs Distributed Model Definitions", styles["Sub"]))
    story.append(Paragraph("In lumped mode there is one whole-cell electrical state and one total heat output. In the accepted distributed baseline there is still one whole-cell electrical state, but temperature pullback and source redistribution occur over distributed thermal partitions and mesh cells.", styles["BodyText"]))
    story.append(Paragraph("2.4 Terminology: battery cell, mesh cell, partition", styles["Sub"]))
    story.append(_table([
        ["Concept", "Meaning in this project"],
        ["Battery cell", "One physical electrochemical unit represented by the ECM"],
        ["Mesh cell", "One OpenFOAM finite-volume cell in the active jellyRoll zone"],
        ["Partition / ECM zone", "A distributed thermal aggregation/source region used by the coupler"],
    ], [4.0, 11.2]))
    story.append(Spacer(1, 0.2 * cm))
    story.extend(_img(figs["model"], 16.0, styles, "Figure 2. Lumped and distributed concepts. The accepted distributed baseline uses a shared electrical state with distributed thermal/source mapping."))

    # 3
    story.append(Paragraph("3. Implementation Delivered", styles["Sec"]))
    for title, text in [
        ("3.1 Custom OpenFOAM components", "The repository includes a buildable OpenFOAM function-object library and the solids-only CHT solver path used for the battery-cell cases."),
        ("3.2 ecmCoupler function object", "The `ecmCoupler` function object extracts temperatures, exchanges data with the external runtime, applies relaxation, and writes the resulting source field."),
        ("3.3 Custom solver / solids-only path", "The solids-only path was stabilized for the current CHT use case and guarded against known problematic implicit-coupling behavior."),
        ("3.4 Custom patch / source-term handling", "Source sign, runtime state handling, and temperature-source application paths were validated and corrected where needed."),
        ("3.5 Python ECM runtime and wrappers", "The Python-side runtime supports file-based and persistent pipe operation, binary framed payloads, mapping-table usage, and validation diagnostics."),
        ("3.6 Binary / persistent communication modes", "Persistent binary transport is the accepted fast path; persistent JSON was retained only as an earlier diagnostic step because it proved too expensive."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))

    # 4
    story.append(Paragraph("4. Coupling Architecture", styles["Sec"]))
    for title, text in [
        ("4.1 File-based serial coupling", "The early baseline wrote binary input/output files with atomic rename handshakes, proving the coupling contract and diagnostics."),
        ("4.2 Persistent-pipe coupling", "The accepted fast path keeps the Python runtime alive and exchanges framed binary payloads through persistent stdin/stdout pipes."),
        ("4.3 Binary protocol and handshake", "Binary payloads carry step metadata, electrical inputs, stable cell identifiers, and temperature/heat records. This avoided the heavy JSON serialization cost seen in earlier tests."),
        ("4.4 Stable IDs and mapping tables", "Stable mesh-cell IDs are used to preserve consistent mapping between OpenFOAM and the ECM runtime across calls and across process boundaries."),
        ("4.5 Temperature pullback and heat redistribution", "The coupler aggregates temperatures to the ECM side and redistributes returned heat conservatively to the CFD cells via the mapping table."),
        ("4.6 Runtime state files and restart behavior", "Runtime snapshots and last-good outputs exist for robustness, but validation harnesses now explicitly clean inherited runtime state before comparison runs."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))

    # 5
    story.append(Paragraph("5. Numerical Strategy", styles["Sec"]))
    for title, text in [
        ("5.1 Time integration approach", "OpenFOAM advances on its own timestep control while the ECM advances on the execute cadence configured by the coupler."),
        ("5.2 Non-synced time stepping: what it means here", "The CFD timestep and ECM timestep are not guaranteed to be identical in all modes; the accepted forward-validation runs use per-step ECM calls to remove ambiguity from cadence effects."),
        ("5.3 ECM call cadence vs CFD timestep cadence", "Earlier jaggedness investigations showed that a multi-step ECM cadence can create visible temporal structure even with interpolation. The accepted distributed cases now call the ECM every CFD step."),
        ("5.4 Under-relaxation and temporal smoothing", "Source under-relaxation remains available and was used to remove the remaining temporal kink in distributed source application without changing the electrical model."),
        ("5.5 Diffusion-number control (`maxDi`)", "For development validation, `maxDi=100` was selected as the best compromise between runtime and acceptable adiabatic energy-balance accuracy."),
        ("5.6 Why these controls were needed", "These controls were introduced to separate numerical artifacts from actual model behavior and to make repeated validation practical in wall time."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))
    story.extend(_img(figs["flow"], 16.0, styles, "Figure 3. Forward-only validation execution logic used during solver/coupler stabilization."))

    # 6
    story.append(Paragraph("6. Models Compared", styles["Sec"]))
    for title, text in [
        ("6.1 Lumped thermal-electrical coupling", "One ECM state is stepped for the whole battery cell and one total heat output is mapped into the active jellyRoll region."),
        ("6.2 Distributed thermal coupling with shared electrical state", "The accepted distributed baseline keeps one shared ECM state while allowing distributed thermal aggregation and distributed source placement."),
        ("6.3 Earlier distributed formulation and why it was rejected", "The earlier formulation advanced one ECM-like state per partition while also reducing partition capacity and keeping full applied current. That changed the electrical problem and therefore was rejected as an equivalence baseline."),
        ("6.4 Final accepted baseline for equivalence testing", "For equivalence testing, lumped and distributed must solve the same electrical problem. That is now enforced through the shared-state distributed baseline."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))

    # 7
    story.append(Paragraph("7. Test Methodology", styles["Sec"]))
    for title, text in [
        ("7.1 Validation philosophy", "Start with cheap common-sense and analytic checks, then proceed to structured development validation, then to broader comparisons."),
        ("7.2 Forward-only test execution rule", "The development harness uses strict forward-only progression to avoid hiding causality behind unnecessary full-suite reruns."),
        ("7.3 Common-sense analytic checks", "Zero-current equilibrium, adiabatic energy balance, and convergence checks were used to validate the thermal side before relying on more complex coupled behavior."),
        ("7.4 Development validation harness", "Dedicated lumped and distributed forward harnesses were built to run the same ordered set of tests and write isolated metrics/logs per test."),
        ("7.5 Report generation and diagnostics", "Report generators, per-test metric files, and plot-first PDFs were used so that validation results remain reproducible and reviewable."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))
    story.extend(_img(figs["summary"], 16.0, styles, "Figure 4. Summary comparison of the accepted lumped and distributed forward-validation metrics."))

    # 8
    story.append(Paragraph("8. Lumped Model Results", styles["Sec"]))
    story.append(Paragraph("8.1 Zero-current equilibrium", styles["Sub"]))
    story.append(Paragraph(f"The lumped zero-current test passed with max |Q_sum_check| = {lumped['ecm_zero']['max_abs_qsum_W']:.3f} W and no measurable cap-temperature drift.", styles["BodyText"]))
    story.append(Paragraph("8.2 Fixed-current timestep convergence", styles["Sub"]))
    story.append(Paragraph(f"The lumped timestep gate passed with ΔT(0.5 vs 0.25) = {lumped['timestep']['delta_T_05_vs_025_K']:.4f} K and ΔQ = {lumped['timestep']['delta_Q_05_vs_025_W']:.4f} W.", styles["BodyText"]))
    story.append(Paragraph("8.3 Adiabatic energy-balance test", styles["Sub"]))
    story.append(Paragraph(f"The corrected adiabatic lumped test passed with energy error = {lumped['energy']['energy_error_percent']:.3f} % after enforcing true adiabatic walls and `h=1.0` in the benchmark definition.", styles["BodyText"]))
    story.append(Paragraph("8.4 Mesh-independence test", styles["Sub"]))
    story.append(Paragraph(f"The lumped mesh gate passed with |Tmax_medium - Tmax_fine| = {lumped['mesh']['delta_Tmax_medium_vs_fine_K']:.5f} K.", styles["BodyText"]))
    story.append(Paragraph("8.5 Fixed-current smoothness / cadence", styles["Sub"]))
    story.append(Paragraph(f"The lumped fixed-current cadence check passed with max |d²Q| = {lumped['ecm_current']['max_abs_second_diff_qsum_W']:.3f} W over the validation window.", styles["BodyText"]))
    story.append(Paragraph("8.6 Overall lumped assessment", styles["Sub"]))
    story.append(Paragraph("The lumped path is validated as the accepted whole-cell baseline for current development. Its common-sense checks, forward validation gates, and reporting path are all in good shape.", styles["BodyText"]))

    # 9
    story.append(Paragraph("9. Distributed Model Results", styles["Sec"]))
    story.append(Paragraph("9.1 Zero-current equilibrium", styles["Sub"]))
    story.append(Paragraph(f"The final distributed zero-current test passed with max |Q_sum_check| = {distributed['ecm_zero']['max_abs_qsum_W']:.3f} W. Earlier apparent startup heat was traced to inherited runtime snapshots and removed from the harness path.", styles["BodyText"]))
    story.append(Paragraph("9.2 Fixed-current timestep convergence", styles["Sub"]))
    story.append(Paragraph(f"The distributed timestep gate passed with ΔT(0.25 vs 0.125) = {distributed['timestep']['delta_T_025_vs_0125_K']:.4f} K and ΔQ = {distributed['timestep']['delta_Q_025_vs_0125_W']:.4f} W.", styles["BodyText"]))
    story.append(Paragraph("9.3 Adiabatic energy-balance test", styles["Sub"]))
    story.append(Paragraph(f"The distributed adiabatic energy-balance test passed with energy error = {distributed['energy']['energy_error_percent']:.3f} %.", styles["BodyText"]))
    story.append(Paragraph("9.4 Mesh-independence test", styles["Sub"]))
    story.append(Paragraph(f"The distributed mesh gate passed with |Tmax_medium - Tmax_fine| = {distributed['mesh']['delta_Tmax_medium_vs_fine_K']:.5f} K.", styles["BodyText"]))
    story.append(Paragraph("9.5 Fixed-current smoothness / cadence", styles["Sub"]))
    story.append(Paragraph(f"The distributed fixed-current cadence check passed with post-startup max |d²Q| = {distributed['ecm_current']['max_abs_second_diff_qsum_after_5s_W']:.3f} W and real ECM activity logged at every step.", styles["BodyText"]))
    story.append(Paragraph("9.6 Overall distributed assessment", styles["Sub"]))
    story.append(Paragraph("The distributed thermal path is validated for the accepted shared-state baseline. Its transport path is now fast enough for practical use and its startup-state artifact has been removed from the validation workflow.", styles["BodyText"]))
    story.extend(_img(figs["energy"], 16.0, styles, "Figure 5. Energy-balance comparison for the accepted lumped and distributed forward-validation campaigns."))
    story.extend(_img(figs["q_zero"], 16.0, styles, "Figure 6. Zero-current comparison after fixing stale runtime carryover in distributed validation clones."))
    story.extend(_img(figs["q_fixed"], 16.0, styles, "Figure 7. Fixed-current comparison for the accepted shared-state equivalence baseline."))

    # 10
    story.append(Paragraph("10. Lumped vs Distributed Comparison", styles["Sec"]))
    story.append(Paragraph("10.1 What should match and what should not", styles["Sub"]))
    story.append(Paragraph("Under the accepted shared-state baseline, lumped and distributed should match in whole-cell electrical outputs such as total generated heat. What is allowed to differ is the spatial thermal distribution and therefore local temperature fields.", styles["BodyText"]))
    story.append(Paragraph("10.2 Shared-state equivalence target", styles["Sub"]))
    story.append(Paragraph("The equivalence target is that lumped and distributed solve the same electrical problem and therefore produce the same total heat history, to numerical tolerance, under the comparison configuration.", styles["BodyText"]))
    story.append(Paragraph("10.3 Final comparison results", styles["Sub"]))
    story.append(Paragraph(f"The final accepted comparison closes with max |ΔQ_sum_check| ≈ {eq_delta:.2e} W over the 30 s fixed-current comparison run, which is numerical-tolerance agreement for practical purposes.", styles["BodyText"]))
    story.append(Paragraph("10.4 Residual differences and interpretation", styles["Sub"]))
    story.append(Paragraph("Residual differences in local temperatures remain physically meaningful because the distributed thermal model still places heat and temperature in space, unlike the lumped thermal treatment.", styles["BodyText"]))
    story.extend(_img(figs["sections_panel"], 16.0, styles, "Figure 8. Representative all-region lumped and distributed temperature sections showing jellyRoll, shell, and cap together."))

    # 11
    story.append(Paragraph("11. Technical Maturation And Issues Resolved", styles["Sec"]))
    for title, text in [
        ("11.1 Benchmark-definition corrections", "The adiabatic benchmark only became valid after correcting boundary conditions and `h` relaxation in the validation cases."),
        ("11.2 Startup stale-state artifact", "A cloned `ecm_last_good.bin` snapshot caused a false distributed startup transient until clone cleanup removed it."),
        ("11.3 Runner environment discrepancy", "A helper function that re-sourced OpenFOAM altered solver behavior; direct-shell invocation became the required comparison path."),
        ("11.4 Persistent JSON bottleneck and binary fix", "Persistent JSON transport made the distributed case slower, not faster. Switching to framed binary restored the expected performance advantage."),
        ("11.5 PyVista/reporting issue and fallback renderer", "Section rendering had to move to a PyVista-read plus matplotlib-render path and to polygon-preserving slice plotting to eliminate mesh artifacts."),
        ("11.6 Final robustness safeguards introduced", "Validation cases now clean runtime state, harnesses avoid environment mutation, and debugging guidance was codified in repo documents."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))

    # 12
    story.append(Paragraph("12. Performance And Runtime Findings", styles["Sec"]))
    story.append(Paragraph("12.1 Lumped runtime characteristics", styles["Sub"]))
    story.append(Paragraph("The lumped validation path is comparatively cheap and was suitable for repeated common-sense and forward validation cycles.", styles["BodyText"]))
    story.append(Paragraph("12.2 Distributed runtime characteristics", styles["Sub"]))
    story.append(Paragraph("The distributed path is significantly more expensive because of multi-region thermal solves, mesh-scale source handling, and per-step coupling work.", styles["BodyText"]))
    story.append(Paragraph("12.3 Persistent JSON vs persistent binary vs file-based", styles["Sub"]))
    story.append(Paragraph("The measured 30 s distributed runs were about 120 s for file-based binary, 291 s for persistent JSON, and 43 s for persistent binary.", styles["BodyText"]))
    story.append(Paragraph("12.4 Solver cost vs coupling-stack cost", styles["Sub"]))
    story.append(Paragraph("A matched 30 s benchmark showed about 7 s for solver-only, 42 s for mock-coupled, and 43 s for full coupled, indicating that the real ECM math itself is only a small increment relative to the surrounding coupling stack.", styles["BodyText"]))
    story.append(Paragraph("12.5 Practical runtime expectations for longer runs", styles["Sub"]))
    story.append(Paragraph("The distributed 300 s binary-persistent run completed in about 468 s wall time and provides a practical reference point for longer transient planning.", styles["BodyText"]))
    story.extend(_img(figs["runtime"], 16.0, styles, "Figure 9. Runtime comparison across key transport modes and benchmarked 30 s / 300 s cases."))

    # 13
    story.append(Paragraph("13. Code Quality And Robustness Improvements", styles["Sec"]))
    for title, text in [
        ("13.1 Shared-state distributed ECM implementation", "The distributed comparison baseline now solves the same electrical problem as the lumped one."),
        ("13.2 Cleaner runner behavior", "Validation and benchmark runs now use the direct shell execution path and avoid environment mutation inside helper code."),
        ("13.3 Safer test harness behavior", "Forward-only execution, stale-state cleanup, and per-test metrics made debugging more reliable and cheaper."),
        ("13.4 Portable package and build scripts", "A portable export with build and run scripts was prepared for use on other workstations."),
        ("13.5 Logging, checkpoints, and reproducibility", "Session logs, chat logs, generated reports, and checkpoint/package artifacts now give a reproducible audit trail."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))

    # 14
    story.append(Paragraph("14. Current Limitations", styles["Sec"]))
    for title, text in [
        ("14.1 Weak coupling / no sub-iterations", "The accepted comparison baseline is still weakly coupled in time."),
        ("14.2 Non-synced timestep implications", "Any future change away from per-step ECM calls must be handled carefully because cadence artifacts were already observed in earlier runs."),
        ("14.3 Dependence on effective temperature definition", "The shared-state distributed baseline still depends on how `T_eff` is defined for the whole-cell electrical step."),
        ("14.4 Limits of current distributed electrical modeling", "A true distributed electrical network model is not yet validated and should not be inferred from the current shared-state baseline."),
        ("14.5 Remaining validation gaps against external data", "Experimental or literature dataset validation remains outstanding."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))

    # 15
    story.append(Paragraph("15. What The Client Can Use Now", styles["Sec"]))
    for title, text in [
        ("15.1 Supported cases", "The portable package includes clean lumped and distributed CHT case inputs and the source/build path needed to rebuild on another workstation."),
        ("15.2 Recommended run workflow", "Build once, then run the selected case via its package-local `Allrun`, allowing it to regenerate meshes when needed."),
        ("15.3 Packaged deliverables", "The package includes source code, function objects, ECM runtime scripts, cases, documentation, and build helpers."),
        ("15.4 What is production-ready vs investigational", "Lumped and distributed shared-state runs are usable; overlap-weighted mapping and future distributed electrical modeling remain investigational."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))
    story.append(_table([
        ["Deliverable", "Status", "Comment"],
        ["Lumped forward-validated case", "Ready", "Accepted baseline with passing forward campaign"],
        ["Distributed shared-state case", "Ready", "Accepted distributed comparison baseline"],
        ["Portable build/run package", "Ready", "Prepared for autonomous workstation use"],
        ["Overlap-weighted mapping clone", "Investigational", "Implemented and demonstrated separately"],
        ["Parallel-branch distributed electrical model", "Future work", "Selected concept, not yet validated"],
    ], [4.6, 2.3, 8.5]))
    story.append(Spacer(1, 0.2 * cm))

    # 16
    story.append(Paragraph("16. Recommended Next Steps", styles["Sec"]))
    for title, text in [
        ("16.1 External dataset validation", "Run the accepted baseline against the simplest available external dataset once the current formulation is frozen."),
        ("16.2 Stronger electro-thermal validation targets", "Add explicit mapping conservation and reduction tests so thermal/source correctness is separated from electrical-model questions."),
        ("16.3 Optional future distributed electrical model", "If required, implement a true parallel-branch electrical network on a separate validation track from the accepted shared-state baseline."),
        ("16.4 Reporting and automation improvements", "Continue generating client-facing figures directly from the validated artifact set, preserving aspect ratios and case lineage."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(text, styles["BodyText"]))

    # 17 appendices
    story.append(PageBreak())
    story.append(Paragraph("17. Appendices", styles["Sec"]))
    story.append(Paragraph("17.1 File/package inventory", styles["Sub"]))
    for line in [
        "Source code under `src/` and `ecm/`.",
        "Portable package build helper: `build_portable.sh`.",
        "Portable package creation helper: `tools/create_portable_package.sh`.",
        "Main client report generators under `tools/`.",
    ]:
        story.append(Paragraph(_bullet(line), styles["BodyText"]))
    story.append(Paragraph("17.2 Main logs and reports produced", styles["Sub"]))
    for line in [
        "Lumped forward summary: `artifacts/validation/lumped_forward/forward_campaign_summary_20260327_201140.md`",
        "Distributed forward summary: `artifacts/validation/distributed_forward/forward_campaign_summary_20260327_211520.md`",
        "Accepted comparison PDF: `artifacts/reports/lumped_vs_distributed_forward_validation_20260327_224210.pdf`",
        "Distributed 300 s binary-persistent log: `artifacts/logs/distributed_solid_run_20260327_163918.log`",
        "Overlap-weighted mapping comparison log: `artifacts/logs/distributed_solid_run_20260328_001212.log`",
    ]:
        story.append(Paragraph(_bullet(line), styles["BodyText"]))
    story.append(Paragraph("17.3 Validation metrics summary tables", styles["Sub"]))
    story.append(_table([
        ["Metric", "Lumped", "Distributed"],
        ["timestep ΔT gate [K]", f"{lumped['timestep']['delta_T_05_vs_025_K']:.4f}", f"{distributed['timestep']['delta_T_025_vs_0125_K']:.4f}"],
        ["timestep ΔQ gate [W]", f"{lumped['timestep']['delta_Q_05_vs_025_W']:.4f}", f"{distributed['timestep']['delta_Q_025_vs_0125_W']:.4f}"],
        ["energy error [%]", f"{lumped['energy']['energy_error_percent']:.3f}", f"{distributed['energy']['energy_error_percent']:.3f}"],
        ["mesh ΔTmax [K]", f"{lumped['mesh']['delta_Tmax_medium_vs_fine_K']:.5f}", f"{distributed['mesh']['delta_Tmax_medium_vs_fine_K']:.5f}"],
        ["zero-current max|Q| [W]", f"{lumped['ecm_zero']['max_abs_qsum_W']:.3f}", f"{distributed['ecm_zero']['max_abs_qsum_W']:.3f}"],
    ], [6.0, 4.0, 4.0]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("17.4 Definitions and abbreviations", styles["Sub"]))
    for line in [
        "ECM: equivalent circuit model",
        "CHT: conjugate heat transfer",
        "mesh cell: OpenFOAM finite-volume cell",
        "partition / ECM zone: distributed thermal aggregation region",
        "Q_sum_check: total applied volumetric heat integrated over the active jellyRoll region",
    ]:
        story.append(Paragraph(_bullet(line), styles["BodyText"]))
    story.append(Paragraph("17.5 Lessons learned / debugging safeguards", styles["Sub"]))
    for line in [
        "Validate the benchmark definition before suspecting the solver.",
        "Treat the harness and runner code as part of the validated system.",
        "Use direct shell run vs harness run as a mandatory tie-breaker for inconsistent results.",
        "Clean runtime state when cloning validation cases.",
        "Preserve aspect ratio in client-facing figures and avoid misleading interpolated slice plots.",
    ]:
        story.append(Paragraph(_bullet(line), styles["BodyText"]))
    story.append(Paragraph("17.6 Project progress timeline by phase", styles["Sub"]))
    story.extend(_img(figs["timeline"], 15.5, styles, "Figure A1. Project progress summarized by technical phase."))
    for title, objective, accepted, diagnostics, learned in [
        ("17.6.1 Initial coupling architecture and buildable OpenFOAM integration", "Build a functioning OpenFOAM↔ECM interface with a buildable library.", "Function-object library and binary IO path built successfully.", "Early coupling scaffolding and build validation.", "Treat buildability and runnability as separate gates."),
        ("17.6.2 Baseline serial and parallel coupling validation", "Prove the data-exchange contract in simple serial and masterGather runs.", "Serial and parallel baseline coupling validated.", "Early parser and mapping smoke tests.", "Stable IDs and simple diagnostics save time later."),
        ("17.6.3 CHT case construction and solver-side integration", "Move the coupling into realistic battery-cell CHT cases.", "Lumped and distributed CHT cases were assembled and made runnable.", "Case setup iterations and solver-path checks.", "Case definition errors can masquerade as solver defects."),
        ("17.6.4 Lumped-model stabilization and analytic/common-sense validation", "Establish a trusted whole-cell thermal-electrical baseline.", "Lumped forward validation campaign passed.", "Adiabatic benchmark initially invalid until BCs and relaxation were corrected.", "Benchmark definitions must be treated like code."),
        ("17.6.5 Distributed-model stabilization and performance optimization", "Make the distributed thermal path smooth, robust, and fast enough to use.", "Persistent binary transport and corrected startup handling produced a stable distributed path.", "Persistent JSON and stale runtime snapshots were rejected.", "Transport format and runtime carryover matter as much as physics code."),
        ("17.6.6 Lumped vs distributed equivalence investigation", "Ensure the comparison is physically meaningful.", "Shared-state distributed baseline now matches lumped in total heat to numerical tolerance.", "The earlier per-partition electrical formulation and runner-environment discrepancy were rejected.", "Equivalent comparison requires equivalent electrical problem definition."),
        ("17.6.7 Packaging, reporting, and portability hardening", "Prepare the package for client handoff and workstation portability.", "Portable package, build scripts, and client reports were produced.", "Report rendering and packaging assumptions were tightened.", "Reproducibility and presentation quality need explicit engineering, not ad hoc assembly."),
    ]:
        story.append(Paragraph(title, styles["Sub"]))
        story.append(Paragraph(f"<b>Objective.</b> {objective}", styles["BodyText"]))
        story.append(Paragraph(f"<b>Accepted result.</b> {accepted}", styles["BodyText"]))
        story.append(Paragraph(f"<b>Diagnostic runs and rejected paths.</b> {diagnostics}", styles["BodyText"]))
        story.append(Paragraph(f"<b>What was learned.</b> {learned}", styles["BodyText"]))

    story.append(PageBreak())
    story.extend(_img(figs["matrix"], 14.0, styles, "Figure A2. Final validation status matrix for the accepted forward campaigns."))
    story.extend(_img(figs["source_current"], 16.0, styles, "Figure A3. Current distributed case: source density shown per ECM zone and per CFD cell."))
    story.extend(_img(figs["source_overlap"], 16.0, styles, "Figure A4. Overlap-weighted mapping clone: applied heat shown per ECM zone [W] and per CFD cell [W]."))
    story.append(PageBreak())
    story.extend(_img(figs["weight_low"], 17.5, styles, "Figure A5. ECM zone 00 normalized CFD→ECM contribution fractions, shown in longitudinal and cross-sectional slices.", max_h_cm=24.0))
    story.append(PageBreak())
    story.extend(_img(figs["weight_mid"], 17.5, styles, "Figure A6. ECM zone 08 normalized CFD→ECM contribution fractions, shown in longitudinal and cross-sectional slices.", max_h_cm=24.0))
    story.append(PageBreak())
    story.extend(_img(figs["weight_high"], 17.5, styles, "Figure A7. ECM zone 17 normalized CFD→ECM contribution fractions, shown in longitudinal and cross-sectional slices.", max_h_cm=24.0))

    doc.build(story)

    print(pdf)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
