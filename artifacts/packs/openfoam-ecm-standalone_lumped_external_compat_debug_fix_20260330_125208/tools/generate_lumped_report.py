#!/usr/bin/env python3
"""
Generate a PDF report for a CHT+ECM case using the project default template.

Produces:
- artifacts/plots/<case>_*_<stamp>.png
- artifacts/reports/<case>_ecm_run_report_<stamp>.pdf (+ .txt summary)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _run(cmd: list[str], *, cwd: Path) -> str:
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout}")
    return p.stdout


def _parse_control_dict(control_dict: Path) -> dict:
    # Minimal OpenFOAM dictionary parsing sufficient for controlDict scalars.
    txt = control_dict.read_text(errors="ignore")
    # Drop line comments.
    txt = re.sub(r"//.*", "", txt)
    out: dict[str, str] = {}
    for key in ("application", "startTime", "endTime", "deltaT", "writeControl", "writeInterval"):
        m = re.search(rf"\b{re.escape(key)}\s+([^;]+);", txt)
        if m:
            out[key] = m.group(1).strip()
    return out


def _strip_comments(txt: str) -> str:
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.DOTALL)
    txt = re.sub(r"//.*", "", txt)
    return txt


def _extract_block(txt: str, key: str) -> str:
    idx = txt.find(key)
    if idx < 0:
        return ""
    brace = txt.find("{", idx)
    if brace < 0:
        return ""
    depth = 0
    for i in range(brace, len(txt)):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                return txt[brace + 1 : i]
    return ""


def _find_block_with_type(txt: str, type_name: str) -> str:
    i = 0
    while True:
        m = re.search(r"\b([A-Za-z0-9_]+)\s*\{", txt[i:])
        if not m:
            return ""
        start = i + m.start()
        brace = txt.find("{", start)
        if brace < 0:
            return ""
        depth = 0
        for j in range(brace, len(txt)):
            if txt[j] == "{":
                depth += 1
            elif txt[j] == "}":
                depth -= 1
                if depth == 0:
                    block = txt[brace + 1 : j]
                    if re.search(rf"\btype\s+{re.escape(type_name)}\s*;", block):
                        return block
                    i = j + 1
                    break
        else:
            return ""


def _parse_region_properties(region_props: Path) -> dict[str, list[str]]:
    if not region_props.exists():
        return {}
    txt = _strip_comments(region_props.read_text(errors="ignore"))
    m = re.search(r"regions\s*\((.*?)\);", txt, flags=re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, list[str]] = {}
    for line in block.splitlines():
        m = re.search(r"(\w+)\s*\(([^)]*)\)", line)
        if not m:
            continue
        region_type = m.group(1).strip()
        names = [v for v in m.group(2).split() if v]
        out[region_type] = names
    return out


def _parse_coupler_config(control_dict: Path) -> dict[str, str]:
    if not control_dict.exists():
        return {}
    txt = _strip_comments(control_dict.read_text(errors="ignore"))
    functions_block = _extract_block(txt, "functions")
    if not functions_block:
        functions_block = txt
    coupler_block = _find_block_with_type(functions_block, "ecmCoupler")
    if not coupler_block:
        return {}
    keys = (
        "region",
        "zone",
        "couplingMode",
        "lumpedOutput",
        "parallelMode",
        "keyMode",
        "relaxation",
        "inFile",
        "outFile",
        "command",
    )
    out: dict[str, str] = {}
    for key in keys:
        m = re.search(rf"\b{re.escape(key)}\s+([^;]+);", coupler_block)
        if m:
            out[key] = m.group(1).strip().strip('"')
    return out


def _count_occurrences(text: str, patterns: Iterable[str]) -> int:
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, text, flags=re.IGNORECASE))
    return count


def _numeric_time_dirs(case_dir: Path) -> list[str]:
    times: list[tuple[float, str]] = []
    for p in case_dir.iterdir():
        if not p.is_dir():
            continue
        name = p.name
        if re.fullmatch(r"[0-9]+(\.[0-9]+)?", name):
            try:
                times.append((float(name), name))
            except ValueError:
                pass
    times.sort(key=lambda x: x[0])
    return [name for _, name in times]


def _extract_qsum_series(log_text: str) -> tuple[list[float], list[float]]:
    re_time = re.compile(r"^\s*Time\s*=\s*([0-9eE+\-\.]+)\s*$")
    re_q = re.compile(r"^\s*Q_sum_check\s+([0-9eE+\-\.]+)\s*W\s*$")
    cur_t = None
    t_out: list[float] = []
    q_out: list[float] = []
    for line in log_text.splitlines():
        m = re_time.match(line)
        if m:
            try:
                cur_t = float(m.group(1))
            except ValueError:
                cur_t = None
            continue
        m = re_q.match(line)
        if m and cur_t is not None:
            try:
                q_out.append(float(m.group(1)))
                t_out.append(cur_t)
            except ValueError:
                pass
    return t_out, q_out


def _extract_region_minmax_series(log_text: str, region: str) -> tuple[list[float], list[float], list[float]]:
    re_time = re.compile(r"^\s*Time\s*=\s*([0-9eE+\-\.]+)\s*$")
    re_region = re.compile(rf"Solving for solid region\s+{re.escape(region)}\s*$")
    re_minmax = re.compile(r"Min/max T:([0-9eE+\-\.]+)\s+([0-9eE+\-\.]+)")
    cur_t = None
    times: list[float] = []
    t_min: list[float] = []
    t_max: list[float] = []
    lines = log_text.splitlines()
    i = 0
    while i < len(lines):
        m = re_time.match(lines[i])
        if m:
            try:
                cur_t = float(m.group(1))
            except ValueError:
                cur_t = None
            i += 1
            continue
        if cur_t is not None and re_region.search(lines[i]):
            for j in range(i + 1, min(i + 6, len(lines))):
                mm = re_minmax.search(lines[j])
                if mm:
                    try:
                        times.append(cur_t)
                        t_min.append(float(mm.group(1)))
                        t_max.append(float(mm.group(2)))
                    except ValueError:
                        pass
                    break
        i += 1
    return times, t_min, t_max


def _extract_volavg_T(postprocess_out: str) -> float:
    m = re.search(r"volAverage\(jellyRoll\)\s+of\s+T\s*=\s*([0-9eE+\-\.]+)", postprocess_out)
    if not m:
        raise RuntimeError("Failed to parse volAverage(jellyRoll) of T from postProcess output")
    return float(m.group(1))


def _read_sample_raw(path: Path) -> tuple[list[float], list[float], list[float]]:
    ys: list[float] = []
    zs: list[float] = []
    vals: list[float] = []
    with path.open("r", errors="ignore") as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                # x, y, z, value
                y = float(parts[1])
                z = float(parts[2])
                v = float(parts[3])
            except ValueError:
                continue
            ys.append(y)
            zs.append(z)
            vals.append(v)
    if not ys:
        raise RuntimeError(f"No data parsed from raw file: {path}")
    return ys, zs, vals


def _plot_raw_plane(raw_path: Path, out_path: Path, *, title: str) -> None:
    ys, zs, vals = _read_sample_raw(raw_path)
    plt.figure(figsize=(6.4, 5.2), dpi=160)
    sc = plt.scatter(ys, zs, c=vals, s=6, cmap="inferno")
    plt.xlabel("y [m]")
    plt.ylabel("z [m]")
    plt.title(title)
    plt.gca().set_aspect("equal", adjustable="box")
    cbar = plt.colorbar(sc)
    cbar.set_label("T [K]")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _read_set_raw(path: Path) -> tuple[list[float], list[float]]:
    zs: list[float] = []
    vals: list[float] = []
    with path.open("r", errors="ignore") as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                if len(parts) >= 4:
                    z = float(parts[2])
                    v = float(parts[3])
                else:
                    z = float(parts[0])
                    v = float(parts[1])
            except ValueError:
                continue
            zs.append(z)
            vals.append(v)
    if not zs:
        raise RuntimeError(f"No data parsed from raw set file: {path}")
    return zs, vals


def _plot_axis_line(raw_path: Path, out_path: Path, *, title: str) -> None:
    zs, vals = _read_set_raw(raw_path)
    plt.figure(figsize=(6.4, 4.0), dpi=160)
    plt.plot(zs, vals, lw=1.6)
    plt.grid(True, alpha=0.3)
    plt.xlabel("z [m]")
    plt.ylabel("T [K]")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _plot_axis_lines(series: list[tuple[str, list[float], list[float]]], out_path: Path, *, title: str) -> None:
    if not series:
        raise RuntimeError("No axis line series to plot")
    plt.figure(figsize=(6.6, 4.2), dpi=160)
    for name, zs, vals in series:
        plt.plot(zs, vals, lw=1.6, label=name)
    plt.grid(True, alpha=0.3)
    plt.xlabel("z [m]")
    plt.ylabel("T [K]")
    plt.title(title)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _read_surface_field_value(path: Path) -> tuple[list[float], list[float]]:
    ts: list[float] = []
    vals: list[float] = []
    with path.open("r", errors="ignore") as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                t = float(parts[0])
                v = float(parts[1])
            except ValueError:
                continue
            ts.append(t)
            vals.append(v)
    if not ts:
        raise RuntimeError(f"No data parsed from surfaceFieldValue file: {path}")
    return ts, vals


def _plot_interface_temperatures(
    series: list[tuple[str, list[float], list[float]]], out_path: Path, *, title: str
) -> None:
    if not series:
        raise RuntimeError("No interface temperature series to plot")
    plt.figure(figsize=(6.8, 4.2), dpi=160)
    for name, ts, vals in series:
        plt.plot(ts, vals, lw=1.6, label=name)
    plt.grid(True, alpha=0.3)
    plt.xlabel("time [s]")
    plt.ylabel("T [K]")
    plt.title(title)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _stats(values: Iterable[float]) -> dict[str, float]:
    vals = list(values)
    if not vals:
        return {"count": 0, "min": float("nan"), "max": float("nan"), "mean": float("nan")}
    return {
        "count": float(len(vals)),
        "min": float(min(vals)),
        "max": float(max(vals)),
        "mean": float(sum(vals) / len(vals)),
    }



def _find_pvpython() -> Path | None:
    for candidate in (
        Path("/workspace/.conda/envs/pv/bin/pvpython"),
        Path("/workspace/.conda_paraview/bin/pvpython"),
        Path(os.environ.get("PVPYTHON", "")),
    ):
        if candidate and candidate.exists():
            return candidate
    for p in os.environ.get("PATH", "").split(os.pathsep):
        cand = Path(p) / "pvpython"
        if cand.exists():
            return cand
    return None


def _write_pvpython_script(script_path: Path) -> None:
    script_path.write_text(
        """#!/usr/bin/env python3
