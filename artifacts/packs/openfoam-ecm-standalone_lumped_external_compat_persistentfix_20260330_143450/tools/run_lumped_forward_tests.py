#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

import run_lumped_quick_validations as qv


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "cases"
BASE_ECM_CASE = ROOT / "cases" / "lumped_solid"
BASE_AD_CASE = ROOT / "cases" / "validation_lumped_adiabatic_power"
OUT_ROOT = ROOT / "artifacts" / "validation" / "lumped_forward"

DEV_MAX_DI = 100.0
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
    shutil.copytree(base_case, case_dir, ignore=shutil.ignore_patterns("ecm_daemon.sock", "*.sock"))
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


def _set_runtime(case_dir: Path, *, end_time: float, write_interval: float) -> None:
    control = case_dir / "system" / "controlDict"
    txt = control.read_text()
    txt = re.sub(r"(\bendTime\s+)[^;]+;", rf"\g<1>{end_time};", txt)
    txt = re.sub(r"(\bwriteInterval\s+)[^;]+;", rf"\g<1>{write_interval};", txt)
    control.write_text(txt)


def _set_adjust_timestep(case_dir: Path, enabled: bool) -> None:
    value = "yes" if enabled else "no"
    _replace(case_dir / "system" / "controlDict", r"^\s*adjustTimeStep\s+[^;]+;$", f"adjustTimeStep  {value};")


def _set_delta_t(case_dir: Path, delta_t: float) -> None:
    _replace(case_dir / "system" / "controlDict", r"^\s*deltaT\s+[^;]+;$", f"deltaT          {delta_t};")


def _set_max_di(case_dir: Path, max_di: float) -> None:
    _replace(case_dir / "system" / "controlDict", r"^\s*maxDi\s+[^;]+;$", f"maxDi           {max_di};")


def _set_current(case_dir: Path, current_a: float) -> None:
    _replace(case_dir / "system" / "controlDict", r"(^\s*current_A\s+)[^;]+;", rf"\g<1>{current_a};")


def _set_ecm_call_every_step(case_dir: Path) -> None:
    p = case_dir / "system" / "controlDict"
    txt = p.read_text()
    new = txt.replace("--ecm-call-every-n-steps 3", "--ecm-call-every-n-steps 1")
    if new == txt:
        raise RuntimeError("ECM cadence token not found in controlDict")
    p.write_text(new)


def _set_h_relaxation(case_dir: Path, value: float) -> None:
    qv._set_h_relaxation(case_dir, value)


def _set_external_wall(case_dir: Path, bc_type: str, value: float | None = None) -> None:
    qv._set_external_wall(case_dir, bc_type, value)


def _disable_ecm(case_dir: Path) -> None:
    qv._disable_ecm_coupling(case_dir)


def _set_constant_source(case_dir: Path, qdot: float) -> None:
    qv._set_constant_source(case_dir, qdot)


def _run_case(case_dir: Path, label: str) -> Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    log = ROOT / "artifacts" / "logs" / f"{label}_{stamp}.log"
    out = _run(["chtMultiRegionSolidFoam", "-case", str(case_dir)], cwd=case_dir)
    log.write_text(out)
    return log


def _run_allmesh(case_dir: Path) -> None:
    for rel in ("log.blockMesh", "log.surfaceFeatureExtract", "log.snappyHexMesh", "log.splitMeshRegions"):
        try:
            (case_dir / rel).unlink()
        except FileNotFoundError:
            pass
    for rel in ("constant/polyMesh", "constant/jellyRoll/polyMesh", "constant/shell/polyMesh", "constant/cap/polyMesh"):
        shutil.rmtree(case_dir / rel, ignore_errors=True)
    _run(["bash", "./Allmesh"], cwd=case_dir)


def _set_block_counts(case_dir: Path, nx: int, ny: int, nz: int) -> None:
    p = case_dir / "system" / "blockMeshDict"
    txt = p.read_text()
    pat = r"(hex\s*\(\s*0\s+1\s+2\s+3\s+4\s+5\s+6\s+7\s*\)\s*)\([^)]+\)"
    if not re.search(pat, txt):
        raise RuntimeError("Failed to locate blockMesh cell-count tuple")
    txt2 = re.sub(pat, rf"\1({nx} {ny} {nz})", txt, count=1)
    p.write_text(txt2)


