# E004 Diagnostic Campaign Matrix — 2026-09-10

Baseline: `out/hp2170NCA-RCR-distributed-exact-contact-final.tbm`  
Baseline SHA-256: `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`  
Baseline source: commit `d74b3283cb5d73e114bc141f3f0d18e7c7ed5463`

Baseline axial margins: pkg-sep = -2.00 mm | pkg-neg = 0.00 mm | pkg-pos = +1.00 mm

Recommended test order: C00, C03, C14, C15, C16, C17, C10, C12, C13, C05, C07, C04, C06, C08, C09, C11, C01, C02

Runtime result columns are blank — to be filled from Robert's test results.

---

## C00 — `C00_SIEMENS_CONTROL_validationBattery.tbm`

**SHA-256:** `82aa9daa6a7e9a4218bb8eb5e3aad2fdfb299a3031deede89523715a542dffee`  
**Base SHA-256:** `N/A — Siemens install reference`
**Changed fields:** N/A — unmodified Siemens reference
**Purpose:** Environment/import-path control. Proves Robert's STAR install and Create from Tbm workflow import a known Siemens cylindrical TBM.

| Parameter | Value |
|---|---|
| sep_feed_mm | N/A |
| sep_tail_mm | N/A |
| overlap_start_mm | N/A |
| overlap_end_mm | N/A |
| mandrel_width_mm | N/A |
| jr_width_mm | N/A |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C01 — `C01_FEED10.tbm`

**SHA-256:** `912db12a2183209f2ad4f49c776b176765db6b82cfa8367c532b08ddd62732c7`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepFeedLength_mm: 0 -> 10
**Purpose:** Isolate separator feed length: feed=10 alone vs E004.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 0 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C02 — `C02_TAIL85.tbm`

**SHA-256:** `7596ff01f4f43218ba60484b53b59cd9d52994ff8f9735d50621b27c57ad449a`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepTailLength_mm: 0 -> 85
**Purpose:** Isolate separator tail length: tail=85 alone vs E004.

| Parameter | Value |
|---|---|
| sep_feed_mm | 0 |
| sep_tail_mm | 85 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C03 — `C03_FEED10_TAIL85.tbm`

**SHA-256:** `bf0d6c3e5c22cd3f07a48a2b57be56b1dae36f174610ed648fc36dcdacb80b53`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepFeedLength_mm: 0 -> 10; m_dSepTailLength_mm: 0 -> 85
**Purpose:** H004-5 leading hypothesis: combined feed+tail.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C04 — `C04_END40.tbm`

**SHA-256:** `6e737ca16035da37aa2118f700e38a004f500a17cfebff31368d72e96f82ce80`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dElectrodeOverlapAtEnd_mm: 20 -> 40
**Purpose:** Isolate end-overlap influence on E004.

| Parameter | Value |
|---|---|
| sep_feed_mm | 0 |
| sep_tail_mm | 0 |
| overlap_start_mm | 8 |
| overlap_end_mm | 40 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C05 — `C05_FEED10_TAIL85_END40.tbm`

**SHA-256:** `90d289c9d2e6f20e2759f0dbcf1b7d4327f42bb4c7c7ba4eae0ee04f2f54e5a9`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepFeedLength_mm: 0 -> 10; m_dSepTailLength_mm: 0 -> 85; m_dElectrodeOverlapAtEnd_mm: 20 -> 40
**Purpose:** Feed+tail+end-overlap interaction test.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 8 |
| overlap_end_mm | 40 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C06 — `C06_MANDRELWIDTH0.tbm`

**SHA-256:** `49f4f6f50d57db2dc3aed63ca37733ca0cdd51fe41280d7805f4dd7a5475ce36`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dMandrelWidth_mm: 6 -> 0
**Purpose:** STAR round-mandrel convention: MandrelWidth=0 alone vs E004.

| Parameter | Value |
|---|---|
| sep_feed_mm | 0 |
| sep_tail_mm | 0 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 0 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C07 — `C07_FEED10_TAIL85_MANDRELWIDTH0.tbm`

**SHA-256:** `e418b2f09c0ea957d25607fe7e90df079e3e6da7b2564350eaaeffd5f06654c4`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepFeedLength_mm: 0 -> 10; m_dSepTailLength_mm: 0 -> 85; m_dMandrelWidth_mm: 6 -> 0
**Purpose:** Feed+tail with STAR round-mandrel width convention.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 0 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C08 — `C08_JRWIDTH65p11.tbm`

