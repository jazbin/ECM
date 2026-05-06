#!/usr/bin/env python3
"""
mock_starccm_dryrun.py
======================
Dry-run smoke test that mimics EcmCouplerMacro.java behaviour without STAR-CCM+.

Temperature source (--temp-source):
  lumped      — use T_feedback_degC from the validated lumped OpenFOAM run
                (artifacts/h_sweep/caseLong_h_sweep_20260501_191029/h_110p0/ecm_wrapper_summary.csv)
  distributed — use t_eff_k from the distributed SOC-fix run
                (rev4/dist_3600_fulllog/ecm/heatBalanceHistory.csv)
  fake        — compute T online with a 0-D lumped thermal model (no OpenFOAM data needed)

Per-step loop (mirrors EcmCouplerMacro.java exactly):
  1. Interpolate T_eff from the chosen OpenFOAM T history (or fake model)
  2. Interpolate current_A from electrical_inputs CSV at current sim time
  3. Write ecm_in.bin  (binary v2, N=1, nInputs=1 with current_A)
  4. Subprocess-call ecm_coupler.py  (same env vars as Java macro)
  5. Read ecm_out.bin → Q_GEN [W]  (lumped N=1: record value is watts)
  6. Compare Q to reference Q from the same OpenFOAM run
  7. Write summary CSV + pass/fail

Usage:
    python3 tools/mock_starccm_dryrun.py --temp-source lumped
    python3 tools/mock_starccm_dryrun.py --temp-source distributed --n-steps 400 --dt 1.0
    python3 tools/mock_starccm_dryrun.py --temp-source fake --n-steps 40 --dt 100
"""
from __future__ import annotations
import argparse, csv, math, os, shutil, struct, subprocess, sys, time
from pathlib import Path
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path("/workspace")

LUMPED_CSV = WORKSPACE / "artifacts/h_sweep/caseLong_h_sweep_20260501_191029/h_110p0/ecm_wrapper_summary.csv"
DIST_CSV   = WORKSPACE / "rev4/dist_3600_fulllog/ecm/heatBalanceHistory.csv"
ELEC_CSV   = WORKSPACE / "rev4/dist_3600_fulllog/constant/electrical_inputs_from_validation.csv"
PYTHON_DIR = WORKSPACE / "rev4/python"

DEFAULT_ECM_DIR = Path("/tmp/starccm_dryrun_ecm")
DEFAULT_OUT_CSV = WORKSPACE / "artifacts/plots/starccm_dryrun_results.csv"

PYTHON_EXE = sys.executable

# 21700 cell geometry
CELL_VOLUME_M3 = math.pi * 0.0105**2 * 0.070   # ~2.42e-5 m3

# Fake 0-D thermal model constants
MASS_KG    = 0.065
CP_J_KG_K  = 900.0
H_CONV_W_K = 0.46
T_AMB_K    = 298.15

# ---------------------------------------------------------------------------
# Binary protocol  (matches EcmBinaryIO.java exactly)
# ---------------------------------------------------------------------------
MAGIC = b"ECMIOv1\x00"

def write_ecm_in(path: Path, step_id: int, t_eff_k: float,
                 sim_time: float, dt: float, current_a: float):
    """Write ecm_in.bin — v2, N=1 cell, nInputs=1 (current_A)."""
    name_b = b"current_A"
    buf = bytearray()
    buf += struct.pack("<8sIIIddII", MAGIC, 1, 2, 1, sim_time, dt, 0, 1)
    buf += struct.pack("<Q", step_id)
    buf += struct.pack("<I", len(name_b)) + name_b
    buf += struct.pack("<d", current_a)
    buf += struct.pack("<i", 0)
    buf += struct.pack("<d", t_eff_k)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(bytes(buf))
    tmp.rename(path)