def _poly_patches(boundary_path: Path) -> list[str]:
    out: list[str] = []
    lines = boundary_path.read_text().splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s in {"(", ")"} or s.endswith("{"):
            continue
        if i + 1 < len(lines) and lines[i + 1].strip() == "{":
            out.append(s)
    return out


def _sync_zero_gradient_boundary_entries(case_dir: Path) -> None:
    for region in ("jellyRoll", "shell", "cap"):
        b = case_dir / "constant" / region / "polyMesh" / "boundary"
        z = case_dir / "0" / region
        if not b.exists() or not z.exists():
            continue
        patches = _poly_patches(b)
        for f in z.iterdir():
            if not f.is_file():
                continue
            txt = f.read_text()
            if "boundaryField" not in txt:
                continue
            inserts = []
            for patch in patches:
                if re.search(rf"(^|\n)\s*{re.escape(patch)}\s*\{{", txt):
                    continue
                inserts.append(
                    f"    {patch}\n"
                    "    {\n"
                    "        type            zeroGradient;\n"
                    "    }\n"
                )
            if inserts:
                txt = txt.replace("boundaryField\n{", "boundaryField\n{\n" + "".join(inserts), 1)
                f.write_text(txt)


def _final_time(case_dir: Path) -> str:
    times = qv._numeric_times(case_dir)
    if not times:
        raise RuntimeError(f"No numeric times in {case_dir}")
    return times[-1]


def _temperature_means(case_dir: Path, time_name: str) -> tuple[dict[str, float], dict[str, float], float]:
    means = {}
    caps = {}
    for region in ("jellyRoll", "shell", "cap"):
        means[region] = qv._volavg(case_dir, region, time_name)
        cp, rho = qv._parse_cp_rho(case_dir, region)
        vol = qv._region_volume(case_dir, region)
        caps[region] = cp * rho * vol
    c_total = sum(caps.values())
    tcap = sum(caps[r] * means[r] for r in means) / c_total
    return means, caps, tcap


def _qsum_series(log_path: Path) -> tuple[np.ndarray, np.ndarray]:
    return qv._qsum_series(log_path)


def _final_region_minmax(log_path: Path, region: str) -> tuple[float, float, float]:
    cur_t = None
    active = None
    last = None
    for line in log_path.read_text(errors="ignore").splitlines():
        m = re.match(r"^\s*Time\s*=\s*([0-9eE+\-.]+)\s*$", line)
        if m:
            cur_t = float(m.group(1))
            continue
        m = re.match(r"^\s*Solving for solid region\s+(\S+)\s*$", line)
        if m:
            active = m.group(1)
            continue
        m = re.match(r"^\s*Min/max T:([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s*$", line)
        if m and active == region and cur_t is not None:
            last = (cur_t, float(m.group(1)), float(m.group(2)))
    if last is None:
        raise RuntimeError(f"No min/max for region {region} in {log_path}")
    return last


def _region_cells(case_dir: Path, region: str) -> int:
    out = _run(["checkMesh", "-case", str(case_dir), "-region", region], cwd=case_dir)
    m = re.search(r"cells:\s+([0-9]+)", out)
    if not m:
        raise RuntimeError(f"No cell count for {region} in {case_dir}")
    return int(m.group(1))


def _clock_time(log_path: Path) -> float | None:
    last = None
    for line in log_path.read_text(errors="ignore").splitlines():
        m = re.match(r"^ExecutionTime =\s*([0-9eE+\-.]+)\s*s\s+ClockTime =\s*([0-9eE+\-.]+)\s*s\s*$", line)
        if m:
            last = float(m.group(2))
    return last


def _count_time_steps(log_path: Path) -> int:
    return sum(1 for line in log_path.read_text(errors="ignore").splitlines() if re.match(r"^\s*Time\s*=\s*[0-9eE+\-.]+\s*$", line))


