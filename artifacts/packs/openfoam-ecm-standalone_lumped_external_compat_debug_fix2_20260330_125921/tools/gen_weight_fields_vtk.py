#!/usr/bin/env python3
"""
Generate all 18 ECM zone weight field images using the actual jellyRoll
mesh geometry (vtkOpenFOAMReader + matplotlib PolyCollection).

Run with:  /workspace/.conda_paraview/bin/python tools/gen_weight_fields_vtk.py
Output:    /workspace/artifacts/plots/weight_fields/  (18 PNG + 1 composite)
"""
import sys, os
os.environ.setdefault("DISPLAY", ":99")   # suppress Qt/display warnings

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from pathlib import Path
import pandas as pd

from vtkmodules.all import (
    vtkOpenFOAMReader, vtkCutter, vtkPlane, vtkIdList,
)
from vtkmodules.util.numpy_support import vtk_to_numpy

CASE  = Path("/workspace/cases/distributed_solid")
MAP   = CASE / "ecm/mapping_table_axial6_radial3_2170mesh_overlap.csv"
OUT   = Path("/workspace/artifacts/plots/weight_fields")
OUT.mkdir(parents=True, exist_ok=True)

DPI        = 180
N_ZONES    = 18
CMAP       = "viridis"
FIGW, FIGH = 5.4, 4.8    # individual panel (matches original style)

# ── 1. load mesh ──────────────────────────────────────────────────────────────
print("Reading OpenFOAM mesh …", flush=True)
reader = vtkOpenFOAMReader()
reader.SetFileName(str(CASE / "foam.foam"))
reader.CreateCellToPointOff()
reader.Update()
top = reader.GetOutput()

# jellyRoll is block index 2, sub-block 0 = internalMesh
jr_mesh = top.GetBlock(2).GetBlock(0)
n_cells = jr_mesh.GetNumberOfCells()
print(f"  jellyRoll cells: {n_cells}", flush=True)

# ── 2. build slice geometry (once) ───────────────────────────────────────────
# Slice perpendicular to X at x=0 → gives Y-Z longitudinal half-cross-section
bounds = jr_mesh.GetBounds()   # (xmin,xmax, ymin,ymax, zmin,zmax)
cx = 0.0   # centred cell, slice at x=0

plane = vtkPlane()
plane.SetOrigin(cx, 0.0, 0.0)
plane.SetNormal(1.0, 0.0, 0.0)

# We will re-use the same mesh with different cell arrays
# Precompute the base slice geometry (point coords) without any field
def slice_mesh_with_field(mesh_with_field):
    cutter = vtkCutter()
    cutter.SetCutFunction(plane)
    cutter.SetInputData(mesh_with_field)
    cutter.Update()
    return cutter.GetOutput()

# ── 3. load mapping weights ───────────────────────────────────────────────────
print("Loading mapping table …", flush=True)
df = pd.read_csv(MAP)

# Build weight array: weights[zone, cell] (float32)
weights = np.zeros((N_ZONES, n_cells), dtype=np.float32)
for _, row in df.iterrows():
    ci = int(row["meshKey"])
    zi = int(row["ecmCellId"])
    w  = float(row["weight"])
    if 0 <= ci < n_cells and 0 <= zi < N_ZONES:
        weights[zi, ci] += w

# Per-zone normalise to [0,1]
w_max = weights.max(axis=1, keepdims=True)
w_max[w_max == 0] = 1.0
weights = weights / w_max

print("  weights loaded and normalised", flush=True)

# ── 4. add a cell-data array to the mesh ─────────────────────────────────────
from vtkmodules.all import vtkFloatArray

def make_mesh_with_weight(zone_id):
    arr = vtkFloatArray()
    arr.SetName("weight")
    arr.SetNumberOfComponents(1)
    arr.SetNumberOfTuples(n_cells)
    w = weights[zone_id]
    for i in range(n_cells):
        arr.SetValue(i, float(w[i]))
    mesh2 = jr_mesh.NewInstance()
    mesh2.ShallowCopy(jr_mesh)
    mesh2.GetCellData().AddArray(arr)
    mesh2.GetCellData().SetActiveScalars("weight")
    return mesh2

# ── 5. helper: extract face patches from a slice ──────────────────────────────
def extract_patches(sl):
    pts = vtk_to_numpy(sl.GetPoints().GetData())   # (N_pts, 3)
    # iterate polygons
    polys_vtk = sl.GetPolys()
    polys_vtk.InitTraversal()
    id_list = vtkIdList()
    patches, cell_ids = [], []
    cid = 0
    while polys_vtk.GetNextCell(id_list):
        ids = [id_list.GetId(k) for k in range(id_list.GetNumberOfIds())]
        patches.append(pts[ids][:, [1, 2]])   # Y, Z axes
        cell_ids.append(cid)
        cid += 1
    return patches, pts

