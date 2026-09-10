#!/usr/bin/env python3
"""
validate_tbm.py — Independent static validator for STAR-CCM+ TBM files.

Usage:
    python3 validate_tbm.py <file.tbm> [--ref <reference.tbm>] [--verbose]
    python3 validate_tbm.py --batch tbm_validation/variants/v3_package_20260909/

Produces PASS / WARN / FAIL findings for each check.
Does NOT modify any file.

IMPORTANT: This validator checks for known failure modes and structural
anomalies. A STATIC_PASS here means no known static defects were found.
It does NOT mean STAR-CCM+ will accept the file (STAR_IMPORT_PASS is
a separate, higher-confidence state only achieved by actual STAR import).

Design principle: every check that queries a field inside a <SIMMOD> block
MUST use get_simmod_field() with the specific block type. Never use flat
get()/get_float() calls for model-specific parameters — the TBM format
repeats field names across multiple SIMMOD blocks and the first occurrence
is NOT guaranteed to belong to the active model. The RCRTable 3D block
is our active electrochemical model for the 2170 cell.

Reference file: best results when a known-good Siemens TBM is provided
as --ref (e.g. tbm_validation/reference/HE18650/he18650spiral1.tbm).

Severity levels:
  FAIL  — likely causes STAR-CCM+ import failure or silent wrong geometry
  WARN  — possible issue; needs human review; not confirmed fatal
  INFO  — informational; no action required but worth knowing
  PASS  — check ran and found no issue
"""

