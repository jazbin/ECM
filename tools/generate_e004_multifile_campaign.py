#!/usr/bin/env python3
"""
Deterministic generator — STAR E004 Multifile Diagnostic Campaign C00-C13.

Campaign documents:
  tbm_validation/STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_20260910.md
  tbm_validation/STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_ADDENDUM_20260910.md
  (addendum takes precedence)

Baseline sourced from commit d74b3283cb5d73e114bc141f3f0d18e7c7ed5463,
NOT from the branch-tip working copy (which has been subsequently edited).

Usage:
    cd /workspace && python3 tools/generate_e004_multifile_campaign.py
"""

import csv
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

BASELINE_GIT_COMMIT = "d74b3283cb5d73e114bc141f3f0d18e7c7ed5463"
BASELINE_GIT_PATH   = "out/hp2170NCA-RCR-distributed-exact-contact-final.tbm"
BASELINE_SHA256     = "2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5"

SIEMENS_CONTROL_SRC = REPO_ROOT / "tbm_validation/in_StarCCM_bds/validationBattery.tbm"
VALIDATOR           = REPO_ROOT / "tools/validate_tbm.py"

OUT_DIR  = REPO_ROOT / "out/e004_multifile_campaign_20260910"
ZIP_PATH = REPO_ROOT / "out/hp2170NCA-STAR-E004-multifile-diagnostic-20260910.zip"

# ---------------------------------------------------------------------------
# C01-C11 field-level delta definitions
# All deltas apply only to the first <BUILDER>…</BUILDER> block.
# old_val and new_val are the exact strings as they appear in the TBM.
# ---------------------------------------------------------------------------

FIELD_VARIANTS = [
    {
        "id": "C01", "filename": "C01_FEED10.tbm",
        "deltas": {"m_dSepFeedLength_mm": ("0", "10")},
        "purpose": "Isolate separator feed length: feed=10 alone vs E004.",
        "sep_feed": 10, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
    },
    {
        "id": "C02", "filename": "C02_TAIL85.tbm",
        "deltas": {"m_dSepTailLength_mm": ("0", "85")},
        "purpose": "Isolate separator tail length: tail=85 alone vs E004.",
        "sep_feed": 0, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
    },
    {
        "id": "C03", "filename": "C03_FEED10_TAIL85.tbm",
        "deltas": {"m_dSepFeedLength_mm": ("0", "10"), "m_dSepTailLength_mm": ("0", "85")},
        "purpose": "H004-5 leading hypothesis: combined feed+tail.",
        "sep_feed": 10, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
    },
    {
        "id": "C04", "filename": "C04_END40.tbm",
        "deltas": {"m_dElectrodeOverlapAtEnd_mm": ("20", "40")},
        "purpose": "Isolate end-overlap influence on E004.",
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 40, "mw": 6, "jrw": 0,
    },
    {
        "id": "C05", "filename": "C05_FEED10_TAIL85_END40.tbm",
        "deltas": {
            "m_dSepFeedLength_mm": ("0", "10"),
            "m_dSepTailLength_mm": ("0", "85"),
            "m_dElectrodeOverlapAtEnd_mm": ("20", "40"),
        },
        "purpose": "Feed+tail+end-overlap interaction test.",
        "sep_feed": 10, "sep_tail": 85, "ov_start": 8, "ov_end": 40, "mw": 6, "jrw": 0,
    },
    {
        "id": "C06", "filename": "C06_MANDRELWIDTH0.tbm",
        "deltas": {"m_dMandrelWidth_mm": ("6", "0")},
        "purpose": "STAR round-mandrel convention: MandrelWidth=0 alone vs E004.",
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 0, "jrw": 0,
    },
    {
        "id": "C07", "filename": "C07_FEED10_TAIL85_MANDRELWIDTH0.tbm",
        "deltas": {
            "m_dSepFeedLength_mm": ("0", "10"),
            "m_dSepTailLength_mm": ("0", "85"),
            "m_dMandrelWidth_mm": ("6", "0"),
        },
        "purpose": "Feed+tail with STAR round-mandrel width convention.",
        "sep_feed": 10, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 0, "jrw": 0,
    },
    {
        "id": "C08", "filename": "C08_JRWIDTH65p11.tbm",
        "deltas": {"m_dJellyrollWidth_mm": ("0", "65.11")},
        "purpose": "Low-probability probe: JellyrollWidth zero in Detailed Builder.",
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 65.11,
    },
    {
        "id": "C09", "filename": "C09_FEED10_TAIL85_JRWIDTH65p11.tbm",
        "deltas": {
            "m_dSepFeedLength_mm": ("0", "10"),
            "m_dSepTailLength_mm": ("0", "85"),
            "m_dJellyrollWidth_mm": ("0", "65.11"),
        },
        "purpose": "Feed+tail + JellyrollWidth interaction probe.",
        "sep_feed": 10, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 65.11,
    },
    {
        "id": "C10", "filename": "C10_STAR_BUILDER_PATTERN.tbm",
        "deltas": {
            "m_dSepFeedLength_mm": ("0", "10"),
            "m_dSepTailLength_mm": ("0", "85"),
            "m_dElectrodeOverlapAtStart_mm": ("8", "3"),
            "m_dElectrodeOverlapAtEnd_mm": ("20", "40"),
            "m_dMandrelWidth_mm": ("6", "0"),
        },
        "purpose": "Broad STAR-reference Detailed Builder pattern rescue.",
        "sep_feed": 10, "sep_tail": 85, "ov_start": 3, "ov_end": 40, "mw": 0, "jrw": 0,
    },
    {
        "id": "C11", "filename": "C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm",
        "deltas": {
            "m_dSepFeedLength_mm": ("0", "10"),
            "m_dSepTailLength_mm": ("0", "85"),
            "m_dElectrodeOverlapAtStart_mm": ("8", "3"),
            "m_dElectrodeOverlapAtEnd_mm": ("20", "40"),
            "m_dMandrelWidth_mm": ("6", "0"),
            "m_dJellyrollWidth_mm": ("0", "65.11"),
        },
        "purpose": "Maximum geometry-builder rescue: all STAR-pattern changes + explicit JR width.",
        "sep_feed": 10, "sep_tail": 85, "ov_start": 3, "ov_end": 40, "mw": 0, "jrw": 65.11,
    },
]

