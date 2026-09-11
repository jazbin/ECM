#!/usr/bin/env python3
"""
Generate the post-ROOT E004 fallback campaign.

Use only if ROOT_A and ROOT_B both return the identical:
    Electrode Root 1 : Extrusion distance can not be 0.

Outputs a small, conditional campaign:
  TL_A / TL_B              - tab-length headroom discriminators
  HP_CONTROL               - unmodified verified-clean Siemens HP18650 source
  HP_SHELL_PROJECT_RCR     - HP18650 PCD+Detailed Builder with project model context
  C10                      - project PCD with broad Siemens-like Builder pattern
  C13                      - validationBattery PCD+Detailed Builder with project model context

All project-derived files start from immutable R005, verified by SHA-256.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import re
import subprocess
import sys
import zipfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "tools/validate_tbm.py"

BASELINE_COMMIT = "d74b3283cb5d73e114bc141f3f0d18e7c7ed5463"
BASELINE_PATH = "out/hp2170NCA-RCR-distributed-exact-contact-final.tbm"
BASELINE_SHA256 = "2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5"

HP_REF = "tbm-siemens-reference-corpus"
HP_PATH = "tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm"

VAL_REF = "tbm-rcr-modelmap-fix-exec"
VAL_PATH = "tbm_validation/in_StarCCM_bds/validationBattery.tbm"

OUT_DIR = REPO_ROOT / "out/e004_post_root_fallback_20260911"
ZIP_PATH = REPO_ROOT / "out/hp2170NCA-STAR-E004-post-root-fallback-20260911.zip"

TL_CASES = [
    (
        "TL_A",
        "TL_A_TAB_HEADROOM_0p10.tbm",
        {"+Electrode Tab m_dLength_mm": ("60", "64.21"),
         "-Electrode Tab m_dLength_mm": ("60", "65.21")},
        "+0.10 mm tab-length headroom over each corresponding electrode width",
    ),
    (
        "TL_B",
        "TL_B_TAB_HEADROOM_0p70.tbm",
        {"+Electrode Tab m_dLength_mm": ("60", "64.81"),
         "-Electrode Tab m_dLength_mm": ("60", "65.81")},
        "+0.70 mm tab-length headroom over each corresponding electrode width",
    ),
]

C10_DELTAS = {
    "m_dSepFeedLength_mm": ("0", "10"),
    "m_dSepTailLength_mm": ("0", "85"),
    "m_dElectrodeOverlapAtStart_mm": ("8", "3"),
    "m_dElectrodeOverlapAtEnd_mm": ("20", "40"),
    "m_dMandrelWidth_mm": ("6", "0"),
}

MANIFEST_FIELDS = [
    "id", "filename", "sha256", "source", "changed_scope", "purpose",
    "validator_fail", "validator_warn",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_show(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=REPO_ROOT)


def span(text: str, start_tag: str, end_tag: str, start_at: int = 0) -> tuple[int, int]:
    a = text.index(start_tag, start_at)
    b = text.index(end_tag, a) + len(end_tag)
    return a, b


def pcd_span(text: str) -> tuple[int, int]:
    return span(text, "<Physical Cell Description>", "</Physical Cell Description>")


def first_builder_span(text: str) -> tuple[int, int]:
    return span(text, "<BUILDER>", "</BUILDER>")


def exact_field_replace_in_span(
    text: str, block_span: tuple[int, int], field: str, old: str, new: str
) -> str:
    a, b = block_span
    block = text[a:b]
    pattern = r"(\t" + re.escape(field) + r"\t=\t)" + re.escape(old) + r"(?=[\t\r\n])"
    new_block, n = re.subn(pattern, r"\g<1>" + new, block)
    if n != 1:
        raise RuntimeError(f"{field}: expected exactly one {old!r} in target block, got {n}")
    return text[:a] + new_block + text[b:]


def apply_pcd_deltas(text: str, deltas: dict[str, tuple[str, str]]) -> str:
    out = text
    for field, (old, new) in deltas.items():
        out = exact_field_replace_in_span(out, pcd_span(out), field, old, new)
    return out


def apply_builder_deltas(text: str, deltas: dict[str, tuple[str, str]]) -> str:
    out = text
    for field, (old, new) in deltas.items():
        out = exact_field_replace_in_span(out, first_builder_span(out), field, old, new)
    return out


def replace_pcd_and_first_builder(project: str, source: str) -> str:
    pp0, pp1 = pcd_span(project)
    pb0, pb1 = first_builder_span(project)
    sp0, sp1 = pcd_span(source)
    sb0, sb1 = first_builder_span(source)
    # Preserve every character of the project outside the two replaced blocks.
    # Source block line endings are intentionally retained.
    return (
        project[:pp0]
        + source[sp0:sp1]
        + project[pp1:pb0]
        + source[sb0:sb1]
        + project[pb1:]
    )


def run_validator(path: pathlib.Path) -> tuple[int, int, str]:
    p = subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    out = (p.stdout or "") + (p.stderr or "")
    return out.count("\nFAIL "), out.count("\nWARN "), out.strip()


def assert_tl_only_two_lines(base: str, variant: str, expected_fields: set[str]) -> None:
    b = base.splitlines()
    v = variant.splitlines()
    if len(b) != len(v):
        raise RuntimeError("TL variant changed line count")
    diffs = [(x, y) for x, y in zip(b, v) if x != y]
    if len(diffs) != 2:
        raise RuntimeError(f"TL variant expected exactly 2 changed lines, got {len(diffs)}")
    found = set()
    for old_line, new_line in diffs:
        for field in expected_fields:
            if field in old_line and field in new_line:
                found.add(field)
    if found != expected_fields:
        raise RuntimeError(f"TL changed-line fields mismatch: expected {expected_fields}, found {found}")


def assert_project_suffix_after_first_builder_unchanged(base: str, variant: str) -> None:
    _, bb1 = first_builder_span(base)
    _, vb1 = first_builder_span(variant)
    if base[bb1:] != variant[vb1:]:
        raise RuntimeError("Project content after first BUILDER changed unexpectedly")


def assert_project_middle_between_pcd_builder_unchanged(base: str, variant: str) -> None:
    _, bp1 = pcd_span(base)
    bb0, _ = first_builder_span(base)
    _, vp1 = pcd_span(variant)
    vb0, _ = first_builder_span(variant)
    if base[bp1:bb0] != variant[vp1:vb0]:
        raise RuntimeError("Project content between PCD and first BUILDER changed unexpectedly")


def extract_field(text: str, field: str) -> str:
    m = re.search(r"\t" + re.escape(field) + r"\t=\t([^\t\r\n]+)", text)
    return m.group(1).strip() if m else "?"


def write_case(
    case_id: str,
    filename: str,
    raw: bytes,
    source: str,
    scope: str,
    purpose: str,
    rows: list[dict],
    logs: list[tuple[str, str]],
) -> None:
    path = OUT_DIR / filename
    path.write_bytes(raw)
    fail, warn, log = run_validator(path)
    rows.append({
        "id": case_id,
        "filename": filename,
        "sha256": sha256_bytes(raw),
        "source": source,
        "changed_scope": scope,
        "purpose": purpose,
        "validator_fail": fail,
        "validator_warn": warn,
    })
    logs.append((case_id, log))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    baseline_raw = git_show(BASELINE_COMMIT, BASELINE_PATH)
    got = sha256_bytes(baseline_raw)
    if got != BASELINE_SHA256:
        raise RuntimeError(f"R005 baseline SHA mismatch: expected {BASELINE_SHA256}, got {got}")
    baseline = baseline_raw.decode("latin-1")

    hp_raw = git_show(HP_REF, HP_PATH)
    hp = hp_raw.decode("latin-1")
    validation_raw = git_show(VAL_REF, VAL_PATH)
    validation = validation_raw.decode("latin-1")

    rows: list[dict] = []
    logs: list[tuple[str, str]] = []

    # TL_A / TL_B: exactly two PCD tab-length lines change from R005.
    for case_id, filename, deltas, purpose in TL_CASES:
        variant = apply_pcd_deltas(baseline, deltas)
        assert_tl_only_two_lines(baseline, variant, set(deltas))
        _, bp1 = pcd_span(baseline)
        _, vp1 = pcd_span(variant)
        if baseline[bp1:] != variant[vp1:]:
            raise RuntimeError(f"{case_id}: content after PCD changed unexpectedly")
        write_case(
            case_id, filename, variant.encode("latin-1"),
            f"R005 {BASELINE_SHA256}", "PCD: two tab-length fields only",
            purpose, rows, logs,
        )

    # Known-clean Siemens control, byte-for-byte from the corpus branch.
    write_case(
        "HP_CONTROL", "HP_CONTROL_hp18650Spiral-DIST.tbm", hp_raw,
        f"{HP_REF}:{HP_PATH}", "none (unmodified Siemens source)",
        "Environment/CreateFromTbm control; source lineage has verified-clean 13-solid STEP",
        rows, logs,
    )

    # HP geometry shell + project non-geometry/model context.
    hp_shell = replace_pcd_and_first_builder(baseline, hp)
    assert_project_middle_between_pcd_builder_unchanged(baseline, hp_shell)
    assert_project_suffix_after_first_builder_unchanged(baseline, hp_shell)
    write_case(
        "HP_SHELL", "HP_SHELL_PROJECT_RCR.tbm", hp_shell.encode("latin-1"),
        f"R005 + {HP_REF}:{HP_PATH}",
        "replace complete PCD + first/active Detailed Builder; retain project suffix/model context",
        "Known-clean HP18650 geometry shell with project RCR/SIMMOD/MODELMAP context",
        rows, logs,
    )

    # Cleaner Builder-only rescue than old C12: preserve R005 JR diameter/PCD.
    c10 = apply_builder_deltas(baseline, C10_DELTAS)
    write_case(
        "C10", "C10_STAR_BUILDER_PATTERN.tbm", c10.encode("latin-1"),
        f"R005 {BASELINE_SHA256}", "first/active Detailed Builder: 5 controlled fields",
        "Builder-only broad Siemens-like pattern while preserving project PCD and JR diameter",
        rows, logs,
    )

    # Independent second geometry-shell lineage using validationBattery.
    c13 = replace_pcd_and_first_builder(baseline, validation)
    assert_project_middle_between_pcd_builder_unchanged(baseline, c13)
    assert_project_suffix_after_first_builder_unchanged(baseline, c13)
    write_case(
        "C13", "C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm", c13.encode("latin-1"),
        f"R005 + {VAL_REF}:{VAL_PATH}",
        "replace complete PCD + first/active Detailed Builder; retain project suffix/model context",
        "Independent validationBattery geometry shell with project RCR/SIMMOD/MODELMAP context",
        rows, logs,
    )

    # Record compact geometry discriminators.
    audit_lines = [
        "case,+electrode_width,+tab_length,+headroom,-electrode_width,-tab_length,-headroom,package_int_height,jr_builder",
        "R005,64.11,60,-4.11,65.11,60,-5.11,65.11,20.6274",
        "TL_A,64.11,64.21,+0.10,65.11,65.21,+0.10,65.11,20.6274",
        "TL_B,64.11,64.81,+0.70,65.11,65.81,+0.70,65.11,20.6274",
        f"HP_CONTROL,{extract_field(hp, '+Electrode m_dWidth')},{extract_field(hp, '+Electrode Tab m_dLength_mm')},"
        f"{float(extract_field(hp, '+Electrode Tab m_dLength_mm')) - float(extract_field(hp, '+Electrode m_dWidth')):+.2f},"
        f"{extract_field(hp, '-Electrode m_dWidth')},{extract_field(hp, '-Electrode Tab m_dLength_mm')},"
        f"{float(extract_field(hp, '-Electrode Tab m_dLength_mm')) - float(extract_field(hp, '-Electrode m_dWidth')):+.2f},"
        f"{extract_field(hp, 'Package m_dintHeight')},{extract_field(hp, 'm_dJellyrollThickness_mm')}",
    ]
    (OUT_DIR / "GEOMETRY_AUDIT.csv").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

    with (OUT_DIR / "MANIFEST.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)

    with (OUT_DIR / "VALIDATOR_LOG.txt").open("w", encoding="utf-8") as f:
        for case_id, log in logs:
            f.write(f"===== {case_id} =====\n{log}\n\n")

    readme = f"""hp2170 NCA — STAR E004 POST-ROOT FALLBACK
