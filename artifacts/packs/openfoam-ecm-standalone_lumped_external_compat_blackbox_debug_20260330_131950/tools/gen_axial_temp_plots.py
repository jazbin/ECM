#!/usr/bin/env python3
"""
Generate axial temperature profiles (T vs Z along cell axis) through all regions.

Sources:
  - distributed_solid: postProcessing/sampleLine/{region}/300s/axisLine_T.xy
  - lumped_solid:      vtk reader — sample T along Z at (x≈0, y≈0)

Outputs:
  doc_client/ST01_axial_T_distributed.png  — distributed t=300 s
  doc_client/ST02_axial_T_lumped.png       — lumped t=30 s
  doc_client/ST03_axial_T_comparison.png   — overlay comparison
"""
import os; os.environ.setdefault("DISPLAY", ":99")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

OUT   = Path("/workspace/artifacts/plots/doc_client")
C1    = "#1565c0"   # blue  — jellyRoll
C2    = "#c62828"   # red   — shell
C3    = "#2e7d32"   # green — cap
C_LMP = "#e65100"   # orange — lumped profile
C_DST = "#1565c0"   # blue  — distributed profile

DPI = 200
plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25,
    "font.size": 9.5, "axes.titlesize": 11,
    "axes.labelsize": 9.5, "legend.fontsize": 8.5,
})

# ── 1. load distributed sampleLine data ──────────────────────────────────────
BASE_D = Path("/workspace/cases/distributed_solid/postProcessing/sampleLine")
region_cfg = {
    "jellyRoll": (C1, "jellyRoll (active zone)"),
    "shell":     (C2, "shell (outer casing)"),
    "cap":       (C3, "cap (top)"),
}

dist_data = {}
for region, (color, label) in region_cfg.items():
    rdir = BASE_D / region
    if not rdir.exists():
        continue
    timesteps = sorted([d.name for d in rdir.iterdir() if d.is_dir()], key=float)
    if not timesteps:
        continue
    t_last = timesteps[-1]
    xy_file = rdir / t_last / "axisLine_T.xy"
    if xy_file.exists():
        data = np.loadtxt(xy_file)
        z_m  = data[:, 2]          # z coordinate [m]
        T    = data[:, 3]          # temperature [K]
        idx  = np.argsort(z_m)
        dist_data[region] = {
            "z_mm": z_m[idx] * 1e3,
            "T":    T[idx],
            "t":    float(t_last),
            "color": color,
            "label": label,
        }
        print(f"  {region}: {len(z_m)} pts, z=[{z_m.min()*1e3:.1f},{z_m.max()*1e3:.1f}] mm, "
              f"T=[{T.min():.1f},{T.max():.1f}] K")

# ── 2. extract lumped_solid axial profile using vtk ──────────────────────────
print("Reading lumped_solid vtk mesh …", flush=True)
from vtkmodules.all import (
    vtkOpenFOAMReader, vtkCellLocator, vtkGenericCell,
    vtkStreamingDemandDrivenPipeline as SDP,
)
from vtkmodules.util.numpy_support import vtk_to_numpy
import vtk

def read_latest(foam_file):
    reader = vtkOpenFOAMReader()
    reader.SetFileName(str(foam_file))
    reader.CreateCellToPointOff()
    reader.UpdateInformation()
    ti = reader.GetOutputInformation(0)
    nsteps = ti.Length(SDP.TIME_STEPS())
    if nsteps > 0:
        t = ti.Get(SDP.TIME_STEPS(), nsteps - 1)
        ti.Set(SDP.UPDATE_TIME_STEP(), t)
        print(f"  t={t:.4f} s", flush=True)
    reader.Update()
    return reader.GetOutput()

_REGION_IDX = {"jellyroll": 2, "shell": 3, "cap": 1}

def find_region(top, name):
    idx = _REGION_IDX.get(name.lower())
    if idx is None: return None
    blk = top.GetBlock(idx)
    if blk is None: return None
    nb = blk.GetNumberOfBlocks() if hasattr(blk, "GetNumberOfBlocks") else 0
    return blk.GetBlock(0) if nb > 0 else blk

def sample_axial(mesh, n_bins=50, r_cut_m=1.0e-3):
    """Sample T along Z: average all near-axis cells (r < r_cut_m) per z-bin."""
    if mesh is None: return np.array([]), np.array([])
    cd = mesh.GetCellData()
    t_arr = cd.GetArray("T")
    if t_arr is None: return np.array([]), np.array([])

    from vtkmodules.all import vtkCellCenters
    cc = vtkCellCenters()
    cc.SetInputData(mesh)
    cc.Update()
    pts = vtk_to_numpy(cc.GetOutput().GetPoints().GetData())  # (N,3)
    T   = vtk_to_numpy(t_arr).reshape(-1)

    z    = pts[:, 2]
    r_xy = np.sqrt(pts[:, 0]**2 + pts[:, 1]**2)

    # Keep only near-axis cells; fall back to closest 1% if cutoff catches nothing
    mask = r_xy < r_cut_m
    if mask.sum() < 10:
        mask = r_xy < np.percentile(r_xy, 1)
    if not mask.any():
        return np.array([]), np.array([])

    z_ax, T_ax = z[mask], T[mask]

    # Bin by z and average T within each bin
    z_min, z_max = z_ax.min(), z_ax.max()
    edges = np.linspace(z_min, z_max, n_bins + 1)
    z_out, T_out = [], []
    for k in range(n_bins):
        in_bin = (z_ax >= edges[k]) & (z_ax < edges[k + 1])
        if not in_bin.any():
            continue
        z_out.append(0.5 * (edges[k] + edges[k + 1]))
        T_out.append(T_ax[in_bin].mean())

    return np.array(z_out) * 1e3, np.array(T_out)

