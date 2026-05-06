#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
VAL_ROOT = ROOT / "artifacts" / "validation"
PLOT_ROOT = ROOT / "artifacts" / "plots"
OUT_ROOT = ROOT / "artifacts" / "reports"


def _latest_json(mode: str, test: str) -> Path:
    files = sorted((VAL_ROOT / mode / test).glob("metrics_*.json"))
    if not files:
        raise RuntimeError(f"No metrics for {mode}/{test}")
    return files[-1]


def _load(mode: str, test: str) -> dict:
    return json.loads(_latest_json(mode, test).read_text())


def _qsum_series(log_path: Path) -> tuple[np.ndarray, np.ndarray]:
    times = []
    vals = []
    cur_t = None
    for line in log_path.read_text(errors="ignore").splitlines():
        m = re.match(r"^\s*Time\s*=\s*([0-9eE+\-.]+)\s*$", line)
        if m:
            cur_t = float(m.group(1))
            continue
        m = re.match(r"^\s*Q_sum_check\s+([0-9eE+\-.]+)\s*W?\s*$", line)
        if m and cur_t is not None:
            times.append(cur_t)
            vals.append(float(m.group(1)))
    return np.asarray(times), np.asarray(vals)


def _plot_timestep_overlay(lump: dict, dist: dict) -> tuple[Path, Path]:
    p_t = PLOT_ROOT / "forward_compare_timestep_tcap.png"
    p_q = PLOT_ROOT / "forward_compare_timestep_qsum.png"

    def _arr(d: dict, key: str) -> tuple[np.ndarray, np.ndarray]:
        runs = sorted(d["runs"], key=lambda r: float(r["delta_t"]), reverse=True)
        x = np.asarray([float(r["delta_t"]) for r in runs])
        y = np.asarray([float(r[key]) for r in runs])
        return x, y

    lx, lt = _arr(lump, "tcap_final_K")
    dx, dtv = _arr(dist, "tcap_final_K")
    lxq, lq = _arr(lump, "qsum_final_W")
    dxq, dq = _arr(dist, "qsum_final_W")

    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(lx, lt, marker="o", lw=1.8, label="Lumped")
    plt.plot(dx, dtv, marker="o", lw=1.8, label="Distributed")
    plt.gca().invert_xaxis()
    plt.xlabel("deltaT [s]")
    plt.ylabel("Final capacity-weighted T [K]")
    plt.title("Timestep Comparison: Final Temperature")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(p_t)
    plt.close()

    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(lxq, lq, marker="o", lw=1.8, label="Lumped")
    plt.plot(dxq, dq, marker="o", lw=1.8, label="Distributed")
    plt.gca().invert_xaxis()
    plt.xlabel("deltaT [s]")
    plt.ylabel("Final Q_sum_check [W]")
    plt.title("Timestep Comparison: Final Heat")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(p_q)
    plt.close()

    return p_t, p_q


def _plot_energy_overlay(lump: dict, dist: dict) -> Path:
    p = PLOT_ROOT / "forward_compare_energy.png"
    labels = ["Lumped", "Distributed"]
    err = [float(lump["energy_error_percent"]), float(dist["energy_error_percent"])]
    x = np.arange(2)
    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.bar(x, err, width=0.55, color=["#4c78a8", "#f58518"])
    plt.xticks(x, labels)
    plt.ylabel("Energy error [%]")
    plt.title("Adiabatic Energy Balance Error")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    return p


def _plot_mesh_overlay(lump: dict, dist: dict) -> Path:
    p = PLOT_ROOT / "forward_compare_mesh_tmax.png"

    def _xy(d: dict) -> tuple[np.ndarray, np.ndarray]:
        runs = sorted(d["runs"], key=lambda r: int(r["jellyRoll_cells"]))
        x = np.asarray([int(r["jellyRoll_cells"]) for r in runs], dtype=float)
        y = np.asarray([float(r["tmax_jellyRoll_K"]) for r in runs])
        return x, y

    lx, ly = _xy(lump)
    dx, dy = _xy(dist)
    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(lx, ly, marker="o", lw=1.8, label="Lumped")
    plt.plot(dx, dy, marker="o", lw=1.8, label="Distributed")
    plt.xlabel("jellyRoll cells [-]")
    plt.ylabel("Final Tmax(jellyRoll) [K]")
    plt.title("Mesh Comparison: Peak Temperature")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    return p


