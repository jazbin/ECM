#!/usr/bin/env python3
"""
aggregate_multicell_voltage.py

Aggregate per-cell voltageHistory CSV files from a multi-battery simulation
into a single summary CSV.

Usage:
    python3 tools/aggregate_multicell_voltage.py \
        ecm/cell0/voltageHistory.csv \
        ecm/cell1/voltageHistory.csv \
        [--output artifacts/plots/multicell_voltage_summary.csv] \
        [--series]

Arguments:
    files           Two or more per-cell voltageHistory CSV paths
    --output, -o    Output CSV path (default: artifacts/plots/multicell_voltage_summary_YYYYMMDD_HHMMSS.csv)
    --series        Compute V_pack = sum of V_cell (series configuration; default)
    --parallel      For parallel config: V_pack = V_cell (common terminal voltage, no sum)
    --cell-labels   Comma-separated cell labels to override the cell_id column values

Output columns:
    time_s, cell_id, v_common_v, v_branch_min_v, v_branch_max_v, q_total_w, t_eff_k, n_partitions
    Plus summary columns per timestep (same row for each cell):
        v_pack_v        (series: sum; parallel: max/common)
        q_pack_w        (sum of Q across all cells)
        soc_pack_mean   (mean SOC estimate from v_common_v proxy)
        t_delta_k       (max - min T_eff_K across cells at same timestep)
"""

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd


def load_voltage_history(path: str, cell_label: str = "") -> pd.DataFrame:
    """Load a voltageHistory.csv, attaching a cell_id if not present or overriding it."""
    df = pd.read_csv(path)
    if "cell_id" not in df.columns or df["cell_id"].isnull().all():
        # Infer cell_id from path if not in file
        if cell_label:
            df["cell_id"] = cell_label
        else:
            # Guess from parent directory name or filename
            parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
            df["cell_id"] = parent if parent else os.path.splitext(os.path.basename(path))[0]
    elif cell_label:
        df["cell_id"] = cell_label
    # Ensure cell_id is a string
    df["cell_id"] = df["cell_id"].fillna("").astype(str)
    return df


def aggregate(
    files: list,
    cell_labels: list = None,
    series_mode: bool = True,
) -> pd.DataFrame:
    """
    Load all per-cell voltageHistory files and merge into a single DataFrame.

    Returns a combined DataFrame with all rows tagged by cell_id, plus pack-level
    summary columns (v_pack_v, q_pack_w, t_delta_k) computed per unique timestep.
    """
    dfs = []
    for i, path in enumerate(files):
        label = cell_labels[i] if cell_labels and i < len(cell_labels) else ""
        df = load_voltage_history(path, cell_label=label)
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    combined.sort_values(["time_s", "cell_id"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    # Ensure required columns exist with defaults
    for col, default in [
        ("v_common_v", 0.0),
        ("v_branch_min_v", 0.0),
        ("v_branch_max_v", 0.0),
        ("q_total_w", 0.0),
        ("t_eff_k", 0.0),
        ("n_partitions", 0),
        ("current_a", 0.0),
    ]:
        if col not in combined.columns:
            combined[col] = default
        else:
            combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(default)

    # Compute pack-level aggregates per timestep
    grp = combined.groupby("time_s", sort=True)

    if series_mode:
        # Series: pack voltage = sum of all cell voltages
        v_pack = grp["v_common_v"].sum()
    else:
        # Parallel: all cells share same terminal voltage → use max (should be ~equal)
        v_pack = grp["v_common_v"].max()

    q_pack = grp["q_total_w"].sum()
    t_max = grp["t_eff_k"].max()
    t_min = grp["t_eff_k"].min()
    t_delta = t_max - t_min

    pack_df = pd.DataFrame({
        "time_s": v_pack.index,
        "v_pack_v": v_pack.values,
        "q_pack_w": q_pack.values,
        "t_delta_k": t_delta.values,
    })

    combined = combined.merge(pack_df, on="time_s", how="left")
    return combined


def main():
    ap = argparse.ArgumentParser(
        description="Aggregate per-cell voltageHistory CSVs into a multi-cell summary."
    )
    ap.add_argument(
        "files",
        nargs="+",
        help="Per-cell voltageHistory CSV files (two or more).",
    )
    ap.add_argument(
        "--output", "-o",
        default="",
        help="Output CSV path. Defaults to artifacts/plots/multicell_voltage_summary_YYYYMMDD_HHMMSS.csv",
    )
    ap.add_argument(
        "--series",
        dest="series",
        action="store_true",
        default=True,
        help="Series configuration: V_pack = sum(V_cell). [default]",
    )
    ap.add_argument(
        "--parallel",
        dest="series",
        action="store_false",
        help="Parallel configuration: V_pack = V_common (shared terminal voltage).",
    )
    ap.add_argument(
        "--cell-labels",
        default="",
        help="Comma-separated cell labels to override cell_id (e.g. 'cell0,cell1,cell2').",
    )
    args = ap.parse_args()

    if len(args.files) < 1:
        ap.error("At least one voltageHistory CSV file is required.")

    cell_labels = [s.strip() for s in args.cell_labels.split(",")] if args.cell_labels else []

    for f in args.files:
        if not os.path.exists(f):
            sys.stderr.write(f"[aggregate_multicell] ERROR: file not found: {f}\n")
            sys.exit(1)

    combined = aggregate(
        files=args.files,
        cell_labels=cell_labels or None,
        series_mode=args.series,
    )

    if args.output:
        out_path = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "artifacts", "plots",
        )
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"multicell_voltage_summary_{ts}.csv")

    combined.to_csv(out_path, index=False)
    sys.stdout.write(f"[aggregate_multicell] Written {len(combined)} rows → {out_path}\n")

    # Print summary statistics
    unique_cells = combined["cell_id"].unique()
    sys.stdout.write(f"[aggregate_multicell] {len(unique_cells)} cells: {list(unique_cells)}\n")
    config = "series" if args.series else "parallel"
    t_range = combined["time_s"]
    sys.stdout.write(
        f"[aggregate_multicell] Config={config}, "
        f"time={t_range.min():.1f}–{t_range.max():.1f} s, "
        f"V_pack range={combined['v_pack_v'].min():.3f}–{combined['v_pack_v'].max():.3f} V, "
        f"Q_pack range={combined['q_pack_w'].min():.2f}–{combined['q_pack_w'].max():.2f} W\n"
    )


if __name__ == "__main__":
    main()
