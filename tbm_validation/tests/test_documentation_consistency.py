#!/usr/bin/env python3
"""Regression checks for documentation consistency with extracted TBM values."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from tbm_field_extractor import extract_tbm_fields  # noqa: E402


DOCS = [
    ROOT / "STARCCM_TBM_PROJECT_CONTEXT.md",
    ROOT / "docs/STARCCM_TBM_PROJECT_CONTEXT.md",
    ROOT / "tbm_validation/TBM_STRUCTURAL_COMPARISON.md",
    ROOT / "tbm_validation/CURRENT_TBM_FIELD_AUDIT.md",
    ROOT / "tbm_validation/V4_CANDIDATE_DELTA_REPORT.md",
    ROOT / "tbm_validation/PRE_CLIENT_RELEASE_CHECKLIST.md",
    ROOT / "tbm_validation/GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md",
]

SOURCE = ROOT / "tbm_validation/source/hp2170NCA-ECM.tbm"
HE18650 = ROOT / "tbm_validation/reference/HE18650/he18650spiral1.tbm"
REV3 = sorted((ROOT / "tbm_validation/variants/v3_package_20260909").glob("*.tbm"))
REV4 = sorted((ROOT / "out/v4_candidate").glob("*.tbm"))


def test_all_required_docs_exist():
    assert all(path.is_file() for path in DOCS)


def test_extracted_builder_values_are_protected_in_docs():
    source = extract_tbm_fields(SOURCE)
    he = extract_tbm_fields(HE18650)
    assert source.simple_builder.offset_pos_avg == "0"
    assert he.m_bonly1d_list == ["1", "0", "0", "0"]
    for path in DOCS[2:6]:
        text = path.read_text()
        assert "Simple Builder" in text
        assert "m_dOffsetPosAvg" in text
    v4_text = (ROOT / "tbm_validation/V4_CANDIDATE_DELTA_REPORT.md").read_text()
    assert "Simple Builder value is `0`" in v4_text
    assert "Simple Builder value was already 0.5" not in v4_text


def test_active_capacity_and_package_totals_are_current():
    cap = extract_tbm_fields(REV3[0]).rct3d_capacity
    assert cap == {"m_bSpecifyCapacity": "1", "m_dAhCell": "5.0"}
    combined = "\n".join(path.read_text() for path in DOCS)
    assert "m_bSpecifyCapacity = 1" in combined
    assert "m_dAhCell = 5.0" in combined
    assert "0 FAIL, 11 WARN" in combined
    assert "0 FAIL, 4 WARN" in combined
    assert "0 FAIL, 8 WARN" not in combined


def test_forbidden_documentation_regressions_are_absent():
    combined = "\n".join(path.read_text() for path in DOCS)
    forbidden = [
        r"About-Energy[^\n]*(generated|created|supplied)[^\n]*TBM",
        r"m_bSpecifyCapacity\s*=\s*0[^\n]*m_dAhCell\s*=\s*0",
        r"m_dJellyrollThickness_mm[^\n]*(must|should)[^\n]*20\.6274",
        r"DataSheet section is informational metadata only",
        r"REPORT block informational; not consumed",
        r"STAR likely recomputes",
        r"only STAR-consumed REPORT fields",
        r"Simple Builder value was already 0\.5",
        r"(?<![A-Za-z0-9_-])V3(?![A-Za-z0-9_-])",
        r"(?<![A-Za-z0-9_-])V4(?![A-Za-z0-9_-])",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, combined, flags=re.IGNORECASE), pattern
    assert "Machine extraction confirms HE18650 **does** contain four `m_bOnly1D` fields" in combined


def test_context_files_are_explicitly_related():
    root_text = DOCS[0].read_text()
    docs_text = DOCS[1].read_text()
    for text in (root_text, docs_text):
        assert "About-Energy" in text
        assert "Does NOT supply TBM files" in text
        assert "m_bOnly1D = [1, 0, 0, 0]" in text
        assert "equivalent cell-level and distributed electrothermal response" in text
        assert "Do not assume the JR OD must equal the can ID" in text
    assert "canonical root-level" in root_text or "canonical" in root_text
    assert "synchronized copy" in docs_text


def test_step_characterization_findings_are_recorded():
    evidence = (ROOT / "tbm_validation/GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md").read_text()
    assert "21 isolated TBM variants" in evidence
    assert "19 STEP files" in evidence
    assert "Detailed Builder `m_dJellyrollThickness_mm` is consumed" in evidence
    assert "Simple Builder jelly-roll diameter" in evidence
    assert "zero measured JellyRoll∩Can and JellyRoll∩Mandrel intersection volume" in evidence
    combined = "\n".join(path.read_text() for path in DOCS)
    assert "August STEP characterization established" in combined
    assert "geometry test still pending" not in combined


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_")]
    passed = failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test.__name__}: {exc}")
            failed += 1
    print(f"\n{passed}/{len(tests)} passed, {failed} failed.")
    raise SystemExit(1 if failed else 0)
