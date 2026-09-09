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
    "jellyroll_h_mm":   65.11,                 # negative electrode width = active height
    "mandrel_d_mm":     6.0,
    "capacity_ah":      5.0,
    "pos_coll_width_mm": 64.11,
    "neg_coll_width_mm": 65.11,
    "n_rcr_sets":       3,
    "rcr_temps_k":      [288.15, 298.15, 308.15],
    "n_soc_points":     7,
}

# R0 plausible range from python/params.csv (Ohm, at 25°C, full SOC range)
R0_RANGE = (1e-4, 0.1)
RP_RANGE = (1e-5, 0.1)
TAU_RANGE = (1.0, 1e5)

# Known-good m_bOnly1D patterns from reference TBMs
# Indexed [SIMMOD_0_idx] — position 0 is the first SIMMOD block with m_bOnly1D
# HE18650: [1, 0, 0, 0] — imports successfully
# hp18650Spiral1 (our template): [1, 0(false), 0, 0]
# hp18650Spiral-DIST: [1, 1, 1, 1] — import status unknown
# HV-LiCoO2f (3D, m_bOnly1D=0): [0, 0(false), 0, 0]
KNOWN_GOOD_ONLY1D_PATTERN = [1, 0, 0, 0]   # HE18650 pattern — believed safe for 3D import
ALL_ZERO_ONLY1D_PATTERN   = [0, 0, 0, 0]   # explicitly 3D in all blocks (conservative fix)
ALL_ONE_ONLY1D_PATTERN    = [1, 1, 1, 1]   # source file pattern — triggered BDS warnings


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    level: str        # FAIL / WARN / INFO / PASS
    check: str        # short check name
    message: str
    field: str = ""
    value: str = ""
    expected: str = ""


