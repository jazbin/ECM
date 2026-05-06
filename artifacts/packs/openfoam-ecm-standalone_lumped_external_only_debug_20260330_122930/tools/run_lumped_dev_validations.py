#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import math
import re
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import run_lumped_quick_validations as qv


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "artifacts" / "validation" / "lumped_dev"
CASE_ROOT = ROOT / "cases"
BASE_ECM_CASE = ROOT / "cases" / "lumped_solid"
BASE_AD_CASE = ROOT / "cases" / "validation_lumped_adiabatic_power"

T0_K = qv.T0_K
P_TOTAL_W = qv.P_TOTAL_W
QDOT_CONST = qv.QDOT_CONST


def _run(cmd: list[str], cwd: Path) -> str:
    return qv._run(cmd, cwd)


def _replace(path: Path, pattern: str, repl: str) -> None:
    qv._replace(path, pattern, repl)


def _make_case_from(base_case: Path, name: str) -> Path:
    case_dir = CASE_ROOT / name
    if case_dir.exists():
        shutil.rmtree(case_dir)
    shutil.copytree(
        base_case,
        case_dir,
        ignore=shutil.ignore_patterns("ecm_daemon.sock", "*.sock"),
    )
    for child in case_dir.iterdir():
        if child.is_dir() and child.name != "0":
            try:
                float(child.name)
            except ValueError:
                continue
            shutil.rmtree(child)
    shutil.rmtree(case_dir / "postProcessing", ignore_errors=True)
    for fname in ("ecm_state.json", "ecm_last_good.bin", "ecm_in.json", "ecm_out.json"):
        try:
            (case_dir / "ecm" / fname).unlink()
        except FileNotFoundError:
            pass
    return case_dir


def _set_adjust_timestep(case_dir: Path, enabled: bool) -> None:
    control = case_dir / "system" / "controlDict"
    value = "yes" if enabled else "no"
    _replace(control, r"^\s*adjustTimeStep\s+[^;]+;$", f"adjustTimeStep  {value};")


def _set_delta_t(case_dir: Path, delta_t: float) -> None:
    control = case_dir / "system" / "controlDict"
    _replace(control, r"^\s*deltaT\s+[^;]+;$", f"deltaT          {delta_t};")


def _set_max_di(case_dir: Path, value: float) -> None:
    control = case_dir / "system" / "controlDict"
    _replace(control, r"^\s*maxDi\s+[^;]+;$", f"maxDi           {value};")


def _set_ecm_call_every_step(case_dir: Path) -> None:
    control = case_dir / "system" / "controlDict"
    txt = control.read_text()
    new = txt.replace("--ecm-call-every-n-steps 3", "--ecm-call-every-n-steps 1")
    if new == txt:
        raise RuntimeError("ECM step-cadence pattern not found in controlDict")
    control.write_text(new)


def _set_write_interval(case_dir: Path, value: float) -> None:
    control = case_dir / "system" / "controlDict"
    _replace(control, r"^\s*writeInterval\s+[^;]+;$", f"writeInterval   {value};")


def _set_runtime(case_dir: Path, *, end_time: float, write_interval: float) -> None:
    control = case_dir / "system" / "controlDict"
    txt = control.read_text()
    if not re.search(r"\bendTime\s+[^;]+;", txt):
        raise RuntimeError(f"endTime entry not found in {control}")
    if not re.search(r"\bwriteInterval\s+[^;]+;", txt):
        raise RuntimeError(f"writeInterval entry not found in {control}")
    txt2 = re.sub(r"(\bendTime\s+)[^;]+;", rf"\g<1>{end_time};", txt)
    txt3 = re.sub(r"(\bwriteInterval\s+)[^;]+;", rf"\g<1>{write_interval};", txt2)
    control.write_text(txt3)


