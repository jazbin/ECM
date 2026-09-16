"""
Fixed-scale, fixed-crop zoom on the +Ve (top) end region, rendered with the
SAME camera (position/focal point/parallel scale) for every case so that
small absolute dimensional differences (tab-root/tab-stem growth) are
directly visually comparable -- unlike the per-case auto-fit renders in
render_case.py, which normalize each case to fill the frame.

Usage: python3 render_end_zoom_fixed_scale.py <output_dir> <step_dir>
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))
from step_render_common import load_named_solids, shape_to_polydata, BODY_COLORS, FALLBACK_COLOR, CASE_META
import pyvista as pv

IMG_SIZE = (1400, 1400)

# Fixed crop window around the +Ve (top, +Y) end, shared by every case in the
# comparison. Chosen from the measured T01..T08 bounds (all cases: overall
# ymax ~= 67.56, +Ve EndPlate y in [67.495, 67.555], +Ve Tab Stem top y grows
# from ~65.56 (T01) to ~66.28 (T06/T07/T08), all radii ~+-10.5mm).
FIXED_BOUNDS = (-11.0, 63.5, -11.0, 11.0, 69.0, 11.0)  # xmin,ymin,zmin,xmax,ymax,zmax


def set_fixed_camera(plotter, bounds):
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    cx, cy, cz = (xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2
    diag = ((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2) ** 0.5
    dist = diag * 2.5
    d = 1.0 / math.sqrt(3.0)
    plotter.camera.SetFocalPoint(cx, cy, cz)
    plotter.camera.SetPosition(cx + dist * d, cy + dist * d, cz + dist * d)
    plotter.camera.SetViewUp(0, 1, 0)
    plotter.camera.ParallelProjectionOn()
    plotter.reset_camera(bounds=(xmin, xmax, ymin, ymax, zmin, zmax))
    plotter.camera.Zoom(0.92)
    # Freeze the parallel scale explicitly so it is bit-identical across calls
    plotter._fixed_parallel_scale = plotter.camera.GetParallelScale()


def render_one(case_id, step_path, out_dir):
    shapes = load_named_solids(step_path)
    pl = pv.Plotter(off_screen=True, window_size=IMG_SIZE)
    pl.set_background("white")
    can_op = {"Can": 0.10, "Jellyroll": 0.35, "__default__": 0.95}
    for name, shp in shapes:
        op = can_op.get(name, can_op["__default__"])
        mesh = shape_to_polydata(shp)
        if mesh.n_points == 0:
            continue
        color = BODY_COLORS.get(name, FALLBACK_COLOR)
        pl.add_mesh(mesh, color=color, opacity=op, smooth_shading=True, specular=0.2)
    set_fixed_camera(pl, FIXED_BOUNDS)
    pl.add_text(f"{case_id} — +Ve end, fixed camera/crop/scale", position="upper_left",
                font_size=14, color="black")
    out_path = os.path.join(out_dir, f"{case_id}_D_POS_END_ZOOM_FIXED_SCALE.png")
    pl.screenshot(out_path, transparent_background=True)
    pl.close()
    print(f"{case_id}: wrote {out_path}")


def main():
    out_dir, step_dir = sys.argv[1], sys.argv[2]
    for case_id in ["T01", "T04", "T05", "T06", "T07", "T08"]:
        fname, _purpose = CASE_META[case_id]
        render_one(case_id, os.path.join(step_dir, fname), out_dir)


if __name__ == "__main__":
    main()