import argparse
from pathlib import Path
from paraview.simple import OpenFOAMReader, Slice, Delete
from paraview import servermanager
import vtk

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--field", required=True)
    ap.add_argument("--time", required=True)
    ap.add_argument("--slice-count", type=int, default=5)
    ap.add_argument(
        "--skip-pvpython",
        action="store_true",
        help="Skip pvpython slice rendering; use raw axial slice instead.",
    )
    ap.add_argument("--normal", default="z")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--prefix", required=True)
    args = ap.parse_args()

    case_dir = Path(args.case)
    foam_path = case_dir / "foam.foam"
    if not foam_path.exists():
        foam_path.write_text("")

    reader = OpenFOAMReader(FileName=str(foam_path))
    region_name = args.region
    if "/" not in region_name:
        region_name = f"/{region_name}/internalMesh"
    reader.MeshRegions = [region_name]
    reader.CellArrays = [args.field]
    time_val = float(args.time)
    reader.UpdatePipeline(time_val)

    bounds = reader.GetDataInformation().GetBounds()
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    if zmax <= zmin:
        raise RuntimeError("Invalid bounds for slicing")

    center = [(xmin + xmax) * 0.5, (ymin + ymax) * 0.5, (zmin + zmax) * 0.5]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    normal = args.normal.lower()
    for i in range(args.slice_count):
        frac = (i + 1) / (args.slice_count + 1)
        if normal == "x":
            pos = xmin + frac * (xmax - xmin)
            origin = [pos, center[1], center[2]]
            nvec = [1, 0, 0]
        elif normal == "y":
            pos = ymin + frac * (ymax - ymin)
            origin = [center[0], pos, center[2]]
            nvec = [0, 1, 0]
        else:
            pos = zmin + frac * (zmax - zmin)
            origin = [center[0], center[1], pos]
            nvec = [0, 0, 1]

        slc = Slice(Input=reader)
        slc.SliceType = "Plane"
        slc.SliceType.Origin = origin
        slc.SliceType.Normal = nvec
        slc.UpdatePipeline(time_val)

        poly = servermanager.Fetch(slc)
        if poly is None:
            raise RuntimeError("Slice fetch returned None (no data to render)")

        if isinstance(poly, vtk.vtkMultiBlockDataSet):
            it = poly.NewIterator()
            it.InitTraversal()
            found = None
            while not it.IsDoneWithTraversal():
                data = it.GetCurrentDataObject()
                if data and data.GetCellData() and data.GetCellData().HasArray(args.field):
                    found = data
                    break
                it.GoToNextItem()
            del it
            if found is None:
                raise RuntimeError("No slice block with target field found in multiblock data")
            poly = found
        Delete(slc)

        c2p = vtk.vtkCellDataToPointData()
        c2p.SetInputData(poly)
        c2p.PassCellDataOn()
        c2p.Update()
        poly = c2p.GetOutput()

        bounds = poly.GetBounds()
        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        nx = 400
        ny = 400
        image = vtk.vtkImageData()
        image.SetDimensions(nx, ny, 1)
        image.SetSpacing((xmax - xmin) / (nx - 1), (ymax - ymin) / (ny - 1), 1.0)
        image.SetOrigin(xmin, ymin, 0.0)

        probe = vtk.vtkProbeFilter()
        probe.SetInputData(image)
        probe.SetSourceData(poly)
        probe.Update()

        out = probe.GetOutput()
        arr = out.GetPointData().GetArray(args.field)
        if arr is None:
            raise RuntimeError(f"Field not found in slice output: {args.field}")
        rng = arr.GetRange()

        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(256)
        lut.SetRange(rng)
        lut.Build()

        map_colors = vtk.vtkImageMapToColors()
        map_colors.SetInputData(out)
        map_colors.SetLookupTable(lut)
        map_colors.Update()

        out_path = out_dir / f"{args.prefix}_T_slice_{normal}{i+1}.png"
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(out_path))
        writer.SetInputData(map_colors.GetOutput())
        writer.Write()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""
    )


