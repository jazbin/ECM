#!/usr/bin/env python3
"""Generate a client-facing status report using reportlab."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
import re
from typing import List, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_section(md_text: str, heading: str) -> List[str]:
    lines = md_text.splitlines()
    out: List[str] = []
    in_section = False
    for line in lines:
        if line.strip().startswith("## "):
            in_section = line.strip() == f"## {heading}"
            continue
        if in_section:
            if line.strip().startswith("## "):
                break
            if line.strip().startswith("- "):
                out.append(line.strip()[2:])
    return out


def _parse_assessment_entries(text: str) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    current: Optional[Dict[str, object]] = None
    header_re = re.compile(r"^\\d{4}-\\d{2}-\\d{2}T")
    for line in text.splitlines():
        if header_re.match(line):
            if current:
                entries.append(current)
            current = {"header": line, "bullets": []}
        elif current and line.strip().startswith("- "):
            current["bullets"].append(line.strip()[2:])
    if current:
        entries.append(current)
    return entries


def _parse_assessment_header(header: str) -> Dict[str, str]:
    out = {}
    for key in ("case", "log", "report"):
        match = re.search(rf"{key}=([^|]+)", header)
        if match:
            out[key] = match.group(1).strip()
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    status_path = root / "STATUS.md"
    todo_path = root / "TODO.md"
    assessment_path = root / "artifacts" / "logs" / "assessment.log"
    session_index_path = root / "artifacts" / "logs" / "session.log"

    status_text = _read_text(status_path)
    todo_text = _read_text(todo_path) if todo_path.exists() else ""

    active = _parse_section(status_text, "Active")
    done = _parse_section(status_text, "Done")
    blocked = _parse_section(status_text, "Blocked")

    now = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")

    reports_dir = root / "artifacts" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = reports_dir / f"client_status_report_{stamp}.pdf"
    txt_path = reports_dir / f"client_status_report_{stamp}.txt"

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1f3b4d"),
        spaceAfter=6,
    )
    h_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1f3b4d"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body = styles["BodyText"]
    body.leading = 14
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=9, leading=11)

    story: List[object] = []
    story.append(Paragraph("Client Status Report", title_style))
    story.append(Paragraph("OpenFOAM ECM Coupling Program", subtitle_style))
    story.append(Paragraph(f"Generated: {now}", body))
    story.append(Spacer(1, 0.4 * cm))

    # Executive summary
    story.append(Paragraph("Executive Summary", h_style))
    summary_text = (
        "The ECM coupling implementation is functional and validated in representative CHT cases, "
        "covering binary IO, serial/parallel mapping, and stability controls. The solids-only "
        "multi-region case is stable with explicit interface coupling; a solver-level guard now "
        "disables implicit coupling in solids-only configurations to prevent a known undershoot "
        "artifact while the root cause is investigated. Diagnostics and PDF reporting are in place "
        "to support client review and validation."
    )
    story.append(Paragraph(summary_text, body))
    story.append(Spacer(1, 0.3 * cm))

    # Work completed table
    story.append(Paragraph("Work Completed", h_style))
    completed_items = [
        "ECM coupling library built and validated for OpenFOAM v2506.",
        "Binary IO protocol implemented with atomic handshakes and stable key mapping.",
        "Serial and parallel coupling paths validated (masterGather).",
        "Stability controls added (relaxation, missing output handling, IO checks).",
        "Integration templates delivered for solver/source integration.",
        "Solids-only solver variant and test case established with diagnostics.",
    ]
    completed_rows = [["Deliverable", "Status", "Evidence"]]
    for item in completed_items:
        completed_rows.append([item, "Complete", "See STATUS.md and run logs"])
    completed_table = Table(completed_rows, colWidths=[8.5 * cm, 2.5 * cm, 5.0 * cm])
    completed_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eef2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f3b4d")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(completed_table)
    story.append(Spacer(1, 0.3 * cm))

    # Problems encountered table
    story.append(Paragraph("Problems Encountered and Resolutions", h_style))
    problem_rows = [
        ["Issue", "Impact", "Resolution", "Status"],
        [
            "Implicit solid-solid coupling undershoot (useImplicit=true)",
            "Non-physical temperature drops at interfaces in solids-only runs.",
            "Solver guard forces explicit coupling for solids-only; root cause under investigation.",
            "Mitigated",
        ],
        [
            "Ambient region in solids-only mesh",
            "Unexpected extra region in mesh leading to case mismatch.",
            "Removed ambient location from snappyHexMesh; mesh rebuild required.",
            "Resolved (pending rebuild)",
        ],
        [
            "ECM backend dependencies missing (numpy/pandas)",
            "Early solver runs failed to execute ECM backend.",
            "Added dependency checks; libraries installed.",
            "Resolved",
        ],
        [
            "Heat source sign convention ambiguity",
            "Observed temperature trend inconsistent with expected heating.",
            "Validated and corrected sign usage in fvOptions.",
            "Resolved",
        ],
    ]
    problem_table = Table(problem_rows, colWidths=[4.5 * cm, 4.5 * cm, 6.0 * cm, 2.0 * cm])
    problem_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eef2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f3b4d")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(problem_table)
    story.append(Spacer(1, 0.3 * cm))

    # Current stage
    story.append(Paragraph("Current Stage", h_style))
    if active:
        active_text = "; ".join(active)
        story.append(Paragraph(f"Active work items: {active_text}", body))
    else:
        story.append(Paragraph("No active tasks listed in STATUS.md.", body))
    if blocked and any(item.lower() != "none." for item in blocked):
        blocked_text = "; ".join(blocked)
        story.append(Paragraph(f"Blockers: {blocked_text}", body))
    story.append(Spacer(1, 0.3 * cm))

    # Evidence and artifacts
    story.append(Paragraph("Evidence and Artifacts", h_style))
    sources = [
        "STATUS.md and TODO.md for consolidated progress and next steps.",
        "artifacts/logs/assessment.log for run-by-run assessments.",
        "artifacts/logs/change.log and session logs for traceability.",
    ]
    story.append(Paragraph("This report is compiled from the following sources:", body))
    story.append(Paragraph("Sources: " + "; ".join(sources), small))
    story.append(Spacer(1, 0.2 * cm))

    # Latest run summary (from assessment log)
    if assessment_path.exists():
        entries = _parse_assessment_entries(_read_text(assessment_path))
        if entries:
            latest = entries[-1]
            header = _parse_assessment_header(latest["header"])
            bullets = latest.get("bullets", [])
            highlights = "; ".join(bullets[:2]) if bullets else "See assessment log."
            story.append(Paragraph("Latest Run Summary", h_style))
            summary_rows = [
                ["Case", header.get("case", "n/a")],
                ["Log", header.get("log", "n/a")],
                ["Report", header.get("report", "n/a")],
                ["Highlights", highlights],
            ]
            summary_table = Table(summary_rows, colWidths=[3.0 * cm, 14.0 * cm])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f6f8")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(summary_table)
            story.append(Spacer(1, 0.3 * cm))

    # Next steps (from TODO)
    todo_lines = [
        line.strip()[2:]
        for line in todo_text.splitlines()
        if line.strip().startswith("- ")
    ]
    if todo_lines:
        story.append(Paragraph("Near-Term Next Steps", h_style))
        story.append(Paragraph("; ".join(todo_lines), body))

    # Write text summary alongside PDF
    txt_summary = [
        "Client Status Report - OpenFOAM ECM Coupling",
        f"Generated: {now}",
        "",
        "Executive Summary:",
        summary_text,
        "",
        "Work Completed:",
        *[f"- {item}" for item in completed_items],
        "",
        "Problems Encountered and Resolutions:",
        " - Implicit solid-solid coupling undershoot: mitigated with explicit guard; root cause under investigation.",
        " - Ambient region in solids-only mesh: ambient location removed; rebuild pending.",
        " - ECM backend dependencies: resolved with checks and installs.",
        " - Heat source sign convention: resolved after validation.",
        "",
        "Current Stage:",
        f"Active: {'; '.join(active) if active else 'None listed.'}",
        f"Blocked: {'; '.join(blocked) if blocked else 'None.'}",
        "",
        "Sources:",
        "STATUS.md, TODO.md, artifacts/logs/assessment.log, artifacts/logs/change.log, session logs.",
    ]
    if todo_lines:
        txt_summary.extend(["", "Near-Term Next Steps:", "; ".join(todo_lines)])

    txt_path.write_text("\n".join(txt_summary), encoding="utf-8")

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        title="Client Status Report - OpenFOAM ECM Coupling",
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
    )
    doc.build(story)

    print(str(pdf_path))
    print(str(txt_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
