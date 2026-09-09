#!/usr/bin/env python3
"""Regression tests for TBM MODELMAP selection and the RCR candidate patch."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("validate_tbm_modelmap", ROOT / "tools" / "validate_tbm_modelmap.py")
generator = load_module("generate_tbm_rcr_candidate", ROOT / "tools" / "generate_tbm_rcr_candidate.py")


class TestModelMapParser(unittest.TestCase):
    def test_valid_rcr_fixture(self):
        text = """<SIMMOD>\nRCRTable 3D\nLiIon\\Spiral\nIET\n\tm_bSpecifyCapacity\t=\t1\t!\n\tm_dAhCell\t=\t5.0\t!\n\tm_nRCRParameterSets\t=\t3\t!\n\tm_bOnly1D\t=\t0\t!\n</SIMMOD>\n<MODELMAP>\n\tElectrolyte\t=\tGeneral Electrolyte\n\tIET\t=\tRCRTable 3D\n\tThermal\t=\tDistributed\n</MODELMAP>\n"""
        findings = validator.validate_text(
            text,
            expected_iet="RCRTable 3D",
            expected_capacity_ah=5.0,
            require_all_only1d_zero=True,
        )
        self.assertFalse([f for f in findings if f.severity == "FAIL"], findings)

    def test_wrong_selector_fails_expected_rcr(self):
        text = """<SIMMOD>\nDistributed 3D\nLiIon\\Spiral\nIET\n</SIMMOD>\n<SIMMOD>\nRCRTable 3D\nLiIon\\Spiral\nIET\n\tm_bSpecifyCapacity\t=\t1\t!\n\tm_dAhCell\t=\t5.0\t!\n\tm_nRCRParameterSets\t=\t3\t!\n</SIMMOD>\n<MODELMAP>\n\tIET\t=\tDistributed 3D\n</MODELMAP>\n"""
        findings = validator.validate_text(text, expected_iet="RCRTable 3D")
        self.assertTrue(any(f.code == "modelmap_iet_expected" and f.severity == "FAIL" for f in findings))

    def test_selector_to_missing_simmod_fails(self):
        text = """<MODELMAP>\n\tIET\t=\tRCRTable 3D\n</MODELMAP>\n"""
        findings = validator.validate_text(text)
        self.assertTrue(any(f.code == "modelmap_iet_target_missing" and f.severity == "FAIL" for f in findings))

    def test_capacity_mismatch_fails(self):
        text = """<SIMMOD>\nRCRTable 3D\nLiIon\\Spiral\nIET\n\tm_bSpecifyCapacity\t=\t1\t!\n\tm_dAhCell\t=\t1.1\t!\n\tm_nRCRParameterSets\t=\t3\t!\n</SIMMOD>\n<MODELMAP>\n\tIET\t=\tRCRTable 3D\n</MODELMAP>\n"""
        findings = validator.validate_text(text, expected_iet="RCRTable 3D", expected_capacity_ah=5.0)
        self.assertTrue(any(f.code == "rcr_capacity_value" and f.severity == "FAIL" for f in findings))


class TestRepositoryEvidence(unittest.TestCase):
    def _assert_reference_selector(self, relpath: str, expected: str):
        path = ROOT / relpath
        text = path.read_text(encoding="latin-1")
        modelmap = validator.extract_modelmap(text)
        simmods = validator.extract_simmods(text)
        self.assertEqual(modelmap.get("IET"), expected)
        self.assertIn(expected, simmods)

    def test_star_validation_tbm_selects_rcr(self):
        self._assert_reference_selector(
            "tbm_validation/in_StarCCM_bds/validationBattery.tbm", "RCRTable 3D"
        )

    def test_siemens_dist_reference_selects_distributed3d(self):
        self._assert_reference_selector(
            "tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm", "Distributed 3D"
        )

    def test_star_cylindrical_tutorial_selects_ntgp(self):
        self._assert_reference_selector(
            "tbm_validation/in_StarCCM_bds/tutorialCylindricalCell.tbm", "NTGPTable 3D"
        )

    def test_frozen_v4_variant3_is_wrong_for_expected_rcr(self):
        path = ROOT / "out" / "v4_candidate" / "hp2170-v4c-v3-tabs-on-sameFace.tbm"
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), generator.BASE_SHA256)
        findings = validator.validate_text(raw.decode("latin-1"), expected_iet="RCRTable 3D")
        self.assertTrue(any(f.code == "modelmap_iet_expected" and f.severity == "FAIL" for f in findings))

    def test_patch_changes_only_modelmap_iet_line(self):
        path = ROOT / "out" / "v4_candidate" / "hp2170-v4c-v3-tabs-on-sameFace.tbm"
        raw = path.read_bytes()
        patched = generator.patch_modelmap(raw)
        before = raw.splitlines()
        after = patched.splitlines()
        diffs = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(diffs), 1)
        self.assertIn(b"Distributed 3D", diffs[0][0])
        self.assertIn(b"RCRTable 3D", diffs[0][1])

        findings = validator.validate_text(
            patched.decode("latin-1"),
            expected_iet="RCRTable 3D",
            expected_capacity_ah=5.0,
            require_all_only1d_zero=True,
        )
        self.assertFalse([f for f in findings if f.severity == "FAIL"], findings)


if __name__ == "__main__":
    unittest.main()