**SHA-256:** `a271bfbd6c7012bf9fb9f8543706804c0048594323f4a92047e6967a71acbc88`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dJellyrollWidth_mm: 0 -> 65.11
**Purpose:** Low-probability probe: JellyrollWidth zero in Detailed Builder.

| Parameter | Value |
|---|---|
| sep_feed_mm | 0 |
| sep_tail_mm | 0 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 65.11 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C09 — `C09_FEED10_TAIL85_JRWIDTH65p11.tbm`

**SHA-256:** `364501027db55ce8974224aa20ae9b8e20a515ac10b3c9d6139dd9af18f8387e`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepFeedLength_mm: 0 -> 10; m_dSepTailLength_mm: 0 -> 85; m_dJellyrollWidth_mm: 0 -> 65.11
**Purpose:** Feed+tail + JellyrollWidth interaction probe.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 65.11 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C10 — `C10_STAR_BUILDER_PATTERN.tbm`

**SHA-256:** `08252a958eeacc8157d906637e3d2416d1b7baa74f4e21f7d5f87529c0ad8984`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepFeedLength_mm: 0 -> 10; m_dSepTailLength_mm: 0 -> 85; m_dElectrodeOverlapAtStart_mm: 8 -> 3; m_dElectrodeOverlapAtEnd_mm: 20 -> 40; m_dMandrelWidth_mm: 6 -> 0
**Purpose:** Broad STAR-reference Detailed Builder pattern rescue.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 3 |
| overlap_end_mm | 40 |
| mandrel_width_mm | 0 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C11 — `C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm`

**SHA-256:** `5726c52ff9be146705f9d6ced6bf502ac03c39524ef4f8e379c85e436f2531e6`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** m_dSepFeedLength_mm: 0 -> 10; m_dSepTailLength_mm: 0 -> 85; m_dElectrodeOverlapAtStart_mm: 8 -> 3; m_dElectrodeOverlapAtEnd_mm: 20 -> 40; m_dMandrelWidth_mm: 6 -> 0; m_dJellyrollWidth_mm: 0 -> 65.11
**Purpose:** Maximum geometry-builder rescue: all STAR-pattern changes + explicit JR width.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 3 |
| overlap_end_mm | 40 |
| mandrel_width_mm | 0 |
| jr_width_mm | 65.11 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C12 — `C12_FULL_SIEMENS_DETAILED_BUILDER.tbm`

**SHA-256:** `94e0fef9b7cb4199103dd462b960be5a26f08d78a5829489c9683bfd25b31c8f`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** Complete Detailed Builder block replaced with Siemens validationBattery.tbm BUILDER
**Purpose:** Broad localization control: full Siemens Detailed Builder in project file. If C01-C11 all fail but C12 passes, culprit is in Builder fields outside tested subset.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 3 |
| overlap_end_mm | 40 |
| mandrel_width_mm | 0 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C13 — `C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm`

**SHA-256:** `606b2ccd3d774e90d25f03a55157f7f6acb1dbcdf21da9274a8fab3d06c67d8d`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** Siemens Physical Cell Description + Detailed Builder; project SIMMOD/MODELMAP/RCR retained
**Purpose:** Strongest geometry-vs-model localization control. Siemens geometry with project RCR model. If C12 passes but C13 fails: E004 involves Physical Cell Description interaction. If C13 passes: confirms E004 is localized to project Detailed Builder content.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 3 |
| overlap_end_mm | 40 |
| mandrel_width_mm | 0 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | -2.00 mm |
| pkg − negative  | +0.00 mm |
| pkg − positive  | +1.00 mm |

**Runtime result:** *(pending)*

---

## C14 — `C14_AXIAL_CAVITY68p11.tbm`

**SHA-256:** `4266c8907dcf1f6ad026756160a6a1e7e905c225722d89ff2f63950ad2d1e92c`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** Package m_dintHeight: 65.11 -> 68.11 [PCD]
**Purpose:** Axial cavity clearance only: Package m_dintHeight 65.11->68.11 gives pkg-sep=+1, pkg-neg=+3, pkg-pos=+4 mm (Siemens margins) while retaining all electrode/separator widths. DIAGNOSTIC ONLY — not production target.

| Parameter | Value |
|---|---|
| sep_feed_mm | 0 |
| sep_tail_mm | 0 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 68.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | +1.00 mm |
| pkg − negative  | +3.00 mm |
| pkg − positive  | +4.00 mm |

**Runtime result:** *(pending)*

---

