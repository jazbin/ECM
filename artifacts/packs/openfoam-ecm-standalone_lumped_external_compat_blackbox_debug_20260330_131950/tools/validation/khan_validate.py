#!/usr/bin/env python3
import argparse
import csv
import io
import math
import re
import sys
import zipfile


def normalize_key(key):
    if key is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "", key.strip().lower())


def find_index(header, candidates):
    norm_candidates = {normalize_key(c) for c in candidates}
    for idx, key in enumerate(header):
        if normalize_key(key) in norm_candidates:
            return idx
    return None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def choose_delimiter(sample):
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return dialect.delimiter
    except Exception:
        comma = sample.count(",")
        semi = sample.count(";")
        if semi > comma:
            return ";"
        return ","


def load_csv_text(path=None, zip_path=None, member=None):
    if zip_path:
        if not member:
            raise ValueError("--member is required when using --zip")
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(member) as f:
                data = f.read()
        return data.decode("utf-8", errors="ignore")
    with open(path, "r", newline="") as f:
        return f.read()


def load_table(text):
    lines = text.splitlines()
    if not lines:
        return [], []
    sample = "\n".join(lines[:5])
    delimiter = choose_delimiter(sample)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return [], []
    header = rows[0]
    data = rows[1:]
    return header, data


def rmse(values):
    if not values:
        return None
    return math.sqrt(sum(v * v for v in values) / len(values))


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


def find_key(row, candidates):
    for key in row.keys():
        if normalize_key(key) in {normalize_key(c) for c in candidates}:
            return key
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Validate Khan OSF dataset (Molicell P42A) against simulation outputs."
    )
    parser.add_argument("--zip", dest="zip_path", help="Path to Khan dataset ZIP")
    parser.add_argument("--member", help="CSV member path inside ZIP")
    parser.add_argument("--csv", dest="csv_path", help="Path to extracted Khan CSV")
    parser.add_argument("--sim", required=True, help="Simulation CSV with time/voltage columns")
    parser.add_argument("--out", help="Optional output metrics CSV")
    args = parser.parse_args()

    if not args.zip_path and not args.csv_path:
        parser.error("Provide --zip or --csv")
    if args.zip_path and args.csv_path:
        parser.error("Provide only one of --zip or --csv")

    text = load_csv_text(path=args.csv_path, zip_path=args.zip_path, member=args.member)
    header, data = load_table(text)
    if not header or not data:
        raise SystemExit("No measured rows found")

    time_idx = find_index(header, ["time/s", "time", "times"])
    volt_idx = find_index(header, ["ecell/v", "voltage", "voltage(v)", "v"])
    if time_idx is None or volt_idx is None:
        raise SystemExit("Measured CSV missing required columns (time/s, Ecell/V)")

    sim_rows = []
    with open(args.sim, "r", newline="") as f:
        sim_rows = list(csv.DictReader(f))
    if not sim_rows:
        raise SystemExit("No simulation rows found")

    s0 = sim_rows[0]
    s_time_key = find_key(s0, ["time", "t"])
    s_v_key = find_key(s0, ["voltage", "v", "ecell/v"])
    if not s_time_key or not s_v_key:
        raise SystemExit("Simulation CSV missing required columns (time, voltage)")

    sim_times = []
    sim_v = []
    for row in sim_rows:
        t = to_float(row.get(s_time_key))
        v = to_float(row.get(s_v_key))
        if t is None or v is None:
            continue
        sim_times.append(t)
        sim_v.append(v)

    if not sim_times:
        raise SystemExit("No valid simulation time/voltage rows")

    v_err = []
    for row in data:
        if time_idx >= len(row) or volt_idx >= len(row):
            continue
        t = to_float(row[time_idx])
        mv = to_float(row[volt_idx])
        if t is None or mv is None:
            continue
        sv = interpolate(t, sim_times, sim_v)
        if sv is not None:
            v_err.append(sv - mv)

    metrics = {
        "rmse_voltage": rmse(v_err),
        "max_abs_voltage": max((abs(v) for v in v_err), default=None),
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