# Protected fields — must be byte-identical between baseline and C01-C11 variants.
# Not enforced for C12/C13 (intentional geometry transplant).
PROTECTED_FIELDS = [
    "m_dextDiameter", "m_dextHeight", "m_dintDiameter",
    "m_dJellyrollThickness_mm", "m_dMandrelThickness_mm",
    "+Electrode m_dS1", "+Electrode m_dS2", "+Electrode m_dS3",
    "-Electrode m_dS1", "-Electrode m_dS2", "-Electrode m_dS3",
    "m_bNegTab", "m_bPosTab",
    "m_nNegTabVertOrientation", "m_nPosTabVertOrientation",
    "Transport Number sets", "m_bLumpedEnergyBalance",
    "m_dAhCell", "m_nRCRParameterSets",
]

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())

def normalize_lf(text: str) -> str:
    """Normalize CRLF and CR to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")

def get_first_builder_span(content: str) -> tuple[int, int]:
    """Return (start, end) byte offsets of the first <BUILDER>...</BUILDER> block (inclusive)."""
    start = content.index("<BUILDER>")
    end = content.index("</BUILDER>", start) + len("</BUILDER>")
    return start, end

def get_pcd_span(content: str) -> tuple[int, int]:
    """Return (start, end) of <Physical Cell Description>...</Physical Cell Description>."""
    start = content.index("<Physical Cell Description>")
    end = content.index("</Physical Cell Description>") + len("</Physical Cell Description>")
    return start, end

def count_field_in_builder(content: str, field: str) -> int:
    b_start, b_end = get_first_builder_span(content)
    block = content[b_start:b_end]
    return len(re.findall(r'\t' + re.escape(field) + r'\t=', block))

def apply_field_delta(content: str, field: str, old_val: str, new_val: str) -> tuple[str, int]:
    """Replace field=old_val with field=new_val in the first BUILDER block only."""
    b_start, b_end = get_first_builder_span(content)
    before = content[:b_start]
    block  = content[b_start:b_end]
    after  = content[b_end:]
    pattern     = r'(\t' + re.escape(field) + r'\t=\t)' + re.escape(old_val) + r'([\t\n\r])'
    replacement = r'\g<1>' + new_val + r'\g<2>'
    new_block, n = re.subn(pattern, replacement, block)
    return before + new_block + after, n

def extract_field_lines(content: str, field: str) -> list[str]:
    return [ln for ln in content.splitlines() if field in ln]

def check_protected_fields(baseline: str, variant: str, vid: str) -> list[str]:
    failures = []
    for pat in PROTECTED_FIELDS:
        b_lines = extract_field_lines(baseline, pat)
        v_lines = extract_field_lines(variant, pat)
        if b_lines != v_lines:
            failures.append(
                f"  [{vid}] PROTECTED FIELD MISMATCH: {pat!r}\n"
                f"    baseline: {b_lines}\n"
                f"    variant:  {v_lines}"
            )
    return failures

def run_validator(path: pathlib.Path) -> tuple[int, int, str]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        capture_output=True, text=True,
    )
    out = result.stdout + result.stderr
    fails = out.count("\nFAIL ")
    warns = out.count("\nWARN ")
    return fails, warns, out.strip()

def delta_summary(variant: dict) -> str:
    return "; ".join(
        f"{f}: {ov} -> {nv}" for f, (ov, nv) in variant["deltas"].items()
    )

# ---------------------------------------------------------------------------
# Baseline loading
# ---------------------------------------------------------------------------

def load_baseline() -> tuple[bytes, str]:
    """Load baseline from git commit, verify SHA, return (bytes, text)."""
    print(f"  git show {BASELINE_GIT_COMMIT}:{BASELINE_GIT_PATH}")
    raw = subprocess.check_output(
        ["git", "show", f"{BASELINE_GIT_COMMIT}:{BASELINE_GIT_PATH}"],
        cwd=REPO_ROOT,
    )
    actual = sha256_bytes(raw)
    if actual != BASELINE_SHA256:
        print(f"ABORT: baseline SHA mismatch")
        print(f"  expected: {BASELINE_SHA256}")
        print(f"  actual:   {actual}")
        sys.exit(1)
    print(f"  SHA-256 verified: {actual}")
    return raw, raw.decode("latin-1")

# ---------------------------------------------------------------------------
# C12 — full Siemens Detailed Builder transplant
# ---------------------------------------------------------------------------

def generate_c12(proj_content: str, siemens_content: str) -> tuple[bytes, str]:
    """
    Replace the first <BUILDER>…</BUILDER> block in the project baseline with
    the complete Detailed Builder block from validationBattery.tbm.
    Returns (file_bytes, block_diff_text).
    """
    pb_start, pb_end = get_first_builder_span(proj_content)
    sb_start, sb_end = get_first_builder_span(siemens_content)

    proj_builder    = proj_content[pb_start:pb_end]
    siemens_builder = normalize_lf(siemens_content[sb_start:sb_end])

    c12_content = proj_content[:pb_start] + siemens_builder + proj_content[pb_end:]

    # Block-level diff (line-by-line)
    proj_lines    = proj_builder.splitlines()
    siemens_lines = siemens_builder.splitlines()
    diff_lines = ["--- project Detailed Builder", "+++ Siemens validationBattery Detailed Builder", ""]
    all_fields = set(proj_lines) | set(siemens_lines)
    for ln in proj_lines:
        if ln not in siemens_lines:
            diff_lines.append(f"- {ln}")
    for ln in siemens_lines:
        if ln not in proj_lines:
            diff_lines.append(f"+ {ln}")
    diff_text = "\n".join(diff_lines)

    return c12_content.encode("latin-1"), diff_text

# ---------------------------------------------------------------------------
# C13 — Siemens geometry shell, project model/RCR retained
# ---------------------------------------------------------------------------

def generate_c13(proj_content: str, siemens_content: str) -> bytes:
    """
    Replace Physical Cell Description AND first BUILDER in project with
    the Siemens equivalents (normalized to LF). All project SIMMOD, MODELMAP,
    DEFAULT BUILDER, second BUILDER, and About-Energy RCR data are retained.
    """
    # Project: locate PCD and first BUILDER
    pp_start, pp_end = get_pcd_span(proj_content)
    pb_start, pb_end = get_first_builder_span(proj_content)

    # Siemens: extract PCD and BUILDER (normalize CRLF → LF)
    sp_start, sp_end = get_pcd_span(siemens_content)
    sb_start, sb_end = get_first_builder_span(siemens_content)
    siemens_pcd     = normalize_lf(siemens_content[sp_start:sp_end])
    siemens_builder = normalize_lf(siemens_content[sb_start:sb_end])

    # Separator between PCD and BUILDER in project (typically "\n")
    pcd_to_b1_sep = proj_content[pp_end:pb_start]

    c13_content = (
        proj_content[:pp_start]  # "tbmfileversion\t=\t9.0\n"
        + siemens_pcd
        + pcd_to_b1_sep
        + siemens_builder
        + proj_content[pb_end:]  # "\n<SIMMOD>..." — all project SIMODs retained
    )
    return c13_content.encode("latin-1")

# ---------------------------------------------------------------------------
# Campaign matrix helpers
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "id", "filename", "base_sha256", "sha256", "changed_fields",
    "sep_feed_mm", "sep_tail_mm", "overlap_start_mm", "overlap_end_mm",
    "mandrel_width_mm", "jr_width_mm", "expected_purpose",
    "runtime_result", "runtime_error_class", "runtime_notes",
]

def make_row(id_, filename, base_sha, sha, changed, sf, st, os_, oe, mw, jrw, purpose):
    return {
        "id": id_, "filename": filename, "base_sha256": base_sha, "sha256": sha,
        "changed_fields": changed, "sep_feed_mm": sf, "sep_tail_mm": st,
        "overlap_start_mm": os_, "overlap_end_mm": oe, "mandrel_width_mm": mw,
        "jr_width_mm": jrw, "expected_purpose": purpose,
        "runtime_result": "", "runtime_error_class": "", "runtime_notes": "",
    }

# ---------------------------------------------------------------------------
# README content
# ---------------------------------------------------------------------------

README_TEXT = """\
hp2170 NCA — STAR-CCM+ E004 Multifile Diagnostic Campaign
2026-09-10

