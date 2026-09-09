#!/usr/bin/env python3
"""
Machine extraction of critical TBM fields for audit and regression use.

Correctly distinguishes Detailed Builder (DB) vs Simple Builder (SB) sections,
and enumerates m_bOnly1D per SIMMOD in document order.

Public API:
    extract_tbm_fields(path) -> TbmFields
    extract_rct3d_capacity(path) -> dict

All values are returned as strings (exactly as they appear in the file, stripped
of whitespace and inline comments).  Callers that need floats should cast with
float().
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BuilderFields:
    """Fields from one <BUILDER> block (Detailed or Simple)."""
    builder_type: str           # 'Detailed Builder' | 'Simple Builder'
    offset_pos_avg: Optional[str] = None
    mandrel_width: Optional[str] = None
    electrode_overlap_at_start: Optional[str] = None


@dataclass
class TbmFields:
    detailed_builder: BuilderFields
    simple_builder: BuilderFields
    m_bonly1d_list: list          # values in SIMMOD document order, as strings
    rct3d_capacity: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _read_lines(path: Path) -> list[str]:
    raw = path.read_bytes()
    return raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').decode('utf-8', errors='replace').splitlines()


_FIELD_RE = re.compile(r'^(\S.*?)\s*=\s*([^\t!]+)', re.MULTILINE)


def _parse_field_value(line: str) -> Optional[str]:
    """Return the value from a 'fieldname = value  ! comment' line, or None."""
    m = re.match(r'^[^\t!]+\s*=\s*([^\t!]+)', line.strip())
    if m:
        return m.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Section splitter
# ---------------------------------------------------------------------------

def _split_sections(lines: list[str]) -> dict[str, list[tuple[int, str]]]:
    """
    Return a dict keyed by section name → list of (1-based lineno, content_line).

    Top-level sections are delimited by <TAG> / </TAG> markers.
    Recognised tags: BUILDER, SIMMOD, DEFAULT BUILDER
    """
    sections: dict[str, list] = {}
    current_tag: Optional[str] = None
    current_buf: list[tuple[int, str]] = []
    counts: dict[str, int] = {}

    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        open_m = re.match(r'^<([A-Z][A-Z0-9 ]*)>$', stripped)
        close_m = re.match(r'^</([A-Z][A-Z0-9 ]*)>$', stripped)

        if open_m:
            current_tag = open_m.group(1)
            current_buf = []
        elif close_m and current_tag == close_m.group(1):
            tag = current_tag
            counts[tag] = counts.get(tag, 0) + 1
            key = f'{tag}[{counts[tag]}]'
            sections[key] = current_buf
            current_tag = None
            current_buf = []
        elif current_tag is not None:
            current_buf.append((i, stripped))

    return sections


# ---------------------------------------------------------------------------
# BUILDER extraction
# ---------------------------------------------------------------------------

_BUILDER_HEADER_RE = re.compile(r'^(Detailed Builder|Simple Builder)$', re.IGNORECASE)


def _extract_builder(buf: list[tuple[int, str]]) -> BuilderFields:
    """Parse one BUILDER section buffer into a BuilderFields."""
    btype = None
    for _, line in buf:
        if _BUILDER_HEADER_RE.match(line):
            btype = line
            break

    if btype is None:
        raise ValueError('Could not identify builder type (Detailed/Simple)')

    bf = BuilderFields(builder_type=btype)

    for _, line in buf:
        stripped = line.strip()
        # m_dOffsetPosAvg appears in both DB and SB without _mm suffix
        if re.match(r'm_dOffsetPosAvg\s*=', stripped):
            bf.offset_pos_avg = _parse_field_value(stripped)
        # DB uses m_dMandrelWidth_mm; SB uses m_dMandrelWidth (no _mm)
        elif re.match(r'm_dMandrelWidth(?:_mm)?\s*=', stripped):
            bf.mandrel_width = _parse_field_value(stripped)
        # DB: m_dElectrodeOverlapAtStart_mm; SB: m_dElectrodeOverlapAtStart
        elif re.match(r'm_dElectrodeOverlapAtStart(?:_mm)?\s*=', stripped):
            bf.electrode_overlap_at_start = _parse_field_value(stripped)

    return bf


# ---------------------------------------------------------------------------
# SIMMOD m_bOnly1D extraction
# ---------------------------------------------------------------------------

def _extract_m_bonly1d(buf: list[tuple[int, str]]) -> Optional[str]:
    for _, line in buf:
        if re.match(r'm_bOnly1D\s*=', line.strip()):
            return _parse_field_value(line)
    return None


# ---------------------------------------------------------------------------
# RCRTable 3D capacity fields
# ---------------------------------------------------------------------------

_RCT3D_FIELDS = ('m_bSpecifyCapacity', 'm_dAhCell')


def _extract_rct3d_from_buf(buf: list[tuple[int, str]]) -> Optional[dict]:
    """If buf belongs to an 'RCRTable 3D' SIMMOD, return its capacity fields."""
    # First two content lines after <SIMMOD>: section name, model family
    headers = [line for _, line in buf if line and not line.startswith('!')][:2]
    if not any('RCRTable 3D' in h for h in headers):
        return None
    result = {}
    for _, line in buf:
        for field_name in _RCT3D_FIELDS:
            if re.match(rf'{re.escape(field_name)}\s*=', line.strip()):
                result[field_name] = _parse_field_value(line)
    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_tbm_fields(path: Path) -> TbmFields:
    """Extract all critical audit fields from a TBM file."""
    path = Path(path)
    lines = _read_lines(path)
    sections = _split_sections(lines)

    # --- BUILDER sections ---
    builder_sections = {k: v for k, v in sections.items() if k.startswith('BUILDER[')}
    sorted_builders = sorted(builder_sections.items(), key=lambda kv: int(kv[0].split('[')[1].rstrip(']')))

    if len(sorted_builders) < 2:
        raise ValueError(f'{path}: expected at least 2 BUILDER sections, found {len(sorted_builders)}')

    detailed_builder: Optional[BuilderFields] = None
    simple_builder: Optional[BuilderFields] = None

    for _key, buf in sorted_builders:
        bf = _extract_builder(buf)
        if 'Detailed' in bf.builder_type and detailed_builder is None:
            detailed_builder = bf
        elif 'Simple' in bf.builder_type and simple_builder is None:
            simple_builder = bf
        if detailed_builder and simple_builder:
            break

    if detailed_builder is None:
        raise ValueError(f'{path}: Detailed Builder not found')
    if simple_builder is None:
        raise ValueError(f'{path}: Simple Builder not found')

    # --- SIMMOD m_bOnly1D ---
    simmod_sections = {k: v for k, v in sections.items() if k.startswith('SIMMOD[')}
    sorted_simmods = sorted(simmod_sections.items(), key=lambda kv: int(kv[0].split('[')[1].rstrip(']')))

    bonly1d_list = []
    rct3d_cap: dict = {}
    for _key, buf in sorted_simmods:
        val = _extract_m_bonly1d(buf)
        if val is not None:
            bonly1d_list.append(val)
        cap = _extract_rct3d_from_buf(buf)
        if cap is not None:
            rct3d_cap = cap

    return TbmFields(
        detailed_builder=detailed_builder,
        simple_builder=simple_builder,
        m_bonly1d_list=bonly1d_list,
        rct3d_capacity=rct3d_cap,
    )


if __name__ == '__main__':
    import sys, json
    for p in sys.argv[1:]:
        f = extract_tbm_fields(Path(p))
        print(f'\n=== {p} ===')
        print(f'  DB  m_dOffsetPosAvg              = {f.detailed_builder.offset_pos_avg}')
        print(f'  SB  m_dOffsetPosAvg              = {f.simple_builder.offset_pos_avg}')
        print(f'  DB  m_dMandrelWidth              = {f.detailed_builder.mandrel_width}')
        print(f'  SB  m_dMandrelWidth              = {f.simple_builder.mandrel_width}')
        print(f'  DB  m_dElectrodeOverlapAtStart   = {f.detailed_builder.electrode_overlap_at_start}')
        print(f'  SB  m_dElectrodeOverlapAtStart   = {f.simple_builder.electrode_overlap_at_start}')
        print(f'  m_bOnly1D (per SIMMOD)           = {f.m_bonly1d_list}')
        print(f'  RCRTable 3D capacity             = {f.rct3d_capacity}')
