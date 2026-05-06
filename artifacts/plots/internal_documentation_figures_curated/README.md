# Internal Documentation - Curated Visualizations

**Curated:** 2026-03-28
**Total Figures:** Complete visual suite for internal documentation
**Location:** `/workspace/artifacts/plots/internal_documentation_figures_curated/`

---

## 📊 CURATED FIGURE SET (By Category)

### Architecture & System Design (3 figures)
- **01_architecture_diagram.png** - Complete system overview with all components
- **02_coupling_sequence_diagram.png** - 12-step timestep execution sequence
- **12_timestep_and_interpolation_logic.png** - Temporal coupling implementation details

### Model Architecture (3 figures)
- **02_model_concept_lumped_vs_distributed.png** - Conceptual comparison
- **04_zero_current_comparison_30s.png** - Equilibrium validation (ECM off)
- **05_fixed_current_comparison_30s.png** - Fixed-current validation (ECM on)

### Temperature Field Visualizations (8 figures)
**Lumped Case:**
- **07_lumped_allregions_longitudinal_30s.png** - Longitudinal cross-section @ 30s (3 regions)
- **22_lumped_allregions_longitudinal_10s.png** - Longitudinal cross-section @ 10s (early transient)
- **09_lumped_allregions_cross_section_30s.png** - Cross-sectional view @ 30s
- **24_lumped_allregions_cross_section_10s.png** - Cross-sectional view @ 10s

**Distributed Case:**
- **08_distributed_allregions_longitudinal_30s.png** - Longitudinal @ 30s with 18 ECM zones
- **23_distributed_allregions_longitudinal_10s.png** - Longitudinal @ 10s (early transient)
- **10_distributed_allregions_cross_section_30s.png** - Cross-section @ 30s
- **25_distributed_allregions_cross_section_10s.png** - Cross-section @ 10s

### Heat Generation & ECM Mapping (6 figures)
- **13_overlap_mapping_heat_per_ecm_zone_W.png** - Heat distribution by ECM zone (longitudinal)
- **14_overlap_mapping_heat_per_cfd_cell_W.png** - Heat at CFD cell scale (longitudinal)
- **28_overlap_mapping_heat_per_ecm_zone_W_cross.png** - Heat per zone (cross-section)
- **29_overlap_mapping_heat_per_cfd_cell_W_cross.png** - Heat per cell (cross-section)
- **30_overlap_mapping_zone_volumes.png** - ECM zone volume fractions
- **31_overlap_mapping_zone_heat_share.png** - Percentage heat per zone

### Weight Distribution & Mapping (3 figures)
- **16_weight_support_zone00.png** - Central zone weight distribution
- **17_weight_support_zone08.png** - Mid-level zone weight distribution
- **18_weight_support_zone17.png** - Top zone weight distribution

### Validation & Performance (8 figures)
- **20_validation_campaign_results.png** - Summary: 10/10 tests PASSED
- **21_detailed_validation_metrics.png** - Detailed breakdown with statistics
- **03_validation_summary_metrics.png** - Validation gate metrics
- **06_energy_balance_comparison.png** - Adiabatic energy balance test
- **11_runtime_comparison.png** - Execution time breakdown
- **15_assignment_vs_overlap_mapping_qsum.png** - Mapping comparison (Q_sum_check)
- **19_zero_current_comparison_first5s.png** - Early transient (ECM off)
- **20_fixed_current_comparison_first5s.png** - Early transient (ECM on)

### Case Geometry & Mesh (3 figures)
- **40_mesh_partition_structure.png** - Lumped vs distributed mesh organization
- **26_overlap_case_allregions_longitudinal_300s.png** - Extended run (300s) longitudinal
- **27_overlap_case_allregions_cross_section_300s.png** - Extended run (300s) cross-section

### Protocol & Performance (5 figures)
- **50_binary_protocol_diagram.png** - Binary I/O v2 protocol specification
- **30_heat_generation_timeseries.png** - Heat generation vs time
- **60_mesh_convergence_analysis.png** - Mesh refinement convergence
- **70_coupling_modes_comparison.png** - Lumped vs ElementWise vs Binary vs JSON
- **80_performance_profiles.png** - Performance benchmarks & scaling

---

## 🎯 ORGANIZATION BY REPORT SECTION

### Section 1: Executive Summary
Use: 01, 03, 20, 21

### Section 2: Architecture Overview
Use: 01, 02, 12, 40

### Section 3: C++ Coupling Core
Use: 02, 70, 50

### Section 4: Python Backend & Protocol
Use: 50, 13, 14, 16-18

### Section 5: Case Setups
Use: 40, 26, 27, 04, 05

### Section 6: Validation Results
Use: 20, 21, 03, 06, 19, 20, 09, 10, 24, 25

### Section 7: Thermal Transients
Use: 07, 08, 22, 23, 09, 10, 24, 25

### Section 8: Performance Analysis
Use: 11, 15, 30, 60, 70, 80

### Section 9: Lessons Learned
Use: 26, 27, 28, 29, 31

---

## 📈 TECHNICAL HIGHLIGHTS

**Temperature Slices:**
- Multiple z-heights shown (10s and 30s timepoints)
- Both longitudinal and radial cross-sections
- All 3 solid regions visible (jellyRoll, shell, cap)
- Color scale normalized across cases

**Heat Distribution:**
- ECM zone-level heat allocation
- Cell-scale heat application
- Weight distribution from mapping table
- Zone volume fractions

**Validation:**
- Zero-current baseline (ECM off) matches solver-only
- Fixed-current response follows ECM model
- Energy balance verified (adiabatic test)
- Mesh independence demonstrated

**Performance:**
- Execution time breakdown
- Mapping comparison (assignment vs overlap)
- Scaling analysis
- Mode comparison (CPU cost vs fidelity)

---

## ✨ KEY INSIGHTS CAPTURED

✓ Temperature evolution from 10s to 300s
✓ Heat generation spatial distribution
✓ ECM partition architecture (18 zones)
✓ Mapping weight fields (overlap vs assignment)
✓ Validation test results (10/10 pass)
✓ Performance characteristics (11% overhead)
✓ Binary I/O efficiency (23× vs JSON)

---

## 📋 USAGE FOR INTERNAL DOCUMENTATION

1. **Total visual assets:** ~40 figures
2. **Organization:** 9 categorical directories
3. **Ready for:** Direct embedding in Markdown/PDF report
4. **High resolution:** All @ 300 DPI minimum
5. **Format:** PNG (web-ready, PDF-compatible)

All figures are curated from validated project outputs and ready for comprehensive internal documentation.

---

**Generated:** 2026-03-28
**Source:** `/workspace/artifacts/plots/report_image_set_20260328/`
**Destination:** `/workspace/artifacts/plots/internal_documentation_figures_curated/`
