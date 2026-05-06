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
IN_ROOT = ROOT / "artifacts" / "validation" / "distributed_forward"
OUT_ROOT = ROOT / "artifacts" / "reports"
PLOT_ROOT = ROOT / "artifacts" / "plots"


def _latest_json(test: str) -> Path:
    files = sorted((IN_ROOT / test).glob("metrics_*.json"))
    if not files:
        raise RuntimeError(f"No metrics JSON for {test}")
    return files[-1]


def _load(test: str) -> dict:
    return json.loads(_latest_json(test).read_text())


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


def _plot_timestep(metrics: dict) -> tuple[Path, Path]:
    runs = sorted(metrics["runs"], key=lambda r: float(r["delta_t"]), reverse=True)
    dts = np.asarray([float(r["delta_t"]) for r in runs])
    tcap = np.asarray([float(r["tcap_final_K"]) for r in runs])
    qsum = np.asarray([float(r["qsum_final_W"]) for r in runs])

    p1 = PLOT_ROOT / "distributed_forward_timestep_tcap.png"
    p2 = PLOT_ROOT / "distributed_forward_timestep_qsum.png"

    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(dts, tcap, marker="o", lw=1.8)
    plt.gca().invert_xaxis()
    plt.xlabel("deltaT [s]")
    plt.ylabel("Final capacity-weighted T [K]")
    plt.title("Distributed Timestep Check: Final Temperature vs deltaT")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(p1)
    plt.close()

    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(dts, qsum, marker="o", lw=1.8)
    plt.gca().invert_xaxis()
    plt.xlabel("deltaT [s]")
    plt.ylabel("Final Q_sum_check [W]")
    plt.title("Distributed Timestep Check: Final Heat vs deltaT")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(p2)
    plt.close()

    return p1, p2


def _plot_energy(metrics: dict) -> Path:
    p = PLOT_ROOT / "distributed_forward_energy_balance.png"
    expected = float(metrics["energy_expected_J"])
    stored = float(metrics["energy_stored_J"])
    err = float(metrics["energy_error_percent"])
    x = np.arange(2)
    y = np.asarray([expected, stored])
    plt.figure(figsize=(7.2, 4.0), dpi=170)
    plt.bar(x, y, width=0.55, color=["#4c78a8", "#f58518"])
    plt.xticks(x, ["Expected", "Stored"])
    plt.ylabel("Energy [J]")
    plt.title(f"Distributed Adiabatic Energy Balance (error = {err:.3f}%)")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    return p


def _plot_mesh(metrics: dict) -> tuple[Path, Path]:
    runs = sorted(metrics["runs"], key=lambda r: int(r["jellyRoll_cells"]))
    cells = np.asarray([int(r["jellyRoll_cells"]) for r in runs], dtype=float)
    tmax = np.asarray([float(r["tmax_jellyRoll_K"]) for r in runs])
    tcap = np.asarray([float(r["tcap_K"]) for r in runs])
    p1 = PLOT_ROOT / "distributed_forward_mesh_tmax.png"
    p2 = PLOT_ROOT / "distributed_forward_mesh_tcap.png"

    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(cells, tmax, marker="o", lw=1.8)
    plt.xlabel("jellyRoll cells [-]")
    plt.ylabel("Final Tmax(jellyRoll) [K]")
    plt.title("Distributed Mesh Check: Peak Temperature vs Mesh Size")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(p1)
    plt.close()

    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(cells, tcap, marker="o", lw=1.8)
    plt.xlabel("jellyRoll cells [-]")
    plt.ylabel("Final capacity-weighted T [K]")
    plt.title("Distributed Mesh Check: Capacity-Weighted T vs Mesh Size")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(p2)
    plt.close()
    return p1, p2


def _plot_ecm_series(metrics: dict, out_name: str, title: str) -> Path:
    t, q = _qsum_series(Path(metrics["log"]))
    p = PLOT_ROOT / out_name
    plt.figure(figsize=(7.2, 3.8), dpi=170)
    plt.plot(t, q, lw=1.4)
    plt.xlabel("time [s]")
    plt.ylabel("Q_sum_check [W]")
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    return p


