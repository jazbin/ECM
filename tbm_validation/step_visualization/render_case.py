"""
Render FULL_TRANSPARENT_ISO / CAN_TRANSPARENT_ISO / INTERNALS_ISO views for one
returned STEP file. See README.md for full methodology.

Usage:
    python3 render_case.py <case_id> <step_path> <output_dir>

Writes:
    <output_dir>/<case_id>_A_FULL_TRANSPARENT_ISO.png
    <output_dir>/<case_id>_B_CAN_TRANSPARENT_ISO.png
    <output_dir>/<case_id>_C_INTERNALS_ISO.png
    <output_dir>/<case_id>_import_log.txt   (STEP reader stdout, body list)
"""
import sys
import os
import io
import contextlib

sys.path.insert(0, os.path.dirname(__file__))
from step_render_common import (
    load_named_solids, overall_bbox, shape_to_polydata,
    BODY_COLORS, FALLBACK_COLOR, group_of,
)
import pyvista as pv

IMG_SIZE = (1600, 1600)


def set_iso_camera(plotter: pv.Plotter, bounds):
    """Consistent orthographic isometric camera for every case.

    Cell axial direction is global Y for every returned STEP (verified by
    inspecting overall bounding boxes: Y extent ~65-70 mm, X/Z ~21 mm).
    Eye direction is the standard isometric (1,1,1) diagonal; up vector is
    the axial (Y) direction so the cell reads as vertical in every image.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    cx, cy, cz = (xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2
    diag = ((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2) ** 0.5
    dist = diag * 2.5
    import math
    d = 1.0 / math.sqrt(3.0)
    plotter.camera.SetFocalPoint(cx, cy, cz)
    plotter.camera.SetPosition(cx + dist * d, cy + dist * d, cz + dist * d)
    plotter.camera.SetViewUp(0, 1, 0)
    plotter.camera.ParallelProjectionOn()
    vtk_bounds = (xmin, xmax, ymin, ymax, zmin, zmax)  # VTK bounds ordering
    plotter.reset_camera(bounds=vtk_bounds)
    plotter.camera.Zoom(0.92)  # small margin so the cell doesn't touch the frame edge


def add_legend(plotter: pv.Plotter, names_present):
    entries = []
    for n in names_present:
        color = BODY_COLORS.get(n, FALLBACK_COLOR)
        entries.append([n, color])
    plotter.add_legend(entries, bcolor="white", face="rectangle", size=(0.34, 0.34 if len(entries) > 8 else 0.28), loc="lower right")


def render_view(shapes, view_name, out_path, bounds, opacities, title):
    pl = pv.Plotter(off_screen=True, window_size=IMG_SIZE)
    pl.set_background("white")
    names_present = []
    for name, shp in shapes:
        op = opacities.get(name, opacities.get("__default__", 1.0))
        if op <= 0.0:
            continue
        names_present.append(name)
        mesh = shape_to_polydata(shp)
        if mesh.n_points == 0:
            continue
        color = BODY_COLORS.get(name, FALLBACK_COLOR)
        pl.add_mesh(mesh, color=color, opacity=op, smooth_shading=True,
                    specular=0.2, show_edges=False)
    set_iso_camera(pl, bounds)
    add_legend(pl, names_present)
    pl.add_text(title, position="upper_left", font_size=12, color="black")
    pl.screenshot(out_path, transparent_background=True)
    pl.close()
    return names_present


def main():
    case_id, step_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)

    log_buf = io.StringIO()
    with contextlib.redirect_stdout(log_buf):
        shapes = load_named_solids(step_path)
        bounds = overall_bbox(shapes)

    log_path = os.path.join(out_dir, f"{case_id}_import_log.txt")
    with open(log_path, "w") as f:
        f.write(f"STEP file: {step_path}\n")
        f.write(f"Body count: {len(shapes)}\n")
        f.write("Body names:\n")
        for name, _ in shapes:
            f.write(f"  - {name}\n")
        f.write("\n--- pythonocc/OCCT reader stdout (import warnings) ---\n")
        f.write(log_buf.getvalue())

    default_op = {"__default__": 0.45}
    render_view(shapes, "FULL_TRANSPARENT_ISO",
                os.path.join(out_dir, f"{case_id}_A_FULL_TRANSPARENT_ISO.png"),
                bounds, default_op, f"{case_id} — FULL_TRANSPARENT_ISO")

    can_op = {"__default__": 0.92, "Can": 0.08}
    render_view(shapes, "CAN_TRANSPARENT_ISO",
                os.path.join(out_dir, f"{case_id}_B_CAN_TRANSPARENT_ISO.png"),
                bounds, can_op, f"{case_id} — CAN_TRANSPARENT_ISO")

    internals_op = {"__default__": 1.0, "Can": 0.0}
    render_view(shapes, "INTERNALS_ISO",
                os.path.join(out_dir, f"{case_id}_C_INTERNALS_ISO.png"),
                bounds, internals_op, f"{case_id} — INTERNALS_ISO")

    print(f"{case_id}: OK, {len(shapes)} bodies -> {out_dir}")


if __name__ == "__main__":
    main()
