#!/usr/bin/env python3
"""
Regression tests for tools/validate_tbm.py.

Run from repo root:
    python3 -m pytest tbm_validation/tests/test_validator.py -v

These tests verify the critical design decisions in the validator, especially:
1. SIMMOD-block-aware field lookup (not flat file scan).
2. Correct identification of the active RCRTable 3D block capacity fields.
3. m_bOnly1D per-block analysis, not a global pattern match.
4. REPORT block parsing.
5. Mandrel-width=0 is NOT flagged as FAIL.
"""

import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))
import validate_tbm as v


# ---------------------------------------------------------------------------
# Minimal TBM fixture builder
# ---------------------------------------------------------------------------
def make_tbm(*, extra_top="", extra_simmod="", extra_builder="", extra_report="",
             pkg_ext_d="21.09", pkg_ext_h="70.02", pkg_int_d="20.6274", pkg_int_h="65.11",
             bspec_in_ntgp="0", ahcell_in_ntgp="0",
             bspec_in_rcr="1", ahcell_in_rcr="5.0",
             only1d_ntgp="0", only1d_rcr="0",
             jr_od="19.25", overlap_start="8",
             offset_pos_avg="0.5") -> v.TBMParser:
    """Return a TBMParser for a minimal synthetic TBM."""
    txt = textwrap.dedent(f"""
        Package m_strName  = 2170
        Package m_dextDiameter = {pkg_ext_d}
        Package m_dextHeight   = {pkg_ext_h}
        Package m_dintDiameter = {pkg_int_d}
        Package m_dintHeight   = {pkg_int_h}
        Package m_dextVolume   = 16.5321
        Package m_dintVolume   = 14.9232
        Package m_bextVolCalc  = 1
        Package m_bintVolCalc  = 1
        DataSheet m_strName    = 2170
        DataSheet m_strDSName  = 2170
        DataSheet m_dHeight    = 70.02
        DataSheet m_dDSHeight  = 70.02
        DataSheet m_dCapacity  = 5.0
        DataSheet m_dDSCapacity = 5.0
        {extra_top}

        <BUILDER>
        m_dJellyrollThickness_mm = {jr_od}
        m_dMandrelThickness_mm   = 6
        m_dMandrelWidth_mm       = 6
        m_dElectrodeOverlapAtStart_mm = {overlap_start}
        m_dElectrodeOverlapAtEnd_mm   = 20
        m_dOffsetPosAvg          = {offset_pos_avg}
        m_bMandrelFlat           = 0
        +Electrode Collector m_dWidth_mm = 64.11
        -Electrode Collector m_dWidth_mm = 65.11
        {extra_builder}
        </BUILDER>

        <REPORT>
        m_dRepCanXDim      = {pkg_ext_d}   0
        m_dRepCanYDim      = {pkg_ext_d}   0
        m_dRepCanZDim      = {pkg_ext_h}   0
        m_dRepJellyrollDiameter = 17.8064  0
        m_dRepJellyrollHeight   = 52.5     0
        m_dRepCapacity          = 1.14762  0
        {extra_report}
        </REPORT>

        <SIMMOD>
        NTGPTable 3D
        m_bOnly1D = {only1d_ntgp}
        m_bSpecifyCapacity = {bspec_in_ntgp}
        m_dAhCell = {ahcell_in_ntgp}
        Set[0]_m_dT = 0
        </SIMMOD>

        <SIMMOD>
        RCRTable 3D
        m_bOnly1D = {only1d_rcr}
        m_bSpecifyCapacity = {bspec_in_rcr}
        m_dAhCell = {ahcell_in_rcr}
        m_nRCRParameterSets = 3
        Set[0]_m_dT = 288.15
        Set[1]_m_dT = 298.15
        Set[2]_m_dT = 308.15
        Set[0]_RCR_V_SOC_1 = 1.0
        Set[0]_RCR_V_SOC_2 = 0.833
        Set[0]_RCR_V_SOC_3 = 0.667
        Set[0]_RCR_V_SOC_4 = 0.5
        Set[0]_RCR_V_SOC_5 = 0.333
        Set[0]_RCR_V_SOC_6 = 0.167
        Set[0]_RCR_V_SOC_7 = 0.0
        Set[0]_RCR_V_Ro_1 = 0.023
        Set[0]_RCR_V_Ro_2 = 0.022
        Set[0]_RCR_V_Ro_3 = 0.021
        Set[0]_RCR_V_Ro_4 = 0.020
        Set[0]_RCR_V_Ro_5 = 0.019
        Set[0]_RCR_V_Ro_6 = 0.018
        Set[0]_RCR_V_Ro_7 = 0.017
        {extra_simmod}
        </SIMMOD>
    """)
    with tempfile.NamedTemporaryFile(suffix=".tbm", mode="w", delete=False) as f:
        f.write(txt)
        p = Path(f.name)
    return v.TBMParser(p)


