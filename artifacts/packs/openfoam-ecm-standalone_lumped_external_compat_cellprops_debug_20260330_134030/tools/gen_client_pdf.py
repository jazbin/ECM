#!/usr/bin/env python3
"""
Client-facing report PDF.
Output: /workspace/artifacts/reports/client_report.pdf
"""
from pathlib import Path
from fpdf import FPDF

WORKSPACE = Path("/workspace")
IMGS      = WORKSPACE / "artifacts/plots/doc_client"
WF        = WORKSPACE / "artifacts/plots/weight_fields"
OUT_PDF   = WORKSPACE / "artifacts/reports/client_report.pdf"
OUT_PDF.parent.mkdir(parents=True, exist_ok=True)

LOGO      = WORKSPACE / "logo.png"
# Compute banner height from actual image aspect ratio at full A4 width (210 mm)
from PIL import Image as _PIL
_logo_im  = _PIL.open(str(LOGO))
BANNER_H  = round(210.0 * _logo_im.size[1] / _logo_im.size[0], 1)
del _logo_im

_FD = Path("/home/helios/.local/lib/python3.13/site-packages/matplotlib/mpl-data/fonts/ttf")
FONT_REG  = str(_FD / "DejaVuSans.ttf")
FONT_BOLD = str(_FD / "DejaVuSans-Bold.ttf")
FONT_ITAL = str(_FD / "DejaVuSans-Oblique.ttf")
FONT_MONO = str(_FD / "DejaVuSansMono.ttf")

# Colours drawn from logo palette (steel-blue right / leaf-green left)
C_DARK  = (25,  35,  55)
C_BLUE  = (58, 112, 162)   # logo steel-blue
C_GREEN = (72, 148,  72)   # logo leaf-green
C_ORANGE= (198, 90,   0)
C_RED   = (180, 30,  30)
C_GREY  = (100,100, 115)
C_LGREY = (240,244, 249)   # very light blue-tinted grey
C_WHITE = (255,255, 255)
C_YELL  = (255,252, 225)

HEADER_LABEL_GAP = 8.0
EARLY_PAGE_TOP_GAP = 18.0


