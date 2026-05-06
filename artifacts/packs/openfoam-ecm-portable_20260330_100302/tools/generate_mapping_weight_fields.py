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
    return data[region]["internalMesh"], actual_time


def _poly_faces(poly: pv.PolyData) -> list[np.ndarray]:
    faces = np.asarray(poly.faces, dtype=np.int64)
    out: list[np.ndarray] = []
    i = 0
    while i < len(faces):
        n = int(faces[i])
        out.append(faces[i + 1 : i + 1 + n])
        i += n + 1
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
    coll = PolyCollection(patches, array=vals, cmap="viridis", edgecolors="none", linewidths=0.0)
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Plot CFD->ECM weight fields for each ECM partition")
    ap.add_argument("--case", required=True)
    ap.add_argument("--region", default="jellyRoll")
    ap.add_argument("--time", type=float, required=True)
    ap.add_argument("--mapping-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--normal", choices=("x", "y", "z"), default="x")
    ap.add_argument("--prefix", default="mapping_weight")
    args = ap.parse_args()

    case_dir = Path(args.case).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mesh, actual_time = _read_mesh(case_dir, args.region, args.time)
    mapping_df = pd.read_csv(args.mapping_file)
    center = list(mesh.center)
    slice_axis = AXES[args.normal][2]
    origin = center.copy()
    origin[slice_axis] = center[slice_axis]

    cell_weight_sum = mapping_df.groupby("meshKey")["weight"].sum()

    for ecm_id, g in mapping_df.groupby("ecmCellId"):
        field = np.zeros(mesh.n_cells, dtype=float)
        mesh_keys = g["meshKey"].to_numpy(dtype=int)
        norm = (g["weight"] / g["meshKey"].map(cell_weight_sum)).to_numpy(dtype=float)
        field[mesh_keys] = norm
        mesh2 = mesh.copy()
        name = f"weightFrac_ecm{int(ecm_id):02d}"
        mesh2.cell_data[name] = field
        out_path = out_dir / f"{args.prefix}_{name}_{args.normal}.png"
        _render_slice(
            mesh2,
            name,
            args.normal,
            tuple(origin),
            out_path,
            f"{args.region} CFD→ECM normalized contribution | ecm{int(ecm_id):02d} | {args.normal}=0 | t={actual_time:.6f} s",
        )
        print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