def get_cell_values(sl, field="weight"):
    cd = sl.GetCellData()
    arr = cd.GetArray(field)
    if arr is None:
        return np.zeros(sl.GetNumberOfCells())
    return vtk_to_numpy(arr).flatten()

# ── 6. render individual zone images ─────────────────────────────────────────
# Zone labels: axial_idx = zone // 3, radial_idx = zone % 3
zone_labels = {
    z: f"z{z//3} r{z%3}  (zone {z:02d})"
    for z in range(N_ZONES)
}

y_bounds = (bounds[2], bounds[3])   # ymin, ymax
z_bounds = (bounds[4], bounds[5])   # zmin, zmax

img_paths = []

print("Rendering 18 zone images …", flush=True)
for zone in range(N_ZONES):
    mesh_w = make_mesh_with_weight(zone)
    sl = slice_mesh_with_field(mesh_w)
    patches, pts = extract_patches(sl)
    vals = get_cell_values(sl, "weight")

    fig, ax = plt.subplots(figsize=(FIGW, FIGH), dpi=DPI)
    norm = plt.Normalize(vmin=0.0, vmax=1.0)
    coll = PolyCollection(
        patches, array=vals,
        cmap=CMAP, norm=norm,
        edgecolors="none", linewidths=0.0,
    )
    ax.add_collection(coll)
    ax.set_xlim(float(pts[:, 1].min()), float(pts[:, 1].max()))
    ax.set_ylim(float(pts[:, 2].min()), float(pts[:, 2].max()))
    ax.set_aspect("equal")
    ax.set_xlabel("Y [mm]", fontsize=9)
    ax.set_ylabel("Z [mm]", fontsize=9)
    # convert axis ticks to mm and limit count
    ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    ax.yaxis.set_major_locator(plt.MaxNLocator(5))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v*1e3:.0f}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v*1e3:.0f}"))
    ax.set_title(
        f"ECM zone {zone:02d}  [z{zone//3} r{zone%3}]",
        fontsize=9.5
    )
    ax.grid(True, alpha=0.18)
    cb = fig.colorbar(coll, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Normalised weight", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.tight_layout()

    out_path = OUT / f"weight_zone{zone:02d}.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    img_paths.append(out_path)
    print(f"  ✓  zone {zone:02d}  ({len(patches)} patches)  → {out_path.name}", flush=True)

# ── 7. three 3×2 sub-composites (one per report page) ─────────────────────
# page k shows axial rows 2k, 2k+1  ×  3 radial cols  → 6 zones per page
print("Building 3 sub-composite pages …", flush=True)
from matplotlib.image import imread

page_paths = []
for page in range(3):
    axial_rows = [page * 2, page * 2 + 1]   # e.g. [0,1], [2,3], [4,5]
    fig, axes = plt.subplots(2, 3, figsize=(13, 9))
    fig.suptitle(
        f"Overlap-Weighted Mapping — ECM Zone Weight Fields  "
        f"(axial z{axial_rows[0]}–z{axial_rows[1]})\n"
        "Rows: axial sections  |  Columns: radial r0 (inner) → r2 (outer)",
        fontsize=10, fontweight="bold"
    )
    for row_i, ax_row in enumerate(axial_rows):
        for col in range(3):
            zone = ax_row * 3 + col
            ax = axes[row_i, col]
            img = imread(str(img_paths[zone]))
            ax.imshow(img)
            ax.axis("off")
            ax.set_title(f"z{ax_row} r{col}  (zone {zone:02d})", fontsize=9, pad=3)
    fig.tight_layout()
    p = OUT / f"weight_fields_page{page+1}.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    page_paths.append(p)
    print(f"  ✓  page {page+1}  (z{axial_rows[0]}–z{axial_rows[1]}) → {p.name}", flush=True)

# also keep old composite for reference
composite_path = OUT / "weight_fields_all_zones_composite.png"
fig2, axes2 = plt.subplots(6, 3, figsize=(13, 22))
fig2.suptitle(
    "Overlap-Weighted Mapping — All 18 ECM Zone Weight Fields\n"
    "Rows: axial z0 (bottom) → z5 (top)   |   Columns: radial r0 (inner) → r2 (outer)",
    fontsize=11, fontweight="bold"
)
for ax_row in range(6):
    for col in range(3):
        zone = ax_row * 3 + col
        ax2 = axes2[ax_row, col]
        img = imread(str(img_paths[zone]))
        ax2.imshow(img)
        ax2.axis("off")
        ax2.set_title(f"z{ax_row} r{col}", fontsize=8, pad=2)
fig2.tight_layout()
fig2.savefig(composite_path, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"  ✓  composite → {composite_path.name}", flush=True)

print("\n" + "="*60)
print(f"DONE — {len(img_paths)} individual images + 3 sub-composite pages + 1 full composite")
print(f"Output directory: {OUT}")
for p in page_paths:
    print(f"  {p}")
print(f"  {composite_path}")
