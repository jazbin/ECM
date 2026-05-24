#!/usr/bin/env python3
"""
Live monitor: tail the latest caseLong run log and compare to validationData.csv.
Runs every 60 s, appends a summary row to monitor_live.txt.
"""
import re, time, glob, os, sys
import numpy as np
import pandas as pd

LOG_DIR   = os.path.join(os.path.dirname(__file__), "logs")
VAL_CSV   = "/workspace/projectConstraintsParameters/validationData.csv"
OUT_FILE  = os.path.join(os.path.dirname(__file__), "monitor_live.txt")
INTERVAL  = 60   # seconds

val = pd.read_csv(VAL_CSV)
T_val = np.array(val["T_cell_K"])
Q_val = np.array(val["Q_cell_W"])
t_val = np.array(val["t_ss"])

pat_energy = re.compile(
    r"EnergyDebug region jellyRoll_rotated time ([\d.eE+\-]+).*TAvgAfter ([\d.eE+\-]+)"
)
pat_q = re.compile(r"^Q_sum_check ([\d.eE+\-]+) W")

def latest_log():
    logs = sorted(glob.glob(os.path.join(LOG_DIR, "run_*.log")))
    return logs[-1] if logs else None

def parse_log(logpath):
    times, Tsim, Qsim = [], [], []
    with open(logpath, errors="replace") as f:
        for line in f:
            m = pat_energy.search(line)
            if m:
                times.append(float(m.group(1)))
                Tsim.append(float(m.group(2)))
                continue
            m = pat_q.match(line.strip())
            if m:
                Qsim.append(float(m.group(1)))
    n = min(len(times), len(Qsim))
    return np.array(times[:n]), np.array(Tsim[:n]), np.array(Qsim[:n])

def stats(t_sim, T_sim, Q_sim):
    if len(t_sim) == 0:
        return None
    t_end = t_sim[-1]
    T_v   = np.interp(t_sim, t_val, T_val)
    Q_v   = np.interp(t_sim, t_val, Q_val)

    def win(lo, hi):
        m = (t_sim > lo) & (t_sim <= hi)
        if m.sum() == 0:
            return None
        dT = T_sim[m] - T_v[m]
        dQ = Q_sim[m] - Q_v[m]
        return {
            "n": m.sum(),
            "T_rmse": float(np.sqrt(np.mean(dT**2))),
            "T_bias": float(np.mean(dT)),
            "Q_rmse": float(np.sqrt(np.mean(dQ**2))),
            "Q_bias": float(np.mean(dQ)),
            "T_sim_last": float(T_sim[m][-1]),
            "T_val_last": float(T_v[m][-1]),
        }

    return {
        "t_end": t_end,
        "T_sim_now": float(T_sim[-1]),
        "T_val_now": float(np.interp(t_end, t_val, T_val)),
        "Q_sim_now": float(Q_sim[-1]),
        "Q_val_now": float(np.interp(t_end, t_val, Q_val)),
        "w0_180":   win(0,   180),
        "w400_1260":win(400, 1260),
        "w1260_end":win(1260, t_end) if t_end > 1260 else None,
    }

header = (
    f"{'time':>8} {'T_sim':>8} {'T_val':>8} {'dT':>7} "
    f"{'Q_sim':>7} {'Q_val':>7} {'dQ':>7} | "
    f"Q_rmse(0-180) Q_rmse(400-1260) T_rmse(1260-end)"
)

with open(OUT_FILE, "w") as f:
    f.write(header + "\n")
    f.write("-" * len(header) + "\n")
print(f"Monitor started. Output: {OUT_FILE}", flush=True)
print(header, flush=True)

while True:
    log = latest_log()
    if log:
        t_sim, T_sim, Q_sim = parse_log(log)
        s = stats(t_sim, T_sim, Q_sim)
        if s:
            w0   = s["w0_180"]
            w4   = s["w400_1260"]
            w12  = s["w1260_end"]
            q0   = f"{w0['Q_rmse']:.3f}" if w0 else "  --  "
            q4   = f"{w4['Q_rmse']:.3f}" if w4 else "  --  "
            t12  = f"{w12['T_rmse']:.3f}" if w12 else "  --  "
            row = (
                f"{s['t_end']:8.1f} {s['T_sim_now']:8.3f} {s['T_val_now']:8.3f} "
                f"{s['T_sim_now']-s['T_val_now']:+7.3f} "
                f"{s['Q_sim_now']:7.4f} {s['Q_val_now']:7.4f} "
                f"{s['Q_sim_now']-s['Q_val_now']:+7.4f} | "
                f"{q0:>13} {q4:>15} {t12:>17}"
            )
            with open(OUT_FILE, "a") as f:
                f.write(row + "\n")
            print(row, flush=True)
    time.sleep(INTERVAL)
