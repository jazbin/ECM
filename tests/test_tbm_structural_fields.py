#!/usr/bin/env python3
"""
Regression tests for critical TBM structural fields.

Tests verify:
1. Machine-extracted values from source TBM files match the expected ground truth.
2. Generated audit prose/table in docs/TBM_STRUCTURAL_COMPARISON.md is consistent
   with the machine-extracted values — any stale or hand-edited claim in that doc
   that contradicts the files will cause a failure here.

Run:
    python3 -m pytest tests/test_tbm_structural_fields.py -v
    # or directly:
    python3 tests/test_tbm_structural_fields.py
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
TOOLS = WORKSPACE / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from tbm_field_extractor import extract_tbm_fields

SOURCE  = WORKSPACE / 'out' / 'hp2170NCA-ECM.tbm'
HE18650 = WORKSPACE / 'BDS_files' / '_Projects' / 'HE18650' / 'he18650spiral1.tbm'
V3      = WORKSPACE / 'out' / 'test' / 'hp2170-test-v3-tabs-on-sameFace.tbm'
V4      = WORKSPACE / 'out' / 'test' / 'hp2170-test-v4-tabs-off-sameFace.tbm'
AUDIT   = WORKSPACE / 'docs' / 'TBM_STRUCTURAL_COMPARISON.md'


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _flt(v) -> float:
    """Parse a TBM field string to float."""
    return float(v)


# ---------------------------------------------------------------------------
# Ground-truth assertions for extracted values
# ---------------------------------------------------------------------------

class TestSourceTbm:
    """Extracted values from out/hp2170NCA-ECM.tbm."""

    def setup_method(self):
        self.f = extract_tbm_fields(SOURCE)

    def test_db_offset_pos_avg(self):
        assert _flt(self.f.detailed_builder.offset_pos_avg) == 1e-06

    def test_sb_offset_pos_avg(self):
        assert _flt(self.f.simple_builder.offset_pos_avg) == 0.0

    def test_db_sb_offset_pos_avg_independently(self):
        """DB and SB occurrences must be extracted independently, not aliased."""
        db = _flt(self.f.detailed_builder.offset_pos_avg)
        sb = _flt(self.f.simple_builder.offset_pos_avg)
        assert db != sb, (
            f'DB ({db}) and SB ({sb}) values are identical, suggesting both were '
            'read from the same occurrence rather than extracted independently.'
        )

    def test_db_mandrel_width(self):
        assert _flt(self.f.detailed_builder.mandrel_width) == 0.0

    def test_sb_mandrel_width(self):
        assert _flt(self.f.simple_builder.mandrel_width) == 0.0

    def test_db_electrode_overlap_at_start(self):
        # Source DB was a placeholder zero (BDS rejects this)
        assert _flt(self.f.detailed_builder.electrode_overlap_at_start) == 0.0

    def test_sb_electrode_overlap_at_start(self):
        assert _flt(self.f.simple_builder.electrode_overlap_at_start) == 8.0

    def test_m_bonly1d_per_simmod(self):
        """Source TBM has m_bOnly1D = 1 in all four affected SIMODs."""
        vals = self.f.m_bonly1d_list
        assert len(vals) == 4, f'Expected 4 SIMMOD m_bOnly1D fields, got {len(vals)}'
        assert all(int(v) == 1 for v in vals), (
            f'Expected all-ones, got {vals}'
        )

    def test_rct3d_capacity(self):
        cap = self.f.rct3d_capacity
        assert int(cap['m_bSpecifyCapacity']) == 1
        assert _flt(cap['m_dAhCell']) == 5.0


class TestHe18650Tbm:
    """Extracted values from the known-good HE18650 reference TBM."""

    def setup_method(self):
        self.f = extract_tbm_fields(HE18650)

    def test_db_offset_pos_avg(self):
        assert _flt(self.f.detailed_builder.offset_pos_avg) == 0.5

    def test_sb_offset_pos_avg(self):
        assert _flt(self.f.simple_builder.offset_pos_avg) == 0.0

    def test_db_sb_offset_pos_avg_independently(self):
        db = _flt(self.f.detailed_builder.offset_pos_avg)
        sb = _flt(self.f.simple_builder.offset_pos_avg)
        assert db != sb, (
            f'DB ({db}) and SB ({sb}) should differ; if they are the same the '
            'extractor is returning the same occurrence for both.'
        )

    def test_m_bonly1d_per_simmod(self):
        """HE18650 has m_bOnly1D = [1, 0, 0, 0] — first SIMMOD is 1, rest are 0."""
        vals = [int(v) for v in self.f.m_bonly1d_list]
        assert len(vals) == 4, f'Expected 4, got {len(vals)}: {vals}'
        assert vals[0] == 1, f'First SIMMOD m_bOnly1D should be 1, got {vals[0]}'
        assert vals[1:] == [0, 0, 0], f'SIMODs 2-4 should be [0,0,0], got {vals[1:]}'

    def test_he18650_does_contain_m_bonly1d(self):
        """Regression: prior documentation falsely claimed HE18650 has no m_bOnly1D field."""
        assert len(self.f.m_bonly1d_list) > 0, (
            'HE18650 should contain m_bOnly1D fields. '
            'Prior incorrect claim: "HE18650 has NO m_bOnly1D field (defaults to 0)".'
        )


class TestV3Tbm:
    """V3 variant: tabs-on, same-face orientation."""

    def setup_method(self):
        self.f = extract_tbm_fields(V3)

    def test_sb_offset_pos_avg_is_zero(self):
        """Regression: prior audit doc incorrectly showed V3 SB m_dOffsetPosAvg = 0.5."""
        assert _flt(self.f.simple_builder.offset_pos_avg) == 0.0, (
            f'V3 Simple Builder m_dOffsetPosAvg should be 0, '
            f'got {self.f.simple_builder.offset_pos_avg!r}. '
            'Prior doc bug: SB value was falsely reported as 0.5 (the HE18650 DB value).'
        )

    def test_db_offset_pos_avg(self):
        assert _flt(self.f.detailed_builder.offset_pos_avg) == 1e-06

    def test_db_sb_offset_pos_avg_independently(self):
        db = _flt(self.f.detailed_builder.offset_pos_avg)
        sb = _flt(self.f.simple_builder.offset_pos_avg)
        assert db != sb

    def test_db_electrode_overlap_at_start_fixed(self):
        assert _flt(self.f.detailed_builder.electrode_overlap_at_start) == 8.0

    def test_db_mandrel_width_fixed(self):
        assert _flt(self.f.detailed_builder.mandrel_width) == 6.0

    def test_m_bonly1d_all_zero(self):
        vals = [int(v) for v in self.f.m_bonly1d_list]
        assert len(vals) == 4
        assert all(v == 0 for v in vals), f'Expected all-zeros, got {vals}'

    def test_rct3d_capacity(self):
        cap = self.f.rct3d_capacity
        assert int(cap['m_bSpecifyCapacity']) == 1
        assert _flt(cap['m_dAhCell']) == 5.0


class TestV4Tbm:
    """V4 variant: tabs-off, same-face orientation (target configuration)."""

    def setup_method(self):
        self.f = extract_tbm_fields(V4)

    def test_sb_offset_pos_avg_is_zero(self):
        """Regression: prior audit doc incorrectly showed V4 SB m_dOffsetPosAvg = 0.5."""
        assert _flt(self.f.simple_builder.offset_pos_avg) == 0.0, (
            f'V4 Simple Builder m_dOffsetPosAvg should be 0, '
            f'got {self.f.simple_builder.offset_pos_avg!r}.'
        )

    def test_db_sb_offset_pos_avg_independently(self):
        """DB and SB values must be extracted from separate BUILDER sections."""
        db = _flt(self.f.detailed_builder.offset_pos_avg)
        sb = _flt(self.f.simple_builder.offset_pos_avg)
        assert db != sb, (
            f'DB ({db}) == SB ({sb}): suggests both came from the same BUILDER section.'
        )

    def test_db_electrode_overlap_at_start_fixed(self):
        assert _flt(self.f.detailed_builder.electrode_overlap_at_start) == 8.0

    def test_m_bonly1d_all_zero(self):
        vals = [int(v) for v in self.f.m_bonly1d_list]
        assert len(vals) == 4
        assert all(v == 0 for v in vals)

    def test_rct3d_capacity(self):
        cap = self.f.rct3d_capacity
        assert int(cap['m_bSpecifyCapacity']) == 1
        assert _flt(cap['m_dAhCell']) == 5.0


# ---------------------------------------------------------------------------
# Consistency regression: audit doc vs extracted values
# ---------------------------------------------------------------------------

class TestAuditDocConsistency:
    """
    The generated doc TBM_STRUCTURAL_COMPARISON.md must never contradict the files.

    This class re-extracts all values and then parses the markdown to check every
    critical claim in the table rows.  If the doc is regenerated from the generator
    script these tests are redundant; but they catch the case where the doc was
    hand-edited or the generator produced stale content without being re-run.
    """

    def setup_method(self):
        self.src = extract_tbm_fields(SOURCE)
        self.he  = extract_tbm_fields(HE18650)
        self.v3  = extract_tbm_fields(V3)
        self.v4  = extract_tbm_fields(V4)
        assert AUDIT.exists(), f'Audit doc not found: {AUDIT}'
        self.doc = AUDIT.read_text(encoding='utf-8')

    # ---- helpers ----

    def _assert_in_doc(self, substring: str, context: str = ''):
        assert substring in self.doc, (
            f'Expected to find {substring!r} in {AUDIT.name}. {context}'
        )

    def _assert_not_in_doc(self, substring: str, context: str = ''):
        assert substring not in self.doc, (
            f'Found {substring!r} in {AUDIT.name} but it should not be there. {context}'
        )

    # ---- m_dOffsetPosAvg ----

    def test_doc_source_db_offset_pos_avg(self):
        expected = str(self.src.detailed_builder.offset_pos_avg)
        self._assert_in_doc(f'| Source | {expected} |',
                            'Source DB m_dOffsetPosAvg mismatch in audit table.')

    def test_doc_source_sb_offset_pos_avg(self):
        sb = str(self.src.simple_builder.offset_pos_avg)
        # The Source row in the offset table: "| Source | <db> | <sb> |"
        db = str(self.src.detailed_builder.offset_pos_avg)
        self._assert_in_doc(f'| Source | {db} | {sb} |')

    def test_doc_he18650_db_offset_pos_avg(self):
        db = str(self.he.detailed_builder.offset_pos_avg)
        sb = str(self.he.simple_builder.offset_pos_avg)
        self._assert_in_doc(f'| HE18650 | {db} | {sb} |',
                            'HE18650 m_dOffsetPosAvg row mismatch.')

    def test_doc_v3_sb_offset_pos_avg_is_zero(self):
        """Regression: doc must NOT claim V3 SB = 0.5."""
        db = str(self.v3.detailed_builder.offset_pos_avg)
        sb = str(self.v3.simple_builder.offset_pos_avg)
        self._assert_in_doc(f'| V3 | {db} | {sb} |',
                            'V3 m_dOffsetPosAvg row mismatch (prior bug: SB was shown as 0.5).')
        # Explicitly guard against the known-bad value
        self._assert_not_in_doc('| V3 | 1e-06 | 0.5 |',
                                'V3 SB was 0.5 in a prior buggy doc — must not reappear.')

    def test_doc_v4_sb_offset_pos_avg_is_zero(self):
        """Regression: doc must NOT claim V4 SB = 0.5."""
        db = str(self.v4.detailed_builder.offset_pos_avg)
        sb = str(self.v4.simple_builder.offset_pos_avg)
        self._assert_in_doc(f'| V4 | {db} | {sb} |',
                            'V4 m_dOffsetPosAvg row mismatch.')
        self._assert_not_in_doc('| V4 | 1e-06 | 0.5 |')

    # ---- m_bOnly1D ----

    def test_doc_he18650_m_bonly1d_present(self):
        """Regression: prior doc falsely stated HE18650 has no m_bOnly1D field."""
        he_list = self.he.m_bonly1d_list
        listed  = '[' + ', '.join(he_list) + ']'
        self._assert_in_doc(listed,
                            f'HE18650 m_bOnly1D list {listed!r} not in audit doc.')

    def test_doc_he18650_m_bonly1d_not_described_as_absent(self):
        """The incorrect narrative 'HE18650 has NO m_bOnly1D field' must not appear."""
        bad_phrases = [
            'HE18650 has NO m_bOnly1D',
            'HE18650 has no m_bOnly1D',
            'does not contain m_bOnly1D',
            'does not have m_bOnly1D',
        ]
        for phrase in bad_phrases:
            self._assert_not_in_doc(phrase,
                f'Found stale false claim: {phrase!r}. '
                'HE18650 does contain m_bOnly1D = [1, 0, 0, 0].')

    def test_doc_source_m_bonly1d(self):
        src_list = self.src.m_bonly1d_list
        listed = '[' + ', '.join(src_list) + ']'
        self._assert_in_doc(listed)

    def test_doc_v3_m_bonly1d(self):
        listed = '[' + ', '.join(self.v3.m_bonly1d_list) + ']'
        self._assert_in_doc(listed)

    def test_doc_v4_m_bonly1d(self):
        listed = '[' + ', '.join(self.v4.m_bonly1d_list) + ']'
        self._assert_in_doc(listed)

    # ---- m_dMandrelWidth ----

    def test_doc_source_mandrel_width(self):
        db = str(self.src.detailed_builder.mandrel_width)
        sb = str(self.src.simple_builder.mandrel_width)
        self._assert_in_doc(f'| Source | {db} | {sb} |')

    def test_doc_v3_mandrel_width(self):
        db = str(self.v3.detailed_builder.mandrel_width)
        sb = str(self.v3.simple_builder.mandrel_width)
        self._assert_in_doc(f'| V3 | {db} | {sb} |')

    def test_doc_v4_mandrel_width(self):
        db = str(self.v4.detailed_builder.mandrel_width)
        sb = str(self.v4.simple_builder.mandrel_width)
        self._assert_in_doc(f'| V4 | {db} | {sb} |')

    # ---- m_dElectrodeOverlapAtStart ----

    def test_doc_source_electrode_overlap(self):
        db = str(self.src.detailed_builder.electrode_overlap_at_start)
        sb = str(self.src.simple_builder.electrode_overlap_at_start)
        self._assert_in_doc(f'| Source | {db} | {sb} |')

    def test_doc_v3_electrode_overlap(self):
        db = str(self.v3.detailed_builder.electrode_overlap_at_start)
        sb = str(self.v3.simple_builder.electrode_overlap_at_start)
        self._assert_in_doc(f'| V3 | {db} | {sb} |')

    def test_doc_v4_electrode_overlap(self):
        db = str(self.v4.detailed_builder.electrode_overlap_at_start)
        sb = str(self.v4.simple_builder.electrode_overlap_at_start)
        self._assert_in_doc(f'| V4 | {db} | {sb} |')

    # ---- RCRTable 3D capacity ----

    def test_doc_source_rct3d_capacity(self):
        cap = self.src.rct3d_capacity
        spec = str(cap.get('m_bSpecifyCapacity', ''))
        ah   = str(cap.get('m_dAhCell', ''))
        self._assert_in_doc(f'| Source | {spec} | {ah} |')

    def test_doc_v3_rct3d_capacity(self):
        cap = self.v3.rct3d_capacity
        spec = str(cap.get('m_bSpecifyCapacity', ''))
        ah   = str(cap.get('m_dAhCell', ''))
        self._assert_in_doc(f'| V3 | {spec} | {ah} |')

    def test_doc_v4_rct3d_capacity(self):
        cap = self.v4.rct3d_capacity
        spec = str(cap.get('m_bSpecifyCapacity', ''))
        ah   = str(cap.get('m_dAhCell', ''))
        self._assert_in_doc(f'| V4 | {spec} | {ah} |')


# ---------------------------------------------------------------------------
# Standalone runner (no pytest required)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import traceback

    total = 0
    passed = 0
    failed = 0

    test_classes = [
        TestSourceTbm, TestHe18650Tbm, TestV3Tbm, TestV4Tbm,
        TestAuditDocConsistency,
    ]

    for cls in test_classes:
        inst = cls()
        methods = [m for m in dir(inst) if m.startswith('test_')]
        for meth in methods:
            total += 1
            try:
                inst.setup_method()
                getattr(inst, meth)()
                print(f'  PASS  {cls.__name__}.{meth}')
                passed += 1
            except Exception as e:
                print(f'  FAIL  {cls.__name__}.{meth}')
                traceback.print_exc()
                failed += 1

    print(f'\n{passed}/{total} passed, {failed} failed.')
    sys.exit(0 if failed == 0 else 1)