def _render_pyvista_matplotlib_slices(
    *,
    case_dir: Path,
    region: str,
    field: str,
    section_time: str,
    plots_dir: Path,
    prefix: str,
    normal: str,
    slice_count: int,
) -> list[Path]:
    script = Path("tools/render_slices_pyvista.py").resolve()
    _run(
        [
            "python3",
            str(script),
            "--case",
            str(case_dir),
            "--region",
            region,
            "--field",
            field,
            "--time",
            str(section_time),
            "--out-dir",
            str(plots_dir),
            "--prefix",
            prefix,
            "--normal",
            normal,
            "--slice-count",
            str(slice_count),
        ],
        cwd=case_dir,
    )
    return [plots_dir / f"{prefix}_{field}_slice_{normal}{i+1}.png" for i in range(slice_count)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="cases/lumped", help="Case directory (default: cases/lumped)")
    ap.add_argument("--log", default="", help="Solver log file (default: latest artifacts/logs/lumped_run_*.log)")
    ap.add_argument("--section-time", default="100", help="Time for section plot (default: 100)")
    ap.add_argument("--report-prefix", default="", help="Report file prefix (default: case directory name)")
    ap.add_argument(
        "--table-step",
        type=int,
        default=10,
        help="Sample table every N timesteps (default: 10)",
    )
    ap.add_argument(
        "--slice-count",
        type=int,
        default=5,
        help="Number of axial slices to render with pvpython (default: 5)",
    )
    ap.add_argument(
        "--skip-pvpython",
        action="store_true",
        help="Skip pvpython slice rendering; use raw axial slice instead.",
    )
    args = ap.parse_args()

    case_dir = Path(args.case).resolve()
    if not case_dir.exists():
        raise SystemExit(f"Case directory not found: {case_dir}")

    logs_dir = (case_dir / ".." / ".." / "artifacts" / "logs").resolve()
    if not logs_dir.exists():
        logs_dir = Path("artifacts/logs").resolve()

    if args.log:
        log_path = Path(args.log).resolve()
    else:
        candidates = sorted(logs_dir.glob("lumped_run_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise SystemExit(f"No run logs found under: {logs_dir}")
        log_path = candidates[0]

    log_text = log_path.read_text(errors="ignore")

    case_tag = args.report_prefix.strip() or case_dir.name

    control_info = _parse_control_dict(case_dir / "system" / "controlDict")
    application = control_info.get("application", "unknown")
    start_time = control_info.get("startTime", "unknown")
    end_time = control_info.get("endTime", "unknown")
    delta_t = control_info.get("deltaT", "unknown")
    write_control = control_info.get("writeControl", "unknown")
    write_interval = control_info.get("writeInterval", "unknown")

    region_info = _parse_region_properties(case_dir / "constant" / "regionProperties")
    coupler_info = _parse_coupler_config(case_dir / "system" / "controlDict")

    stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")
    plots_dir = Path("artifacts/plots").resolve()
    reports_dir = Path("artifacts/reports").resolve()
    plots_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Q_sum_check from solver log
    t_q, qsum = _extract_qsum_series(log_text)
    q_stats = _stats(qsum)
    q_nonzero = sum(1 for v in qsum if abs(v) > 0)

    # Region-average T(jellyRoll) at written times
    times = _numeric_time_dirs(case_dir)
    # Keep only times that contain jellyRoll/T (ie actual solver writes, not functionObject-only dirs).
    write_times = [t for t in times if (case_dir / t / "jellyRoll" / "T").exists()]

    t_T: list[float] = []
    Tavg: list[float] = []
    for t in write_times:
        out = _run(
            ["postProcess", "-case", str(case_dir), "-region", "jellyRoll", "-time", t, "-func", "volFieldValue"],
            cwd=case_dir,
        )
        t_T.append(float(t))
        Tavg.append(_extract_volavg_T(out))

    T_stats = _stats(Tavg)
    t_region, Tmin_region, Tmax_region = _extract_region_minmax_series(log_text, "jellyRoll")
    Tmax_stats = _stats(Tmax_region)

    # Generate axial slice (normal to x) using raw sampling or pvpython.
    section_time = str(write_times[-1]) if write_times else args.section_time
    slice_images: list[Path] = []
    axial_image: Path | None = None
    axis_line_image: Path | None = None
    interface_image: Path | None = None
    if args.skip_pvpython:
        try:
            _run(
                [
                    "postProcess",
                    "-case",
                    str(case_dir),
                    "-region",
                    "jellyRoll",
                    "-time",
                    str(section_time),
                    "-func",
                    "samplePlanes",
                ],
                cwd=case_dir,
            )
            raw_path = case_dir / "postProcessing" / "samplePlanes" / str(section_time) / "T_plane_x0.raw"
            axial_image = plots_dir / f"{case_tag}_t{section_time}_T_plane_x0_raw.png"
            _plot_raw_plane(raw_path, axial_image, title=f"T slice (x=0) t={section_time}s")
        except RuntimeError as exc:
            print(f"WARNING: raw axial slice generation failed: {exc}")
    else:
        if args.slice_count > 0:
            pvpython = _find_pvpython()
            slice_prefix = f"{case_tag}_t{section_time}"
            rendered_with_pvpython = False
            if pvpython:
                pv_script = Path("tools/_pv_slices_tmp.py").resolve()
                _write_pvpython_script(pv_script)
                os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
                os.environ.setdefault("VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN", "1")
                try:
                    _run(
                        [
                            str(pvpython),
                            "--force-offscreen-rendering",
                            str(pv_script),
                            "--case",
                            str(case_dir),
                            "--region",
                            "jellyRoll",
                            "--field",
                            "T",
                            "--slice-count",
                            str(args.slice_count),
                            "--time",
                            str(section_time),
                            "--out-dir",
                            str(plots_dir),
                            "--prefix",
                            slice_prefix,
                            "--normal",
                            "z",
                        ],
                        cwd=case_dir,
                    )
                    slice_images = [
                        plots_dir / f"{slice_prefix}_T_slice_z{i+1}.png"
                        for i in range(args.slice_count)
                    ]
                    _run(
                        [
                            str(pvpython),
                            "--force-offscreen-rendering",
                            str(pv_script),
                            "--case",
                            str(case_dir),
                            "--region",
                            "jellyRoll",
                            "--field",
                            "T",
                            "--slice-count",
                            "1",
                            "--time",
                            str(section_time),
                            "--out-dir",
                            str(plots_dir),
                            "--prefix",
                            f"{slice_prefix}_x0",
                            "--normal",
                            "x",
                        ],
                        cwd=case_dir,
                    )
                    axial_image = plots_dir / f"{slice_prefix}_x0_T_slice_x1.png"
                    rendered_with_pvpython = True
                except RuntimeError as exc:
                    print(f"WARNING: pvpython slice rendering failed: {exc}")
            if not rendered_with_pvpython:
                try:
                    slice_images = _render_pyvista_matplotlib_slices(
                        case_dir=case_dir,
                        region="jellyRoll",
                        field="T",
                        section_time=str(section_time),
                        plots_dir=plots_dir,
                        prefix=slice_prefix,
                        normal="z",
                        slice_count=args.slice_count,
                    )
                    axial_image = _render_pyvista_matplotlib_slices(
                        case_dir=case_dir,
                        region="jellyRoll",
                        field="T",
                        section_time=str(section_time),
                        plots_dir=plots_dir,
                        prefix=f"{slice_prefix}_x0",
                        normal="x",
                        slice_count=1,
                    )[0]
                except RuntimeError as exc:
                    print(f"WARNING: pyvista slice rendering failed: {exc}")

    # Generate axis line (0 0 1) temperature plot using raw set sampling.
    try:
        line_series: list[tuple[str, list[float], list[float]]] = []
        region_names: list[str] = []
        for names in region_info.values():
            region_names.extend(names)
        if not region_names:
            region_names = ["jellyRoll", "shell", "cap"]
        for region in region_names:
            _run(
                [
                    "postProcess",
                    "-case",
                    str(case_dir),
                    "-region",
                    region,
                    "-time",
                    str(section_time),
                    "-func",
                    "sampleLine",
                ],
                cwd=case_dir,
            )
            line_raw = (
                case_dir
                / "postProcessing"
                / "sampleLine"
                / region
                / str(section_time)
                / "axisLine_T.xy"
            )
            zs, vals = _read_set_raw(line_raw)
            line_series.append((region, zs, vals))
        axis_line_image = plots_dir / f"{case_tag}_t{section_time}_axisLine_T.png"
        _plot_axis_lines(line_series, axis_line_image, title=f"T along axis (0 0 1) t={section_time}s")
    except RuntimeError as exc:
        print(f"WARNING: axis line sampling failed: {exc}")

    # Plot interface temperature diagnostics from surfaceFieldValue.
    try:
        interface_series: list[tuple[str, list[float], list[float]]] = []
        interface_paths = [
            (
                "jellyRoll_to_shell",
                case_dir
                / "postProcessing"
                / "jellyRoll"
                / "interfaceT_jellyRoll_to_shell"
                / "0"
                / "surfaceFieldValue.dat",
            ),
            (
                "shell_to_jellyRoll",
                case_dir
                / "postProcessing"
                / "shell"
                / "interfaceT_shell_to_jellyRoll"
                / "0"
                / "surfaceFieldValue.dat",
            ),
            (
                "jellyRoll_to_cap",
                case_dir
                / "postProcessing"
                / "jellyRoll"
                / "interfaceT_jellyRoll_to_cap"
                / "0"
                / "surfaceFieldValue.dat",
            ),
            (
                "cap_to_jellyRoll",
                case_dir
                / "postProcessing"
                / "cap"
                / "interfaceT_cap_to_jellyRoll"
                / "0"
                / "surfaceFieldValue.dat",
            ),
        ]
        for name, path in interface_paths:
            if path.exists():
                ts, vals = _read_surface_field_value(path)
                interface_series.append((name, ts, vals))
        if interface_series:
            interface_image = plots_dir / f"{case_tag}_interface_T.png"
            _plot_interface_temperatures(
                interface_series, interface_image, title="Interface T (areaAverage)"
            )
    except RuntimeError as exc:
        print(f"WARNING: interface temperature plotting failed: {exc}")

    # Plot: dense log-derived jellyRoll Tmax
    p_tmax = plots_dir / f"{case_tag}_Tmax_jellyRoll_{stamp}.png"
    plt.figure(figsize=(7.2, 3.6), dpi=160)
    if t_region and Tmax_region:
        plt.plot(t_region, Tmax_region, lw=1.4)
    plt.grid(True, alpha=0.3)
    plt.xlabel("time [s]")
    plt.ylabel("max T (jellyRoll) [K]")
    plt.tight_layout()
    plt.savefig(p_tmax)
    plt.close()

    # Plot: Q_sum_check
    p_qsum = plots_dir / f"{case_tag}_Q_sum_check_{stamp}.png"
    plt.figure(figsize=(7.2, 3.6), dpi=160)
    if t_q and qsum:
        plt.plot(t_q, qsum, lw=1.4)
    plt.grid(True, alpha=0.3)
    plt.xlabel("time [s]")
    plt.ylabel("Q_sum_check [W]")
    plt.tight_layout()
    plt.savefig(p_qsum)
    plt.close()

    # Axial slice images are generated via pvpython

    # Sample table (every N timesteps)
    delta_t_val = None
    try:
        delta_t_val = float(delta_t)
    except ValueError:
        delta_t_val = None
    table_step = max(1, args.table_step)
    tavg_map = {t: v for t, v in zip(t_T, Tavg)}
    table_rows: list[str] = []
    for t_val, q_val in zip(t_q, qsum):
        if delta_t_val:
            step_idx = int(round(t_val / delta_t_val))
            if step_idx % table_step != 0:
                continue
        else:
            if int(round(t_val)) % table_step != 0:
                continue
        tavg_val = tavg_map.get(t_val)
        tavg_str = f"{tavg_val:.6f}" if tavg_val is not None else "NA"
        table_rows.append(f"{t_val:.3f}, {q_val:.6f}, {tavg_str}")

    table_csv = plots_dir / f"{case_tag}_table_{stamp}.csv"
    table_csv.write_text("time_s,Q_sum_check_W,Tavg_jellyRoll_K\n" + "\n".join(table_rows) + "\n")
    table_data = [["time_s", "Q_sum_check_W", "Tavg_jellyRoll_K"]]
    for row in table_rows:
        parts = [p.strip() for p in row.split(",")]
        table_data.append(parts)

    # Report text
    report_txt = reports_dir / f"{case_tag}_ecm_run_report_{stamp}.txt"
    report_pdf = reports_dir / f"{case_tag}_ecm_run_report_{stamp}.pdf"

    now_iso = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    time_samples = len(t_q)
    time_min = min(t_q) if t_q else float("nan")
    time_max = max(t_q) if t_q else float("nan")
    stack_traces = _count_occurrences(log_text, [r"readOutput stack trace"])
    missing_outputs = _count_occurrences(log_text, [r"Missing output file"])
    missing_summary = "none" if missing_outputs == 0 else str(missing_outputs)

    last_write_time = write_times[-1] if write_times else section_time

    ecm_in = case_dir / "ecm" / "ecm_in.bin"
    ecm_out = case_dir / "ecm" / "ecm_out.bin"
    ecm_in_size = ecm_in.stat().st_size if ecm_in.exists() else 0
    ecm_out_size = ecm_out.stat().st_size if ecm_out.exists() else 0

    axial_entry = str(axial_image) if axial_image else "skipped"
    axis_line_entry = str(axis_line_image) if axis_line_image else "skipped"
    interface_entry = str(interface_image) if interface_image else "skipped"
    z_count = len(slice_images)
    z_entries = "\n".join(f"- {p}" for p in slice_images) if slice_images else "- (none)"

    summary = (
        f"{case_tag} ECM Run Report ({start_time}-{end_time} s)\n"
        f"Date (UTC): {now_iso}\n\n"
        "Case\n"
        f"- Path: {case_dir}\n"
        f"- Log: {log_path}\n"
        f"- Application: {application}\n"
        f"- startTime: {start_time}, endTime: {end_time}, deltaT: {delta_t}\n\n"
        "Regions\n"
        + "\n".join(
            f"- {k} ({' '.join(v)})" for k, v in region_info.items()
        )
        + "\n\n"
        "Coupling\n"
        + "\n".join(f"- {k}: {v}" for k, v in coupler_info.items())
        + "\n\n"
        "Run Summary\n"
        f"- Time samples: {time_samples} (min {time_min}, max {time_max})\n"
        f"- readOutput stack traces: {stack_traces}\n"
        f"- Missing output recoveries: {missing_summary}\n"
        f"- Q_sum_check: count {int(q_stats['count'])}, min {q_stats['min']:.6f}, max {q_stats['max']:.6f}, mean {q_stats['mean']:.6f}, nonzero {q_nonzero}\n\n"
        f"Axial slice (normal to x) t={section_time}\n"
        f"- {axial_entry}\n\n"
        f"Axis line (0 0 1) t={section_time}\n"
        f"- {axis_line_entry}\n\n"
        "Interface temperatures (areaAverage)\n"
        f"- {interface_entry}\n\n"
        f"Axial slices (normal to z) t={section_time}\n"
        f"- count: {z_count}\n"
        + z_entries
        + "\n\n"
        "Sample Table (every N timesteps)\n"
        f"- tableStep: {table_step}\n"
        f"- CSV: {table_csv}\n"
        "time_s, Q_sum_check_W, Tavg_jellyRoll_K\n"
        + "\n".join(table_rows)
        + "\n\n"
        "ECM I/O Files\n"
        f"- ecm/ecm_in.bin: {ecm_in_size}\n"
        f"- ecm/ecm_out.bin: {ecm_out_size}\n"
    )
    report_txt.write_text(summary)

    # PDF
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(report_pdf), pagesize=A4, title=f"{case_tag} ECM Run Report")
    story = []
    story.append(Paragraph(f"{case_tag} ECM Run Report", styles["Title"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Generated (UTC): {now_iso}", styles["Normal"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Case: {case_dir}", styles["Normal"]))
    story.append(Paragraph(f"Solver log: {log_path}", styles["Normal"]))
    story.append(Paragraph(f"Application: {application}", styles["Normal"]))
    story.append(Paragraph(f"startTime={start_time}, endTime={end_time}, deltaT={delta_t}", styles["Normal"]))
    story.append(Paragraph(f"writeControl={write_control}, writeInterval={write_interval}", styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Regions:", styles["Normal"]))
    for k, v in region_info.items():
        story.append(Paragraph(f"- {k} ({' '.join(v)})", styles["Normal"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Coupling:", styles["Normal"]))
    for k, v in coupler_info.items():
        story.append(Paragraph(f"- {k}: {v}", styles["Normal"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Time samples: {time_samples} (min {time_min}, max {time_max})", styles["Normal"]))
    story.append(Paragraph(f"Q_sum_check: min={q_stats['min']:.3f} W, max={q_stats['max']:.3f} W, mean={q_stats['mean']:.3f} W, nonzero={q_nonzero}", styles["Normal"]))
    story.append(Paragraph(f"Tavg(jellyRoll): min={T_stats['min']:.6f} K, max={T_stats['max']:.6f} K, mean={T_stats['mean']:.6f} K", styles["Normal"]))
    story.append(Paragraph(f"Tmax(jellyRoll, from log): min={Tmax_stats['min']:.6f} K, max={Tmax_stats['max']:.6f} K, mean={Tmax_stats['mean']:.6f} K", styles["Normal"]))
    story.append(Paragraph(f"ECM I/O sizes: in={ecm_in_size} B, out={ecm_out_size} B", styles["Normal"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Sample Table (every {table_step} timesteps):", styles["Normal"]))
    if len(table_data) > 1:
        table = Table(table_data, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), "#E6E6E6"),
                    ("GRID", (0, 0), (-1, -1), 0.5, "#666666"),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ]
            )
        )
        story.append(table)
    story.append(Spacer(1, 10))
    story.append(Image(str(p_tmax), width=520, height=260))
    story.append(Spacer(1, 8))
    story.append(Image(str(p_qsum), width=520, height=260))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Axial slice (normal to x, t={section_time} s):", styles["Normal"]))
    if axial_image and axial_image.exists():
        story.append(Image(str(axial_image), width=420, height=320))
        story.append(Spacer(1, 8))
    story.append(Paragraph(f"Axis line (0 0 1, t={section_time} s):", styles["Normal"]))
    if axis_line_image and axis_line_image.exists():
        story.append(Image(str(axis_line_image), width=420, height=260))
        story.append(Spacer(1, 8))
    story.append(Paragraph("Interface temperatures (areaAverage):", styles["Normal"]))
    if interface_image and interface_image.exists():
        story.append(Image(str(interface_image), width=420, height=260))
        story.append(Spacer(1, 8))
    story.append(Paragraph(f"Axial slices (normal to z, t={section_time} s):", styles["Normal"]))
    for img in slice_images:
        if img.exists():
            story.append(Image(str(img), width=420, height=320))
            story.append(Spacer(1, 6))

    doc.build(story)

    print(str(report_pdf))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