def findings_of(tbm: v.TBMParser, ref=None) -> list[v.Finding]:
    val = v.TBMValidator(tbm, ref)
    return val.run_all()


def levels(findings, check_prefix=""):
    return [f.level for f in findings if f.check.startswith(check_prefix)]


def has_level(findings, level, check_prefix=""):
    return any(f.level == level and f.check.startswith(check_prefix) for f in findings)


# ---------------------------------------------------------------------------
# 1. SIMMOD-aware capacity lookup
#    THE CRITICAL REGRESSION: if the validator used flat file scan, it would
#    find m_bSpecifyCapacity=0 (from NTGPTable) and emit a capacity WARN/FAIL
#    even though the RCRTable 3D block has m_bSpecifyCapacity=1, m_dAhCell=5.
# ---------------------------------------------------------------------------
def test_capacity_uses_rcrtable_block_not_flat_scan():
    """Validator must look up capacity fields from RCRTable 3D block, not flat scan.

    The critical regression check: with a flat scan, the validator would find
    m_bSpecifyCapacity=0 in the NTGPTable 3D block (which appears before RCRTable 3D
    in the file) and incorrectly emit a WARN even though RCRTable 3D has bspec=1,
    ahcell=5. The main `capacity` check (not `report_capacity`) must be PASS.
    """
    tbm = make_tbm(bspec_in_ntgp="0", ahcell_in_ntgp="0",
                   bspec_in_rcr="1", ahcell_in_rcr="5.0")
    findings = findings_of(tbm)
    # Only check the main `capacity` finding, not `report_capacity` (which checks REPORT block
    # and will legitimately WARN about stale 18650 geometry values in the REPORT block)
    main_cap = [f for f in findings if f.check == "capacity"]
    assert main_cap, f"Expected a 'capacity' finding. Got: {[f.check for f in findings]}"
    assert main_cap[0].level == "PASS", \
        f"False WARN/FAIL for capacity despite RCRTable bspec=1, ahcell=5. Got: {main_cap[0]}"


def test_capacity_fail_when_rcrtable_has_zero_ahcell():
    """Validator must FAIL when RCRTable 3D block has bspec=1 but ahcell=0."""
    tbm = make_tbm(bspec_in_rcr="1", ahcell_in_rcr="0")
    findings = findings_of(tbm)
    cap_findings = [f for f in findings if "capacity" in f.check.lower()]
    assert has_level(cap_findings, "FAIL", "capacity"), \
        f"Expected FAIL for rcr bspec=1 ahcell=0. Got: {cap_findings}"


def test_capacity_warn_when_rcrtable_bspec_zero():
    """Validator must WARN when RCRTable 3D block has bspec=0 (derived)."""
    tbm = make_tbm(bspec_in_rcr="0", ahcell_in_rcr="0")
    findings = findings_of(tbm)
    cap_findings = [f for f in findings if "capacity" in f.check.lower()]
    assert has_level(cap_findings, "WARN", "capacity"), \
        f"Expected WARN for rcr bspec=0. Got: {cap_findings}"


