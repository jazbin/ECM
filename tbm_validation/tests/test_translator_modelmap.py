#!/usr/bin/env python3
"""Regression tests for translate_tbm_from_openfoam.py MODELMAP wiring.

Covers:
  A. DIST-style template → apply_modelmap_iet produces IET = RCRTable 3D
  B. Already-RCR template → idempotent
  C. Missing RCR SIMMOD → fail closed (ValueError)
  D. Multiple MODELMAP/IET entries → fail closed (ValueError)
  E. RCR numerical data is unchanged by the selector operation
"""

from __future__ import annotations

import importlib.util
import re
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


translator = load_module(
    "translate_tbm_from_openfoam",
    ROOT / "tools" / "translate_tbm_from_openfoam.py",
)


def _fixture(iet_selector: str, simmods: tuple[str, ...] = ("Distributed 3D", "RCRTable 3D")) -> str:
    simmod_blocks = "\n".join(f"<SIMMOD>\n{n}\n</SIMMOD>" for n in simmods)
    modelmap = f"<MODELMAP>\n\tIET\t=\t{iet_selector}\n</MODELMAP>"
    return f"{simmod_blocks}\n{modelmap}\n"


def _rcr_numbers(content: str) -> list[str]:
    """Extract all RCR_V_Ro/Rp lines so we can verify numerical content is unchanged."""
    return re.findall(r'(?m)^\t*Set\[\d+\]_RCR_V_(?:Ro|Rp|Rp1|V|SOC|tau|tau1)_\d+\t[^\r\n]+', content)


class TestApplyModelMapIET(unittest.TestCase):
    """Unit tests for the apply_modelmap_iet helper."""

    def test_a_dist_template_becomes_rcr(self):
        """A: DIST-selector template → IET changes to RCRTable 3D."""
        content = _fixture("Distributed 3D")
        result = translator.apply_modelmap_iet(content, "RCRTable 3D")
        mm = re.search(r'<MODELMAP>(.*?)</MODELMAP>', result, re.DOTALL)
        self.assertIsNotNone(mm)
        iet_lines = [l for l in mm.group(1).splitlines() if 'IET' in l]
        self.assertEqual(len(iet_lines), 1)
        self.assertIn("RCRTable 3D", iet_lines[0])
        self.assertNotIn("Distributed 3D", iet_lines[0])

    def test_b_already_rcr_is_idempotent(self):
        """B: Already-RCR template → content returned byte-identical."""
        content = _fixture("RCRTable 3D")
        result = translator.apply_modelmap_iet(content, "RCRTable 3D")
        self.assertEqual(content, result)

    def test_c_missing_simmod_raises(self):
        """C: No RCRTable 3D SIMMOD present → ValueError (fail closed)."""
        content = (
            "<SIMMOD>\nDistributed 3D\n</SIMMOD>\n"
            "<MODELMAP>\n\tIET\t=\tDistributed 3D\n</MODELMAP>\n"
        )
        with self.assertRaises(ValueError):
            translator.apply_modelmap_iet(content, "RCRTable 3D")

    def test_d_multiple_modelmap_raises(self):
        """D: Two MODELMAP blocks → ValueError (fail closed)."""
        content = _fixture("Distributed 3D") + "<MODELMAP>\n\tIET\t=\tDistributed 3D\n</MODELMAP>\n"
        with self.assertRaises(ValueError):
            translator.apply_modelmap_iet(content, "RCRTable 3D")

    def test_d_multiple_iet_in_block_raises(self):
        """D: Two IET entries in one MODELMAP → ValueError (fail closed)."""
        content = (
            "<SIMMOD>\nRCRTable 3D\n</SIMMOD>\n"
            "<MODELMAP>\n\tIET\t=\tDistributed 3D\n\tIET\t=\tRCRTable 3D\n</MODELMAP>\n"
        )
        with self.assertRaises(ValueError):
            translator.apply_modelmap_iet(content, "RCRTable 3D")

    def test_e_rcr_data_unchanged(self):
        """E: RCR numerical fields are not touched by the selector operation."""
        rcr_data = (
            "\t\tSet[0]_RCR_V_Ro_1\t=\t0.00814\t!\t\t!\tSet[0]_RCR_V_Ro_1\n"
            "\t\tSet[0]_RCR_V_Rp_1\t=\t0.00400\t!\t\t!\tSet[0]_RCR_V_Rp_1\n"
            "\t\tSet[0]_RCR_V_V_1\t=\t3.65000\t!\t\t!\tSet[0]_RCR_V_V_1\n"
        )
        simmod_blocks = (
            f"<SIMMOD>\nDistributed 3D\n</SIMMOD>\n"
            f"<SIMMOD>\nRCRTable 3D\n{rcr_data}</SIMMOD>\n"
        )
        content = simmod_blocks + "<MODELMAP>\n\tIET\t=\tDistributed 3D\n</MODELMAP>\n"
        result = translator.apply_modelmap_iet(content, "RCRTable 3D")
        # All RCR field lines must survive verbatim
        self.assertIn("Set[0]_RCR_V_Ro_1\t=\t0.00814", result)
        self.assertIn("Set[0]_RCR_V_Rp_1\t=\t0.00400", result)
        self.assertIn("Set[0]_RCR_V_V_1\t=\t3.65000", result)


