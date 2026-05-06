#!/usr/bin/env python3
"""
plot_dist_taufix_vs_validation.py
Compare distributed tau-fix run vs validation data and lumped reference.
4-panel: T overlay, Q overlay, deltaT, deltaQ.
"""
from __future__ import annotations
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf as pdf_backend

VAL_CSV   = Path("/workspace/projectConstraintsParameters/validationData.csv")
LUMP_CSV  = Path("/workspace/artifacts/h_sweep/caseLong_h_sweep_20260501_161811/h_110p0/ecm_wrapper_summary.csv")
DIST_CSV  = Path("/workspace/rev4/dist_3600_fulllog/ecm/heatBalanceHistory.csv")
OUT_PDF   = Path("/workspace/artifacts/plots/dist_socfix_vs_validation.pdf")
OUT_PNG   = Path("/workspace/artifacts/plots/dist_socfix_vs_validation.png")


def load_validation(path):
    t, T_c, Q = [], [], []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t.append(float(row["t_ss"]))
            T_c.append(float(row["T_cell_K"]) - 273.15)
            Q.append(float(row["Q_cell_W"]))
    return np.array(t), np.array(T_c), np.array(Q)


def load_lumped(path):
    t, T_c, Q = [], [], []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tv = float(row["time_s"])
            if t and tv <= t[-1]:
                t.clear(); T_c.clear(); Q.clear()
            t.append(tv)
            T_c.append(float(row["T_feedback_degC"]))
            Q.append(float(row["Q_GEN_W"]))
    return np.array(t), np.array(T_c), np.array(Q)


def load_dist(path):
    t, T_c, Q = [], [], []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tv = float(row["time_s"])
            if t and tv <= t[-1]:
                t.clear(); T_c.clear(); Q.clear()
            t.append(tv)
            T_c.append(float(row["t_eff_k"]) - 273.15)
            Q.append(float(row["q_raw_w"]))
    return np.array(t), np.array(T_c), np.array(Q)


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def bias(a, b):
    return float(np.mean(a - b))


def main():
    plt.style.use("seaborn-v0_8-whitegrid")

    val_t,  val_T,  val_Q  = load_validation(VAL_CSV)
    lump_t, lump_T, lump_Q = load_lumped(LUMP_CSV)
    dist_t, dist_T, dist_Q = load_dist(DIST_CSV)

    t_end = max(val_t.max(), lump_t.max(), dist_t.max())

    # Interpolate all series to validation time base for error metrics
    lump_T_i = np.interp(lump_t, val_t, val_T)
    lump_Q_i = np.interp(lump_t, val_t, val_Q)
    dist_T_i = np.interp(dist_t, val_t, val_T)
    dist_Q_i = np.interp(dist_t, val_t, val_Q)

    rT_lump = rmse(lump_T, lump_T_i)
    rQ_lump = rmse(lump_Q, lump_Q_i)
    bT_lump = bias(lump_T, lump_T_i)
    bQ_lump = bias(lump_Q, lump_Q_i)

    rT_dist = rmse(dist_T, dist_T_i)
    rQ_dist = rmse(dist_Q, dist_Q_i)
    bT_dist = bias(dist_T, dist_T_i)
    bQ_dist = bias(dist_Q, dist_Q_i)

    C_VAL  = "#111111"
    C_LUMP = "#2e8b57"
    C_DIST = "#005f73"

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    with pdf_backend.PdfPages(str(OUT_PDF)) as pdf:

        # ── Page 1: overlays ────────────────────────────────────────────────
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.subplots_adjust(hspace=0.42)
        fig.suptitle(
            "Distributed ECM (SOC-fix) vs Validation — 3600 s full run",
            fontweight="bold", fontsize=13
        )

        ax = axes[0]
        ax.plot(val_t,  val_T,  color=C_VAL,  lw=2.2, ls="--",
                label="Validation (exp)", zorder=10)
        ax.plot(lump_t, lump_T, color=C_LUMP, lw=1.8,
                label=f"Lumped h=110  RMSE={rT_lump:.3f} degC  bias={bT_lump:+.3f} degC",
                zorder=5)
        ax.plot(dist_t, dist_T, color=C_DIST, lw=1.5,
                label=f"Distributed (SOC-fix)  RMSE={rT_dist:.3f} degC  bias={bT_dist:+.3f} degC")
        ax.set_title("Cell Temperature", fontweight="bold")
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Temperature [degC]")
        ax.set_xlim(0, t_end)
        ax.legend(frameon=True, fontsize=8)

        ax = axes[1]
        ax.plot(val_t,  val_Q,  color=C_VAL,  lw=2.2, ls="--",
                label="Validation (exp)", zorder=10)
        ax.plot(lump_t, lump_Q, color=C_LUMP, lw=1.8,
                label=f"Lumped h=110  RMSE={rQ_lump:.4f} W  bias={bQ_lump:+.4f} W",
                zorder=5)
        ax.plot(dist_t, dist_Q, color=C_DIST, lw=1.5,
                label=f"Distributed (SOC-fix)  RMSE={rQ_dist:.4f} W  bias={bQ_dist:+.4f} W")
        ax.set_title("ECM Heat Generation", fontweight="bold")
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Heat [W]")
        ax.set_xlim(0, t_end)
        ax.legend(frameon=True, fontsize=8)

        pdf.savefig(fig, bbox_inches="tight")
        fig.savefig(str(OUT_PNG), dpi=150, bbox_inches="tight")
        plt.close(fig)

        # ── Page 2: differences ─────────────────────────────────────────────
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.subplots_adjust(hspace=0.42)
        fig.suptitle(
            "Model minus Validation — Distributed ECM (SOC-fix)",
            fontweight="bold", fontsize=13
        )

        ax = axes[0]
        ax.plot(lump_t, lump_T - lump_T_i, color=C_LUMP, lw=1.8, label="Lumped h=110")
        ax.plot(dist_t, dist_T - dist_T_i, color=C_DIST, lw=1.5, label="Distributed (SOC-fix)")
        ax.axhline(0, color="#555", lw=1.0, ls="--", alpha=0.8)
        ax.set_title("Temperature Error: Model - Validation", fontweight="bold")
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("DeltaT [degC]")
        ax.set_xlim(0, t_end)
        ax.legend(frameon=True, fontsize=9)

        ax = axes[1]
        ax.plot(lump_t, lump_Q - lump_Q_i, color=C_LUMP, lw=1.8, label="Lumped h=110")
        ax.plot(dist_t, dist_Q - dist_Q_i, color=C_DIST, lw=1.5, label="Distributed (SOC-fix)")
        ax.axhline(0, color="#555", lw=1.0, ls="--", alpha=0.8)
        ax.set_title("Heat Generation Error: Model - Validation", fontweight="bold")
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("DeltaQ [W]")
        ax.set_xlim(0, t_end)
        ax.legend(frameon=True, fontsize=9)

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    print(f"\nSaved: {OUT_PDF}")
    print(f"Saved: {OUT_PNG}")
    print()
    print(f"{'Model':<35} {'T RMSE':>10} {'T Bias':>10} {'Q RMSE':>10} {'Q Bias':>10}")
    print(f"{'Lumped h=110':<35} {rT_lump:>10.4f} {bT_lump:>+10.4f} {rQ_lump:>10.4f} {bQ_lump:>+10.4f}")
    print(f"{'Distributed (SOC-fix)':<35} {rT_dist:>10.4f} {bT_dist:>+10.4f} {rQ_dist:>10.4f} {bQ_dist:>+10.4f}")


if __name__ == "__main__":
    main()