# ---------------------------------------------------------------------------
# 2. m_bOnly1D per-block analysis
# ---------------------------------------------------------------------------
def test_m_bOnly1D_rcr_zero_gives_pass():
    """m_bOnly1D=0 in RCRTable 3D must give PASS."""
    tbm = make_tbm(only1d_rcr="0")
    findings = findings_of(tbm)
    rcr_1d = [f for f in findings if "m_bOnly1D_rcrtable" in f.check]
    assert rcr_1d, "Expected a finding for m_bOnly1D_rcrtable."
    assert rcr_1d[0].level == "PASS", f"Expected PASS for rcr m_bOnly1D=0. Got: {rcr_1d[0]}"


def test_m_bOnly1D_rcr_one_gives_warn():
    """m_bOnly1D=1 in RCRTable 3D must give WARN (only HP18650-DIST has 1; import status unknown)."""
    tbm = make_tbm(only1d_rcr="1")
    findings = findings_of(tbm)
    rcr_1d = [f for f in findings if "m_bOnly1D_rcrtable" in f.check]
    assert rcr_1d, "Expected a finding for m_bOnly1D_rcrtable."
    assert rcr_1d[0].level == "WARN", f"Expected WARN for rcr m_bOnly1D=1. Got: {rcr_1d[0]}"


def test_m_bOnly1D_ntgp_zero_not_fail():
    """m_bOnly1D=0 in NTGPTable 3D is normal — must NOT produce FAIL."""
    tbm = make_tbm(only1d_ntgp="0", only1d_rcr="0")
    findings = findings_of(tbm)
    fail_1d = [f for f in findings if "m_bOnly1D" in f.check and f.level == "FAIL"]
    assert not fail_1d, f"Unexpected FAIL for m_bOnly1D: {fail_1d}"


# ---------------------------------------------------------------------------
# 3. REPORT block parsing and stale value detection
# ---------------------------------------------------------------------------
def test_report_stale_jr_diameter_detected():
    """Stale m_dRepJellyrollDiameter in REPORT block (17.8 vs builder 19.25) must produce WARN."""
    tbm = make_tbm(jr_od="19.25")  # REPORT has 17.8064 hardcoded in fixture
    findings = findings_of(tbm)
    rep_findings = [f for f in findings if "report_jr_diameter" in f.check]
    assert rep_findings, "Expected report_jr_diameter finding."
    assert rep_findings[0].level == "WARN", f"Expected WARN for stale REPORT JR diameter. Got: {rep_findings}"


def test_report_can_dims_match_package():
    """REPORT m_dRepCanXDim matches Package m_dextDiameter → PASS."""
    # In the fixture, REPORT can dims = pkg_ext_d = 21.09 exactly
    tbm = make_tbm()
    findings = findings_of(tbm)
    rep_can = [f for f in findings if "report_can_dims" in f.check]
    for rf in rep_can:
        assert rf.level == "PASS", f"Expected PASS for REPORT can dims. Got: {rf}"


