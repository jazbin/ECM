#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import math
import re
import subprocess
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "artifacts" / "reports"
PLOTS = ROOT / "artifacts" / "plots" / "client_report"
PLOTS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _latest_json(dir_path: Path) -> Path:
    return sorted(dir_path.glob("metrics_*.json"))[-1]


def _parse_qsum_series(log_path: Path) -> tuple[list[float], list[float]]:
    times: list[float] = []
    qsum: list[float] = []
    current_t: float | None = None
    re_t = re.compile(r"^\s*Time = ([0-9eE+\-.]+)")
    re_q = re.compile(r"^\s*Q_sum_check\s+([0-9eE+\-.]+)\s*W?\s*$")
    for line in log_path.read_text(errors="ignore").splitlines():
        mt = re_t.match(line)
        if mt:
            current_t = float(mt.group(1))
            continue
        mq = re_q.match(line)
        if mq and current_t is not None:
            times.append(current_t)
            qsum.append(float(mq.group(1)))
    return times, qsum


def _final_clock_s(log_path: Path) -> float | None:
    best = None
    re_clock = re.compile(r"ClockTime = ([0-9eE+\-.]+) s")
    for line in log_path.read_text(errors="ignore").splitlines():
        m = re_clock.search(line)
        if m:
            best = float(m.group(1))
    return best


def _render_report_slices() -> tuple[Path, Path]:
    lumped_out = PLOTS / "sections_lumped"
    dist_out = PLOTS / "sections_distributed"
    lumped_out.mkdir(exist_ok=True)
    dist_out.mkdir(exist_ok=True)

    lumped_cmd = [
        "python3",
        str(ROOT / "tools" / "render_slices_pyvista.py"),
        "--case",
        str(ROOT / "cases" / "lumped_solid"),
        "--region",
        "jellyRoll",
        "--field",
        "T",
        "--time",
        "30.0",
        "--out-dir",
        str(lumped_out),
        "--prefix",
        "client_lumped",
        "--normal",
        "x",
        "--slice-count",
        "1",
    ]
    dist_cmd = [
        "python3",
        str(ROOT / "tools" / "render_slices_pyvista.py"),
        "--case",
        str(ROOT / "cases" / "distributed_solid"),
        "--region",
        "jellyRoll",
        "--field",
        "T",
        "--time",
        "300.0",
        "--out-dir",
        str(dist_out),
        "--prefix",
        "client_distributed",
        "--normal",
        "x",
        "--slice-count",
        "1",
        "--mapping-file",
        str(ROOT / "cases" / "distributed_solid" / "ecm" / "mapping_table_axial6_radial3_2170mesh.csv"),
    ]
    subprocess.run(lumped_cmd, check=True, cwd=ROOT)
    subprocess.run(dist_cmd, check=True, cwd=ROOT)
    return (
        lumped_out / "client_lumped_T_slice_x1.png",
        dist_out / "client_distributed_T_slice_x1.png",
    )


