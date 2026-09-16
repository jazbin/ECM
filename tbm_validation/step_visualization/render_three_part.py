"""
Three-part reduced view: Can + Jellyroll + Cap only.

Purpose: compare the returned STAR-CCM+/BDS STEP topology against the
target ECM-OpenFOAM coupling topology, which represents a cell with only
three parts (Can, Jellyroll, Cap). This is a body-SELECTION filter only --
no geometry is modified, healed, or merged. All other bodies (Mandrel,
tab-root/stem, washer, internal-post) are simply not drawn.

Mapping note (explicit, not inferred from appearance): the returned STEP
files have no body literally named "Cap". The axial end-cap equivalent is
the "EndPlate" body (+Ve EndPlate / -Ve EndPlate). This script treats
Cap := EndPlate. This is a naming/selection assumption, stated here so it
is not mistaken for a measured fact.

Usage:
    python3 render_three_part.py <case_id> <step_path> <output_dir>

Writes:
    <output_dir>/<case_id>_E_THREEPART_CAN_TRANSPARENT_ISO.png
    <output_dir>/<case_id>_F_THREEPART_INTERNALS_ISO.png
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from step_render_common import load_named_solids, overall_bbox, shape_to_polydata, BODY_COLORS, FALLBACK_COLOR
import pyvista as pv

IMG_SIZE = (1600, 1600)

THREE_PART_BODIES = {"Can", "Jellyroll", "+Ve EndPlate", "-Ve EndPlate"}


def set_iso_camera(plotter, bounds):
    import math
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


def add_legend(plotter, names_present):
    entries = [[n, BODY_COLORS.get(n, FALLBACK_COLOR)] for n in names_present]
    plotter.add_legend(entries, bcolor="white", face="rectangle", size=(0.26, 0.20), loc="lower right")


def render_view(shapes, out_path, bounds, opacities, title):
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
        pl.add_mesh(mesh, color=color, opacity=op, smooth_shading=True, specular=0.2)
    set_iso_camera(pl, bounds)
    add_legend(pl, names_present)
    pl.add_text(title, position="upper_left", font_size=12, color="black")
    pl.screenshot(out_path, transparent_background=True)
    pl.close()


def main():
    case_id, step_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)

    all_shapes = load_named_solids(step_path)
    shapes = [(n, s) for n, s in all_shapes if n in THREE_PART_BODIES]
    if len(shapes) != 4:
        found = sorted(n for n, _ in shapes)
        print(f"WARNING {case_id}: expected 4 three-part bodies (Can, Jellyroll, "
              f"+Ve EndPlate, -Ve EndPlate), found {len(shapes)}: {found}")

    # Bounds from the three-part subset only, so cropping/scale reflects
    # just Can+Jellyroll+Cap, not the full 13-body cell.
    bounds = overall_bbox(shapes)

    can_transparent_op = {"__default__": 0.92, "Can": 0.10}
    render_view(shapes, os.path.join(out_dir, f"{case_id}_E_THREEPART_CAN_TRANSPARENT_ISO.png"),
                bounds, can_transparent_op,
                f"{case_id} — Can+Jellyroll+Cap only, Can transparent")

    internals_op = {"__default__": 1.0, "Can": 0.0}
    render_view(shapes, os.path.join(out_dir, f"{case_id}_F_THREEPART_INTERNALS_ISO.png"),
                bounds, internals_op,
                f"{case_id} — Jellyroll+Cap only (Can hidden)")

    print(f"{case_id}: OK, three-part views -> {out_dir}")


if __name__ == "__main__":
    main()