top_l = read_latest(Path("/workspace/cases/lumped_solid/foam.foam"))
lmp_data = {}
for region, (color, label) in region_cfg.items():
    mesh = find_region(top_l, region)
    z_mm, T = sample_axial(mesh)
    if len(z_mm) > 0:
        lmp_data[region] = {
            "z_mm": z_mm,
            "T": T,
            "color": color,
            "label": label,
        }
        print(f"  lumped {region}: {len(z_mm)} pts, "
              f"z=[{z_mm.min():.1f},{z_mm.max():.1f}] mm, "
              f"T=[{T.min():.1f},{T.max():.1f}] K")


def _add_region_spans(ax):
    """Shade background regions."""
    ax.axvspan(0,   2.1, alpha=0.05, color=C2, label="_shell-bottom")
    ax.axvspan(2.1, 58.4, alpha=0.06, color=C1, label="_jellyRoll span")
    ax.axvspan(58.4, 70.0, alpha=0.05, color=C3, label="_cap span")
    ax.axvline(2.1,  lw=0.6, ls="--", color="grey", alpha=0.4)
    ax.axvline(58.4, lw=0.6, ls="--", color="grey", alpha=0.4)
    ax.text(1.0,  ax.get_ylim()[0] + 0.5, "shell", fontsize=7, color=C2, rotation=90,
            va="bottom", ha="center", alpha=0.8)
    ax.text(30.0, ax.get_ylim()[0] + 0.5, "jellyRoll", fontsize=7.5, color=C1,
            ha="center", va="bottom", alpha=0.8)
    ax.text(64.0, ax.get_ylim()[0] + 0.5, "cap", fontsize=7, color=C3, rotation=90,
            va="bottom", ha="center", alpha=0.8)


# ── 3. Figure ST01: distributed axial T ──────────────────────────────────────
print("Plotting ST01 …", flush=True)
fig, ax = plt.subplots(figsize=(9, 4.5), dpi=DPI)
for region, d in dist_data.items():
    ax.plot(d["z_mm"], d["T"], color=d["color"], lw=1.8, label=d["label"])
ax.set_xlabel("Z position along cell axis [mm]")
ax.set_ylabel("Temperature T [K]")
ax.set_title("Axial temperature profile — distributed case  (t = 300 s)")
ax.set_xlim(0, 72)
ax.xaxis.set_major_locator(plt.MultipleLocator(10))
ylo, yhi = ax.get_ylim()
ax.set_ylim(ylo, yhi)
_add_region_spans(ax)
ax.legend(loc="upper right", framealpha=0.9)
fig.tight_layout()
fig.savefig(OUT / "ST01_axial_T_distributed.png", dpi=DPI, bbox_inches="tight")
plt.close(fig)
print("  ✓  ST01_axial_T_distributed.png")

# ── 4. Figure ST02: lumped axial T ───────────────────────────────────────────
print("Plotting ST02 …", flush=True)
fig, ax = plt.subplots(figsize=(9, 4.5), dpi=DPI)
for region, d in lmp_data.items():
    ax.scatter(d["z_mm"], d["T"], s=4, color=d["color"], label=d["label"])
    # also thin line through sorted points
    ax.plot(d["z_mm"], d["T"], color=d["color"], lw=1.0, alpha=0.6)
ax.set_xlabel("Z position along cell axis [mm]")
ax.set_ylabel("Temperature T [K]")
ax.set_title("Axial temperature profile — lumped case  (t = 30 s)")
ax.set_xlim(0, 72)
ax.xaxis.set_major_locator(plt.MultipleLocator(10))
ylo, yhi = ax.get_ylim()
ax.set_ylim(ylo, yhi)
_add_region_spans(ax)
ax.legend(loc="upper right", framealpha=0.9)
fig.tight_layout()
fig.savefig(OUT / "ST02_axial_T_lumped.png", dpi=DPI, bbox_inches="tight")
plt.close(fig)
print("  ✓  ST02_axial_T_lumped.png")

# ── 5. Figure ST03: overlay comparison (lumped jellyRoll vs distributed) ─────
print("Plotting ST03 …", flush=True)
fig, ax = plt.subplots(figsize=(9, 4.5), dpi=DPI)

if "jellyRoll" in lmp_data:
    d = lmp_data["jellyRoll"]
    ax.plot(d["z_mm"], d["T"], color=C_LMP, lw=1.8, label="Lumped jellyRoll (t = 30 s)")

if "jellyRoll" in dist_data:
    d = dist_data["jellyRoll"]
    ax.plot(d["z_mm"], d["T"], color=C_DST, lw=1.8, ls="--",
            label="Distributed jellyRoll (t = 300 s)")

ax.set_xlabel("Z position along cell axis [mm]")
ax.set_ylabel("Temperature T [K]")
ax.set_title("Axial temperature profile — jellyRoll centreline comparison")
ax.set_xlim(0, 72)
ax.xaxis.set_major_locator(plt.MultipleLocator(10))
ylo, yhi = ax.get_ylim()
ax.set_ylim(ylo, yhi)
_add_region_spans(ax)
ax.legend(loc="upper right", framealpha=0.9)
fig.tight_layout()
fig.savefig(OUT / "ST03_axial_T_comparison.png", dpi=DPI, bbox_inches="tight")
plt.close(fig)
print("  ✓  ST03_axial_T_comparison.png")

print("\nDone — ST01 ST02 ST03 written to", OUT)
