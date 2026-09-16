"""
Shared helpers for the 2026-09-16 client-return STEP visualization package.

Read-only visualization pipeline: STEP files are read exactly as delivered
via pythonocc-core (OpenCASCADE bindings). The only geometric operation
performed is triangulation (BRepMesh_IncrementalMesh) purely for rendering.
The tessellation is never written back over the source STEP and never
feeds into any CAD/geometry-generation step. See README.md for details.
"""
import os
import numpy as np

from OCC.Extend.DataExchange import read_step_file_with_names_colors
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopAbs import TopAbs_REVERSED
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib

import pyvista as pv

# Tessellation deflection (mm). Rendering only -- not used for any
# geometric/engineering conclusion. Cell overall size is ~O(20mm) diameter
# x O(70mm) length, so this deflection resolves fine surface detail.
LINEAR_DEFLECTION = 0.02
ANGULAR_DEFLECTION = 0.3

# Canonical short label for each STEP body name (STEP names are prefixed
# "Cylindrical Cell: <part>").
def short_name(step_name: str) -> str:
    return step_name.split(":", 1)[-1].strip() if ":" in step_name else step_name.strip()

# Fixed color assigned per canonical short body name. Same mapping used for
# every case so colors are comparable across renders. Colors are chosen for
# visual distinguishability only; they do NOT indicate any known material.
BODY_COLORS = {
    "Can":                  (0.80, 0.80, 0.80),  # light neutral gray
    "Jellyroll":            (0.85, 0.66, 0.13),  # gold
    "Mandrel":              (0.30, 0.30, 0.34),  # dark slate gray
    "+Ve Tab Root":         (0.80, 0.10, 0.10),  # red
    "+Ve Tab Stem":         (0.92, 0.40, 0.10),  # orange-red
    "+Ve Washer":           (0.60, 0.00, 0.00),  # dark red
    "+Ve EndPlate":         (0.92, 0.55, 0.45),  # salmon
    "+Ve Internal-Post":    (0.55, 0.10, 0.20),  # maroon
    "-Ve Tab Root":         (0.10, 0.20, 0.85),  # blue
    "-Ve Tab Stem":         (0.10, 0.55, 0.92),  # teal-blue
    "-Ve Washer":           (0.00, 0.00, 0.55),  # navy
    "-Ve EndPlate":         (0.45, 0.65, 0.92),  # sky blue
    "-Ve Internal-Post":    (0.28, 0.10, 0.55),  # indigo
}
FALLBACK_COLOR = (0.5, 0.5, 0.5)

# Conceptual grouping requested by the task, used for the legend and for
# per-view transparency rules (e.g. "make Can transparent").
def group_of(short: str) -> str:
    if short == "Can":
        return "Can"
    if short == "Jellyroll":
        return "Jellyroll"
    if short == "Mandrel":
        return "Mandrel"
    if short.startswith("+Ve"):
        return "Positive-side structures"
    if short.startswith("-Ve"):
        return "Negative-side structures"
    return "Other"


def load_named_solids(step_path: str, log_fn=print):
    """Read a STEP file and return list of (short_name, TopoDS_Shape).

    Uses pythonocc's OCC.Extend.DataExchange.read_step_file_with_names_colors,
    which internally uses STEPCAFControl_Reader (OCAF) so body names are
    recovered exactly as authored in the STEP file. No geometry is modified.
    """
    shapes = read_step_file_with_names_colors(step_path)
    out = []
    for shp, (name, _color) in shapes.items():
        out.append((short_name(name), shp))
    return out


def overall_bbox(shapes):
    box = Bnd_Box()
    for _name, shp in shapes:
        brepbndlib.Add(shp, box)
    return box.Get()  # xmin,ymin,zmin,xmax,ymax,zmax


def shape_to_polydata(shape) -> pv.PolyData:
    """Tessellate a TopoDS_Shape (rendering only) and return a pyvista mesh."""
    BRepMesh_IncrementalMesh(shape, LINEAR_DEFLECTION, False, ANGULAR_DEFLECTION, True)
    verts = []
    faces = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            n_before = len(verts)
            nb_nodes = tri.NbNodes()
            for i in range(1, nb_nodes + 1):
                p = tri.Node(i)
                p.Transform(trsf)
                verts.append((p.X(), p.Y(), p.Z()))
            reversed_face = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                t = tri.Triangle(i)
                a, b, c = t.Get()
                a += n_before - 1
                b += n_before - 1
                c += n_before - 1
                if reversed_face:
                    faces.append((3, a, c, b))
                else:
                    faces.append((3, a, b, c))
        exp.Next()
    if not verts:
        return pv.PolyData()
    points = np.array(verts, dtype=float)
    face_arr = np.hstack(faces).astype(np.int64) if faces else np.array([], dtype=np.int64)
    return pv.PolyData(points, face_arr)


CASE_META = {
    # case_id: (step filename, purpose text from client xlsx "test purpose" column)
    "H01": ("H01_POS_ZERO_SURPLUS.step", "Working cell; +tab length = +electrode width => +surplus 0.00 mm."),
    "H02": ("H02_POS_SURPLUS_0p10.step", "Working cell; +tab surplus +0.10 mm."),
    "H03": ("H03_POS_SURPLUS_0p70.step", "Working cell; +tab surplus +0.70 mm."),
    "H04": ("H04_POS_SURPLUS_2p00.step", "Working cell; +tab surplus +2.00 mm."),
    "H05": ("H05_NEG_ZERO_SURPLUS.step", "Working cell; -tab length = -electrode width => -surplus 0.00 mm."),
    "H06": ("H06_NEG_SURPLUS_0p10.step", "Working cell; -tab surplus +0.10 mm."),
    "H07": ("H07_NEG_SURPLUS_0p70.step", "Working cell; -tab surplus +0.70 mm."),
    "H08": ("H08_NEG_SURPLUS_2p00.step", "Working cell; -tab surplus +2.00 mm."),
    "H11": ("H11_BOTH_SURPLUS_0p70.step", "Working cell; both surpluses +0.70 mm."),
    "H12": ("H12_BOTH_SURPLUS_2p00.step", "Working cell; both surpluses +2.00 mm."),
    "H13": ("H13_BOTH_TAB_LENGTH_60.step", "Working cell; absolute tab length 60 mm, positive surpluses +4/+3 mm."),
    "T01": ("T01_TARGET_AXIAL_TABS65.step", "Target axial stack, 65-mm tabs: +surplus +0.89 mm; -surplus -0.11 mm."),
    "T04": ("T04_TARGET_AXIAL_SURPLUS_0p70.step", "Target axial stack; both surpluses +0.70 mm."),
    "T05": ("T05_TARGET_AXIAL_SURPLUS_1p00.step", "Target axial stack; both surpluses +1.00 mm."),
    "T06": ("T06_TARGET_AXIAL_SURPLUS_2p00.step", "Target axial stack; both surpluses +2.00 mm."),
    "T07": ("T07_TARGET_AXIAL_SURPLUS_5p00.step", "Target axial stack; both surpluses +5.00 mm."),
    "T08": ("T08_TARGET_AXIAL_WORKING_DERIVED_HEIGHTS.step", "Target axial stack; working derived heights +9/+8 mm."),
}

T_PROGRESSION = ["T01", "T04", "T05", "T06", "T07", "T08"]
