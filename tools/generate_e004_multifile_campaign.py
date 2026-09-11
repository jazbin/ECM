#!/usr/bin/env python3
"""
Deterministic generator — STAR E004 Multifile Diagnostic Campaign C00-C17.

Campaign documents:
  tbm_validation/STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_20260910.md
  tbm_validation/STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_ADDENDUM_20260910.md
  tbm_validation/STAR_E004_AXIAL_RECESS_IMPORT_AND_ELECTRICAL_ADDENDUM_20260910.md
  (each addendum extends/takes precedence over prior documents)

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

# Baseline axial geometry values (from the Robert-tested failed baseline)
BASELINE_PKG_HEIGHT  = 65.11
BASELINE_SEP_WIDTH   = 67.11
BASELINE_NEG_WIDTH   = 65.11
BASELINE_POS_WIDTH   = 64.11

SIEMENS_CONTROL_SRC = REPO_ROOT / "tbm_validation/in_StarCCM_bds/validationBattery.tbm"
VALIDATOR           = REPO_ROOT / "tools/validate_tbm.py"

OUT_DIR  = REPO_ROOT / "out/e004_multifile_campaign_20260910"
ZIP_PATH = REPO_ROOT / "out/hp2170NCA-STAR-E004-multifile-diagnostic-20260910.zip"

# ---------------------------------------------------------------------------
# C01-C11 field-level delta definitions (BUILDER block changes)
# All deltas apply only to the first <BUILDER>...</BUILDER> block.
# old_val and new_val are the exact strings as they appear in the TBM.
# ---------------------------------------------------------------------------

FIELD_VARIANTS = [
    {
        "id": "C01", "filename": "C01_FEED10.tbm",
        "deltas": {"m_dSepFeedLength_mm": ("0", "10")},
        "purpose": "Isolate separator feed length: feed=10 alone vs E004.",
        "sep_feed": 10, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
    },
    {
        "id": "C02", "filename": "C02_TAIL85.tbm",
        "deltas": {"m_dSepTailLength_mm": ("0", "85")},
        "purpose": "Isolate separator tail length: tail=85 alone vs E004.",
        "sep_feed": 0, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
    },
    {
        "id": "C03", "filename": "C03_FEED10_TAIL85.tbm",
        "deltas": {"m_dSepFeedLength_mm": ("0", "10"), "m_dSepTailLength_mm": ("0", "85")},
        "purpose": "H004-5 leading hypothesis: combined feed+tail.",
        "sep_feed": 10, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
    },
    {
        "id": "C04", "filename": "C04_END40.tbm",
        "deltas": {"m_dElectrodeOverlapAtEnd_mm": ("20", "40")},
        "purpose": "Isolate end-overlap influence on E004.",
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 40, "mw": 6, "jrw": 0,
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
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
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
    },
    {
        "id": "C06", "filename": "C06_MANDRELWIDTH0.tbm",
        "deltas": {"m_dMandrelWidth_mm": ("6", "0")},
        "purpose": "STAR round-mandrel convention: MandrelWidth=0 alone vs E004.",
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 0, "jrw": 0,
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
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
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
    },
    {
        "id": "C08", "filename": "C08_JRWIDTH65p11.tbm",
        "deltas": {"m_dJellyrollWidth_mm": ("0", "65.11")},
        "purpose": "Low-probability probe: JellyrollWidth zero in Detailed Builder.",
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 65.11,
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
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
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
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
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
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
        "pkg": BASELINE_PKG_HEIGHT, "sep_w": BASELINE_SEP_WIDTH,
        "neg_w": BASELINE_NEG_WIDTH, "pos_w": BASELINE_POS_WIDTH,
    },
]

# ---------------------------------------------------------------------------
# C14-C17 — axial clearance / recession variants (PCD + optional BUILDER changes)
# All source: same immutable baseline commit d74b328...
# PCD deltas apply to <Physical Cell Description> block.
# Builder deltas apply to first <BUILDER> block.
# ---------------------------------------------------------------------------

# Target axial margins matching Siemens validationBattery.tbm pattern:
#   package - separator = +1.00 mm
#   package - negative  = +3.00 mm
#   package - positive  = +4.00 mm
#   separator - negative = +2.00 mm
#   negative - positive  = +1.00 mm

AXIAL_VARIANTS = [
    {
        "id": "C14",
        "filename": "C14_AXIAL_CAVITY68p11.tbm",
        "pcd_deltas": {
            "Package m_dintHeight": ("65.11", "68.11"),
        },
        "builder_deltas": {},
        "pkg": 68.11, "sep_w": 67.11, "neg_w": 65.11, "pos_w": 64.11,
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
        "purpose": (
            "Axial cavity clearance only: Package m_dintHeight 65.11->68.11 gives "
            "pkg-sep=+1, pkg-neg=+3, pkg-pos=+4 mm (Siemens margins) while retaining "
            "all electrode/separator widths. DIAGNOSTIC ONLY — not production target."
        ),
    },
    {
        "id": "C15",
        "filename": "C15_AXIAL_CAVITY68p11_FEED10_TAIL85.tbm",
        "pcd_deltas": {
            "Package m_dintHeight": ("65.11", "68.11"),
        },
        "builder_deltas": {
            "m_dSepFeedLength_mm": ("0", "10"),
            "m_dSepTailLength_mm": ("0", "85"),
        },
        "pkg": 68.11, "sep_w": 67.11, "neg_w": 65.11, "pos_w": 64.11,
        "sep_feed": 10, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
        "purpose": (
            "Axial cavity clearance + feed/tail leading hypothesis: both strongest independent "
            "geometry suspects combined. If C03 fails but C15 passes, axial package clearance "
            "participates in E004. DIAGNOSTIC ONLY."
        ),
    },
    {
        "id": "C16",
        "filename": "C16_RECESSED_LAYERS_FIXED_CAVITY.tbm",
        "pcd_deltas": {
            "SeparatorList1_Separator m_dWidth_mm": ("67.11", "64.11"),
            "+Electrode m_dWidth":          ("64.11", "61.11"),
            "+Electrode m_dCoatingWidth":   ("64.11", "61.11"),
            "+Electrode Collector m_dWidth_mm": ("64.11", "61.11"),
            "-Electrode m_dWidth":          ("65.11", "62.11"),
            "-Electrode m_dCoatingWidth":   ("65.11", "62.11"),
            "-Electrode Collector m_dWidth_mm": ("65.11", "62.11"),
        },
        "builder_deltas": {},
        "pkg": 65.11, "sep_w": 64.11, "neg_w": 62.11, "pos_w": 61.11,
        "sep_feed": 0, "sep_tail": 0, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
        "purpose": (
            "Explicit layer recession inside original 65.11 mm cavity: all electrode/separator "
            "widths reduced by 3 mm so pkg-sep=+1, pkg-neg=+3, pkg-pos=+4 mm. "
            "DIAGNOSTIC ONLY — do not use for electrical equivalence assessment. "
            "Physical electrode widths alter active area and RCR mapping. "
            "Tab widths, tape widths, S1-S6, RCR data, radial geometry unchanged."
        ),
    },
    {
        "id": "C17",
        "filename": "C17_RECESSED_LAYERS_FEED10_TAIL85.tbm",
        "pcd_deltas": {
            "SeparatorList1_Separator m_dWidth_mm": ("67.11", "64.11"),
            "+Electrode m_dWidth":          ("64.11", "61.11"),
            "+Electrode m_dCoatingWidth":   ("64.11", "61.11"),
            "+Electrode Collector m_dWidth_mm": ("64.11", "61.11"),
            "-Electrode m_dWidth":          ("65.11", "62.11"),
            "-Electrode m_dCoatingWidth":   ("65.11", "62.11"),
            "-Electrode Collector m_dWidth_mm": ("65.11", "62.11"),
        },
        "builder_deltas": {
            "m_dSepFeedLength_mm": ("0", "10"),
            "m_dSepTailLength_mm": ("0", "85"),
        },
        "pkg": 65.11, "sep_w": 64.11, "neg_w": 62.11, "pos_w": 61.11,
        "sep_feed": 10, "sep_tail": 85, "ov_start": 8, "ov_end": 20, "mw": 6, "jrw": 0,
        "purpose": (
            "Maximum axial-recession rescue retaining original 65.11 mm package internal height: "
            "all C16 layer-width reductions plus feed=10 tail=85. DIAGNOSTIC ONLY — "
            "do not use for electrical equivalence assessment."
        ),
    },
]

# Protected fields — must be byte-identical between baseline and C01-C11 variants.
# Not enforced for C12/C13 (intentional geometry transplant).
# Not applied globally to C14-C17 (they have controlled PCD changes); instead
# variant-specific protected checks are used below.
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

# For C14/C15: electrode and separator widths must be unchanged from baseline
PROTECTED_FIELDS_C14_C15 = [
    "SeparatorList1_Separator m_dWidth_mm",
    "+Electrode m_dWidth",
    "+Electrode m_dCoatingWidth",
    "+Electrode Collector m_dWidth_mm",
    "-Electrode m_dWidth",
    "-Electrode m_dCoatingWidth",
    "-Electrode Collector m_dWidth_mm",
] + PROTECTED_FIELDS

# For C16/C17: package internal height must be unchanged from baseline
PROTECTED_FIELDS_C16_C17 = [
    "Package m_dintHeight",
] + PROTECTED_FIELDS

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

def count_field_in_pcd(content: str, field: str) -> int:
    p_start, p_end = get_pcd_span(content)
    block = content[p_start:p_end]
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

def apply_pcd_delta(content: str, field: str, old_val: str, new_val: str) -> tuple[str, int]:
    """Replace field=old_val with field=new_val in the Physical Cell Description block only."""
    p_start, p_end = get_pcd_span(content)
    before = content[:p_start]
    block  = content[p_start:p_end]
    after  = content[p_end:]
    pattern     = r'(\t' + re.escape(field) + r'\t=\t)' + re.escape(old_val) + r'([\t\n\r])'
    replacement = r'\g<1>' + new_val + r'\g<2>'
    new_block, n = re.subn(pattern, replacement, block)
    return before + new_block + after, n

def extract_field_lines(content: str, field: str) -> list[str]:
    return [ln for ln in content.splitlines() if field in ln]

def check_protected_fields(baseline: str, variant: str, vid: str,
                           fields: list[str] | None = None) -> list[str]:
    if fields is None:
        fields = PROTECTED_FIELDS
    failures = []
    for pat in fields:
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
    parts = []
    if variant.get("pcd_deltas"):
        for f, (ov, nv) in variant["pcd_deltas"].items():
            parts.append(f"{f}: {ov} -> {nv} [PCD]")
    if variant.get("builder_deltas"):
        for f, (ov, nv) in variant["builder_deltas"].items():
            parts.append(f"{f}: {ov} -> {nv} [BUILDER]")
    if variant.get("deltas"):
        for f, (ov, nv) in variant["deltas"].items():
            parts.append(f"{f}: {ov} -> {nv}")
    return "; ".join(parts)

def axial_margins(pkg: float, sep_w: float, neg_w: float, pos_w: float) -> dict:
    return {
        "package_int_height_mm": pkg,
        "separator_width_mm": sep_w,
        "negative_width_mm": neg_w,
        "positive_width_mm": pos_w,
        "package_minus_separator_mm": round(pkg - sep_w, 4),
        "package_minus_negative_mm": round(pkg - neg_w, 4),
        "package_minus_positive_mm": round(pkg - pos_w, 4),
    }

def parse_axial_from_content(content: str) -> dict | None:
    """Parse the four canonical axial geometry values from TBM content.
    Returns None if any field is missing (e.g. a geometry-less TBM section)."""
    def extract(field):
        m = re.search(r'\t' + re.escape(field) + r'\t=\t([0-9.+-]+)', content)
        return float(m.group(1)) if m else None
    pkg = extract("Package m_dintHeight")
    sep = extract("SeparatorList1_Separator m_dWidth_mm")
    neg = extract("-Electrode m_dWidth")
    pos = extract("+Electrode m_dWidth")
    if any(v is None for v in [pkg, sep, neg, pos]):
        return None
    return axial_margins(pkg, sep, neg, pos)

def assert_axial_regression(row: dict, parsed: dict | None, vid: str) -> None:
    """Abort if matrix axial values do not match values parsed from the emitted TBM.
    Skips numeric check when a row field is 'N/A' (C00 builder params) or when
    parsed is None (TBM lacks a PCD — should not occur in this campaign)."""
    if parsed is None:
        print(f"  ABORT [{vid}]: parse_axial_from_content returned None — "
              f"required PCD fields missing from generated TBM")
        sys.exit(1)
    AXIAL_KEYS = [
        "package_int_height_mm", "separator_width_mm",
        "negative_width_mm", "positive_width_mm",
        "package_minus_separator_mm", "package_minus_negative_mm",
        "package_minus_positive_mm",
    ]
    mismatches = []
    for k in AXIAL_KEYS:
        rval = row.get(k)
        pval = parsed.get(k)
        if rval in ("N/A", "", None):
            continue
        try:
            if abs(float(rval) - float(pval)) > 0.001:
                mismatches.append(f"    {k}: matrix={rval}, parsed-from-TBM={pval}")
        except (TypeError, ValueError):
            mismatches.append(f"    {k}: cannot compare matrix={rval!r} vs parsed={pval!r}")
    if mismatches:
        print(f"  ABORT [{vid}]: axial regression — matrix values do not match parsed TBM:")
        for m in mismatches:
            print(m)
        sys.exit(1)
    print(f"    Axial regression: PASS")

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
    Replace the first <BUILDER>...</BUILDER> block in the project baseline with
    the complete Detailed Builder block from validationBattery.tbm.
    Returns (file_bytes, block_diff_text).
    """
    pb_start, pb_end = get_first_builder_span(proj_content)
    sb_start, sb_end = get_first_builder_span(siemens_content)

    proj_builder    = proj_content[pb_start:pb_end]
    siemens_builder = normalize_lf(siemens_content[sb_start:sb_end])

    c12_content = proj_content[:pb_start] + siemens_builder + proj_content[pb_end:]

    proj_lines    = proj_builder.splitlines()
    siemens_lines = siemens_builder.splitlines()
    diff_lines = ["--- project Detailed Builder", "+++ Siemens validationBattery Detailed Builder", ""]
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
    pp_start, pp_end = get_pcd_span(proj_content)
    pb_start, pb_end = get_first_builder_span(proj_content)

    sp_start, sp_end = get_pcd_span(siemens_content)
    sb_start, sb_end = get_first_builder_span(siemens_content)
    siemens_pcd     = normalize_lf(siemens_content[sp_start:sp_end])
    siemens_builder = normalize_lf(siemens_content[sb_start:sb_end])

    pcd_to_b1_sep = proj_content[pp_end:pb_start]

    c13_content = (
        proj_content[:pp_start]
        + siemens_pcd
        + pcd_to_b1_sep
        + siemens_builder
        + proj_content[pb_end:]
    )
    return c13_content.encode("latin-1")