Generated by tools/generate_e004_post_root_fallback.py

USE THIS PACKAGE ONLY IF ROOT_A AND ROOT_B BOTH RETURN THE IDENTICAL:
    Electrode Root 1 : Extrusion distance can not be 0.

Immutable project baseline SHA-256:
    {BASELINE_SHA256}

TEST ORDER / STOP RULES

1. TL_A_TAB_HEADROOM_0p10.tbm
   - If E004 disappears or changes to a downstream error: STOP.
     Return the complete console output and, if geometry is created, export STEP.
   - If identical E004 remains: continue.

2. TL_B_TAB_HEADROOM_0p70.tbm
   - If E004 disappears or changes: STOP and return output/STEP.
   - If identical E004 remains: continue.

3. HP_CONTROL_hp18650Spiral-DIST.tbm
   - This is an unmodified Siemens HP18650 source whose generated 13-solid STEP is
     already known geometry-clean.
   - If it fails in the current STAR environment: STOP. Do not interpret hybrids.
   - If it passes: continue.

4. HP_SHELL_PROJECT_RCR.tbm
   - Siemens HP18650 PCD + active Detailed Builder with the project model/RCR context.
   - If it passes while project cases fail, the project geometry content is implicated.
   - If HP_CONTROL passes but this fails with E004, investigate project model/context
     coupling or non-transplanted sections.

