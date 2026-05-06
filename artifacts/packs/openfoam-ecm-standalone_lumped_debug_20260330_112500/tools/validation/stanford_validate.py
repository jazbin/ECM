#!/usr/bin/env python3
import argparse
import csv
import math
import re
import xml.etree.ElementTree as ET
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


def col_to_index(col):
    idx = 0
    for ch in col:
        if "A" <= ch <= "Z":
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_shared_strings(zf):
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    strings = []
    for si in root.findall(".//{*}si"):
        t = si.find(".//{*}t")
        strings.append(t.text if t is not None else "")
    return strings


def iter_sheet_rows(zf, shared_strings, sheet_path="xl/worksheets/sheet1.xml"):
    with zf.open(sheet_path) as f:
        context = ET.iterparse(f, events=("start", "end"))
        row_cells = None
        for event, elem in context:
            tag = elem.tag
            if event == "start" and tag.endswith("row"):
                row_cells = {}
            elif event == "end" and tag.endswith("c"):
                if row_cells is None:
                    continue
                ref = elem.attrib.get("r", "")
                match = re.match(r"[A-Z]+", ref)
                if not match:
                    elem.clear()
                    continue
                col = match.group(0)
                idx = col_to_index(col)
                v = elem.find("{*}v")
                if v is None or v.text is None:
                    elem.clear()
                    continue
                val = v.text
                if elem.attrib.get("t") == "s":
                    try:
                        val = shared_strings[int(val)]
                    except (ValueError, IndexError):
                        val = None
                row_cells[idx] = val
                elem.clear()
            elif event == "end" and tag.endswith("row"):
                if row_cells:
                    max_idx = max(row_cells) + 1
                    row = [None] * max_idx
                    for idx, val in row_cells.items():
                        row[idx] = val
                    yield row
                row_cells = None
                elem.clear()


def find_key(row, candidates):
    for key in row.keys():
        if normalize_key(key) in {normalize_key(c) for c in candidates}:
            return key
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Validate Stanford/Mendeley 2021 dataset against simulation outputs."
    )
    parser.add_argument("--xlsx", required=True, help="Path to Stanford dataset XLSX")
    parser.add_argument("--sim", required=True, help="Simulation CSV with time/voltage/temperature columns")
    parser.add_argument("--out", help="Optional output metrics CSV")
    args = parser.parse_args()

    with zipfile.ZipFile(args.xlsx, "r") as zf:
        shared_strings = read_shared_strings(zf)
        rows_iter = iter_sheet_rows(zf, shared_strings)
        try:
            header = next(rows_iter)
        except StopIteration:
            raise SystemExit("No measured rows found")

        time_idx = find_index(
            header,
            ["test_time(s)", "test time(s)", "test time", "testtime", "time"],
        )
        volt_idx = find_index(header, ["voltage(v)", "voltage", "v"])
        tsurf_idx = find_index(
            header,
            ["surface_temp(degc)", "surface temp(degc)", "surface_temp", "surface temp"],
        )
        if time_idx is None or volt_idx is None:
            raise SystemExit("Measured XLSX missing required columns (Test_Time(s), Voltage(V))")

        measured_times = []
        measured_v = []
        measured_tsurf = []
        for row in rows_iter:
            if time_idx >= len(row) or volt_idx >= len(row):
                continue
            t = to_float(row[time_idx])
            v = to_float(row[volt_idx])
            if t is None or v is None:
                continue
            measured_times.append(t)
            measured_v.append(v)
            if tsurf_idx is not None and tsurf_idx < len(row):
                measured_tsurf.append(to_float(row[tsurf_idx]))

    if not measured_times:
        raise SystemExit("No valid measured time/voltage rows")

    with open(args.sim, "r", newline="") as f:
        sim_rows = list(csv.DictReader(f))
    if not sim_rows:
        raise SystemExit("No simulation rows found")

    s0 = sim_rows[0]
    s_time_key = find_key(s0, ["time", "t"])
    s_v_key = find_key(s0, ["voltage", "v"])
    s_tsurf_key = find_key(s0, ["t_surf", "tsurf", "t_outer", "surface_temp", "t_surface"])
    if not s_time_key or not s_v_key:
        raise SystemExit("Simulation CSV missing required columns (time, voltage)")

    sim_times = []
    sim_v = []
    sim_tsurf = []
    for row in sim_rows:
        t = to_float(row.get(s_time_key))
        v = to_float(row.get(s_v_key))
        if t is None or v is None:
            continue
        sim_times.append(t)
        sim_v.append(v)
        if s_tsurf_key:
            sim_tsurf.append(to_float(row.get(s_tsurf_key)))

    if not sim_times:
        raise SystemExit("No valid simulation time/voltage rows")

    v_err = []
    tsurf_err = []
    for t, mv, mts in zip(measured_times, measured_v, measured_tsurf or [None] * len(measured_times)):
        sv = interpolate(t, sim_times, sim_v)
        if sv is not None:
            v_err.append(sv - mv)
        if mts is not None and s_tsurf_key and len(sim_tsurf) == len(sim_times):
            sts = interpolate(t, sim_times, sim_tsurf)
            if sts is not None:
                tsurf_err.append(sts - mts)

    metrics = {
        "rmse_voltage": rmse(v_err),
        "max_abs_voltage": max((abs(v) for v in v_err), default=None),
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