def read_ecm_out(path: Path, expected_step_id: int):
    """Return (q_gen_W, ok). q_gen_W is total watts for lumped N=1 output."""
    data = path.read_bytes()
    off = 8
    _ft, _ver, _N = struct.unpack_from("<III", data, off); off += 12
    _t, _dt       = struct.unpack_from("<dd",  data, off); off += 16
    _km, n_inp    = struct.unpack_from("<II",  data, off); off += 8
    sid,          = struct.unpack_from("<Q",   data, off); off += 8
    if sid != expected_step_id:
        return 0.0, False
    for _ in range(n_inp):
        nl, = struct.unpack_from("<I", data, off); off += 4
        off += nl + 8
    _key, q_gen_w = struct.unpack_from("<id", data, off)
    return q_gen_w, True

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_lumped_run(path: Path):
    """Return dict of numpy arrays: time_s, T_K, Q_W, current_A."""
    t, T, Q, I = [], [], [], []
    with path.open() as f:
        reader = csv.DictReader(f)
        prev_t = -1.0
        for row in reader:
            tv = float(row["time_s"])
            if tv <= prev_t:          # reset on restart
                t.clear(); T.clear(); Q.clear(); I.clear()
            prev_t = tv
            t.append(tv)
            T.append(float(row["T_feedback_degC"]) + 273.15)
            Q.append(float(row["Q_GEN_W"]))
            I.append(float(row["current_a"]))
    return {"t": np.array(t), "T_K": np.array(T),
            "Q_W": np.array(Q), "I_A": np.array(I)}


def load_distributed_run(path: Path):
    """Return dict: time_s, T_K, Q_W.  No current_a — load from elec CSV."""
    t, T, Q = [], [], []
    with path.open() as f:
        reader = csv.DictReader(f)
        prev_t = -1.0
        for row in reader:
            tv = float(row["time_s"])
            if tv <= prev_t:
                t.clear(); T.clear(); Q.clear()
            prev_t = tv
            t.append(tv)
            T.append(float(row["t_eff_k"]))
            Q.append(float(row["q_raw_w"]))
    return {"t": np.array(t), "T_K": np.array(T),
            "Q_W": np.array(Q), "I_A": None}


def load_current_csv(path: Path):
    times, amps = [], []
    with path.open() as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [c.strip().strip('"') for c in (reader.fieldnames or [])]
        for row in reader:
            i_str = row.get("current_A", "").strip()
            if not i_str:
                continue
            try:
                times.append(float(row["time"]))
                amps.append(float(i_str))
            except (KeyError, ValueError):
                pass
    return np.array(times), np.array(amps)


