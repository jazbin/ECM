#!/usr/bin/env pvpython
"""
Render temperature (and optionally ecmQdot) slices of an OpenFOAM multi-region
case using ParaView's OpenFOAM reader + matplotlib for publication-quality output.

All requested regions are overlaid on the same axes per slice, sharing a global
colour range so temperatures are directly comparable across jellyRoll / shell / cap.

Usage (via pvpython):
    pvpython render_slices.py --case /path/to/case --time 100 --out-dir /path/to/out
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
import numpy as np

from paraview import servermanager
from paraview.simple import Delete, OpenFOAMReader, Slice
import vtk
from vtk.util.numpy_support import vtk_to_numpy


# ---------------------------------------------------------------------------
# VTK / ParaView helpers
# ---------------------------------------------------------------------------

def _open_reader(foam_path: Path, region: str, fields: list[str], time_val: float):
    reader = OpenFOAMReader(FileName=str(foam_path))
    reader.MeshRegions = [f"/{region}/internalMesh"]
    reader.CellArrays  = fields
    reader.UpdatePipeline(time_val)
    return reader


def _global_bounds(readers: list) -> tuple[float, ...]:
    xmn, xmx = float("inf"), float("-inf")
    ymn, ymx = float("inf"), float("-inf")
    zmn, zmx = float("inf"), float("-inf")
    for r in readers:
        b = r.GetDataInformation().GetBounds()
        xmn = min(xmn, b[0]); xmx = max(xmx, b[1])
        ymn = min(ymn, b[2]); ymx = max(ymx, b[3])
        zmn = min(zmn, b[4]); zmx = max(zmx, b[5])
    return xmn, xmx, ymn, ymx, zmn, zmx


# in-plane axis index pairs and labels for each slice normal
_AX_MAP = {
    "x": (1, 2, "Y (m)", "Z (m)"),
    "y": (0, 2, "X (m)", "Z (m)"),
    "z": (0, 1, "X (m)", "Y (m)"),
}


def _fetch_slice(reader, *, time_val: float, normal: str,
                 origin: list[float], field: str):
    """
    Return (xy_coords, values, edge_segments) for one plane slice.

    edge_segments: list of 2-point line segments (for mesh wireframe), in 2D coords.
    Returns (None, None, None) if slice is empty.
    """
    normals_vec = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
    i0, i1 = _AX_MAP[normal][:2]

    slc = Slice(Input=reader)
    slc.SliceType        = "Plane"
    slc.SliceType.Origin = origin
    slc.SliceType.Normal = normals_vec[normal]
    slc.UpdatePipeline(time_val)

    poly = servermanager.Fetch(slc)
    Delete(slc)

    # Unwrap multiblock
    if isinstance(poly, vtk.vtkMultiBlockDataSet):
        it = poly.NewIterator(); it.InitTraversal(); found = None
        while not it.IsDoneWithTraversal():
            blk = it.GetCurrentDataObject()
            if blk and blk.GetCellData() and blk.GetCellData().HasArray(field):
                found = blk; break
            it.GoToNextItem()
        if found is None:
            return None, None, None
        poly = found

    if poly is None or poly.GetNumberOfPoints() == 0:
        return None, None, None

    # ---- Extract mesh edges from the raw polygon data ----
    edge_segments: list[tuple] = []
    try:
        ext = vtk.vtkExtractEdges()
        ext.SetInputData(poly)
        ext.Update()
        ep = ext.GetOutput()
        if ep and ep.GetNumberOfPoints() > 0:
            pts3d = vtk_to_numpy(ep.GetPoints().GetData())
            for ci in range(ep.GetNumberOfCells()):
                cell = ep.GetCell(ci)
                if cell.GetNumberOfPoints() == 2:
                    p0 = pts3d[cell.GetPointId(0)]
                    p1 = pts3d[cell.GetPointId(1)]
                    edge_segments.append(
                        [[p0[i0], p0[i1]], [p1[i0], p1[i1]]]
                    )
    except Exception:
        pass

    # ---- Cell → point data for smooth colour fill ----
    c2p = vtk.vtkCellDataToPointData()
    c2p.SetInputData(poly); c2p.PassCellDataOn(); c2p.Update()
    poly = c2p.GetOutput()

    pts = poly.GetPoints()
    if pts is None or pts.GetNumberOfPoints() == 0:
        return None, None, None

    coords = vtk_to_numpy(pts.GetData())
    arr    = poly.GetPointData().GetArray(field)
    if arr is None:
        return None, None, None
    values = vtk_to_numpy(arr)
    if values.ndim > 1:
        values = values[:, 0]

    return coords[:, [i0, i1]], values, edge_segments


# ---------------------------------------------------------------------------
# Matplotlib rendering
# ---------------------------------------------------------------------------

def _triplot(ax, xy: np.ndarray, values: np.ndarray, *, norm, cmap: str):
    """Filled tricontour (no iso-lines) for one region patch; returns mappable."""
    from matplotlib.tri import Triangulation
    try:
        tri = Triangulation(xy[:, 0], xy[:, 1])
        x0 = xy[tri.triangles[:, 0], 0]; x1 = xy[tri.triangles[:, 1], 0]; x2 = xy[tri.triangles[:, 2], 0]
        y0 = xy[tri.triangles[:, 0], 1]; y1 = xy[tri.triangles[:, 1], 1]; y2 = xy[tri.triangles[:, 2], 1]
        med = np.median(np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2))
        if med > 0:
            mask = (
                (np.sqrt((x1-x0)**2 + (y1-y0)**2) > 3*med) |
                (np.sqrt((x2-x1)**2 + (y2-y1)**2) > 3*med) |
                (np.sqrt((x0-x2)**2 + (y0-y2)**2) > 3*med)
            )
            tri.set_mask(mask)
        return ax.tricontourf(tri, values, levels=64, cmap=cmap, norm=norm)
    except Exception:
        return ax.scatter(xy[:, 0], xy[:, 1], c=values, cmap=cmap, norm=norm,
                          s=1, linewidths=0, rasterized=True)


def _draw_mesh(ax, edge_segments: list, *, alpha: float = 0.35, lw: float = 0.4):
    """Overlay mesh wireframe from pre-extracted edge segments."""
    if not edge_segments:
        return
    lc = LineCollection(edge_segments, linewidths=lw, colors="0.25",
                        alpha=alpha, rasterized=True)
    ax.add_collection(lc)


def _render_combined(region_data: list[tuple],
                     *, title: str, xlabel: str, ylabel: str,
                     cbar_label: str, cmap: str, vmin: float, vmax: float,
                     out_path: Path, dpi: int = 150) -> None:
    """Overlay all regions on one axes with shared colorbar and mesh wireframe."""
    fig, ax = plt.subplots(figsize=(5.5, 5.0), dpi=dpi)
    norm = Normalize(vmin=vmin, vmax=vmax)

    mappable = None
    for _region_name, xy, values, _edges in region_data:
        m = _triplot(ax, xy, values, norm=norm, cmap=cmap)
        if mappable is None:
            mappable = m

    # Mesh edges drawn on top of all filled regions
    for _region_name, _xy, _values, edges in region_data:
        _draw_mesh(ax, edges)

    if mappable is not None:
        cbar = fig.colorbar(mappable, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(cbar_label, fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    # Region name annotations at centroid
    for region_name, xy, _values, _edges in region_data:
        cx, cy = xy[:, 0].mean(), xy[:, 1].mean()
        ax.text(cx, cy, region_name, fontsize=6, ha="center", va="center",
                color="white", alpha=0.8,
                bbox=dict(boxstyle="round,pad=0.1", fc="none", ec="none"))

    ax.set_aspect("equal")
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.3f"))
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.3f"))
    ax.set_title(title, fontsize=9, pad=6)

    fig.tight_layout()
    fig.savefig(str(out_path), dpi=dpi)
    plt.close(fig)
    print(f"  Wrote: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Render OpenFOAM multi-region slice plots via ParaView + matplotlib")
    ap.add_argument("--case",        required=True)
    ap.add_argument("--regions",     default="jellyRoll,shell,cap",
                    help="Comma-separated region names")
    ap.add_argument("--fields",      default="T",
                    help="Comma-separated field names. Fields missing from a region are skipped.")
    ap.add_argument("--time",        default="100",
                    help="Comma-separated simulation times to visualise")
    ap.add_argument("--n-slices",    type=int, default=5,
                    help="Number of evenly-spaced z-normal slices (default: 5)")
    ap.add_argument("--longitudinal", action="store_true",
                    help="Also render one longitudinal slice (y=0, contains the z-axis)")
    ap.add_argument("--out-dir",     required=True)
    ap.add_argument("--prefix",      default="slice")
    ap.add_argument("--dpi",         type=int, default=150)
    ap.add_argument("--cmap-T",      default="coolwarm")
    ap.add_argument("--cmap-q",      default="plasma")
    ap.add_argument("--vmin-T",      type=float, default=None,
                    help="Fixed T colorbar min (K); auto if omitted")
    ap.add_argument("--vmax-T",      type=float, default=None,
                    help="Fixed T colorbar max (K); auto if omitted")
    ap.add_argument("--out-range",   default=None,
                    help="Path to write computed vmin/vmax as JSON (for report verification)")
    args = ap.parse_args()

    case_dir  = Path(args.case).resolve()
    out_dir   = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")

    regions   = [r.strip() for r in args.regions.split(",")]
    fields    = [f.strip() for f in args.fields.split(",")]
    time_vals = [float(t.strip()) for t in args.time.split(",")]

    print(f"Case: {foam_path}")
    print(f"Regions: {regions}  |  Fields: {fields}  |  Times: {time_vals}")

    def _available_fields(region: str, t: float) -> list[str]:
        for t_str in (str(int(t)), str(t)):
            d = case_dir / t_str / region
            if d.exists():
                return [f for f in fields if (d / f).exists()]
        return []

    t_probe = time_vals[0]
    readers: dict[str, tuple] = {}
    for region in regions:
        rf = _available_fields(region, t_probe)
        if not rf:
            print(f"  WARNING: none of {fields} found for region '{region}'; skipping.")
            continue
        print(f"  Opening region '{region}' with fields {rf}")
        readers[region] = (_open_reader(foam_path, region, rf, t_probe), rf)

    if not readers:
        print("No regions could be opened.", file=sys.stderr)
        return 1

    gb = _global_bounds([v[0] for v in readers.values()])
    # xmin xmax ymin ymax zmin zmax
    cx = (gb[0] + gb[1]) * 0.5
    cy = (gb[2] + gb[3]) * 0.5
    cz = (gb[4] + gb[5]) * 0.5
    z_lo, z_hi = gb[4], gb[5]

    generated: list[Path] = []

    for field in fields:
        cmap     = args.cmap_T if field == "T" else args.cmap_q
        cbar_lbl = "Temperature (K)" if field == "T" else "Heat generation (W m⁻³)"
        vmin_ovr = args.vmin_T if field == "T" else None
        vmax_ovr = args.vmax_T if field == "T" else None

        # Build the full list of (slice_tag, normal, origin, frac_idx) to render
        # slice_tag goes into the filename
        slice_specs: list[tuple[str, str, list[float], int]] = []

        for i in range(args.n_slices):
            frac = (i + 1) / (args.n_slices + 1)
            pos  = z_lo + frac * (z_hi - z_lo)
            slice_specs.append((f"z{i+1}", "z", [cx, cy, pos], i))

        if args.longitudinal:
            # y=0 plane contains the z-axis; show as one additional slice
            slice_specs.append(("long", "y", [cx, cy, cz], 0))

        # ---- pass 1: gather all data to compute global colour range ----
        all_vals: list[np.ndarray] = []
        cache: dict[tuple, list] = {}   # (time_val, tag) → region_patches

        for time_val in time_vals:
            for region, (reader, _) in readers.items():
                reader.UpdatePipeline(time_val)

            for tag, normal, origin, _idx in slice_specs:
                region_patches = []
                for region, (reader, region_fields) in readers.items():
                    if field not in region_fields:
                        continue
                    print(f"  Slice: {field} region={region} {tag} t={time_val}s")
                    xy, values, edges = _fetch_slice(
                        reader, time_val=time_val, normal=normal,
                        origin=origin, field=field)
                    if xy is None:
                        print(f"    (empty — skipped)")
                        continue
                    region_patches.append((region, xy, values, edges))
                    all_vals.append(values)
                cache[(time_val, tag)] = region_patches

        if not all_vals:
            continue

        # Global colour range — identical for z-normal AND longitudinal slices
        flat = np.concatenate(all_vals)
        vmin = float(vmin_ovr) if vmin_ovr is not None else float(np.nanpercentile(flat, 1))
        vmax = float(vmax_ovr) if vmax_ovr is not None else float(np.nanpercentile(flat, 99))
        print(f"  Global colour range for {field}: vmin={vmin:.4f}  vmax={vmax:.4f}")

        # Write range sidecar so the report can display/verify the fixed range
        if field == "T" and args.out_range:
            import json as _json
            Path(args.out_range).write_text(
                _json.dumps({"T_vmin": vmin, "T_vmax": vmax}, indent=2))

        # ---- pass 2: render ----
        for time_val in time_vals:
            for tag, normal, origin, _idx in slice_specs:
                region_patches = cache.get((time_val, tag), [])
                if not region_patches:
                    continue

                _, _, xlabel, ylabel = _AX_MAP[normal]
                pos = origin[{"x": 0, "y": 1, "z": 2}[normal]]
                regions_str = ", ".join(r for r, *_ in region_patches)
                slice_label = f"{normal} = {pos*1e3:.1f} mm" if tag != "long" else "longitudinal (y=0)"
                title = (f"{field}  |  {slice_label}  |  "
                         f"t = {time_val:.0f} s  |  {regions_str}")
                fname = out_dir / f"{args.prefix}_{field}_{tag}_t{int(time_val):04d}.png"
                _render_combined(region_patches,
                                 title=title, xlabel=xlabel, ylabel=ylabel,
                                 cbar_label=cbar_lbl, cmap=cmap,
                                 vmin=vmin, vmax=vmax,
                                 out_path=fname, dpi=args.dpi)
                generated.append(fname)

    for reader, _ in readers.values():
        Delete(reader)

    print(f"\nDone. {len(generated)} image(s) written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
