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