BACKGROUND

This package diagnoses the persistent STAR-CCM+ geometry creation failure:

    Feature execution failed.
    Electrode Root 1 : Extrusion distance can not be 0.
    Command: CreateFromTbm

This exact fatal error has appeared across multiple packages since 2026-09-04.
Each file in this package intentionally changes only a controlled subset of
Detailed Builder geometry fields so that test results can isolate the cause.

FILES (14 total)

C00_SIEMENS_CONTROL_validationBattery.tbm
    Unmodified Siemens STAR install reference TBM.
    Run this first to confirm your STAR installation and Create from Tbm
    workflow work on a known-good Siemens file. No project data.

C01_FEED10.tbm
    Delta: m_dSepFeedLength_mm 0 -> 10 only.

C02_TAIL85.tbm
    Delta: m_dSepTailLength_mm 0 -> 85 only.

C03_FEED10_TAIL85.tbm
    Delta: m_dSepFeedLength_mm 0 -> 10  AND  m_dSepTailLength_mm 0 -> 85.
    Highest-probability fix candidate.

C04_END40.tbm
    Delta: m_dElectrodeOverlapAtEnd_mm 20 -> 40 only.

C05_FEED10_TAIL85_END40.tbm
    Delta: Feed=10, Tail=85, OverlapEnd=40.

