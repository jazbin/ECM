#!/usr/bin/env python3
"""
Regression tests for critical TBM structural fields on the tbm-review-integration branch.

Covers:
  - Machine-extracted field values from source, HE18650, all package_rev3 variants,
    all package_rev4_candidate variants
  - DB and SB m_dOffsetPosAvg extracted independently (never aliased)
  - HE18650 m_bOnly1D present and = [1, 0, 0, 0]
  - package_rev4_candidate DB = 0.5, SB = 0
  - Consistency: generated TBM_STRUCTURAL_COMPARISON.md agrees with extracted values
  - All known documentation bugs guarded against re-appearing

Run:
    python3 -m pytest tbm_validation/tests/test_structural_fields.py -v
    # or directly:
    python3 tbm_validation/tests/test_structural_fields.py
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
TOOLS = WORKSPACE / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from tbm_field_extractor import extract_tbm_fields

# Source and reference
SOURCE  = WORKSPACE / 'tbm_validation/source/hp2170NCA-ECM.tbm'
HE18650 = WORKSPACE / 'tbm_validation/reference/HE18650/he18650spiral1.tbm'

# package_rev3 variants
PKG_REV3 = [
    WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v1-tabs-on-standard.tbm',
    WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v2-tabs-off-standard.tbm',
    WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v3-tabs-on-sameFace.tbm',
    WORKSPACE / 'tbm_validation/variants/v3_package_20260909/hp2170-test-v4-tabs-off-sameFace.tbm',
]

# package_rev4_candidate variants
PKG_REV4C = [
    WORKSPACE / 'out/v4_candidate/hp2170-v4c-v1-tabs-on-standard.tbm',
    WORKSPACE / 'out/v4_candidate/hp2170-v4c-v2-tabs-off-standard.tbm',
    WORKSPACE / 'out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm',
    WORKSPACE / 'out/v4_candidate/hp2170-v4c-v4-tabs-off-sameFace.tbm',
]

# Generated audit doc
AUDIT = WORKSPACE / 'tbm_validation/TBM_STRUCTURAL_COMPARISON.md'

# Known SHA-256 hashes from 2ea5b45 (must not change)
KNOWN_HASHES = {
    # package_rev3
    'tbm_validation/variants/v3_package_20260909/hp2170-test-v1-tabs-on-standard.tbm':
        'cae78b4d66204b18898ce081252a1aae4fbf53f6cb325b77310690f727e411ad',
    'tbm_validation/variants/v3_package_20260909/hp2170-test-v2-tabs-off-standard.tbm':
        '9f388fdf2a177a01d0441ce5ef5a24d06ae2104491a73db3ef955eeff7393593',
    'tbm_validation/variants/v3_package_20260909/hp2170-test-v3-tabs-on-sameFace.tbm':
        'e03d2eaf97cf21d0a16e24bb503ab632bd1a2b0c17dfb0d3b6d8d1cbf8011c81',
    'tbm_validation/variants/v3_package_20260909/hp2170-test-v4-tabs-off-sameFace.tbm':
        '9a973f4de048907520d8b48f592dab2d2c29e3d120b2db97a5c29bbacfcd8329',
    # package_rev4_candidate
    'out/v4_candidate/hp2170-v4c-v1-tabs-on-standard.tbm':
        'a505a2d820239e8502f05394ef6cc0a7603bf6884695af1c446a7f941cb9142c',
    'out/v4_candidate/hp2170-v4c-v2-tabs-off-standard.tbm':
        '401543af24341e34ab10ba250872b08caf370de77ef8da54687928588739d669',
    'out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm':
        '24eacae56e40d826f162046bc63131f7c590b3c5d72dec80828c7e6a5520667f',
    'out/v4_candidate/hp2170-v4c-v4-tabs-off-sameFace.tbm':
        '214e4a81a94743dfc4c26d848fea5468e2cdc33e34fdcb764ea5d7676a59382c',
}


def _flt(v) -> float:
    return float(v)


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Hash integrity
# ---------------------------------------------------------------------------

class TestTbmFileIntegrity:
    """Verify that no TBM file changed from the 2ea5b45 state."""

    def test_package_rev3_hashes(self):
        for path in PKG_REV3:
            rel = str(path.relative_to(WORKSPACE))
            expected = KNOWN_HASHES[rel]
            actual = _sha256(path)
            assert actual == expected, (
                f'package_rev3 hash mismatch for {rel}:\n'
                f'  expected: {expected}\n'
                f'  actual:   {actual}'
            )

    def test_package_rev4_candidate_hashes(self):
        for path in PKG_REV4C:
            rel = str(path.relative_to(WORKSPACE))
            expected = KNOWN_HASHES[rel]
            actual = _sha256(path)
            assert actual == expected, (
                f'package_rev4_candidate hash mismatch for {rel}:\n'
                f'  expected: {expected}\n'
                f'  actual:   {actual}'
            )


# ---------------------------------------------------------------------------
# Source TBM
# ---------------------------------------------------------------------------

class TestSourceTbm:
    def setup_method(self):
        self.f = extract_tbm_fields(SOURCE)

    def test_db_offset_pos_avg(self):
        assert _flt(self.f.detailed_builder.offset_pos_avg) == 1e-06

    def test_sb_offset_pos_avg(self):
        assert _flt(self.f.simple_builder.offset_pos_avg) == 0.0

    def test_db_sb_offset_extracted_independently(self):
        db = _flt(self.f.detailed_builder.offset_pos_avg)
        sb = _flt(self.f.simple_builder.offset_pos_avg)
        assert db != sb, 'DB and SB values are identical — aliasing bug'

    def test_db_mandrel_width(self):
        assert _flt(self.f.detailed_builder.mandrel_width) == 0.0

    def test_sb_mandrel_width(self):
        assert _flt(self.f.simple_builder.mandrel_width) == 0.0

    def test_db_electrode_overlap(self):
        assert _flt(self.f.detailed_builder.electrode_overlap_at_start) == 0.0

    def test_sb_electrode_overlap(self):
        assert _flt(self.f.simple_builder.electrode_overlap_at_start) == 8.0

    def test_m_bonly1d(self):
        vals = self.f.m_bonly1d_list
        assert len(vals) == 4
        assert all(int(v) == 1 for v in vals)

    def test_rct3d_capacity(self):
        cap = self.f.rct3d_capacity
        assert int(cap['m_bSpecifyCapacity']) == 1
        assert _flt(cap['m_dAhCell']) == 5.0


# ---------------------------------------------------------------------------
# HE18650 reference
# ---------------------------------------------------------------------------

class TestHe18650:
    def setup_method(self):
        self.f = extract_tbm_fields(HE18650)

    def test_db_offset_pos_avg(self):
        assert _flt(self.f.detailed_builder.offset_pos_avg) == 0.5

    def test_sb_offset_pos_avg(self):
        assert _flt(self.f.simple_builder.offset_pos_avg) == 0.0

    def test_db_sb_extracted_independently(self):
        db = _flt(self.f.detailed_builder.offset_pos_avg)
        sb = _flt(self.f.simple_builder.offset_pos_avg)
        assert db != sb

    def test_m_bonly1d_field_present(self):
        """Regression: prior docs falsely stated HE18650 has NO m_bOnly1D field."""
        assert len(self.f.m_bonly1d_list) > 0, (
            'HE18650 must contain m_bOnly1D fields. '
            'Prior false claim: "HE18650 does NOT have the m_bOnly1D field in any SIMMOD block."'
        )

    def test_m_bonly1d_values(self):
        """HE18650 m_bOnly1D = [1, 0, 0, 0] in document order."""
        vals = [int(v) for v in self.f.m_bonly1d_list]
        assert len(vals) == 4, f'Expected 4, got {len(vals)}'
        assert vals[0] == 1, f'First SIMMOD (Distributed 3D) should be 1, got {vals[0]}'
        assert vals[1:] == [0, 0, 0], f'SIMODs 2-4 should be [0,0,0], got {vals[1:]}'


# ---------------------------------------------------------------------------
# package_rev3 variants
# ---------------------------------------------------------------------------

class TestPackageRev3:
    def setup_method(self):
        self.fields = [extract_tbm_fields(p) for p in PKG_REV3]
        self.labels = ['variant_1', 'variant_2', 'variant_3', 'variant_4']

    def test_db_offset_pos_avg_all(self):
        for label, f in zip(self.labels, self.fields):
            assert _flt(f.detailed_builder.offset_pos_avg) == 1e-06, label

    def test_sb_offset_pos_avg_all_zero(self):
        """Regression: prior doc incorrectly showed package_rev3 SB m_dOffsetPosAvg = 0.5."""
        for label, f in zip(self.labels, self.fields):
            assert _flt(f.simple_builder.offset_pos_avg) == 0.0, (
                f'{label}: Simple Builder m_dOffsetPosAvg should be 0, '
                f'got {f.simple_builder.offset_pos_avg!r}. '
                'Prior bug: value was reported as 0.5 (the HE18650 DB value).'
            )

    def test_db_sb_extracted_independently_all(self):
        for label, f in zip(self.labels, self.fields):
            db = _flt(f.detailed_builder.offset_pos_avg)
            sb = _flt(f.simple_builder.offset_pos_avg)
            assert db != sb, f'{label}: DB == SB suggests aliasing bug'

    def test_db_electrode_overlap_fixed(self):
        for label, f in zip(self.labels, self.fields):
            assert _flt(f.detailed_builder.electrode_overlap_at_start) == 8.0, label

    def test_db_mandrel_width_fixed(self):
        for label, f in zip(self.labels, self.fields):
            assert _flt(f.detailed_builder.mandrel_width) == 6.0, label

    def test_m_bonly1d_all_zero(self):
        for label, f in zip(self.labels, self.fields):
            vals = [int(v) for v in f.m_bonly1d_list]
            assert len(vals) == 4, f'{label}: expected 4'
            assert all(v == 0 for v in vals), f'{label}: expected all-zeros, got {vals}'

    def test_rct3d_capacity_all(self):
        for label, f in zip(self.labels, self.fields):
            cap = f.rct3d_capacity
            assert int(cap['m_bSpecifyCapacity']) == 1, label
            assert _flt(cap['m_dAhCell']) == 5.0, label


# ---------------------------------------------------------------------------
# package_rev4_candidate variants
# ---------------------------------------------------------------------------

class TestPackageRev4Candidate:
    def setup_method(self):
        self.fields = [extract_tbm_fields(p) for p in PKG_REV4C]
        self.labels = ['variant_1', 'variant_2', 'variant_3', 'variant_4']

    def test_db_offset_pos_avg_all_corrected(self):
        """DB m_dOffsetPosAvg must be 0.5 in all package_rev4_candidate variants."""
        for label, f in zip(self.labels, self.fields):
            assert _flt(f.detailed_builder.offset_pos_avg) == 0.5, (
                f'{label}: package_rev4_candidate DB should be 0.5 (corrected from 1e-06). '
                f'Got {f.detailed_builder.offset_pos_avg!r}'
            )

    def test_sb_offset_pos_avg_all_zero(self):
        """SB remains 0 — only DB was changed in the V4 candidate."""
        for label, f in zip(self.labels, self.fields):
            assert _flt(f.simple_builder.offset_pos_avg) == 0.0, (
                f'{label}: Simple Builder should be 0, got {f.simple_builder.offset_pos_avg!r}'
            )

    def test_db_sb_extracted_independently_all(self):
        for label, f in zip(self.labels, self.fields):
            db = _flt(f.detailed_builder.offset_pos_avg)
            sb = _flt(f.simple_builder.offset_pos_avg)
            assert db != sb, f'{label}: DB == SB suggests aliasing bug'

    def test_db_matches_he18650_pattern(self):
        """package_rev4_candidate DB/SB must match HE18650 DB/SB exactly."""
        he = extract_tbm_fields(HE18650)
        for label, f in zip(self.labels, self.fields):
            assert f.detailed_builder.offset_pos_avg == he.detailed_builder.offset_pos_avg, (
                f'{label}: DB mismatch vs HE18650 ({f.detailed_builder.offset_pos_avg!r} vs {he.detailed_builder.offset_pos_avg!r})'
            )
            assert f.simple_builder.offset_pos_avg == he.simple_builder.offset_pos_avg, (
                f'{label}: SB mismatch vs HE18650'
            )

    def test_m_bonly1d_all_zero(self):
        for label, f in zip(self.labels, self.fields):
            vals = [int(v) for v in f.m_bonly1d_list]
            assert all(v == 0 for v in vals), f'{label}: {vals}'

    def test_rct3d_capacity_all(self):
        for label, f in zip(self.labels, self.fields):
            cap = f.rct3d_capacity
            assert int(cap['m_bSpecifyCapacity']) == 1, label
            assert _flt(cap['m_dAhCell']) == 5.0, label


# ---------------------------------------------------------------------------
# Audit doc consistency
# ---------------------------------------------------------------------------

class TestAuditDocConsistency:
    """Generated TBM_STRUCTURAL_COMPARISON.md must never contradict extracted values."""

    def setup_method(self):
        assert AUDIT.exists(), f'Audit doc not found: {AUDIT}'
        self.doc = AUDIT.read_text(encoding='utf-8')
        self.src   = extract_tbm_fields(SOURCE)
        self.he    = extract_tbm_fields(HE18650)
        self.r3v1  = extract_tbm_fields(PKG_REV3[0])
        self.r3v4  = extract_tbm_fields(PKG_REV3[3])
        self.r4v4  = extract_tbm_fields(PKG_REV4C[3])

    def _has(self, s):
        assert s in self.doc, f'Expected in {AUDIT.name}: {s!r}'

    def _not(self, s, context=''):
        assert s not in self.doc, f'Must not appear in {AUDIT.name}: {s!r}. {context}'

    def test_source_db_sb_offset(self):
        db = str(self.src.detailed_builder.offset_pos_avg)
        sb = str(self.src.simple_builder.offset_pos_avg)
        self._has(f'| source | {db} | {sb} |')

    def test_he18650_db_sb_offset(self):
        db = str(self.he.detailed_builder.offset_pos_avg)
        sb = str(self.he.simple_builder.offset_pos_avg)
        self._has(f'| HE18650 | {db} | {sb} |')

    def test_pkg_rev3_variant1_sb_zero(self):
        """Regression: prior doc showed package_rev3 SB = 0.5."""
        db = str(self.r3v1.detailed_builder.offset_pos_avg)
        sb = str(self.r3v1.simple_builder.offset_pos_avg)
        self._has(f'| package_rev3 / variant_1 | {db} | {sb} |')
        self._not('| package_rev3 / variant_1 | 1e-06 | 0.5 |',
                  'package_rev3 SB was 0.5 in the old buggy doc — must not reappear.')

    def test_pkg_rev4c_variant4_db_05(self):
        db = str(self.r4v4.detailed_builder.offset_pos_avg)
        sb = str(self.r4v4.simple_builder.offset_pos_avg)
        self._has(f'| package_rev4_candidate / variant_4 | {db} | {sb} |')

    def test_he18650_m_bonly1d_present_in_doc(self):
        he_list = self.he.m_bonly1d_list
        self._has('[' + ', '.join(he_list) + ']')

    def test_he18650_m_bonly1d_positive_correction_present(self):
        """Doc must confirm HE18650 HAS m_bOnly1D fields (not absent). Guards against regression."""
        self._has(
            'Machine extraction confirms HE18650 **does** contain four `m_bOnly1D` fields',
        )

    def test_source_m_bonly1d_in_doc(self):
        listed = '[' + ', '.join(self.src.m_bonly1d_list) + ']'
        self._has(listed)

    def test_pkg_rev3_m_bonly1d_in_doc(self):
        listed = '[' + ', '.join(self.r3v1.m_bonly1d_list) + ']'
        self._has(listed)

    def test_pkg_rev4c_m_bonly1d_in_doc(self):
        listed = '[' + ', '.join(self.r4v4.m_bonly1d_list) + ']'
        self._has(listed)

    def test_pkg_rev3_capacity_in_doc(self):
        cap = self.r3v1.rct3d_capacity
        self._has(f'| package_rev3 / variant_1 | {cap["m_bSpecifyCapacity"]} | {cap["m_dAhCell"]} |')

    def test_pkg_rev4c_capacity_in_doc(self):
        cap = self.r4v4.rct3d_capacity
        self._has(f'| package_rev4_candidate / variant_4 | {cap["m_bSpecifyCapacity"]} | {cap["m_dAhCell"]} |')

    def test_no_bare_v3_or_v4_in_tables(self):
        """Naming convention: tables must use package_rev3 / variant_N, not bare V3/V4."""
        self._not('| V3 |', 'Bare "V3" table cell — use package_rev3 / variant_N.')
        self._not('| V4 |', 'Bare "V4" table cell — use package_rev4_candidate / variant_N.')


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import traceback

    test_classes = [
        TestTbmFileIntegrity, TestSourceTbm, TestHe18650,
        TestPackageRev3, TestPackageRev4Candidate, TestAuditDocConsistency,
    ]
    total = passed = failed = 0
    for cls in test_classes:
        inst = cls()
        for meth in sorted(m for m in dir(inst) if m.startswith('test_')):
            total += 1
            try:
                getattr(inst, 'setup_method', lambda: None)()
                getattr(inst, meth)()
                print(f'  PASS  {cls.__name__}.{meth}')
                passed += 1
            except Exception:
                print(f'  FAIL  {cls.__name__}.{meth}')
                traceback.print_exc()
                failed += 1
    print(f'\n{passed}/{total} passed, {failed} failed.')
    sys.exit(0 if failed == 0 else 1)