# ---------------------------------------------------------------------------
# TBM parser
# ---------------------------------------------------------------------------
class TBMParser:
    """Parse a TBM file into a flat dict of field_name -> list of values."""

    def __init__(self, path: Path):
        self.path = path
        self.raw = path.read_bytes()
        self.lines = self.raw.split(b"\n")
        self._fields: dict[str, list[str]] = {}
        self._simmod_blocks: list[dict] = []
        self._parse()

    def _parse(self):
        current_simmod = None
        for i, raw_line in enumerate(self.lines):
            line = raw_line.decode("latin-1", errors="replace")
            stripped = line.strip()

            # SIMMOD block tracking
            if "<SIMMOD>" in stripped:
                current_simmod = {"start_line": i, "type": "", "fields": {}, "m_bOnly1D": None}
                continue
            if "</SIMMOD>" in stripped:
                if current_simmod is not None:
                    self._simmod_blocks.append(current_simmod)
                current_simmod = None
                continue
            if current_simmod is not None and current_simmod["type"] == "" and stripped and not stripped.startswith("m_"):
                # Second line inside SIMMOD after the opening tag is the type
                current_simmod["type"] = stripped

            # Field parsing: field_name TAB = TAB value (TAB ! optional comment)
            m = re.match(r'^[\t ]*([^\t=!]+?)\s*=\s*([^\t\r\n!]+?)(?:\s*!.*)?$', line)
            if m:
                fname = m.group(1).strip()
                fval  = m.group(2).strip()
                if fname:
                    if fname not in self._fields:
                        self._fields[fname] = []
                    self._fields[fname].append(fval)
                    if current_simmod is not None:
                        current_simmod["fields"][fname] = fval
                        if fname == "m_bOnly1D":
                            current_simmod["m_bOnly1D"] = fval

    def get(self, name: str, default=None) -> Optional[str]:
        """Return first occurrence value, or default."""
        vals = self._fields.get(name)
        return vals[0] if vals else default

    def get_all(self, name: str) -> list[str]:
        return self._fields.get(name, [])

    def get_from_simmod(self, simmod_type: str, field: str, default=None) -> Optional[str]:
        """Return field value from first SIMMOD block whose type starts with simmod_type (case-insensitive)."""
        for b in self._simmod_blocks:
            if b["type"].lower().startswith(simmod_type.lower()):
                v = b["fields"].get(field)
                if v is not None:
                    return v
        return default

    def get_float(self, name: str, default=None) -> Optional[float]:
        v = self.get(name)
        if v is None:
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def has(self, name: str) -> bool:
        return name in self._fields

    @property
    def simmod_blocks_with_only1d(self):
        return [b for b in self._simmod_blocks if b.get("m_bOnly1D") is not None]

    @property
    def simmod_types(self):
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

    # -----------------------------------------------------------------------
    def run_all(self):
        self.check_file_sanity()
        self.check_mode_compatibility()
        self.check_package_geometry()
        self.check_builder_geometry()
        self.check_cross_field_consistency()
        self.check_electrochemical_tables()
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
            self._add("FAIL", "file_size", f"File is suspiciously small ({size} bytes) — likely truncated or empty.")
            return
        self._add("PASS", "file_size", f"File size {size} bytes, {t.line_count()} lines.")

        # Encoding: check for null bytes (binary corruption indicator)
        if b"\x00" in t.raw:
            self._add("WARN", "encoding", "File contains null bytes — possible binary corruption.")
        else:
            self._add("PASS", "encoding", "No null bytes found.")

        # SIMMOD block balance
        open_count  = t.raw.count(b"<SIMMOD>")
        close_count = t.raw.count(b"</SIMMOD>")
        if open_count != close_count:
            self._add("FAIL", "simmod_balance",
                      f"Unbalanced SIMMOD tags: {open_count} open, {close_count} close.",
                      expected="equal counts")
        else:
            self._add("PASS", "simmod_balance", f"{open_count} balanced SIMMOD blocks.")

        # Required high-level markers
        for marker in [b"<SIMMOD>", b"Package m_dextDiameter", b"m_dJellyrollThickness_mm",
                       b"RCRTable 3D"]:
            if marker not in t.raw:
                self._add("WARN", "required_blocks",
                          f"Expected marker not found: {marker.decode()!r}. File may be incomplete.")
        if b"RCRTable 3D" in t.raw:
            self._add("PASS", "required_blocks", "RCRTable 3D block present.")

        # Duplicate Package definition check
        ext_d_vals = t.get_all("Package m_dextDiameter")
        if len(ext_d_vals) > 1:
            self._add("WARN", "duplicate_package",
                      f"Package m_dextDiameter appears {len(ext_d_vals)} times: {ext_d_vals}. "
                      "Conflicting definitions may confuse the importer.")
        elif len(ext_d_vals) == 1:
            self._add("PASS", "duplicate_package", "Single Package m_dextDiameter definition.")

    # -----------------------------------------------------------------------
    # 2. Mode compatibility
    # -----------------------------------------------------------------------
    def check_mode_compatibility(self):
        t = self.tbm
        blocks = t.simmod_blocks_with_only1d
        vals = []
        for b in blocks:
            raw = b["m_bOnly1D"].lower().strip()
            v = 0 if raw in ("0", "false") else 1 if raw in ("1", "true") else -1
            vals.append((b["type"], raw, v))

        if not vals:
            self._add("INFO", "m_bOnly1D", "No m_bOnly1D fields found — file may not have a <SIMMOD> electrochemical model section.")
            return

        int_vals = [v for _, _, v in vals]

        # Known-good pattern: [1, 0, 0, 0] (HE18650 — confirmed STAR import works)
        if int_vals == KNOWN_GOOD_ONLY1D_PATTERN:
            self._add("PASS", "m_bOnly1D",
                      f"m_bOnly1D pattern {int_vals} matches HE18650 reference (known-good 3D import). "
                      "Blocks: " + ", ".join(f"{t}={r}" for t,r,_ in vals))
            return

        if int_vals == ALL_ZERO_ONLY1D_PATTERN:
            self._add("INFO", "m_bOnly1D",
                      f"m_bOnly1D = 0 in all {len(vals)} blocks. More conservative than HE18650 pattern "
                      f"(which has first=1). Not confirmed to cause issues — awaiting import test.")
            return

        if int_vals == ALL_ONE_ONLY1D_PATTERN:
            self._add("WARN", "m_bOnly1D",
                      f"m_bOnly1D = 1 in all {len(vals)} blocks. "
                      f"STAR-CCM+ BDS logged 'Warning: m_bOnly1D option is not supported' x2 for "
                      f"this pattern (v1 and v2 client packages). "
                      f"Known-good HE18650 uses pattern [1,0,0,0] not [1,1,1,1]. "
                      f"HP18650-DIST also uses [1,1,1,1] but its import status is unknown. "
                      f"RECOMMEND: change blocks 2-4 to 0 to match HE18650 reference. "
                      f"Blocks: " + ", ".join(f"SIMMOD[{t}]={r}" for t,r,_ in vals))
            return

        # Unexpected pattern
        self._add("WARN", "m_bOnly1D",
                  f"m_bOnly1D pattern {int_vals} is unusual. "
                  f"Known patterns: HE18650=[1,0,0,0], source_file=[1,1,1,1], conservative_fix=[0,0,0,0]. "
                  f"Blocks: " + ", ".join(f"SIMMOD[{t}]={r}" for t,r,_ in vals))

    # -----------------------------------------------------------------------
    # 3. Package geometry
    # -----------------------------------------------------------------------
    def check_package_geometry(self):
        t = self.tbm
        ext_d = t.get_float("Package m_dextDiameter")
        ext_h = t.get_float("Package m_dextHeight")
        int_d = t.get_float("Package m_dintDiameter")
        int_h = t.get_float("Package m_dintHeight")

        if ext_d is None:
            self._add("FAIL", "pkg_ext_diameter", "Package m_dextDiameter not found.")
        elif ext_d <= 0:
            self._add("FAIL", "pkg_ext_diameter", f"Package m_dextDiameter = {ext_d} <= 0.",
                      field="Package m_dextDiameter", value=str(ext_d), expected="> 0")
        else:
            delta = abs(ext_d - REF_2170["can_od_mm"])
            if delta > 0.5:
                self._add("WARN", "pkg_ext_diameter",
                          f"Package m_dextDiameter = {ext_d} mm deviates {delta:.2f} mm from 2170 target "
                          f"{REF_2170['can_od_mm']} mm.",
                          field="Package m_dextDiameter", value=str(ext_d),
                          expected=str(REF_2170["can_od_mm"]))
            else:
                self._add("PASS", "pkg_ext_diameter", f"Package m_dextDiameter = {ext_d} mm (target {REF_2170['can_od_mm']} mm).")

        if ext_h is None:
            self._add("FAIL", "pkg_ext_height", "Package m_dextHeight not found.")
        elif ext_h <= 0:
            self._add("FAIL", "pkg_ext_height", f"Package m_dextHeight = {ext_h} <= 0.")
        else:
            delta = abs(ext_h - REF_2170["can_height_mm"])
            if delta > 1.0:
                self._add("WARN", "pkg_ext_height",
                          f"Package m_dextHeight = {ext_h} mm deviates {delta:.2f} mm from 2170 target "
                          f"{REF_2170['can_height_mm']} mm.",
                          field="Package m_dextHeight", value=str(ext_h),
                          expected=str(REF_2170["can_height_mm"]))
            else:
                self._add("PASS", "pkg_ext_height", f"Package m_dextHeight = {ext_h} mm.")

        if int_d is None:
            self._add("WARN", "pkg_int_diameter", "Package m_dintDiameter not found.")
        elif int_d <= 0:
            self._add("FAIL", "pkg_int_diameter", f"Package m_dintDiameter = {int_d} <= 0.")
        elif ext_d and int_d >= ext_d:
            self._add("FAIL", "pkg_int_diameter",
                      f"Package m_dintDiameter = {int_d} >= m_dextDiameter = {ext_d}. Impossible geometry.",
                      field="Package m_dintDiameter", value=str(int_d), expected=f"< {ext_d}")
        else:
            delta = abs(int_d - REF_2170["can_id_mm"])
            if delta > 0.5:
                self._add("WARN", "pkg_int_diameter",
                          f"Package m_dintDiameter = {int_d} mm deviates {delta:.2f} mm from 2170 can ID "
                          f"{REF_2170['can_id_mm']:.4f} mm (= OD - 2×wall). "
                          "Possible 18650-stock value if ~17.8 mm.",
                          field="Package m_dintDiameter", value=str(int_d),
                          expected=f"{REF_2170['can_id_mm']:.4f}")
            else:
                self._add("PASS", "pkg_int_diameter", f"Package m_dintDiameter = {int_d} mm (target {REF_2170['can_id_mm']:.4f} mm).")

        if int_h is None:
            self._add("WARN", "pkg_int_height", "Package m_dintHeight not found.")
        elif int_h <= 0:
            self._add("FAIL", "pkg_int_height", f"Package m_dintHeight = {int_h} <= 0.")
        else:
            delta = abs(int_h - REF_2170["jellyroll_h_mm"])
            if delta > 1.0:
                self._add("WARN", "pkg_int_height",
                          f"Package m_dintHeight = {int_h} mm deviates {delta:.2f} mm from 2170 "
                          f"jellyroll height {REF_2170['jellyroll_h_mm']} mm. Possible 18650-stock value if ~60 mm.",
                          field="Package m_dintHeight", value=str(int_h),
                          expected=str(REF_2170["jellyroll_h_mm"]))
            else:
                self._add("PASS", "pkg_int_height", f"Package m_dintHeight = {int_h} mm.")

        # Implied can wall thickness
        if ext_d and int_d and ext_d > int_d:
            implied_wall = (ext_d - int_d) / 2.0
            delta_wall = abs(implied_wall - REF_2170["can_wall_mm"])
            if delta_wall > 0.1:
                self._add("WARN", "pkg_wall",
                          f"Implied can wall = (OD-ID)/2 = ({ext_d}-{int_d})/2 = {implied_wall:.4f} mm. "
                          f"Expected ~{REF_2170['can_wall_mm']} mm. Delta {delta_wall:.4f} mm.")
            else:
                self._add("PASS", "pkg_wall", f"Implied can wall {implied_wall:.4f} mm ≈ {REF_2170['can_wall_mm']} mm.")

        # Package name
        name = t.get("Package m_strName")
        if name and name.strip("'\"") != "2170":
            self._add("WARN", "pkg_name",
                      f"Package m_strName = {name!r}. Should be '2170' for this cell.",
                      field="Package m_strName", value=name, expected="2170")
        elif name:
            self._add("PASS", "pkg_name", f"Package m_strName = {name!r}.")

    # -----------------------------------------------------------------------
    # 4. Detailed Builder geometry
    # -----------------------------------------------------------------------
    def check_builder_geometry(self):
        t = self.tbm

        # Jellyroll OD
        jr = t.get_float("m_dJellyrollThickness_mm")
        can_id = REF_2170["can_id_mm"]
        if jr is None:
            self._add("WARN", "jr_od", "m_dJellyrollThickness_mm not found.")
        elif jr <= 0:
            self._add("FAIL", "jr_od", f"m_dJellyrollThickness_mm = {jr} <= 0 — zero extrusion likely.",
                      field="m_dJellyrollThickness_mm", value=str(jr), expected="> 0")
        else:
            gap = can_id - jr
            if jr < 1.0:
                self._add("FAIL", "jr_od",
                          f"m_dJellyrollThickness_mm = {jr} mm is implausibly small. "
                          "May cause STAR geometry failure.")
            elif gap < -0.5:
                self._add("WARN", "jr_od",
                          f"m_dJellyrollThickness_mm = {jr} mm > can ID {can_id:.4f} mm by {abs(gap):.4f} mm. "
                          "Jellyroll is larger than can cavity — interference geometry.")
            elif gap > 2.0:
                self._add("WARN", "jr_od",
                          f"m_dJellyrollThickness_mm = {jr} mm leaves {gap:.4f} mm gap to can ID {can_id:.4f} mm. "
                          "Large gap — no JellyRoll/Can contact in STAR geometry. "
                          "Stock 18650 value is ~17.9 mm (gap ~2.7 mm for 2170); correct value is ~{can_id:.1f} mm.",
                          field="m_dJellyrollThickness_mm", value=str(jr), expected=f"~{can_id:.2f}")
            else:
                self._add("PASS", "jr_od",
                          f"m_dJellyrollThickness_mm = {jr} mm. Gap to can ID = {gap:.4f} mm.")

        # Mandrel
        mand_t = t.get_float("m_dMandrelThickness_mm")
        mand_w = t.get_float("m_dMandrelWidth_mm")
        if mand_t is None:
            self._add("WARN", "mandrel", "m_dMandrelThickness_mm not found.")
        elif mand_t <= 0:
            self._add("FAIL", "mandrel", f"m_dMandrelThickness_mm = {mand_t} <= 0. BDS rejects zero mandrel thickness.",
                      field="m_dMandrelThickness_mm", value=str(mand_t), expected="> 0")
        else:
            delta = abs(mand_t - REF_2170["mandrel_d_mm"])
            if delta > 1.0:
                self._add("WARN", "mandrel",
                          f"m_dMandrelThickness_mm = {mand_t} mm deviates {delta:.1f} mm from expected {REF_2170['mandrel_d_mm']} mm.")
            elif jr and mand_t >= jr:
                self._add("FAIL", "mandrel",
                          f"m_dMandrelThickness_mm = {mand_t} >= jellyroll OD {jr}. Impossible winding geometry.")
            else:
                self._add("PASS", "mandrel", f"m_dMandrelThickness_mm = {mand_t} mm.")

        if mand_w is None:
            self._add("WARN", "mandrel_width", "m_dMandrelWidth_mm not found.")
        elif mand_w == 0:
            self._add("WARN", "mandrel_width",
                      "m_dMandrelWidth_mm = 0. HE18650 reference omits this field (not present). "
                      "hp18650Spiral1 (our template) has 0. Whether 0 is acceptable for cylindrical mandrel "
                      "(m_bMandrelFlat=0) is UNCONFIRMED. Pre-emptive fix set it to mandrel_thickness.",
                      field="m_dMandrelWidth_mm", value="0")
        else:
            self._add("PASS", "mandrel_width", f"m_dMandrelWidth_mm = {mand_w} mm.")

        # Electrode overlap at start
        ovlp_start = t.get_float("m_dElectrodeOverlapAtStart_mm")
        if ovlp_start is None:
            self._add("WARN", "overlap_start", "m_dElectrodeOverlapAtStart_mm not found in Detailed Builder.")
        elif ovlp_start == 0:
            self._add("FAIL", "overlap_start",
                      "m_dElectrodeOverlapAtStart_mm = 0. This caused 'Electrode Root 1 : Extrusion distance "
                      "can not be 0' in STAR-CCM+ v1+v2 client packages. Must be > 0.",
                      field="m_dElectrodeOverlapAtStart_mm", value="0", expected="> 0 (8 mm from Simple Builder)")
        elif ovlp_start < 0:
            self._add("FAIL", "overlap_start",
                      f"m_dElectrodeOverlapAtStart_mm = {ovlp_start} < 0. Negative overlap is invalid.")
        else:
            self._add("PASS", "overlap_start",
                      f"m_dElectrodeOverlapAtStart_mm = {ovlp_start} mm. "
                      f"(NOTE: value taken from Simple Builder block; not confirmed from cell design spec.)")

        ovlp_end = t.get_float("m_dElectrodeOverlapAtEnd_mm")
        if ovlp_end is None:
            self._add("INFO", "overlap_end", "m_dElectrodeOverlapAtEnd_mm not found (field may use different name).")
        elif ovlp_end < 0:
            self._add("WARN", "overlap_end", f"m_dElectrodeOverlapAtEnd_mm = {ovlp_end} < 0.")
        else:
            self._add("INFO", "overlap_end",
                      f"m_dElectrodeOverlapAtEnd_mm = {ovlp_end} mm. "
                      "Value not independently verified against cell spec.")

        # Collector widths (= axial electrode height)
        pos_w = t.get_float("+Electrode Collector m_dWidth_mm")
        neg_w = t.get_float("-Electrode Collector m_dWidth_mm")
        if pos_w is None:
            self._add("WARN", "collector_width", "+Electrode Collector m_dWidth_mm not found.")
        elif pos_w <= 0:
            self._add("FAIL", "collector_width", f"+Electrode Collector m_dWidth_mm = {pos_w} <= 0.")
        else:
            d = abs(pos_w - REF_2170["pos_coll_width_mm"])
            if d > 5:
                self._add("WARN", "collector_width_pos",
                          f"+Electrode Collector width = {pos_w} mm, expected ~{REF_2170['pos_coll_width_mm']} mm. "
                          "Stock 18650 value is ~58 mm.")
            else:
                self._add("PASS", "collector_width_pos", f"+Electrode Collector m_dWidth_mm = {pos_w} mm.")

        if neg_w is None:
            self._add("WARN", "collector_width_neg", "-Electrode Collector m_dWidth_mm not found.")
        elif neg_w <= 0:
            self._add("FAIL", "collector_width_neg", f"-Electrode Collector m_dWidth_mm = {neg_w} <= 0.")
        else:
            d = abs(neg_w - REF_2170["neg_coll_width_mm"])
            if d > 5:
                self._add("WARN", "collector_width_neg",
                          f"-Electrode Collector width = {neg_w} mm, expected ~{REF_2170['neg_coll_width_mm']} mm.")
            else:
                self._add("PASS", "collector_width_neg", f"-Electrode Collector m_dWidth_mm = {neg_w} mm.")

        # Separator lengths
        sep_feed = t.get_float("m_dSepFeedLength_mm")
        sep_tail = t.get_float("m_dSepTailLength_mm")
        if sep_feed is not None and sep_feed < 0:
            self._add("FAIL", "sep_feed", f"m_dSepFeedLength_mm = {sep_feed} < 0.")
        elif sep_feed == 0:
            self._add("INFO", "sep_feed",
                      "m_dSepFeedLength_mm = 0. HE18650 reference also has 0 (field absent). "
                      "hp18650Spiral1 (template) has 10 mm in Simple Builder but 0 in Detailed Builder. "
                      "Whether 0 is valid for 3D import is UNCONFIRMED.")
        else:
            self._add("INFO", "sep_feed", f"m_dSepFeedLength_mm = {sep_feed} mm.")

        # Tab configuration
        neg_tab = t.get("m_bNegTab")
        pos_tab = t.get("m_bPosTab")
        neg_orient = t.get("m_nNegTabVertOrientation")
        pos_orient = t.get("m_nPosTabVertOrientation")

        for fname, val, desc in [
            ("m_bNegTab", neg_tab, "neg tab enable"),
            ("m_bPosTab", pos_tab, "pos tab enable"),
            ("m_nNegTabVertOrientation", neg_orient, "neg tab orientation (0=top, 1=bottom)"),
            ("m_nPosTabVertOrientation", pos_orient, "pos tab orientation (0=top, 1=bottom)"),
        ]:
            if val is None:
                self._add("WARN", "tab_config", f"{fname} not found ({desc}).")
            else:
                self._add("INFO", "tab_config", f"{fname} = {val!r} ({desc}).")

        # Same-face consistency: if both tabs enabled and both on top
        if neg_tab == "0" and pos_tab == "0":
            self._add("INFO", "tab_suppressed", "Both tabs suppressed (m_bNegTab=0, m_bPosTab=0). Geometry test variant.")
        elif neg_orient == "0" and pos_orient == "0":
            self._add("INFO", "tab_same_face", "Both tab orientations = 0 (top). Same-face configuration.")
        elif neg_orient == "1" and pos_orient == "0":
            self._add("INFO", "tab_standard", "Standard orientation: neg tab bottom (1), pos tab top (0).")

    # -----------------------------------------------------------------------
    # 5. Cross-field consistency
    # -----------------------------------------------------------------------
    def check_cross_field_consistency(self):
        t = self.tbm

        # Package ID vs jellyroll OD
        int_d = t.get_float("Package m_dintDiameter")
        jr    = t.get_float("m_dJellyrollThickness_mm")
        if int_d and jr:
            gap = int_d - jr
            if abs(gap) > 0.5:
                self._add("WARN", "pkg_id_vs_jr",
                          f"Package m_dintDiameter ({int_d}) - jellyroll OD ({jr}) = {gap:.4f} mm. "
                          "Non-trivial gap/interference. The correct relationship (tight fit vs designed gap) "
                          "is UNCONFIRMED from cell spec. Siemens stock TBMs show near-zero gap.",
                          field="m_dJellyrollThickness_mm vs Package m_dintDiameter",
                          value=f"gap={gap:.4f}mm")
            else:
                self._add("PASS", "pkg_id_vs_jr",
                          f"Package ID ({int_d}) ≈ jellyroll OD ({jr}), gap = {gap:.4f} mm.")

        # Package internal height vs neg electrode width
        int_h = t.get_float("Package m_dintHeight")
        neg_w = t.get_float("-Electrode Collector m_dWidth_mm")
        if int_h and neg_w:
            diff = abs(int_h - neg_w)
            if diff > 2.0:
                self._add("WARN", "pkg_inth_vs_neg_width",
                          f"Package m_dintHeight ({int_h} mm) differs from -Electrode Collector width "
                          f"({neg_w} mm) by {diff:.2f} mm. These are NOT required to be equal — "
                          "package height is jelly-roll cavity, electrode width is active coating height. "
                          "Documenting for human review.",
                          field="Package m_dintHeight vs -Electrode Collector m_dWidth_mm",
                          value=f"diff={diff:.2f}mm")
            else:
                self._add("INFO", "pkg_inth_vs_neg_width",
                          f"Package m_dintHeight ({int_h}) ≈ neg electrode width ({neg_w}), diff={diff:.2f} mm.")

        # Package ext height vs DataSheet height
        ext_h   = t.get_float("Package m_dextHeight")
        ds_h    = t.get_float("DataSheet m_dDSHeight")
        if ext_h and ds_h:
            diff = abs(ext_h - ds_h)
            if diff > 1.0:
                self._add("WARN", "ds_height_vs_pkg",
                          f"DataSheet m_dDSHeight ({ds_h}) differs from Package m_dextHeight ({ext_h}) "
                          f"by {diff:.2f} mm. DataSheet is a label field; Package ext height drives "
                          "the actual can geometry. Both should reflect the 2170 can height of "
                          f"{REF_2170['can_height_mm']} mm.",
                          field="DataSheet m_dDSHeight", value=str(ds_h), expected=str(ext_h))

        # Capacity specification
        bspec = t.get("m_bSpecifyCapacity")
        ahcell = t.get_float("m_dAhCell")
        if bspec == "1":
            if ahcell is None or ahcell == 0:
                self._add("FAIL", "capacity",
                          "m_bSpecifyCapacity=1 but m_dAhCell is 0 or missing. "
                          "BDS will use zero capacity.",
                          field="m_dAhCell", value=str(ahcell), expected=str(REF_2170["capacity_ah"]))
            elif abs(ahcell - REF_2170["capacity_ah"]) > 0.5:
                self._add("WARN", "capacity",
                          f"m_bSpecifyCapacity=1, m_dAhCell={ahcell} Ah — deviates from expected "
                          f"{REF_2170['capacity_ah']} Ah.",
                          field="m_dAhCell", value=str(ahcell), expected=str(REF_2170["capacity_ah"]))
            else:
                self._add("PASS", "capacity", f"m_bSpecifyCapacity=1, m_dAhCell={ahcell} Ah.")
        elif bspec == "0" or bspec is None:
            self._add("WARN", "capacity",
                      f"m_bSpecifyCapacity = {bspec!r} (capacity derived from electrode geometry). "
                      "If electrode geometry is not fully correct for 2170, derived capacity may be wrong. "
                      "UNVERIFIED whether BDS-derived capacity matches 5 Ah target.",
                      field="m_bSpecifyCapacity", value=str(bspec))

        # Active area specification
        barea = t.get("m_bSpecifyActiveArea")
        if barea == "1":
            area = t.get_float("m_dActiveArea_m2")
            if area is None or area == 0:
                self._add("WARN", "active_area",
                          "m_bSpecifyActiveArea=1 but m_dActiveArea_m2 is 0 or missing.")
            else:
                self._add("INFO", "active_area", f"m_bSpecifyActiveArea=1, m_dActiveArea_m2={area} m².")
        else:
            self._add("INFO", "active_area",
                      "m_bSpecifyActiveArea=0 — active area derived from geometry (consistent with capacity derivation).")

        # Simple Builder vs Detailed Builder cross-check
        simple_ovlp = t.get_float("m_dElectrodeOverlapAtStart")   # no _mm in Simple Builder
        detail_ovlp = t.get_float("m_dElectrodeOverlapAtStart_mm")
        if simple_ovlp is not None and detail_ovlp is not None:
            if abs(simple_ovlp - detail_ovlp) > 0.5:
                self._add("WARN", "simple_vs_detailed",
                          f"Simple Builder m_dElectrodeOverlapAtStart={simple_ovlp} mm differs from "
                          f"Detailed Builder m_dElectrodeOverlapAtStart_mm={detail_ovlp} mm. "
                          "Both exist in the file; which one STAR-CCM+ uses for 'Create from Tbm' is UNCONFIRMED.",
                          field="m_dElectrodeOverlapAtStart vs _mm",
                          value=f"simple={simple_ovlp}, detailed={detail_ovlp}")
            else:
                self._add("PASS", "simple_vs_detailed",
                          f"Simple and Detailed Builder overlap_at_start agree: {simple_ovlp} mm.")

    # -----------------------------------------------------------------------
    # 6. Electrochemical tables
    # -----------------------------------------------------------------------
    def check_electrochemical_tables(self):
        t = self.tbm
        ref = REF_2170

        # Check RCRTable 3D block present
        if b"RCRTable 3D" not in t.raw:
            self._add("FAIL", "rcr_block", "RCRTable 3D SIMMOD block not found.")
            return
        self._add("PASS", "rcr_block", "RCRTable 3D block present.")

        # Temperature sets — read from the RCRTable block specifically to avoid
        # picking up Set[0]_m_dT = 0 that appears in the NTGPTable block earlier in the file.
        temp_vals = []
        for i in range(10):
            k = f"Set[{i}]_m_dT"
            raw = t.get_from_simmod("rcrtable", k)
            if raw is None:
                break
            try:
                temp_vals.append(float(raw))
            except (ValueError, TypeError):
                break

        n_sets = len(temp_vals)
        if n_sets == 0:
            self._add("WARN", "rcr_temps", "No Set[N]_m_dT temperature entries found in RCRTable.")
        elif n_sets != ref["n_rcr_sets"]:
            self._add("WARN", "rcr_temps",
                      f"Found {n_sets} temperature sets, expected {ref['n_rcr_sets']} (288.15/298.15/308.15 K).",
                      value=str(temp_vals))
        else:
            # Check temperature values
            for i, (got, exp) in enumerate(zip(temp_vals, ref["rcr_temps_k"])):
                if abs(got - exp) > 1.0:
                    self._add("WARN", "rcr_temps",
                              f"Set[{i}]_m_dT = {got} K, expected {exp} K.",
                              field=f"Set[{i}]_m_dT", value=str(got), expected=str(exp))
            self._add("PASS", "rcr_temps", f"RCR temperature sets: {temp_vals} K.")

        # Check monotonicity of temperature sets
        if len(temp_vals) > 1:
            if not all(temp_vals[i] < temp_vals[i+1] for i in range(len(temp_vals)-1)):
                self._add("WARN", "rcr_temp_monotonic",
                          f"Temperature sets are not monotonically increasing: {temp_vals}.")
            else:
                self._add("PASS", "rcr_temp_monotonic", "Temperature sets are monotonically increasing.")

        # Check R0 values per set — read from RCRTable block to avoid collisions
        for i in range(n_sets):
            r0_vals = []
            for j in range(1, ref["n_soc_points"] + 3):  # a few extra to check for more than expected
                k = f"Set[{i}]_RCR_V_Ro_{j}"
                raw = t.get_from_simmod("rcrtable", k)
                if raw is None:
                    break
                try:
                    r0_vals.append(float(raw))
                except (ValueError, TypeError):
                    break

            if len(r0_vals) == 0:
                self._add("WARN", "rcr_r0", f"Set[{i}] RCR_V_Ro_* values not found.")
                continue
            if len(r0_vals) != ref["n_soc_points"]:
                self._add("WARN", "rcr_r0",
                          f"Set[{i}] has {len(r0_vals)} R0 values, expected {ref['n_soc_points']}.")

            bad = [v for v in r0_vals if not (R0_RANGE[0] <= v <= R0_RANGE[1])]
            if bad:
                self._add("WARN", "rcr_r0",
                          f"Set[{i}] R0 values out of plausible range {R0_RANGE}: {bad}.")
            elif any(v < 0 for v in r0_vals):
                self._add("FAIL", "rcr_r0", f"Set[{i}] contains negative R0 values: {r0_vals}.")
            else:
                self._add("PASS", "rcr_r0",
                          f"Set[{i}] R0: {len(r0_vals)} values, range [{min(r0_vals):.5f}, {max(r0_vals):.5f}] Ohm.")

        # Check OCV presence (look for equilibrium data)
        has_ocv = b"EquilData" in t.raw or b"E_OCV" in t.raw or b"m_dOCV" in t.raw
        if not has_ocv:
            self._add("WARN", "ocv_data", "No OCV/equilibrium data found in file.")
        else:
            self._add("PASS", "ocv_data", "OCV/equilibrium data present.")

    # -----------------------------------------------------------------------
    # 7. Units audit
    # -----------------------------------------------------------------------
    def check_units_audit(self):
        t = self.tbm
        # Fields that should be in mm (not m, not um)
        mm_fields = [
            "m_dJellyrollThickness_mm",
            "m_dMandrelThickness_mm",
            "m_dMandrelWidth_mm",
            "m_dElectrodeOverlapAtStart_mm",
            "m_dElectrodeOverlapAtEnd_mm",
            "+Electrode Collector m_dWidth_mm",
            "-Electrode Collector m_dWidth_mm",
            "Package m_dextDiameter",
            "Package m_dextHeight",
            "Package m_dintDiameter",
            "Package m_dintHeight",
        ]
        for fname in mm_fields:
            v = t.get_float(fname)
            if v is None:
                continue
            if 0 < v < 0.5:
                self._add("WARN", "units_mm",
                          f"{fname} = {v} — suspiciously small for a mm field. "
                          "Possible unit error (metres instead of mm)? Expected range: 1–100 mm.",
                          field=fname, value=str(v))
            elif v > 500:
                self._add("WARN", "units_mm",
                          f"{fname} = {v} — suspiciously large for a mm field. "
                          "Possible unit error (µm or cm)? Expected range: 1–100 mm.",
                          field=fname, value=str(v))

        # Active area (should be m², order of magnitude ~0.09 m²)
        area = t.get_float("m_dActiveArea_m2")
        if area is not None and area > 0:
            if area > 10 or area < 0.001:
                self._add("WARN", "units_area",
                          f"m_dActiveArea_m2 = {area} m² seems implausible. Expected ~0.09 m² for 2170.",
                          field="m_dActiveArea_m2", value=str(area))

        # RCR temperatures (should be K, ~288–308 K) — use block-aware lookup
        for i in range(5):
            k = f"Set[{i}]_m_dT"
            raw = t.get_from_simmod("rcrtable", k)
            if raw is None:
                break
            try:
                v = float(raw)
            except (ValueError, TypeError):
                break
            if 0 < v < 50:
                self._add("FAIL", "units_temperature",
                          f"{k} = {v} — looks like Celsius, not Kelvin. BDS expects Kelvin.",
                          field=k, value=str(v), expected=f"~{v + 273.15} K")
            elif v < 200 or v > 400:
                self._add("WARN", "units_temperature",
                          f"{k} = {v} — outside 200–400 K plausible range.")

    # -----------------------------------------------------------------------
    # 8. Structural comparison vs reference
    # -----------------------------------------------------------------------
    def check_structural_vs_reference(self):
        if not self.ref:
            return
        t = self.tbm
        r = self.ref

        # SIMMOD type comparison
        our_types = set(t.simmod_types)
        ref_types = set(r.simmod_types)
        missing_in_ours = ref_types - our_types
        extra_in_ours   = our_types - ref_types
        if missing_in_ours:
            self._add("WARN", "simmod_types_vs_ref",
                      f"SIMMOD types in reference but not in our file: {missing_in_ours}. "
                      "May indicate missing electrochemical model blocks.")
        if extra_in_ours:
            self._add("INFO", "simmod_types_vs_ref",
                      f"SIMMOD types in our file but not in reference: {extra_in_ours}.")
        if not missing_in_ours and not extra_in_ours:
            self._add("PASS", "simmod_types_vs_ref", f"SIMMOD types match reference.")

        # Key geometry field comparison
        geom_fields = [
            "Package m_dextDiameter", "Package m_dextHeight",
            "Package m_dintDiameter", "Package m_dintHeight",
            "m_dJellyrollThickness_mm", "m_dMandrelThickness_mm",
            "m_dElectrodeOverlapAtStart_mm",
        ]
        for fname in geom_fields:
            our_v = t.get(fname)
            ref_v = r.get(fname)
            if our_v is None and ref_v is not None:
                self._add("WARN", "field_vs_ref",
                          f"Field {fname!r}: in reference ({ref_v}) but MISSING in our file.",
                          field=fname)
            elif our_v is not None and ref_v is None:
                self._add("INFO", "field_vs_ref",
                          f"Field {fname!r}: in our file ({our_v}) but not in reference (may be our addition).",
                          field=fname)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_validator(tbm_path: Path, ref_path: Optional[Path] = None, verbose: bool = False) -> tuple[list[Finding], str]:
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
    p.add_argument("--batch", metavar="DIR", help="Validate all .tbm files in directory")
    p.add_argument("--ref", metavar="TBM", help="Known-good reference TBM for structural comparison")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--json", action="store_true", help="Output as JSON")
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