def _set_block_counts(case_dir: Path, nx: int, ny: int, nz: int) -> None:
    block_dict = case_dir / "system" / "blockMeshDict"
    txt = block_dict.read_text()
    pattern = r"(hex\s*\(\s*0\s+1\s+2\s+3\s+4\s+5\s+6\s+7\s*\)\s*)\(\s*\d+\s+\d+\s+\d+\s*\)(\s*simpleGrading\s*\(\s*1\s+1\s+1\s*\))"
    if not re.search(pattern, txt):
        raise RuntimeError("Failed to find blockMesh cell-count entry")
    new = re.sub(pattern, rf"\1({nx} {ny} {nz})\2", txt)
    block_dict.write_text(new)


def _set_snappy_surface_level(case_dir: Path, level: int) -> None:
    shmd = case_dir / "system" / "snappyHexMeshDict"
    txt = shmd.read_text()
    pattern = r"(externalWall\s*\{[^}]*?level\s*)\(\s*\d+\s+\d+\s*\)(\s*;)"
    if not re.search(pattern, txt, flags=re.DOTALL):
        raise RuntimeError("Failed to find snappy surface level entry")
    new = re.sub(pattern, rf"\1({level} {level})\2", txt, flags=re.DOTALL)
    shmd.write_text(new)


def _run_allmesh(case_dir: Path) -> None:
    for rel in (
        "log.blockMesh",
        "log.surfaceFeatureExtract",
        "log.snappyHexMesh",
        "log.splitMeshRegions",
    ):
        try:
            (case_dir / rel).unlink()
        except FileNotFoundError:
            pass
    for rel in (
        "constant/polyMesh",
        "constant/jellyRoll/polyMesh",
        "constant/shell/polyMesh",
        "constant/cap/polyMesh",
    ):
        shutil.rmtree(case_dir / rel, ignore_errors=True)
    _run(["bash", "./Allmesh"], cwd=case_dir)


def _poly_boundary_patches(boundary_path: Path) -> list[str]:
    names: list[str] = []
    lines = boundary_path.read_text().splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped in {"(", ")"}:
            continue
        if stripped.endswith("{"):
            continue
        if i + 1 < len(lines) and lines[i + 1].strip() == "{":
            names.append(stripped)
    return names


def _sync_zero_gradient_boundary_entries(case_dir: Path) -> None:
    for region in ("jellyRoll", "shell", "cap"):
        boundary_path = case_dir / "constant" / region / "polyMesh" / "boundary"
        region_zero = case_dir / "0" / region
        if not boundary_path.exists() or not region_zero.exists():
            continue
        patch_names = _poly_boundary_patches(boundary_path)
        for field_path in region_zero.iterdir():
            if not field_path.is_file():
                continue
            txt = field_path.read_text()
            if "boundaryField" not in txt:
                continue
            inserts = []
            for patch in patch_names:
                if re.search(rf"(^|\n)\s*{re.escape(patch)}\s*\{{", txt):
                    continue
                inserts.append(
                    f"    {patch}\n"
                    "    {\n"
                    "        type            zeroGradient;\n"
                    "    }\n"
                )
            if not inserts:
                continue
            if "boundaryField\n{" in txt:
                txt = txt.replace("boundaryField\n{", "boundaryField\n{\n" + "".join(inserts), 1)
            else:
                raise RuntimeError(f"boundaryField block not found in {field_path}")
            field_path.write_text(txt)


def _run_case(case_dir: Path, label: str) -> Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    log = ROOT / "artifacts" / "logs" / f"{label}_{stamp}.log"
    out = _run(["chtMultiRegionSolidFoam", "-case", str(case_dir)], cwd=case_dir)
    log.write_text(out)
    return log


def _final_time(case_dir: Path) -> str:
    times = qv._numeric_times(case_dir)
    if not times:
        raise RuntimeError(f"No time directories found in {case_dir}")
    return times[-1]


def _temperature_means(case_dir: Path, time_name: str) -> tuple[dict[str, float], dict[str, float], float]:
    means = {}
    caps = {}
    for region in ("jellyRoll", "shell", "cap"):
        means[region] = qv._volavg(case_dir, region, time_name)
        cp, rho = qv._parse_cp_rho(case_dir, region)
        vol = qv._region_volume(case_dir, region)
        caps[region] = cp * rho * vol
    total_cap = sum(caps.values())
    tcap = sum(caps[r] * means[r] for r in means) / total_cap
    return means, caps, tcap


