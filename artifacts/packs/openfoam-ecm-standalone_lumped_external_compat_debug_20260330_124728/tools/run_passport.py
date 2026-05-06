#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


LOG_SCAN_PATTERNS = [
    re.compile(r"FOAM FATAL", re.IGNORECASE),
    re.compile(r"Floating point exception", re.IGNORECASE),
    re.compile(r"\bnan\b", re.IGNORECASE),
    re.compile(r"\binf\b", re.IGNORECASE),
    re.compile(r"\bsigFpe\b", re.IGNORECASE),
]

RE_TIME = re.compile(r"^Time =\s*([0-9eE+\-\.]+)\s*$")
RE_RESIDUAL = re.compile(
    r"Solving for (\S+), Initial residual = ([0-9eE+\-\.]+), Final residual = ([0-9eE+\-\.]+), No Iterations (\d+)"
)
RE_COURANT = re.compile(r"Courant Number mean:\s*([0-9eE+\-\.]+)\s*max:\s*([0-9eE+\-\.]+)")
RE_CONTINUITY = re.compile(
    r"time step continuity errors : sum local = ([0-9eE+\-\.]+), global = ([0-9eE+\-\.]+), cumulative = ([0-9eE+\-\.]+)"
)
RE_TMINMAX = re.compile(r"(min|max)\(T\)\s*=\s*([0-9eE+\-\.]+)")
RE_QSUM = re.compile(r"Q_sum_check\s+([0-9eE+\-\.]+)\s*W")
RE_QINT = re.compile(r"volIntegrate\(solid\) of ecmQdot =\s*([0-9eE+\-\.]+)")
RE_ENERGY = re.compile(
    r"EnergyBalance\(solid\)\s+E=([0-9eE+\-\.]+)\s+dE/dt=([0-9eE+\-\.]+)\s+Qsrc=([0-9eE+\-\.]+)\s+QfluxOut=([0-9eE+\-\.]+)\s+residual=([0-9eE+\-\.]+)"
)
RE_INTERFACE_FLUX = re.compile(
    r"sum\(solid_to_fluid\) of wallHeatFlux =\s*([0-9eE+\-\.]+)"
)


def git_sha(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root)
        ).decode("utf-8")
        return out.strip()
    except Exception:
        return "unknown"


def read_control_dict(case_path: Path) -> dict:
    control = case_path / "system" / "controlDict"
    time_step = None
    write_interval = None
    if not control.exists():
        return {"time_step": None, "write_interval": None}
    for line in control.read_text().splitlines():
        if line.strip().startswith("deltaT"):
            parts = line.split()
            if len(parts) >= 2:
                time_step = float(parts[1].rstrip(";"))
        if line.strip().startswith("writeInterval"):
            parts = line.split()
            if len(parts) >= 2:
                write_interval = float(parts[1].rstrip(";"))
    return {"time_step": time_step, "write_interval": write_interval}


def load_config(config_path: Path, case_name: str) -> dict:
    cfg = json.loads(config_path.read_text())
    defaults = cfg.get("defaults", {})
    case_cfg = cfg.get("cases", {}).get(case_name, {})
    merged = json.loads(json.dumps(defaults))
    for k, v in case_cfg.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def scan_log(log_path: Path):
    text = log_path.read_text(errors="ignore")
    fatal = any(p.search(text) for p in LOG_SCAN_PATTERNS)
    return fatal