# ---------------------------------------------------------------------------
# 4. Mandrel-width=0 is valid (not a FAIL)
# ---------------------------------------------------------------------------
def test_mandrel_width_zero_not_fail():
    """m_dMandrelWidth_mm=0 is valid per tutorialCylindricalCell.tbm reference. Must not be FAIL."""
    tbm = make_tbm(extra_builder="m_dMandrelWidth_mm = 0")
    # Override the default 6 in the builder section
    # But fixture already writes m_dMandrelWidth_mm = 6 first; second occurrence will be in _builder_fields
    # Let's build a specific TBM where width=0 is the only occurrence
    txt = f"""
Package m_dextDiameter = 21.09
Package m_dextHeight = 70.02
Package m_dintDiameter = 20.6274
Package m_dintHeight = 65.11

<BUILDER>
m_dJellyrollThickness_mm = 19.25
m_dMandrelThickness_mm = 6
m_dMandrelWidth_mm = 0
m_dElectrodeOverlapAtStart_mm = 8
m_bMandrelFlat = 0
m_dOffsetPosAvg = 0.5
</BUILDER>

<SIMMOD>
RCRTable 3D
m_bOnly1D = 0
m_bSpecifyCapacity = 1
m_dAhCell = 5.0
m_nRCRParameterSets = 3
Set[0]_m_dT = 288.15
Set[1]_m_dT = 298.15
Set[2]_m_dT = 308.15
Set[0]_RCR_V_SOC_1 = 1.0
Set[0]_RCR_V_SOC_2 = 0.833
Set[0]_RCR_V_SOC_3 = 0.667
Set[0]_RCR_V_SOC_4 = 0.5
Set[0]_RCR_V_SOC_5 = 0.333
Set[0]_RCR_V_SOC_6 = 0.167
Set[0]_RCR_V_SOC_7 = 0.0
Set[0]_RCR_V_Ro_1 = 0.023
Set[0]_RCR_V_Ro_2 = 0.022
Set[0]_RCR_V_Ro_3 = 0.021
Set[0]_RCR_V_Ro_4 = 0.020
Set[0]_RCR_V_Ro_5 = 0.019
Set[0]_RCR_V_Ro_6 = 0.018
Set[0]_RCR_V_Ro_7 = 0.017
</SIMMOD>
"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".tbm", mode="w", delete=False) as f:
        f.write(txt)
        p = Path(f.name)
    tbm = v.TBMParser(p)
    findings = findings_of(tbm)
    fail_mandrel = [f for f in findings if "mandrel" in f.check.lower() and f.level == "FAIL"]
    assert not fail_mandrel, \
        f"m_dMandrelWidth_mm=0 must not produce FAIL. Got: {fail_mandrel}"


def test_mandrel_thickness_zero_is_fail():
    """m_dMandrelThickness_mm=0 must produce FAIL (causes 'Extrusion distance cannot be 0')."""
    txt = f"""
Package m_dextDiameter = 21.09
Package m_dextHeight = 70.02
Package m_dintDiameter = 20.6274
Package m_dintHeight = 65.11

<BUILDER>
m_dJellyrollThickness_mm = 19.25
m_dMandrelThickness_mm = 0
m_dMandrelWidth_mm = 0
m_dElectrodeOverlapAtStart_mm = 8
m_bMandrelFlat = 0
m_dOffsetPosAvg = 0.5
</BUILDER>

<SIMMOD>
RCRTable 3D
m_bOnly1D = 0
m_bSpecifyCapacity = 1
m_dAhCell = 5.0
</SIMMOD>
"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".tbm", mode="w", delete=False) as f:
        f.write(txt)
        p = Path(f.name)
    tbm = v.TBMParser(p)
    findings = findings_of(tbm)
    fail_mandrel = [f for f in findings if "mandrel_t" in f.check and f.level == "FAIL"]
    assert fail_mandrel, "m_dMandrelThickness_mm=0 must produce FAIL."


# ---------------------------------------------------------------------------
# 5. Electrode overlap at start = 0 is FAIL
# ---------------------------------------------------------------------------
def test_overlap_start_zero_is_fail():
    """m_dElectrodeOverlapAtStart_mm=0 must be FAIL (caused V1 'Extrusion distance = 0' error)."""
    tbm = make_tbm(overlap_start="0")
    findings = findings_of(tbm)
    assert has_level(findings, "FAIL", "overlap_start"), \
        "Expected FAIL for overlap_start=0."


def test_overlap_start_positive_is_pass():
    """m_dElectrodeOverlapAtStart_mm=8 must be PASS."""
    tbm = make_tbm(overlap_start="8")
    findings = findings_of(tbm)
    assert has_level(findings, "PASS", "overlap_start"), \
        "Expected PASS for overlap_start=8."