# ---------------------------------------------------------------------------
# Campaign matrix helpers
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "id", "filename", "base_sha256", "sha256", "changed_fields",
    "sep_feed_mm", "sep_tail_mm", "overlap_start_mm", "overlap_end_mm",
    "mandrel_width_mm", "jr_width_mm",
    "package_int_height_mm", "separator_width_mm", "negative_width_mm", "positive_width_mm",
    "package_minus_separator_mm", "package_minus_negative_mm", "package_minus_positive_mm",
    "expected_purpose",
    "runtime_result", "runtime_error_class", "runtime_notes",
]

BASELINE_AXIAL = axial_margins(BASELINE_PKG_HEIGHT, BASELINE_SEP_WIDTH,
                               BASELINE_NEG_WIDTH, BASELINE_POS_WIDTH)

def make_row(id_, filename, base_sha, sha, changed, sf, st, os_, oe, mw, jrw, purpose,
             pkg=BASELINE_PKG_HEIGHT, sep_w=BASELINE_SEP_WIDTH,
             neg_w=BASELINE_NEG_WIDTH, pos_w=BASELINE_POS_WIDTH):
    ax = axial_margins(pkg, sep_w, neg_w, pos_w)
    return {
        "id": id_, "filename": filename, "base_sha256": base_sha, "sha256": sha,
        "changed_fields": changed, "sep_feed_mm": sf, "sep_tail_mm": st,
        "overlap_start_mm": os_, "overlap_end_mm": oe, "mandrel_width_mm": mw,
        "jr_width_mm": jrw,
        "package_int_height_mm": ax["package_int_height_mm"],
        "separator_width_mm": ax["separator_width_mm"],
        "negative_width_mm": ax["negative_width_mm"],
        "positive_width_mm": ax["positive_width_mm"],
        "package_minus_separator_mm": ax["package_minus_separator_mm"],
        "package_minus_negative_mm": ax["package_minus_negative_mm"],
        "package_minus_positive_mm": ax["package_minus_positive_mm"],
        "expected_purpose": purpose,
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
geometry fields so that test results can isolate the cause.

Campaign covers: Detailed Builder fields (C01-C11), full Siemens transplants
(C12-C13), and axial clearance / recession variants (C14-C17).

FILES (18 total)

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
    Highest-probability feed/tail fix candidate.

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
    Siemens Detailed Builder transplanted into project file; project Physical
    Cell Description, SIMMOD, MODELMAP and RCR data retained.
    Diagnostic only.

C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm
    Both the Physical Cell Description and Detailed Builder from Siemens
    validationBattery.tbm, with project MODELMAP, RCRTable 3D SIMMOD, General
    Electrolyte SIMMOD, and Distributed Thermal SIMMOD retained.
    Diagnostic only.

C12/C13 PAIRED INTERPRETATION

Use C12 and C13 results together, not individually:

    C12 PASS:
        Replacing the project Detailed Builder with the Siemens Builder is
        sufficient to clear E004 under the project Physical Cell Description.
        Strongly localizes E004 to project Detailed Builder content.

    C12 PASS + C13 PASS:
        Project Detailed Builder is the dominant localization result.

    C12 FAIL + C13 PASS:
        The Siemens Physical Cell Description (in addition to the Siemens
        Builder) was needed to clear E004. Project PCD or PCD/Builder
        interaction is implicated.

    C12 PASS + C13 FAIL:
        Anomalous cross-interaction: Siemens PCD combined with project
        model/SIMMOD context introduces a failure. Treat separately from
        the standard localization sequence.

    C12 FAIL + C13 FAIL while C00 PASS:
        E004 is not eliminated by Siemens geometry transplants inside the
        project model context. Investigate geometry/model coupling or
        non-transplanted sections.

C14_AXIAL_CAVITY68p11.tbm
    Delta: Package m_dintHeight 65.11 -> 68.11 only.
    Gives pkg-sep=+1, pkg-neg=+3, pkg-pos=+4 mm (Siemens clearance margins)
    while retaining all electrode/separator widths unchanged.
    Diagnostic only. Not a production geometry candidate.

C15_AXIAL_CAVITY68p11_FEED10_TAIL85.tbm
    Delta: Package m_dintHeight 65.11 -> 68.11, Feed=10, Tail=85.
    Tests the two strongest independent geometry hypotheses together.
    Diagnostic only.

C16_RECESSED_LAYERS_FIXED_CAVITY.tbm
    Delta: Separator width 67.11->64.11, NegElectrode widths 65.11->62.11,
    PosElectrode widths 64.11->61.11. Package internal height unchanged at 65.11.
    Achieves same Siemens clearance margins via layer recession rather than
    cavity enlargement. DIAGNOSTIC ONLY. Physical electrode widths alter active
    area and RCR spatial mapping. Do not use for electrical equivalence.

C17_RECESSED_LAYERS_FEED10_TAIL85.tbm
    Delta: All C16 layer-width reductions plus Feed=10 Tail=85.
    Maximum axial-recession rescue retaining original package height.
    DIAGNOSTIC ONLY. Do not use for electrical equivalence.

AXIAL GEOMETRY CONTEXT

The failed project baseline has these axial margins:
    Package internal height:  65.11 mm
    Separator width:          67.11 mm  -> pkg - sep = -2.00 mm
    Negative electrode width: 65.11 mm  -> pkg - neg =  0.00 mm
    Positive electrode width: 64.11 mm  -> pkg - pos = +1.00 mm

Siemens validationBattery.tbm reference margins:
    pkg - sep = +1.00 mm
    pkg - neg = +3.00 mm
    pkg - pos = +4.00 mm

C14/C15 restore Siemens margins by enlarging the package cavity.
C16/C17 restore Siemens margins by recessing the electrode/separator layers.

The nested layer relationship (separator - negative = 2 mm, negative -
positive = 1 mm) is the same in both the project and Siemens reference.

WHAT TO DO

Before any Create from Tbm runs, please send ONE screenshot of the complete
"Import Battery Options" dialog that appears when you select a TBM, showing
all available selectable object/checkbox names. If the full list does not fit
in one screenshot, send as many as needed.

Run Batteries > Battery Cell > Create from Tbm for all 18 files.

Recommended order:
    C00   Siemens environment control
    C03   feed+tail leading hypothesis
    C14   axial cavity clearance only
    C15   axial cavity + feed/tail
    C16   recessed layers fixed cavity
    C17   recessed layers + feed/tail
    C10   broad STAR-pattern rescue
    C12   full Siemens Detailed Builder
    C13   Siemens geometry shell / project RCR
    C05, C07, C04, C06, C08, C09, C11  remaining isolation variants
    C01, C02  individual feed/tail isolations

Return results in this exact format:

    C00: PASS / <exact error text>
    C01: PASS / <exact error text>
    ...
    C17: PASS / <exact error text>

    E00 RCR-data-only import: PASS / <exact error or warning>

    Import-options screenshot: attached

IMPORTANT

If a file creates geometry successfully, record PASS and continue testing all
remaining files.

If STAR reaches a DIFFERENT error than "Electrode Root 1", report that full
error text. A different error means E004 was cleared for that variant, which
is important diagnostic information even if full creation did not succeed.

The exact error text matters. Do not reduce a different downstream blocker
to just FAIL — report what STAR actually says.

C16 and C17 are geometry diagnostics and MUST NOT be used for production
electrical simulations even if they import. Reduced electrode widths alter
active area and RCR spatial mapping.

E00 — RCR DATA-ONLY IMPORT (independent control, can be done at any time)

This control bypasses the 3D cylindrical CAD builder entirely and tests
whether the project TBM's RCR electrical data can be ingested independently.

Steps:
    1. In STAR-CCM+, create a User Defined Battery Cell.
    2. Select the RCR Model.
    3. Under the RCR equivalent-circuit model, select
       "Extract RCR Parameters from TBM File".
    4. Choose the project TBM:
       hp2170NCA-RCR-distributed-exact-contact-final.tbm
       SHA-256: 2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5
    5. Record whether RCR parameter tables are created.

Expected result if RCR data are valid:
    3 temperature-condition RCR parameter tables
    288.15 K / 298.15 K / 308.15 K

Record as: E00_RCR_DATA_ONLY_IMPORT: PASS / <exact error>

Interpretation:
    E00 PASS + Create-from-Tbm E004 FAIL
        -> RCR numerical/model data are separable from the CAD-builder failure.
           E004 is isolated to geometry construction, not RCR table content.
    E00 FAIL
        -> there is an electrical/model-data problem in addition to geometry.

E00 PASS does not prove correct distributed 3D spatial mapping or terminal
connectivity. It confirms only that STAR can parse the RCR tables.

IMPORT OPTIONS — SCHEMA CAPTURE

Please send a screenshot of the "Import Battery Options" dialog with all
selectable object names visible. Your exact STAR version determines what
appears in this dialog and we must not guess the names.

This screenshot is needed before we can design selective-import tests (Ixx)
that intentionally omit specific object types. No selective-import runs are
requested in this package — only the screenshot/list is needed now.
"""

# ---------------------------------------------------------------------------
# IMPORT_SELECTION_MATRIX template rows (I00-I05, to be filled after screenshot)
# ---------------------------------------------------------------------------

IMPORT_CSV_FIELDS = [
    "id", "tbm_id", "exact_import_object_selection",
    "cell_node_created", "geometry_created", "e004_present", "new_error_text",
    "unit_cell_model", "electrical_mesh_present",
    "core_parts_populated", "positive_tab_parts_populated", "negative_tab_parts_populated",
    "electrical_completeness", "notes",
]

IMPORT_ROWS = [
    {
        "id": "I00", "tbm_id": "TBD — use a passing Cxx TBM once known",
        "exact_import_object_selection": "ALL OBJECTS (normal workflow reference)",
        "cell_node_created": "", "geometry_created": "", "e004_present": "",
        "new_error_text": "", "unit_cell_model": "", "electrical_mesh_present": "",
        "core_parts_populated": "", "positive_tab_parts_populated": "",
        "negative_tab_parts_populated": "", "electrical_completeness": "",
        "notes": "Reference for all-objects import. Identical selection to main Cxx campaign.",
    },
    {
        "id": "I01", "tbm_id": "TBD",
        "exact_import_object_selection": "MODEL/DATA ONLY — geometry deselected (if dialog allows)",
        "cell_node_created": "", "geometry_created": "", "e004_present": "",
        "new_error_text": "", "unit_cell_model": "", "electrical_mesh_present": "",
        "core_parts_populated": "", "positive_tab_parts_populated": "",
        "negative_tab_parts_populated": "", "electrical_completeness": "",
        "notes": "Purpose: prove E004 is isolated to geometry. PASS does not prove usable distributed 3D sim.",
    },
    {
        "id": "I02", "tbm_id": "TBD",
        "exact_import_object_selection": "CORE/JELLYROLL + BOTH TAB OBJECTS — omit package/can/cap if allowed. EXACT NAMES FROM ROBERT SCREENSHOT REQUIRED.",
        "cell_node_created": "", "geometry_created": "", "e004_present": "",
        "new_error_text": "", "unit_cell_model": "", "electrical_mesh_present": "",
        "core_parts_populated": "", "positive_tab_parts_populated": "",
        "negative_tab_parts_populated": "", "electrical_completeness": "",
        "notes": "Minimum geometry likely required for distributed 3D electrical core. Check Section F electrical completeness.",
    },
    {
        "id": "I03", "tbm_id": "TBD",
        "exact_import_object_selection": "CORE/JELLYROLL + BOTH TAB OBJECTS + CAN/CAP — omit detailed electrode/root if separately selectable. EXACT NAMES FROM ROBERT SCREENSHOT REQUIRED.",
        "cell_node_created": "", "geometry_created": "", "e004_present": "",
        "new_error_text": "", "unit_cell_model": "", "electrical_mesh_present": "",
        "core_parts_populated": "", "positive_tab_parts_populated": "",
        "negative_tab_parts_populated": "", "electrical_completeness": "",
        "notes": "Candidate minimal electrothermal topology. Must pass electrical-completeness audit before production.",
    },
    {
        "id": "I04", "tbm_id": "TBD",
        "exact_import_object_selection": "CAN/CAP + JELLYROLL/CORE — intentionally omit electrical tab/root objects. EXACT NAMES FROM ROBERT SCREENSHOT REQUIRED.",
        "cell_node_created": "", "geometry_created": "", "e004_present": "",
        "new_error_text": "", "unit_cell_model": "", "electrical_mesh_present": "",
        "core_parts_populated": "", "positive_tab_parts_populated": "",
        "negative_tab_parts_populated": "", "electrical_completeness": "GEOMETRY_ONLY_DIAGNOSTIC",
        "notes": "Geometry-only diagnostic for contact topology. DO NOT use for production electrical simulation.",
    },
    {
        "id": "I05", "tbm_id": "TBD",
        "exact_import_object_selection": "ALL OBJECTS EXCEPT the object associated with Electrode Root 1 (one-object omission test). EXACT NAME FROM ROBERT SCREENSHOT REQUIRED.",
        "cell_node_created": "", "geometry_created": "", "e004_present": "",
        "new_error_text": "", "unit_cell_model": "", "electrical_mesh_present": "",
        "core_parts_populated": "", "positive_tab_parts_populated": "",
        "negative_tab_parts_populated": "", "electrical_completeness": "",
        "notes": "High-value: if omitting one object clears E004, that object is directly associated with the failing construction path.",
    },
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("STAR E004 Multifile Diagnostic Campaign Generator — C00-C17")
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

    # C00 axial values must come from the Siemens TBM, not from project-baseline defaults.
    siemens_axial = parse_axial_from_content(siemens_str)
    if siemens_axial is None:
        print("ABORT: could not parse axial fields from Siemens validationBattery.tbm")
        sys.exit(1)
    print(f"  Siemens axial: pkg={siemens_axial['package_int_height_mm']} "
          f"sep={siemens_axial['separator_width_mm']} "
          f"neg={siemens_axial['negative_width_mm']} "
          f"pos={siemens_axial['positive_width_mm']}")

    c00_row = make_row(
        "C00", "C00_SIEMENS_CONTROL_validationBattery.tbm",
        "N/A — Siemens install reference", c00_sha,
        "N/A — unmodified Siemens reference",
        "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
        "Environment/import-path control. Proves Robert's STAR install and "
        "Create from Tbm workflow import a known Siemens cylindrical TBM.",
        pkg=siemens_axial["package_int_height_mm"],
        sep_w=siemens_axial["separator_width_mm"],
        neg_w=siemens_axial["negative_width_mm"],
        pos_w=siemens_axial["positive_width_mm"],
    )
    assert_axial_regression(c00_row, siemens_axial, "C00")
    matrix_rows.append(c00_row)

    # ------------------------------------------------------------------
    # 5. C01-C11 — field-level delta variants (BUILDER only)
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

        prot_failures = check_protected_fields(baseline_str, content, vid)
        if prot_failures:
            all_protected_ok = False
            for msg in prot_failures:
                print(msg)
        else:
            print(f"    Protected fields: PASS")

        f_count, w_count, val_out = run_validator(dst)
        vsummary = f"FAIL={f_count} WARN={w_count}"
        print(f"    Validator: {vsummary}")
        validator_log.append((vid, filename, vsummary, val_out))

        row = make_row(
            vid, filename, BASELINE_SHA256, file_sha, delta_summary(v),
            v["sep_feed"], v["sep_tail"], v["ov_start"], v["ov_end"],
            v["mw"], v["jrw"], v["purpose"],
            pkg=v.get("pkg", BASELINE_PKG_HEIGHT),
            sep_w=v.get("sep_w", BASELINE_SEP_WIDTH),
            neg_w=v.get("neg_w", BASELINE_NEG_WIDTH),
            pos_w=v.get("pos_w", BASELINE_POS_WIDTH),
        )
        assert_axial_regression(row, parse_axial_from_content(content), vid)
        matrix_rows.append(row)

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

    sbi = siemens_str[siemens_str.index("<BUILDER>"):siemens_str.index("</BUILDER>") + len("</BUILDER>")]
    def get_sv(field, default="?"):
        m = re.search(r'\t' + re.escape(field) + r'\t=\t([^\t\n]+)', sbi)
        return m.group(1) if m else default

    # C12 retains the project PCD, so axial geometry values are project-baseline values.
    c12_str = c12_bytes.decode("latin-1")
    c12_axial = parse_axial_from_content(c12_str)
    c12_row = make_row(
        "C12", "C12_FULL_SIEMENS_DETAILED_BUILDER.tbm",
        BASELINE_SHA256, c12_sha,
        "Complete Detailed Builder block replaced with Siemens validationBattery.tbm BUILDER",
        get_sv("m_dSepFeedLength_mm"), get_sv("m_dSepTailLength_mm"),
        get_sv("m_dElectrodeOverlapAtStart_mm"), get_sv("m_dElectrodeOverlapAtEnd_mm"),
        get_sv("m_dMandrelWidth_mm"), get_sv("m_dJellyrollWidth_mm"),
        "Broad localization control: full Siemens Detailed Builder inside project Physical Cell Description. "
        "C12 PASS: replacing the project Detailed Builder with the Siemens Builder is sufficient to clear E004 "
        "under the project PCD — strongly localizes E004 to project Detailed Builder content. "
        "C12 FAIL with C00 PASS: project Detailed Builder alone does not explain E004; "
        "see C13 result to determine whether PCD or PCD/Builder interaction is involved.",
        pkg=BASELINE_PKG_HEIGHT, sep_w=BASELINE_SEP_WIDTH,
        neg_w=BASELINE_NEG_WIDTH, pos_w=BASELINE_POS_WIDTH,
    )
    assert_axial_regression(c12_row, c12_axial, "C12")
    matrix_rows.append(c12_row)

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

    # C13 contains the Siemens PCD, so axial geometry values must be parsed from the
    # generated C13 bytes — they are Siemens values, NOT project-baseline values.
    c13_str = c13_bytes.decode("latin-1")
    c13_axial = parse_axial_from_content(c13_str)
    c13_row = make_row(
        "C13", "C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm",
        BASELINE_SHA256, c13_sha,
        "Siemens Physical Cell Description + Detailed Builder; project SIMMOD/MODELMAP/RCR retained",
        get_sv("m_dSepFeedLength_mm"), get_sv("m_dSepTailLength_mm"),
        get_sv("m_dElectrodeOverlapAtStart_mm"), get_sv("m_dElectrodeOverlapAtEnd_mm"),
        get_sv("m_dMandrelWidth_mm"), get_sv("m_dJellyrollWidth_mm"),
        "Strongest geometry-vs-model localization control. Siemens PCD and Detailed Builder, project RCR/SIMMOD retained. "
        "Paired interpretation with C12: "
        "C12 PASS + C13 PASS — project Detailed Builder is the dominant localization. "
        "C12 FAIL + C13 PASS — Siemens PCD (in addition to Builder) was needed; project PCD or PCD-Builder interaction implicated. "
        "C12 PASS + C13 FAIL — anomalous: Siemens PCD plus project model/SIMMOD context introduces a failure; treat separately. "
        "C12 FAIL + C13 FAIL while C00 PASS — E004 not eliminated by Siemens geometry transplants inside project model context.",
        pkg=c13_axial["package_int_height_mm"] if c13_axial else BASELINE_PKG_HEIGHT,
        sep_w=c13_axial["separator_width_mm"] if c13_axial else BASELINE_SEP_WIDTH,
        neg_w=c13_axial["negative_width_mm"] if c13_axial else BASELINE_NEG_WIDTH,
        pos_w=c13_axial["positive_width_mm"] if c13_axial else BASELINE_POS_WIDTH,
    )
    assert_axial_regression(c13_row, c13_axial, "C13")
    matrix_rows.append(c13_row)

    if not all_protected_ok:
        print("\nABORT: protected field parity failures in C01-C11 — see above.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 8. C14-C17 — axial clearance / recession variants
    # ------------------------------------------------------------------
    print(f"\n[7] Generating C14-C17 (axial clearance/recession variants from baseline)")

    axial_shas = {}
    axial_margins_check = {}

    for v in AXIAL_VARIANTS:
        vid      = v["id"]
        filename = v["filename"]
        dst      = OUT_DIR / filename
        print(f"\n  {vid}  {filename}")
        print(f"    deltas: {delta_summary(v)}")

        content = baseline_str

        # Apply PCD deltas
        pcd_delta_count = 0
        for field, (old_val, new_val) in v["pcd_deltas"].items():
            n_in_pcd = count_field_in_pcd(content, field)
            if n_in_pcd != 1:
                print(f"  ABORT: {vid}: PCD field {field!r} occurs {n_in_pcd} times "
                      f"in Physical Cell Description block (expected 1)")
                sys.exit(1)
            content, replaced = apply_pcd_delta(content, field, old_val, new_val)
            if replaced != 1:
                print(f"  ABORT: {vid}: PCD {field!r} = {old_val!r} -> {new_val!r} "
                      f"replaced {replaced} times (expected 1)")
                sys.exit(1)
            pcd_delta_count += 1

        # Apply BUILDER deltas
        for field, (old_val, new_val) in v["builder_deltas"].items():
            n_before = count_field_in_builder(content, field)
            if n_before != 1:
                print(f"  ABORT: {vid}: BUILDER field {field!r} occurs {n_before} times "
                      f"(expected 1)")
                sys.exit(1)
            content, replaced = apply_field_delta(content, field, old_val, new_val)
            if replaced != 1:
                print(f"  ABORT: {vid}: BUILDER {field!r} = {old_val!r} -> {new_val!r} "
                      f"replaced {replaced} times (expected 1)")
                sys.exit(1)

        total_deltas = pcd_delta_count + len(v["builder_deltas"])
        print(f"    Total field changes applied: {total_deltas} "
              f"({pcd_delta_count} PCD, {len(v['builder_deltas'])} BUILDER)")

        file_bytes = content.encode("latin-1")
        dst.write_bytes(file_bytes)
        file_sha = sha256_bytes(file_bytes)
        axial_shas[vid] = file_sha
        print(f"    SHA-256: {file_sha}")

        # Variant-specific protected field check
        if vid in ("C14", "C15"):
            prot_fields = PROTECTED_FIELDS_C14_C15
        else:
            prot_fields = PROTECTED_FIELDS_C16_C17

        prot_failures = check_protected_fields(baseline_str, content, vid, prot_fields)
        if prot_failures:
            all_protected_ok = False
            for msg in prot_failures:
                print(msg)
        else:
            print(f"    Protected fields: PASS")

        # Verify axial margins
        ax = axial_margins(v["pkg"], v["sep_w"], v["neg_w"], v["pos_w"])
        axial_margins_check[vid] = ax
        print(f"    Axial margins:")
        print(f"      pkg_int_height = {ax['package_int_height_mm']} mm")
        print(f"      separator_w    = {ax['separator_width_mm']} mm")
        print(f"      negative_w     = {ax['negative_width_mm']} mm")
        print(f"      positive_w     = {ax['positive_width_mm']} mm")
        print(f"      pkg - sep      = {ax['package_minus_separator_mm']:+.2f} mm")
        print(f"      pkg - neg      = {ax['package_minus_negative_mm']:+.2f} mm")
        print(f"      pkg - pos      = {ax['package_minus_positive_mm']:+.2f} mm")

        f_count, w_count, val_out = run_validator(dst)
        vsummary = f"FAIL={f_count} WARN={w_count}"
        print(f"    Validator: {vsummary}")
        validator_log.append((vid, filename, vsummary, val_out))

        row = make_row(
            vid, filename, BASELINE_SHA256, file_sha, delta_summary(v),
            v["sep_feed"], v["sep_tail"], v["ov_start"], v["ov_end"],
            v["mw"], v["jrw"], v["purpose"],
            pkg=v["pkg"], sep_w=v["sep_w"], neg_w=v["neg_w"], pos_w=v["pos_w"],
        )
        assert_axial_regression(row, parse_axial_from_content(content), vid)
        matrix_rows.append(row)

    if not all_protected_ok:
        print("\nABORT: protected field parity failures — see above.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 9. Campaign matrix — CSV
    # ------------------------------------------------------------------
    print(f"\n[8] Writing CAMPAIGN_MATRIX.csv")
    csv_path = OUT_DIR / "CAMPAIGN_MATRIX.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(matrix_rows)
    print(f"  {csv_path}")

    # ------------------------------------------------------------------
    # 10. Campaign matrix — Markdown
    # ------------------------------------------------------------------
    print(f"[9] Writing CAMPAIGN_MATRIX.md")
    md_path = OUT_DIR / "CAMPAIGN_MATRIX.md"
    md = [
        "# E004 Diagnostic Campaign Matrix — 2026-09-10",
        "",
        f"Baseline: `out/hp2170NCA-RCR-distributed-exact-contact-final.tbm`  ",
        f"Baseline SHA-256: `{BASELINE_SHA256}`  ",
        f"Baseline source: commit `{BASELINE_GIT_COMMIT}`",
        "",
        "Baseline axial margins: pkg-sep = -2.00 mm | pkg-neg = 0.00 mm | pkg-pos = +1.00 mm",
        "",
        "Recommended test order: C00, C03, C14, C15, C16, C17, C10, C12, C13, C05, C07, C04, C06, C08, C09, C11, C01, C02",
        "",
        "Runtime result columns are blank — to be filled from Robert's test results.",
        "",
        "---",
        "",
    ]
    for row in matrix_rows:
        ax_section = ""
        if row["package_int_height_mm"] not in ("N/A", ""):
            try:
                ax_section = (
                    f"\n**Axial geometry:**\n\n"
                    f"| Dimension | Value |\n|---|---|\n"
                    f"| package_int_height_mm | {row['package_int_height_mm']} |\n"
                    f"| separator_width_mm | {row['separator_width_mm']} |\n"
                    f"| negative_width_mm | {row['negative_width_mm']} |\n"
                    f"| positive_width_mm | {row['positive_width_mm']} |\n"
                    f"| pkg − separator | {row['package_minus_separator_mm']:+.2f} mm |\n"
                    f"| pkg − negative  | {row['package_minus_negative_mm']:+.2f} mm |\n"
                    f"| pkg − positive  | {row['package_minus_positive_mm']:+.2f} mm |\n"
                )
            except (TypeError, ValueError):
                ax_section = ""

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
        ]
        if ax_section:
            md.append(ax_section)
        md += [
            "**Runtime result:** *(pending)*",
            "",
            "---",
            "",
        ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  {md_path}")

    # ------------------------------------------------------------------
    # 11. IMPORT_SELECTION_MATRIX
    # ------------------------------------------------------------------
    print(f"[10] Writing IMPORT_SELECTION_MATRIX.csv")
    imp_csv_path = OUT_DIR / "IMPORT_SELECTION_MATRIX.csv"
    with open(imp_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=IMPORT_CSV_FIELDS)
        w.writeheader()
        w.writerows(IMPORT_ROWS)
    print(f"  {imp_csv_path}")

    # ------------------------------------------------------------------
    # 12. STAR_IMPORT_OBJECT_SCHEMA_RUNTIME placeholder
    # ------------------------------------------------------------------
    schema_placeholder_path = REPO_ROOT / "tbm_validation" / "STAR_IMPORT_OBJECT_SCHEMA_RUNTIME.md"
    if not schema_placeholder_path.exists():
        schema_placeholder_path.write_text(
            "# STAR-CCM+ Import Battery Options — Runtime Object Schema\n\n"
            "**Status:** PENDING — awaiting screenshot from Robert.\n\n"
            "## Instructions\n\n"
            "Ask Robert for a screenshot of the complete `Import Battery Options` dialog "
            "that appears when selecting a TBM during `Create from Tbm`, with all "
            "selectable object/checkbox names visible.\n\n"
            "Record the exact UI labels below exactly as they appear in Robert's STAR "
            "version. Do not translate or normalize names.\n\n"
            "## Selectable objects (to be filled from screenshot)\n\n"
            "| # | Exact UI label | Selected by default? | Notes |\n"
            "|---|---|---|---|\n"
            "| 1 | *(from screenshot)* | | |\n\n"
            "## Notes\n\n"
            "Once this list is populated, design Ixx selective-import tests from "
            "IMPORT_SELECTION_MATRIX.csv using the exact labels above.\n",
            encoding="utf-8",
        )
        print(f"  Created placeholder: {schema_placeholder_path}")
    else:
        print(f"  Schema placeholder already exists: {schema_placeholder_path}")

    # ------------------------------------------------------------------
    # 13. README.txt
    # ------------------------------------------------------------------
    print(f"[11] Writing README.txt")
    readme_path = OUT_DIR / "README.txt"
    readme_path.write_text(README_TEXT, encoding="utf-8")
    print(f"  {readme_path}")

    # ------------------------------------------------------------------
    # 14. Build ZIP
    # ------------------------------------------------------------------
    print(f"\n[12] Building ZIP: {ZIP_PATH.name}")
    zip_member_order = [
        ("README.txt",                                    OUT_DIR / "README.txt"),
        ("CAMPAIGN_MATRIX.csv",                           OUT_DIR / "CAMPAIGN_MATRIX.csv"),
        ("CAMPAIGN_MATRIX.md",                            OUT_DIR / "CAMPAIGN_MATRIX.md"),
        ("IMPORT_SELECTION_MATRIX.csv",                   OUT_DIR / "IMPORT_SELECTION_MATRIX.csv"),
        ("C00_SIEMENS_CONTROL_validationBattery.tbm",     OUT_DIR / "C00_SIEMENS_CONTROL_validationBattery.tbm"),
        ("C01_FEED10.tbm",                                OUT_DIR / "C01_FEED10.tbm"),
        ("C02_TAIL85.tbm",                                OUT_DIR / "C02_TAIL85.tbm"),
        ("C03_FEED10_TAIL85.tbm",                         OUT_DIR / "C03_FEED10_TAIL85.tbm"),
        ("C04_END40.tbm",                                 OUT_DIR / "C04_END40.tbm"),
        ("C05_FEED10_TAIL85_END40.tbm",                   OUT_DIR / "C05_FEED10_TAIL85_END40.tbm"),
        ("C06_MANDRELWIDTH0.tbm",                         OUT_DIR / "C06_MANDRELWIDTH0.tbm"),
        ("C07_FEED10_TAIL85_MANDRELWIDTH0.tbm",           OUT_DIR / "C07_FEED10_TAIL85_MANDRELWIDTH0.tbm"),
        ("C08_JRWIDTH65p11.tbm",                          OUT_DIR / "C08_JRWIDTH65p11.tbm"),
        ("C09_FEED10_TAIL85_JRWIDTH65p11.tbm",            OUT_DIR / "C09_FEED10_TAIL85_JRWIDTH65p11.tbm"),
        ("C10_STAR_BUILDER_PATTERN.tbm",                  OUT_DIR / "C10_STAR_BUILDER_PATTERN.tbm"),
        ("C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm",     OUT_DIR / "C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm"),
        ("C12_FULL_SIEMENS_DETAILED_BUILDER.tbm",         OUT_DIR / "C12_FULL_SIEMENS_DETAILED_BUILDER.tbm"),
        ("C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm",    OUT_DIR / "C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm"),
        ("C14_AXIAL_CAVITY68p11.tbm",                     OUT_DIR / "C14_AXIAL_CAVITY68p11.tbm"),
        ("C15_AXIAL_CAVITY68p11_FEED10_TAIL85.tbm",       OUT_DIR / "C15_AXIAL_CAVITY68p11_FEED10_TAIL85.tbm"),
        ("C16_RECESSED_LAYERS_FIXED_CAVITY.tbm",          OUT_DIR / "C16_RECESSED_LAYERS_FIXED_CAVITY.tbm"),
        ("C17_RECESSED_LAYERS_FEED10_TAIL85.tbm",         OUT_DIR / "C17_RECESSED_LAYERS_FEED10_TAIL85.tbm"),
    ]

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, src in zip_member_order:
            zf.write(src, arcname)
            print(f"  + {arcname}")

    zip_sha = sha256_file(ZIP_PATH)

    with zipfile.ZipFile(ZIP_PATH) as zf:
        actual = sorted(zf.namelist())
    expected = sorted(a for a, _ in zip_member_order)
    if actual != expected:
        print(f"ABORT: ZIP member mismatch\n  expected: {expected}\n  actual: {actual}")
        sys.exit(1)
    print(f"  Members verified: {len(actual)}")
    print(f"  ZIP SHA-256: {zip_sha}")

    # ------------------------------------------------------------------
    # 15. Completion report
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CAMPAIGN COMPLETION REPORT")
    print("=" * 70)
    print(f"\nBranch: tbm-rcr-modelmap-fix-exec")
    print(f"Generator: tools/generate_e004_multifile_campaign.py")
    print(f"\nVerified baseline SHA-256: {BASELINE_SHA256}")
    print(f"Baseline source: commit {BASELINE_GIT_COMMIT}")
    print(f"\nTBMs in package: 18 (C00-C17)")
    print(f"\nC00 source: {SIEMENS_CONTROL_SRC}")
    print(f"C00 SHA-256: {c00_sha}")

    print(f"\nC01-C13 SHA-256 values and deltas:")
    for row in matrix_rows[1:14]:
        print(f"  {row['id']:4s}  {row['sha256']}  |  {row['changed_fields'][:55]}")

    print(f"\nC14-C17 axial variant report:")
    for v in AXIAL_VARIANTS:
        vid = v["id"]
        sha = axial_shas[vid]
        ax  = axial_margins_check[vid]
        ds  = delta_summary(v)
        print(f"\n  {vid}  SHA-256: {sha}")
        print(f"       Deltas: {ds}")
        print(f"       pkg_int_height = {ax['package_int_height_mm']} mm")
        print(f"       sep_width      = {ax['separator_width_mm']} mm")
        print(f"       neg_width      = {ax['negative_width_mm']} mm")
        print(f"       pos_width      = {ax['positive_width_mm']} mm")
        print(f"       pkg - sep      = {ax['package_minus_separator_mm']:+.2f} mm")
        print(f"       pkg - neg      = {ax['package_minus_negative_mm']:+.2f} mm")
        print(f"       pkg - pos      = {ax['package_minus_positive_mm']:+.2f} mm")

    print(f"\nValidator results (all variants):")
    for vid, fname, vsummary, _ in validator_log:
        print(f"  {vid:4s}  {vsummary}")

    print(f"\nProtected field parity (C01-C11): {'PASS' if all_protected_ok else 'FAIL'}")
    print(f"Protected field parity (C14-C17): {'PASS' if all_protected_ok else 'FAIL — see above'}")
    print(f"Protected field parity (C12, C13): NOT CHECKED (intentional geometry transplant)")

    print(f"\nCampaign matrix:")
    print(f"  CSV: {csv_path}")
    print(f"  MD:  {md_path}")
    print(f"\nImport selection matrix: {imp_csv_path}")

    schema_path = REPO_ROOT / "tbm_validation" / "STAR_IMPORT_OBJECT_SCHEMA_RUNTIME.md"
    print(f"Import object schema placeholder: {schema_path}")

    print(f"\nZIP: {ZIP_PATH}")
    print(f"ZIP SHA-256: {zip_sha}")
    print(f"\nZIP members ({len(actual)}):")
    for m in sorted(actual):
        print(f"  {m}")
    print(f"\nIMPORT_SELECTION_MATRIX created: YES (I00-I05 template rows)")
    print(f"E00 RCR-data-only import instructions included: YES (in README.txt)")
    print(f"Import-options screenshot instructions included: YES (in README.txt)")
    print(f"\nNothing was sent to Robert.")
    print(f"E004 status: ACTIVE / UNRESOLVED")
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