def parse_log_timeseries(log_path: Path):
    metrics = {
        "residuals": {},
        "courant": {"mean": [], "max": []},
        "continuity": {"local": [], "global": [], "cumulative": []},
        "temperature": {"min": [], "max": []},
        "coupling": {"Q_sum_check": [], "Q_integral": [], "interface_flux_sum": []},
        "energy": {"E": [], "dEdt": [], "Qsrc": [], "QfluxOut": [], "residual": []},
        "times": [],
    }
    current_time = None

    for raw in log_path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        m_time = RE_TIME.match(line)
        if m_time:
            current_time = float(m_time.group(1))
            metrics["times"].append(current_time)
            continue

        m_res = RE_RESIDUAL.search(line)
        if m_res:
            field = m_res.group(1)
            init = float(m_res.group(2))
            final = float(m_res.group(3))
            iters = int(m_res.group(4))
            rec = metrics["residuals"].setdefault(field, {"initial": [], "final": [], "iters": []})
            rec["initial"].append(init)
            rec["final"].append(final)
            rec["iters"].append(iters)
            continue

        m_co = RE_COURANT.search(line)
        if m_co:
            metrics["courant"]["mean"].append(float(m_co.group(1)))
            metrics["courant"]["max"].append(float(m_co.group(2)))
            continue

        m_cont = RE_CONTINUITY.search(line)
        if m_cont:
            metrics["continuity"]["local"].append(float(m_cont.group(1)))
            metrics["continuity"]["global"].append(float(m_cont.group(2)))
            metrics["continuity"]["cumulative"].append(float(m_cont.group(3)))
            continue

        if "fieldMinMax" in line and "TMinMax" in line:
            continue

        m_tmm = RE_TMINMAX.search(line)
        if m_tmm:
            kind = m_tmm.group(1)
            val = float(m_tmm.group(2))
            metrics["temperature"][kind].append(val)
            continue

        m_qsum = RE_QSUM.search(line)
        if m_qsum:
            metrics["coupling"]["Q_sum_check"].append(float(m_qsum.group(1)))
            continue

        m_qint = RE_QINT.search(line)
        if m_qint:
            metrics["coupling"]["Q_integral"].append(float(m_qint.group(1)))
            continue

        m_int = RE_INTERFACE_FLUX.search(line)
        if m_int:
            metrics["coupling"]["interface_flux_sum"].append(float(m_int.group(1)))
            continue

        m_energy = RE_ENERGY.search(line)
        if m_energy:
            metrics["energy"]["E"].append(float(m_energy.group(1)))
            metrics["energy"]["dEdt"].append(float(m_energy.group(2)))
            metrics["energy"]["Qsrc"].append(float(m_energy.group(3)))
            metrics["energy"]["QfluxOut"].append(float(m_energy.group(4)))
            metrics["energy"]["residual"].append(float(m_energy.group(5)))
            continue

    return metrics


def max_abs(values):
    if not values:
        return None
    return max(abs(v) for v in values)


def last_value(values):
    if not values:
        return None
    return values[-1]


