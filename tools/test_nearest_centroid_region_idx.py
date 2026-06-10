#!/usr/bin/env python3
"""
Standalone test of the nearest-centroid regionIdx algorithm from EcmCouplerMacro.java.

Replicates computeRegionIndicesNearestCentroid() in pure Python (no STAR required).
Tests:
  1. Synthetic interleaved data  — core bug scenario (FvRep-block vs spatial)
  2. Diagnostic on real distributed ecm_cell_map.csv — confirms stale single-cell data
  3. Synthetic two-cell realistic geometry — k-means and CSV-origin must agree
  4. CSV-origin takes precedence over k-means

Usage:
  python3 tools/test_nearest_centroid_region_idx.py
"""

import csv
import math
import os
import sys
import tempfile

PASS = 0
FAIL = 0

def check(label, cond):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        FAIL += 1


# ---------------------------------------------------------------------------
# Core algorithm — direct translation of Java computeRegionIndicesNearestCentroid
# ---------------------------------------------------------------------------

def nearest_centroid(k, xs, ys, zs, geom_csv=None, log_prefix="[SPATIAL]"):
    """
    Returns (ri, centers) or (None, None) on failure.
    ri[i]  = region index for cell i (0-based)
    centers[r] = (x, y, z) centroid used for region r
    """
    n = len(xs)
    centers = [None] * k
    centers_loaded = False

    # --- (a) Try ecm_region_geometry.csv ---
    if geom_csv and os.path.exists(geom_csv):
        try:
            seen = [False] * k
            with open(geom_csv) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r = int(row["regionIdx"])
                    if 0 <= r < k:
                        centers[r] = (float(row["origin_x"]),
                                      float(row["origin_y"]),
                                      float(row["origin_z"]))
                        seen[r] = True
            if all(seen):
                centers_loaded = True
                print(f"{log_prefix} Loaded centroids from {os.path.basename(geom_csv)}:")
                for r in range(k):
                    c = centers[r]
                    print(f"{log_prefix}   r{r} = ({c[0]:.6f}, {c[1]:.6f}, {c[2]:.6f})")
            else:
                missing = [r for r, s in enumerate(seen) if not s]
                print(f"{log_prefix} geom CSV missing regions {missing} — k-means fallback")
        except Exception as e:
            print(f"{log_prefix} Could not read geom CSV: {e} — k-means fallback")

    # --- (b) k-means ---
    if not centers_loaded:
        print(f"{log_prefix} Running k-means (k={k}) on {n} cells")
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        z_range = max(zs) - min(zs)
        max_range = max(x_range, y_range, z_range)
        if max_range < 1e-6:
            print(f"{log_prefix} ERROR: centroid spread < 1 µm")
            return None, None

        axis = xs if x_range >= y_range and x_range >= z_range else (ys if y_range >= z_range else zs)
        sort_idx = sorted(range(n), key=lambda i: axis[i])
        for r in range(k):
            si = sort_idx[r * (n - 1) // (k - 1)]
            centers[r] = (xs[si], ys[si], zs[si])

        ri = [0] * n
        for iteration in range(50):
            changed = False
            for i in range(n):
                min_d2, best = float("inf"), 0
                for r in range(k):
                    dx = xs[i] - centers[r][0]
                    dy = ys[i] - centers[r][1]
                    dz = zs[i] - centers[r][2]
                    d2 = dx*dx + dy*dy + dz*dz
                    if d2 < min_d2:
                        min_d2, best = d2, r
                if ri[i] != best:
                    ri[i] = best
                    changed = True
            if not changed and iteration > 0:
                print(f"{log_prefix} k-means converged at iteration {iteration}")
                break
            new_c = [[0.0, 0.0, 0.0] for _ in range(k)]
            cnt = [0] * k
            for i in range(n):
                new_c[ri[i]][0] += xs[i]; new_c[ri[i]][1] += ys[i]; new_c[ri[i]][2] += zs[i]
                cnt[ri[i]] += 1
            for r in range(k):
                if cnt[r] > 0:
                    centers[r] = (new_c[r][0]/cnt[r], new_c[r][1]/cnt[r], new_c[r][2]/cnt[r])

        counts = [ri.count(r) for r in range(k)]
        if any(c == 0 for c in counts):
            print(f"{log_prefix} ERROR: empty cluster — data may not contain {k} distinct regions")
            return None, None
        for r in range(k):
            c = centers[r]
            print(f"{log_prefix} k-means r{r}: {counts[r]} cells, "
                  f"center=({c[0]:.6f},{c[1]:.6f},{c[2]:.6f})")
        return ri, centers

    # --- nearest-centroid from CSV origins ---
    ri = [0] * n
    for i in range(n):
        min_d2, best = float("inf"), 0
        for r in range(k):
            dx = xs[i] - centers[r][0]; dy = ys[i] - centers[r][1]; dz = zs[i] - centers[r][2]
            d2 = dx*dx + dy*dy + dz*dz
            if d2 < min_d2:
                min_d2, best = d2, r
        ri[i] = best

    counts = [ri.count(r) for r in range(k)]
    for r in range(k):
        print(f"{log_prefix} nearest-centroid r{r}: {counts[r]} cells")
    return ri, centers


def make_cylinder_cells(n, cx, cy, cz, radius, length, axis="x", seed=42):
    """Generate n cell centroids for a cylinder of given geometry."""
    cells = []
    s = seed
    def lcg(s): return (1664525 * s + 1013904223) & 0xFFFFFFFF
    for _ in range(n):
        s = lcg(s); r  = (s & 0xFFFF) / 0xFFFF * radius
        s = lcg(s); th = (s & 0xFFFF) / 0xFFFF * 2 * math.pi
        s = lcg(s); ax = ((s & 0xFFFF) / 0xFFFF - 0.5) * length
        if axis == "x":
            cells.append((cx + ax, cy + r*math.sin(th), cz + r*math.cos(th)))
        elif axis == "y":
            cells.append((cx + r*math.cos(th), cy + ax, cz + r*math.sin(th)))
    return cells


# ---------------------------------------------------------------------------
# TEST 1: Synthetic interleaved — core bug scenario
# ---------------------------------------------------------------------------
def test_synthetic_interleaved():
    print("\n=== TEST 1: synthetic interleaved (FvRep-block bug reproduction) ===")
    # Two jellyRolls along X axis, separated by 50 mm in Y
    cells_r0 = make_cylinder_cells(500, cx=0.032, cy=0.000, cz=0.000,
                                   radius=0.011, length=0.065, seed=1)
    cells_r1 = make_cylinder_cells(500, cx=0.031, cy=0.050, cz=0.000,
                                   radius=0.011, length=0.065, seed=2)

    # STAR interleaves them — alternate rows from each region in T-table
    interleaved = []
    for i in range(500):
        interleaved.append((cells_r0[i], 0))
        interleaved.append((cells_r1[i], 1))

    xs = [c[0][0] for c in interleaved]
    ys = [c[0][1] for c in interleaved]
    zs = [c[0][2] for c in interleaved]
    true_ri = [c[1] for c in interleaved]
    n = len(xs)

    # FvRep-block (broken): first half → r0, second half → r1
    fvrep_ri = [0] * (n//2) + [1] * (n//2)
    fvrep_errors = sum(a != b for a, b in zip(fvrep_ri, true_ri))
    print(f"  FvRep-block errors: {fvrep_errors}/{n} ({100*fvrep_errors/n:.1f}%)")

    ri, _ = nearest_centroid(2, xs, ys, zs, log_prefix="  [kmeans]")
    # Allow label flip
    errors = min(sum(a != b for a, b in zip(ri, true_ri)),
                 sum((1-a) != b for a, b in zip(ri, true_ri)))
    print(f"  Spatial errors: {errors}/{n} ({100*errors/n:.1f}%)")

    check("FvRep-block produces ~50% errors on interleaved data",  fvrep_errors > n//4)
    check("Spatial assignment: 0 errors on interleaved data",       errors == 0)


# ---------------------------------------------------------------------------
# TEST 2: Diagnostic on real distributed ecm_cell_map.csv
# ---------------------------------------------------------------------------
def test_real_data_diagnostic():
    print("\n=== TEST 2: real distributed ecm_cell_map.csv diagnostic ===")
    cell_map = ("/workspace/in/starCCM_10C_experiment_twoCells_distributed"
                "/ecm/ecm_cell_map.csv")
    geom_csv = ("/workspace/in/starCCM_10C_experiment_twoCells_distributed"
                "/ecm/ecm_region_geometry.csv")

    xs, ys, zs, old_ri = [], [], [], []
    with open(cell_map) as f:
        for row in csv.DictReader(f):
            xs.append(float(row["x_m"]))
            ys.append(float(row["y_m"]))
            zs.append(float(row["z_m"]))
            old_ri.append(int(row["regionIdx"]))
    n = len(xs)

    old_counts = [old_ri.count(r) for r in range(2)]
    y_range = max(ys) - min(ys)
    cells_far = sum(1 for y in ys if abs(y) > 0.020)

    print(f"  Total cells: {n}")
    print(f"  Old regionIdx: r0={old_counts[0]}, r1={old_counts[1]}  "
          f"(all-zeros confirms FvRep-block bug)")
    print(f"  Y range: {min(ys)*1000:.1f}mm .. {max(ys)*1000:.1f}mm  "
          f"(range = {y_range*1000:.1f} mm)")
    print(f"  Cells with |y| > 20 mm: {cells_far}  "
          f"(0 → second jellyRoll absent — CSV is stale single-cell data)")

    # Confirm the CSV is single-cell stale data
    check("Old regionIdx all-zeros (FvRep-block bug)",    old_counts[1] == 0)
    check("No cells from second jellyRoll (stale CSV)",   cells_far == 0)
    check("Y range < 25 mm (single cylinder only)",       y_range < 0.025)

    print("  NOTE: ecm_cell_map.csv must be regenerated from a fresh two-cell STAR run.")
    print("        The new spatial code will produce correct regionIdx automatically.")


# ---------------------------------------------------------------------------
# TEST 3: Synthetic two-cell geometry — k-means and CSV-origin must agree
# ---------------------------------------------------------------------------
def test_synthetic_two_cell_agreement():
    print("\n=== TEST 3: synthetic two-cell geometry (k-means vs CSV-origin agreement) ===")
    # Geometry matching the real distributed sim:
    #   JellyRoll_1: x-axis cylinder, centre (0.032, 0.000, 0.000), r=11mm, L=65mm
    #   JellyRoll_2: x-axis cylinder, centre (0.031, 0.050, 0.000), r=11mm, L=65mm
    N = 2000  # cells per region — large enough for k-means to be stable
    cells_r0 = make_cylinder_cells(N, 0.032, 0.000, 0.000, 0.011, 0.065, seed=10)
    cells_r1 = make_cylinder_cells(N, 0.031, 0.050, 0.000, 0.011, 0.065, seed=20)

    # Interleave (worst case for FvRep-block)
    cells_all = []
    true_ri = []
    for i in range(N):
        cells_all.append(cells_r0[i]); true_ri.append(0)
        cells_all.append(cells_r1[i]); true_ri.append(1)

    xs = [c[0] for c in cells_all]
    ys = [c[1] for c in cells_all]
    zs = [c[2] for c in cells_all]
    n = len(xs)

    # Write a matching geom CSV
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("regionIdx,origin_x,origin_y,origin_z,axis_x,axis_y,axis_z\n")
        f.write("0,0.032,0.000,0.000,1,0,0\n")
        f.write("1,0.031,0.050,0.000,1,0,0\n")
        geom_path = f.name

    try:
        print("  -- k-means (no CSV) --")
        ri_k, centers_k = nearest_centroid(2, xs, ys, zs, log_prefix="  [kmeans]")
        print("  -- CSV-origin --")
        ri_c, centers_c = nearest_centroid(2, xs, ys, zs, geom_csv=geom_path, log_prefix="  [csv]")

        # Both must succeed
        check("k-means returned result",   ri_k is not None)
        check("CSV-origin returned result", ri_c is not None)

        # Compute errors vs ground truth (allow label flip)
        err_k = min(sum(a != b for a, b in zip(ri_k, true_ri)),
                    sum((1-a) != b for a, b in zip(ri_k, true_ri)))
        err_c = min(sum(a != b for a, b in zip(ri_c, true_ri)),
                    sum((1-a) != b for a, b in zip(ri_c, true_ri)))
        print(f"  k-means errors vs ground truth:   {err_k}/{n} ({100*err_k/n:.2f}%)")
        print(f"  CSV-origin errors vs ground truth: {err_c}/{n} ({100*err_c/n:.2f}%)")

        check("k-means 0 errors vs ground truth",   err_k == 0)
        check("CSV-origin 0 errors vs ground truth", err_c == 0)

        # Both methods must agree with each other
        disagree = min(sum(a != b for a, b in zip(ri_k, ri_c)),
                       sum((1-a) != b for a, b in zip(ri_k, ri_c)))
        print(f"  k-means vs CSV-origin disagreement: {disagree}/{n}")
        check("k-means and CSV-origin agree on same assignment", disagree == 0)

        # Spatial separation: check Y gap between assigned regions
        ys_r0 = [ys[i] for i, r in enumerate(ri_c) if r == 0]
        ys_r1 = [ys[i] for i, r in enumerate(ri_c) if r == 1]
        if max(ys_r0) > min(ys_r1):
            ys_r0, ys_r1 = ys_r1, ys_r0  # label flip OK
        gap = min(ys_r1) - max(ys_r0)
        print(f"  Y-gap between assigned regions: {gap*1000:.1f} mm")
        check("Regions spatially separated — Y-gap > 10 mm", gap > 0.010)

    finally:
        os.unlink(geom_path)


# ---------------------------------------------------------------------------
# TEST 4: CSV-origin takes precedence when geom CSV is present
# ---------------------------------------------------------------------------
def test_csv_overrides_kmeans():
    print("\n=== TEST 4: CSV-origin takes precedence over k-means ===")
    # 200 cells: first 100 at y in [0, 0.095], second 100 at y in [0.200, 0.295]
    # (large gap ensures even offset origins cleanly separate them)
    xs = [0.0] * 200
    ys = [0.001 * i for i in range(100)] + [0.200 + 0.001 * i for i in range(100)]
    zs = [0.0] * 200
    true_ri = [0]*100 + [1]*100

    # Origins are the exact means of each group
    mean0 = sum(ys[:100]) / 100   # = 0.0495
    mean1 = sum(ys[100:]) / 100   # = 0.2495

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("regionIdx,origin_x,origin_y,origin_z,axis_x,axis_y,axis_z\n")
        f.write(f"0,0.0,{mean0:.6f},0.0,1,0,0\n")
        f.write(f"1,0.0,{mean1:.6f},0.0,1,0,0\n")
        geom_path = f.name

    try:
        ri, _ = nearest_centroid(2, xs, ys, zs, geom_csv=geom_path, log_prefix="  [csv]")
        err = min(sum(a != b for a, b in zip(ri, true_ri)),
                  sum((1-a) != b for a, b in zip(ri, true_ri)))
        print(f"  Counts: r0={ri.count(0)}, r1={ri.count(1)}")
        check("CSV-origin gives correct 100/100 split", err == 0)
    finally:
        os.unlink(geom_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_synthetic_interleaved()
    test_real_data_diagnostic()
    test_synthetic_two_cell_agreement()
    test_csv_overrides_kmeans()

    print(f"\n=== RESULTS: {PASS} passed, {FAIL} failed ===")
    if FAIL:
        sys.exit(1)