def _case_table(rows: list[tuple[str, str]]) -> Table:
    data = [["Case Info", "Value"]] + [[k, v] for k, v in rows]
    tbl = Table(data, colWidths=[190, 310])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), "#E6E6E6"),
                ("GRID", (0, 0), (-1, -1), 0.4, "#777777"),
            ]
        )
    )
    return tbl


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    PLOT_ROOT.mkdir(parents=True, exist_ok=True)

    timestep = _load("timestep")
    energy = _load("energy")
    mesh = _load("mesh")
    ecm_zero = _load("ecm_zero")
    ecm_current = _load("ecm_current")

    p_ts_t, p_ts_q = _plot_timestep(timestep)
    p_en = _plot_energy(energy)
    p_m_tmax, p_m_tcap = _plot_mesh(mesh)
    p_zero = _plot_ecm_series(ecm_zero, "distributed_forward_ecm_zero_qsum.png", "Distributed ECM Zero-Current: Q_sum_check vs Time")
    p_cur = _plot_ecm_series(ecm_current, "distributed_forward_ecm_current_qsum.png", "Distributed ECM Fixed-Current: Q_sum_check vs Time")

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    pdf = OUT_ROOT / f"distributed_forward_validation_report_{stamp}.pdf"

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, title="Distributed Forward Validation Report")
    story = [
        Paragraph("Distributed CFD-ECM Forward Validation Report", styles["Title"]),
        Spacer(1, 8),
        Paragraph("Plot-first report. Tables are used only for case/run settings.", styles["Normal"]),
        Spacer(1, 10),
    ]

    story.append(Paragraph("Test 1: Timestep Consistency", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Status", "PASS" if timestep["passed"] else "FAIL"),
                ("Runs", "dt = 0.5, 0.25, 0.125 s"),
                ("Case", "/workspace/cases/distributed_solid clones"),
                ("Window", "0-3 s"),
                ("maxDi", "100"),
                ("Metric file", str(_latest_json("timestep"))),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_ts_t), width=520, height=255))
    story.append(Spacer(1, 6))
    story.append(Image(str(p_ts_q), width=520, height=255))
    story.append(PageBreak())

    story.append(Paragraph("Test 2: Adiabatic Energy Balance", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Status", "PASS" if energy["passed"] else "FAIL"),
                ("Case", "/workspace/cases/validation_lumped_adiabatic_power clone"),
                ("Source", "fixed volumetric heat, ECM disabled"),
                ("Boundary", "adiabatic outer shell/cap"),
                ("maxDi", "100"),
                ("Metric file", str(_latest_json("energy"))),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_en), width=520, height=285))
    story.append(PageBreak())

    story.append(Paragraph("Test 3: Mesh Independence", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Status", "PASS" if mesh["passed"] else "FAIL"),
                ("Block variants", "(20,20,54), (28,28,76), (36,36,98)"),
                ("Case", "/workspace/cases/validation_lumped_adiabatic_power clones"),
                ("maxDi", "100"),
                ("Metric file", str(_latest_json("mesh"))),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_m_tmax), width=520, height=255))
    story.append(Spacer(1, 6))
    story.append(Image(str(p_m_tcap), width=520, height=255))
    story.append(PageBreak())

    story.append(Paragraph("Test 4: ECM Zero-Current Equilibrium", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Status", "PASS" if ecm_zero["passed"] else "FAIL"),
                ("Case", "/workspace/cases/distributed_solid clone"),
                ("Current", "0 A"),
                ("ECM mode", "enabled, per-step cadence"),
                ("Steady gate", "max|Q_sum_check| after 10 s"),
                ("Metric file", str(_latest_json("ecm_zero"))),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(Image(str(p_zero), width=520, height=255))
    story.append(PageBreak())

    story.append(Paragraph("Test 5: ECM Fixed-Current Cadence/Smoothness", styles["Heading2"]))
    story.append(
        _case_table(
            [
                ("Status", "PASS" if ecm_current["passed"] else "FAIL"),
                ("Case", "/workspace/cases/distributed_solid clone"),
                ("Current", "79 A"),
                ("ECM mode", "enabled, per-step cadence"),
                ("Smoothness gate", "max|d2Q| after 5 s"),
                ("Metric file", str(_latest_json("ecm_current"))),
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