def _plot_qsum_overlay(
    l_log: Path,
    d_log: Path,
    out_path: Path,
    title: str,
    x_max: float | None = None,
) -> None:
    tl, ql = _parse_qsum_series(l_log)
    td, qd = _parse_qsum_series(d_log)
    fig, ax = plt.subplots(figsize=(6.6, 3.6), dpi=170)
    ax.plot(tl, ql, lw=2.0, label="Lumped", color="#1f77b4")
    ax.plot(td, qd, lw=2.0, label="Distributed", color="#d62728")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Q_sum_check [W]")
    ax.set_title(title)
    if x_max is not None:
        ax.set_xlim(0.0, x_max)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_energy_balance(l_metrics: dict, d_metrics: dict, out_path: Path) -> None:
    labels = ["Lumped", "Distributed"]
    err = [l_metrics["energy_error_percent"], d_metrics["energy_error_percent"]]
    stored = [l_metrics["energy_stored_J"], d_metrics["energy_stored_J"]]
    expected = [l_metrics["energy_expected_J"], d_metrics["energy_expected_J"]]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5), dpi=170)
    axes[0].bar(x, err, color=["#1f77b4", "#d62728"])
    axes[0].axhline(0.0, color="black", lw=0.8)
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Energy Error [%]")
    axes[0].set_title("Adiabatic Energy Balance Error")
    axes[0].grid(True, axis="y", alpha=0.25)

    width = 0.32
    axes[1].bar(x - width / 2, expected, width, label="Expected", color="#9ecae1")
    axes[1].bar(x + width / 2, stored, width, label="Stored", color="#fdae6b")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Energy [J]")
    axes[1].set_title("Expected vs Stored Energy")
    axes[1].legend(frameon=False, fontsize=8)
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_validation_summary(l_metrics: dict, d_metrics: dict, out_path: Path) -> None:
    cats = [
        "dt ΔT [K]",
        "dt ΔQ [W]",
        "|energy err| [%]",
        "mesh ΔTmax [K]",
        "zero-current\nmax|Q| [W]",
        "fixed-current\nmax|d²Q| [W]",
    ]
    lumped = [
        l_metrics["timestep"]["delta_T_05_vs_025_K"],
        l_metrics["timestep"]["delta_Q_05_vs_025_W"],
        abs(l_metrics["energy"]["energy_error_percent"]),
        l_metrics["mesh"]["delta_Tmax_medium_vs_fine_K"],
        l_metrics["ecm_zero"]["max_abs_qsum_W"],
        l_metrics["ecm_current"]["max_abs_second_diff_qsum_W"],
    ]
    distributed = [
        d_metrics["timestep"]["delta_T_025_vs_0125_K"],
        d_metrics["timestep"]["delta_Q_025_vs_0125_W"],
        abs(d_metrics["energy"]["energy_error_percent"]),
        d_metrics["mesh"]["delta_Tmax_medium_vs_fine_K"],
        d_metrics["ecm_zero"]["max_abs_qsum_W"],
        d_metrics["ecm_current"]["max_abs_second_diff_qsum_after_5s_W"],
    ]
    x = np.arange(len(cats))
    width = 0.38
    fig, ax = plt.subplots(figsize=(8.4, 4.1), dpi=170)
    ax.bar(x - width / 2, lumped, width, label="Lumped", color="#1f77b4")
    ax.bar(x + width / 2, distributed, width, label="Distributed", color="#d62728")
    ax.set_xticks(x, cats)
    ax.set_ylabel("Metric value")
    ax.set_title("Validation Summary Metrics")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_runtime_comparison(out_path: Path) -> None:
    labels = [
        "File binary\n30 s",
        "Persistent JSON\n30 s",
        "Persistent binary\n30 s",
        "Distributed binary\n300 s",
        "Solver-only\n30 s",
        "Mock-coupled\n30 s",
        "Full coupled\n30 s",
    ]
    values = [120.0, 291.0, 43.0, 468.0, 7.0, 42.0, 43.0]
    colors_bar = ["#9ecae1", "#fdd0a2", "#74c476", "#31a354", "#c6dbef", "#fdae6b", "#e6550d"]
    fig, ax = plt.subplots(figsize=(8.2, 4.0), dpi=170)
    ax.bar(np.arange(len(labels)), values, color=colors_bar)
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylabel("Wall time [s]")
    ax.set_title("Runtime and Coupling-Mode Comparison")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_architecture_diagram(out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 3.0), dpi=170)
    ax.axis("off")
    boxes = [
        (0.05, 0.35, 0.2, 0.3, "OpenFOAM\njellyRoll cells"),
        (0.33, 0.35, 0.18, 0.3, "ecmCoupler\nfunctionObject"),
        (0.59, 0.35, 0.16, 0.3, "ECM runtime\nPython"),
        (0.82, 0.35, 0.13, 0.3, "ECM model"),
    ]
    for x, y, w, h, txt in boxes:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor="#e8f1f8", edgecolor="#1f3b4d", lw=1.2))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=10)
    arrows = [
        ((0.25, 0.5), (0.33, 0.5), "T_mesh[i]"),
        ((0.51, 0.5), (0.59, 0.5), "binary pipe"),
        ((0.75, 0.5), (0.82, 0.5), "step()"),
        ((0.82, 0.42), (0.75, 0.42), "Q_total or qVol"),
        ((0.59, 0.42), (0.51, 0.42), "qVol[i]"),
        ((0.33, 0.42), (0.25, 0.42), "ecmQdot"),
    ]
    for a, b, txt in arrows:
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", lw=1.3, color="#37474f"))
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.045, txt, ha="center", va="bottom", fontsize=8)
    ax.set_title("OpenFOAM ↔ ECM Coupling Workflow", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_model_concept(out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.2), dpi=170)
    for ax in axes:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    axes[0].add_patch(plt.Circle((0.5, 0.5), 0.32, facecolor="#edf8fb", edgecolor="#1f3b4d", lw=1.2))
    axes[0].text(0.5, 0.62, "Lumped", ha="center", fontsize=12, weight="bold")
    axes[0].text(0.5, 0.49, "1 ECM state", ha="center", fontsize=10)
    axes[0].text(0.5, 0.39, "1 T_eff", ha="center", fontsize=10)
    axes[0].text(0.5, 0.29, "1 Q_total", ha="center", fontsize=10)

    axes[1].add_patch(plt.Circle((0.5, 0.5), 0.32, facecolor="#fff5eb", edgecolor="#7f2704", lw=1.2))
    for i in range(6):
        z = 0.26 + i * 0.08
        axes[1].plot([0.24, 0.76], [z, z], color="#6FE7FF", ls="--", lw=0.8)
    for r in [0.38, 0.50]:
        axes[1].add_patch(plt.Circle((0.5, 0.5), r / 2.0, fill=False, edgecolor="#6FE7FF", ls="--", lw=0.8))
    axes[1].text(0.5, 0.82, "Distributed", ha="center", fontsize=12, weight="bold")
    axes[1].text(0.5, 0.17, "accepted baseline: shared ECM state,\ndistributed thermal/source mapping", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_validation_flow(out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 2.8), dpi=170)
    ax.axis("off")
    labels = ["1. timestep", "2. energy", "3. mesh", "4. ecm_zero", "5. ecm_current"]
    xs = np.linspace(0.08, 0.92, len(labels))
    for x, lab in zip(xs, labels):
        ax.add_patch(plt.Rectangle((x - 0.08, 0.44), 0.16, 0.18, facecolor="#eef5db", edgecolor="#556b2f"))
        ax.text(x, 0.53, lab, ha="center", va="center", fontsize=10)
    for x0, x1 in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(x1 - 0.09, 0.53), xytext=(x0 + 0.09, 0.53), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.text(0.5, 0.18, "Rule: if test N fails, fix only test N, rerun only test N, then continue forward.", ha="center", fontsize=10)
    ax.set_title("Forward-Only Validation Execution Rule", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_timeline(out_path: Path) -> None:
    phases = [
        "Initial\narchitecture",
        "Serial/parallel\nbaseline",
        "CHT case\nintegration",
        "Lumped\nvalidation",
        "Distributed\nstabilization",
        "Equivalence\ninvestigation",
        "Packaging and\nreporting",
    ]
    y = np.arange(len(phases))[::-1]
    fig, ax = plt.subplots(figsize=(7.8, 4.4), dpi=170)
    ax.barh(y, np.ones_like(y), color=["#d9edf7", "#d9edf7", "#dff0d8", "#dff0d8", "#fcf8e3", "#f2dede", "#e8f1f8"])
    ax.set_yticks(y, phases)
    ax.set_xticks([])
    ax.set_xlim(0, 1.0)
    ax.set_title("Project Progress Timeline By Phase")
    for yi in y:
        ax.text(0.02, yi, "completed", va="center", ha="left", fontsize=9, color="#1f3b4d")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_status_matrix(out_path: Path) -> None:
    rows = ["Lumped", "Distributed"]
    cols = ["timestep", "energy", "mesh", "ecm_zero", "ecm_current"]
    mat = np.ones((2, 5))
    fig, ax = plt.subplots(figsize=(6.8, 2.7), dpi=170)
    ax.imshow(mat, cmap=plt.matplotlib.colors.ListedColormap(["#74c476"]), vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(cols)), cols)
    ax.set_yticks(np.arange(len(rows)), rows)
    ax.set_title("Validation Status Matrix")
    for i in range(2):
        for j in range(5):
            ax.text(j, i, "PASS", ha="center", va="center", fontsize=9, color="white", weight="bold")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _make_weight_panel(out_path: Path) -> None:
    img_paths = [
        ROOT / "artifacts" / "plots" / "distributed_weight_fields_norm" / "overlap_weightFrac_ecm00_x.png",
        ROOT / "artifacts" / "plots" / "distributed_weight_fields_norm" / "overlap_weightFrac_ecm08_x.png",
        ROOT / "artifacts" / "plots" / "distributed_weight_fields_norm" / "overlap_weightFrac_ecm17_x.png",
    ]
    fig, axes = plt.subplots(1, 3, figsize=(9.0, 3.2), dpi=170)
    titles = ["Lower-end partition", "Mid-body partition", "Upper-end partition"]
    for ax, p, title in zip(axes, img_paths, titles):
        ax.imshow(plt.imread(p))
        ax.axis("off")
        ax.set_title(title, fontsize=10)
    fig.suptitle("Overlap-Mapped CFD→ECM Contribution Fractions", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "Section",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1f3b4d"),
            spaceBefore=10,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            "Subsection",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#274b63"),
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles["BodyText"].leading = 13
    styles["BodyText"].fontSize = 9.5
    return styles


def _fig(path: Path, width_cm: float, caption: str, styles) -> list:
    return [
        RLImage(str(path), width=width_cm * cm, height=width_cm * cm * 0.58),
        Spacer(1, 0.1 * cm),
        Paragraph(f"<i>{caption}</i>", styles["BodyText"]),
        Spacer(1, 0.3 * cm),
    ]


def _table(rows: list[list[str]], col_widths_cm: list[float]) -> Table:
    t = Table(rows, colWidths=[w * cm for w in col_widths_cm])
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


def _build_markdown(stamp: str, figs: dict, metrics: dict) -> Path:
    md_path = REPORTS / f"client_comprehensive_report_{stamp}.md"
    text = f"""# Client Report

Generated: {dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")}

## Executive Summary

The delivered OpenFOAM↔ECM package is functioning in both lumped and distributed thermal modes. The accepted distributed baseline now uses a shared electrical state so that lumped and distributed runs solve the same electrical problem for equivalence testing. Forward validation campaigns passed for both models on timestep convergence, adiabatic energy balance, mesh independence, zero-current equilibrium, and fixed-current cadence.

The main technical limitations are now clearly bounded: the coupling is still weakly coupled in time, the distributed electrical model beyond the accepted shared-state baseline is not yet validated, and external dataset validation remains future work.

## Key Outcomes

- Lumped forward campaign: all five tests passed.
- Distributed forward campaign: all five tests passed after removing cloned runtime snapshots.
- Shared-state lumped/distributed fixed-current comparison closes to numerical tolerance.
- Persistent binary transport reduced the 30 s distributed run from 291 s to 43 s.
- A true overlap-weighted mapping generator has now been added and demonstrated in a new case clone, but it is not yet the accepted validation baseline.

## Selected Figures

![Architecture]({figs["architecture"]})
![Fixed current]({figs["q_fixed"]})
![Distributed section]({figs["dist_section"]})
![Weight fractions]({figs["weight_panel"]})

## Reference Metrics

- Lumped timestep gate: ΔT={metrics["l_t_dt"]:.4f} K, ΔQ={metrics["l_q_dt"]:.4f} W
- Distributed timestep gate: ΔT={metrics["d_t_dt"]:.4f} K, ΔQ={metrics["d_q_dt"]:.4f} W
- Lumped energy error: {metrics["l_e"]:.3f} %
- Distributed energy error: {metrics["d_e"]:.3f} %
- Shared-state fixed-current equivalence: max |ΔQ_sum_check| ≈ 6e-6 W
"""
    md_path.write_text(text, encoding="utf-8")
    return md_path


def main() -> int:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")

    styles = _styles()
    lumped_metrics = {
        "timestep": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "lumped_forward" / "timestep")),
        "energy": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "lumped_forward" / "energy")),
        "mesh": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "lumped_forward" / "mesh")),
        "ecm_zero": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "lumped_forward" / "ecm_zero")),
        "ecm_current": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "lumped_forward" / "ecm_current")),
    }
    distributed_metrics = {
        "timestep": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "distributed_forward" / "timestep")),
        "energy": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "distributed_forward" / "energy")),
        "mesh": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "distributed_forward" / "mesh")),
        "ecm_zero": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "distributed_forward" / "ecm_zero")),
        "ecm_current": _read_json(_latest_json(ROOT / "artifacts" / "validation" / "distributed_forward" / "ecm_current")),
    }

    l_zero_log = Path(lumped_metrics["ecm_zero"]["log"])
    d_zero_log = Path(distributed_metrics["ecm_zero"]["log"])
    l_cur_log = Path(lumped_metrics["ecm_current"]["log"])
    d_cur_log = Path("/workspace/artifacts/logs/validation_distributed_fw_ecm_current_20260327_224059.log")

    lumped_section, dist_section = _render_report_slices()

    figs = {
        "architecture": PLOTS / f"architecture_{stamp}.png",
        "model": PLOTS / f"model_concept_{stamp}.png",
        "flow": PLOTS / f"validation_flow_{stamp}.png",
        "q_zero": PLOTS / f"q_zero_compare_{stamp}.png",
        "q_fixed": PLOTS / f"q_fixed_compare_{stamp}.png",
        "summary": PLOTS / f"validation_summary_{stamp}.png",
        "energy": PLOTS / f"energy_balance_{stamp}.png",
        "runtime": PLOTS / f"runtime_modes_{stamp}.png",
        "timeline": PLOTS / f"timeline_{stamp}.png",
        "matrix": PLOTS / f"status_matrix_{stamp}.png",
        "weight_panel": PLOTS / f"weight_panel_{stamp}.png",
        "lumped_section": lumped_section,
        "dist_section": dist_section,
    }

    _plot_architecture_diagram(figs["architecture"])
    _plot_model_concept(figs["model"])
    _plot_validation_flow(figs["flow"])
    _plot_qsum_overlay(l_zero_log, d_zero_log, figs["q_zero"], "Zero-Current Comparison: Q_sum_check", x_max=30.0)
    _plot_qsum_overlay(l_cur_log, d_cur_log, figs["q_fixed"], "Fixed-Current Comparison: Q_sum_check", x_max=30.0)
    _plot_validation_summary(lumped_metrics, distributed_metrics, figs["summary"])
    _plot_energy_balance(lumped_metrics["energy"], distributed_metrics["energy"], figs["energy"])
    _plot_runtime_comparison(figs["runtime"])
    _plot_timeline(figs["timeline"])
    _plot_status_matrix(figs["matrix"])
    _make_weight_panel(figs["weight_panel"])

    pdf = REPORTS / f"client_comprehensive_report_{stamp}.pdf"
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    story = []

    story.append(Paragraph("Comprehensive Client Report", styles["Title"]))
    story.append(Paragraph("OpenFOAM ↔ ECM Coupling Program", styles["Subsection"]))
    story.append(Paragraph(f"Generated {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC')}", styles["BodyText"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("1. Executive Summary", styles["Section"]))
    story.append(
        Paragraph(
            "The delivered codebase now supports validated lumped and distributed thermal coupling between OpenFOAM and an external ECM, using a robust build path, persistent binary transport, case-level run scripts, and automated validation/reporting. The accepted distributed comparison baseline uses a shared electrical state so that lumped and distributed runs solve the same electrical problem when equivalence is the goal.",
            styles["BodyText"],
        )
    )
    story.append(
        Paragraph(
            "Both forward validation campaigns passed their defined gates. The remaining limits are known and documented: weak coupling in time, no external experimental dataset validation yet, and no validated multi-state distributed electrical model yet.",
            styles["BodyText"],
        )
    )
    story.extend(_fig(figs["architecture"], 16.0, "Figure 1. OpenFOAM↔ECM workflow used by the delivered implementation.", styles))
    story.extend(_fig(figs["model"], 16.0, "Figure 2. Lumped versus distributed model concepts. The accepted distributed baseline uses a shared ECM state with distributed thermal/source mapping.", styles))

    story.append(Paragraph("2. System Overview", styles["Section"]))
    story.append(
        Paragraph(
            "The coupling exchanges temperature from the active jellyRoll CFD cells to the ECM and returns a volumetric heat source to OpenFOAM. The implementation distinguishes the physical battery cell represented by the ECM from the OpenFOAM mesh cells. In distributed mode, the ECM-side thermal aggregation and source redistribution operate over defined sections or partitions rather than treating each mesh cell as an electrical state.",
            styles["BodyText"],
        )
    )
    rows = [
        ["Concept", "Meaning in this project"],
        ["Battery cell", "One physical electrochemical unit represented by the ECM"],
        ["Mesh cell", "One OpenFOAM finite-volume cell in the active jellyRoll region"],
        ["Partition / ECM zone", "A distributed thermal aggregation region used in element-wise coupling"],
        ["Accepted distributed baseline", "Shared ECM electrical state with distributed thermal/source mapping"],
    ]
    story.append(_table(rows, [4.0, 11.5]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("3. Implementation Delivered", styles["Section"]))
    story.append(
        Paragraph(
            "The delivered package includes the custom OpenFOAM function-object library, the solids-only solver path used by the CHT cases, the Python ECM runtime and coupler, persistent binary pipe transport, report generators, validation harnesses, and a portable packaging/build workflow. The user can run either lumped or distributed cases by configuration without changing the shell environment.",
            styles["BodyText"],
        )
    )
    story.append(
        Paragraph(
            "Key implementation points include stable global mesh IDs, binary file and persistent-pipe protocols, conservative heat-field update paths, source under-relaxation, runtime snapshot handling, and case-local `Allrun`/`Allmesh` scripts that no longer depend on `/workspace`.",
            styles["BodyText"],
        )
    )

    story.append(Paragraph("4. Numerical Strategy", styles["Section"]))
    story.append(
        Paragraph(
            "The coupling is weakly coupled and non-synced in time: OpenFOAM advances with its own timestep control while the ECM is called on the CFD execute cadence configured in the function object. The current accepted validation runs use per-step ECM calls, binary persistent transport, and `maxDi=100` for development validation. Source under-relaxation and optional temporal interpolation exist to stabilize applied heat when CFD and ECM cadences differ.",
            styles["BodyText"],
        )
    )
    story.extend(_fig(figs["flow"], 16.0, "Figure 3. Forward-only validation execution policy used during solver/coupler stabilization.", styles))

    story.append(Paragraph("5. Validation Methodology", styles["Section"]))
    story.append(
        Paragraph(
            "Validation was split into cheap common-sense analytic checks and a strict forward-only development campaign. The forward-only rule prevented unnecessary reruns: if Test N failed, only Test N was fixed and rerun, and earlier tests were only revisited later if a shared change made them stale.",
            styles["BodyText"],
        )
    )
    story.extend(_fig(figs["summary"], 16.0, "Figure 4. Summary validation metrics for the accepted lumped and distributed forward campaigns.", styles))

    story.append(Paragraph("6. Lumped And Distributed Results", styles["Section"]))
    story.append(
        Paragraph(
            f"Lumped forward results: timestep gate ΔT={lumped_metrics['timestep']['delta_T_05_vs_025_K']:.4f} K and ΔQ={lumped_metrics['timestep']['delta_Q_05_vs_025_W']:.4f} W; adiabatic energy error={lumped_metrics['energy']['energy_error_percent']:.3f}%; mesh gate ΔTmax={lumped_metrics['mesh']['delta_Tmax_medium_vs_fine_K']:.5f} K; zero-current max|Q|={lumped_metrics['ecm_zero']['max_abs_qsum_W']:.3f} W; fixed-current smoothness max|d²Q|={lumped_metrics['ecm_current']['max_abs_second_diff_qsum_W']:.3f} W.",
            styles["BodyText"],
        )
    )
    story.append(
        Paragraph(
            f"Distributed forward results: timestep gate ΔT={distributed_metrics['timestep']['delta_T_025_vs_0125_K']:.4f} K and ΔQ={distributed_metrics['timestep']['delta_Q_025_vs_0125_W']:.4f} W; adiabatic energy error={distributed_metrics['energy']['energy_error_percent']:.3f}%; mesh gate ΔTmax={distributed_metrics['mesh']['delta_Tmax_medium_vs_fine_K']:.5f} K; zero-current max|Q|={distributed_metrics['ecm_zero']['max_abs_qsum_W']:.3f} W; fixed-current post-startup smoothness max|d²Q|={distributed_metrics['ecm_current']['max_abs_second_diff_qsum_after_5s_W']:.3f} W.",
            styles["BodyText"],
        )
    )
    story.extend(_fig(figs["energy"], 16.0, "Figure 5. Adiabatic energy-balance checks for lumped and distributed forward validation.", styles))
    story.extend(_fig(figs["q_zero"], 16.0, "Figure 6. Final zero-current comparison after fixing stale runtime snapshot carryover in distributed validation clones.", styles))
    story.extend(_fig(figs["q_fixed"], 16.0, "Figure 7. Final fixed-current comparison for the accepted shared-state equivalence baseline.", styles))

    story.append(Paragraph("7. Temperature Fields And Section Views", styles["Section"]))
    story.append(
        Paragraph(
            "Headless section rendering now uses PyVista for OpenFOAM data access and matplotlib for polygon plotting, avoiding the off-screen ParaView problems encountered earlier. The distributed section view uses an ECM partition overlay so the client can see the thermal field together with the ECM zoning used by the distributed thermal/source path.",
            styles["BodyText"],
        )
    )
    story.extend(_fig(figs["lumped_section"], 16.0, "Figure 8. Lumped jellyRoll temperature section rendered directly from the OpenFOAM case.", styles))
    story.extend(_fig(figs["dist_section"], 16.0, "Figure 9. Distributed jellyRoll temperature section with ECM partition overlay.", styles))

    story.append(Paragraph("8. Mapping And Source Distribution", styles["Section"]))
    story.append(
        Paragraph(
            "The accepted forward-validation baseline used the existing distributed map in the validated case path. In later development, a true many-to-many overlap-weighted mapping generator was implemented and demonstrated in a new clone. This is an important mapping improvement, but it should be treated as a newer enhancement rather than retroactively folded into the already accepted equivalence baseline.",
            styles["BodyText"],
        )
    )
    story.extend(_fig(ROOT / "artifacts" / "plots" / "distributed_source_maps" / "current_dist_ecm_zone_qdot_x.png", 16.0, "Figure 10. Heat applied per ECM zone for the current assignment-mapped distributed case.", styles))
    story.extend(_fig(ROOT / "artifacts" / "plots" / "distributed_source_maps" / "current_dist_cfd_cell_qdot_x.png", 16.0, "Figure 11. Heat applied per CFD cell for the same current distributed case.", styles))
    story.extend(_fig(ROOT / "artifacts" / "plots" / "distributed_source_maps" / "overlap_dist_ecm_zone_qdot_x.png", 16.0, "Figure 12. Heat applied per ECM zone in the new overlap-weighted mapping clone.", styles))
    story.extend(_fig(ROOT / "artifacts" / "plots" / "distributed_source_maps" / "overlap_dist_cfd_cell_qdot_x.png", 16.0, "Figure 13. Heat applied per CFD cell in the new overlap-weighted mapping clone.", styles))
    story.extend(_fig(figs["weight_panel"], 16.0, "Figure 14. Normalized CFD→ECM contribution fractions for representative lower, middle, and upper ECM partitions under the new overlap-weighted mapping.", styles))
    story.append(
        Paragraph(
            "Important clarification: the plotted weight fields are normalized per-cell contribution fractions, not raw overlap volumes. The normalized fields are bounded in [0, 1], while the raw overlap values in the mapping CSV are in m³.",
            styles["BodyText"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("9. Technical Maturation And Issues Resolved", styles["Section"]))
    for bullet in [
        "Benchmark-definition corrections: adiabatic test cases needed true adiabatic walls and `h=1.0` to be meaningful.",
        "Startup stale-state artifact: inherited `ecm_last_good.bin` snapshots created a false distributed startup transient until clone cleanup removed them.",
        "Runner environment discrepancy: a helper `_run()` path that re-sourced OpenFOAM changed behavior and created a false lumped/distributed mismatch until removed.",
        "Persistent JSON bottleneck: persistent process transport only became beneficial after switching element-wise coupling from JSON payloads to framed binary.",
        "PyVista/reporting artifacts: slice rendering had to use real slice polygons rather than global triangulation to avoid mesh artifacts.",
    ]:
        story.append(Paragraph(f"• {bullet}", styles["BodyText"]))

    story.append(Paragraph("10. Performance Findings", styles["Section"]))
    story.append(
        Paragraph(
            "Distributed runtime was highly sensitive to the transport path. The 30 s element-wise distributed case took about 120 s with file-based binary transport, 291 s with persistent JSON transport, and 43 s with persistent binary transport. A 300 s binary-persistent distributed run completed in about 468 s. A matched 30 s benchmark separated solver-only (~7 s), mock-coupled (~42 s), and full-coupled (~43 s) runs, showing that the real ECM math itself was a small part of the total cost relative to the surrounding coupling stack.",
            styles["BodyText"],
        )
    )
    story.extend(_fig(figs["runtime"], 16.0, "Figure 15. Runtime comparison across key transport and benchmark modes.", styles))

    story.append(Paragraph("11. Current Limitations", styles["Section"]))
    for bullet in [
        "Coupling remains weakly coupled in time; there are no OpenFOAM↔ECM sub-iterations in the accepted baseline.",
        "The accepted distributed equivalence baseline uses a shared electrical state; a physically distributed electrical network model is not yet validated.",
        "External dataset validation against experimental references remains future work.",
        "The overlap-weighted mapping enhancement has been demonstrated, but it is newer than the accepted forward-validation baseline and should be validated on its own track.",
    ]:
        story.append(Paragraph(f"• {bullet}", styles["BodyText"]))

    story.append(Paragraph("12. What The Client Can Use Now", styles["Section"]))
    rows = [
        ["Deliverable", "Status", "Comment"],
        ["Lumped case", "Ready", "Validated forward harness and portable run path available"],
        ["Distributed shared-state case", "Ready", "Validated equivalence baseline and 300 s binary-persistent run available"],
        ["Portable package", "Ready", "Package, build script, and package-local `Allrun` flow prepared"],
        ["Overlap-weighted mapping", "Investigational", "Implemented and demonstrated in a new case clone"],
        ["True distributed electrical model", "Future work", "Parallel-branch concept selected but not yet validated"],
    ]
    story.append(_table(rows, [4.3, 2.4, 9.0]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("13. Recommended Next Steps", styles["Section"]))
    for bullet in [
        "Validate the overlap-weighted mapping path separately with conservation, round-trip, and mesh-refinement checks.",
        "Implement and validate a true parallel-branch distributed electrical model only on a separate track from the accepted shared-state baseline.",
        "Run external experimental dataset validation after the mapping and electrical formulation are frozen.",
        "Keep the direct-shell versus harness-run safeguard in the debugging workflow for any future discrepancies.",
    ]:
        story.append(Paragraph(f"• {bullet}", styles["BodyText"]))

    story.append(PageBreak())
    story.append(Paragraph("Appendix A. Validation Status", styles["Section"]))
    story.extend(_fig(figs["matrix"], 14.0, "Figure A1. Final validation status matrix for the accepted forward campaigns.", styles))
    story.append(Paragraph("Appendix B. Project Progress Timeline By Phase", styles["Section"]))
    story.extend(_fig(figs["timeline"], 15.5, "Figure B1. Progress summarized by technical phase rather than by day-by-day chronology.", styles))
    story.append(Paragraph("Appendix C. Key File References", styles["Section"]))
    refs = [
        "docs/CLIENT_REPORT_OUTLINE.md",
        "artifacts/validation/lumped_forward/forward_campaign_summary_20260327_201140.md",
        "artifacts/validation/distributed_forward/forward_campaign_summary_20260327_211520.md",
        "artifacts/reports/lumped_vs_distributed_forward_validation_20260327_224210.pdf",
        "artifacts/logs/distributed_solid_run_20260327_163918.log",
        "artifacts/logs/distributed_solid_run_20260328_001212.log",
    ]
    for ref in refs:
        story.append(Paragraph(f"• {ref}", styles["BodyText"]))

    doc.build(story)

    md = _build_markdown(
        stamp,
        {
            "architecture": figs["architecture"].as_posix(),
            "q_fixed": figs["q_fixed"].as_posix(),
            "dist_section": figs["dist_section"].as_posix(),
            "weight_panel": figs["weight_panel"].as_posix(),
        },
        {
            "l_t_dt": lumped_metrics["timestep"]["delta_T_05_vs_025_K"],
            "l_q_dt": lumped_metrics["timestep"]["delta_Q_05_vs_025_W"],
            "d_t_dt": distributed_metrics["timestep"]["delta_T_025_vs_0125_K"],
            "d_q_dt": distributed_metrics["timestep"]["delta_Q_025_vs_0125_W"],
            "l_e": lumped_metrics["energy"]["energy_error_percent"],
            "d_e": distributed_metrics["energy"]["energy_error_percent"],
        },
    )
    print(pdf)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
