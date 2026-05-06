#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np
import pandas as pd
import pyvista as pv


AXES = {
    "x": (1, 2, 0, "Y [m]", "Z [m]"),
    "y": (0, 2, 1, "X [m]", "Z [m]"),
    "z": (0, 1, 2, "X [m]", "Y [m]"),
}


def _nearest_time(reader: pv.OpenFOAMReader, requested: float) -> float:
    return min(reader.time_values, key=lambda t: abs(float(t) - requested))


def _read_mesh(case_dir: Path, region: str, time_value: float):
    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")
    reader = pv.OpenFOAMReader(str(foam_path))
    actual_time = _nearest_time(reader, time_value)
    reader.set_active_time_value(actual_time)
    data = reader.read()
    mesh = data[region]["internalMesh"]
    return mesh, actual_time


def _poly_faces(poly: pv.PolyData) -> list[np.ndarray]:
    faces = np.asarray(poly.faces, dtype=np.int64)
    out: list[np.ndarray] = []
    i = 0
    while i < len(faces):
        n = int(faces[i])
        out.append(faces[i + 1 : i + 1 + n])
        i += n + 1
    return out


def _cluster_sorted(values: list[float], tol: float) -> list[list[float]]:
    groups: list[list[float]] = []
    for v in sorted(float(x) for x in values):
        if not groups or abs(v - groups[-1][-1]) > tol:
            groups.append([v])
        else:
            groups[-1].append(v)
    return groups


def _infer_partition_geometry(mesh, mapping_df: pd.DataFrame) -> dict:
    centers = np.asarray(mesh.cell_centers().points)
    r = np.sqrt(centers[:, 0] ** 2 + centers[:, 1] ** 2)
    z = centers[:, 2]

    df = mapping_df.copy()
    df["r"] = r[df["meshKey"].to_numpy(dtype=int)]
    df["z"] = z[df["meshKey"].to_numpy(dtype=int)]

    stats = []
    for ecm_id, g in df.groupby("ecmCellId"):
        stats.append(
            {
                "ecm_id": int(ecm_id),
                "r_mean": float(g["r"].mean()),
                "r_max": float(g["r"].max()),
                "z_mean": float(g["z"].mean()),
                "z_max": float(g["z"].max()),
            }
        )

    r_groups = _cluster_sorted([s["r_mean"] for s in stats], tol=5e-4)
    z_groups = _cluster_sorted([s["z_mean"] for s in stats], tol=5e-3)

    radial_bounds: list[float] = []
    for grp in r_groups[:-1]:
        grp_max = max(s["r_max"] for s in stats if any(abs(s["r_mean"] - v) < 5e-4 for v in grp))
        radial_bounds.append(float(grp_max))

    axial_bounds: list[float] = []
    for grp in z_groups[:-1]:
        grp_max = max(s["z_max"] for s in stats if any(abs(s["z_mean"] - v) < 5e-3 for v in grp))
        axial_bounds.append(float(grp_max))

    return {
        "center": mesh.center,
        "bounds": mesh.bounds,
        "radial_bounds": radial_bounds,
        "axial_bounds": axial_bounds,
    }


def _build_zone_field(mesh, mapping_df: pd.DataFrame, field_name: str = "ecmQdot") -> np.ndarray:
    mesh_vals = np.asarray(mesh.cell_data[field_name]).reshape(-1)
    part_groups = mapping_df.groupby("ecmCellId")
    zone_val = {}
    for ecm_id, g in part_groups:
        idx = g["meshKey"].to_numpy(dtype=int)
        w = g["weight"].to_numpy(dtype=float)
        zone_val[int(ecm_id)] = float(np.sum(mesh_vals[idx] * w) / np.sum(w))

    row_idx = mapping_df.groupby("meshKey")["weight"].idxmax().to_numpy(dtype=int)
    owner = mapping_df.loc[row_idx, ["meshKey", "ecmCellId"]].sort_values("meshKey")
    out = np.zeros(mesh.n_cells, dtype=float)
    out[owner["meshKey"].to_numpy(dtype=int)] = owner["ecmCellId"].map(zone_val).to_numpy(dtype=float)
    return out


def _render_slice(mesh, field: str, normal: str, origin: tuple[float, float, float], out_path: Path, title: str) -> None:
    axis0, axis1, _, xlabel, ylabel = AXES[normal]
    sl = mesh.slice(normal=normal, origin=origin)
    if field not in sl.cell_data and field in sl.point_data:
        sl = sl.point_data_to_cell_data()
    pts = np.asarray(sl.points)
    polys = _poly_faces(sl)
    patches = [pts[idx][:, [axis0, axis1]] for idx in polys]
    vals = np.asarray(sl.cell_data[field]).reshape(-1)

    fig, ax = plt.subplots(figsize=(5.4, 4.8), dpi=180)
    coll = PolyCollection(patches, array=vals, cmap="inferno", edgecolors="none", linewidths=0.0)
    ax.add_collection(coll)
    ax.set_xlim(float(np.min(pts[:, axis0])), float(np.max(pts[:, axis0])))
    ax.set_ylim(float(np.min(pts[:, axis1])), float(np.max(pts[:, axis1])))
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.18)
    cb = fig.colorbar(coll, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(field)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _render_zone_slice(mesh, zone_field: np.ndarray, normal: str, origin: tuple[float, float, float], out_path: Path, title: str) -> None:
    mesh2 = mesh.copy()
    mesh2.cell_data["ecmZoneQdot"] = zone_field
    _render_slice(mesh2, "ecmZoneQdot", normal, origin, out_path, title)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate ECM-zone and CFD-cell source maps for a distributed case")
    ap.add_argument("--case", required=True)
    ap.add_argument("--region", default="jellyRoll")
    ap.add_argument("--time", type=float, required=True)
    ap.add_argument("--mapping-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--normal", choices=("x", "y", "z"), default="x")
    ap.add_argument("--prefix", default="distributed_source")
    args = ap.parse_args()

    case_dir = Path(args.case).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mesh, actual_time = _read_mesh(case_dir, args.region, args.time)
    mapping_df = pd.read_csv(args.mapping_file)
    geom = _infer_partition_geometry(mesh, mapping_df)
    center = list(mesh.center)

    slice_axis = AXES[args.normal][2]
    origin = center.copy()
    origin[slice_axis] = center[slice_axis]

    zone_field = _build_zone_field(mesh, mapping_df, "ecmQdot")

    out_zone = out_dir / f"{args.prefix}_ecm_zone_qdot_{args.normal}.png"
    out_cfd = out_dir / f"{args.prefix}_cfd_cell_qdot_{args.normal}.png"
    _render_zone_slice(
        mesh,
        zone_field,
        args.normal,
        tuple(origin),
        out_zone,
        f"{args.region} ECM-zone qVol | {args.normal}=0 center slice | t={actual_time:.6f} s",
    )
    _render_slice(
        mesh,
        "ecmQdot",
        args.normal,
        tuple(origin),
        out_cfd,
        f"{args.region} CFD-cell ecmQdot | {args.normal}=0 center slice | t={actual_time:.6f} s",
    )
    print(out_zone)
    print(out_cfd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