## C15 — `C15_AXIAL_CAVITY68p11_FEED10_TAIL85.tbm`

**SHA-256:** `1973b801d294163e5259cf88b218e6644ed303ca1a474aa89aa93ea74d81f1d5`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** Package m_dintHeight: 65.11 -> 68.11 [PCD]; m_dSepFeedLength_mm: 0 -> 10 [BUILDER]; m_dSepTailLength_mm: 0 -> 85 [BUILDER]
**Purpose:** Axial cavity clearance + feed/tail leading hypothesis: both strongest independent geometry suspects combined. If C03 fails but C15 passes, axial package clearance participates in E004. DIAGNOSTIC ONLY.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 68.11 |
| separator_width_mm | 67.11 |
| negative_width_mm | 65.11 |
| positive_width_mm | 64.11 |
| pkg − separator | +1.00 mm |
| pkg − negative  | +3.00 mm |
| pkg − positive  | +4.00 mm |

**Runtime result:** *(pending)*

---

## C16 — `C16_RECESSED_LAYERS_FIXED_CAVITY.tbm`

**SHA-256:** `711a1dad4c52cbd17c3dc72d2604f9661a4dcfb065f744431c2aa4d574c2a445`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** SeparatorList1_Separator m_dWidth_mm: 67.11 -> 64.11 [PCD]; +Electrode m_dWidth: 64.11 -> 61.11 [PCD]; +Electrode m_dCoatingWidth: 64.11 -> 61.11 [PCD]; +Electrode Collector m_dWidth_mm: 64.11 -> 61.11 [PCD]; -Electrode m_dWidth: 65.11 -> 62.11 [PCD]; -Electrode m_dCoatingWidth: 65.11 -> 62.11 [PCD]; -Electrode Collector m_dWidth_mm: 65.11 -> 62.11 [PCD]
**Purpose:** Explicit layer recession inside original 65.11 mm cavity: all electrode/separator widths reduced by 3 mm so pkg-sep=+1, pkg-neg=+3, pkg-pos=+4 mm. DIAGNOSTIC ONLY — do not use for electrical equivalence assessment. Physical electrode widths alter active area and RCR mapping. Tab widths, tape widths, S1-S6, RCR data, radial geometry unchanged.

| Parameter | Value |
|---|---|
| sep_feed_mm | 0 |
| sep_tail_mm | 0 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 64.11 |
| negative_width_mm | 62.11 |
| positive_width_mm | 61.11 |
| pkg − separator | +1.00 mm |
| pkg − negative  | +3.00 mm |
| pkg − positive  | +4.00 mm |

**Runtime result:** *(pending)*

---

## C17 — `C17_RECESSED_LAYERS_FEED10_TAIL85.tbm`

**SHA-256:** `71292128d4fedfb9a57cbe6361115a5016be2e59e4a91d05377b61627ae0a175`  
**Base SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Changed fields:** SeparatorList1_Separator m_dWidth_mm: 67.11 -> 64.11 [PCD]; +Electrode m_dWidth: 64.11 -> 61.11 [PCD]; +Electrode m_dCoatingWidth: 64.11 -> 61.11 [PCD]; +Electrode Collector m_dWidth_mm: 64.11 -> 61.11 [PCD]; -Electrode m_dWidth: 65.11 -> 62.11 [PCD]; -Electrode m_dCoatingWidth: 65.11 -> 62.11 [PCD]; -Electrode Collector m_dWidth_mm: 65.11 -> 62.11 [PCD]; m_dSepFeedLength_mm: 0 -> 10 [BUILDER]; m_dSepTailLength_mm: 0 -> 85 [BUILDER]
**Purpose:** Maximum axial-recession rescue retaining original 65.11 mm package internal height: all C16 layer-width reductions plus feed=10 tail=85. DIAGNOSTIC ONLY — do not use for electrical equivalence assessment.

| Parameter | Value |
|---|---|
| sep_feed_mm | 10 |
| sep_tail_mm | 85 |
| overlap_start_mm | 8 |
| overlap_end_mm | 20 |
| mandrel_width_mm | 6 |
| jr_width_mm | 0 |

**Axial geometry:**

| Dimension | Value |
|---|---|
| package_int_height_mm | 65.11 |
| separator_width_mm | 64.11 |
| negative_width_mm | 62.11 |
| positive_width_mm | 61.11 |
| pkg − separator | +1.00 mm |
| pkg − negative  | +3.00 mm |
| pkg − positive  | +4.00 mm |

**Runtime result:** *(pending)*

---