C06_MANDRELWIDTH0.tbm
    Delta: m_dMandrelWidth_mm 6 -> 0 only.

C07_FEED10_TAIL85_MANDRELWIDTH0.tbm
    Delta: Feed=10, Tail=85, MandrelWidth=0.

C08_JRWIDTH65p11.tbm
    Delta: m_dJellyrollWidth_mm 0 -> 65.11 only.

C09_FEED10_TAIL85_JRWIDTH65p11.tbm
    Delta: Feed=10, Tail=85, JellyrollWidth=65.11.

C10_STAR_BUILDER_PATTERN.tbm
    Delta: Feed=10, Tail=85, OverlapStart=3, OverlapEnd=40, MandrelWidth=0.
    Broad rescue using STAR-reference Detailed Builder conventions.

C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm
    Delta: All C10 changes plus JellyrollWidth=65.11. Maximum rescue variant.

C12_FULL_SIEMENS_DETAILED_BUILDER.tbm
    Complete Detailed Builder block from Siemens validationBattery.tbm,
    transplanted into the project file. Project SIMMOD and RCR data retained.
    Diagnostic only — not a production geometry candidate.

C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm
    Both the Physical Cell Description and Detailed Builder from Siemens
    validationBattery.tbm, with project MODELMAP, RCRTable 3D SIMMOD, General
    Electrolyte SIMMOD, and Distributed Thermal SIMMOD retained.
    Diagnostic only — not a production geometry candidate.