def _plot_ecm_series_overlay(lump: dict, dist: dict, out_name: str, title: str) -> Path:
    p = PLOT_ROOT / out_name
    lt, lq = _qsum_series(Path(lump["log"]))
    dt, dq = _qsum_series(Path(dist["log"]))
    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(lt, lq, lw=1.5, label="Lumped")
    plt.plot(dt, dq, lw=1.5, label="Distributed")
    plt.xlabel("time [s]")
    plt.ylabel("Q_sum_check [W]")
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    return p


def _case_table(rows: list[tuple[str, str]]) -> Table:
    data = [["Case Info", "Value"]] + [[k, v] for k, v in rows]
    t = Table(data, colWidths=[180, 320])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), "#E6E6E6"),
                ("GRID", (0, 0), (-1, -1), 0.4, "#777777"),
            ]
        )
    )
    return t


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    PLOT_ROOT.mkdir(parents=True, exist_ok=True)

    lt = _load("lumped_forward", "timestep")
    dtm = _load("distributed_forward", "timestep")
    le = _load("lumped_forward", "energy")
    de = _load("distributed_forward", "energy")
    lm = _load("lumped_forward", "mesh")
    dm = _load("distributed_forward", "mesh")
    lz = _load("lumped_forward", "ecm_zero")
    dz = _load("distributed_forward", "ecm_zero")
    lc = _load("lumped_forward", "ecm_current")
    dc = _load("distributed_forward", "ecm_current")

    p_ts_t, p_ts_q = _plot_timestep_overlay(lt, dtm)
    p_en = _plot_energy_overlay(le, de)
    p_mesh = _plot_mesh_overlay(lm, dm)
    p_zero = _plot_ecm_series_overlay(lz, dz, "forward_compare_ecm_zero_qsum.png", "ECM Zero-Current: Q_sum_check")
    p_cur = _plot_ecm_series_overlay(lc, dc, "forward_compare_ecm_current_qsum.png", "ECM Fixed-Current: Q_sum_check")

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    pdf = OUT_ROOT / f"lumped_vs_distributed_forward_validation_{stamp}.pdf"
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, title="Lumped vs Distributed Forward Validation")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Lumped vs Distributed Forward Validation", styles["Title"]),
        Spacer(1, 8),
        Paragraph("Plot-first comparison report. Tables contain case metadata only.", styles["Normal"]),
        Spacer(1, 10),
    ]

    story.append(Paragraph("Timestep Comparison", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Lumped metrics", str(_latest_json("lumped_forward", "timestep"))),
                ("Distributed metrics", str(_latest_json("distributed_forward", "timestep"))),
                ("Distributed window", "0-3 s consistency"),
                ("maxDi default", "100"),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_ts_t), width=520, height=255))
    story.append(Spacer(1, 6))
    story.append(Image(str(p_ts_q), width=520, height=255))
    story.append(PageBreak())

    story.append(Paragraph("Adiabatic Energy Comparison", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Lumped metrics", str(_latest_json("lumped_forward", "energy"))),
                ("Distributed metrics", str(_latest_json("distributed_forward", "energy"))),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_en), width=520, height=255))
    story.append(PageBreak())

    story.append(Paragraph("Mesh Comparison", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Lumped metrics", str(_latest_json("lumped_forward", "mesh"))),
                ("Distributed metrics", str(_latest_json("distributed_forward", "mesh"))),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_mesh), width=520, height=255))
    story.append(PageBreak())

    story.append(Paragraph("ECM Zero-Current Comparison", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Lumped metrics", str(_latest_json("lumped_forward", "ecm_zero"))),
                ("Distributed metrics", str(_latest_json("distributed_forward", "ecm_zero"))),
                ("Distributed gate", "steady-state after 10 s"),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_zero), width=520, height=255))
    story.append(PageBreak())

    story.append(Paragraph("ECM Fixed-Current Comparison", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Lumped metrics", str(_latest_json("lumped_forward", "ecm_current"))),
                ("Distributed metrics", str(_latest_json("distributed_forward", "ecm_current"))),
                ("Distributed smoothness gate", "post-warmup d2Q after 5 s"),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_cur), width=520, height=255))

    doc.build(story)
    print(pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