def build_passport(case_path: Path, log_path: Path, config_path: Path) -> dict:
    case_name = case_path.name
    cfg = load_config(config_path, case_name)

    meta = {
        "case_name": case_name,
        "case_path": str(case_path),
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(case_path),
        "openfoam_version": os.environ.get("WM_PROJECT_VERSION", "unknown"),
        "solver": cfg.get("solver", "unknown"),
        "host": os.uname().nodename,
        "n_procs": int(os.environ.get("OMPI_COMM_WORLD_SIZE", "1")),
    }

    ctrl = read_control_dict(case_path)
    metrics_ts = parse_log_timeseries(log_path)
    fatal = scan_log(log_path)

    temperature_min = min(metrics_ts["temperature"]["min"]) if metrics_ts["temperature"]["min"] else None
    temperature_max = max(metrics_ts["temperature"]["max"]) if metrics_ts["temperature"]["max"] else None

    qsum = last_value(metrics_ts["coupling"]["Q_sum_check"])
    qint = last_value(metrics_ts["coupling"]["Q_integral"])
    power_mismatch_rel = None
    if qsum is not None and qint is not None:
        denom = max(abs(qsum), 1e-12)
        power_mismatch_rel = abs(qsum - qint) / denom

    energy_residual = last_value(metrics_ts["energy"]["residual"])
    energy_qsrc = last_value(metrics_ts["energy"]["Qsrc"])
    energy_qflux = last_value(metrics_ts["energy"]["QfluxOut"])
    energy_residual_rel = None
    if energy_residual is not None and energy_qsrc is not None and energy_qflux is not None:
        denom = max(abs(energy_qsrc) + abs(energy_qflux), 1e-12)
        energy_residual_rel = abs(energy_residual) / denom

    metrics = {
        "log_scan.fatal_or_nan": fatal,
        "residuals.max_initial": {
            k: max(v["initial"]) if v["initial"] else None
            for k, v in metrics_ts["residuals"].items()
        },
        "continuity.global_abs_max": max_abs(metrics_ts["continuity"]["global"]),
        "courant.max": max_abs(metrics_ts["courant"]["max"]),
        "temperature.min": temperature_min,
        "temperature.max": temperature_max,
        "coupling.Q_sum_check": qsum,
        "coupling.Q_integral": qint,
        "coupling.power_mismatch_rel": power_mismatch_rel,
        "coupling.interface_flux_sum": last_value(metrics_ts["coupling"]["interface_flux_sum"]),
        "energy.solid.residual_rel": energy_residual_rel,
        "energy.solid.residual": energy_residual,
    }

    thresholds = cfg
    pass_fail = {
        "fatal_or_nan": not fatal,
        "temperature.min": (
            temperature_min is None or temperature_min >= thresholds["temperature"]["min_K"]
        ),
        "temperature.max": (
            temperature_max is None or temperature_max <= thresholds["temperature"]["max_K"]
        ),
        "continuity.global_abs_max": (
            metrics["continuity.global_abs_max"] is None
            or metrics["continuity.global_abs_max"] <= thresholds["continuity"]["global_abs_max"]
        ),
        "courant.max": (
            metrics["courant.max"] is None or metrics["courant.max"] <= thresholds["courant"]["max"]
        ),
        "energy.solid.residual_rel": (
            metrics["energy.solid.residual_rel"] is None
            or metrics["energy.solid.residual_rel"] <= thresholds["energy"]["residual_rel_max"]
        ),
        "coupling.power_mismatch_rel": (
            metrics["coupling.power_mismatch_rel"] is None
            or metrics["coupling.power_mismatch_rel"] <= thresholds["coupling"]["power_mismatch_rel_max"]
        ),
    }
    overall_pass = all(pass_fail.values())

    return {
        "metadata": meta,
        "config": {
            "time_step": ctrl["time_step"],
            "write_interval": ctrl["write_interval"],
            "thresholds": thresholds,
        },
        "metrics": metrics,
        "pass": overall_pass,
        "pass_fail": pass_fail,
    }, metrics_ts


def write_timeseries_csv(path: Path, metrics_ts: dict):
    rows = []
    for field, series in metrics_ts.get("residuals", {}).items():
        for v in series["initial"]:
            rows.append({"time": None, "metric_name": f"residual.initial.{field}", "value": v})

    for v in metrics_ts["courant"]["max"]:
        rows.append({"time": None, "metric_name": "courant.max", "value": v})
    for v in metrics_ts["continuity"]["global"]:
        rows.append({"time": None, "metric_name": "continuity.global", "value": v})

    for v in metrics_ts["temperature"]["min"]:
        rows.append({"time": None, "metric_name": "temperature.min", "value": v})
    for v in metrics_ts["temperature"]["max"]:
        rows.append({"time": None, "metric_name": "temperature.max", "value": v})

    for v in metrics_ts["coupling"]["Q_sum_check"]:
        rows.append({"time": None, "metric_name": "coupling.Q_sum_check", "value": v})
    for v in metrics_ts["coupling"]["Q_integral"]:
        rows.append({"time": None, "metric_name": "coupling.Q_integral", "value": v})
    for v in metrics_ts["coupling"]["interface_flux_sum"]:
        rows.append({"time": None, "metric_name": "coupling.interface_flux_sum", "value": v})

    for v in metrics_ts["energy"]["residual"]:
        rows.append({"time": None, "metric_name": "energy.solid.residual", "value": v})

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "metric_name", "value"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, help="Case directory")
    parser.add_argument("--log", required=True, help="Solver log path")
    parser.add_argument("--config", default="tools/metrics_config.json")
    parser.add_argument("--out", default="run_passport.json")
    parser.add_argument("--timeseries", default="metrics_timeseries.csv")
    args = parser.parse_args()

    case_path = Path(args.case).resolve()
    log_path = Path(args.log).resolve()
    config_path = Path(args.config).resolve()

    passport, metrics_ts = build_passport(case_path, log_path, config_path)

    Path(args.out).write_text(json.dumps(passport, indent=2))
    write_timeseries_csv(Path(args.timeseries), metrics_ts)


if __name__ == "__main__":
    main()