def _write_json(test_name: str, payload: dict) -> Path:
    out_dir = OUT_ROOT / test_name
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"metrics_{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return out


def run_test_timestep() -> dict:
    timestep_defs = [("dt1p0", 1.0), ("dt0p5", 0.5), ("dt0p25", 0.25)]
    vals = []
    for tag, dt_val in timestep_defs:
        c = _make_case_from(BASE_ECM_CASE, f"validation_lumped_fw_timestep_{tag}")
        _set_h_relaxation(c, 1.0)
        _set_runtime(c, end_time=12, write_interval=12)
        _set_max_di(c, DEV_MAX_DI)
        _set_adjust_timestep(c, False)
        _set_delta_t(c, dt_val)
        _set_ecm_call_every_step(c)
        log = _run_case(c, f"validation_lumped_fw_timestep_{tag}")
        t_end = _final_time(c)
        _, _, tcap = _temperature_means(c, t_end)
        _, qs = _qsum_series(log)
        vals.append(
            {
                "tag": tag,
                "delta_t": dt_val,
                "tcap_final_K": tcap,
                "qsum_final_W": float(qs[-1]),
                "log": str(log),
                "clock_s": _clock_time(log),
                "steps": _count_time_steps(log),
            }
        )
    by_tag = {v["tag"]: v for v in vals}
    d_t_05 = abs(by_tag["dt0p5"]["tcap_final_K"] - by_tag["dt0p25"]["tcap_final_K"])
    d_q_05 = abs(by_tag["dt0p5"]["qsum_final_W"] - by_tag["dt0p25"]["qsum_final_W"])
    passed = (d_t_05 <= 0.2) and (d_q_05 <= 0.25)
    return {"test": "timestep", "passed": passed, "delta_T_05_vs_025_K": d_t_05, "delta_Q_05_vs_025_W": d_q_05, "runs": vals}


def run_test_energy() -> dict:
    c = _make_case_from(BASE_AD_CASE, "validation_lumped_fw_energy")
    _set_runtime(c, end_time=60, write_interval=10)
    _set_max_di(c, DEV_MAX_DI)
    _set_h_relaxation(c, 1.0)
    _disable_ecm(c)
    _set_external_wall(c, "zeroGradient")
    _set_constant_source(c, QDOT_CONST)
    log = _run_case(c, "validation_lumped_fw_energy")
    t_end = _final_time(c)
    _, caps, tcap = _temperature_means(c, t_end)
    c_total = sum(caps.values())
    sim_time = float(t_end)
    e_expected = P_TOTAL_W * sim_time
    e_stored = c_total * (tcap - T0_K)
    err_pct = 100.0 * (e_stored - e_expected) / max(e_expected, 1.0e-12)
    passed = abs(err_pct) <= 2.0
    return {
        "test": "energy",
        "passed": passed,
        "sim_time_s": sim_time,
        "energy_expected_J": e_expected,
        "energy_stored_J": e_stored,
        "energy_error_percent": err_pct,
        "log": str(log),
        "clock_s": _clock_time(log),
        "steps": _count_time_steps(log),
    }


def run_test_mesh() -> dict:
    mesh_defs = [("coarse", (20, 20, 54)), ("medium", (28, 28, 76)), ("fine", (36, 36, 98))]
    runs = []
    for tag, (nx, ny, nz) in mesh_defs:
        c = _make_case_from(BASE_AD_CASE, f"validation_lumped_fw_mesh_{tag}")
        _set_block_counts(c, nx, ny, nz)
        _run_allmesh(c)
        _sync_zero_gradient_boundary_entries(c)
        _set_runtime(c, end_time=30, write_interval=30)
        _set_max_di(c, DEV_MAX_DI)
        _set_h_relaxation(c, 1.0)
        _disable_ecm(c)
        _set_external_wall(c, "zeroGradient")
        _set_constant_source(c, QDOT_CONST)
        log = _run_case(c, f"validation_lumped_fw_mesh_{tag}")
        t_end = _final_time(c)
        means, _, tcap = _temperature_means(c, t_end)
        _, _, tmax = _final_region_minmax(log, "jellyRoll")
        runs.append(
            {
                "tag": tag,
                "block_cells": nx * ny * nz,
                "jellyRoll_cells": _region_cells(c, "jellyRoll"),
                "tmax_jellyRoll_K": tmax,
                "tcap_K": tcap,
                "region_mean_T_K": means,
                "log": str(log),
                "clock_s": _clock_time(log),
                "steps": _count_time_steps(log),
            }
        )
    by_tag = {r["tag"]: r for r in runs}
    d_mf = abs(by_tag["medium"]["tmax_jellyRoll_K"] - by_tag["fine"]["tmax_jellyRoll_K"])
    passed = d_mf <= 0.25
    return {"test": "mesh", "passed": passed, "delta_Tmax_medium_vs_fine_K": d_mf, "runs": runs}