def _qsum_final(log_path: Path) -> float:
    times, qs = qv._qsum_series(log_path)
    if len(qs) == 0:
        raise RuntimeError(f"No Q_sum_check data found in {log_path}")
    return float(qs[-1])


def _final_region_minmax(log_path: Path, region: str) -> tuple[float, float, float]:
    cur_t = None
    active_region = None
    last = None
    for line in log_path.read_text(errors="ignore").splitlines():
        m = re.match(r"^\s*Time\s*=\s*([0-9eE+\-.]+)\s*$", line)
        if m:
            cur_t = float(m.group(1))
            continue
        m = re.match(r"^\s*Solving for solid region\s+(\S+)\s*$", line)
        if m:
            active_region = m.group(1)
            continue
        m = re.match(r"^\s*Min/max T:([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s*$", line)
        if m and cur_t is not None and active_region == region:
            last = (cur_t, float(m.group(1)), float(m.group(2)))
    if last is None:
        raise RuntimeError(f"Final Min/max T for region {region} not found in {log_path}")
    return last


def _region_cells(case_dir: Path, region: str) -> int:
    out = _run(["checkMesh", "-case", str(case_dir), "-region", region], cwd=case_dir)
    m = re.search(r"cells:\s+([0-9]+)", out)
    if not m:
        raise RuntimeError(f"Cell count not found for region {region}")
    return int(m.group(1))


