#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Circle
import numpy as np
import pandas as pd
import pyvista as pv


_AXES = {
    "x": (1, 2, 0, "Y [m]", "Z [m]"),
    "y": (0, 2, 1, "X [m]", "Z [m]"),
    "z": (0, 1, 2, "X [m]", "Y [m]"),
}

def _poly_faces(poly: pv.PolyData) -> list[np.ndarray]:
    """Return a list of point-index arrays for each polygonal face."""
    faces = np.asarray(poly.faces, dtype=np.int64)
    out: list[np.ndarray] = []
    i = 0
    while i < len(faces):
        n = int(faces[i])
        if n <= 0:
            break
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


def _partition_overlay_geometry(case_dir: Path, region: str, mapping_file: Path) -> dict:
    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")
    reader = pv.OpenFOAMReader(str(foam_path))
    reader.set_active_time_value(reader.time_values[-1])
    mesh = reader.read()[region]["internalMesh"]
    centers = np.asarray(mesh.cell_centers().points)
    r = np.sqrt(centers[:, 0] ** 2 + centers[:, 1] ** 2)
    z = centers[:, 2]

    df = pd.read_csv(mapping_file)
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
                "z_min": float(g["z"].min()),
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

    bounds = mesh.bounds
    return {
        "center": mesh.center,
        "mesh_bounds": bounds,
        "r_outer": float(max(r)),
        "radial_bounds": radial_bounds,
        "axial_bounds": axial_bounds,
    }


def _draw_overlay(ax, *, normal: str, overlay: dict, line_kw: dict) -> None:
    cx, cy, cz = overlay["center"]
    radial_bounds = overlay["radial_bounds"]
    axial_bounds = overlay["axial_bounds"]
    mesh_bounds = overlay["mesh_bounds"]

    if normal == "z":
        for rr in radial_bounds:
            ax.add_patch(Circle((cx, cy), rr, fill=False, **line_kw))
        return

    if normal == "x":
        ymin, ymax = mesh_bounds[2], mesh_bounds[3]
        zmin, zmax = mesh_bounds[4], mesh_bounds[5]
        for rr in radial_bounds:
            ax.plot([-rr, -rr], [zmin, zmax], **line_kw)
            ax.plot([rr, rr], [zmin, zmax], **line_kw)
        for zz in axial_bounds:
            ax.plot([ymin, ymax], [zz, zz], **line_kw)
        return

    if normal == "y":
        xmin, xmax = mesh_bounds[0], mesh_bounds[1]
        zmin, zmax = mesh_bounds[4], mesh_bounds[5]
        for rr in radial_bounds:
            ax.plot([-rr, -rr], [zmin, zmax], **line_kw)
            ax.plot([rr, rr], [zmin, zmax], **line_kw)
        for zz in axial_bounds:
            ax.plot([xmin, xmax], [zz, zz], **line_kw)
        return


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


def _render_slice(
    mesh,
    *,
    field: str,
    normal: str,
    origin: tuple[float, float, float],
    out_path: Path,
    title: str,
    overlay: dict | None = None,
) -> None:
    axis0, axis1, _slice_axis, xlabel, ylabel = _AXES[normal]
    sl = mesh.slice(normal=normal, origin=origin)
    if sl.n_points == 0:
        raise RuntimeError(f"empty slice for {normal=} at {origin}")
    if field not in sl.cell_data and field in sl.point_data:
        sl = sl.point_data_to_cell_data()
    if field not in sl.cell_data:
        raise RuntimeError(f"field {field!r} not found in slice cell data")

    pts = np.asarray(sl.points)
    polys = _poly_faces(sl)
    if not polys:
        raise RuntimeError(f"slice produced no polygon faces for {normal=} at {origin}")

    patches = [pts[idx][:, [axis0, axis1]] for idx in polys]
    vals = np.asarray(sl.cell_data[field]).reshape(-1)
    if len(vals) != len(patches):
        raise RuntimeError(
            f"cell-data length mismatch for {field}: {len(vals)} values vs {len(patches)} patches"
        )

    fig, ax = plt.subplots(figsize=(5.2, 4.6), dpi=160)
    cmap = "tab20" if field == "ecmPartitionId" else "inferno"
    coll = PolyCollection(
        patches,
        array=vals,
        cmap=cmap,
        edgecolors="none",
        linewidths=0.0,
    )
    ax.add_collection(coll)
    x_all = pts[:, axis0]
    y_all = pts[:, axis1]
    ax.set_xlim(float(np.min(x_all)), float(np.max(x_all)))
    ax.set_ylim(float(np.min(y_all)), float(np.max(y_all)))
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=9)
    ax.grid(True, alpha=0.18)
    cb = fig.colorbar(coll, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(field, fontsize=8)
    cb.ax.tick_params(labelsize=7)
    if overlay is not None:
        _draw_overlay(
            ax,
            normal=normal,
            overlay=overlay,
            line_kw={"color": "#6FE7FF", "lw": 0.95, "alpha": 0.95, "ls": "--"},
        )
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="Headless OpenFOAM slice renderer using PyVista read + matplotlib plot")
    ap.add_argument("--case", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--field", default="T")
    ap.add_argument("--time", type=float, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--normal", choices=("x", "y", "z"), default="z")
    ap.add_argument("--slice-count", type=int, default=3)
    ap.add_argument("--mapping-file")
    args = ap.parse_args()

    case_dir = Path(args.case).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay = None
    if args.mapping_file:
        overlay = _partition_overlay_geometry(case_dir, args.region, Path(args.mapping_file))

    mesh, actual_time = _read_mesh(case_dir, args.region, args.time)
    if args.field == "ecmPartitionId":
        if not args.mapping_file:
            raise RuntimeError("ecmPartitionId rendering requires --mapping-file")
        df = pd.read_csv(args.mapping_file)
        part = np.full(mesh.n_cells, -1.0, dtype=float)
        part[df["meshKey"].to_numpy(dtype=int)] = df["ecmCellId"].to_numpy(dtype=float)
        mesh = mesh.copy()
        mesh.cell_data["ecmPartitionId"] = part
    bounds = mesh.bounds
    slice_axis = _AXES[args.normal][2]
    axis_min = bounds[2 * slice_axis]
    axis_max = bounds[2 * slice_axis + 1]
    center = mesh.center

    for i in range(args.slice_count):
        frac = (i + 1) / (args.slice_count + 1)
        pos = axis_min + frac * (axis_max - axis_min)
        origin = [center[0], center[1], center[2]]
        origin[slice_axis] = pos
        out_path = out_dir / f"{args.prefix}_{args.field}_slice_{args.normal}{i+1}.png"
        pos_mm = pos * 1e3
        title = f"{args.region} {args.field} | {args.normal}={pos_mm:.2f} mm | t={actual_time:.6f} s"
        _render_slice(
            mesh,
            field=args.field,
            normal=args.normal,
            origin=tuple(origin),
            out_path=out_path,
            title=title,
            overlay=overlay,
        )
        print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