WHAT TO DO

Run Batteries > Battery Cell > Create from Tbm for all 14 files.
Recommended order: C00, C03, C01, C02, C10, C12, C13, C05, C07, C04, C06,
C08, C09, C11.

Return results in this exact format:

    C00: PASS / <exact error text>
    C01: PASS / <exact error text>
    C02: PASS / <exact error text>
    C03: PASS / <exact error text>
    C04: PASS / <exact error text>
    C05: PASS / <exact error text>
    C06: PASS / <exact error text>
    C07: PASS / <exact error text>
    C08: PASS / <exact error text>
    C09: PASS / <exact error text>
    C10: PASS / <exact error text>
    C11: PASS / <exact error text>
    C12: PASS / <exact error text>
    C13: PASS / <exact error text>

IMPORTANT

If a file creates geometry successfully, record PASS and continue testing all
remaining files.

If STAR reaches a DIFFERENT error than "Electrode Root 1", report that full
error text. A different error means E004 was cleared for that variant, which
is important diagnostic information even if full creation did not succeed.

The exact error text matters. Do not reduce a different downstream blocker
to just FAIL — report what STAR actually says.
"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("STAR E004 Multifile Diagnostic Campaign Generator — C00-C13")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Load and verify baseline from git commit
    # ------------------------------------------------------------------
    print(f"\n[1] Loading baseline from commit {BASELINE_GIT_COMMIT}")
    baseline_raw, baseline_str = load_baseline()

    # ------------------------------------------------------------------
    # 2. Load Siemens control
    # ------------------------------------------------------------------
    print(f"\n[2] Loading Siemens control: {SIEMENS_CONTROL_SRC.name}")
    if not SIEMENS_CONTROL_SRC.exists():
        print(f"ABORT: {SIEMENS_CONTROL_SRC} not found")
        sys.exit(1)
    siemens_raw = SIEMENS_CONTROL_SRC.read_bytes()
    siemens_str = siemens_raw.decode("latin-1")
    siemens_sha = sha256_bytes(siemens_raw)
    print(f"  SHA-256: {siemens_sha}")

    # ------------------------------------------------------------------
    # 3. Setup output directory
    # ------------------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 4. C00 — Siemens control (unmodified copy)
    # ------------------------------------------------------------------
    print(f"\n[3] C00 — Siemens control")
    c00_dst = OUT_DIR / "C00_SIEMENS_CONTROL_validationBattery.tbm"
    c00_dst.write_bytes(siemens_raw)
    c00_sha = siemens_sha
    print(f"  SHA-256: {c00_sha}")

    matrix_rows = []
    validator_log = []
    all_protected_ok = True

    c00_row = make_row(
        "C00", "C00_SIEMENS_CONTROL_validationBattery.tbm",
        "N/A — Siemens install reference", c00_sha,
        "N/A — unmodified Siemens reference",
        "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
        "Environment/import-path control. Proves Robert's STAR install and "
        "Create from Tbm workflow import a known Siemens cylindrical TBM.",
    )
    matrix_rows.append(c00_row)

    # ------------------------------------------------------------------
    # 5. C01-C11 — field-level delta variants
    # ------------------------------------------------------------------
    print(f"\n[4] Generating C01-C11 (field-level deltas from baseline)")

    for v in FIELD_VARIANTS:
        vid      = v["id"]
        filename = v["filename"]
        dst      = OUT_DIR / filename
        print(f"\n  {vid}  {filename}")
        print(f"    deltas: {delta_summary(v)}")

        content = baseline_str
        for field, (old_val, new_val) in v["deltas"].items():
            n_before = count_field_in_builder(content, field)
            if n_before != 1:
                print(f"  ABORT: {vid}: field {field!r} occurs {n_before} times in "
                      f"first BUILDER block (expected 1)")
                sys.exit(1)
            content, replaced = apply_field_delta(content, field, old_val, new_val)
            if replaced != 1:
                print(f"  ABORT: {vid}: {field!r} = {old_val!r} -> {new_val!r} "
                      f"replaced {replaced} times (expected 1)")
                sys.exit(1)

        file_bytes = content.encode("latin-1")
        dst.write_bytes(file_bytes)
        file_sha = sha256_bytes(file_bytes)
        print(f"    SHA-256: {file_sha}")

        # Protected field check
        prot_failures = check_protected_fields(baseline_str, content, vid)
        if prot_failures:
            all_protected_ok = False
            for msg in prot_failures:
                print(msg)
        else:
            print(f"    Protected fields: PASS")

        # Validator
        f_count, w_count, val_out = run_validator(dst)
        vsummary = f"FAIL={f_count} WARN={w_count}"
        print(f"    Validator: {vsummary}")
        validator_log.append((vid, filename, vsummary, val_out))

        matrix_rows.append(make_row(
            vid, filename, BASELINE_SHA256, file_sha, delta_summary(v),
            v["sep_feed"], v["sep_tail"], v["ov_start"], v["ov_end"],
            v["mw"], v["jrw"], v["purpose"],
        ))

    # ------------------------------------------------------------------
    # 6. C12 — full Siemens Detailed Builder transplant
    # ------------------------------------------------------------------
    print(f"\n[5] C12 — Full Siemens Detailed Builder transplant")
    c12_bytes, c12_diff = generate_c12(baseline_str, siemens_str)
    c12_dst = OUT_DIR / "C12_FULL_SIEMENS_DETAILED_BUILDER.tbm"
    c12_dst.write_bytes(c12_bytes)
    c12_sha = sha256_bytes(c12_bytes)
    print(f"  SHA-256: {c12_sha}")
    (OUT_DIR / "C12_BUILDER_BLOCK_DIFF.txt").write_text(c12_diff, encoding="utf-8")

    f_count, w_count, val_out = run_validator(c12_dst)
    vsummary = f"FAIL={f_count} WARN={w_count} (expected FAILs: Siemens JR/geometry values differ from project spec)"
    print(f"  Validator: {vsummary}")
    validator_log.append(("C12", "C12_FULL_SIEMENS_DETAILED_BUILDER.tbm", vsummary, val_out))

    # Extract Siemens builder values for matrix
    sbi = siemens_str[siemens_str.index("<BUILDER>"):siemens_str.index("</BUILDER>") + len("</BUILDER>")]
    def get_sv(field, default="?"):
        m = re.search(r'\t' + re.escape(field) + r'\t=\t([^\t\n]+)', sbi)
        return m.group(1) if m else default

    matrix_rows.append(make_row(
        "C12", "C12_FULL_SIEMENS_DETAILED_BUILDER.tbm",
        BASELINE_SHA256, c12_sha,
        "Complete Detailed Builder block replaced with Siemens validationBattery.tbm BUILDER",
        get_sv("m_dSepFeedLength_mm"), get_sv("m_dSepTailLength_mm"),
        get_sv("m_dElectrodeOverlapAtStart_mm"), get_sv("m_dElectrodeOverlapAtEnd_mm"),
        get_sv("m_dMandrelWidth_mm"), get_sv("m_dJellyrollWidth_mm"),
        "Broad localization control: full Siemens Detailed Builder in project file. "
        "If C01-C11 all fail but C12 passes, culprit is in Builder fields outside tested subset.",
    ))

    # ------------------------------------------------------------------
    # 7. C13 — Siemens geometry shell, project model/RCR retained
    # ------------------------------------------------------------------
    print(f"\n[6] C13 — Siemens geometry shell, project model/RCR retained")
    c13_bytes = generate_c13(baseline_str, siemens_str)
    c13_dst = OUT_DIR / "C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm"
    c13_dst.write_bytes(c13_bytes)
    c13_sha = sha256_bytes(c13_bytes)
    print(f"  SHA-256: {c13_sha}")

    f_count, w_count, val_out = run_validator(c13_dst)
    vsummary = f"FAIL={f_count} WARN={w_count} (expected FAILs: Siemens geometry shell — JR/electrode dimensions are Siemens values)"
    print(f"  Validator: {vsummary}")
    validator_log.append(("C13", "C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm", vsummary, val_out))

    matrix_rows.append(make_row(
        "C13", "C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm",
        BASELINE_SHA256, c13_sha,
        "Siemens Physical Cell Description + Detailed Builder; project SIMMOD/MODELMAP/RCR retained",
        get_sv("m_dSepFeedLength_mm"), get_sv("m_dSepTailLength_mm"),
        get_sv("m_dElectrodeOverlapAtStart_mm"), get_sv("m_dElectrodeOverlapAtEnd_mm"),
        get_sv("m_dMandrelWidth_mm"), get_sv("m_dJellyrollWidth_mm"),
        "Strongest geometry-vs-model localization control. Siemens geometry with project RCR model. "
        "If C12 passes but C13 fails: E004 involves Physical Cell Description interaction. "
        "If C13 passes: confirms E004 is localized to project Detailed Builder content.",
    ))

    if not all_protected_ok:
        print("\nABORT: protected field parity failures in C01-C11 — see above.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 8. Campaign matrix — CSV
    # ------------------------------------------------------------------
    print(f"\n[7] Writing CAMPAIGN_MATRIX.csv")
    csv_path = OUT_DIR / "CAMPAIGN_MATRIX.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(matrix_rows)
    print(f"  {csv_path}")

    # ------------------------------------------------------------------
    # 9. Campaign matrix — Markdown
    # ------------------------------------------------------------------
    print(f"[8] Writing CAMPAIGN_MATRIX.md")
    md_path = OUT_DIR / "CAMPAIGN_MATRIX.md"
    md = [
        "# E004 Diagnostic Campaign Matrix — 2026-09-10",
        "",
        f"Baseline: `out/hp2170NCA-RCR-distributed-exact-contact-final.tbm`  ",
        f"Baseline SHA-256: `{BASELINE_SHA256}`  ",
        f"Baseline source: commit `{BASELINE_GIT_COMMIT}`",
        "",
        "Recommended test order: C00, C03, C01, C02, C10, C12, C13, C05, C07, C04, C06, C08, C09, C11",
        "",
        "Runtime result columns are blank — to be filled from Robert's test results.",
        "",
        "---",
        "",
    ]
    for row in matrix_rows:
        md += [
            f"## {row['id']} — `{row['filename']}`",
            "",
            f"**SHA-256:** `{row['sha256']}`  ",
            f"**Base SHA-256:** `{row['base_sha256']}`",
            f"**Changed fields:** {row['changed_fields']}",
            f"**Purpose:** {row['expected_purpose']}",
            "",
            "| Parameter | Value |",
            "|---|---|",
            f"| sep_feed_mm | {row['sep_feed_mm']} |",
            f"| sep_tail_mm | {row['sep_tail_mm']} |",
            f"| overlap_start_mm | {row['overlap_start_mm']} |",
            f"| overlap_end_mm | {row['overlap_end_mm']} |",
            f"| mandrel_width_mm | {row['mandrel_width_mm']} |",
            f"| jr_width_mm | {row['jr_width_mm']} |",
            "",
            "**Runtime result:** *(pending)*",
            "",
            "---",
            "",
        ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  {md_path}")

    # ------------------------------------------------------------------
    # 10. README.txt
    # ------------------------------------------------------------------
    print(f"[9] Writing README.txt")
    readme_path = OUT_DIR / "README.txt"
    readme_path.write_text(README_TEXT, encoding="utf-8")
    print(f"  {readme_path}")

    # ------------------------------------------------------------------
    # 11. Build ZIP
    # ------------------------------------------------------------------
    print(f"\n[10] Building ZIP: {ZIP_PATH.name}")
    zip_member_order = [
        ("README.txt",           OUT_DIR / "README.txt"),
        ("CAMPAIGN_MATRIX.csv",  OUT_DIR / "CAMPAIGN_MATRIX.csv"),
        ("CAMPAIGN_MATRIX.md",   OUT_DIR / "CAMPAIGN_MATRIX.md"),
        ("C00_SIEMENS_CONTROL_validationBattery.tbm",   OUT_DIR / "C00_SIEMENS_CONTROL_validationBattery.tbm"),
        ("C01_FEED10.tbm",                              OUT_DIR / "C01_FEED10.tbm"),
        ("C02_TAIL85.tbm",                              OUT_DIR / "C02_TAIL85.tbm"),
        ("C03_FEED10_TAIL85.tbm",                       OUT_DIR / "C03_FEED10_TAIL85.tbm"),
        ("C04_END40.tbm",                               OUT_DIR / "C04_END40.tbm"),
        ("C05_FEED10_TAIL85_END40.tbm",                 OUT_DIR / "C05_FEED10_TAIL85_END40.tbm"),
        ("C06_MANDRELWIDTH0.tbm",                       OUT_DIR / "C06_MANDRELWIDTH0.tbm"),
        ("C07_FEED10_TAIL85_MANDRELWIDTH0.tbm",         OUT_DIR / "C07_FEED10_TAIL85_MANDRELWIDTH0.tbm"),
        ("C08_JRWIDTH65p11.tbm",                        OUT_DIR / "C08_JRWIDTH65p11.tbm"),
        ("C09_FEED10_TAIL85_JRWIDTH65p11.tbm",          OUT_DIR / "C09_FEED10_TAIL85_JRWIDTH65p11.tbm"),
        ("C10_STAR_BUILDER_PATTERN.tbm",                OUT_DIR / "C10_STAR_BUILDER_PATTERN.tbm"),
        ("C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm",   OUT_DIR / "C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm"),
        ("C12_FULL_SIEMENS_DETAILED_BUILDER.tbm",       OUT_DIR / "C12_FULL_SIEMENS_DETAILED_BUILDER.tbm"),
        ("C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm",  OUT_DIR / "C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm"),
    ]

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, src in zip_member_order:
            zf.write(src, arcname)
            print(f"  + {arcname}")

    zip_sha = sha256_file(ZIP_PATH)

    # Verify member list
    with zipfile.ZipFile(ZIP_PATH) as zf:
        actual = sorted(zf.namelist())
    expected = sorted(a for a, _ in zip_member_order)
    if actual != expected:
        print(f"ABORT: ZIP member mismatch\n  expected: {expected}\n  actual: {actual}")
        sys.exit(1)
    print(f"  Members verified: {len(actual)}")
    print(f"  ZIP SHA-256: {zip_sha}")

    # ------------------------------------------------------------------
    # 12. Completion report
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CAMPAIGN COMPLETION REPORT")
    print("=" * 70)
    print(f"\nBranch: tbm-rcr-modelmap-fix-exec")
    print(f"Generator: tools/generate_e004_multifile_campaign.py")
    print(f"\nVerified baseline SHA-256: {BASELINE_SHA256}")
    print(f"Baseline source: commit {BASELINE_GIT_COMMIT}")
    print(f"\nTBMs in package: 14 (C00-C13)")
    print(f"\nC00 source: {SIEMENS_CONTROL_SRC}")
    print(f"C00 SHA-256: {c00_sha}")
    print(f"\nC01-C13 SHA-256 values and deltas:")
    for row in matrix_rows[1:]:
        print(f"  {row['id']:4s}  {row['sha256']}  |  {row['changed_fields'][:60]}")
    print(f"\nValidator results (all variants):")
    for vid, fname, vsummary, _ in validator_log:
        print(f"  {vid:4s}  {vsummary}")
    print(f"\nProtected field parity (C01-C11): {'PASS' if all_protected_ok else 'FAIL'}")
    print(f"Protected field parity (C12, C13): NOT CHECKED (intentional geometry transplant)")
    print(f"\nCampaign matrix:")
    print(f"  CSV: {csv_path}")
    print(f"  MD:  {md_path}")
    print(f"\nZIP: {ZIP_PATH}")
    print(f"ZIP SHA-256: {zip_sha}")
    print(f"\nZIP members ({len(actual)}):")
    for m in sorted(actual):
        print(f"  {m}")
    print(f"\nNothing was sent to Robert.")
    print(f"E004 is NOT declared resolved.")
    print(f"\nDone.")

    return {
        "baseline_sha": BASELINE_SHA256,
        "c00_sha": c00_sha,
        "zip_sha": zip_sha,
        "matrix_rows": matrix_rows,
        "validator_log": validator_log,
    }


if __name__ == "__main__":
    main()