def _plot_series(x: np.ndarray, y: np.ndarray, y_ref: np.ndarray | None, out: Path, title: str, ylabel: str, xlabel: str) -> None:
    plt.figure(figsize=(7.0, 3.8), dpi=160)
    plt.plot(x, y, marker="o", lw=1.8, label="Simulation")
    if y_ref is not None:
        plt.plot(x, y_ref, lw=1.5, ls="--", label="Reference")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    plots = OUT_ROOT / "plots"
    plots.mkdir(parents=True, exist_ok=True)

    metrics_lines = ["test,metric,value"]
    logs: list[str] = []

    # 1. Time-step independence on the lumped ECM-enabled case.
    timestep_defs = [("dt1p0", 1.0), ("dt0p5", 0.5), ("dt0p25", 0.25)]
    dt_values = []
    tcap_values = []
    qsum_values = []
    t_end = 12.0
    for tag, dt_val in timestep_defs:
        case_dir = _make_case_from(BASE_ECM_CASE, f"validation_lumped_dev_timestep_{tag}")
        qv._set_h_relaxation(case_dir, 1.0)
        _set_runtime(case_dir, end_time=t_end, write_interval=t_end)
        _set_max_di(case_dir, 100)
        _set_adjust_timestep(case_dir, False)
        _set_delta_t(case_dir, dt_val)
        _set_ecm_call_every_step(case_dir)
        log_path = _run_case(case_dir, f"validation_lumped_dev_timestep_{tag}")
        logs.append(log_path.name)
        final_time = _final_time(case_dir)
        _, _, tcap = _temperature_means(case_dir, final_time)
        dt_values.append(dt_val)
        tcap_values.append(tcap)
        qsum_values.append(_qsum_final(log_path))
        metrics_lines.append(f"timestep_{tag},final_capacity_weighted_T_K,{tcap:.10g}")
        metrics_lines.append(f"timestep_{tag},final_Q_sum_check_W,{qsum_values[-1]:.10g}")
    tcap_ref = tcap_values[-1]
    qsum_ref = qsum_values[-1]
    for (tag, _), tcap, qsum in zip(timestep_defs[:-1], tcap_values[:-1], qsum_values[:-1]):
        metrics_lines.append(f"timestep_{tag},delta_T_vs_dt0p25_K,{abs(tcap - tcap_ref):.10g}")
        metrics_lines.append(f"timestep_{tag},delta_Q_vs_dt0p25_W,{abs(qsum - qsum_ref):.10g}")
    p_dt_t = plots / "timestep_independence_temperature.png"
    _plot_series(
        np.asarray(dt_values),
        np.asarray(tcap_values),
        np.full(len(dt_values), tcap_ref),
        p_dt_t,
        "Time-Step Independence: Final Capacity-Weighted Temperature",
        "final T [K]",
        "deltaT [s]",
    )
    p_dt_q = plots / "timestep_independence_qsum.png"
    _plot_series(
        np.asarray(dt_values),
        np.asarray(qsum_values),
        np.full(len(dt_values), qsum_ref),
        p_dt_q,
        "Time-Step Independence: Final Q_sum_check",
        "final Q_sum_check [W]",
        "deltaT [s]",
    )

    # 2. Formal energy-balance check on the analytic adiabatic case.
    c_energy = _make_case_from(BASE_AD_CASE, "validation_lumped_dev_energy_balance")
    _set_runtime(c_energy, end_time=60, write_interval=10)
    _set_max_di(c_energy, 100)
    qv._set_h_relaxation(c_energy, 1.0)
    qv._disable_ecm_coupling(c_energy)
    qv._set_external_wall(c_energy, "zeroGradient")
    qv._set_constant_source(c_energy, QDOT_CONST)
    log_energy = _run_case(c_energy, "validation_lumped_dev_energy_balance")
    logs.append(log_energy.name)
    time_name = _final_time(c_energy)
    _, caps_energy, tcap_energy = _temperature_means(c_energy, time_name)
    c_total = sum(caps_energy.values())
    sim_time = float(time_name)
    e_expected = P_TOTAL_W * sim_time
    e_stored = c_total * (tcap_energy - T0_K)
    e_err = e_stored - e_expected
    e_err_pct = 100.0 * e_err / max(e_expected, 1.0e-12)
    metrics_lines.append(f"energy_balance,simulated_time_s,{sim_time:.10g}")
    metrics_lines.append(f"energy_balance,expected_energy_J,{e_expected:.10g}")
    metrics_lines.append(f"energy_balance,stored_energy_J,{e_stored:.10g}")
    metrics_lines.append(f"energy_balance,error_J,{e_err:.10g}")
    metrics_lines.append(f"energy_balance,error_percent,{e_err_pct:.10g}")
    p_energy = plots / "energy_balance.png"
    _plot_series(
        np.asarray([0.0, sim_time]),
        np.asarray([0.0, e_stored]),
        np.asarray([0.0, e_expected]),
        p_energy,
        "Adiabatic Energy Balance",
        "energy added/stored [J]",
        "time [s]",
    )

    # 3. Mesh independence on the analytic adiabatic case.
    mesh_defs = [("coarse", (20, 20, 54)), ("medium", (28, 28, 76)), ("fine", (36, 36, 98))]
    mesh_labels = []
    mesh_tmax = []
    mesh_tcap = []
    mesh_cells = []
    mesh_err = []
    mesh_t_end = 30
    for tag, (nx, ny, nz) in mesh_defs:
        case_dir = _make_case_from(BASE_AD_CASE, f"validation_lumped_dev_mesh_{tag}")
        _set_block_counts(case_dir, nx, ny, nz)
        _run_allmesh(case_dir)
        _sync_zero_gradient_boundary_entries(case_dir)
        _set_runtime(case_dir, end_time=mesh_t_end, write_interval=mesh_t_end)
        _set_max_di(case_dir, 100)
        qv._set_h_relaxation(case_dir, 1.0)
        qv._disable_ecm_coupling(case_dir)
        qv._set_external_wall(case_dir, "zeroGradient")
        qv._set_constant_source(case_dir, QDOT_CONST)
        log_path = _run_case(case_dir, f"validation_lumped_dev_mesh_{tag}")
        logs.append(log_path.name)
        final_time = _final_time(case_dir)
        _, caps_mesh, tcap = _temperature_means(case_dir, final_time)
        _, _, tmax = _final_region_minmax(log_path, "jellyRoll")
        c_mesh = sum(caps_mesh.values())
        tref = T0_K + P_TOTAL_W * float(final_time) / c_mesh
        mesh_labels.append(tag)
        mesh_tmax.append(tmax)
        mesh_tcap.append(tcap)
        mesh_cells.append(_region_cells(case_dir, "jellyRoll"))
        mesh_err.append(tcap - tref)
        metrics_lines.append(f"mesh_{tag},block_cells,{nx*ny*nz}")
        metrics_lines.append(f"mesh_{tag},jellyRoll_cells,{mesh_cells[-1]}")
        metrics_lines.append(f"mesh_{tag},final_jellyRoll_Tmax_K,{tmax:.10g}")
        metrics_lines.append(f"mesh_{tag},final_capacity_weighted_T_K,{tcap:.10g}")
        metrics_lines.append(f"mesh_{tag},analytic_error_K,{(tcap - tref):.10g}")
    mesh_ref = mesh_tmax[-1]
    for tag, tmax in zip(mesh_labels[:-1], mesh_tmax[:-1]):
        metrics_lines.append(f"mesh_{tag},delta_Tmax_vs_fine_K,{abs(tmax - mesh_ref):.10g}")
    p_mesh = plots / "mesh_independence.png"
    _plot_series(
        np.asarray(mesh_cells, dtype=float),
        np.asarray(mesh_tmax),
        np.full(len(mesh_cells), mesh_ref),
        p_mesh,
        "Mesh Independence: Final jellyRoll Tmax",
        "final jellyRoll Tmax [K]",
        "jellyRoll cells [-]",
    )

    metrics_csv = OUT_ROOT / "metrics.csv"
    metrics_csv.write_text("\n".join(metrics_lines) + "\n")

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    pdf = OUT_ROOT / f"lumped_dev_validation_report_{stamp}.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, title="Lumped Development Validation Report")
    summary_rows = [
        ["Check", "Purpose", "Primary metric", "Result"],
        [
            "Time-step independence",
            "ECM-enabled lumped run",
            f"|T(dt=1.0)-T(dt=0.25)| = {abs(tcap_values[0] - tcap_ref):.3e} K",
            f"|Q(dt=1.0)-Q(dt=0.25)| = {abs(qsum_values[0] - qsum_ref):.3e} W",
        ],
        [
            "Energy balance",
            "Adiabatic fixed-power control",
            f"stored = {e_stored:.3f} J, expected = {e_expected:.3f} J",
            f"error = {e_err:.3f} J ({e_err_pct:.3e}%)",
        ],
        [
            "Mesh independence",
            "Adiabatic fixed-power control",
            f"|Tmax(coarse)-Tmax(fine)| = {abs(mesh_tmax[0] - mesh_ref):.3e} K",
            f"|Tmax(medium)-Tmax(fine)| = {abs(mesh_tmax[1] - mesh_ref):.3e} K",
        ],
    ]
    tbl = Table(summary_rows, colWidths=[95, 150, 135, 120])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), "#E6E6E6"),
                ("GRID", (0, 0), (-1, -1), 0.5, "#666666"),
            ]
        )
    )
    story = [
        Paragraph("Lumped Development Validation Report", styles["Title"]),
        Spacer(1, 8),
        Paragraph("Development gate: time-step independence, energy balance, and mesh independence.", styles["Normal"]),
        Paragraph("Time-step independence is run on the ECM-enabled lumped case; the analytic energy and mesh checks are run on the corrected adiabatic fixed-power control case.", styles["Normal"]),
        Spacer(1, 8),
        tbl,
        Spacer(1, 10),
        Image(str(p_dt_t), width=500, height=250),
        Spacer(1, 6),
        Image(str(p_dt_q), width=500, height=250),
        Spacer(1, 6),
        Image(str(p_energy), width=500, height=250),
        Spacer(1, 6),
        Image(str(p_mesh), width=500, height=250),
        Spacer(1, 6),
        Paragraph(f"Metrics CSV: {metrics_csv}", styles["Normal"]),
        Paragraph(f"Logs: {', '.join(logs)}", styles["Normal"]),
    ]
    doc.build(story)

    print(pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