import re
import sys
import math
import hashlib
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Known reference values (from docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md
# and python/params.csv)
# ---------------------------------------------------------------------------
REF_2170 = {
    "can_od_mm":        21.09,
    "can_height_mm":    70.02,
    "can_wall_mm":      0.2313,
    "can_id_mm":        21.09 - 2 * 0.2313,   # 20.6274
    "jellyroll_h_mm":   65.11,
    "mandrel_d_mm":     6.0,
    "capacity_ah":      5.0,
    "pos_coll_width_mm": 64.11,
    "neg_coll_width_mm": 65.11,
    "n_rcr_sets":       3,
    "rcr_temps_k":      [288.15, 298.15, 308.15],
    "n_soc_points":     7,
}

# R0 plausible range (Ohm, at 25°C)
R0_RANGE = (1e-4, 0.1)

# m_bOnly1D per-SIMMOD-block reference table.
# Derived by machine extraction from: HE18650, HP18650-template, LiIonSpiral,
# tutorialCylindricalCell, HV-LiCoO2f, HP18650-DIST (see TBM_STRUCTURAL_COMPARISON.md)
# Format: {simmod_type: {tbm_name: value}}
M_BONLY1D_REFERENCE = {
    "Distributed 3D": {
        "HE18650":       "1",
        "HP18650-templ": "1",
        "LiIonSpiral":   "0",
        "Tutorial":      "0",
        "HV-LiCoO2f":   "0",
        "HP18650-DIST":  "1",
    },
    "Distributed": {
        "HE18650":       "0",
        "HP18650-templ": "false",
        "LiIonSpiral":   "true",   # Note: 'true' in STAR install = 1
        "Tutorial":      "true",
        "HV-LiCoO2f":   "false",
        "HP18650-DIST":  "1",
    },
    "NTGPTable 3D": {
        "HE18650":       "0",
        "HP18650-templ": "0",
        "LiIonSpiral":   "0",
        "Tutorial":      "0",
        "HV-LiCoO2f":   "0",
        "HP18650-DIST":  "1",
    },
    "RCRTable 3D": {
        "HE18650":       "0",
        "HP18650-templ": "0",
        "LiIonSpiral":   "0",
        "Tutorial":      "0",
        "HV-LiCoO2f":   "0",
        "HP18650-DIST":  "1",    # HP18650-DIST is the only outlier
    },
}
# Consensus value for the RCRTable 3D block (our active model): 0
# All working references except HP18650-DIST (unknown import status) have 0.
RCR_BLOCK_ONLY1D_CONSENSUS = "0"


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    level: str
    check: str
    message: str
    field: str = ""
    value: str = ""
    expected: str = ""


# ---------------------------------------------------------------------------
# TBM parser
# ---------------------------------------------------------------------------
class TBMParser:
    """Parse a TBM file into structured sections.

    The TBM format has three distinct zones:
    1. Top-level fields and blocks (<BUILDER>, <REPORT>, Package, DataSheet, ...)
    2. <SIMMOD> blocks — each has a type identifier and key=value fields
    3. Fields inside <SIMMOD> blocks may share names with each other and with
       top-level fields. Never use flat lookup for SIMMOD-specific checks.
    """

    def __init__(self, path: Path):
        self.path = path
        self.raw = path.read_bytes()
        self.lines = self.raw.split(b"\n")
        self._top_fields: dict[str, list[str]] = {}   # flat first-occurrence store (top-level only)
        self._simmod_blocks: list[dict] = []
        self._builder_fields: dict[str, list[str]] = {}  # from <BUILDER> block
        self._report_fields: dict[str, str] = {}          # from <REPORT> block
        self._parse()

    def _parse(self):
        current_simmod = None
        in_builder = False
        in_report = False

        for i, raw_line in enumerate(self.lines):
            line = raw_line.decode("latin-1", errors="replace")
            stripped = line.strip()

            # Block boundary tracking
            if "<BUILDER>" in stripped:
                in_builder = True
                continue
            if "</BUILDER>" in stripped:
                in_builder = False
                continue
            if "<REPORT>" in stripped:
                in_report = True
                continue
            if "</REPORT>" in stripped:
                in_report = False
                continue
            if "<SIMMOD>" in stripped:
                current_simmod = {"start_line": i + 1, "type": "", "fields": {}}
                continue
            if "</SIMMOD>" in stripped:
                if current_simmod is not None:
                    self._simmod_blocks.append(current_simmod)
                current_simmod = None
                continue

            # Determine SIMMOD type from first non-field line inside <SIMMOD>
            if current_simmod is not None and current_simmod["type"] == "" and stripped:
                if not re.match(r'^[\t ]*(.+?)\s*=', line):
                    current_simmod["type"] = stripped
                    continue

            # REPORT block uses a different format:
            #   field TAB = TAB value TAB flag(0|1) TAB ! comment
            # The value is followed by a TAB and then a BDS-computed flag — the main
            # field regex (which excludes TAB from the value group) cannot capture this
            # correctly, so handle REPORT lines first with a dedicated pattern.
            if in_report and current_simmod is None:
                # REPORT format: field [tabs/spaces] = [tabs/spaces] value [tabs/spaces] flag(0|1) ...
                rm = re.match(r'^[\t ]*([^\t=!]+?)[\t ]*=[\t ]+(\S+)(?:[\t ]+\d+)?', line)
                if rm:
                    self._report_fields[rm.group(1).strip()] = rm.group(2).strip()
                continue

            # Field parsing (non-REPORT lines)
            m = re.match(r'^[\t ]*([^\t=!]+?)\s*=\s*([^\t\r\n!]+?)(?:\s*!.*)?$', line)
            if m:
                fname = m.group(1).strip()
                fval  = m.group(2).strip()
                if not fname:
                    continue

                if current_simmod is not None:
                    current_simmod["fields"][fname] = fval
                    if fname == "m_bOnly1D":
                        current_simmod["m_bOnly1D"] = fval
                elif in_builder:
                    if fname not in self._builder_fields:
                        self._builder_fields[fname] = []
                    self._builder_fields[fname].append(fval)
                else:
                    if fname not in self._top_fields:
                        self._top_fields[fname] = []
                    self._top_fields[fname].append(fval)

    # -- SIMMOD-aware accessors --

    def get_simmod_field(self, simmod_type: str, field: str, default=None) -> Optional[str]:
        """Return field value from first SIMMOD block whose type starts with simmod_type (case-insensitive)."""
        for b in self._simmod_blocks:
            if b["type"].lower().startswith(simmod_type.lower()):
                v = b["fields"].get(field)
                if v is not None:
                    return v
        return default

    def get_simmod_float(self, simmod_type: str, field: str, default=None) -> Optional[float]:
        v = self.get_simmod_field(simmod_type, field)
        if v is None:
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def simmod_blocks_by_type(self, simmod_type: str) -> list[dict]:
        return [b for b in self._simmod_blocks if b["type"].lower().startswith(simmod_type.lower())]

    # -- BUILDER-aware accessors --

    def get_builder_field(self, field: str, index: int = 0, default=None) -> Optional[str]:
        """Return field from BUILDER block. index=0 is Detailed Builder occurrence; index=1 is Simple Builder."""
        vals = self._builder_fields.get(field)
        if vals is None or index >= len(vals):
            return default
        return vals[index]

    def get_builder_float(self, field: str, index: int = 0, default=None) -> Optional[float]:
        v = self.get_builder_field(field, index)
        if v is None:
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    # -- Top-level accessors (Package, DataSheet) --

    def get(self, name: str, default=None) -> Optional[str]:
        """Return first top-level occurrence value."""
        vals = self._top_fields.get(name)
        return vals[0] if vals else default

    def get_float(self, name: str, default=None) -> Optional[float]:
        v = self.get(name)
        if v is None:
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def get_all(self, name: str) -> list[str]:
        return self._top_fields.get(name, [])

    # -- REPORT accessors --

    def get_report(self, field: str, default=None) -> Optional[str]:
        return self._report_fields.get(field, default)

    def get_report_float(self, field: str, default=None) -> Optional[float]:
        v = self.get_report(field)
        if v is None:
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    # -- Metadata --

    @property
    def simmod_types(self) -> list[str]:
        return [b["type"] for b in self._simmod_blocks]

    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()

    def line_count(self) -> int:
        return len(self.lines)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------
class TBMValidator:
    def __init__(self, tbm: TBMParser, ref: Optional[TBMParser] = None, verbose: bool = False):
        self.tbm = tbm
        self.ref = ref
        self.verbose = verbose
        self.findings: list[Finding] = []

    def _add(self, level, check, message, field="", value="", expected=""):
        self.findings.append(Finding(level, check, message, field, value, expected))

    def run_all(self):
        self.check_file_sanity()
        self.check_mode_compatibility()
        self.check_package_geometry()
        self.check_builder_geometry()
        self.check_cross_field_consistency()
        self.check_report_block()
        self.check_volume_consistency()
        self.check_electrochemical_tables()
        self.check_datasheet_residuals()
        self.check_units_audit()
        if self.ref:
            self.check_structural_vs_reference()
        return self.findings

    # -----------------------------------------------------------------------
    # 1. File / schema sanity
    # -----------------------------------------------------------------------
    def check_file_sanity(self):
        t = self.tbm
        size = len(t.raw)
        if size < 1000:
            self._add("FAIL", "file_size", f"File is suspiciously small ({size} bytes).")
            return
        self._add("PASS", "file_size", f"File size {size} bytes, {t.line_count()} lines.")

        if b"\x00" in t.raw:
            self._add("WARN", "encoding", "File contains null bytes — possible binary corruption.")
        else:
            self._add("PASS", "encoding", "No null bytes found.")

        open_count  = t.raw.count(b"<SIMMOD>")
        close_count = t.raw.count(b"</SIMMOD>")
        if open_count != close_count:
            self._add("FAIL", "simmod_balance",
                      f"Unbalanced SIMMOD tags: {open_count} open, {close_count} close.")
        else:
            self._add("PASS", "simmod_balance", f"{open_count} balanced SIMMOD blocks.")

        for marker in [b"<SIMMOD>", b"RCRTable 3D", b"<BUILDER>", b"Package m_dextDiameter"]:
            if marker not in t.raw:
                self._add("WARN", "required_blocks",
                          f"Expected marker not found: {marker.decode()!r}. File may be incomplete.")

        if b"RCRTable 3D" in t.raw:
            self._add("PASS", "required_blocks", "RCRTable 3D block present.")

        ext_d_vals = t.get_all("Package m_dextDiameter")
        if len(ext_d_vals) > 1:
            self._add("WARN", "duplicate_package",
                      f"Package m_dextDiameter appears {len(ext_d_vals)} times: {ext_d_vals}.")
        elif len(ext_d_vals) == 1:
            self._add("PASS", "duplicate_package", "Single Package m_dextDiameter definition.")

    # -----------------------------------------------------------------------
    # 2. Mode compatibility — per-SIMMOD-block analysis
    # -----------------------------------------------------------------------
    def check_mode_compatibility(self):
        t = self.tbm
        blocks_with_flag = [(b["type"], b.get("m_bOnly1D")) for b in t._simmod_blocks
                             if b.get("m_bOnly1D") is not None]

        if not blocks_with_flag:
            self._add("INFO", "m_bOnly1D",
                      "No m_bOnly1D fields found. The known-good HE18650 reference contains "
                      "m_bOnly1D = [1, 0, 0, 0]; absence in this file is therefore unconfirmed.")
            return

        # Build per-block table
        table_lines = []
        for btype, val in blocks_with_flag:
            raw_val = str(val).lower().strip()
            numeric = 0 if raw_val in ("0", "false") else 1 if raw_val in ("1", "true") else -1
            ref_vals = M_BONLY1D_REFERENCE.get(btype, {})
            ref_str = ", ".join(f"{k}={v}" for k, v in ref_vals.items()) if ref_vals else "no reference data"
            table_lines.append(f"  {btype}: {val!r} (numeric={numeric}; refs: {ref_str})")

        self._add("INFO", "m_bOnly1D_table",
                  "Per-SIMMOD m_bOnly1D values:\n" + "\n".join(table_lines))

        # Critical check: the RCRTable 3D block (our active model)
        rcr_val = t.get_simmod_field("RCRTable", "m_bOnly1D")
        if rcr_val is not None:
            rcr_norm = str(rcr_val).lower().strip()
            rcr_numeric = 0 if rcr_norm in ("0", "false") else 1 if rcr_norm in ("1", "true") else -1
            if rcr_numeric == 0:
                self._add("PASS", "m_bOnly1D_rcrtable",
                          f"RCRTable 3D block m_bOnly1D = {rcr_val!r} (0/false). "
                          "Matches consensus from HE18650, HP18650-template, LiIonSpiral, Tutorial, HV-LiCoO2f. "
                          "This is the active electrochemical model block.")
            elif rcr_numeric == 1:
                self._add("WARN", "m_bOnly1D_rcrtable",
                          f"RCRTable 3D block m_bOnly1D = {rcr_val!r} (1 = 1D-only mode). "
                          "All working references (HE18650, HP18650-template, LiIonSpiral, Tutorial) have 0 here. "
                          "Only HP18650-DIST has 1 — its 3D import status is unknown. "
                          "BDS logged 'Warning: m_bOnly1D option is not supported' in V2 package when all blocks were 1.",
                          field="RCRTable 3D / m_bOnly1D", value=str(rcr_val), expected="0")

        # Advisory: Distributed 3D block — references disagree
        dist3d_val = t.get_simmod_field("Distributed 3D", "m_bOnly1D")
        if dist3d_val is not None:
            norm = str(dist3d_val).lower().strip()
            numeric = 0 if norm in ("0", "false") else 1 if norm in ("1", "true") else -1
            if numeric == 1:
                self._add("INFO", "m_bOnly1D_dist3d",
                          f"Distributed 3D block m_bOnly1D = {dist3d_val!r}. "
                          "HE18650 and HP18650-template both have 1 here — this matches those references.")
            else:
                self._add("INFO", "m_bOnly1D_dist3d",
                          f"Distributed 3D block m_bOnly1D = {dist3d_val!r}. "
                          "STAR-install TBMs (LiIonSpiral, Tutorial) have 0 here, HE18650/HP18650-template have 1. "
                          "References disagree; import impact of this block's value is UNCONFIRMED.")

    # -----------------------------------------------------------------------
    # 3. Package geometry
    # -----------------------------------------------------------------------
    def check_package_geometry(self):
        t = self.tbm
        ext_d = t.get_float("Package m_dextDiameter")
        ext_h = t.get_float("Package m_dextHeight")
        int_d = t.get_float("Package m_dintDiameter")
        int_h = t.get_float("Package m_dintHeight")

        for fname, val, target, tol, note in [
            ("Package m_dextDiameter", ext_d, REF_2170["can_od_mm"],    0.5, "2170 OD"),
            ("Package m_dextHeight",   ext_h, REF_2170["can_height_mm"], 1.0, "2170 height"),
            ("Package m_dintDiameter", int_d, REF_2170["can_id_mm"],     0.5, "2170 can ID = OD - 2×wall"),
            ("Package m_dintHeight",   int_h, REF_2170["jellyroll_h_mm"],1.0, "2170 JR height"),
        ]:
            if val is None:
                self._add("WARN", fname.replace(" ", "_"), f"{fname} not found.")
                continue
            delta = abs(val - target)
            if delta > tol:
                self._add("WARN", fname.replace(" ", "_"),
                          f"{fname} = {val} mm, target {target} mm (Δ={delta:.3f} mm; {note}).",
                          field=fname, value=str(val), expected=str(target))
            else:
                self._add("PASS", fname.replace(" ", "_"),
                          f"{fname} = {val} mm (target {target} mm).")

        if ext_d and int_d and ext_d > int_d:
            implied_wall = (ext_d - int_d) / 2.0
            delta = abs(implied_wall - REF_2170["can_wall_mm"])
            if delta > 0.1:
                self._add("WARN", "pkg_wall",
                          f"Implied can wall = ({ext_d}-{int_d})/2 = {implied_wall:.4f} mm. "
                          f"Expected ~{REF_2170['can_wall_mm']} mm. Δ={delta:.4f} mm.")
            else:
                self._add("PASS", "pkg_wall", f"Implied can wall {implied_wall:.4f} mm.")

        if int_d and ext_d and int_d >= ext_d:
            self._add("FAIL", "pkg_id_vs_od",
                      f"Package m_dintDiameter ({int_d}) ≥ m_dextDiameter ({ext_d}). Impossible geometry.")

        name = t.get("Package m_strName")
        if name and name.strip("'\"") != "2170":
            self._add("WARN", "pkg_name",
                      f"Package m_strName = {name!r}. Expected '2170'.",
                      field="Package m_strName", value=name, expected="2170")
        elif name:
            self._add("PASS", "pkg_name", f"Package m_strName = {name!r}.")

    # -----------------------------------------------------------------------
    # 4. BUILDER geometry
    # -----------------------------------------------------------------------
    def check_builder_geometry(self):
        t = self.tbm

        # Jellyroll OD — Detailed Builder occurrence (index 0)
        jr = t.get_builder_float("m_dJellyrollThickness_mm", index=0)
        can_id = REF_2170["can_id_mm"]
        if jr is None:
            self._add("WARN", "jr_od", "m_dJellyrollThickness_mm not found in BUILDER block.")
        elif jr <= 0:
            self._add("FAIL", "jr_od", f"m_dJellyrollThickness_mm = {jr} <= 0. Zero extrusion likely.",
                      field="m_dJellyrollThickness_mm", value=str(jr))
        else:
            gap = can_id - jr
            if gap > 2.0:
                self._add("WARN", "jr_od",
                          f"m_dJellyrollThickness_mm = {jr} mm. Radial clearance to can ID "
                          f"({can_id:.4f} mm) = {gap:.4f} mm diametral = {gap/2:.4f} mm radial. "
                          "All Siemens cylindrical references have near-zero clearance (< 0.5 mm). "
                          "BDS may generate a JellyRoll that does not contact the Can inner surface. "
                          "Correct value UNCONFIRMED — pending cell construction data.",
                          field="m_dJellyrollThickness_mm", value=str(jr), expected=f"~{can_id:.2f}")
            elif gap < -0.5:
                self._add("WARN", "jr_od",
                          f"m_dJellyrollThickness_mm = {jr} mm > can ID {can_id:.4f} mm. "
                          "JellyRoll would be larger than can cavity — interference geometry.")
            else:
                self._add("PASS", "jr_od",
                          f"m_dJellyrollThickness_mm = {jr} mm (clearance to can ID = {gap:.4f} mm).")

        # Mandrel
        mand_t = t.get_builder_float("m_dMandrelThickness_mm")
        mand_w = t.get_builder_float("m_dMandrelWidth_mm")

        if mand_t is None:
            self._add("WARN", "mandrel_t", "m_dMandrelThickness_mm not found in BUILDER.")
        elif mand_t <= 0:
            self._add("FAIL", "mandrel_t",
                      f"m_dMandrelThickness_mm = {mand_t} <= 0. BDS rejects zero mandrel thickness.",
                      value=str(mand_t))
        else:
            self._add("PASS", "mandrel_t", f"m_dMandrelThickness_mm = {mand_t} mm.")

        if mand_w is None:
            self._add("INFO", "mandrel_w", "m_dMandrelWidth_mm not found in BUILDER.")
        elif mand_w == 0:
            self._add("INFO", "mandrel_w",
                      "m_dMandrelWidth_mm = 0 in Detailed Builder. "
                      "Note: tutorialCylindricalCell.tbm (STAR install) also has width=0 with thickness=6 — "
                      "zero width IS valid for cylindrical mandrel (m_bMandrelFlat=0). "
                      "HE18650 uses width=thickness=5. HP18650-template has width=0. "
                      "Whether the Detailed Builder value matters vs Simple Builder is UNCONFIRMED.")
        else:
            self._add("INFO", "mandrel_w", f"m_dMandrelWidth_mm = {mand_w} mm.")

        # Electrode overlap at start — Detailed Builder (index 0) is the critical one
        ovlp_det = t.get_builder_float("m_dElectrodeOverlapAtStart_mm", index=0)
        ovlp_sim = t.get_builder_float("m_dElectrodeOverlapAtStart", index=0)

        if ovlp_det is None and ovlp_sim is None:
            self._add("WARN", "overlap_start", "m_dElectrodeOverlapAtStart_mm not found in BUILDER.")
        elif ovlp_det is not None and ovlp_det == 0:
            self._add("FAIL", "overlap_start",
                      "m_dElectrodeOverlapAtStart_mm = 0 in Detailed Builder. "
                      "This caused 'Electrode Root 1 : Extrusion distance can not be 0' in V1 package. "
                      "Must be > 0. HE18650 uses 30 mm; HP18650-template uses 8 mm; Tutorial uses 3 mm.",
                      field="m_dElectrodeOverlapAtStart_mm", value="0", expected="> 0")
        elif ovlp_det is not None and ovlp_det > 0:
            self._add("PASS", "overlap_start",
                      f"m_dElectrodeOverlapAtStart_mm = {ovlp_det} mm (Detailed Builder). "
                      "HP18650-template uses same 8 mm. Value not confirmed from About-Energy cell spec.")
        elif ovlp_sim is not None and ovlp_sim > 0:
            self._add("INFO", "overlap_start",
                      f"m_dElectrodeOverlapAtStart_mm absent; Simple Builder m_dElectrodeOverlapAtStart = {ovlp_sim}.")

        # +Electrode m_dS3 — must be > 0 for STAR cylindrical 3D import.
        # Evidence: all 4 STAR-install cylindrical references (validationBattery, testTBM,
        # LiIonSpiral, tutorialCylindricalCell) and HE18650 use S3=5. BDS-generated source
        # files (hp18650Spiral1, hp18650Spiral-DIST, hp18650Spiral1-1D) have S3=0 and have
        # UNCONFIRMED 3D import status. Robert's V1 RCR candidate (2026-09-09) had S3=0 and
        # failed with "Electrode Root 1 : Extrusion distance can not be 0".
        # V2 sets S3=5 as the controlled fix.
        # NOTE: the exact internal STAR mapping of S3 to "Electrode Root 1" is inferred from
        # the pattern; not proven until V2 passes runtime import. Do not update this comment
        # to say "proven" until Robert confirms a successful CreateFromTbm with S3=5.
        pos_s3 = t.get_float("+Electrode m_dS3")
        if pos_s3 is None:
            self._add("WARN", "pos_electrode_s3",
                      "+Electrode m_dS3 not found. All STAR cylindrical references have this field set to 5.")
        elif pos_s3 == 0:
            self._add("FAIL", "pos_electrode_s3",
                      "+Electrode m_dS3 = 0. All 4 STAR-install cylindrical references use S3=5; "
                      "Robert's V1 RCR candidate failed with 'Electrode Root 1 : Extrusion distance can not be 0' "
                      "when this field was 0 (2026-09-09). The BDS-generated source files also have S3=0 but "
                      "their 3D import status is unconfirmed. Fix: set to 5 (matches STAR references).",
                      field="+Electrode m_dS3", value="0", expected="> 0 (reference value: 5)")
        elif pos_s3 > 0:
            self._add("PASS", "pos_electrode_s3",
                      f"+Electrode m_dS3 = {pos_s3} mm. "
                      "STAR cylindrical references use 5 mm. V2 RCR candidate uses 5 mm.")
        neg_s3 = t.get_float("-Electrode m_dS3")
        if neg_s3 is not None and neg_s3 > 0:
            self._add("PASS", "neg_electrode_s3",
                      f"-Electrode m_dS3 = {neg_s3} mm (nonzero; consistent with STAR references).")
        elif neg_s3 == 0:
            self._add("WARN", "neg_electrode_s3",
                      "-Electrode m_dS3 = 0. STAR references use 50 mm for -Electrode S3.")

        # m_dOffsetPosAvg — critical: references use 0.5; our source and HP18650-DIST use 1e-06
        offset_pos = t.get_builder_float("m_dOffsetPosAvg", index=0)
        if offset_pos is not None:
            if abs(offset_pos) < 1e-3 and offset_pos != 0:
                self._add("WARN", "offset_pos_avg",
                          f"m_dOffsetPosAvg (Detailed Builder) = {offset_pos} ≈ 0 (near-zero epsilon). "
                          "HE18650, HP18650-template, LiIonSpiral, Tutorial all use 0.5. "
                          "Only HP18650-DIST also uses 1e-06. Provenance of 1e-06 in our source TBM is UNKNOWN — "
                          "possibly set during initial BDS session as non-zero epsilon, or inherited from HP18650-DIST. "
                          "Impact on BDS winding geometry calculation is UNCONFIRMED.",
                          field="m_dOffsetPosAvg", value=str(offset_pos), expected="0.5 (from HE18650/Tutorial)")
            elif offset_pos == 0.5:
                self._add("PASS", "offset_pos_avg",
                          f"m_dOffsetPosAvg = {offset_pos} (matches HE18650/HP18650-template/Tutorial).")
            else:
                self._add("INFO", "offset_pos_avg",
                          f"m_dOffsetPosAvg = {offset_pos}. Reference values are 0.5 (HE18650/Tutorial) and 1e-06 (HP18650-DIST/our source).")

        # Transport Number sets — STAR cylindrical RCR release profile importer completeness.
        # All 4 STAR-install cylindrical references contain this field in the General Electrolyte
        # SIMMOD with value 0. Robert's runtime log (V1 RCR candidate, 2026-09-09) reported:
        #   "Transport Number sets not found in the file, defaulting to 0."
        # This is the explicit runtime evidence that the field is consumed by STAR's importer.
        # BDS-origin references (HE18650, HP18650-DIST, HP18650-RCR25deg) lack this field —
        # they use an older format that predates the STAR-install version. Absence will not crash
        # the importer (STAR defaults to 0), but it triggers a runtime warning that may obscure
        # other issues and represents a structural divergence from the STAR-install standard.
        tn_val = t.get_simmod_field("General Electrolyte", "Transport Number sets")
        if tn_val is None:
            self._add("WARN", "transport_number_sets",
                      "Transport Number sets not found in General Electrolyte SIMMOD. "
                      "All 4 STAR-install cylindrical references (validationBattery, testTBM, LiIonSpiral, "
                      "tutorialCylindricalCell) contain this field with value 0. "
                      "Robert's runtime log (V1 RCR candidate, 2026-09-09) reported: "
                      "'Transport Number sets not found in the file, defaulting to 0.' "
                      "Fix: add 'Transport Number sets = 0' to the General Electrolyte SIMMOD block "
                      "after INL(Kevin_L_Gering)_EC:DMC_Transport# m_dR6.",
                      field="Transport Number sets", value="missing", expected="0")
        elif tn_val.strip() == "0":
            self._add("PASS", "transport_number_sets",
                      "Transport Number sets = 0 present in General Electrolyte SIMMOD. "
                      "Matches all 4 STAR-install cylindrical references. "
                      "Runtime default confirmed in Robert's 2026-09-09 log (V1 RCR candidate).")
        else:
            self._add("WARN", "transport_number_sets",
                      f"Transport Number sets = {tn_val!r}. STAR cylindrical references use 0.",
                      field="Transport Number sets", value=str(tn_val), expected="0")

        # Electrode overlap at end — unverified, flag for review
        ovlp_end = t.get_builder_float("m_dElectrodeOverlapAtEnd_mm")
        if ovlp_end is not None:
            self._add("INFO", "overlap_end",
                      f"m_dElectrodeOverlapAtEnd_mm = {ovlp_end} mm. "
                      "HE18650 = 50 mm; HP18650-template = 30 mm; Tutorial = 40 mm. "
                      "Our value 20 mm is lower than all references. Not confirmed from cell spec.")

        # Separator lengths
        sep_feed = t.get_builder_float("m_dSepFeedLength_mm")
        sep_tail = t.get_builder_float("m_dSepTailLength_mm")
        if sep_feed == 0 or sep_feed is None:
            self._add("INFO", "sep_lengths",
                      f"m_dSepFeedLength_mm = {sep_feed!r} (= Simple: 0). HE18650 also 0; HP18650-template = 10 mm. "
                      "Whether 0 affects 3D geometry is UNCONFIRMED.")

        # Collector widths
        for fname, expected, desc in [
            ("+Electrode Collector m_dWidth_mm", REF_2170["pos_coll_width_mm"], "pos"),
            ("-Electrode Collector m_dWidth_mm", REF_2170["neg_coll_width_mm"], "neg"),
        ]:
            # These appear as top-level fields but inside the Electrode section, not inside BUILDER
            v = t.get_float(fname)
            if v is None:
                self._add("WARN", f"coll_width_{desc}", f"{fname} not found.")
            elif abs(v - expected) > 5:
                self._add("WARN", f"coll_width_{desc}",
                          f"{fname} = {v} mm, expected {expected} mm (from About-Energy).",
                          field=fname, value=str(v), expected=str(expected))
            else:
                self._add("PASS", f"coll_width_{desc}", f"{fname} = {v} mm.")

    # -----------------------------------------------------------------------
    # 5. Cross-field consistency
    # -----------------------------------------------------------------------
    def check_cross_field_consistency(self):
        t = self.tbm

        # Package ID vs JR OD
        int_d = t.get_float("Package m_dintDiameter")
        jr    = t.get_builder_float("m_dJellyrollThickness_mm")
        if int_d and jr:
            gap = int_d - jr
            if abs(gap) > 0.5:
                self._add("WARN", "pkg_id_vs_jr",
                          f"Package m_dintDiameter ({int_d}) - JellyRoll OD ({jr}) = {gap:.4f} mm. "
                          "Non-trivial gap. Correct relationship (fit vs clearance) UNCONFIRMED from cell spec.",
                          field="gap", value=f"{gap:.4f}mm")
            else:
                self._add("PASS", "pkg_id_vs_jr",
                          f"Package ID ({int_d}) ≈ JR OD ({jr}), gap = {gap:.4f} mm.")

        # Capacity — MUST check RCRTable 3D block, not flat lookup
        bspec = t.get_simmod_field("RCRTable", "m_bSpecifyCapacity")
        ahcell = t.get_simmod_float("RCRTable", "m_dAhCell")

        if bspec is None:
            self._add("WARN", "capacity",
                      "m_bSpecifyCapacity not found in RCRTable 3D block. "
                      "Ensure this is checked in the correct SIMMOD block, not a flat file scan.")
        elif bspec in ("1", "true"):
            if ahcell is None or ahcell == 0:
                self._add("FAIL", "capacity",
                          f"RCRTable 3D: m_bSpecifyCapacity=1 but m_dAhCell = {ahcell!r}. BDS will use zero capacity.",
                          field="m_dAhCell", value=str(ahcell), expected=str(REF_2170["capacity_ah"]))
            elif abs(ahcell - REF_2170["capacity_ah"]) < 0.1:
                self._add("PASS", "capacity",
                          f"RCRTable 3D: m_bSpecifyCapacity=1, m_dAhCell = {ahcell} Ah (target {REF_2170['capacity_ah']} Ah).")
            else:
                self._add("WARN", "capacity",
                          f"RCRTable 3D: m_bSpecifyCapacity=1, m_dAhCell = {ahcell} Ah. "
                          f"Deviates from expected {REF_2170['capacity_ah']} Ah.",
                          field="m_dAhCell", value=str(ahcell), expected=str(REF_2170["capacity_ah"]))
        else:
            self._add("WARN", "capacity",
                      f"RCRTable 3D: m_bSpecifyCapacity = {bspec!r} — capacity derived from electrode geometry. "
                      "If electrode geometry not fully correct for 2170, derived capacity will be wrong silently.",
                      field="m_bSpecifyCapacity", value=str(bspec))

        # Simple Builder vs Detailed Builder overlap cross-check
        ovlp_det = t.get_builder_float("m_dElectrodeOverlapAtStart_mm", index=0)
        ovlp_sim = t.get_builder_float("m_dElectrodeOverlapAtStart", index=0)
        if ovlp_det is not None and ovlp_sim is not None and abs(ovlp_det - ovlp_sim) > 0.5:
            self._add("WARN", "simple_vs_detailed",
                      f"Detailed Builder m_dElectrodeOverlapAtStart_mm = {ovlp_det} mm differs from "
                      f"Simple Builder m_dElectrodeOverlapAtStart = {ovlp_sim} mm. "
                      "Which one STAR-CCM+ uses for 'Create from Tbm' is UNCONFIRMED.",
                      field="overlap start mismatch", value=f"detailed={ovlp_det}, simple={ovlp_sim}")
        elif ovlp_det is not None and ovlp_sim is not None:
            self._add("PASS", "simple_vs_detailed",
                      f"Simple and Detailed Builder overlap_at_start agree: {ovlp_det} mm.")

    # -----------------------------------------------------------------------
    # 6. REPORT block
    # -----------------------------------------------------------------------
    def check_report_block(self):
        t = self.tbm
        if not t._report_fields:
            self._add("INFO", "report_block",
                      "No REPORT block values found. REPORT block may be empty or absent in this TBM.")
            return

        n_fields = len(t._report_fields)
        self._add("INFO", "report_block",
                  f"REPORT block present with {n_fields} fields. "
                  "Fields with flag=0 are BDS-computed during a previous BDS session — "
                  "STAR-CCM+ may recompute some at import. "
                  "`m_dRepCanXDim/YDim/ZDim` are documented as Level-C fields consumed by STAR (see translate_tbm).")

        # Can dimensions in REPORT — should match Package external dims
        rep_x = t.get_report_float("m_dRepCanXDim")
        rep_y = t.get_report_float("m_dRepCanYDim")
        rep_z = t.get_report_float("m_dRepCanZDim")
        ext_d = t.get_float("Package m_dextDiameter")
        ext_h = t.get_float("Package m_dextHeight")

        for rep_v, pkg_v, label in [
            (rep_x, ext_d, "m_dRepCanXDim vs Package m_dextDiameter"),
            (rep_y, ext_d, "m_dRepCanYDim vs Package m_dextDiameter"),
            (rep_z, ext_h, "m_dRepCanZDim vs Package m_dextHeight"),
        ]:
            if rep_v is None or pkg_v is None:
                continue
            delta = abs(rep_v - pkg_v)
            if delta > 0.5:
                self._add("WARN", "report_can_dims",
                          f"{label}: REPORT = {rep_v}, Package = {pkg_v}, Δ = {delta:.3f} mm. "
                          "These REPORT fields are documented as consumed by STAR — inconsistency may cause wrong geometry.",
                          field=label, value=str(rep_v), expected=str(pkg_v))
            else:
                self._add("PASS", "report_can_dims",
                          f"{label}: REPORT = {rep_v} ≈ Package = {pkg_v}.")

        # Jellyroll diameter in REPORT vs BUILDER
        rep_jr_d = t.get_report_float("m_dRepJellyrollDiameter")
        bld_jr_d = t.get_builder_float("m_dJellyrollThickness_mm")
        if rep_jr_d is not None and bld_jr_d is not None:
            delta = abs(rep_jr_d - bld_jr_d)
            if delta > 0.5:
                self._add("WARN", "report_jr_diameter",
                          f"m_dRepJellyrollDiameter (REPORT) = {rep_jr_d} mm vs "
                          f"m_dJellyrollThickness_mm (BUILDER) = {bld_jr_d} mm, Δ = {delta:.3f} mm. "
                          "REPORT value is stale from a prior BDS session with old geometry. "
                          "Whether STAR uses this REPORT value at import is UNKNOWN. "
                          "Consumed status: NOT documented as Level-C in translate_tbm.py.",
                          field="m_dRepJellyrollDiameter", value=str(rep_jr_d), expected=str(bld_jr_d))
            else:
                self._add("PASS", "report_jr_diameter",
                          f"m_dRepJellyrollDiameter ({rep_jr_d}) ≈ BUILDER JR OD ({bld_jr_d}).")

        # Jellyroll height in REPORT vs Package dintHeight
        rep_jr_h = t.get_report_float("m_dRepJellyrollHeight")
        int_h = t.get_float("Package m_dintHeight")
        if rep_jr_h is not None and int_h is not None:
            delta = abs(rep_jr_h - int_h)
            if delta > 1.0:
                self._add("WARN", "report_jr_height",
                          f"m_dRepJellyrollHeight (REPORT) = {rep_jr_h} mm vs "
                          f"Package m_dintHeight = {int_h} mm, Δ = {delta:.2f} mm. "
                          "REPORT value is stale from prior BDS session with old geometry.",
                          field="m_dRepJellyrollHeight", value=str(rep_jr_h), expected=str(int_h))

        # Capacity in REPORT vs RCRTable 3D active capacity
        rep_cap = t.get_report_float("m_dRepCapacity")
        rcr_ah = t.get_simmod_float("RCRTable", "m_dAhCell")
        if rep_cap is not None and rcr_ah is not None:
            delta = abs(rep_cap - rcr_ah)
            if delta > 0.5:
                self._add("WARN", "report_capacity",
                          f"m_dRepCapacity (REPORT) = {rep_cap} Ahr vs "
                          f"RCRTable 3D m_dAhCell = {rcr_ah} Ahr, Δ = {delta:.3f} Ahr. "
                          "REPORT capacity is stale from prior BDS session. "
                          "Not documented as consumed by STAR — likely an informational field recomputed by BDS.",
                          field="m_dRepCapacity", value=str(rep_cap), expected=str(rcr_ah))

        # Active area in REPORT (informational)
        rep_area = t.get_report_float("m_dRepActiveArea_m2")
        if rep_area is not None:
            self._add("INFO", "report_active_area",
                      f"m_dRepActiveArea_m2 (REPORT) = {rep_area} m². "
                      "This is BDS-computed from the winding geometry. The translate_tbm.py script notes this "
                      "should be read back from BDS after 'Create from Tbm' to set m_dActiveArea_m2.")

    # -----------------------------------------------------------------------
    # 7. Volume consistency
    # -----------------------------------------------------------------------
    def check_volume_consistency(self):
        t = self.tbm
        ext_vol_calc = t.get("Package m_bextVolCalc")
        int_vol_calc = t.get("Package m_bintVolCalc")
        ext_vol = t.get_float("Package m_dextVolume")
        int_vol = t.get_float("Package m_dintVolume")
        ext_d = t.get_float("Package m_dextDiameter")
        ext_h = t.get_float("Package m_dextHeight")
        int_d = t.get_float("Package m_dintDiameter")
        int_h = t.get_float("Package m_dintHeight")

        if ext_vol_calc == "1":
            self._add("INFO", "volume_calc_flag",
                      "Package m_bextVolCalc = 1 — STAR recalculates external volume at import. "
                      "Stored m_dextVolume is informational.")
        if int_vol_calc == "1":
            self._add("INFO", "volume_calc_flag",
                      "Package m_bintVolCalc = 1 — STAR recalculates internal volume at import. "
                      "Stored m_dintVolume is informational.")

        if ext_d and ext_h and ext_vol is not None:
            geom_ext = math.pi * (ext_d / 2) ** 2 * ext_h / 1000.0  # mm^3 → cm^3
            delta_pct = abs(geom_ext - ext_vol) / geom_ext * 100 if geom_ext > 0 else 0
            if delta_pct > 5:
                severity = "INFO" if ext_vol_calc == "1" else "WARN"
                self._add(severity, "volume_ext",
                          f"Package m_dextVolume = {ext_vol} cm³ but geometric cylinder = "
                          f"π×({ext_d}/2)²×{ext_h}/1000 = {geom_ext:.4f} cm³ (Δ={delta_pct:.1f}%). "
                          f"{'STAR recomputes (m_bextVolCalc=1) — stale stored value.' if ext_vol_calc == '1' else 'STAR does NOT recompute — stored value inconsistent with Package dims.'}")

        if int_d and int_h and int_vol is not None:
            geom_int = math.pi * (int_d / 2) ** 2 * int_h / 1000.0
            delta_pct = abs(geom_int - int_vol) / geom_int * 100 if geom_int > 0 else 0
            if delta_pct > 5:
                severity = "INFO" if int_vol_calc == "1" else "WARN"
                self._add(severity, "volume_int",
                          f"Package m_dintVolume = {int_vol} cm³ but geometric cylinder = "
                          f"π×({int_d}/2)²×{int_h}/1000 = {geom_int:.4f} cm³ (Δ={delta_pct:.1f}%). "
                          f"{'STAR recomputes (m_bintVolCalc=1) — stale stored value.' if int_vol_calc == '1' else 'STAR does NOT recompute.'}")

    # -----------------------------------------------------------------------
    # 8. Electrochemical tables — SIMMOD-block-aware
    # -----------------------------------------------------------------------
    def check_electrochemical_tables(self):
        t = self.tbm
        if b"RCRTable 3D" not in t.raw:
            self._add("FAIL", "rcr_block", "RCRTable 3D SIMMOD block not found.")
            return
        self._add("PASS", "rcr_block", "RCRTable 3D block present.")

        rcr_blocks = t.simmod_blocks_by_type("RCRTable")
        if not rcr_blocks:
            self._add("WARN", "rcr_parse", "RCRTable 3D block not parsed into SIMMOD structure.")
            return

        rcr = rcr_blocks[0]

        # Temperature sets from the RCRTable 3D block
        temp_vals = []
        for i in range(10):
            raw = rcr["fields"].get(f"Set[{i}]_m_dT")
            if raw is None:
                break
            try:
                temp_vals.append(float(raw))
            except (ValueError, TypeError):
                break

        n_sets = len(temp_vals)
        if n_sets == 0:
            self._add("WARN", "rcr_temps", "No Set[N]_m_dT temperature entries in RCRTable 3D block.")
        elif n_sets != REF_2170["n_rcr_sets"]:
            self._add("WARN", "rcr_temps",
                      f"Found {n_sets} temperature sets in RCRTable 3D, expected {REF_2170['n_rcr_sets']}.")
        else:
            mismatch = [(i, t_got, t_exp) for i, (t_got, t_exp) in enumerate(zip(temp_vals, REF_2170["rcr_temps_k"]))
                        if abs(t_got - t_exp) > 1.0]
            if mismatch:
                for i, got, exp in mismatch:
                    self._add("WARN", "rcr_temps",
                              f"Set[{i}]_m_dT = {got} K, expected {exp} K.",
                              field=f"Set[{i}]_m_dT", value=str(got), expected=str(exp))
            else:
                self._add("PASS", "rcr_temps",
                          f"RCRTable 3D temperature sets: {temp_vals} K.")

        if len(temp_vals) > 1 and not all(temp_vals[i] < temp_vals[i+1] for i in range(len(temp_vals)-1)):
            self._add("WARN", "rcr_temp_mono", f"Temperature sets not monotonically increasing: {temp_vals}.")

        # R0 values per set
        for i in range(n_sets):
            r0_vals = []
            for j in range(1, REF_2170["n_soc_points"] + 3):
                raw = rcr["fields"].get(f"Set[{i}]_RCR_V_Ro_{j}")
                if raw is None:
                    break
                try:
                    r0_vals.append(float(raw))
                except (ValueError, TypeError):
                    break

            if not r0_vals:
                self._add("WARN", "rcr_r0", f"Set[{i}] RCR_V_Ro values not found in RCRTable 3D block.")
                continue
            if len(r0_vals) != REF_2170["n_soc_points"]:
                self._add("WARN", "rcr_r0",
                          f"Set[{i}] has {len(r0_vals)} R0 values, expected {REF_2170['n_soc_points']}.")
            bad = [v for v in r0_vals if not (R0_RANGE[0] <= v <= R0_RANGE[1])]
            if bad:
                self._add("WARN", "rcr_r0", f"Set[{i}] R0 values outside plausible range {R0_RANGE}: {bad}.")
            elif any(v < 0 for v in r0_vals):
                self._add("FAIL", "rcr_r0", f"Set[{i}] negative R0 values: {r0_vals}.")
            else:
                self._add("PASS", "rcr_r0",
                          f"Set[{i}] R0: {len(r0_vals)} values, range [{min(r0_vals):.5f}, {max(r0_vals):.5f}] Ω.")

        # SOC range — check for values outside [0,1]
        soc_out = []
        for i in range(n_sets):
            for j in range(1, REF_2170["n_soc_points"] + 2):
                raw = rcr["fields"].get(f"Set[{i}]_RCR_V_SOC_{j}")
                if raw is None:
                    break
                try:
                    sv = float(raw)
                    if sv < 0 or sv > 1:
                        soc_out.append(f"Set[{i}]_SOC_{j}={sv}")
                except (ValueError, TypeError):
                    pass

        if soc_out:
            self._add("INFO", "rcr_soc_range",
                      f"RCR SOC table contains values outside [0,1]: {soc_out}. "
                      "In this TBM the minimum is -0.08, derived from translate_tbm_from_openfoam.py: "
                      "SOC = 1 - Q_Ah/5.0 with Q_max=5.4 Ah → SOC_min = 1 - 5.4/5 = -0.08. "
                      "This represents an extrapolation point beyond full charge. "
                      "HE18650 reference SOC range is [0, 1] (11 points). "
                      "Whether STAR-CCM+ permits SOC < 0 in RCR tables is UNCONFIRMED — "
                      "WARN if this causes issues; not flagged as FAIL pending evidence.")

        # OCV data
        has_ocv = b"EquilData" in t.raw or b"E_OCV" in t.raw or b"m_dOCV" in t.raw
        if has_ocv:
            self._add("PASS", "ocv_data", "OCV/equilibrium data present.")
        else:
            self._add("WARN", "ocv_data", "No OCV/equilibrium data found.")

        # n_sets from block
        n_rcr_param = t.get_simmod_field("RCRTable", "m_nRCRParameterSets")
        if n_rcr_param is not None:
            try:
                n_stated = int(n_rcr_param)
                if n_stated != n_sets:
                    self._add("WARN", "rcr_set_count",
                              f"m_nRCRParameterSets = {n_stated} but {n_sets} temperature sets found.",
                              value=str(n_stated), expected=str(n_sets))
                else:
                    self._add("PASS", "rcr_set_count",
                              f"m_nRCRParameterSets = {n_stated} matches {n_sets} sets found.")
            except (ValueError, TypeError):
                pass

    # -----------------------------------------------------------------------
    # 9. DataSheet residuals — 18650-stock value scan
    # -----------------------------------------------------------------------
    def check_datasheet_residuals(self):
        t = self.tbm

        # Known 18650-stock values and expected 2170 values
        checks = [
            ("DataSheet m_dHeight",     65.0,     REF_2170["can_height_mm"],
             "HP18650 can height is 65 mm; 2170 can height is 70.02 mm. Residual 18650 value."),
            ("DataSheet m_dDSHeight",   65.0,     REF_2170["can_height_mm"],
             "Same 18650 residual as m_dHeight."),
            ("DataSheet m_dCapacity",   1.1,      REF_2170["capacity_ah"],
             "HP18650 capacity ~1.1 Ah; 2170 nominal = 5.0 Ah. Residual 18650 value."),
            ("DataSheet m_dDSCapacity", 0.9,      REF_2170["capacity_ah"],
             "HP18650 DS capacity ~0.9 Ah; residual."),
            ("DataSheet m_dDSDiameter", 21.09,    REF_2170["can_od_mm"],
             "Updated to 2170 value. No issue."),
        ]
        for fname, stock_val, target, note in checks:
            v = t.get_float(fname)
            if v is None:
                continue
            if abs(v - stock_val) < 0.05:
                if stock_val != target:
                    self._add("WARN", "ds_residual",
                              f"{fname} = {v} — matches 18650-stock value ({stock_val}), expected {target}. {note}",
                              field=fname, value=str(v), expected=str(target))
            elif abs(v - target) < 0.5:
                self._add("PASS", "ds_residual",
                          f"{fname} = {v} ≈ 2170 target {target}.")

        # Cell name fields
        ds_name = t.get("DataSheet m_strName")
        ds_dsname = t.get("DataSheet m_strDSName")
        for fname, val in [("DataSheet m_strName", ds_name), ("DataSheet m_strDSName", ds_dsname)]:
            if val and val.strip("'\"").lower() in ("hpcell", "hecell", "18650"):
                self._add("WARN", "ds_name",
                          f"{fname} = {val!r}. This is the HP18650 cell name — stale residual. "
                          "Label field only; does not affect geometry or physics.",
                          field=fname, value=val, expected="2170 / hp2170NCA or similar")
            elif val:
                self._add("INFO", "ds_name", f"{fname} = {val!r}.")

    # -----------------------------------------------------------------------
    # 10. Units audit
    # -----------------------------------------------------------------------
    def check_units_audit(self):
        t = self.tbm
        # Package mm fields
        for fname in ["Package m_dextDiameter", "Package m_dextHeight",
                      "Package m_dintDiameter", "Package m_dintHeight"]:
            v = t.get_float(fname)
            if v is None:
                continue
            if 0 < v < 0.5:
                self._add("WARN", "units_mm",
                          f"{fname} = {v} — suspiciously small for a mm field (possible unit error).",
                          field=fname, value=str(v))
            elif v > 500:
                self._add("WARN", "units_mm",
                          f"{fname} = {v} — suspiciously large for a mm field.",
                          field=fname, value=str(v))

        # BUILDER mm fields
        for fname in ["m_dJellyrollThickness_mm", "m_dMandrelThickness_mm"]:
            v = t.get_builder_float(fname)
            if v is None:
                continue
            if 0 < v < 0.5:
                self._add("WARN", "units_mm_builder",
                          f"BUILDER {fname} = {v} — suspiciously small.", field=fname, value=str(v))

        # RCR temperatures from block
        rcr_blocks = t.simmod_blocks_by_type("RCRTable")
        if rcr_blocks:
            for i in range(5):
                raw = rcr_blocks[0]["fields"].get(f"Set[{i}]_m_dT")
                if raw is None:
                    break
                try:
                    v = float(raw)
                except (ValueError, TypeError):
                    break
                if 0 < v < 50:
                    self._add("FAIL", "units_temperature",
                              f"Set[{i}]_m_dT = {v} — looks like Celsius, not Kelvin. BDS expects Kelvin.",
                              field=f"Set[{i}]_m_dT", value=str(v), expected=f"~{v+273.15} K")
                elif v < 200 or v > 400:
                    self._add("WARN", "units_temperature",
                              f"Set[{i}]_m_dT = {v} — outside 200–400 K plausible range.")

    # -----------------------------------------------------------------------
    # 11. Structural comparison vs reference
    # -----------------------------------------------------------------------
    def check_structural_vs_reference(self):
        if not self.ref:
            return
        t = self.tbm
        r = self.ref

        our_types = set(t.simmod_types)
        ref_types = set(r.simmod_types)
        missing = ref_types - our_types
        extra   = our_types - ref_types
        if missing:
            self._add("WARN", "simmod_types_vs_ref",
                      f"SIMMOD types in reference but missing in our file: {missing}.")
        if extra:
            self._add("INFO", "simmod_types_vs_ref",
                      f"SIMMOD types in our file but not in reference: {extra}.")
        if not missing and not extra:
            self._add("PASS", "simmod_types_vs_ref", "SIMMOD types match reference.")

        # Key geometry comparison
        for fname in ["Package m_dextDiameter", "Package m_dextHeight",
                      "Package m_dintDiameter", "Package m_dintHeight"]:
            our_v = t.get(fname)
            ref_v = r.get(fname)
            if our_v and ref_v:
                try:
                    diff = abs(float(our_v) - float(ref_v))
                    if diff > 0.5:
                        self._add("INFO", "geom_vs_ref",
                                  f"{fname}: ours={our_v}, ref={ref_v} (expected to differ — different cell).")
                except (ValueError, TypeError):
                    pass


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_validator(tbm_path: Path, ref_path: Optional[Path] = None,
                  verbose: bool = False) -> tuple[list[Finding], str]:
    tbm = TBMParser(tbm_path)
    ref = TBMParser(ref_path) if ref_path else None
    validator = TBMValidator(tbm, ref, verbose)
    findings = validator.run_all()
    return findings, tbm.sha256()


def summarize(findings: list[Finding], path: Path, sha: str) -> str:
    counts = {"FAIL": 0, "WARN": 0, "INFO": 0, "PASS": 0}
    for f in findings:
        counts[f.level] = counts.get(f.level, 0) + 1
    lines = [
        f"\n{'='*70}",
        f"FILE: {path.name}",
        f"SHA-256: {sha}",
        f"RESULT: {counts['FAIL']} FAIL | {counts['WARN']} WARN | {counts['INFO']} INFO | {counts['PASS']} PASS",
        f"{'='*70}",
    ]
    for level in ("FAIL", "WARN", "INFO", "PASS"):
        for f in findings:
            if f.level == level:
                line = f"  [{level:4s}] {f.check}: {f.message}"
                if f.field and f.value:
                    line += f"\n         field={f.field!r} value={f.value!r}"
                    if f.expected:
                        line += f" expected={f.expected!r}"
                lines.append(line)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Static validator for STAR-CCM+ TBM files")
    p.add_argument("path", nargs="?", help="TBM file or directory to validate")
    p.add_argument("--batch", metavar="DIR", help="Validate all .tbm in directory")
    p.add_argument("--ref", metavar="TBM", help="Known-good reference TBM")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--json", action="store_true", help="Output JSON")
    args = p.parse_args()

    ref_path = Path(args.ref) if args.ref else None
    targets = []
    if args.batch:
        targets = sorted(Path(args.batch).glob("**/*.tbm"))
    elif args.path:
        targets = [Path(args.path)]
    else:
        p.print_help()
        sys.exit(1)

    all_results = []
    any_fail = False
    for tbm_path in targets:
        findings, sha = run_validator(tbm_path, ref_path, args.verbose)
        fail_count = sum(1 for f in findings if f.level == "FAIL")
        warn_count = sum(1 for f in findings if f.level == "WARN")
        if fail_count > 0:
            any_fail = True
        print(summarize(findings, tbm_path, sha))
        all_results.append({
            "file": str(tbm_path),
            "sha256": sha,
            "fail": fail_count,
            "warn": warn_count,
            "findings": [vars(f) for f in findings],
        })

    if args.json:
        import json
        print("\n" + json.dumps(all_results, indent=2))

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