def run_test_ecm_zero() -> dict:
    c = _make_case_from(BASE_ECM_CASE, "validation_lumped_fw_ecm_zero")
    _set_runtime(c, end_time=30, write_interval=10)
    _set_max_di(c, DEV_MAX_DI)
    _set_adjust_timestep(c, False)
    _set_delta_t(c, 1.0)
    _set_h_relaxation(c, 1.0)
    _set_current(c, 0.0)
    _set_ecm_call_every_step(c)
    log = _run_case(c, "validation_lumped_fw_ecm_zero")
    ts, qs = _qsum_series(log)
    t_end = _final_time(c)
    _, _, tcap = _temperature_means(c, t_end)
    drift = abs(tcap - T0_K)
    max_abs_q = float(np.max(np.abs(qs))) if len(qs) else math.inf
    passed = (max_abs_q <= 0.5) and (drift <= 0.05)
    return {
        "test": "ecm_zero",
        "passed": passed,
        "max_abs_qsum_W": max_abs_q,
        "tcap_final_K": tcap,
        "tcap_drift_K": drift,
        "samples": int(len(ts)),
        "log": str(log),
        "clock_s": _clock_time(log),
        "steps": _count_time_steps(log),
    }


def run_test_ecm_current() -> dict:
    c = _make_case_from(BASE_ECM_CASE, "validation_lumped_fw_ecm_current")
    _set_runtime(c, end_time=30, write_interval=10)
    _set_max_di(c, DEV_MAX_DI)
    _set_adjust_timestep(c, False)
    _set_delta_t(c, 0.5)
    _set_h_relaxation(c, 1.0)
    _set_current(c, 79.0)
    _set_ecm_call_every_step(c)
    log = _run_case(c, "validation_lumped_fw_ecm_current")
    ts, qs = _qsum_series(log)
    if len(qs) < 3:
        d2_max = math.inf
    else:
        d2 = np.diff(qs, n=2)
        d2_max = float(np.max(np.abs(d2)))
    n_steps = _count_time_steps(log)
    n_q = int(len(qs))
    txt = log.read_text(errors="ignore")
    n_real_ecm = len(re.findall(r"Real ECM", txt))
    cadence_ok = (n_real_ecm == 0) or (n_real_ecm >= max(n_steps - 1, 1))
    passed = (n_q == n_steps) and cadence_ok and (d2_max <= 5.0)
    return {
        "test": "ecm_current",
        "passed": passed,
        "time_steps": n_steps,
        "qsum_samples": n_q,
        "real_ecm_markers": n_real_ecm,
        "max_abs_second_diff_qsum_W": d2_max,
        "log": str(log),
        "clock_s": _clock_time(log),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run forward-only lumped validation tests")
    parser.add_argument(
        "--test",
        choices=("timestep", "energy", "mesh", "ecm_zero", "ecm_current"),
        required=True,
        help="Run exactly one test",
    )
    args = parser.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.test == "timestep":
        res = run_test_timestep()
    elif args.test == "energy":
        res = run_test_energy()
    elif args.test == "mesh":
        res = run_test_mesh()
    elif args.test == "ecm_zero":
        res = run_test_ecm_zero()
    else:
        res = run_test_ecm_current()

    out = _write_json(args.test, res)
    print(out)
    if not res["passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