# ---------------------------------------------------------------------------
# Stage ECM files into working dir
# ---------------------------------------------------------------------------
def stage_ecm_files(ecm_dir: Path):
    ecm_dir.mkdir(parents=True, exist_ok=True)
    for fname in ["ecm_coupler.py", "ecm_io.py", "ecm_step.py",
                  "mock_ecm_backend.py", "mock_model.py", "params.csv"]:
        src = PYTHON_DIR / fname
        if src.exists():
            shutil.copy(src, ecm_dir / fname)
        elif not (ecm_dir / fname).exists():
            sys.exit(f"ERROR: {fname} not found in {PYTHON_DIR}")
    csv_dst = ecm_dir / "electrical_inputs_from_validation.csv"
    if ELEC_CSV.exists() and not csv_dst.exists():
        shutil.copy(ELEC_CSV, csv_dst)
    for stale in ["ecm_state.json", "ecm_in.bin", "ecm_out.bin", "ecm_last_good.bin"]:
        (ecm_dir / stale).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--temp-source", choices=["lumped", "distributed", "fake"],
                    default="lumped",
                    help="Source for T_eff fed into ECM each step")
    ap.add_argument("--ecm-dir",  type=Path, default=DEFAULT_ECM_DIR)
    ap.add_argument("--n-steps",  type=int,  default=None,
                    help="Number of steps (default: match source timeseries length)")
    ap.add_argument("--dt",       type=float, default=None,
                    help="Timestep [s] (default: match source timeseries dt)")
    ap.add_argument("--alpha",    type=float, default=1.0)
    ap.add_argument("--out-csv",  type=Path, default=DEFAULT_OUT_CSV)
    args = ap.parse_args()

    ecm_dir = args.ecm_dir
    stage_ecm_files(ecm_dir)

    # ---- load temperature source ----
    if args.temp_source == "lumped":
        if not LUMPED_CSV.exists():
            sys.exit(f"Lumped CSV not found: {LUMPED_CSV}")
        ref = load_lumped_run(LUMPED_CSV)
        source_label = "Lumped OpenFOAM run (h=110)"
        print(f"T source: {LUMPED_CSV.name}")
    elif args.temp_source == "distributed":
        if not DIST_CSV.exists():
            sys.exit(f"Distributed CSV not found: {DIST_CSV}")
        ref = load_distributed_run(DIST_CSV)
        source_label = "Distributed OpenFOAM run (SOC-fix)"
        print(f"T source: {DIST_CSV.name}")
    else:
        ref = None
        source_label = "Fake 0-D thermal model"
        print("T source: fake 0-D lumped thermal model")

    # ---- current profile ----
    cur_t, cur_I = load_current_csv(ecm_dir / "electrical_inputs_from_validation.csv")
    print(f"Current profile: {len(cur_t)} rows, I_max={cur_I.max():.2f} A")

    # ---- determine n_steps and dt ----
    if ref is not None:
        ref_t = ref["t"]
        dt = args.dt or float(ref_t[1] - ref_t[0])
        n_steps = args.n_steps or len(ref_t)
    else:
        dt = args.dt or 1.0
        n_steps = args.n_steps or 3600

    print(f"Steps: {n_steps} × dt={dt:.2f} s = {n_steps*dt:.0f} s")
    print(f"Cell volume: {CELL_VOLUME_M3:.4e} m3")
    print()

    # ---- ECM subprocess env ----
    ecm_env = os.environ.copy()
    ecm_env.update({
        "ECM_USE_REAL_STEP":     "1",
        "ECM_STATE_FILE":        str(ecm_dir / "ecm_state.json"),
        "ECM_INTERP_MODE":       "linear",
        "ECM_LOG_EVERY_N_STEPS": "999999",
    })

    ecm_in  = ecm_dir / "ecm_in.bin"
    ecm_out = ecm_dir / "ecm_out.bin"
    script  = ecm_dir / "ecm_coupler.py"

    # ---- fake thermal state ----
    T_fake_k = T_AMB_K

    results = []
    q_gen_w  = 0.0
    errors   = 0
    t_wall   = time.time()

    print(f"{'Step':>6}  {'Time':>7}  {'T_eff':>8}  {'I':>7}  "
          f"{'Q_ecm':>8}  {'Q_ref':>8}  {'err%':>6}")
    print("-" * 65)

    log_every = max(1, n_steps // 40)

    for step in range(n_steps):
        step_id  = step + 1
        sim_time = step_id * dt

        # ---- T_eff for this step ----
        if ref is not None:
            T_k = float(np.interp(sim_time, ref["t"], ref["T_K"]))
            if ref["I_A"] is not None:
                current_a = float(np.interp(sim_time, ref["t"], ref["I_A"]))
            else:
                current_a = float(np.interp(sim_time, cur_t, cur_I))
        else:
            T_k = T_fake_k
            current_a = float(np.interp(sim_time, cur_t, cur_I))

        # ---- reference Q (for comparison) ----
        if ref is not None:
            Q_ref = float(np.interp(sim_time, ref["t"], ref["Q_W"]))
        else:
            Q_ref = float("nan")

        # ---- write ecm_in.bin ----
        write_ecm_in(ecm_in, step_id, T_k, sim_time, dt, current_a)
        ecm_out.unlink(missing_ok=True)

        # ---- subprocess ----
        res = subprocess.run(
            [PYTHON_EXE, str(script)],
            cwd=str(ecm_dir),
            env=ecm_env,
            capture_output=True,
            timeout=120,
        )

        if res.returncode != 0 or not ecm_out.exists():
            errors += 1
            err = res.stderr.decode(errors="replace").strip().splitlines()
            print(f"  step {step_id} t={sim_time:.0f}s  ECM error: "
                  f"{err[-1] if err else 'no output'}")
            if errors > 5:
                sys.exit("Too many ECM errors — aborting")
        else:
            q_new, ok = read_ecm_out(ecm_out, step_id)
            if ok:
                q_gen_w = args.alpha * q_new + (1.0 - args.alpha) * q_gen_w

        # ---- fake thermal update (only if no reference) ----
        if ref is None:
            q_cool = H_CONV_W_K * (T_fake_k - T_AMB_K)
            T_fake_k += (q_gen_w - q_cool) / (MASS_KG * CP_J_KG_K) * dt

        # ---- error vs reference ----
        if not math.isnan(Q_ref) and abs(Q_ref) > 1e-6:
            err_pct = (q_gen_w - Q_ref) / abs(Q_ref) * 100.0
        else:
            err_pct = float("nan")

        if step_id % log_every == 0 or step_id <= 3:
            elapsed = time.time() - t_wall
            ref_str = f"{Q_ref:8.4f}" if not math.isnan(Q_ref) else "     N/A"
            err_str = f"{err_pct:+6.1f}%" if not math.isnan(err_pct) else "    N/A"
            print(f"{step_id:6d}  {sim_time:7.1f}s  "
                  f"{T_k-273.15:7.3f}°C  {current_a:7.3f}A  "
                  f"{q_gen_w:8.4f}W  {ref_str}W  {err_str}  [{elapsed:.1f}s]")

        results.append({
            "time_s":    sim_time,
            "T_degC":    T_k - 273.15,
            "current_A": current_a,
            "Q_ecm_W":   q_gen_w,
            "Q_ref_W":   Q_ref,
            "err_pct":   err_pct,
        })

    # ---- save CSV ----
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader(); w.writerows(results)

    # ---- summary stats ----
    elapsed_total = time.time() - t_wall
    valid = [r for r in results if not math.isnan(r["Q_ref_W"])]
    Q_max_ecm = max(r["Q_ecm_W"] for r in results)
    T_max     = max(r["T_degC"]  for r in results)

    print()
    print(f"Done. {n_steps} steps in {elapsed_total:.1f}s "
          f"({elapsed_total/n_steps*1000:.0f} ms/step)")

    if valid:
        rmse = math.sqrt(sum((r["Q_ecm_W"] - r["Q_ref_W"])**2 for r in valid) / len(valid))
        bias = sum(r["Q_ecm_W"] - r["Q_ref_W"] for r in valid) / len(valid)
        print(f"vs {source_label}:")
        print(f"  Q RMSE = {rmse:.4f} W   bias = {bias:+.4f} W")
        print(f"  T_max  = {T_max:.3f} °C  Q_max = {Q_max_ecm:.4f} W")
    else:
        print(f"  T_max  = {T_max:.3f} °C  Q_max = {Q_max_ecm:.4f} W")

    print(f"Results: {args.out_csv}")

    # ---- pass/fail ----
    if valid:
        passed = errors == 0 and Q_max_ecm > 0.5 and rmse < 1.0
        crit   = "no errors, Q_max>0.5W, Q RMSE<1.0W vs reference"
    else:
        passed = errors == 0 and Q_max_ecm > 0.001
        crit   = "no errors, Q_max>0.001W"

    print()
    print("=" * 56)
    print(f"SMOKE TEST: {'PASS ✓' if passed else 'FAIL ✗'}  [{crit}]")
    if valid:
        print(f"  Q RMSE  = {rmse:.4f} W")
        print(f"  Q bias  = {bias:+.4f} W")
    print(f"  Q_max   = {Q_max_ecm:.4f} W")
    print(f"  T_max   = {T_max:.3f} °C")
    print(f"  errors  = {errors}")
    print("=" * 56)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
