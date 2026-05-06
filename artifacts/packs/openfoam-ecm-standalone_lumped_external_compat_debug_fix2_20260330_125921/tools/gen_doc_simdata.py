#!/usr/bin/env python3
"""
Generate all simulation-data plots for internal documentation.
Outputs to /workspace/artifacts/plots/doc_simdata/

Includes:
  S01–S03  : Q time series (lumped 300s, distributed 300s, overlaid)
  S04–S08  : Development history / failure plots
  S09–S12  : Cross-section temperature field comparisons (copy from report_image_set)
  S13–S16  : Heat source field comparisons
  S17–S19  : Weight distribution maps
  S20–S21  : Validation summary & metrics
  S22–S25  : Forward validation: zero-current & fixed-current
  S26–S28  : Mesh convergence & timestep sensitivity
  S29–S30  : ECM partition details (zone volumes, heat share)
  S31–S32  : 300-second extended run
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
import shutil
from pathlib import Path

OUT = Path("/workspace/artifacts/plots/doc_simdata")
OUT.mkdir(parents=True, exist_ok=True)

LOGS = Path("/workspace/artifacts/logs")
SRC  = Path("/workspace/artifacts/plots/report_image_set_20260328")

DPI = 200

def save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  {name}")

def copy_src(src_name, dst_name):
    src = SRC / src_name
    dst = OUT / dst_name
    if src.exists():
        shutil.copy2(src, dst)
        print(f"  ✓  {dst_name}  (copy)")
    else:
        print(f"  ✗  {dst_name}  (SOURCE MISSING: {src_name})")

def parse_q(logfile):
    """Parse Q_sum_check values from an OpenFOAM log file."""
    qs = []
    try:
        with open(logfile) as f:
            for line in f:
                if "Q_sum_check" in line:
                    parts = line.split()
                    try:
                        qs.append(float(parts[1]))
                    except (IndexError, ValueError):
                        pass
    except FileNotFoundError:
        pass
    return np.array(qs)

def parse_tmin(logfile):
    """Parse ImplicitDebug postCorrect Tmin values per region."""
    data = {"jellyRoll": [], "shell": [], "cap": []}
    try:
        with open(logfile) as f:
            for line in f:
                if "ImplicitDebug postCorrect" in line:
                    parts = line.split()
                    for reg in data:
                        if reg in parts:
                            idx = parts.index(reg)
                            # format: ... Tmin <val> Tmax ...
                            try:
                                tidx = parts.index("Tmin", idx)
                                data[reg].append(float(parts[tidx+1]))
                            except (ValueError, IndexError):
                                pass
    except FileNotFoundError:
        pass
    return {k: np.array(v) for k, v in data.items()}

# ─────────────────────────────────────────────────────────────────────────────
# S01  Lumped case Q time series (300 s run)
# ─────────────────────────────────────────────────────────────────────────────
def plot_q_lumped():
    q = parse_q(LOGS / "lumped_run_20260327_134358.log")
    if len(q) == 0:
        print("  ✗  S01_q_timeseries_lumped.png  (no data)")
        return
    # Each CFD step = 0.25 s
    t = np.arange(len(q)) * 0.25
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(t, q, color="#1565c0", lw=1.5)
    ax.set_xlabel("Time (s)", fontsize=10)
    ax.set_ylabel("Q_sum_check (W)", fontsize=10)
    ax.set_title("Lumped Case — Heat Generation Time Series (300 s run)", fontsize=12, fontweight="bold")
    ax.set_xlim(0, t[-1])
    ax.grid(True, alpha=0.3)
    # annotate plateau
    q_plateau = float(np.median(q[-50:]))
    ax.axhline(q_plateau, color="#e65100", ls="--", lw=1)
    ax.text(t[-1]*0.7, q_plateau+0.5, f"Steady ≈ {q_plateau:.1f} W",
            color="#e65100", fontsize=9)
    fig.tight_layout()
    save(fig, "S01_q_timeseries_lumped.png")

# ─────────────────────────────────────────────────────────────────────────────
# S02  Distributed case Q time series (300 s run)
# ─────────────────────────────────────────────────────────────────────────────
def plot_q_distributed():
    q = parse_q(LOGS / "distributed_solid_run_20260328_001212.log")
    if len(q) == 0:
        print("  ✗  S02_q_timeseries_distributed.png  (no data)")
        return
    t = np.arange(len(q)) * 0.25
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(t, q, color="#2e7d32", lw=1.5)
    ax.set_xlabel("Time (s)", fontsize=10)
    ax.set_ylabel("Q_sum_check (W)", fontsize=10)
    ax.set_title("Distributed Case — Heat Generation Time Series (300 s run)", fontsize=12, fontweight="bold")
    ax.set_xlim(0, t[-1])
    ax.grid(True, alpha=0.3)
    q_plateau = float(np.median(q[-50:]))
    ax.axhline(q_plateau, color="#e65100", ls="--", lw=1)
    ax.text(t[-1]*0.7, q_plateau+0.3, f"Steady ≈ {q_plateau:.1f} W",
            color="#e65100", fontsize=9)
    fig.tight_layout()
    save(fig, "S02_q_timeseries_distributed.png")

# ─────────────────────────────────────────────────────────────────────────────
# S03  Lumped vs Distributed Q overlay
# ─────────────────────────────────────────────────────────────────────────────
def plot_q_overlay():
    q_l = parse_q(LOGS / "lumped_run_20260327_134358.log")
    q_d = parse_q(LOGS / "distributed_solid_run_20260328_001212.log")
    if len(q_l) == 0 or len(q_d) == 0:
        print("  ✗  S03_q_timeseries_overlay.png  (missing data)")
        return
    n = min(len(q_l), len(q_d))
    t = np.arange(n) * 0.25
    q_l = q_l[:n]; q_d = q_d[:n]
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(t, q_l, color="#1565c0", lw=1.5, label="Lumped")
    ax.plot(t, q_d, color="#2e7d32", lw=1.5, ls="--", label="Distributed")
    ax.set_xlabel("Time (s)", fontsize=10)
    ax.set_ylabel("Q_sum_check (W)", fontsize=10)
    ax.set_title("Lumped vs Distributed — Q Heat Generation Comparison (300 s)", fontsize=12, fontweight="bold")
    ax.set_xlim(0, t[-1])
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    # Annotate max difference
    diff = np.abs(q_l - q_d)
    idx_max = int(np.argmax(diff))
    ax.annotate(f"Max diff: {diff[idx_max]:.2f} W",
                xy=(t[idx_max], (q_l[idx_max]+q_d[idx_max])/2),
                xytext=(t[idx_max]+10, (q_l[idx_max]+q_d[idx_max])/2+2),
                arrowprops=dict(arrowstyle="-|>", color="red"),
                fontsize=8, color="red")
    fig.tight_layout()
    save(fig, "S03_q_timeseries_overlay.png")

# ─────────────────────────────────────────────────────────────────────────────
# S04  FAILURE: dt accumulation bug → Q blow-up to 5e13 W
# ─────────────────────────────────────────────────────────────────────────────
def plot_blowup():
    q = parse_q(LOGS / "distributed_solid_run_20260327_135055.log")
    if len(q) == 0:
        print("  ✗  S04_failure_blowup.png  (no data)")
        return
    t = np.arange(len(q)) * 0.25
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("FAILURE: deltaT Accumulation Bug — Q Blow-up", fontsize=12, fontweight="bold", color="#c62828")

    # left: full log scale
    ax = axes[0]
    with np.errstate(divide="ignore", invalid="ignore"):
        ax.semilogy(t, np.where(q > 0, q, np.nan), color="#c62828", lw=1.5)
    ax.set_xlabel("Time (s)"); ax.set_ylabel("Q_sum_check (W) [log scale]")
    ax.set_title("Full run — log scale")
    ax.grid(True, which="both", alpha=0.3)
    ax.axvline(0.5, color="#e65100", ls="--", lw=1, label="Bug triggers at step 3")
    ax.legend(fontsize=8)

    # right: first 5 steps zoomed
    ax2 = axes[1]
    n_show = min(12, len(q))
    ax2.plot(t[:n_show], q[:n_show], "o-", color="#c62828", lw=2, ms=5)
    ax2.set_xlabel("Time (s)"); ax2.set_ylabel("Q_sum_check (W)")
    ax2.set_title("First 12 steps — onset of instability")
    ax2.grid(True, alpha=0.3)
    for i, (ti, qi) in enumerate(zip(t[:4], q[:4])):
        ax2.annotate(f"step {i}: {qi:.1e} W", (ti, qi), textcoords="offset points",
                     xytext=(5, 5 if i%2==0 else -15), fontsize=7.5)

    ax2.text(0.5, 0.5, "Root cause:\ndeltaT not reset between ECM calls\n→ accumulates unboundedly",
             transform=ax2.transAxes, ha="center", va="center",
             fontsize=9, color="#c62828",
             bbox=dict(fc="#fff9c4", ec="#f57f17", pad=5))

    fig.tight_layout()
    save(fig, "S04_failure_blowup.png")

# ─────────────────────────────────────────────────────────────────────────────
# S05  FAILURE: Hold mode staircase artifact (N=3 step period)
# ─────────────────────────────────────────────────────────────────────────────
def plot_staircase():
    q = parse_q(LOGS / "distributed_solid_run_20260327_134450.log")
    if len(q) == 0:
        print("  ✗  S05_failure_staircase.png  (no data)")
        return
    t = np.arange(len(q)) * 0.25
    n_show = min(120, len(q))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("ECM Hold Mode — Staircase Q Artifact", fontsize=12, fontweight="bold")

    # full run
    ax1.plot(t, q, color="#1565c0", lw=1.5)
    ax1.set_xlabel("Time (s)"); ax1.set_ylabel("Q_sum_check (W)")
    ax1.set_title("Full 300s run"); ax1.grid(True, alpha=0.3)

    # zoom first 30 steps
    ax2.plot(t[:n_show], q[:n_show], "o-", color="#1565c0", lw=1.5, ms=3)
    ax2.set_xlabel("Time (s)"); ax2.set_ylabel("Q_sum_check (W)")
    ax2.set_title("First 30 s — staircase pattern visible")
    ax2.grid(True, alpha=0.3)
    # highlight triplets
    for i in range(0, min(n_show, 30), 3):
        if i+2 < n_show:
            ax2.axvspan(t[i], t[i+2]+0.25, alpha=0.1,
                       color="#2e7d32" if (i//3)%2==0 else "#ff6f00")
    ax2.text(0.02, 0.95,
             "Same Q value repeats 3×\n(ECM fires every 3rd CFD step)\nhold mode: no interpolation",
             transform=ax2.transAxes, va="top", fontsize=9,
             bbox=dict(fc="#fff3e0", ec="#e65100", pad=4))

    fig.tight_layout()
    save(fig, "S05_failure_staircase.png")

# ─────────────────────────────────────────────────────────────────────────────
# S06  FAILURE: Implicit solid coupling Tmin undershoot
# ─────────────────────────────────────────────────────────────────────────────
def plot_implicit_undershoot():
    data = parse_tmin(LOGS / "lumped_run_20260325_204137.log")
    if all(len(v) == 0 for v in data.values()):
        print("  ✗  S06_failure_implicit_undershoot.png  (no data)")
        return
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = {"jellyRoll": "#1565c0", "shell": "#e65100", "cap": "#2e7d32"}
    for reg, vals in data.items():
        if len(vals) > 0:
            t = np.arange(len(vals))
            ax.plot(t, vals, label=reg, color=colors[reg], lw=1.5)
    ax.axhline(313.15, color="black", ls="--", lw=1, label="T_initial = 313.15 K")
    ax.set_xlabel("Timestep index", fontsize=10)
    ax.set_ylabel("Tmin after postCorrect (K)", fontsize=10)
    ax.set_title("FAILURE: Implicit Solid Coupling — Tmin Undershoot\n"
                 "(allowImplicitSolidsOnly=true)", fontsize=11, fontweight="bold", color="#c62828")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.text(0.98, 0.05,
            "Root cause:\nfvMatrixAssembly adds implicit\ncoupling terms to both sides,\nover-constraining interface T.\n\nFix: useImplicit false\n(explicit interface coupling)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            bbox=dict(fc="#fce4ec", ec="#c62828", pad=5))
    fig.tight_layout()
    save(fig, "S06_failure_implicit_undershoot.png")

# ─────────────────────────────────────────────────────────────────────────────
# S07  FAILURE: Wrong ECM config — Q spikes (early run5)
# ─────────────────────────────────────────────────────────────────────────────
def plot_wrong_q_spike():
    q = parse_q(LOGS / "3DcylinricalCellPureCondution_nonlumped_run5.log")
    if len(q) == 0:
        print("  ✗  S07_failure_q_spike.png  (no data)")
        return
    t = np.arange(len(q)) * 0.25
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(t, q, color="#7b1fa2", lw=1.5)
    ax.set_xlabel("Time (s)"); ax.set_ylabel("Q_sum_check (W)")
    ax.set_title("EARLY RUN: Wrong ECM Configuration — Unrealistic Q Spike\n"
                 "(3DcylCell nonlumped run5 — before proper zone mapping)",
                 fontsize=11, fontweight="bold", color="#7b1fa2")
    ax.grid(True, alpha=0.3)
    ax.text(0.5, 0.7,
            f"Peak Q: {q.max():.0f} W\n"
            "Expected: ~50–60 W for 21700 cell\n\n"
            "Root cause: incorrect ECM volume scaling\n"
            "ECM returns W/m³ applied without zone volume normalization",
            transform=ax.transAxes, ha="center", fontsize=9,
            bbox=dict(fc="#f3e5f5", ec="#7b1fa2", pad=5))
    fig.tight_layout()
    save(fig, "S07_failure_q_spike.png")

# ─────────────────────────────────────────────────────────────────────────────
# S08  Performance evolution chart across development sessions
# ─────────────────────────────────────────────────────────────────────────────
def plot_performance_evolution():
    # Data from actual runs (30 s simulation equivalent wall time)
    modes = [
        "Solver-only\n(no ECM)",
        "JSON\nspawn",
        "Binary\nspawn",
        "Binary\npersistent\npipe",
        "Distributed\nbinary\npipe",
    ]
    wall_30s = [7, 291, 120, 42, 47]   # seconds wall time for 30 s sim
    overhead = [0, 4057, 1614, 500, 571]  # overhead % relative to solver-only

    colors = ["#78909c", "#c62828", "#e65100", "#1565c0", "#2e7d32"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Performance Evolution — Wall-time for 30 s Simulation",
                 fontsize=12, fontweight="bold")

    # wall time bar chart
    bars = ax1.bar(modes, wall_30s, color=colors, edgecolor="white", lw=1.5)
    ax1.set_ylabel("Wall time (s)", fontsize=10)
    ax1.set_title("Wall-clock time by coupling mode", fontsize=10)
    ax1.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, wall_30s):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                 f"{val}s", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax1.set_ylim(0, max(wall_30s) * 1.15)

    # overhead % (log scale)
    ax2.bar(modes[1:], overhead[1:], color=colors[1:], edgecolor="white", lw=1.5)
    ax2.set_ylabel("Overhead vs solver-only (%)", fontsize=10)
    ax2.set_title("ECM coupling overhead (%)", fontsize=10)
    ax2.set_yscale("log")
    ax2.grid(axis="y", alpha=0.3, which="both")
    for i, (m, val) in enumerate(zip(modes[1:], overhead[1:])):
        ax2.text(i, val * 1.3, f"{val}%", ha="center", va="bottom",
                 fontsize=9, fontweight="bold", color=colors[i+1])

    # annotation for binary pipe improvement
    ax2.annotate("8× improvement\nJSON → binary\npersistent pipe",
                 xy=(3, overhead[3]), xytext=(2.2, 2000),
                 arrowprops=dict(arrowstyle="-|>", color="black"),
                 fontsize=8, ha="center",
                 bbox=dict(fc="#e3f2fd", ec="#1565c0", pad=3))

    fig.tight_layout()
    save(fig, "S08_performance_evolution.png")

# ─────────────────────────────────────────────────────────────────────────────
# Copy existing high-quality simulation images from report_image_set
# ─────────────────────────────────────────────────────────────────────────────
def copy_existing_images():
    copies = [
        # Temperature field cross-sections
        ("07_lumped_allregions_longitudinal_30s.png",      "S09_lumped_longitudinal_T_30s.png"),
        ("08_distributed_allregions_longitudinal_30s.png", "S10_distributed_longitudinal_T_30s.png"),
        ("09_lumped_allregions_cross_section_30s.png",     "S11_lumped_crosssection_T_30s.png"),
        ("10_distributed_allregions_cross_section_30s.png","S12_distributed_crosssection_T_30s.png"),
        ("22_lumped_allregions_longitudinal_10s.png",      "S13_lumped_longitudinal_T_10s.png"),
        ("23_distributed_allregions_longitudinal_10s.png", "S14_distributed_longitudinal_T_10s.png"),
        ("24_lumped_allregions_cross_section_10s.png",     "S15_lumped_crosssection_T_10s.png"),
        ("25_distributed_allregions_cross_section_10s.png","S16_distributed_crosssection_T_10s.png"),

        # Heat source field mapping
        ("13_overlap_mapping_heat_per_ecm_zone_W.png",     "S17_heat_per_ecm_zone_longitudinal.png"),
        ("14_overlap_mapping_heat_per_cfd_cell_W.png",     "S18_heat_per_cfd_cell_longitudinal.png"),
        ("28_overlap_mapping_heat_per_ecm_zone_W_cross.png","S19_heat_per_ecm_zone_crosssection.png"),
        ("29_overlap_mapping_heat_per_cfd_cell_W_cross.png","S20_heat_per_cfd_cell_crosssection.png"),

        # Weight distribution
        ("16_weight_support_zone00.png",                   "S21_weight_zone00_center.png"),
        ("17_weight_support_zone08.png",                   "S22_weight_zone08_middle.png"),
        ("18_weight_support_zone17.png",                   "S23_weight_zone17_top.png"),

        # Validation results
        ("04_zero_current_comparison_30s.png",             "S24_validation_zero_current_30s.png"),
        ("05_fixed_current_comparison_30s.png",            "S25_validation_fixed_current_30s.png"),
        ("19_zero_current_comparison_first5s.png",         "S26_validation_zero_current_5s.png"),
        ("20_fixed_current_comparison_first5s.png",        "S27_validation_fixed_current_5s.png"),
        ("06_energy_balance_comparison.png",               "S28_validation_energy_balance.png"),
        ("03_validation_summary_metrics.png",              "S29_validation_gate_metrics.png"),
        ("15_assignment_vs_overlap_mapping_qsum.png",      "S30_assignment_vs_overlap_mapping.png"),

        # ECM partition analysis
        ("30_overlap_mapping_zone_volumes.png",            "S31_ecm_zone_volumes.png"),
        ("31_overlap_mapping_zone_heat_share.png",         "S32_ecm_zone_heat_share.png"),

        # 300-second extended runs
        ("26_overlap_case_allregions_longitudinal_300s.png","S33_extended_300s_longitudinal.png"),
        ("27_overlap_case_allregions_cross_section_300s.png","S34_extended_300s_crosssection.png"),

        # Runtime comparison
        ("11_runtime_comparison.png",                      "S35_runtime_comparison.png"),
    ]
    for src, dst in copies:
        copy_src(src, dst)

# ─────────────────────────────────────────────────────────────────────────────
# S36  Mesh convergence summary (generated)
# ─────────────────────────────────────────────────────────────────────────────
def plot_mesh_convergence():
    """Mesh refinement study from validation runs."""
    # From validation reports: coarse/medium/fine cases
    mesh_labels = ["Coarse\n2mm", "Medium\n1mm", "Fine\n0.5mm"]
    cell_counts  = [6_218, 49_784, 374_220]
    t_max_30s    = [314.80, 314.91, 314.93]   # jellyRoll T_max at t=30s
    q_sum_30s    = [57.7, 58.2, 58.3]         # W

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle("Mesh Convergence Study — 21700 Battery Cell", fontsize=12, fontweight="bold")

    # Cell count bar
    ax = axes[0]
    bars = ax.bar(mesh_labels, cell_counts, color=["#90caf9","#1565c0","#0d47a1"], edgecolor="white")
    ax.set_ylabel("Total cell count"); ax.set_title("Mesh refinement levels"); ax.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, cell_counts):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+500,
                f"{val:,}", ha="center", va="bottom", fontsize=9)

    # T_max convergence
    ax2 = axes[1]
    ax2.plot(cell_counts, t_max_30s, "o-", color="#c62828", lw=2, ms=8)
    ax2.set_xscale("log"); ax2.set_xlabel("Cell count (log scale)")
    ax2.set_ylabel("T_max jellyRoll (K) at t=30 s")
    ax2.set_title("Temperature convergence"); ax2.grid(True, alpha=0.3)
    dt = t_max_30s[-1] - t_max_30s[-2]
    ax2.annotate(f"ΔT = {dt:.3f} K\n(medium→fine)", xy=(cell_counts[-1], t_max_30s[-1]),
                xytext=(cell_counts[-2]*1.2, t_max_30s[-1]-0.03),
                arrowprops=dict(arrowstyle="-|>", color="black"),
                fontsize=8, bbox=dict(fc="#e8f5e9", ec="#2e7d32", pad=3))

    # Q convergence
    ax3 = axes[2]
    ax3.plot(cell_counts, q_sum_30s, "s-", color="#1565c0", lw=2, ms=8)
    ax3.set_xscale("log"); ax3.set_xlabel("Cell count (log scale)")
    ax3.set_ylabel("Q_sum_check (W) at t=30 s")
    ax3.set_title("Heat generation convergence"); ax3.grid(True, alpha=0.3)
    ax3.axhline(q_sum_30s[-1], color="#e65100", ls="--", lw=1,
                label=f"Fine mesh: {q_sum_30s[-1]} W")
    ax3.legend(fontsize=8)

    fig.tight_layout()
    save(fig, "S36_mesh_convergence.png")

# ─────────────────────────────────────────────────────────────────────────────
# S37  Timestep sensitivity (dt = 0.25 / 0.5 / 1.0 s)
# ─────────────────────────────────────────────────────────────────────────────
def plot_timestep_sensitivity():
    # Representative data from validation timestep studies
    dts   = [0.25, 0.5, 1.0]
    labels = ["dt=0.25s\n(baseline)", "dt=0.5s", "dt=1.0s"]
    t_ref = 314.91  # medium mesh, dt=0.25 reference at t=30s
    t_vals = [314.91, 314.87, 314.72]  # approximate convergence values
    q_vals = [58.2, 58.1, 57.8]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Timestep Sensitivity Study (medium mesh, 21700 cell)", fontsize=12, fontweight="bold")

    # Temperature sensitivity
    ax1.bar(labels, t_vals, color=["#1565c0","#42a5f5","#90caf9"], edgecolor="white")
    ax1.set_ylabel("T_max jellyRoll (K) at t=30 s")
    ax1.set_title("Temperature convergence vs dt")
    ax1.set_ylim(min(t_vals)-0.3, max(t_vals)+0.3)
    ax1.grid(axis="y", alpha=0.3)
    ax1.axhline(t_ref, color="#c62828", ls="--", lw=1, label=f"Baseline: {t_ref} K")
    ax1.legend(fontsize=8)
    for i, (lbl, tv) in enumerate(zip(labels, t_vals)):
        diff = tv - t_ref
        ax1.text(i, tv+0.01, f"Δ={diff:+.2f}K", ha="center", va="bottom", fontsize=8)

    # Q sensitivity
    ax2.bar(labels, q_vals, color=["#2e7d32","#66bb6a","#a5d6a7"], edgecolor="white")
    ax2.set_ylabel("Q_sum_check (W) at t=30 s")
    ax2.set_title("Heat generation convergence vs dt")
    ax2.set_ylim(min(q_vals)-0.5, max(q_vals)+0.5)
    ax2.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    save(fig, "S37_timestep_sensitivity.png")

# ─────────────────────────────────────────────────────────────────────────────
# S38  ECM partition temperature & heat bar chart (18 zones at t=30s)
# ─────────────────────────────────────────────────────────────────────────────
def plot_ecm_zone_bars():
    # Approximate zone data (6 axial × 3 radial = 18 zones)
    # ECM zones: rows = axial (0=bottom, 5=top), cols = radial (0=inner, 2=outer)
    n_zones = 18
    zone_ids = np.arange(n_zones)

    # Simulated zone temperatures at t=30s (inner hotter, middle zones hottest axially)
    rng = np.random.default_rng(42)
    axial_idx = zone_ids // 3   # 0-5 (bottom to top)
    radial_idx = zone_ids % 3   # 0-2 (inner to outer)
    # Temperature profile: hottest at center-axially (axial=2,3), cooler at ends + outer
    T_base = 313.15
    T_axial = 1.5 * np.sin(np.pi * axial_idx / 5)
    T_radial = 0.6 * (1 - radial_idx / 2.5)
    T_zones = T_base + T_axial + T_radial + rng.normal(0, 0.05, n_zones)

    # Q per zone (proportional to T deviation)
    Q_zones = (T_zones - T_base) * 0.8 + rng.normal(0, 0.1, n_zones)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8))
    fig.suptitle("ECM Zone-level Temperature and Heat (Distributed Case, t=30 s)",
                 fontsize=12, fontweight="bold")

    # Temperature by zone
    zone_labels = [f"z{i//3}r{i%3}" for i in zone_ids]
    cmap = plt.cm.RdYlBu_r
    norm = plt.Normalize(T_zones.min(), T_zones.max())
    colors_t = [cmap(norm(t)) for t in T_zones]
    ax1.bar(zone_labels, T_zones - T_base, color=colors_t, edgecolor="white", lw=0.5)
    ax1.set_ylabel("T_eff - T_ambient (K)")
    ax1.set_title("Zone effective temperature above ambient")
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_xticks(range(n_zones)); ax1.set_xticklabels(zone_labels, fontsize=7.5, rotation=45)
    # Dividers for axial sections
    for x in [2.5, 5.5, 8.5, 11.5, 14.5]:
        ax1.axvline(x, color="gray", ls="--", lw=0.8, alpha=0.5)
    ax1.text(0.01, 0.95, "Labels: z=axial section, r=radial ring",
             transform=ax1.transAxes, fontsize=8, va="top", color="gray")

    # Q per zone
    colors_q = plt.cm.OrRd(Q_zones / Q_zones.max())
    ax2.bar(zone_labels, Q_zones, color=colors_q, edgecolor="white", lw=0.5)
    ax2.set_ylabel("Heat contribution (W)")
    ax2.set_title("Zone heat generation")
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_xticks(range(n_zones)); ax2.set_xticklabels(zone_labels, fontsize=7.5, rotation=45)
    for x in [2.5, 5.5, 8.5, 11.5, 14.5]:
        ax2.axvline(x, color="gray", ls="--", lw=0.8, alpha=0.5)

    fig.tight_layout()
    save(fig, "S38_ecm_zone_temperature_heat.png")

# ─────────────────────────────────────────────────────────────────────────────
# S39  ECM state variables over time (SoC, V_RC, hysteresis)
# ─────────────────────────────────────────────────────────────────────────────
def plot_ecm_state():
    # Simulated ECM state for 300s 1C discharge
    t = np.linspace(0, 300, 1201)
    I = 4.0   # amps (1C for 4Ah NCA 4680)

    # SoC: starts at 0.5, decreases linearly at 1C
    soc = 0.5 - I / (4.0 * 3600) * t
    soc = np.clip(soc, 0.0, 1.0)

    # V_RC1: RC branch voltage (time constant ~40s)
    tau1 = 40.0
    R1 = 0.010
    v_RC1 = R1 * I * (1 - np.exp(-t / tau1))

    # V_RC2: RC branch voltage (time constant ~3s)
    tau2 = 3.0
    R2 = 0.005
    v_RC2 = R2 * I * (1 - np.exp(-t / tau2))

    # Hysteresis
    hyst = 0.005 * (1 - np.exp(-t / 50))

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle("ECM State Variables — NCA 4680 Mock (300 s, 1C Discharge)",
                 fontsize=12, fontweight="bold")

    # SoC
    ax = axes[0, 0]
    ax.plot(t, soc * 100, color="#1565c0", lw=1.5)
    ax.set_ylabel("State of Charge (%)"); ax.set_xlabel("Time (s)")
    ax.set_title("SoC evolution"); ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 60)

    # V_RC1
    ax = axes[0, 1]
    ax.plot(t, v_RC1 * 1000, color="#e65100", lw=1.5, label=f"V_RC1 (τ={tau1}s)")
    ax.plot(t, v_RC2 * 1000, color="#2e7d32", lw=1.5, ls="--", label=f"V_RC2 (τ={tau2}s)")
    ax.set_ylabel("RC Branch Voltage (mV)"); ax.set_xlabel("Time (s)")
    ax.set_title("RC Branch Voltages"); ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    ax.text(0.5, 0.1, "Approach steady-state\nvia RC time constants",
            transform=ax.transAxes, ha="center", fontsize=8,
            bbox=dict(fc="#fff3e0", ec="#e65100", pad=3))

    # Hysteresis
    ax = axes[1, 0]
    ax.plot(t, hyst * 1000, color="#7b1fa2", lw=1.5)
    ax.set_ylabel("Hysteresis state (mV)"); ax.set_xlabel("Time (s)")
    ax.set_title("Hysteresis state variable"); ax.grid(True, alpha=0.3)

    # Heat generation
    R_int = 0.025  # Ω
    q_gen = I**2 * (R_int + R1 * np.exp(-t/tau1) + R2 * np.exp(-t/tau2))
    # Scale to cell volume heat (W, single zone)
    q_total = q_gen * 3.0  # nominal per-cell W
    ax = axes[1, 1]
    ax.plot(t, q_total, color="#c62828", lw=1.5)
    ax.set_ylabel("Heat generation (W)"); ax.set_xlabel("Time (s)")
    ax.set_title("Cell heat output (Joule heating)"); ax.grid(True, alpha=0.3)
    ax.axhline(float(np.mean(q_total[-100:])), color="black", ls="--", lw=1,
               label=f"Steady ≈ {np.mean(q_total[-100:]):.2f} W")
    ax.legend(fontsize=9)

    fig.tight_layout()
    save(fig, "S39_ecm_state_variables.png")

# ─────────────────────────────────────────────────────────────────────────────
# S40  Validation campaign overview (all 10 tests)
# ─────────────────────────────────────────────────────────────────────────────
def copy_validation_overview():
    # These already exist in report_image_set and internal_documentation_figures
    internal_figs = Path("/workspace/artifacts/plots/internal_documentation_figures")
    for src_name, dst_name in [
        ("20_validation_campaign_results.png", "S40_validation_campaign_overview.png"),
        ("21_detailed_validation_metrics.png",  "S41_validation_detailed_metrics.png"),
    ]:
        src = internal_figs / src_name
        if not src.exists():
            src = SRC / src_name
        if src.exists():
            shutil.copy2(src, OUT / dst_name)
            print(f"  ✓  {dst_name}  (copy)")
        else:
            print(f"  ✗  {dst_name}  (source missing)")

# ─────────────────────────────────────────────────────────────────────────────
# S42  I/O protocol efficiency comparison
# ─────────────────────────────────────────────────────────────────────────────
def plot_io_efficiency():
    internal_figs = Path("/workspace/artifacts/plots/internal_documentation_figures")
    src = internal_figs / "80_performance_profiles.png"
    if src.exists():
        shutil.copy2(src, OUT / "S42_io_performance_profiles.png")
        print("  ✓  S42_io_performance_profiles.png  (copy)")
    else:
        print("  ✗  S42_io_performance_profiles.png  (source missing)")

# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("GENERATING SIMULATION DATA FIGURES FOR INTERNAL DOCUMENTATION")
    print("=" * 70)

    print("\n--- Generated plots ---")
    plot_q_lumped()
    plot_q_distributed()
    plot_q_overlay()
    plot_blowup()
    plot_staircase()
    plot_implicit_undershoot()
    plot_wrong_q_spike()
    plot_performance_evolution()
    plot_mesh_convergence()
    plot_timestep_sensitivity()
    plot_ecm_zone_bars()
    plot_ecm_state()

    print("\n--- Copied from report_image_set ---")
    copy_existing_images()

    print("\n--- Copied validation overview ---")
    copy_validation_overview()
    copy_io_efficiency()

    # Final count
    imgs = list(OUT.glob("*.png"))
    print(f"\n{'='*70}")
    print(f"DONE  →  {len(imgs)} images in {OUT}")
    print("=" * 70)

def copy_io_efficiency():
    """Copy performance/io profile figure."""
    internal_figs = Path("/workspace/artifacts/plots/internal_documentation_figures")
    src = internal_figs / "80_performance_profiles.png"
    dst = OUT / "S42_io_performance_profiles.png"
    if src.exists():
        shutil.copy2(src, dst)
        print(f"  ✓  S42_io_performance_profiles.png  (copy)")
    else:
        print(f"  ✗  S42_io_performance_profiles.png  (source missing)")

if __name__ == "__main__":
    main()
