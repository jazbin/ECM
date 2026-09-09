#!/usr/bin/env python3
"""Validate TBM MODELMAP selection against available SIMMOD blocks.

This validator is deliberately independent of tools/validate_tbm.py so it can catch
selector mistakes that a field-level validator may miss.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def extract_modelmap(text: str) -> dict[str, str]:
    blocks = re.findall(r"<MODELMAP>(.*?)</MODELMAP>", text, flags=re.DOTALL)
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one MODELMAP block, found {len(blocks)}")
    fields: dict[str, str] = {}
    for raw in blocks[0].splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip().split("\t", 1)[0].strip()
    return fields


def extract_simmods(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for body in re.findall(r"<SIMMOD>(.*?)</SIMMOD>", text, flags=re.DOTALL):
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        if not lines:
            continue
        name = lines[0]
        result.setdefault(name, []).append(body)
    return result


def _field(block: str, name: str) -> str | None:
    m = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*([^\t\r\n!]+)", block)
    return m.group(1).strip() if m else None


def validate_text(
    text: str,
    *,
    expected_iet: str | None = None,
    expected_capacity_ah: float | None = None,
    require_all_only1d_zero: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    try:
        modelmap = extract_modelmap(text)
    except ValueError as exc:
        return [Finding("FAIL", "modelmap_structure", str(exc))]

    simmods = extract_simmods(text)
    iet = modelmap.get("IET")
    if not iet:
        findings.append(Finding("FAIL", "modelmap_iet_missing", "MODELMAP has no IET selector"))
        return findings

    if iet not in simmods:
        findings.append(
            Finding("FAIL", "modelmap_iet_target_missing", f"MODELMAP selects {iet!r}, but no matching SIMMOD exists")
        )
    else:
        findings.append(Finding("PASS", "modelmap_iet_target", f"MODELMAP IET selects existing SIMMOD {iet!r}"))

    if expected_iet is not None:
        if iet != expected_iet:
            findings.append(
                Finding("FAIL", "modelmap_iet_expected", f"expected IET {expected_iet!r}, found {iet!r}")
            )
        else:
            findings.append(Finding("PASS", "modelmap_iet_expected", f"IET selector is {iet!r}"))

    if expected_iet == "RCRTable 3D" or expected_capacity_ah is not None:
        blocks = simmods.get("RCRTable 3D", [])
        if len(blocks) != 1:
            findings.append(
                Finding("FAIL", "rcr_block_count", f"expected exactly one RCRTable 3D SIMMOD, found {len(blocks)}")
            )
        else:
            block = blocks[0]
            specify = _field(block, "m_bSpecifyCapacity")
            capacity = _field(block, "m_dAhCell")
            nsets = _field(block, "m_nRCRParameterSets")
            if specify != "1":
                findings.append(Finding("FAIL", "rcr_capacity_override", f"m_bSpecifyCapacity={specify!r}, expected '1'"))
            else:
                findings.append(Finding("PASS", "rcr_capacity_override", "RCR capacity override enabled"))

            try:
                nsets_i = int(float(nsets)) if nsets is not None else 0
            except ValueError:
                nsets_i = 0
            if nsets_i <= 0:
                findings.append(Finding("FAIL", "rcr_parameter_sets", f"m_nRCRParameterSets={nsets!r}"))
            else:
                findings.append(Finding("PASS", "rcr_parameter_sets", f"RCR parameter sets={nsets_i}"))

            if expected_capacity_ah is not None:
                try:
                    cap = float(capacity) if capacity is not None else None
                except ValueError:
                    cap = None
                if cap is None or abs(cap - expected_capacity_ah) > 1e-12:
                    findings.append(
                        Finding("FAIL", "rcr_capacity_value", f"expected m_dAhCell={expected_capacity_ah}, found {capacity!r}")
                    )
                else:
                    findings.append(Finding("PASS", "rcr_capacity_value", f"m_dAhCell={cap} Ah"))

    if require_all_only1d_zero:
        vals = re.findall(r"(?m)^\s*m_bOnly1D\s*=\s*([^\t\r\n!]+)", text)
        bad = [v.strip() for v in vals if v.strip() != "0"]
        if not vals:
            findings.append(Finding("WARN", "only1d_absent", "no m_bOnly1D fields found"))
        elif bad:
            findings.append(Finding("FAIL", "only1d_nonzero", f"nonzero m_bOnly1D values: {bad}"))
        else:
            findings.append(Finding("PASS", "only1d_zero", f"all {len(vals)} m_bOnly1D fields are zero"))

    return findings


def validate_file(path: Path, **kwargs) -> list[Finding]:
    return validate_text(path.read_text(encoding="latin-1"), **kwargs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", type=Path)
    ap.add_argument("--expect-iet", default=None)
    ap.add_argument("--expect-capacity-ah", type=float, default=None)
    ap.add_argument("--require-all-only1d-zero", action="store_true")
    args = ap.parse_args()

    if not args.path.exists():
        sys.exit(f"ERROR: file not found: {args.path}")

    findings = validate_file(
        args.path,
        expected_iet=args.expect_iet,
        expected_capacity_ah=args.expect_capacity_ah,
        require_all_only1d_zero=args.require_all_only1d_zero,
    )
    for f in findings:
        print(f"{f.severity:4s} {f.code}: {f.message}")
    if any(f.severity == "FAIL" for f in findings):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
