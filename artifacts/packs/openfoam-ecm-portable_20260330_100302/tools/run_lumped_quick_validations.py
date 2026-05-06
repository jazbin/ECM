#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import math
import os
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


ROOT = Path(__file__).resolve().parents[1]
BASE_CASE = ROOT / "cases" / "lumped_solid"
OUT_ROOT = ROOT / "artifacts" / "validation" / "lumped_quick"
CASE_ROOT = ROOT / "cases"

T0_K = 313.15
P_TOTAL_W = 50.0
QDOT_CONST = 3.07e6
P_HALF_W = 25.0
QDOT_HALF = QDOT_CONST * 0.5


def _run(cmd: list[str], cwd: Path) -> str:
    shell_cmd = " ".join(subprocess.list2cmdline([part]) for part in cmd)
    p = subprocess.run(
        ["bash", "-lc", shell_cmd],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {cmd}\n{p.stdout}")
    return p.stdout


def _write(path: Path, text: str) -> None:
    path.write_text(text)


def _replace(path: Path, pattern: str, repl: str) -> None:
    txt = path.read_text()
    new = re.sub(pattern, repl, txt, flags=re.MULTILINE)
    if new == txt:
        raise RuntimeError(f"Pattern not found in {path}: {pattern}")
    path.write_text(new)


def _make_case(name: str) -> Path:
    case_dir = CASE_ROOT / name
    if case_dir.exists():
        shutil.rmtree(case_dir)
    shutil.copytree(
        BASE_CASE,
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


def _set_runtime(case_dir: Path, *, end_time: int, write_interval: int) -> None:
    control = case_dir / "system" / "controlDict"
    _replace(control, r"^\s*endTime\s+[^;]+;$", f"endTime         {end_time};")
    _replace(control, r"^\s*writeInterval\s+[^;]+;$", f"writeInterval   {write_interval};")


def _disable_ecm_coupling(case_dir: Path) -> None:
    control = case_dir / "system" / "controlDict"
    txt = control.read_text()
    txt = txt.replace("type            ecmCoupler;\n", "type            ecmCoupler;\n        enabled         false;\n", 1)
    control.write_text(txt)


def _set_current(case_dir: Path, current_a: float) -> None:
    control = case_dir / "system" / "controlDict"
    _replace(control, r"(^\s*current_A\s+)[^;]+;", rf"\g<1>{current_a};")


def _set_external_wall(case_dir: Path, bc_type: str, value: float | None = None) -> None:
    for region in ("shell", "cap"):
        path = case_dir / "0" / region / "T"
        txt = path.read_text()
        if bc_type == "zeroGradient":
            txt = re.sub(
                r"externalWall\s*\{[^}]*\}",
                "externalWall\n    {\n        type            zeroGradient;\n    }",
                txt,
                flags=re.DOTALL,
            )
        else:
            txt = re.sub(
                r"externalWall\s*\{[^}]*\}",
                (
                    "externalWall\n    {\n"
                    f"        type            fixedValue;\n        value           uniform {value:.5f};\n"
                    "    }"
                ),
                txt,
                flags=re.DOTALL,
            )
        path.write_text(txt)


def _set_h_relaxation(case_dir: Path, value: float) -> None:
    for region in ("jellyRoll", "shell", "cap"):
        path = case_dir / "system" / region / "fvSolution"
        txt = path.read_text()
        txt = re.sub(
            r"(^\s*h\s+)[0-9eE+\-.]+;",
            rf"\g<1>{value};",
            txt,
            flags=re.MULTILINE,
        )
        path.write_text(txt)


def _set_constant_source(case_dir: Path, qdot: float) -> None:
    txt = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2506                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system/jellyRoll";
    object      fvOptions;
}}