# ---------------------------------------------------------------------------
# 6. m_dOffsetPosAvg warning
# ---------------------------------------------------------------------------
def test_offset_pos_avg_epsilon_gives_warn():
    """m_dOffsetPosAvg=1e-06 (near-zero epsilon) must give WARN."""
    tbm = make_tbm(offset_pos_avg="1e-06")
    findings = findings_of(tbm)
    off = [f for f in findings if "offset_pos_avg" in f.check]
    assert off, "Expected offset_pos_avg finding."
    assert off[0].level == "WARN", f"Expected WARN for offset_pos_avg=1e-06. Got: {off[0]}"


def test_offset_pos_avg_half_gives_pass():
    """m_dOffsetPosAvg=0.5 must give PASS."""
    tbm = make_tbm(offset_pos_avg="0.5")
    findings = findings_of(tbm)
    off = [f for f in findings if "offset_pos_avg" in f.check]
    assert off, "Expected offset_pos_avg finding."
    assert off[0].level == "PASS", f"Expected PASS for offset_pos_avg=0.5. Got: {off[0]}"


# ---------------------------------------------------------------------------
# 7. DataSheet residuals
# ---------------------------------------------------------------------------
def test_ds_hpcell_name_gives_warn():
    """DataSheet m_strName='HPCell' must produce a WARN."""
    tbm = make_tbm(extra_top="DataSheet m_strName = HPCell")
    # We need to override the clean DataSheet m_strName from make_tbm.
    # The parser will have two entries; the fixture sets it to 2170 first,
    # then our extra sets it to HPCell — flat dict keeps the first value.
    # Rebuild with a raw TBM to test properly.
    txt = """
Package m_dextDiameter = 21.09
Package m_dextHeight = 70.02
Package m_dintDiameter = 20.6274
Package m_dintHeight = 65.11
DataSheet m_strName = HPCell
DataSheet m_strDSName = HPCell
DataSheet m_dHeight = 65.0
DataSheet m_dDSHeight = 65.0
DataSheet m_dCapacity = 1.1
DataSheet m_dDSCapacity = 0.9

<BUILDER>
m_dJellyrollThickness_mm = 19.25
m_dMandrelThickness_mm = 6
m_dMandrelWidth_mm = 6
m_dElectrodeOverlapAtStart_mm = 8
m_bMandrelFlat = 0
m_dOffsetPosAvg = 0.5
</BUILDER>

<SIMMOD>
RCRTable 3D
m_bOnly1D = 0
m_bSpecifyCapacity = 1
m_dAhCell = 5.0
Set[0]_m_dT = 288.15
Set[1]_m_dT = 298.15
Set[2]_m_dT = 308.15
Set[0]_RCR_V_SOC_1 = 1.0
Set[0]_RCR_V_SOC_2 = 0.833
Set[0]_RCR_V_SOC_3 = 0.667
Set[0]_RCR_V_SOC_4 = 0.5
Set[0]_RCR_V_SOC_5 = 0.333
Set[0]_RCR_V_SOC_6 = 0.167
Set[0]_RCR_V_SOC_7 = 0.0
Set[0]_RCR_V_Ro_1 = 0.023
Set[0]_RCR_V_Ro_2 = 0.022
Set[0]_RCR_V_Ro_3 = 0.021
Set[0]_RCR_V_Ro_4 = 0.020
Set[0]_RCR_V_Ro_5 = 0.019
Set[0]_RCR_V_Ro_6 = 0.018
Set[0]_RCR_V_Ro_7 = 0.017
</SIMMOD>
"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".tbm", mode="w", delete=False) as f:
        f.write(txt)
        p = Path(f.name)
    tbm = v.TBMParser(p)
    findings = findings_of(tbm)
    ds_warns = [f for f in findings if "ds_" in f.check and f.level == "WARN"]
    assert ds_warns, f"Expected WARN for DataSheet residuals. Got: {[f.check for f in findings]}"


# ---------------------------------------------------------------------------
# 8. Volume consistency
# ---------------------------------------------------------------------------
def test_volume_stale_with_recalc_flag_is_info_not_warn():
    """When m_bextVolCalc=1, stale stored volume should be INFO not WARN."""
    # Fixture has m_bextVolCalc=1 and stale volume (16.5321 vs geometric ~24.46 cm3)
    tbm = make_tbm()
    findings = findings_of(tbm)
    vol_findings = [f for f in findings if "volume_ext" in f.check or "volume_int" in f.check]
    for vf in vol_findings:
        assert vf.level in ("INFO", "PASS"), \
            f"With m_bextVolCalc=1, volume mismatch should be INFO. Got {vf.level}: {vf.message}"


# ---------------------------------------------------------------------------
# 9. Package geometry baseline
# ---------------------------------------------------------------------------
def test_package_geometry_correct_values_pass():
    """All Package fields at 2170 target values must produce PASS."""
    tbm = make_tbm()
    findings = findings_of(tbm)
    pkg_pass = [f for f in findings if f.level == "PASS" and "pkg" in f.check.lower()]
    assert pkg_pass, "Expected at least some PASS findings for package geometry."
    pkg_fail = [f for f in findings if f.level == "FAIL" and "pkg" in f.check.lower()]
    assert not pkg_fail, f"Unexpected FAIL for correct package values: {pkg_fail}"


def test_package_geometry_wrong_diameter_warns():
    """Package m_dextDiameter far from 21.09 must produce WARN."""
    tbm = make_tbm(pkg_ext_d="18.0")
    findings = findings_of(tbm)
    assert has_level(findings, "WARN", "Package_m_dextDiameter") or \
           has_level(findings, "WARN", "Package m_dextDiameter"), \
           f"Expected WARN for wrong package diameter. Got: {[f.check for f in findings if f.level=='WARN']}"


# ---------------------------------------------------------------------------
# 10. SIMMOD parsing correctness
# ---------------------------------------------------------------------------
def test_simmod_parser_finds_rcrtable_fields():
    """RCRTable 3D block fields must be parseable via get_simmod_field."""
    tbm = make_tbm(bspec_in_rcr="1", ahcell_in_rcr="5.0")
    assert tbm.get_simmod_field("RCRTable", "m_bSpecifyCapacity") == "1"
    assert tbm.get_simmod_float("RCRTable", "m_dAhCell") == 5.0


def test_simmod_parser_distinguishes_blocks():
    """Fields shared between SIMMOD blocks must be read from the correct block."""
    # Both NTGPTable and RCRTable have m_bSpecifyCapacity; they have different values.
    tbm = make_tbm(bspec_in_ntgp="0", bspec_in_rcr="1")
    ntgp_val = tbm.get_simmod_field("NTGPTable", "m_bSpecifyCapacity")
    rcr_val  = tbm.get_simmod_field("RCRTable",  "m_bSpecifyCapacity")
    assert ntgp_val == "0", f"NTGPTable bspec should be 0, got {ntgp_val}"
    assert rcr_val  == "1", f"RCRTable bspec should be 1, got {rcr_val}"
    # Flat lookup should NOT be used for SIMMOD-specific checks
    # (this test proves block-awareness is working)


def test_simmod_temperature_reads_from_rcrtable():
    """Set[0]_m_dT in RCRTable 3D block must read 288.15 K, not 0 from NTGPTable."""
    tbm = make_tbm()  # fixture has NTGPTable Set[0]_m_dT=0, RCRTable Set[0]_m_dT=288.15
    rcr_t = tbm.get_simmod_float("RCRTable", "Set[0]_m_dT")
    assert rcr_t is not None and abs(rcr_t - 288.15) < 0.01, \
        f"Expected 288.15 K from RCRTable block, got {rcr_t}"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed.")
    sys.exit(0 if failed == 0 else 1)
