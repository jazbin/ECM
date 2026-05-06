#!/usr/bin/env python3
"""
Generate a PDF comparison report between lumped_solid and distributed_solid ECM runs.

Usage:
  python3 tools/generate_comparison_report.py

Reads from existing log files; does not require a new solver run.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib import colors


# ── paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PLOTS = ROOT / "artifacts" / "plots"
REPORTS = ROOT / "artifacts" / "reports"
PLOTS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

LUMPED_LOG   = ROOT / "cases" / "lumped_solid" / "log.ecm_step_300s"
DIST_LOG     = ROOT / "artifacts" / "logs" / "distributed_solid_run_20260327_163918.log"
LUMPED_CASE  = ROOT / "cases" / "lumped_solid"
DIST_CASE    = ROOT / "cases" / "distributed_solid"

STAMP = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")

# colour palette
C_LUMPED = "#1f77b4"
C_DIST   = "#d62728"


# ── parsers ───────────────────────────────────────────────────────────────────

def parse_qsum(log_text: str) -> tuple[list[float], list[float]]:
    re_t = re.compile(r"^\s*Time\s*=\s*([0-9eE+\-\.]+)\s*$", re.M)
    re_q = re.compile(r"^\s*Q_sum_check\s+([0-9eE+\-\.]+)\s*W?\s*$", re.M)
    times, qsums = [], []
    cur_t = None
    for line in log_text.splitlines():
        m = re_t.match(line)
        if m:
            try:
                cur_t = float(m.group(1))
            except ValueError:
                cur_t = None
            continue
        m = re_q.match(line)
        if m and cur_t is not None:
            try:
                qsums.append(float(m.group(1)))
                times.append(cur_t)
            except ValueError:
                pass
    return times, qsums


def parse_minmax_T(log_text: str, region: str) -> tuple[list[float], list[float], list[float]]:
    """
    Return (times, T_min, T_max) for the named region, taken from the line
    immediately following each 'Solving for solid region <region>' line.
    """
    times, tmins, tmaxs = [], [], []
    cur_t = None
    lines = log_text.splitlines()
    re_t = re.compile(r"^\s*Time\s*=\s*([0-9eE+\-\.]+)\s*$")
    re_region = re.compile(rf"Solving for solid region\s+{re.escape(region)}\s*$")
    re_minmax = re.compile(r"Min/max T:([0-9eE+\-\.]+)\s+([0-9eE+\-\.]+)")
    i = 0
    while i < len(lines):
        m = re_t.match(lines[i])
        if m:
            try:
                cur_t = float(m.group(1))
            except ValueError:
                cur_t = None
        if re_region.search(lines[i]) and cur_t is not None:
            # Scan forward up to 5 lines for the Min/max T line
            for j in range(i + 1, min(i + 6, len(lines))):
                mm = re_minmax.search(lines[j])
                if mm:
                    try:
                        tmins.append(float(mm.group(1)))
                        tmaxs.append(float(mm.group(2)))
                        times.append(cur_t)
                    except ValueError:
                        pass
                    break
        i += 1
    return times, tmins, tmaxs


def parse_solver_config(case: Path) -> dict:
    """Extract key coupling params from controlDict."""
    cd = case / "system" / "controlDict"
    if not cd.exists():
        return {}
    txt = re.sub(r"//.*", "", cd.read_text(errors="ignore"))
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.DOTALL)
    keys = ("application", "endTime", "deltaT", "couplingMode", "parallelMode",
            "keyMode", "relaxation", "current_A", "SOC")
    out = {}
    for k in keys:
        m = re.search(rf"\b{re.escape(k)}\s+([^;]+);", txt)
        if m:
            out[k] = m.group(1).strip().strip('"')
    return out


def downsample(xs: list, ys: list, n: int = 400) -> tuple[list, list]:
    if len(xs) <= n:
        return xs, ys
    idx = np.round(np.linspace(0, len(xs) - 1, n)).astype(int)
    return [xs[i] for i in idx], [ys[i] for i in idx]


def parse_clock_time(log_text: str) -> int | None:
    vals = [int(m.group(1)) for m in re.finditer(r"ClockTime =\s*([0-9]+)\s*s", log_text)]
    return vals[-1] if vals else None


def build_timing_breakdown(full_log: Path | None, solver_log: Path | None, mock_log: Path | None) -> dict | None:
    if not full_log or not solver_log or not mock_log:
        return None
    if not full_log.exists() or not solver_log.exists() or not mock_log.exists():
        return None
    full_clock = parse_clock_time(full_log.read_text(errors="ignore"))
    solver_clock = parse_clock_time(solver_log.read_text(errors="ignore"))
    mock_clock = parse_clock_time(mock_log.read_text(errors="ignore"))
    if not full_clock or not solver_clock or not mock_clock:
        return None
    transport_clock = max(0, mock_clock - solver_clock)
    real_ecm_clock = max(0, full_clock - mock_clock)
    total = float(full_clock)
    return {
        "full_clock_s": full_clock,
        "solver_clock_s": solver_clock,
        "mock_clock_s": mock_clock,
        "solver_pct": 100.0 * solver_clock / total,
        "transport_pct": 100.0 * transport_clock / total,
        "real_ecm_pct": 100.0 * real_ecm_clock / total,
        "transport_clock_s": transport_clock,
        "real_ecm_clock_s": real_ecm_clock,
        "full_log": full_log,
        "solver_log": solver_log,
        "mock_log": mock_log,
    }


# ── plotting ──────────────────────────────────────────────────────────────────

def plot_qsum_comparison(
    t_l, q_l, t_d, q_d, out: Path
) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=160)
    t_l_ds, q_l_ds = downsample(t_l, q_l)
    t_d_ds, q_d_ds = downsample(t_d, q_d)
    ax.plot(t_l_ds, q_l_ds, lw=1.6, color=C_LUMPED, label="Lumped")
    ax.plot(t_d_ds, q_d_ds, lw=1.6, color=C_DIST,   label="Distributed")
    ax.set_xlabel("Simulation time [s]", fontsize=9)
    ax.set_ylabel("Q_sum_check [W]", fontsize=9)
    ax.set_title("ECM Heat Generation — Lumped vs Distributed", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_qsum_overlay_early(
    t_l, q_l, t_d, q_d, out: Path, window: float = 30.0
) -> None:
    """Same plot but cropped to the first `window` seconds for direct comparison."""
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=160)
    t_l2 = [t for t in t_l if t <= window]
    q_l2 = [q for t, q in zip(t_l, q_l) if t <= window]
    t_d2 = [t for t in t_d if t <= window]
    q_d2 = [q for t, q in zip(t_d, q_d) if t <= window]
    ax.plot(t_l2, q_l2, lw=1.8, color=C_LUMPED, label="Lumped")
    ax.plot(t_d2, q_d2, lw=1.8, color=C_DIST,   label="Distributed (18 zones)")
    ax.set_xlabel("Simulation time [s]", fontsize=9)
    ax.set_ylabel("Q_sum_check [W]", fontsize=9)
    ax.set_title(f"Heat Generation — First {window:.0f} s (direct comparison)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_Tmax_comparison(
    t_l, tmax_l, t_d, tmax_d, out: Path, region: str = "jellyRoll"
) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=160)
    t_l_ds, tmax_l_ds = downsample(t_l, tmax_l)
    ax.plot(t_l_ds, tmax_l_ds, lw=1.6, color=C_LUMPED, label="Lumped")
    ax.plot(t_d, tmax_d, lw=1.6, color=C_DIST, label="Distributed")
    ax.set_xlabel("Simulation time [s]", fontsize=9)
    ax.set_ylabel("T_max [K]", fontsize=9)
    ax.set_title(f"Peak Temperature ({region}) — Lumped vs Distributed", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_Tmax_early(
    t_l, tmax_l, t_d, tmax_d, out: Path, window: float = 30.0
) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=160)
    t_l2 = [t for t in t_l if t <= window]
    tm_l2 = [v for t, v in zip(t_l, tmax_l) if t <= window]
    ax.plot(t_l2, tm_l2, lw=1.8, color=C_LUMPED, label="Lumped")
    ax.plot([t for t in t_d if t <= window],
            [v for t, v in zip(t_d, tmax_d) if t <= window],
            lw=1.8, color=C_DIST, label="Distributed")
    ax.set_xlabel("Simulation time [s]", fontsize=9)
    ax.set_ylabel("T_max jellyRoll [K]", fontsize=9)
    ax.set_title(f"Peak Temperature — First {window:.0f} s", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_qvol_zones(log_text: str, out: Path, n_zones: int = 18) -> None:
    """Plot qVol range (min..max) per ECM call from the distributed log."""
    re_t = re.compile(r"^\s*Time\s*=\s*([0-9eE+\-\.]+)\s*$", re.M)
    re_qvol = re.compile(r"qVol=\[([0-9eE+\-\.]+)\.\.([0-9eE+\-\.]+)\]")
    times, qmin_list, qmax_list = [], [], []
    cur_t = None
    for line in log_text.splitlines():
        m = re_t.match(line)
        if m:
            try: cur_t = float(m.group(1))
            except ValueError: cur_t = None
            continue
        m = re_qvol.search(line)
        if m and cur_t is not None:
            try:
                times.append(cur_t)
                qmin_list.append(float(m.group(1)))
                qmax_list.append(float(m.group(2)))
            except ValueError:
                pass
    if not times:
        return
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=160)
    ax.fill_between(times, qmin_list, qmax_list, alpha=0.25, color=C_DIST, label="zone spread")
    ax.plot(times, qmin_list, lw=1.0, color=C_DIST, ls="--", label="qVol min")
    ax.plot(times, qmax_list, lw=1.4, color=C_DIST, label="qVol max")
    ax.set_xlabel("Simulation time [s]", fontsize=9)
    ax.set_ylabel("qVol [W/m³]", fontsize=9)
    ax.set_title(f"Distributed ECM — Zone qVol Spread ({n_zones} zones)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_shell_cap_Tmax(
    t_ls, tmax_ls_shell, tmax_ls_cap,
    t_ds, tmax_ds_shell, tmax_ds_cap,
    out: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), dpi=160)
    for ax, tmax_l, tmax_d, region in zip(
        axes,
        [tmax_ls_shell, tmax_ls_cap],
        [tmax_ds_shell, tmax_ds_cap],
        ["shell", "cap"],
    ):
        t_l2, tm_l2 = downsample(t_ls, tmax_l)
        ax.plot(t_l2, tm_l2, lw=1.6, color=C_LUMPED, label="Lumped")
        ax.plot(t_ds, tmax_d, lw=1.6, color=C_DIST,   label="Distributed")
        ax.set_xlabel("time [s]", fontsize=8)
        ax.set_ylabel("T_max [K]", fontsize=8)
        ax.set_title(f"T_max — {region}", fontsize=9)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Passive Region Peak Temperatures", fontsize=10, y=1.01)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


# ── PDF builder ───────────────────────────────────────────────────────────────

def img(path: Path, w: float = 490, h: float = 230) -> Image:
    return Image(str(path), width=w, height=h)


def build_pdf(
    out_path: Path,
    *,
    lumped_cfg: dict,
    dist_cfg: dict,
    lumped_log_path: Path,
    dist_log_path: Path,
    t_l_q, q_l, t_d_q, q_d,
    t_l_jmax, tmax_l_j,
    t_d_jmax, tmax_d_j,
    t_l_smax, tmax_l_s,
    t_d_smax, tmax_d_s,
    t_l_cmax, tmax_l_c,
    t_d_cmax, tmax_d_c,
    plot_qsum_full: Path,
    plot_qsum_early: Path,
    plot_Tmax_full: Path,
    plot_Tmax_early: Path,
    plot_qvol_zones: Path | None,
    plot_passive: Path,
    lumped_sections: list[Path] | None = None,
    dist_sections: list[Path] | None = None,
    timing_summary: dict | None = None,
) -> None:
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, leading=11)
    bold  = ParagraphStyle("bold",  parent=normal, fontName="Helvetica-Bold")
    now = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        title="Lumped vs Distributed ECM — Comparison Report",
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
    )
    story = []

    # ── Title ──
    story.append(Paragraph("Lumped vs Distributed ECM Coupling — Comparison Report", h1))
    story.append(Paragraph(f"Generated (UTC): {now}", small))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#444444")))
    story.append(Spacer(1, 8))

    # ── 1. Overview ──
    story.append(Paragraph("1. Overview", h2))
    story.append(Paragraph(
        "This report compares two ECM coupling strategies implemented in the "
        "OpenFOAM CHT battery-cell thermal framework:",
        normal,
    ))
    story.append(Spacer(1, 4))
    overview = [
        ["Parameter", "Lumped Solid", "Distributed Solid"],
        ["Case", "cases/lumped_solid", "cases/distributed_solid"],
        ["Solver", lumped_cfg.get("application", "—"), dist_cfg.get("application", "—")],
        ["Coupling mode", lumped_cfg.get("couplingMode", "lumped"), dist_cfg.get("couplingMode", "elementWise")],
        ["ECM zones", "1 (volume-averaged T)", "18 (axial6 × radial3)"],
        ["Current", f"{lumped_cfg.get('current_A', '79')} A", f"{dist_cfg.get('current_A', '79')} A"],
        ["Simulation duration", f"{max(t_l_q):.1f} s" if t_l_q else "—", f"{max(t_d_q):.1f} s" if t_d_q else "—"],
        ["Timesteps logged", str(len(t_l_q)), str(len(t_d_q))],
        ["Log file", lumped_log_path.name, dist_log_path.name],
    ]
    t = Table(overview, colWidths=[130, 175, 175])
    t.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#DDEEFF")),
        ("BACKGROUND",  (0, 1), (0, -1), colors.HexColor("#F5F5F5")),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("LEADING",     (0, 0), (-1, -1), 11),
        ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # ── 2. Heat Generation ──
    story.append(Paragraph("2. ECM Heat Generation (Q_sum_check)", h2))
    story.append(Paragraph(
        "Q_sum_check is the total volumetric heat summed over the jellyRoll zone "
        "(∑ qVol·V) reported each timestep by the ecmCoupler function object.",
        small,
    ))
    story.append(Spacer(1, 4))

    # Stats table
    def _stats(vals):
        if not vals:
            return {"min": float("nan"), "max": float("nan"), "mean": float("nan"), "final": float("nan")}
        return {"min": min(vals), "max": max(vals),
                "mean": sum(vals)/len(vals), "final": vals[-1]}

    sl = _stats(q_l)
    sd = _stats(q_d)
    qstats = [
        ["Metric", "Lumped [W]", "Distributed [W]", "Δ (Dist − Lump)"],
        ["Initial",  f"{q_l[0]:.2f}" if q_l else "—",  f"{q_d[0]:.2f}" if q_d else "—", "—"],
        ["Final",    f"{sl['final']:.2f}", f"{sd['final']:.2f}",
         f"{sd['final']-sl['final']:+.2f}"],
        ["Min",      f"{sl['min']:.2f}",  f"{sd['min']:.2f}",  f"{sd['min']-sl['min']:+.2f}"],
        ["Max",      f"{sl['max']:.2f}",  f"{sd['max']:.2f}",  f"{sd['max']-sl['max']:+.2f}"],
        ["Mean",     f"{sl['mean']:.2f}", f"{sd['mean']:.2f}", f"{sd['mean']-sl['mean']:+.2f}"],
    ]
    tq = Table(qstats, colWidths=[130, 110, 130, 110])
    tq.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDEEFF")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F5F5F5")),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(tq)
    story.append(Spacer(1, 8))
    story.append(img(plot_qsum_full, w=490, h=230))
    story.append(Spacer(1, 4))
    story.append(img(plot_qsum_early, w=490, h=230))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Key observations:</b> The lumped run maintains a higher total heat release "
        "than the distributed run across the 300 s horizon, while the distributed run "
        "still reaches a higher jellyRoll peak temperature. That combination is "
        "consistent with more spatially concentrated heating in the distributed model.",
        small,
    ))
    story.append(Spacer(1, 10))

    # ── 3. Temperature ──
    story.append(Paragraph("3. jellyRoll Peak Temperature", h2))
    story.append(Paragraph(
        "T_max is the maximum cell temperature in the jellyRoll region "
        "(active electrode volume) extracted from the solver log each timestep.",
        small,
    ))
    story.append(Spacer(1, 4))

    tl_jmax_f = tmax_l_j[-1] if tmax_l_j else float("nan")
    td_jmax_f = tmax_d_j[-1] if tmax_d_j else float("nan")
    Tstats = [
        ["Metric", "Lumped [K]", "Distributed [K]", "Δ (Dist − Lump)"],
        ["T_initial", f"{tmax_l_j[0]:.3f}" if tmax_l_j else "—",
                      f"{tmax_d_j[0]:.3f}" if tmax_d_j else "—", "—"],
        ["T_final",   f"{tl_jmax_f:.3f}", f"{td_jmax_f:.3f}",
         f"{td_jmax_f - tl_jmax_f:+.3f}"],
        ["T_max",     f"{max(tmax_l_j):.3f}" if tmax_l_j else "—",
                      f"{max(tmax_d_j):.3f}" if tmax_d_j else "—", "—"],
        ["ΔT rise",   f"{max(tmax_l_j)-313.15:.3f}" if tmax_l_j else "—",
                      f"{max(tmax_d_j)-313.15:.3f}" if tmax_d_j else "—", "—"],
    ]
    tt = Table(Tstats, colWidths=[130, 110, 130, 110])
    tt.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFEEDD")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F5F5F5")),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(tt)
    story.append(Spacer(1, 8))
    story.append(img(plot_Tmax_full, w=490, h=230))
    story.append(Spacer(1, 4))
    story.append(img(plot_Tmax_early, w=490, h=230))
    story.append(Spacer(1, 8))

    # ── 4. Distributed zone spread ──
    if plot_qvol_zones and plot_qvol_zones.exists():
        story.append(Paragraph("4. Distributed ECM — Zone-level qVol Spread", h2))
        story.append(Paragraph(
            "With elementWise coupling, each of the 18 ECM zones (3 axial × 6 radial) "
            "receives an independent temperature and returns its own qVol [W/m³]. "
            "The shaded band shows the min–max spread across zones each timestep.",
            small,
        ))
        story.append(Spacer(1, 4))
        story.append(img(plot_qvol_zones, w=490, h=220))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "The converging spread indicates zones equilibrating to a common "
            "temperature as conduction homogenises the cell. A persistent non-zero "
            "spread would indicate genuine spatial heterogeneity in heat generation.",
            small,
        ))
        story.append(Spacer(1, 10))

    # ── 5. Passive regions ──
    story.append(Paragraph("5. Passive Region Temperatures (shell, cap)", h2))
    story.append(Paragraph(
        "Shell and cap are passive conductors. Their peak temperature reflects how "
        "efficiently heat is conducted out of the jellyRoll.",
        small,
    ))
    story.append(Spacer(1, 4))
    story.append(img(plot_passive, w=490, h=230))
    story.append(Spacer(1, 10))

    if lumped_sections and dist_sections:
        story.append(Paragraph("6. Section Comparison at ~300 s", h2))
        story.append(Paragraph(
            "Representative jellyRoll cross-sections from the two 300 s runs. The "
            "lumped case images are the archived 300 s slices, and the distributed "
            "case images were regenerated with the new headless PyVista reader plus "
            "matplotlib renderer.",
            small,
        ))
        story.append(Spacer(1, 4))
        rows = [[Paragraph("Lumped", bold), Paragraph("Distributed", bold)]]
        for l_img, d_img in zip(lumped_sections, dist_sections):
            rows.append([img(l_img, w=220, h=220), img(d_img, w=220, h=220)])
        sec_table = Table(rows, colWidths=[235, 235], hAlign="CENTER")
        sec_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CCCCCC")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F6F6F6")),
        ]))
        story.append(sec_table)
        story.append(Spacer(1, 10))

    if timing_summary:
        story.append(Paragraph("7. Distributed Solve-Time Breakdown", h2))
        story.append(Paragraph(
            "Breakdown based on matched 30 s benchmarks of the distributed case: "
            "solver-only, solver plus mock binary-pipe coupling, and solver plus full "
            "real ECM coupling. This separates the thermal solve from coupling "
            "transport overhead and the incremental cost of the real ECM step.",
            small,
        ))
        story.append(Spacer(1, 4))
        timing_rows = [
            ["Component", "Time [s]", "Share of full 30 s run"],
            ["Thermal solve only", f"{timing_summary['solver_clock_s']}", f"{timing_summary['solver_pct']:.1f}%"],
            ["Coupling transport/wrapper", f"{timing_summary['transport_clock_s']}", f"{timing_summary['transport_pct']:.1f}%"],
            ["Real ECM compute", f"{timing_summary['real_ecm_clock_s']}", f"{timing_summary['real_ecm_pct']:.1f}%"],
            ["Full distributed 30 s run", f"{timing_summary['full_clock_s']}", "100.0%"],
        ]
        ttiming = Table(timing_rows, colWidths=[220, 90, 150])
        ttiming.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3EA")),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F5F5F5")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ]))
        story.append(ttiming)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Benchmark logs: full={timing_summary['full_log'].name}, "
            f"solver-only={timing_summary['solver_log'].name}, "
            f"mock-coupled={timing_summary['mock_log'].name}.",
            small,
        ))
        story.append(Spacer(1, 10))

    # ── 8. Method comparison ──
    story.append(Paragraph("8. Method Comparison Summary", h2))
    summary_data = [
        ["Aspect", "Lumped (single zone)", "Distributed (18 zones)"],
        ["ECM calls / step",  "1", "18"],
        ["T fed to ECM",  "Volume-averaged jellyRoll T", "Per-zone average T"],
        ["Spatial heat resolution", "Uniform qVol over jellyRoll", "Zone-varying qVol"],
        ["Startup behaviour",  "Immediate peak heat, slow decay", "Ramp-up as zones heat independently"],
        ["Q at 30 s", f"~{next((q for t,q in zip(t_l_q,q_l) if t>=29), q_l[-1] if q_l else 0):.0f} W",
                      f"~{q_d[-1]:.0f} W" if q_d else "—"],
        ["T_max at 30 s",
         f"~{next((v for t,v in zip(t_l_jmax,tmax_l_j) if t>=29), tmax_l_j[-1] if tmax_l_j else 313):.2f} K",
         f"~{tmax_d_j[-1]:.2f} K" if tmax_d_j else "—"],
        ["Use case",  "Fast runs, SOC/SOP monitoring", "Spatial hotspot prediction"],
        ["Recommended for",  "System-level simulations", "Cell-level detailed analysis"],
    ]
    ts = Table(summary_data, colWidths=[150, 170, 160])
    ts.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FE")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F5F5F5")),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("LEADING",    (0, 0), (-1, -1), 11),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(ts)
    story.append(Spacer(1, 10))

    # ── Footer ──
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#AAAAAA")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"OpenFOAM–ECM Coupling Framework | Report generated {now} | "
        f"Lumped log: {lumped_log_path.name} | Distributed log: {dist_log_path.name}",
        small,
    ))

    doc.build(story)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lumped-log", default=str(LUMPED_LOG))
    ap.add_argument("--dist-log", default=str(DIST_LOG))
    ap.add_argument("--lumped-case", default=str(LUMPED_CASE))
    ap.add_argument("--dist-case", default=str(DIST_CASE))
    ap.add_argument(
        "--lumped-sections",
        nargs="*",
        default=[
            str(PLOTS / "lumped_solid_300s_final_T_z1_t0300.png"),
            str(PLOTS / "lumped_solid_300s_final_T_z2_t0300.png"),
            str(PLOTS / "lumped_solid_300s_final_T_z3_t0300.png"),
        ],
    )
    ap.add_argument(
        "--dist-sections",
        nargs="*",
        default=[
            str(PLOTS / "distributed_solid_300s_cmp_T_slice_z1.png"),
            str(PLOTS / "distributed_solid_300s_cmp_T_slice_z2.png"),
            str(PLOTS / "distributed_solid_300s_cmp_T_slice_z3.png"),
        ],
    )
    ap.add_argument(
        "--timing-full-log",
        default=str(ROOT / "artifacts" / "logs" / "distributed_solid_run_20260327_162502.log"),
    )
    ap.add_argument(
        "--timing-solver-log",
        default=str(ROOT / "artifacts" / "logs" / "distributed_bench_solveronly_30s_20260327_170411.log"),
    )
    ap.add_argument(
        "--timing-mock-log",
        default=str(ROOT / "artifacts" / "logs" / "distributed_bench_mock_ok_30s_20260327_170729.log"),
    )
    args = ap.parse_args()

    lumped_log = Path(args.lumped_log).resolve()
    dist_log = Path(args.dist_log).resolve()
    lumped_case = Path(args.lumped_case).resolve()
    dist_case = Path(args.dist_case).resolve()
    lumped_sections = [Path(p).resolve() for p in args.lumped_sections if Path(p).exists()]
    dist_sections = [Path(p).resolve() for p in args.dist_sections if Path(p).exists()]
    timing_summary = build_timing_breakdown(
        Path(args.timing_full_log).resolve(),
        Path(args.timing_solver_log).resolve(),
        Path(args.timing_mock_log).resolve(),
    )

    print("Reading logs...")
    lumped_text = lumped_log.read_text(errors="ignore")
    dist_text   = dist_log.read_text(errors="ignore")

    lumped_cfg = parse_solver_config(lumped_case)
    dist_cfg   = parse_solver_config(dist_case)

    print("Parsing Q_sum series...")
    t_l_q, q_l = parse_qsum(lumped_text)
    t_d_q, q_d = parse_qsum(dist_text)
    print(f"  Lumped: {len(t_l_q)} points, t=[{min(t_l_q):.2f},{max(t_l_q):.2f}] s, "
          f"Q=[{min(q_l):.1f},{max(q_l):.1f}] W")
    print(f"  Distributed: {len(t_d_q)} points, t=[{min(t_d_q):.2f},{max(t_d_q):.2f}] s, "
          f"Q=[{min(q_d):.1f},{max(q_d):.1f}] W")

    print("Parsing T series...")
    t_l_jt, tmin_l_j, tmax_l_j = parse_minmax_T(lumped_text, "jellyRoll")
    t_d_jt, tmin_d_j, tmax_d_j = parse_minmax_T(dist_text,   "jellyRoll")
    t_l_st, _,        tmax_l_s  = parse_minmax_T(lumped_text, "shell")
    t_d_st, _,        tmax_d_s  = parse_minmax_T(dist_text,   "shell")
    t_l_ct, _,        tmax_l_c  = parse_minmax_T(lumped_text, "cap")
    t_d_ct, _,        tmax_d_c  = parse_minmax_T(dist_text,   "cap")
    print(f"  Lumped jellyRoll: {len(t_l_jt)} points, "
          f"T_max range [{min(tmax_l_j):.2f},{max(tmax_l_j):.2f}] K")
    print(f"  Distributed jellyRoll: {len(t_d_jt)} points, "
          f"T_max range [{min(tmax_d_j):.2f},{max(tmax_d_j):.2f}] K")

    print("Generating plots...")
    p_qfull  = PLOTS / f"comparison_Q_full_{STAMP}.png"
    p_qearly = PLOTS / f"comparison_Q_early_{STAMP}.png"
    p_Tfull  = PLOTS / f"comparison_Tmax_full_{STAMP}.png"
    p_Tearly = PLOTS / f"comparison_Tmax_early_{STAMP}.png"
    p_zones  = PLOTS / f"comparison_zones_qvol_{STAMP}.png"
    p_passive = PLOTS / f"comparison_passive_{STAMP}.png"

    plot_qsum_comparison(t_l_q, q_l, t_d_q, q_d, p_qfull)
    print(f"  {p_qfull.name}")
    plot_qsum_overlay_early(t_l_q, q_l, t_d_q, q_d, p_qearly)
    print(f"  {p_qearly.name}")
    plot_Tmax_comparison(t_l_jt, tmax_l_j, t_d_jt, tmax_d_j, p_Tfull)
    print(f"  {p_Tfull.name}")
    plot_Tmax_early(t_l_jt, tmax_l_j, t_d_jt, tmax_d_j, p_Tearly)
    print(f"  {p_Tearly.name}")
    plot_qvol_zones(dist_text, p_zones)
    print(f"  {p_zones.name}")
    plot_shell_cap_Tmax(t_l_st, tmax_l_s, tmax_l_c,
                        t_d_st, tmax_d_s, tmax_d_c, p_passive)
    print(f"  {p_passive.name}")

    out_pdf = REPORTS / f"lumped_vs_distributed_comparison_{STAMP}.pdf"
    print(f"Building PDF → {out_pdf.name} ...")
    build_pdf(
        out_pdf,
        lumped_cfg=lumped_cfg,
        dist_cfg=dist_cfg,
        lumped_log_path=lumped_log,
        dist_log_path=dist_log,
        t_l_q=t_l_q, q_l=q_l,
        t_d_q=t_d_q, q_d=q_d,
        t_l_jmax=t_l_jt, tmax_l_j=tmax_l_j,
        t_d_jmax=t_d_jt, tmax_d_j=tmax_d_j,
        t_l_smax=t_l_st, tmax_l_s=tmax_l_s,
        t_d_smax=t_d_st, tmax_d_s=tmax_d_s,
        t_l_cmax=t_l_ct, tmax_l_c=tmax_l_c,
        t_d_cmax=t_d_ct, tmax_d_c=tmax_d_c,
        plot_qsum_full=p_qfull,
        plot_qsum_early=p_qearly,
        plot_Tmax_full=p_Tfull,
        plot_Tmax_early=p_Tearly,
        plot_qvol_zones=p_zones if p_zones.exists() else None,
        plot_passive=p_passive,
        lumped_sections=lumped_sections,
        dist_sections=dist_sections,
        timing_summary=timing_summary,
    )
    print(f"\nReport written: {out_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