fixedHeatSource
{{
    type            scalarCodedSource;
    active          yes;
    name            fixedHeatSource;

    scalarCodedSourceCoeffs
    {{
        selectionMode   cellZone;
        cellZone        jellyRoll;
        fields          (h);

        codeInclude
        #{{
            #include "fvCFD.H"
        #}};

        codeAddSup
        #{{
            const scalar qdot = {qdot:.12g};
            forAll(cells_, i)
            {{
                const label cellI = cells_[i];
                eqn.source()[cellI] -= qdot*mesh().V()[cellI];
            }}
        #}};

        codeAddSupRho
        #{{
            const scalar qdot = {qdot:.12g};
            forAll(cells_, i)
            {{
                const label cellI = cells_[i];
                eqn.source()[cellI] -= qdot*mesh().V()[cellI];
            }}
        #}};

        codeCorrect
        #{{
        #}};

        codeConstrain
        #{{
        #}};
    }}
}}
"""
    _write(case_dir / "system" / "jellyRoll" / "fvOptions", txt)


def _parse_cp_rho(case_dir: Path, region: str) -> tuple[float, float]:
    txt = (case_dir / "constant" / region / "thermophysicalProperties").read_text()
    cp = float(re.search(r"Cp\s+([0-9eE+\-.]+);", txt).group(1))
    rho = float(re.search(r"rho\s+([0-9eE+\-.]+);", txt).group(1))
    return cp, rho


def _region_volume(case_dir: Path, region: str) -> float:
    out = _run(["checkMesh", "-case", str(case_dir), "-region", region], cwd=case_dir)
    m = re.search(r"Total volume =\s*([0-9eE+\-.]+)", out)
    if not m:
        raise RuntimeError(f"Total volume not found for region {region}\n{out}")
    return float(m.group(1).rstrip("."))


def _run_case(case_dir: Path, label: str) -> Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    log = ROOT / "artifacts" / "logs" / f"{label}_{stamp}.log"
    out = _run(["chtMultiRegionSolidFoam", "-case", str(case_dir)], cwd=case_dir)
    log.write_text(out)
    return log


def _numeric_times(case_dir: Path) -> list[str]:
    vals = []
    for p in case_dir.iterdir():
        if not p.is_dir() or p.name == "0":
            continue
        try:
            float(p.name)
        except ValueError:
            continue
        vals.append(p.name)
    return sorted(vals, key=float)


def _volavg(case_dir: Path, region: str, time_name: str) -> float:
    out = _run(
        ["postProcess", "-case", str(case_dir), "-region", region, "-time", time_name, "-func", "volFieldValue"],
        cwd=case_dir,
    )
    m = re.search(r"volAverage\([^)]+\)\s+of\s+T\s*=\s*([0-9eE+\-.]+)", out)
    if not m:
        raise RuntimeError(f"volAverage(T) not found for {region} at {time_name}\n{out}")
    return float(m.group(1))


def _qsum_series(log_path: Path) -> tuple[np.ndarray, np.ndarray]:
    times = []
    qs = []
    cur_t = None
    for line in log_path.read_text(errors="ignore").splitlines():
        m = re.match(r"^\s*Time\s*=\s*([0-9eE+\-.]+)\s*$", line)
        if m:
            cur_t = float(m.group(1))
            continue
        m = re.match(r"^\s*Q_sum_check\s+([0-9eE+\-.]+)\s*W?\s*$", line)
        if m and cur_t is not None:
            times.append(cur_t)
            qs.append(float(m.group(1)))
    return np.asarray(times), np.asarray(qs)


def _collect_temperature_series(case_dir: Path) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    times = _numeric_times(case_dir)
    region_means: dict[str, list[float]] = {"jellyRoll": [], "shell": [], "cap": []}
    cap_weights: dict[str, float] = {}
    for region in region_means:
        cp, rho = _parse_cp_rho(case_dir, region)
        vol = _region_volume(case_dir, region)
        cap_weights[region] = cp * rho * vol
    tvals = np.asarray([float(t) for t in times], dtype=float)
    for t in times:
        for region in region_means:
            region_means[region].append(_volavg(case_dir, region, t))
    region_arrays = {k: np.asarray(v) for k, v in region_means.items()}
    total_cap = sum(cap_weights.values())
    tcap = (
        cap_weights["jellyRoll"] * region_arrays["jellyRoll"]
        + cap_weights["shell"] * region_arrays["shell"]
        + cap_weights["cap"] * region_arrays["cap"]
    ) / total_cap
    return tvals, tcap, region_arrays, cap_weights


def _fit_first_order(times: np.ndarray, temps: np.ndarray, p_w: float) -> tuple[float, float, float]:
    y = temps - T0_K
    tau_grid = np.logspace(math.log10(1.0), math.log10(max(float(times.max()), 2.0) * 4.0), 400)
    best_sse = float("inf")
    best_tau = 1.0
    best_amp = 0.0
    for tau in tau_grid:
        basis = 1.0 - np.exp(-times / tau)
        denom = float(np.dot(basis, basis))
        if denom <= 0.0:
            continue
        amp = float(np.dot(y, basis) / denom)
        pred = amp * basis
        sse = float(np.dot(y - pred, y - pred))
        if sse < best_sse:
            best_sse = sse
            best_tau = float(tau)
            best_amp = amp
    return best_amp / p_w, best_tau, best_sse


def _plot_series(times: np.ndarray, y_num: np.ndarray, y_ref: np.ndarray | None, out: Path, title: str, ylabel: str) -> None:
    plt.figure(figsize=(7.0, 3.8), dpi=160)
    plt.plot(times, y_num, lw=1.8, label="Simulation")
    if y_ref is not None:
        plt.plot(times, y_ref, lw=1.5, ls="--", label="Reference")
    plt.xlabel("time [s]")
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

    # Case 1: zero heat equilibrium
    c_zero = _make_case("validation_lumped_zero_heat")
    _set_runtime(c_zero, end_time=30, write_interval=10)
    _set_h_relaxation(c_zero, 1.0)
    _set_current(c_zero, 0.0)
    log_zero = _run_case(c_zero, "validation_lumped_zero_heat")
    tz, qz = _qsum_series(log_zero)
    t_zero, tcap_zero, _, _ = _collect_temperature_series(c_zero)
    p_zero = plots / "zero_heat_temperature.png"
    _plot_series(t_zero, tcap_zero, np.full_like(t_zero, T0_K), p_zero, "Zero-Heat Equilibrium", "capacity-weighted T [K]")

    # Case 2: adiabatic constant-power rise
    c_ad = _make_case("validation_lumped_adiabatic_power")
    _set_runtime(c_ad, end_time=60, write_interval=10)
    _set_h_relaxation(c_ad, 1.0)
    _disable_ecm_coupling(c_ad)
    _set_external_wall(c_ad, "zeroGradient")
    _set_constant_source(c_ad, QDOT_CONST)
    log_ad = _run_case(c_ad, "validation_lumped_adiabatic_power")
    t_ad, tcap_ad, _, caps_ad = _collect_temperature_series(c_ad)
    c_total = sum(caps_ad.values())
    tref_ad = T0_K + P_TOTAL_W * t_ad / c_total
    p_ad = plots / "adiabatic_constant_power.png"
    _plot_series(t_ad, tcap_ad, tref_ad, p_ad, "Adiabatic Constant-Power Rise", "capacity-weighted T [K]")

    # Case 3: fixed-ambient step response
    c_step = _make_case("validation_lumped_fixed_ambient")
    _set_runtime(c_step, end_time=120, write_interval=10)
    _set_h_relaxation(c_step, 1.0)
    _disable_ecm_coupling(c_step)
    _set_external_wall(c_step, "fixedValue", T0_K)
    _set_constant_source(c_step, QDOT_CONST)
    log_step = _run_case(c_step, "validation_lumped_fixed_ambient")
    t_step, tcap_step, _, _ = _collect_temperature_series(c_step)
    r_th, tau, _sse = _fit_first_order(t_step, tcap_step, P_TOTAL_W)
    tref_step = T0_K + P_TOTAL_W * r_th * (1.0 - np.exp(-t_step / tau))
    p_step = plots / "fixed_ambient_step_response.png"
    _plot_series(t_step, tcap_step, tref_step, p_step, "Fixed-Ambient Step Response", "capacity-weighted T [K]")

    # Case 4: fixed-ambient linearity at half power
    c_half = _make_case("validation_lumped_fixed_ambient_halfpower")
    _set_runtime(c_half, end_time=120, write_interval=10)
    _set_h_relaxation(c_half, 1.0)
    _disable_ecm_coupling(c_half)
    _set_external_wall(c_half, "fixedValue", T0_K)
    _set_constant_source(c_half, QDOT_HALF)
    log_half = _run_case(c_half, "validation_lumped_fixed_ambient_halfpower")
    t_half, tcap_half, _, _ = _collect_temperature_series(c_half)
    interp_half = np.interp(t_step, t_half, tcap_half)
    linearity_ratio = np.divide(
        tcap_step - T0_K,
        np.maximum(interp_half - T0_K, 1.0e-12),
    )
    ratio_target = np.full_like(t_step, 2.0)
    ratio_mask = (interp_half - T0_K) > 1.0e-3
    ratio_rmse = float(np.sqrt(np.mean((linearity_ratio[ratio_mask] - 2.0) ** 2))) if np.any(ratio_mask) else float("nan")
    ratio_max = float(np.max(np.abs(linearity_ratio[ratio_mask] - 2.0))) if np.any(ratio_mask) else float("nan")
    p_lin = plots / "fixed_ambient_linearity.png"
    _plot_series(t_step, linearity_ratio, ratio_target, p_lin, "Fixed-Ambient Linearity (50 W / 25 W)", "temperature-rise ratio [-]")

    # Metrics
    zero_q_abs = float(np.max(np.abs(qz))) if len(qz) else float("nan")
    zero_t_drift = float(np.max(np.abs(tcap_zero - T0_K)))
    ad_rmse = float(np.sqrt(np.mean((tcap_ad - tref_ad) ** 2)))
    ad_max = float(np.max(np.abs(tcap_ad - tref_ad)))
    step_rmse = float(np.sqrt(np.mean((tcap_step - tref_step) ** 2)))
    step_max = float(np.max(np.abs(tcap_step - tref_step)))

    metrics_csv = OUT_ROOT / "metrics.csv"
    metrics_csv.write_text(
        "test,metric,value\n"
        f"zero_heat,max_abs_qsum_W,{zero_q_abs:.10g}\n"
        f"zero_heat,max_capacity_weighted_temp_drift_K,{zero_t_drift:.10g}\n"
        f"adiabatic,rmse_K,{ad_rmse:.10g}\n"
        f"adiabatic,max_abs_err_K,{ad_max:.10g}\n"
        f"adiabatic,total_heat_capacity_J_per_K,{c_total:.10g}\n"
        f"fixed_ambient,fit_Rth_K_per_W,{r_th:.10g}\n"
        f"fixed_ambient,fit_tau_s,{tau:.10g}\n"
        f"fixed_ambient,rmse_K,{step_rmse:.10g}\n"
        f"fixed_ambient,max_abs_err_K,{step_max:.10g}\n"
        f"linearity,ratio_rmse_from_2,{ratio_rmse:.10g}\n"
        f"linearity,ratio_max_abs_err_from_2,{ratio_max:.10g}\n"
    )

    # PDF summary
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    pdf = OUT_ROOT / f"lumped_quick_validation_report_{stamp}.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, title="Lumped Quick Validation Report")
    story = [
        Paragraph("Lumped Quick Validation Report", styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"Base case: {BASE_CASE}", styles["Normal"]),
        Paragraph("Runs executed on derived CHT copies with either zero-current ECM or fixed volumetric heating.", styles["Normal"]),
        Spacer(1, 8),
    ]
    rows = [
        ["Test", "Reference", "Metric 1", "Metric 2"],
        ["Zero heat", "T = const, Q = 0", f"max |Q_sum_check| = {zero_q_abs:.3e} W", f"max drift = {zero_t_drift:.3e} K"],
        ["Adiabatic power", "Tcap = T0 + P t / C", f"RMSE = {ad_rmse:.3e} K", f"max err = {ad_max:.3e} K"],
        ["Fixed ambient", "T = T0 + P Rth (1-exp(-t/tau))", f"Rth = {r_th:.4f} K/W, tau = {tau:.2f} s", f"RMSE = {step_rmse:.3e} K"],
        ["Linearity", "ΔT(50 W) / ΔT(25 W) = 2", f"ratio RMSE = {ratio_rmse:.3e}", f"max err = {ratio_max:.3e}"],
    ]
    tbl = Table(rows, colWidths=[90, 170, 110, 110])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), "#E6E6E6"),
                ("GRID", (0, 0), (-1, -1), 0.5, "#666666"),
            ]
        )
    )
    story.extend([tbl, Spacer(1, 10), Image(str(p_zero), width=500, height=250), Spacer(1, 6)])
    story.extend([Image(str(p_ad), width=500, height=250), Spacer(1, 6)])
    story.extend([Image(str(p_step), width=500, height=250), Spacer(1, 6)])
    story.extend([Image(str(p_lin), width=500, height=250), Spacer(1, 6)])
    story.append(Paragraph(f"Logs: {log_zero.name}, {log_ad.name}, {log_step.name}, {log_half.name}", styles["Normal"]))
    story.append(Paragraph(f"Metrics CSV: {metrics_csv}", styles["Normal"]))
    doc.build(story)

    print(pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
