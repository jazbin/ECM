#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv
import vtk


def _cluster_sorted(values: list[float], tol: float) -> list[list[float]]:
    groups: list[list[float]] = []
    for v in sorted(float(x) for x in values):
        if not groups or abs(v - groups[-1][-1]) > tol:
            groups.append([v])
        else:
            groups[-1].append(v)
    return groups


def _read_mesh(case_dir: Path, region: str):
    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")
    reader = pv.OpenFOAMReader(str(foam_path))
    reader.set_active_time_value(reader.time_values[-1])
    data = reader.read()
    return data[region]["internalMesh"]


def _infer_cuts(mesh, assignment_df: pd.DataFrame) -> tuple[list[float], list[float]]:
    centers = np.asarray(mesh.cell_centers().points)
    r = np.sqrt(centers[:, 0] ** 2 + centers[:, 1] ** 2)
    z = centers[:, 2]

    df = assignment_df.copy()
    df["r"] = r[df["meshKey"].to_numpy(dtype=int)]
    df["z"] = z[df["meshKey"].to_numpy(dtype=int)]

    stats = []
    for ecm_id, g in df.groupby("ecmCellId"):
        stats.append(
            {
                "r_mean": float(g["r"].mean()),
                "r_max": float(g["r"].max()),
                "z_mean": float(g["z"].mean()),
                "z_max": float(g["z"].max()),
            }
        )

    r_groups = _cluster_sorted([s["r_mean"] for s in stats], tol=5e-4)
    z_groups = _cluster_sorted([s["z_mean"] for s in stats], tol=5e-3)

    r_cuts: list[float] = []
    for grp in r_groups[:-1]:
        r_cuts.append(
            float(max(s["r_max"] for s in stats if any(abs(s["r_mean"] - v) < 5e-4 for v in grp)))
        )
    r_cuts = sorted(r_cuts)

    z_cuts: list[float] = []
    for grp in z_groups[:-1]:
        z_cuts.append(
            float(max(s["z_max"] for s in stats if any(abs(s["z_mean"] - v) < 5e-3 for v in grp)))
        )
    z_cuts = sorted(z_cuts)

    return r_cuts, z_cuts


def _band_index(value: float, cuts: list[float]) -> int:
    for i, cut in enumerate(cuts):
        if value < cut:
            return i
    return len(cuts)


def _candidate_bands(vmin: float, vmax: float, cuts: list[float]) -> list[int]:
    ids = []
    bounds = [-np.inf, *cuts, np.inf]
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        if vmax <= lo or vmin >= hi:
            continue
        ids.append(i)
    return ids


def _sample_hex_zone_fractions(vtk_cell, *, r_cuts: list[float], z_cuts: list[float], n: int) -> dict[int, float]:
    counts: dict[int, int] = {}
    total = n * n * n
    weights = [0.0] * vtk_cell.GetNumberOfPoints()
    sub_id = vtk.reference(0)

    for i in range(n):
        xi = (i + 0.5) / n
        for j in range(n):
            eta = (j + 0.5) / n
            for k in range(n):
                zeta = (k + 0.5) / n
                x = [0.0, 0.0, 0.0]
                vtk_cell.EvaluateLocation(sub_id, [xi, eta, zeta], x, weights)
                rr = float(np.hypot(x[0], x[1]))
                zz = float(x[2])
                rad = _band_index(rr, r_cuts)
                axi = _band_index(zz, z_cuts)
                ecm_id = axi * (len(r_cuts) + 1) + rad
                counts[ecm_id] = counts.get(ecm_id, 0) + 1
    return {ecm_id: c / total for ecm_id, c in counts.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate true overlap-weighted mapping table for distributed ECM sections")
    ap.add_argument("--case", required=True)
    ap.add_argument("--region", default="jellyRoll")
    ap.add_argument("--assignment-mapping", required=True, help="Existing assignment-style mapping used to infer cuts")
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-summary", required=True)
    ap.add_argument("--samples-per-axis", type=int, default=4)
    args = ap.parse_args()

    case_dir = Path(args.case).resolve()
    mesh = _read_mesh(case_dir, args.region)
    assignment_df = pd.read_csv(args.assignment_mapping)
    r_cuts, z_cuts = _infer_cuts(mesh, assignment_df)
    n_rad = len(r_cuts) + 1

    mesh_with_vol = mesh.compute_cell_sizes(length=False, area=False, volume=True)
    cell_vol = np.asarray(mesh_with_vol.cell_data["Volume"]).reshape(-1)

    rows: list[tuple[int, int, float]] = []
    sampled_cells = 0
    multi_map_cells = 0

    for cell_id in range(mesh.n_cells):
        cell = mesh.get_cell(cell_id)
        pts = np.asarray(cell.points)
        rr = np.sqrt(pts[:, 0] ** 2 + pts[:, 1] ** 2)
        zz = pts[:, 2]

        rad_cands = _candidate_bands(float(rr.min()), float(rr.max()), r_cuts)
        axi_cands = _candidate_bands(float(zz.min()), float(zz.max()), z_cuts)

        if len(rad_cands) == 1 and len(axi_cands) == 1:
            ecm_id = axi_cands[0] * n_rad + rad_cands[0]
            rows.append((cell_id, ecm_id, float(cell_vol[cell_id])))
            continue

        sampled_cells += 1
        vtk_cell = cell.cast_to_unstructured_grid().GetCell(0)
        frac = _sample_hex_zone_fractions(
            vtk_cell,
            r_cuts=r_cuts,
            z_cuts=z_cuts,
            n=args.samples_per_axis,
        )
        if len(frac) > 1:
            multi_map_cells += 1
        for ecm_id, f in frac.items():
            w = float(cell_vol[cell_id]) * float(f)
            if w > 0.0:
                rows.append((cell_id, int(ecm_id), w))

        if (cell_id + 1) % 5000 == 0:
            print(f"[mapping] processed {cell_id + 1}/{mesh.n_cells} cells")

    out_df = pd.DataFrame(rows, columns=["meshKey", "ecmCellId", "weight"])
    out_df.sort_values(["meshKey", "ecmCellId"], inplace=True)
    out_df.to_csv(args.out_csv, index=False)

    part_vol = out_df.groupby("ecmCellId")["weight"].sum().sort_index()
    dup = out_df.groupby("meshKey").size()
    with Path(args.out_summary).open("w") as f:
        bounds = mesh.bounds
        f.write(f"z_min {bounds[4]}\n")
        f.write(f"z_max {bounds[5]}\n")
        f.write("z_cuts " + " ".join(str(v) for v in z_cuts) + "\n")
        f.write("r_cuts " + " ".join(str(v) for v in r_cuts) + "\n")
        f.write(f"mesh_cells {mesh.n_cells}\n")
        f.write(f"rows {len(out_df)}\n")
        f.write(f"sampled_cells {sampled_cells}\n")
        f.write(f"multi_map_cells {multi_map_cells}\n")
        f.write(f"max_rows_per_meshKey {int(dup.max())}\n")
        f.write("section_volume_weights\n")
        for ecm_id, vol in part_vol.items():
            f.write(f"  ecm{int(ecm_id)} {vol:.16e}\n")

    print(args.out_csv)
    print(args.out_summary)
    print(f"sampled_cells={sampled_cells} multi_map_cells={multi_map_cells} max_rows_per_meshKey={int(dup.max())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