class TestApplyRCRTable3DIntegration(unittest.TestCase):
    """Integration: apply_rcrtable_3d now sets MODELMAP IET to RCRTable 3D."""

    def _build_ecm(self) -> dict:
        """Minimal ECM dict sufficient for apply_rcrtable_3d."""
        soc = [-0.08, 0.28, 0.64, 1.00]
        return {
            "capacity_ah": 5.0,
            "sets": [{
                "T_K":  288.15,
                "SOC":  soc,
                "V":    [3.60, 3.80, 4.00, 4.18],
                "Ro":   [0.0086, 0.0080, 0.0075, 0.0072],
                "Rp":   [0.0040, 0.0040, 0.0040, 0.0040],
                "Rp1":  [0.0020, 0.0020, 0.0020, 0.0020],
                "tau":  [8.0, 8.0, 8.0, 8.0],
                "tau1": [40.0, 40.0, 40.0, 40.0],
            }],
            "dudt_soc": soc,
            "dudt_val": [0.0, 0.0, 0.0, 0.0],
            "source": "test-fixture",
        }

    def _base_tbm_dist(self) -> str:
        """Minimal TBM skeleton with Distributed 3D selector and RCRTable 3D SIMMOD."""
        return (
            "<SIMMOD>\n"
            "Distributed 3D\n"
            "LiIon\\Spiral\n"
            "IET\n"
            "</SIMMOD>\n"
            "<SIMMOD>\n"
            "RCRTable 3D\n"
            "LiIon\\Spiral\n"
            "IET\n"
            "\tm_bSpecifyCapacity\t=\t1\t!\n"
            "\tm_dAhCell\t=\t5.0\t!\t\t!\tCell Capacity. Ah\n"
            "\tm_nRCRParameterSets\t=\t3\t!\t\t!\tNo. RCR Data Sets\n"
            "\tRCR_Veq_nSize\t=\t4\t!\n"
            "\tm_bOnly1D\t=\t0\t!\n"
            "\tm_dCondX_W_permK\t=\t1.4\t!\t\t!\tConductivity X dir, W/m.K\n"
            "\tm_dCondY_W_permK\t=\t1.4\t!\t\t!\tConductivity Y dir, W/m.K\n"
            "\tm_dCondZ_W_permK\t=\t29.0\t!\t\t!\tConductivity Z dir, W/m.K\n"
            "\tm_dkx_WpermK\t=\t1.4\t!\t\t!\tThermal conductivity in x, W/m-K\n"
            "\tm_dky_WpermK\t=\t1.4\t!\t\t!\tThermal conductivity in y, W/m-K\n"
            "\tm_dkz_WpermK\t=\t29.0\t!\t\t!\tThermal conductivity in z, W/m-K\n"
            "</SIMMOD>\n"
            "<MODELMAP>\n"
            "\tIET\t=\tDistributed 3D\n"
            "</MODELMAP>\n"
        )

    def test_a_translation_from_dist_produces_rcr_iet(self):
        """A integration: apply_rcrtable_3d on DIST template → IET = RCRTable 3D."""
        content = self._base_tbm_dist()
        result = translator.apply_rcrtable_3d(content, self._build_ecm(), 1.4, 29.0)
        mm = re.search(r'<MODELMAP>(.*?)</MODELMAP>', result, re.DOTALL)
        self.assertIsNotNone(mm)
        iet_lines = [l for l in mm.group(1).splitlines() if 'IET' in l]
        self.assertEqual(len(iet_lines), 1)
        self.assertIn("RCRTable 3D", iet_lines[0])
        self.assertNotIn("Distributed 3D", iet_lines[0])

    def test_b_already_rcr_apply_is_idempotent(self):
        """B integration: apply_rcrtable_3d on already-RCR template → IET unchanged."""
        content = self._base_tbm_dist().replace(
            "\tIET\t=\tDistributed 3D\n", "\tIET\t=\tRCRTable 3D\n"
        )
        result = translator.apply_rcrtable_3d(content, self._build_ecm(), 1.4, 29.0)
        mm = re.search(r'<MODELMAP>(.*?)</MODELMAP>', result, re.DOTALL)
        iet_lines = [l for l in mm.group(1).splitlines() if 'IET' in l]
        self.assertEqual(len(iet_lines), 1)
        self.assertIn("RCRTable 3D", iet_lines[0])

    def test_e_numerical_data_from_dist_base_matches_ecm_input(self):
        """E integration: RCR numerical values written by apply_rcrtable_3d match ECM input."""
        content = self._base_tbm_dist()
        ecm = self._build_ecm()
        result = translator.apply_rcrtable_3d(content, ecm, 1.4, 29.0)
        # Spot-check one Ro value from the only Set
        expected_ro = ecm["sets"][0]["Ro"][0]
        self.assertIn(f"Set[0]_RCR_V_Ro_1\t=\t{expected_ro}", result)


if __name__ == "__main__":
    unittest.main()
