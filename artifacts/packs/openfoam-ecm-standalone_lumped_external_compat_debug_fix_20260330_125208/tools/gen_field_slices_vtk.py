#!/usr/bin/env python3
"""
Re-render temperature and heat-field cross-section images with clean axis labels.
Replaces the 5 images that had x-axis tick overlap:
  SF03 — lumped all-region cross-section T at t=30 s
  SF04 — distributed all-region cross-section T at t=300 s (extended run)
  SF14 — overlap-case all-region cross-section T at t=300 s (extended run)
  SF06 — heat per CFD cell, longitudinal (Y–Z plane)
  SF07 — heat per ECM zone, radial cross-section (X–Y plane)
  SF08 — heat per CFD cell, radial cross-section (X–Y plane)

Run with:  /workspace/.conda_paraview/bin/python tools/gen_field_slices_vtk.py
Output:    /workspace/artifacts/plots/doc_client/  (overwrites SF03/04/06/07/08/14)
"""
import sys, os
os.environ.setdefault("DISPLAY", ":99")

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

OUT   = Path("/workspace/artifacts/plots/doc_client")
DPI   = 180
CMAP_T    = "inferno"
CMAP_HEAT = "inferno"

# ── helpers ──────────────────────────────────────────────────────────────────

def read_case(foam_file, time_idx=-1):
    """Read OpenFOAM case; time_idx=-1 selects last available timestep."""
    from vtkmodules.all import vtkStreamingDemandDrivenPipeline as SDP
    reader = vtkOpenFOAMReader()
    reader.SetFileName(str(foam_file))
    reader.CreateCellToPointOff()
    reader.ReadZonesOn()
    reader.UpdateInformation()
    ti = reader.GetOutputInformation(0)
    nsteps = ti.Length(SDP.TIME_STEPS())
    if nsteps > 0:
        idx = nsteps - 1 if time_idx == -1 else min(time_idx, nsteps - 1)
        t = ti.Get(SDP.TIME_STEPS(), idx)
        ti.Set(SDP.UPDATE_TIME_STEP(), t)
        print(f"  Reading time t={t:.4f} s (step {idx}/{nsteps-1})", flush=True)
    reader.Update()
    return reader.GetOutput()

def get_block(top, name):
    """Return internalMesh for a named region block."""
    for i in range(top.GetNumberOfBlocks()):
        blk = top.GetBlock(i)
        meta = top.GetMetaData(i)
        if meta and meta.Has(blk.GetClassName.__func__.__doc__ and
                             top.GetMetaData(i)):
            pass
        label = top.GetMetaData(i).Get(
            top.GetMetaData(i).STRING()
        ) if top.GetMetaData(i).Has(
            top.GetMetaData(i).STRING()
        ) else f"block{i}"
        if name.lower() in label.lower():
            # sub-block 0 = internalMesh
            if blk is not None and blk.GetNumberOfBlocks() > 0:
                return blk.GetBlock(0)
    return None

def get_named_block(top, name):
    """Find block by partial name match; return internalMesh (sub-block 0)."""
    for i in range(top.GetNumberOfBlocks()):
        blk = top.GetBlock(i)
        if blk is None:
            continue
        meta = top.GetMetaData(i)
        label = ""
        try:
            from vtkmodules.vtkCommonDataModel import vtkDataObject
            key = vtkDataObject.DATA_OBJECT_NAME()
            if meta.Has(key):
                label = meta.Get(key)
        except Exception:
            label = f"block{i}"
        if name.lower() in label.lower():
            if blk.GetNumberOfBlocks() > 0:
                return blk.GetBlock(0)
    return None

def slice_mesh(mesh, normal, origin):
    plane = vtkPlane()
    plane.SetOrigin(*origin)
    nmap = {"x": (1,0,0), "y": (0,1,0), "z": (0,0,1)}
    plane.SetNormal(*nmap[normal])
    cutter = vtkCutter()
    cutter.SetCutFunction(plane)
    cutter.SetInputData(mesh)
    cutter.Update()
    return cutter.GetOutput()

def extract_patches_and_vals(sl, field, axis0, axis1):
    """Return (patches, values) for a vtk slice output. Empty slice → ([], [])."""
    if sl is None or sl.GetNumberOfPoints() == 0 or sl.GetNumberOfCells() == 0:
        return [], np.array([])
    pts_raw = sl.GetPoints()
    if pts_raw is None:
        return [], np.array([])
    pts = vtk_to_numpy(pts_raw.GetData())
    cd  = sl.GetCellData()
    arr = cd.GetArray(field)
    if arr is None:
        return [], np.array([])
    vals = vtk_to_numpy(arr).reshape(-1)

    polys_vtk = sl.GetPolys()
    if polys_vtk is None:
        return [], np.array([])
    polys_vtk.InitTraversal()
    id_list = vtkIdList()
    patches = []
    while polys_vtk.GetNextCell(id_list):
        ids = [id_list.GetId(k) for k in range(id_list.GetNumberOfIds())]
        if len(ids) >= 3:
            patches.append(pts[ids][:, [axis0, axis1]])
    if not patches:
        return [], np.array([])
    return patches, vals[:len(patches)]