ONLY IF REQUESTED AFTER THE ABOVE RESULTS:
5. C10_STAR_BUILDER_PATTERN.tbm
6. C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm

IMPORTANT
- Every file here is diagnostic only except the unmodified HP_CONTROL.
- TL_A/TL_B are not approved production tab dimensions.
- A different downstream error counts as clearing E004 for localization purposes.
- Do not reduce a different error to just FAIL; return exact text.
"""
    (OUT_DIR / "README.txt").write_text(readme, encoding="utf-8")

    include_names = [
        "TL_A_TAB_HEADROOM_0p10.tbm",
        "TL_B_TAB_HEADROOM_0p70.tbm",
        "HP_CONTROL_hp18650Spiral-DIST.tbm",
        "HP_SHELL_PROJECT_RCR.tbm",
        "C10_STAR_BUILDER_PATTERN.tbm",
        "C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm",
        "README.txt",
        "MANIFEST.csv",
        "GEOMETRY_AUDIT.csv",
    ]
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in include_names:
            z.write(OUT_DIR / name, arcname=name)

    print(f"Baseline: {BASELINE_SHA256}")
    print(f"HP source SHA-256: {sha256_bytes(hp_raw)}")
    for row in rows:
        print(f"{row['id']}: {row['sha256']} | FAIL={row['validator_fail']} WARN={row['validator_warn']}")
    print(f"ZIP: {ZIP_PATH}")
    print(f"ZIP SHA-256: {sha256_bytes(ZIP_PATH.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
