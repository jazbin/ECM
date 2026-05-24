#!/usr/bin/env python3
"""
plot_multicell_comparison.py

Four-panel comparison plot for multi-battery cell simulations.

Panels:
  1. Temperature (vol-avg T per cell + experiment if available)
  2. Heat generation (Q per cell + Q_pack)
  3. Terminal voltage (V per cell + V_pack + experiment if available)
  4. SOC (per cell + pack mean)

Usage:
    python3 tools/plot_multicell_comparison.py \
        --voltage-history ecm/cell0/voltageHistory.csv ecm/cell1/voltageHistory.csv \
        [--volAvgT-csv cell0:postProcessing/jellyRoll_0/jellyRollMeanT/0/volFieldValue.dat] \
        [--exp-csv constant/electrical_inputs_experimental_10C_discharge.csv] \
        [--series | --parallel] \
        [--cell-labels cell0,cell1] \
        [--output artifacts/plots/multicell_comparison.pdf]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path("/workspace")
PLOTS = ROOT / "artifacts" / "plots"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

Q_NOM_AH = 5.0

# Color palette for up to 6 cells
CELL_COLORS = ["#ca6702", "#005f73", "#9b2226", "#0a9396", "#ae2012", "#94d2bd"]
C_PACK = "#001219"
C_EXP = "#111111"


def load_voltage_history(path: str, cell_label: str = "") -> pd.DataFrame:
    df = pd.read_csv(path)
    if "cell_id" not in df.columns or df["cell_id"].isnull().all():
        parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
        df["cell_id"] = cell_label if cell_label else (parent or "cell0")
    elif cell_label:
        df["cell_id"] = cell_label
    df["cell_id"] = df["cell_id"].fillna("").astype(str)
    for col in ["v_common_v", "v_branch_min_v", "v_branch_max_v", "q_total_w", "t_eff_k", "n_partitions", "current_a"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def load_volAvgT(spec: str) -> tuple[str, np.ndarray, np.ndarray]:
    """
    Parse a spec like "cell0:path/to/volFieldValue.dat" or just a file path.
    Handles glob patterns for multiple time-directory shards.
    Returns (cell_label, time_array, T_celsius_array).
    """
    if ":" in spec:
        label, pattern = spec.split(":", 1)
    else:
        label = os.path.basename(os.path.dirname(os.path.abspath(spec)))
        pattern = spec

    seen: dict[float, float] = {}
    for fpath in sorted(glob.glob(pattern)):
        for line in open(fpath):
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                seen[float(parts[0])] = float(parts[1])

    if not seen:
        sys.stderr.write(f"[plot_multicell] WARN: no data found in: {pattern}\n")
        return label, np.array([]), np.array([])

    t_arr = np.array(sorted(seen.keys()))
    T_arr = np.array([seen[t] for t in t_arr]) - 273.15
    return label, t_arr, T_arr


def load_experiment(path: str) -> dict | None:
    """Try to load experimental voltage + temperature from an electrical inputs CSV."""
    if not path or not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None

    # Detect column names flexibly
    t_col = next((c for c in df.columns if "time" in c.lower()), None)
    v_col = next((c for c in df.columns if "voltage" in c.lower() or "v_exp" in c.lower()), None)
    T_col = next((c for c in df.columns if "temp" in c.lower() or "T_" in c), None)
    if t_col is None or v_col is None:
        return None
    out = dict(t=df[t_col].values, V=df[v_col].values)
    if T_col:
        out["T_C"] = df[T_col].values - 273.15 if df[T_col].mean() > 100 else df[T_col].values
    return out


def compute_soc(df: pd.DataFrame) -> np.ndarray:
    """
    Estimate SOC per row from q_total_w and current_a by numerical integration.
    Falls back to 1 - cumulative_charge / Q_nom if possible, otherwise returns NaN.
    """
    t = df["time_s"].values
    I = df["current_a"].values
    if len(t) < 2 or np.all(I == 0):
        return np.full(len(t), np.nan)
    # Trapezoidal cumulative charge (Ah)
    dt = np.diff(t, prepend=t[0])
    charge = np.cumsum(I * dt) / 3600.0
    soc = 1.0 - charge / Q_NOM_AH
    return np.clip(soc, 0.0, 1.0)


def make_figure(
    cell_dfs: list[tuple[str, pd.DataFrame]],      # (label, df)
    cell_T: list[tuple[str, np.ndarray, np.ndarray]] | None,  # (label, t, T_C)
    exp: dict | None,
    series_mode: bool,
    title: str,
) -> plt.Figure:
    fig, axes = plt.subplots(4, 1, figsize=(10, 14), sharex=False)
    ax_T, ax_Q, ax_V, ax_SOC = axes

    # ── Panel 1: Temperature ─────────────────────────────────────────────────
    ax_T.set_ylabel("Temperature (°C)")
    ax_T.set_title(title, fontsize=11, fontweight="bold")

    if cell_T:
        for i, (lbl, t_arr, T_arr) in enumerate(cell_T):
            if len(t_arr) > 0:
                color = CELL_COLORS[i % len(CELL_COLORS)]
                ax_T.plot(t_arr, T_arr, color=color, label=f"{lbl} vol-avg T", lw=1.5)
    else:
        # Fall back to T_eff_K from voltageHistory
        for i, (lbl, df) in enumerate(cell_dfs):
            color = CELL_COLORS[i % len(CELL_COLORS)]
            t = df["time_s"].values
            T = df["t_eff_k"].values - 273.15
            ax_T.plot(t, T, color=color, label=f"{lbl} T_eff", lw=1.5, ls="--")

    if exp and "T_C" in exp:
        ax_T.plot(exp["t"], exp["T_C"], color=C_EXP, lw=1.0, ls=":", label="Experiment")

    ax_T.legend(loc="upper left", fontsize=8, ncol=2)
    ax_T.grid(True, alpha=0.3)

    # ── Panel 2: Heat Generation ─────────────────────────────────────────────
    ax_Q.set_ylabel("Heat generation (W)")
    q_pack_total = None

    for i, (lbl, df) in enumerate(cell_dfs):
        color = CELL_COLORS[i % len(CELL_COLORS)]
        t = df["time_s"].values
        Q = df["q_total_w"].values
        ax_Q.plot(t, Q, color=color, label=f"{lbl} Q", lw=1.5)
        if q_pack_total is None:
            q_pack_total = pd.Series(Q, index=t)
        else:
            q_pack_total = q_pack_total.add(pd.Series(Q, index=t), fill_value=0.0)

    if q_pack_total is not None and len(cell_dfs) > 1:
        ax_Q.plot(
            q_pack_total.index, q_pack_total.values,
            color=C_PACK, lw=2.0, ls="-", label="Q_pack (total)", zorder=5,
        )

    ax_Q.legend(loc="upper left", fontsize=8, ncol=2)
    ax_Q.grid(True, alpha=0.3)

    # ── Panel 3: Terminal Voltage ────────────────────────────────────────────
    ax_V.set_ylabel("Terminal voltage (V)")
    v_pack = None

    for i, (lbl, df) in enumerate(cell_dfs):
        color = CELL_COLORS[i % len(CELL_COLORS)]
        t = df["time_s"].values
        V = df["v_common_v"].values
        ax_V.plot(t, V, color=color, label=f"{lbl} V", lw=1.5)
        if series_mode:
            if v_pack is None:
                v_pack = pd.Series(V, index=t)
            else:
                v_pack = v_pack.add(pd.Series(V, index=t), fill_value=0.0)
        else:
            # Parallel: V_pack is the common voltage (same for all)
            if v_pack is None:
                v_pack = pd.Series(V, index=t)

    if v_pack is not None and len(cell_dfs) > 1:
        pack_label = "V_pack (series sum)" if series_mode else "V_pack (parallel)"
        ax_V.plot(
            v_pack.index, v_pack.values,
            color=C_PACK, lw=2.0, ls="-", label=pack_label, zorder=5,
        )

    if exp:
        ax_V.plot(exp["t"], exp["V"], color=C_EXP, lw=1.0, ls=":", label="Experiment", zorder=4)

    ax_V.legend(loc="upper right", fontsize=8, ncol=2)
    ax_V.grid(True, alpha=0.3)

    # ── Panel 4: SOC ─────────────────────────────────────────────────────────
    ax_SOC.set_ylabel("SOC")
    ax_SOC.set_xlabel("Time (s)")
    soc_all = []

    for i, (lbl, df) in enumerate(cell_dfs):
        color = CELL_COLORS[i % len(CELL_COLORS)]
        t = df["time_s"].values
        soc = compute_soc(df)
        if not np.all(np.isnan(soc)):
            ax_SOC.plot(t, soc, color=color, label=f"{lbl} SOC", lw=1.5)
            soc_all.append(pd.Series(soc, index=t))

    if len(soc_all) > 1:
        soc_df = pd.concat(soc_all, axis=1)
        soc_mean = soc_df.mean(axis=1)
        ax_SOC.plot(
            soc_mean.index, soc_mean.values,
            color=C_PACK, lw=2.0, ls="-", label="SOC pack mean", zorder=5,
        )

    ax_SOC.set_ylim(bottom=0.0)
    ax_SOC.legend(loc="upper right", fontsize=8, ncol=2)
    ax_SOC.grid(True, alpha=0.3)

    fig.tight_layout(pad=2.0)
    return fig


def main():
    ap = argparse.ArgumentParser(
        description="Four-panel multi-cell comparison plot."
    )
    ap.add_argument(
        "--voltage-history", "-v",
        nargs="+",
        required=True,
        help="Per-cell voltageHistory CSV files.",
    )
    ap.add_argument(
        "--volAvgT-csv",
        nargs="*",
        default=[],
        help="Per-cell vol-avg T specs: 'cell0:path/to/volFieldValue*.dat'. "
             "May be repeated for each cell.",
    )
    ap.add_argument(
        "--exp-csv",
        default="",
        help="Experimental CSV with time, voltage, temperature columns (optional).",
    )
    ap.add_argument(
        "--series",
        dest="series",
        action="store_true",
        default=True,
        help="Series pack: V_pack = sum(V_cell). [default]",
    )
    ap.add_argument(
        "--parallel",
        dest="series",
        action="store_false",
        help="Parallel pack: V_pack = V_common.",
    )
    ap.add_argument(
        "--cell-labels",
        default="",
        help="Comma-separated override labels for cells (e.g. 'cell0,cell1').",
    )
    ap.add_argument(
        "--output", "-o",
        default="",
        help="Output path prefix (no extension). Saves .pdf and .png.",
    )
    ap.add_argument(
        "--title",
        default="",
        help="Plot title override.",
    )
    args = ap.parse_args()

    cell_labels = [s.strip() for s in args.cell_labels.split(",")] if args.cell_labels else []

    # Load per-cell voltageHistory
    cell_dfs = []
    for i, path in enumerate(args.voltage_history):
        if not os.path.exists(path):
            sys.stderr.write(f"[plot_multicell] ERROR: file not found: {path}\n")
            sys.exit(1)
        label = cell_labels[i] if i < len(cell_labels) else ""
        df = load_voltage_history(path, cell_label=label)
        # Use cell_id from file if no override
        if not label:
            label = df["cell_id"].iloc[0] if len(df) > 0 else f"cell{i}"
        cell_dfs.append((label, df))

    # Load vol-avg T if provided
    cell_T = [load_volAvgT(spec) for spec in (args.volAvgT_csv or [])]
    cell_T = [(lbl, t, T) for (lbl, t, T) in cell_T if len(t) > 0]

    # Load experiment
    exp = load_experiment(args.exp_csv)
    if exp:
        sys.stderr.write(f"[plot_multicell] Loaded experiment data: {len(exp['t'])} rows\n")

    # Build title
    config = "series" if args.series else "parallel"
    n_cells = len(cell_dfs)
    title = args.title or f"{n_cells}-cell {config} pack — multi-cell comparison"

    fig = make_figure(
        cell_dfs=cell_dfs,
        cell_T=cell_T if cell_T else None,
        exp=exp,
        series_mode=args.series,
        title=title,
    )

    # Output paths
    if args.output:
        base = args.output
    else:
        PLOTS.mkdir(parents=True, exist_ok=True)
        base = str(PLOTS / f"multicell_comparison_{STAMP}")

    pdf_path = base + ".pdf"
    png_path = base + ".png"

    with PdfPages(pdf_path) as pdf:
        pdf.savefig(fig, bbox_inches="tight")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    sys.stdout.write(f"[plot_multicell] Saved: {pdf_path}\n")
    sys.stdout.write(f"[plot_multicell] Saved: {png_path}\n")


if __name__ == "__main__":
    main()
