#!/usr/bin/env python3
import argparse
import csv
import io
import math
import sys
import zipfile


def load_csv_rows(path=None, zip_path=None, member=None):
    if zip_path:
        if not member:
            raise ValueError("--member is required when using --zip")
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(member) as f:
                data = f.read()
        text = data.decode("utf-8", errors="ignore")
        return list(csv.DictReader(io.StringIO(text)))
    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def find_key(row, candidates):
    for key in row.keys():
        for c in candidates:
            if key.strip().lower() == c:
                return key
    return None


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def interpolate(x, xs, ys):
    if not xs or not ys or len(xs) != len(ys):
        return None
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo = 0
    hi = len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    x0, x1 = xs[lo], xs[hi]
    y0, y1 = ys[lo], ys[hi]
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def rmse(values):
    if not values:
        return None
    return math.sqrt(sum(v * v for v in values) / len(values))


def main():
    parser = argparse.ArgumentParser(description="Validate TU Berlin dataset against simulation outputs.")
    parser.add_argument("--zip", dest="zip_path", help="Path to TU Berlin dataset ZIP")
    parser.add_argument("--member", help="CSV member path inside ZIP")
    parser.add_argument("--csv", dest="csv_path", help="Path to extracted TU Berlin CSV")
    parser.add_argument("--sim", required=True, help="Simulation CSV with time/voltage/temperature columns")
    parser.add_argument("--out", help="Optional output metrics CSV")
    args = parser.parse_args()

    if not args.zip_path and not args.csv_path:
        parser.error("Provide --zip or --csv")
    if args.zip_path and args.csv_path:
        parser.error("Provide only one of --zip or --csv")

    measured_rows = load_csv_rows(path=args.csv_path, zip_path=args.zip_path, member=args.member)
    if not measured_rows:
        raise SystemExit("No measured rows found")

    sim_rows = load_csv_rows(path=args.sim)
    if not sim_rows:
        raise SystemExit("No simulation rows found")

    m0 = measured_rows[0]
    s0 = sim_rows[0]

    m_time_key = find_key(m0, ["time"])
    m_v_key = find_key(m0, ["voltage", "v"])
    m_tcore_key = find_key(m0, ["inner_temp", "t_core", "tinner", "t_core_c", "t_inner"])
    m_tsurf_key = find_key(m0, ["outer_temp", "t_surf", "tsurf", "t_outer", "t_surface"])

    s_time_key = find_key(s0, ["time", "t"])
    s_v_key = find_key(s0, ["voltage", "v"])
    s_tcore_key = find_key(s0, ["t_core", "tinner", "t_inner", "inner_temp"])
    s_tsurf_key = find_key(s0, ["t_surf", "tsurf", "t_outer", "outer_temp", "t_surface"])

    if not m_time_key or not m_v_key:
        raise SystemExit("Measured CSV missing required columns (Time, Voltage)")
    if not s_time_key or not s_v_key:
        raise SystemExit("Simulation CSV missing required columns (time, voltage)")

    sim_times = []
    sim_v = []
    sim_tcore = []
    sim_tsurf = []
    for row in sim_rows:
        t = to_float(row.get(s_time_key))
        v = to_float(row.get(s_v_key))
        if t is None or v is None:
            continue
        sim_times.append(t)
        sim_v.append(v)
        if s_tcore_key:
            sim_tcore.append(to_float(row.get(s_tcore_key)))
        if s_tsurf_key:
            sim_tsurf.append(to_float(row.get(s_tsurf_key)))

    if not sim_times:
        raise SystemExit("No valid simulation time/voltage rows")

    v_err = []
    tcore_err = []
    tsurf_err = []

    for row in measured_rows:
        t = to_float(row.get(m_time_key))
        mv = to_float(row.get(m_v_key))
        if t is None or mv is None:
            continue
        sv = interpolate(t, sim_times, sim_v)
        if sv is not None:
            v_err.append(sv - mv)
        if m_tcore_key and s_tcore_key:
            mtc = to_float(row.get(m_tcore_key))
            if mtc is not None and len(sim_tcore) == len(sim_times):
                stc = interpolate(t, sim_times, sim_tcore)
                if stc is not None:
                    tcore_err.append(stc - mtc)
        if m_tsurf_key and s_tsurf_key:
            mts = to_float(row.get(m_tsurf_key))
            if mts is not None and len(sim_tsurf) == len(sim_times):
                sts = interpolate(t, sim_times, sim_tsurf)
                if sts is not None:
                    tsurf_err.append(sts - mts)

    metrics = {
        "rmse_voltage": rmse(v_err),
        "max_abs_voltage": max((abs(v) for v in v_err), default=None),
        "rmse_tcore": rmse(tcore_err) if tcore_err else None,
        "max_abs_tcore": max((abs(v) for v in tcore_err), default=None),
        "rmse_tsurf": rmse(tsurf_err) if tsurf_err else None,
        "max_abs_tsurf": max((abs(v) for v in tsurf_err), default=None),
        "n_samples": len(v_err),
    }

    for k, v in metrics.items():
        print(f"{k}: {v}")

    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            for k, v in metrics.items():
                w.writerow([k, v])


if __name__ == "__main__":
    main()