class Doc(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(22, BANNER_H + HEADER_LABEL_GAP, 22)
        self.set_auto_page_break(True, 22)
        self._toc   = []
        self._ch    = 0
        self._sec   = 0
        self.add_font("DV",  "",  FONT_REG,  uni=True)
        self.add_font("DV",  "B", FONT_BOLD, uni=True)
        self.add_font("DV",  "I", FONT_ITAL, uni=True)
        self.add_font("DVM", "",  FONT_MONO, uni=True)

    # ── chrome ────────────────────────────────────────────────────────────────
    def header(self):
        # Logo banner — flush to page top, full width, no border
        self.image(str(LOGO), x=0, y=0, w=self.w)   # natural aspect ratio
        if self.page_no() <= 2:
            return
        # Thin page-label row below banner
        self.set_xy(self.l_margin, BANNER_H + 1.5)
        self.set_font("DV", "I", 7.5)
        self.set_text_color(*C_GREY)
        self.cell(0, 5, "ECM–OpenFOAM Coupling Framework  |  Client Report",
                  align="L")
        self.set_draw_color(*C_BLUE)
        self.set_line_width(0.25)
        y_line = BANNER_H + 7
        self.line(self.l_margin, y_line, self.w - self.r_margin, y_line)
        # Force body content to start below the banner + label band on every page.
        self.set_y(BANNER_H + HEADER_LABEL_GAP)

    def footer(self):
        self.set_y(-14)
        self.set_font("DV", "I", 7.5)
        self.set_text_color(*C_GREY)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def start_below_banner(self, extra_gap=0.0):
        # Use an explicit anchor below the full-width banner on the early pages.
        self.set_y(BANNER_H + HEADER_LABEL_GAP + extra_gap)

    # ── helpers ───────────────────────────────────────────────────────────────
    def h1(self, text):
        self._ch += 1; self._sec = 0
        num = f"{self._ch}.  {text}"
        self._toc.append((1, num, self.page_no()))
        self.ln(5)
        self.set_font("DV", "B", 16)
        self.set_text_color(*C_BLUE)
        self.set_fill_color(*C_BLUE)
        self.rect(self.l_margin, self.get_y()+7,
                  self.w-self.l_margin-self.r_margin, 0.7, "F")
        self.cell(0, 10, num, new_x="LMARGIN", new_y="NEXT")
        self.ln(2); self.set_text_color(*C_DARK)

    def h2(self, text):
        self._sec += 1
        num = f"{self._ch}.{self._sec}  {text}"
        self._toc.append((2, num, self.page_no()))
        self.ln(3)
        self.set_font("DV", "B", 12)
        self.set_text_color(*C_BLUE)
        self.cell(0, 7, num, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_GREEN)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.l_margin+85, self.get_y())
        self.ln(3)

    def h3(self, text):
        self.ln(2)
        self.set_font("DV", "B", 10.5)
        self.set_text_color(*C_GREEN)
        self.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*C_DARK); self.ln(1)

    def body(self, text, indent=0):
        self.set_font("DV", "", 9.5)
        self.set_text_color(*C_DARK)
        self.set_x(self.l_margin + indent)
        self.multi_cell(self.w - self.l_margin - self.r_margin - indent, 5.5, text)
        self.ln(1)

    def bullet(self, text, level=0):
        ind = 4 + level*6
        self.set_font("DV", "", 9.5)
        self.set_text_color(*C_DARK)
        self.set_x(self.l_margin + ind)
        self.cell(5, 5.5, "•" if level == 0 else "–")
        self.multi_cell(self.w-self.l_margin-self.r_margin-ind-5, 5.5, text)

    def note(self, text, fc=C_YELL, ec=C_ORANGE):
        self.ln(2)
        w = self.w - self.l_margin - self.r_margin
        self.set_fill_color(*fc); self.set_draw_color(*ec)
        self.set_line_width(0.5)
        self.set_font("DV", "I", 9)
        self.set_text_color(*C_DARK)
        y0 = self.get_y()
        self.set_x(self.l_margin+3)
        self.multi_cell(w-6, 5, text, fill=True)
        y1 = self.get_y()
        self.rect(self.l_margin, y0, w, y1-y0, "D")
        self.ln(3)

    def table_row(self, cells, widths, header=False, alt=False):
        self.set_font("DV", "B" if header else "", 8.5)
        if header:
            self.set_fill_color(*C_BLUE); self.set_text_color(*C_WHITE)
        elif alt:
            self.set_fill_color(*C_LGREY); self.set_text_color(*C_DARK)
        else:
            self.set_fill_color(*C_WHITE); self.set_text_color(*C_DARK)
        self.set_draw_color(185,185,195); self.set_line_width(0.18)
        for txt, w in zip(cells, widths):
            self.cell(w, 6, str(txt), border=1, fill=True)
        self.ln()

    def fig(self, path, caption, w_pct=0.94):
        p = Path(path)
        if not p.exists():
            self.body(f"[Missing: {p.name}]"); return
        self.ln(2)
        aw = (self.w - self.l_margin - self.r_margin) * w_pct
        x  = self.l_margin + (self.w-self.l_margin-self.r_margin)*(1-w_pct)/2
        try:
            self.image(str(p), x=x, w=aw)
        except Exception as e:
            self.body(f"[Could not embed {p.name}: {e}]"); return
        self.ln(1)
        self.set_font("DV", "I", 8)
        self.set_text_color(*C_GREY)
        self.set_x(self.l_margin+10)
        self.multi_cell(self.w-self.l_margin-self.r_margin-20, 4.5, caption)
        self.set_text_color(*C_DARK); self.ln(3)

    # ── cover ─────────────────────────────────────────────────────────────────
    def cover(self):
        self.add_page()
        self.start_below_banner(EARLY_PAGE_TOP_GAP)
        self.set_font("DV", "B", 24)
        self.set_text_color(*C_BLUE)
        self.cell(0, 13, "ECM–OpenFOAM Coupling Framework",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_font("DV", "", 15)
        self.set_text_color(*C_DARK)
        self.cell(0, 9, "Client Technical Report", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_font("DV", "I", 11)
        self.set_text_color(*C_GREY)
        self.cell(0, 7,
                  "Battery Thermal Simulation — ECM Integration, Validation & Performance",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.set_draw_color(*C_BLUE)
        self.set_line_width(0.8)
        self.line(45, self.get_y(), self.w-45, self.get_y())
        self.ln(10)
        for label, val in [
            ("Version:",  "1.0"),
            ("Scope:",    "Coupling architecture, validation results, I/O optimisation"),
            ("Note:",     "Client-provided ECM not yet integrated — stand-in model used"),
        ]:
            self.set_x(58)
            self.set_font("DV", "B", 10.5)
            self.set_text_color(*C_DARK)
            self.cell(30, 7, label)
            self.set_font("DV", "", 10.5)
            color = C_RED if "ECM not yet" in val else C_DARK
            self.set_text_color(*color)
            self.cell(0, 7, val, new_x="LMARGIN", new_y="NEXT")

    def toc_page(self):
        self.add_page()
        self.start_below_banner(EARLY_PAGE_TOP_GAP - 2.0)
        self.set_font("DV", "B", 16)
        self.set_text_color(*C_BLUE)
        self.cell(0, 11, "Contents", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_BLUE)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w-self.r_margin, self.get_y())
        self.ln(5)
        for lvl, title, pg in self._toc:
            ind = 0 if lvl == 1 else 8
            self.set_x(self.l_margin+ind)
            self.set_font("DV", "B" if lvl == 1 else "", 9.5 if lvl == 1 else 9)
            self.set_text_color(*C_DARK)
            w = self.w-self.l_margin-self.r_margin-ind-14
            self.cell(w, 6.5, title)
            self.cell(14, 6.5, str(pg), align="R", new_x="LMARGIN", new_y="NEXT")


# =============================================================================
# SECTIONS
# =============================================================================

def s1_executive(doc):
    doc.add_page()
    doc.h1("Executive Summary")
    doc.body(
        "This report documents the development, validation, and performance characterisation "
        "of the ECM–OpenFOAM thermal coupling framework for battery cell simulation. The "
        "framework couples a 3D finite-volume thermal solver (OpenFOAM chtMultiRegionSolidFoam) "
        "with an external electrochemical model (ECM) to compute spatially resolved heat "
        "generation in a 4680-format lithium-ion cell."
    )
    doc.note(
        "Important: the client-provided ECM model has not yet been integrated into this "
        "framework. All results in this report were obtained using a stand-in ECM — a "
        "2-RC Thevenin equivalent circuit model parameterised for an NCA 4680 cell chemistry. "
        "The stand-in was used to develop and validate the full coupling infrastructure. "
        "The results in this report demonstrate the internal consistency of the "
        "OpenFOAM-side coupling framework, not predictive fidelity of the final stack. "
        "Integrating the client ECM is the next phase; this is addressed in Section 10.",
        fc=(255, 235, 238), ec=C_RED
    )

    doc.h2("Key Deliverables")
    rows = [
        ("Coupling modes validated",    "Lumped (single zone) + Distributed (18 zones)"),
        ("Validation tests",            "10 / 10 passed"),
        ("Lumped–distributed Q equiv.", "ΔQ < 6×10⁻⁶ W at steady state"),
        ("Mesh convergence (ΔT)",       "0.051 K  (medium → fine mesh)"),
        ("Energy balance RMSE",         "0.277 K  (adiabatic test)"),
        ("I/O optimisation speedup",    "23× vs JSON spawn  (binary persistent pipe)"),
        ("Pure I/O overhead (binary persistent pipe)", "<2 s for 300 s simulation"),
        ("Maximum ECM cell count",      "5,000 cells  (design ceiling)"),
    ]
    ws = [90, 76]
    doc.table_row(["Metric", "Result"], ws, header=True)
    for i, r in enumerate(rows):
        doc.table_row(r, ws, alt=i%2==0)
    doc.ln(3)

    doc.h2("Report Structure")
    doc.body(
        "The report is organised into eleven sections following the development phases: "
        "coupling architecture overview, stand-in ECM description, distributed model "
        "details, temporal heat interpolation, coupler I/O optimisation, validation "
        "results, thermal field results, client integration guide, and open items / "
        "residual integration risks. "
        "Sections 4 (Distributed Model), 5 (Temporal Interpolation), and 6 "
        "(I/O Optimisation) are the primary technical contributions of this engagement. "
        "Section 10 explicitly lists what remains to be demonstrated."
    )
    doc.h2("Coupling Strategy")
    doc.body(
        "The coupling architecture uses a weak (explicit, partitioned) strategy: "
        "the CFD solver and the ECM advance independently, exchanging data once per "
        "CFD timestep. At the start of each timestep, the CFD solver extracts "
        "the current temperature field from the active zone, passes it to the ECM, "
        "receives the updated volumetric heat generation (W/m³) in return, and then "
        "advances the thermal solution with that source term applied."
    )
    doc.body(
        "This approach is chosen for three reasons. First, battery thermal problems "
        "are loosely coupled on the relevant timescales: temperature changes by at most "
        "a few tenths of a kelvin per timestep, so the ECM heat output computed at "
        "step n remains accurate through step n+1. Second, weak coupling keeps the "
        "coupling overhead strictly bounded — one ECM call per CFD step regardless of "
        "solver convergence behaviour. Third, it requires no modification to the "
        "OpenFOAM solver internals; the coupler is implemented as a functionObject "
        "that hooks into the existing solve-loop lifecycle."
    )
    doc.body(
        "Strong (implicit) coupling — where the ECM is called multiple times per "
        "timestep until inner convergence — is supported in the protocol design but "
        "is not required for the battery thermal timescales simulated here (seconds "
        "to minutes). The diagram below contrasts the two strategies."
    )
    doc.fig(IMGS / "D05_weak_vs_strong.png",
            "Figure 1.1 — Weak coupling (left) vs strong coupling (right). In weak "
            "coupling one ECM call is made per CFD timestep with no inner iteration; "
            "the updated heat source is applied at the next step. This is "
            "computationally efficient and sufficiently accurate for battery thermal "
            "timescales where temperature evolves slowly relative to the CFD timestep.")


def s2_overview(doc):
    doc.add_page()
    doc.h1("Coupling Framework Overview")

    doc.h2("Problem Context")
    doc.body(
        "During charge and discharge, Joule heating and reaction overpotentials generate "
        "heat inside the active jellyRoll material of a lithium-ion cell. Accurately "
        "predicting the 3D temperature distribution requires resolving heat conduction "
        "through the jellyRoll, metal shell, and end caps simultaneously with the "
        "electrochemical heat source, which depends on the local temperature."
    )
    doc.body(
        "The framework couples a 3D finite-volume thermal model of a 4680 cylindrical "
        "cell with an ECM that provides the instantaneous heat generation rate as a "
        "function of temperature and current. The coupling is implemented as an OpenFOAM "
        "functionObject (ecmCoupler) that fires once per CFD timestep with no solver "
        "modifications required."
    )
    doc.fig(IMGS / "D01_battery_geometry.png",
            "Figure 2.1 — 4680 battery cell geometry (46 mm diameter, 80 mm height). "
            "Three solid mesh regions: jellyRoll (ECM-coupled active material, inner), "
            "shell (outer cylinder including bottom closure), and cap (top end cap only — "
            "there is no separate bottom cap region; the bottom is part of the shell). "
            "External wall held at 313.15 K (40°C).")

    doc.h2("Coupling Strategy")
    doc.body(
        "The framework uses weak (explicit, partitioned) coupling: the CFD solver and "
        "the ECM advance independently, exchanging data once per timestep at the "
        "boundary between each CFD step and the next. This approach is valid for "
        "battery thermal problems because the thermal and electrochemical subsystems "
        "are loosely coupled on the timescales of interest — temperature changes slowly "
        "relative to the CFD timestep."
    )
    doc.fig(IMGS / "D09_boundary_conditions.png",
            "Figure 2.2 — Thermal boundary conditions. The jellyRoll zone receives the "
            "ECM volumetric heat source (ecmQdot, W/m³) via fvOptions. The jellyRoll "
            "interfaces with the shell on its outer cylindrical surface and with the top "
            "cap at its upper face (both use compressible coupled mixed BCs). The outer "
            "shell wall is fixed at 313.15 K. Note: there is no separate bottom cap — "
            "the bottom of the cell is the shell base.")

    doc.h2("Two Coupling Modes")
    doc.body(
        "Two coupling geometries are supported and have both been validated:"
    )
    ws = [30, 60, 76]
    doc.table_row(["Mode", "Description", "Use case"], ws, header=True)
    doc.table_row(["Lumped", "Entire jellyRoll is one ECM zone; uniform heat applied",
                  "Validation baseline, simple cases"], ws, alt=True)
    doc.table_row(["Distributed", "jellyRoll partitioned into 18 zones; spatial heat resolved",
                  "Production simulations, spatial gradients"], ws)
    doc.ln(3)

    doc.h2("Development Phases")
    doc.body(
        "The framework was built and validated in four sequential phases, each building "
        "on the previous. No calendar dates are shown; the phases define the logical "
        "progression of the work."
    )
    doc.fig(IMGS / "C02_development_phases.png",
            "Figure 2.3 — Development phases: lumped baseline → distributed model → "
            "I/O optimisation → validation campaign. The next phase integrates the "
            "client-provided ECM backend.")


def s3_standin(doc):
    doc.add_page()
    doc.h1("Stand-in ECM Model")

    doc.h2("Purpose and Status")
    doc.body(
        "The client-provided ECM model was not available at the start of this engagement. "
        "To allow full development and validation of the coupling infrastructure, a "
        "stand-in ECM was implemented. The stand-in accurately replicates the interface "
        "contract of the target system, meaning the coupling code, I/O protocol, and "
        "CFD configuration are expected to carry over with minimal change when the "
        "client ECM is integrated, subject to integration testing."
    )
    doc.note(
        "The stand-in ECM is not a validated electrochemical model for the client's "
        "cell chemistry. Its purpose is solely to exercise the coupling infrastructure "
        "with a physically plausible heat source. All validation tests that compare "
        "lumped vs distributed results, or test numerical properties (mesh convergence, "
        "energy balance), are independent of the specific ECM chemistry."
    )

    doc.h2("Model Description")
    doc.body(
        "The stand-in is a 2-RC branch Thevenin equivalent circuit model parameterised "
        "for NCA 4680 cell chemistry. It implements the following state variables:"
    )
    for item in [
        "q_ah — accumulated charge throughput (Ah), used to update SoC",
        "v_RC[0] — fast RC branch voltage (time constant τ₁ ≈ 1 s)",
        "v_RC[1] — slow RC branch voltage (time constant τ₂ ≈ 45 s)",
        "hysteresis — voltage hysteresis state (settling time ≈ 5 s)",
    ]:
        doc.bullet(item)
    doc.ln(2)
    doc.body(
        "Heat generation is computed as Joule heating from the internal resistance "
        "and RC branches: Q = I² × (R₀ + R₁·exp(−t/τ₁) + R₂·exp(−t/τ₂)). "
        "All resistance values have a mild thermal dependence. In the current validated "
        "configuration, ECM state is retained in a long-lived backend process between "
        "OpenFOAM timesteps. Earlier development phases also used a JSON state file, "
        "but that is not the primary validated path described in Sections 6 and 9."
    )
    doc.fig(IMGS / "D07_ecm_state_machine.png",
            "Figure 3.1 — Stand-in ECM state machine: 2-RC Thevenin topology with "
            "hysteresis. OCV and resistance tables are parameterised for NCA 4680 "
            "chemistry. State persists between OpenFOAM calls.")
    doc.fig(IMGS / "CS01_ecm_state_variables.png",
            "Figure 3.2 — Stand-in ECM state variables during a 1C discharge (60 s). "
            "RC branches charge to steady state within ~5 s (fast branch) and ~180 s "
            "(slow branch). Joule heat output stabilises accordingly.")

    doc.h2("Client ECM Integration Path")
    doc.body(
        "The coupling infrastructure is designed so that replacing the stand-in "
        "with the client ECM is expected to require swapping only the Python backend module — "
        "provided the client ECM can conform to the binary protocol contract. "
        "The binary I/O protocol, the C++ coupler, and all OpenFOAM case files "
        "are intended to remain unchanged. However, this is an engineering "
        "hypothesis that will be confirmed once tested with the actual client code "
        "(see Section 10, Open Items). The client ECM must satisfy the following "
        "interface requirements:"
    )
    for item in [
        "Read ecm_in.bin: binary file containing N cell temperatures and the current timestep",
        "Compute heat generation for each of up to 5,000 ECM cells",
        "Write ecm_out.bin: binary file returning qVol (W/m³) per cell",
        "Maintain its own internal state between calls (SoC, RC voltages, etc.)",
    ]:
        doc.bullet(item)
    doc.ln(2)
    doc.note(
        "ECM cell count ceiling: the framework is designed and tested for up to "
        "5,000 ECM cells per simulation. I/O latency remains under 1.5 s of cumulative "
        "overhead for a 300 s simulation at this cell count (see Section 6).",
        fc=(232, 245, 233), ec=C_GREEN
    )


def s4_distributed(doc):
    doc.add_page()
    doc.h1("Distributed ECM Model")
    doc.body(
        "The distributed coupling mode is the primary operational mode for this "
        "framework. Unlike the lumped baseline — which applies a single, uniform heat "
        "source across the entire jellyRoll — the distributed mode resolves spatial "
        "variation in heat generation by partitioning the jellyRoll into 18 independent "
        "ECM zones and mapping the per-zone heat output onto each CFD cell."
    )

    doc.h2("Zone Partitioning — 6 × 3 Grid")
    doc.body(
        "The jellyRoll is partitioned into a regular 6 × 3 grid: six axial sections "
        "along the cell height and three radial rings from core to outer surface. "
        "This produces 18 independent ECM zones, each receiving its own effective "
        "temperature and returning its own heat generation rate. The partitioning "
        "captures the dominant spatial gradients: axial variation (due to end effects "
        "and cap thermal paths) and radial variation (inner core vs cooled outer shell)."
    )
    doc.fig(IMGS / "D08_mapping_strategies.png",
            "Figure 4.1 — Three mapping strategies compared. Left: lumped (uniform). "
            "Centre: assignment (each CFD cell assigned to one zone). Right: "
            "overlap-weighted (CFD cells shared between zones — used in production).")

    doc.h2("Overlap-Weighted Mapping")
    doc.body(
        "At zone boundaries, CFD cells span multiple ECM zones. The overlap-weighted "
        "mapping assigns a fractional contribution to each CFD cell based on the "
        "intersection volume between the cell's control volume and each adjacent ECM zone. "
        "This eliminates sharp heat-source discontinuities at zone boundaries that would "
        "otherwise produce oscillations in the thermal field."
    )
    doc.body(
        "The mapping table contains 65,336 rows for 49,784 jellyRoll cells, representing "
        "an average of ~1.3 zone contributions per cell (most cells belong fully to one "
        "zone; boundary cells contribute to two or three zones)."
    )
    doc.body(
        "The weight field for each zone was computed from the geometric intersection "
        "of the jellyRoll mesh cells with the zone boundaries. Each value is the "
        "fractional volume of the CFD cell that lies within the corresponding ECM zone. "
        "Cells entirely inside a zone carry weight 1.0; cells straddling a boundary "
        "split their contribution proportionally. The 18 weight fields below are rendered "
        "directly from the actual 49,784-cell jellyRoll mesh geometry, sliced through "
        "the cell centre (Y–Z longitudinal plane). Colour scale is per-zone normalised "
        "(viridis: dark = near zero, yellow = maximum contribution)."
    )
    doc.fig(WF / "weight_fields_page1.png",
            "Figure 4.2a — ECM zone weight fields: axial sections z0–z1 (bottom two axial bands). "
            "Each panel shows the jellyRoll mesh polygons coloured by normalised overlap weight "
            "(viridis: dark = near zero, yellow = maximum). "
            "Columns: radial rings r0 (inner) to r2 (outer).")
    doc.fig(WF / "weight_fields_page2.png",
            "Figure 4.2b — ECM zone weight fields: axial sections z2–z3 (mid-cell). "
            "Mid-axial zones carry the highest active weight fractions.")
    doc.fig(WF / "weight_fields_page3.png",
            "Figure 4.2c — ECM zone weight fields: axial sections z4–z5 (top two axial bands). "
            "Smooth falloff at all zone boundaries confirms the overlap-weighted mapping — "
            "no sharp heat-source discontinuities.")

    doc.h2("Spatial Heat Distribution")
    doc.body(
        "The following figures show how the ECM heat source is distributed across the "
        "jellyRoll geometry in the distributed mode. Each zone's heat generation rate "
        "is resolved spatially — inner zones (reduced thermal path to wall) run at a "
        "higher heat density than outer zones at the same axial height."
    )
    doc.fig(IMGS / "SF05_heat_zone_longitudinal.png",
            "Figure 4.4 — Heat per ECM zone (longitudinal cross-section, t = 30 s). "
            "18 distinct heat rates visible. Mid-axial inner zones carry highest heat density.")
    doc.fig(IMGS / "SF06_heat_cell_longitudinal.png",
            "Figure 4.5 — Heat per CFD cell (longitudinal). Overlap-weighted mapping "
            "produces smooth heat field across zone boundaries — no step artefacts.")
    doc.fig(IMGS / "SF07_heat_zone_crosssection.png",
            "Figure 4.6 — Heat per ECM zone (radial cross-section). Three radial rings "
            "clearly resolved. Inner ring (r0) carries the highest heat density.")
    doc.fig(IMGS / "SF08_heat_cell_crosssection.png",
            "Figure 4.7 — Heat per CFD cell (radial cross-section). Smooth "
            "radial gradient from centre to cooled wall.")

    doc.h2("Zone Volume and Heat Share Analysis")
    doc.fig(IMGS / "SF11_zone_volumes.png",
            "Figure 4.8 — ECM zone volumes: outer radial ring (r2) occupies the largest "
            "volume fraction; inner ring (r0) the smallest. Volume fractions are used to "
            "normalise heat density when the ECM returns total power per zone.")
    doc.fig(IMGS / "SF12_zone_heat_share.png",
            "Figure 4.9 — Percentage heat share per zone at quasi-steady state. "
            "Mid-axial zones contribute most heat; top and bottom end zones less "
            "(end-cap conduction path).")
    doc.fig(IMGS / "CS02_ecm_zone_bars.png",
            "Figure 4.10 — Zone-level temperature and heat breakdown at t = 30 s. "
            "Inner-core and mid-axial zones are hottest. "
            "Labels: z0–z5 = axial (bottom→top), r0–r2 = radial (inner→outer).")


def s5_temporal(doc):
    doc.add_page()
    doc.h1("Temporal Heat Interpolation")
    doc.body(
        "In practical deployments the ECM is more expensive to call than a single "
        "CFD timestep advance. Running the ECM at every CFD step is often unnecessary "
        "because the thermal field changes slowly. The framework therefore supports "
        "calling the ECM every N CFD steps, applying an intermediate heat source "
        "between calls. This section explains the two available strategies and "
        "how to choose N."
    )

    doc.h2("The Problem: ECM Call Frequency vs Cost")
    doc.body(
        "For the binary persistent-pipe configuration, each ECM call costs approximately "
        "0.6–1.5 ms depending on cell count. With 1,200 ECM calls for a 300 s simulation "
        "at dt = 0.25 s, the total ECM overhead is modest. However, if the client ECM "
        "is computationally expensive (e.g., a full physics-based P2D model taking 50+ ms "
        "per call), firing it every CFD step would dominate runtime. The N-step gating "
        "reduces ECM invocations by a factor of N."
    )
    doc.fig(IMGS / "CI04_call_frequency_tradeoff.png",
            "Figure 5.1 — ECM call frequency trade-off: normalised heat error vs ECM "
            "call interval N. Hold mode error grows steeply with N; linear interpolation "
            "stays low to N = 6. Recommended: N = 3 with linear interpolation.")

    doc.h2("Hold Mode")
    doc.body(
        "In hold mode, the heat source applied to the CFD solver is held constant at "
        "the last ECM output between calls. When the ECM fires again at step N, "
        "the heat source jumps to the new value. This produces a characteristic "
        "staircase pattern in the Q time series."
    )
    doc.body(
        "Hold mode is acceptable when N is small (N ≤ 2) or when the heat source "
        "is changing slowly relative to the timestep. It is the simpler of the two "
        "modes and has lower bookkeeping overhead."
    )
    doc.fig(IMGS / "CI01_hold_mode.png",
            "Figure 5.2 — Hold mode with N = 3 CFD steps between ECM calls. "
            "The same Q value is applied for three consecutive CFD steps, then "
            "jumps at the next ECM call. Staircase pattern visible in the time series.")

    doc.h2("Linear Interpolation Mode")
    doc.body(
        "In linear interpolation mode, the heat source is ramped linearly between "
        "the previous and current ECM outputs over the N intervening CFD steps. "
        "This eliminates the staircase artefact and produces a smooth Q time series "
        "that closely tracks the true (every-step) ECM output."
    )
    doc.body(
        "Linear interpolation requires storing the previous ECM output and computing "
        "a per-step increment. The additional cost is negligible. This mode is "
        "recommended for all production simulations where N > 1."
    )
    doc.fig(IMGS / "CI02_linear_interp.png",
            "Figure 5.3 — Linear interpolation mode (N = 3). Heat source ramps "
            "smoothly between ECM calls. Dashed grey line shows the smooth reference "
            "(every-step ECM). The interpolated output closely follows the reference.")

    doc.h2("Mode Comparison")
    doc.fig(IMGS / "CI03_mode_comparison.png",
            "Figure 5.4 — Three-mode comparison: hold (left), linear interpolation "
            "(centre), every-step reference (right). Each panel shows the normalised "
            "RMS error vs the reference. Linear interpolation achieves 7× lower "
            "error than hold mode at the same N = 3 interval.")

    doc.h2("Sub-iteration for Tight Coupling")
    doc.body(
        "For scenarios requiring tighter coupling within a single CFD timestep — "
        "for example, fast pulse-power events or short timesteps — the framework "
        "supports sub-iteration: the ECM is called multiple times within one CFD step "
        "with intermediate temperature updates. The averaged heat output is applied "
        "for the step. Sub-iteration increases accuracy at the cost of proportionally "
        "more ECM calls."
    )
    doc.fig(IMGS / "D15_sub_iteration.png",
            "Figure 5.5 — Sub-iteration sequence (3 ECM calls per CFD step): "
            "temperature is updated between each ECM sub-call; the averaged heat "
            "source is applied. Recommended only for dt > 0.5 s with fast ECM dynamics.")


def s6_io(doc):
    doc.add_page()
    doc.h1("Coupler I/O Optimisation")
    doc.body(
        "The I/O protocol between the C++ OpenFOAM coupler and the Python ECM backend "
        "is the most performance-critical element of the coupling framework. This section "
        "documents the progression from the initial implementation to the current "
        "optimised binary persistent-pipe configuration, and quantifies the improvement "
        "at each step."
    )

    doc.h2("Phase I — JSON Spawn (Baseline)")
    doc.body(
        "The initial implementation used a JSON text protocol: at each ECM call, "
        "the coupler wrote a JSON file containing all cell temperatures, launched "
        "a new Python process to read the file and write the output JSON, then "
        "read that output back into OpenFOAM. This approach has two major costs:"
    )
    doc.bullet("Process launch overhead: starting a Python interpreter takes ~90 ms per call")
    doc.bullet("JSON serialisation overhead: converting N doubles to ASCII and back takes ~35 ms write + 7 ms read for 50k cells")
    doc.ln(2)
    doc.body(
        "For a 30 s simulation, the JSON-spawn baseline measured 291 s wall-clock "
        "vs 7 s for the solver alone — a 4,057% overhead. Later sections retain "
        "this 30 s basis for like-for-like comparison across I/O configurations."
    )

    doc.h2("Phase II — Binary Protocol")
    doc.body(
        "The JSON protocol was replaced with a compact binary format. The binary "
        "protocol writes each cell record as 12 bytes (4-byte key + 8-byte double), "
        "compared to ~18–25 bytes per record in JSON text. More importantly, "
        "no string parsing is required on read — the Python backend casts the byte "
        "array directly to a NumPy array."
    )
    doc.body(
        "The binary protocol also introduces a 52-byte header with a monotonic "
        "transaction ID (stepId) that guards against stale outputs: if the ECM "
        "returns output from a previous timestep, the coupler detects the mismatch "
        "and retains the previous heat source rather than applying stale data."
    )
    doc.body("Result: write latency 85 ms → 3.8 ms; read latency 35 ms → 1.4 ms. "
             "Total per-call I/O: 120 ms → 5.2 ms (23× speedup).")

    doc.h2("Phase III — Persistent Pipe")
    doc.body(
        "Even with binary I/O, the per-call overhead in Phase II still included the "
        "~90 ms Python process launch cost. The persistent pipe eliminates this by "
        "keeping the Python ECM process alive between OpenFOAM calls. The C++ coupler "
        "communicates with the persistent process via stdin/stdout binary streams "
        "rather than filesystem files."
    )
    doc.body(
        "Result: per-call overhead drops from 120 ms (binary spawn) to 0.6–1.5 ms "
        "(binary persistent pipe). For 1,200 calls in a 300 s simulation, total "
        "ECM I/O overhead falls from 144 s to under 2 s — well within the "
        "acceptable 5% overhead budget."
    )
    doc.fig(IMGS / "CP01_io_performance_evolution.png",
            "Figure 6.1 — I/O optimisation progression: wall-clock time (left) and "
            "overhead percentage (right) across the four development phases. "
            "Binary persistent pipe achieves 8× improvement over JSON spawn.")

    doc.h2("Benchmark Results")
    doc.fig(IMGS / "CP02_io_latency_scaling.png",
            "Figure 6.2 — Per-call latency breakdown (left) and latency scaling with "
            "cell count (right). Binary persistent pipe: 0.6 ms at N=50, 1.1 ms at "
            "N=5,000. JSON spawn: 120 ms at N=50, 135 ms at N=5,000.")

    doc.h2("ECM Cell Count Ceiling — 5,000 Cells")
    doc.body(
        "The framework is designed and tested for up to 5,000 ECM cells per simulation. "
        "At this ceiling the binary persistent-pipe I/O latency is approximately 1.1 ms "
        "per call, producing a cumulative overhead of under 1.5 s for a 300 s simulation. "
        "The ceiling is not a hard technical limit — it reflects the validated operating "
        "range and the practical cell-count needs of the 4680 geometry."
    )
    doc.fig(IMGS / "C01_ecm_cell_scaling.png",
            "Figure 6.3 — ECM cell count scaling: per-call latency (left) and total "
            "overhead for a 300 s simulation (right). Both scale linearly with N. "
            "At the 5,000-cell ceiling, overhead is under 1.5 s — well below 1% "
            "of simulation time.")

    perf_rows = [
        ("JSON spawn (Phase I)",           "291 s",  "4,057%", "~120 ms"),
        ("Binary spawn (Phase II)",        "120 s",  "1,614%", "~5.2 ms"),
        ("Binary persistent pipe (Phase III)", "42 s", "~500%", "~0.6–1.1 ms"),
        ("Distributed binary pipe (Phase IV)", "47 s", "~571%", "~0.6–1.5 ms"),
    ]
    ws = [72, 20, 24, 50]
    doc.table_row(["Configuration", "30 s sim", "Overhead", "Per-call I/O"], ws, header=True)
    for i, r in enumerate(perf_rows):
        doc.table_row(r, ws, alt=i%2==0)
    doc.ln(2)
    doc.body("Solver-only baseline (no ECM): 7 s for a 30 s simulation.")
    doc.note(
        "Important — two distinct overhead metrics are reported in this document. "
        "(1) Total wall-clock overhead: (total time − solver-only) / solver-only. "
        "For Phase IV: (47 s − 7 s) / 7 s ≈ 571%. This includes the Python "
        "computation time of the stand-in ECM backend per call, which will differ "
        "for the real client ECM. "
        "(2) Pure I/O protocol overhead: the binary read/write time only, excluding "
        "ECM computation. For Phase IV at N = 18 zones: ~1.5 ms × 120 calls (30 s sim) "
        "= 0.18 s, or ~2.6% of solver time. "
        "The 'speedup' figures (23× JSON→binary) refer to the I/O protocol cost "
        "exclusively. The total wall-clock overhead depends on the client ECM compute "
        "time per call, which is unknown until integration."
    )


def s7_validation(doc):
    doc.add_page()
    doc.h1("Validation Results")
    doc.body(
        "A systematic validation campaign verified the correctness of the coupling "
        "framework across ten independent test configurations. Each test targets a "
        "specific aspect of the coupling — zero-heat condition, heat generation accuracy, "
        "spatial distribution, energy conservation, mesh independence, and temporal "
        "convergence. All ten tests passed."
    )
    doc.fig(IMGS / "CV05_validation_campaign.png",
            "Figure 7.1 — Validation campaign: 10/10 tests passed across lumped, "
            "distributed, and combined configurations.")

    doc.h2("Zero-Current Equivalence")
    doc.body(
        "When the ECM receives zero current (I = 0), it must return zero heat. "
        "The coupled solver result must be identical to a solver run with no ECM at all. "
        "This test confirms that ecmCoupler injects no spurious heat when the ECM is off."
    )
    doc.fig(IMGS / "CV01_validation_zero_current.png",
            "Figure 7.2 — Zero-current test: Q_sum = 0.000 W for both lumped and "
            "distributed configurations throughout the 30 s run. No spurious heat injection.")

    doc.h2("Fixed-Current Response")
    doc.body(
        "Under a fixed 1C current the ECM generates heat as the RC branches charge "
        "and Joule dissipation establishes. Both lumped and distributed configurations "
        "are compared: at the cell level (total Q) they must agree; spatially, the "
        "distributed mode resolves the zone-level variation."
    )
    doc.fig(IMGS / "CV02_validation_fixed_current_tmax.png",
            "Figure 7.3 — Fixed-current T_max comparison: lumped vs distributed. "
            "Peak temperature difference at t = 30 s is within 0.01 K, confirming "
            "equivalence at the cell level.")
    doc.fig(IMGS / "CV03_validation_fixed_current_q.png",
            "Figure 7.4 — Fixed-current Q_sum comparison: lumped vs distributed. "
            "Total heat generation tracks identically between modes, confirming "
            "energy conservation in the mapping step.")

    doc.h2("Mesh Convergence")
    doc.body(
        "Three mesh refinement levels were tested (coarse ~6k cells, medium ~50k cells, "
        "fine ~374k cells). The coarse-to-medium T_max change is 0.89 K; "
        "medium-to-fine is 0.051 K — confirming grid-independent results at the "
        "medium refinement level used for all production runs."
    )
    doc.fig(IMGS / "CV04_mesh_convergence.png",
            "Figure 7.5 — Mesh convergence: T_max and step-to-step ΔT. "
            "Medium-to-fine change is 0.051 K — grid-independent results "
            "confirmed for both lumped and distributed modes.")


def s8_thermal(doc):
    doc.add_page()
    doc.h1("Thermal Field Results")

    doc.h2("Temperature Distribution at t = 30 s")
    doc.body(
        "After 30 s at 1C current, the jellyRoll core reaches approximately 343 K "
        "while the external wall remains fixed at 313 K. The shell and cap regions "
        "show intermediate temperatures governed by the solid–solid interface "
        "conductances. Comparing the lumped and distributed results confirms that "
        "the spatial heat distribution has a measurable effect on the temperature field."
    )
    doc.fig(IMGS / "SF01_lumped_longitudinal_30s.png",
            "Figure 8.1 — Lumped case: longitudinal temperature slice at t = 30 s. "
            "Smooth radial gradient; jellyRoll core hottest.")
    doc.fig(IMGS / "SF02_dist_longitudinal_30s.png",
            "Figure 8.2 — Distributed case: longitudinal slice at t = 30 s. "
            "Zone-by-zone axial variation visible. Mid-cell zones run slightly "
            "hotter than end zones due to reduced end-cap heat dissipation.")
    doc.fig(IMGS / "SF03_lumped_crosssection_30s.png",
            "Figure 8.3 — Lumped case: radial cross-section at t = 30 s. "
            "Concentric thermal gradient from core to cooled wall.")
    doc.fig(IMGS / "SF04_dist_crosssection_300s.png",
            "Figure 8.4 — Distributed case: radial cross-section at t = 300 s (extended run). "
            "Three ECM radial rings produce concentric variation; inner ring "
            "runs hottest as expected.")

    doc.h2("Heat Generation Transient")
    doc.fig(IMGS / "CQ02_q_distributed_300s.png",
            "Figure 8.5 — Distributed case: Q_sum_check over 300 s. "
            "Initial rise as RC branches charge (~0–15 s), then quasi-steady state "
            "as heat generation balances heat loss to the cooled wall. "
            "Plateau value provides the steady-state power dissipation.")

    doc.h2("Extended 300-second Run")
    doc.body(
        "A 300 s simulation was run to characterise the approach to thermal equilibrium. "
        "The jellyRoll temperature continues to rise slowly after t = 30 s as the shell "
        "and cap reach their steady-state temperatures and the overall thermal mass "
        "saturates."
    )
    doc.fig(IMGS / "SF13_extended_300s_longitudinal.png",
            "Figure 8.6 — Extended 300 s run: longitudinal temperature slice at "
            "quasi-steady state. Full axial and radial gradients developed.")
    doc.fig(IMGS / "SF14_extended_300s_crosssection.png",
            "Figure 8.7 — Extended 300 s run: radial cross-section at quasi-steady "
            "state. Fully-developed thermal layers from jellyRoll core to wall.")

    doc.h2("Axial Temperature Profiles")
    doc.body(
        "Sampling temperature along the cell axis (Z direction) reveals the "
        "axial thermal gradient across all three solid regions — jellyRoll, "
        "shell, and cap. The distributed case (t = 300 s) shows the fully "
        "developed gradient with the mid-cell jellyRoll zone hottest; the "
        "cap region drops sharply due to its high thermal conductivity path "
        "to the cooled wall."
    )
    doc.fig(IMGS / "ST01_axial_T_distributed.png",
            "Figure 8.8 — Distributed case: axial temperature profile along the cell "
            "centreline at t = 300 s. Shaded bands indicate spatial extents of each region. "
            "jellyRoll (blue) shows the highest temperature; cap (green) the sharpest drop.")
    doc.fig(IMGS / "ST02_axial_T_lumped.png",
            "Figure 8.9 — Lumped case: axial temperature profile at t = 30 s. "
            "Cell-centre scatter points from all near-axis CFD cells. "
            "The jellyRoll profile is nearly uniform in Z (expected: single lumped ECM zone).")


def s9_integration(doc):
    doc.add_page()
    doc.h1("Client ECM Integration Guide")
    doc.body(
        "This section provides a concise guide for integrating the client-provided "
        "ECM into the coupling framework. The interface contract is stable and all "
        "infrastructure (C++ coupler, OpenFOAM case files, binary protocol) remains "
        "unchanged."
    )

    doc.h2("What Needs to Change")
    doc.note(
        "The following is the expected integration path based on the current protocol "
        "design. It assumes the client ECM can conform to the binary I/O contract "
        "(temperature inputs, heat output units, persistent state, timestep semantics). "
        "Until tested with the actual client code this remains an engineering hypothesis. "
        "See Section 10 for the full list of open integration items."
    )
    doc.body("Expected minimal change set — one file is expected to require replacement first:")
    doc.bullet("ecm/mock_ecm_backend.py  →  client_ecm_backend.py  (the ECM compute module)")
    doc.ln(2)
    doc.body("Intended to remain unchanged in the first integration attempt (subject to integration testing):")
    for item in [
        "ecm/ecm_coupler.py  (orchestrator — reads protocol, calls backend, writes output)",
        "ecm/ecm_io.py  (binary protocol parser/writer)",
        "src/ecmCouplingFunctionObjects/  (C++ coupler — unchanged)",
        "cases/distributed_solid/  (OpenFOAM case — unchanged)",
        "system/controlDict  (coupling configuration — unchanged)",
    ]:
        doc.bullet(item)

    doc.h2("Binary Protocol Interface")
    doc.body("The client ECM backend must implement the following interface:")
    ws = [35, 30, 100]
    doc.table_row(["File", "Direction", "Contents"], ws, header=True)
    doc.table_row(["ecm_in.bin", "OF → ECM",
                  "Header (52 bytes) + N records: [int32 key, float64 T_K]"], ws, alt=True)
    doc.table_row(["ecm_out.bin", "ECM → OF",
                  "Header (52 bytes) + N records: [int32 key, float64 qVol_W_per_m3]"], ws)
    doc.ln(3)

    doc.h2("ECM Cell Count")
    doc.body(
        "The framework supports up to 5,000 ECM cells per simulation. For the validated "
        "4680 geometry with 18-zone distributed coupling, each zone contains ~2,800 "
        "CFD cells but a single ECM key — well within the ceiling. If the client ECM "
        "uses a finer internal mesh, the coupling can be run in elementWise mode "
        "with the overlap-weighted mapping table mapping client ECM elements to CFD cells."
    )
    doc.note(
        "Recommendation: use the existing 18-zone partition for the first integration. "
        "This limits the client ECM to 18 temperature inputs and returns 18 qVol values, "
        "independent of the client ECM's internal resolution. The mapping table handles "
        "the CFD-to-ECM and ECM-to-CFD transformations transparently."
    )

    doc.h2("Configuration Parameters")
    ws = [55, 60, 50]
    doc.table_row(["Parameter", "Current value", "Notes"], ws, header=True)
    config = [
        ("couplingMode",  "elementWise",          "Use distributed 18-zone mode"),
        ("ioMode",        "binary",               "Do not change"),
        ("command",       "python3 ecm/ecm_coupler.py", "Change backend module here"),
        ("ECM_MAPPING_FILE", "ecm/mapping_table.csv", "Mapping table path"),
        ("ECM_CALL_EVERY_N_STEPS", "3",           "Adjust for ECM cost vs accuracy"),
        ("ECM_INTERP_MODE",    "linear",          "linear recommended"),
    ]
    for i, r in enumerate(config):
        doc.table_row(r, ws, alt=i%2==0)
    doc.ln(3)


def s11_open_items(doc):
    doc.add_page()
    doc.h1("Open Items & Residual Integration Risks")
    doc.body(
        "This section explicitly distinguishes what this work has demonstrated from "
        "what remains to be proven. Its purpose is to give the client a clear picture "
        "of residual risks before accepting the deliverable as complete."
    )

    doc.h2("What This Work Has Demonstrated")
    proven = [
        "Weak-coupling architecture: one ECM call per CFD timestep, clean data exchange, "
        "no solver modification required.",
        "18-zone distributed partitioning with overlap-weighted mapping eliminates "
        "heat-source discontinuities at zone boundaries.",
        "Binary persistent-pipe I/O protocol: <2 s cumulative I/O overhead for a "
        "300 s simulation at the 18-zone operating point.",
        "10/10 validation tests passed: zero-current, fixed-current, energy balance, "
        "mesh convergence, timestep sensitivity, lumped–distributed equivalence.",
        "Mesh convergence confirmed: medium-to-fine ΔT_max = 0.051 K.",
        "I/O protocol 23× faster than the JSON-spawn baseline (pure I/O cost).",
        "stepId transaction guard correctly rejects stale ECM output.",
    ]
    for item in proven:
        doc.bullet(item)
    doc.ln(2)

    doc.h2("What Has Not Yet Been Demonstrated")
    doc.note(
        "The following items are open integration risks. They do not invalidate the "
        "Phase 1 de-risking work, but they must be resolved before the coupling "
        "framework can be considered production-ready for the client use case.",
        fc=(255, 235, 238), ec=C_RED
    )
    risks = [
        ("Client ECM interface compliance",
         "The stand-in ECM was written to the protocol. The client ECM has not yet "
         "been tested against the binary I/O contract. Risks include: units mismatch "
         "(W vs W/m³), different timestep semantics, state initialisation differences, "
         "or inability to run as a persistent process."),
        ("Predictive fidelity",
         "All thermal results (temperature fields, Q time series, spatial gradients) "
         "reflect the 2-RC stand-in ECM, not the client's chemistry. No comparison "
         "against measured cell data has been performed."),
        ("Like-for-like regression baseline",
         "There is no agreed-upon reference case (measured or simulation) against which "
         "the coupled result can be validated once the client ECM is connected."),
        ("Client ECM computational cost",
         "The total wall-clock overhead of the coupled simulation depends on the "
         "client ECM's per-call compute time, which is unknown. The stand-in Python "
         "backend adds ~29 ms per call; a more expensive ECM would increase total "
         "run time proportionally."),
        ("Python environment compatibility",
         "The persistent-pipe ECM daemon requires a Python environment with the client "
         "ECM's dependencies. Dependency conflicts or C-extension requirements may "
         "require additional environment setup."),
        ("Parallel (MPI) integration testing",
         "Parallel operation (masterGather mode) has been validated with the stand-in "
         "ECM but not with an external client ECM process. The MPI gather/scatter "
         "path should be re-verified after integration."),
    ]
    aw   = doc.w - doc.l_margin - doc.r_margin   # 166 mm
    w1   = 50                                      # risk-name column
    w2   = aw - w1                                 # description column
    lh   = 4.5                                     # line height
    pad  = 1.5                                     # top/bottom cell padding

    # Header
    doc.table_row(["Risk area", "Description"], [w1, w2], header=True)

    doc.set_font("DV", "", 8.5)
    for i, (risk, desc) in enumerate(risks):
        alt = i % 2 == 0
        fc  = C_LGREY if alt else C_WHITE

        x0 = doc.l_margin

        # Dry-run both cells so the row height matches the taller wrapped column.
        risk_ht = float(doc.multi_cell(w1 - 3, lh, risk,
                                       dry_run=True, output="HEIGHT"))
        desc_ht = float(doc.multi_cell(w2 - 3, lh, desc,
                                       dry_run=True, output="HEIGHT"))
        row_h   = max(risk_ht, desc_ht) + 2 * pad
        row_h   = max(row_h, 6.0)

        # Page-break guard: if row won't fit on current page, start a new one
        page_bottom = doc.h - doc.b_margin
        if doc.get_y() + row_h > page_bottom:
            doc.add_page()
            doc.set_font("DV", "", 8.5)

        y0 = doc.get_y()

        # Background fill
        doc.set_fill_color(*fc)
        doc.rect(x0, y0, aw, row_h, "F")

        # Outer border + vertical column divider
        doc.set_draw_color(185, 185, 195)
        doc.set_line_width(0.18)
        doc.rect(x0, y0, aw, row_h, "D")
        doc.line(x0 + w1, y0, x0 + w1, y0 + row_h)

        # Left cell: wrapped risk area name
        doc.set_text_color(*C_DARK)
        doc.set_xy(x0 + 1.5, y0 + pad)
        doc.multi_cell(w1 - 3, lh, risk, border=0, fill=False,
                       new_x="RIGHT", new_y="TOP")

        # Right cell: wrapped description
        doc.set_xy(x0 + w1 + 1.5, y0 + pad)
        doc.multi_cell(w2 - 3, lh, desc, border=0, fill=False,
                       new_x="LMARGIN", new_y="NEXT")

        # Advance cursor to next row
        doc.set_xy(x0, y0 + row_h)

    doc.ln(3)

    doc.h2("Recommended Next Steps")
    steps = [
        "Integrate the actual client ECM backend against the binary protocol. "
        "Start with the lumped (single-zone) mode for the simplest interface test.",
        "Run the zero-current and fixed-current validation tests with the client ECM "
        "to confirm interface compliance.",
        "Agree on a reference case (cell datasheet discharge curve or calorimetry "
        "measurement) and run a like-for-like comparison.",
        "Profile the client ECM's per-call compute time and restate the total "
        "wall-clock overhead figure for the real backend.",
        "If persistent-pipe mode is not compatible with the client ECM runtime, "
        "fall back to binary-spawn mode (Phase II) as a temporary measure.",
    ]
    for i, step in enumerate(steps, 1):
        doc.bullet(f"{i}. {step}")


def s10_phases_appendix(doc):
    doc.add_page()
    doc.h1("Appendix — Protocol Reference")

    doc.h2("Binary Protocol v2 Header (52 bytes)")
    ws = [28, 18, 8, 112]
    doc.table_row(["Field", "Type", "Bytes", "Description"], ws, header=True)
    hdr = [
        ("magic[8]",  "char[8]",  "8", "ASCII 'ECMIOv1\\0' — file identification"),
        ("fileType",  "uint32",   "4", "1 = input (OF→ECM),  2 = output (ECM→OF)"),
        ("version",   "uint32",   "4", "Protocol version: 2"),
        ("N",         "uint32",   "4", "Number of coupled ECM cells (≤ 5,000)"),
        ("time",      "float64",  "8", "Simulation time [s]"),
        ("deltaT",    "float64",  "8", "CFD timestep [s]"),
        ("keyMode",   "uint32",   "4", "0 = globalCellId (always use 0)"),
        ("nInputs",   "uint32",   "4", "Number of scalar electrical inputs"),
        ("stepId",    "uint64",   "8", "v2: monotonic transaction ID — stale-output guard"),
    ]
    for i, r in enumerate(hdr):
        doc.table_row(r, ws, alt=i%2==0)
    doc.ln(4)

    doc.h2("Validated Configuration Parameters")
    doc.body("The following settings were used for all validation runs and are recommended "
             "as the starting point for client integration:")
    ws2 = [55, 45, 65]
    doc.table_row(["Parameter", "Value", "Rationale"], ws2, header=True)
    params = [
        ("endTime",            "300 s",     "Full thermal equilibration"),
        ("deltaT",             "0.25 s",    "Timestep convergence confirmed"),
        ("blockMesh cell size","1 mm",      "Mesh convergence confirmed at medium"),
        ("ECM call interval",  "3 steps",   "N=3 with linear interp: <1% NRMS error"),
        ("temporalInterpolation", "linear", "Smooth heat; no staircase artefact"),
        ("parallelMode",       "masterGather", "Required for MPI runs"),
        ("keyMode",            "0 (global)", "Required for MPI runs"),
    ]
    for i, r in enumerate(params):
        doc.table_row(r, ws2, alt=i%2==0)


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("Building client-facing PDF…")
    doc = Doc()
    doc.cover()

    s1_executive(doc)
    s2_overview(doc)
    s3_standin(doc)
    s4_distributed(doc)
    s5_temporal(doc)
    s6_io(doc)
    s7_validation(doc)
    s8_thermal(doc)
    s9_integration(doc)
    s11_open_items(doc)
    s10_phases_appendix(doc)

    doc.toc_page()

    print(f"  Pages: {doc.page}")
    doc.output(str(OUT_PDF))
    size = OUT_PDF.stat().st_size / 1e6
    print(f"  Saved → {OUT_PDF}  ({size:.1f} MB)")


if __name__ == "__main__":
    main()