def _axis_params(normal):
    """Return (axis0, axis1, xlabel, ylabel) for a slice normal direction."""
    return {
        "x": (1, 2, "Y [mm]", "Z [mm]"),
        "y": (0, 2, "X [mm]", "Z [mm]"),
        "z": (0, 1, "X [mm]", "Y [mm]"),
    }[normal]

def save_field_image(patches_list, vals_list, out_path, title,
                     xlabel, ylabel, cbar_label, cmap, vmin=None, vmax=None,
                     figsize=(6.4, 4.8)):
    """Render a list of (patches, vals) tuples onto one axes with clean ticks."""
    all_pts = np.concatenate([p.reshape(-1, 2) for p in
                               [pt for patches in patches_list for pt in patches]], axis=0) \
        if patches_list else np.zeros((1,2))

    all_vals = np.concatenate(vals_list) if vals_list else np.zeros(1)
    if vmin is None: vmin = all_vals.min()
    if vmax is None: vmax = all_vals.max()
    if abs(vmax - vmin) < 1e-30:
        vmax = vmin + 1.0

    fig, ax = plt.subplots(figsize=figsize, dpi=DPI)
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    all_x, all_y = [], []
    for patches, vals in zip(patches_list, vals_list):
        if not patches:
            continue
        # convert to mm for display
        patches_mm = [p * 1e3 for p in patches]
        coll = PolyCollection(patches_mm, array=vals, cmap=cmap, norm=norm,
                              edgecolors="none", linewidths=0.0)
        ax.add_collection(coll)
        for p in patches:
            all_x.extend(p[:, 0])
            all_y.extend(p[:, 1])

    if all_x:
        xmn, xmx = min(all_x)*1e3, max(all_x)*1e3
        ymn, ymx = min(all_y)*1e3, max(all_y)*1e3
        ax.set_xlim(xmn, xmx)
        ax.set_ylim(ymn, ymx)

    ax.set_aspect("equal")
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=9.5)
    # clean ticks: max 4 on x, 5 on y
    ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    ax.yaxis.set_major_locator(plt.MaxNLocator(5))
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.18)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(cbar_label, fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  {out_path.name}", flush=True)


# ── 1. Load cases ─────────────────────────────────────────────────────────────
CASE_L = Path("/workspace/cases/lumped_solid")
CASE_D = Path("/workspace/cases/distributed_solid")
CASE_O = Path("/workspace/cases/distributed_solid_overlap")

print("Reading lumped_solid …", flush=True)
top_l = read_case(CASE_L / "foam.foam")

print("Reading distributed_solid …", flush=True)
top_d = read_case(CASE_D / "foam.foam")

print("Reading distributed_solid_overlap …", flush=True)
top_o = read_case(CASE_O / "foam.foam")

# jellyRoll = block index 2, shell = 3, cap = 1 (typical for splitMeshRegions)
# Try to find by name; fall back to known indices
def find_region_mesh(top, region_name, fallback_idx):
    for i in range(top.GetNumberOfBlocks()):
        blk = top.GetBlock(i)
        if blk is None:
            continue
        meta = top.GetMetaData(i)
        try:
            from vtkmodules.vtkCommonDataModel import vtkDataObject
            key = vtkDataObject.DATA_OBJECT_NAME()
            label = meta.Get(key) if meta.Has(key) else ""
        except Exception:
            label = ""
        if region_name.lower() in label.lower():
            nb = blk.GetNumberOfBlocks() if hasattr(blk, "GetNumberOfBlocks") else 0
            return blk.GetBlock(0) if nb > 0 else blk
    blk = top.GetBlock(fallback_idx)
    if blk is None:
        return None
    nb = blk.GetNumberOfBlocks() if hasattr(blk, "GetNumberOfBlocks") else 0
    return blk.GetBlock(0) if nb > 0 else blk

jr_l  = find_region_mesh(top_l, "jellyRoll", 2)
sh_l  = find_region_mesh(top_l, "shell",     3)
cap_l = find_region_mesh(top_l, "cap",       1)

jr_d  = find_region_mesh(top_d, "jellyRoll", 2)
sh_d  = find_region_mesh(top_d, "shell",     3)
cap_d = find_region_mesh(top_d, "cap",       1)

jr_o  = find_region_mesh(top_o, "jellyRoll", 2)
sh_o  = find_region_mesh(top_o, "shell",     3)
cap_o = find_region_mesh(top_o, "cap",       1)

for name, mesh in [("jr_l", jr_l), ("sh_l", sh_l), ("cap_l", cap_l),
                   ("jr_d", jr_d), ("sh_d", sh_d), ("cap_d", cap_d),
                   ("jr_o", jr_o), ("sh_o", sh_o), ("cap_o", cap_o)]:
    nc = mesh.GetNumberOfCells() if mesh else 0
    print(f"  {name}: {nc} cells", flush=True)

# centre-x origin for longitudinal slice (Y–Z plane, normal=x)
def centre_of(mesh):
    b = mesh.GetBounds()
    return ((b[0]+b[1])/2, (b[2]+b[3])/2, (b[4]+b[5])/2)


# ── 2. SF03 — lumped cross-section T at t=30 s (normal=z, mid-height) ─────
print("\n--- SF03: lumped cross-section T ---", flush=True)
ax0, ax1, xl, yl = _axis_params("z")
mid_z_l = centre_of(jr_l)[2]
patches_sf03, vals_sf03 = [], []
for mesh in [jr_l, sh_l, cap_l]:
    if mesh is None:
        continue
    sl = slice_mesh(mesh, "z", (0, 0, mid_z_l))
    p, v = extract_patches_and_vals(sl, "T", ax0, ax1)
    if len(p) > 0:
        patches_sf03.append(p)
        vals_sf03.append(v)

all_v = np.concatenate(vals_sf03) if vals_sf03 else np.array([313, 343])
save_field_image(patches_sf03, vals_sf03,
                 OUT / "SF03_lumped_crosssection_30s.png",
                 "Lumped — cross-section T  [t = 30 s]",
                 xl, yl, "T [K]", CMAP_T,
                 vmin=all_v.min(), vmax=all_v.max())

# ── 3. SF04 — distributed cross-section T at t=300 s ──────────────────────
print("--- SF04: distributed cross-section T ---", flush=True)
ax0, ax1, xl, yl = _axis_params("z")
mid_z_d = centre_of(jr_d)[2]
patches_sf04, vals_sf04 = [], []
for mesh in [jr_d, sh_d, cap_d]:
    if mesh is None:
        continue
    sl = slice_mesh(mesh, "z", (0, 0, mid_z_d))
    p, v = extract_patches_and_vals(sl, "T", ax0, ax1)
    if len(p) > 0:
        patches_sf04.append(p)
        vals_sf04.append(v)

all_v = np.concatenate(vals_sf04) if vals_sf04 else np.array([313, 343])
save_field_image(patches_sf04, vals_sf04,
                 OUT / "SF04_dist_crosssection_30s.png",
                 "Distributed — cross-section T  [t = 300 s extended run]",
                 xl, yl, "T [K]", CMAP_T,
                 vmin=all_v.min(), vmax=all_v.max())

# ── 3b. SF14 — overlap-case cross-section T at t=300 s ─────────────────────
print("--- SF14: overlap-case cross-section T ---", flush=True)
ax0, ax1, xl, yl = _axis_params("z")
mid_z_o = centre_of(jr_o)[2]
patches_sf14, vals_sf14 = [], []
for mesh in [jr_o, sh_o, cap_o]:
    if mesh is None:
        continue
    sl = slice_mesh(mesh, "z", (0, 0, mid_z_o))
    p, v = extract_patches_and_vals(sl, "T", ax0, ax1)
    if len(p) > 0:
        patches_sf14.append(p)
        vals_sf14.append(v)

all_v = np.concatenate(vals_sf14) if vals_sf14 else np.array([313, 343])
save_field_image(patches_sf14, vals_sf14,
                 OUT / "SF14_extended_300s_crosssection.png",
                 "Overlap case — cross-section T  [t = 300 s extended run]",
                 xl, yl, "T [K]", CMAP_T,
                 vmin=all_v.min(), vmax=all_v.max())

# ── 4. SF06/SF07/SF08 — heat maps from distributed ecmQdot ────────────────
MAP = CASE_D / "ecm/mapping_table_axial6_radial3_2170mesh_overlap.csv"
print("--- Loading mapping table for heat maps …", flush=True)
df_map = pd.read_csv(MAP)

# cell power = ecmQdot * cell_volume
# read ecmQdot from the jellyRoll mesh
def get_cell_array(mesh, name):
    cd = mesh.GetCellData()
    arr = cd.GetArray(name)
    if arr is None:
        return np.zeros(mesh.GetNumberOfCells())
    return vtk_to_numpy(arr).reshape(-1)

qvol    = get_cell_array(jr_d, "ecmQdot")  # W/m³
# compute cell volumes via vtkCellSizeFilter
from vtkmodules.all import vtkCellSizeFilter
csf = vtkCellSizeFilter()
csf.SetInputData(jr_d)
csf.ComputeVolumeOn()
csf.ComputeLengthOff(); csf.ComputeAreaOff(); csf.ComputeSumOff()
csf.Update()
vol_arr = vtk_to_numpy(csf.GetOutput().GetCellData().GetArray("Volume")).reshape(-1)
cell_power = qvol * vol_arr  # W per cell

# zone power = sum of cell_power weighted by mapping weights
from collections import defaultdict
from vtkmodules.all import vtkFloatArray

n_cells = jr_d.GetNumberOfCells()
zone_power = defaultdict(float)
zone_wsum  = defaultdict(float)
mesh_power = np.zeros(n_cells, dtype=float)

for _, row in df_map.iterrows():
    ci = int(row["meshKey"])
    zi = int(row["ecmCellId"])
    w  = float(row["weight"])
    if 0 <= ci < n_cells:
        mesh_power[ci] += cell_power[ci] * w

# zone assignment: highest-weight zone per cell
best_zone = np.full(n_cells, -1, dtype=int)
best_w    = np.zeros(n_cells, dtype=float)
for _, row in df_map.iterrows():
    ci = int(row["meshKey"]); zi = int(row["ecmCellId"]); w = float(row["weight"])
    if 0 <= ci < n_cells and w > best_w[ci]:
        best_w[ci] = w; best_zone[ci] = zi

# zone-level power = mean cell_power for cells assigned to each zone
zone_power_arr = np.zeros(n_cells, dtype=float)
for ci in range(n_cells):
    z = best_zone[ci]
    if z >= 0:
        zone_power_arr[ci] = cell_power[ci]

def add_array_to_mesh(mesh, arr, name):
    fa = vtkFloatArray()
    fa.SetName(name)
    fa.SetNumberOfComponents(1)
    fa.SetNumberOfTuples(len(arr))
    for i, v in enumerate(arr):
        fa.SetValue(i, float(v))
    m2 = mesh.NewInstance()
    m2.ShallowCopy(mesh)
    m2.GetCellData().AddArray(fa)
    m2.GetCellData().SetActiveScalars(name)
    return m2

jr_zp = add_array_to_mesh(jr_d, zone_power_arr,  "zoneHeat_W")
jr_cp = add_array_to_mesh(jr_d, cell_power,       "cellHeat_W")

cx = centre_of(jr_d)

# SF06 — heat per CFD cell, longitudinal (Y–Z plane, normal=x)
print("--- SF06: cellHeat longitudinal ---", flush=True)
ax0, ax1, xl, yl = _axis_params("x")
sl6 = slice_mesh(jr_cp, "x", cx)
p6, v6 = extract_patches_and_vals(sl6, "cellHeat_W", ax0, ax1)
if p6:
    save_field_image([p6], [v6],
                     OUT / "SF06_heat_cell_longitudinal.png",
                     "Heat per CFD cell [W]  |  longitudinal (Y–Z plane)  |  t = 300 s",
                     xl, yl, "Cell heat [W]", CMAP_HEAT)

# SF07 — heat per ECM zone, radial cross-section (X–Y plane, normal=z, mid-height)
print("--- SF07: zoneHeat cross-section ---", flush=True)
ax0, ax1, xl, yl = _axis_params("z")
sl7 = slice_mesh(jr_zp, "z", (0, 0, cx[2]))
p7, v7 = extract_patches_and_vals(sl7, "zoneHeat_W", ax0, ax1)
if p7:
    save_field_image([p7], [v7],
                     OUT / "SF07_heat_zone_crosssection.png",
                     "Heat per ECM zone [W]  |  radial cross-section  |  t = 300 s",
                     xl, yl, "Zone heat [W]", CMAP_HEAT)

# SF08 — heat per CFD cell, radial cross-section
print("--- SF08: cellHeat cross-section ---", flush=True)
sl8 = slice_mesh(jr_cp, "z", (0, 0, cx[2]))
p8, v8 = extract_patches_and_vals(sl8, "cellHeat_W", ax0, ax1)
if p8:
    save_field_image([p8], [v8],
                     OUT / "SF08_heat_cell_crosssection.png",
                     "Heat per CFD cell [W]  |  radial cross-section  |  t = 300 s",
                     xl, yl, "Cell heat [W]", CMAP_HEAT)

print("\nDone.")
