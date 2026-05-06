# Internal Documentation Figures - Complete Index

**Generated:** 2026-03-28  
**Total Figures:** 11 visualizations  
**Location:** `/workspace/artifacts/plots/internal_documentation_figures/`

---

## ARCHITECTURE & DESIGN (Figures 1-2)

### **01_architecture_diagram.png**
- **Purpose:** System-level architecture overview
- **Content:** 
  - OpenFOAM solver, ecmCoupler function object, binary I/O, ECM backend
  - Data flow: T_mesh → ECM → qVol
  - Coupling modes, parallel strategy, I/O protocol details
- **Audience:** Technical leads, new developers
- **Use in report:** Section 2.3 (Architecture Overview)

### **02_coupling_sequence_diagram.png**
- **Purpose:** Detailed timestep sequence
- **Content:**
  - 12-step coupling loop with actor lifelines
  - Energy equation → executeControl → gather → I/O → ECM → map → apply
  - Shows atomic write semantics and transactional stepId tracking
- **Audience:** C++ developers, integrators
- **Use in report:** Section 3 (C++ Coupling Core)

---

## MESH & PARTITIONING (Figures 3-4)

### **40_mesh_partition_structure.png**
- **Purpose:** Mesh organization and ECM partition layout
- **Content:**
  - Left: Lumped case regions (jellyRoll, shell, cap) with cell counts
  - Right: Distributed ECM partitions (6 axial × 3 radial = 18 regions)
  - Highlights how mesh cells map to ECM partitions
- **Audience:** Domain modelers, validation engineers
- **Use in report:** Section 4 (Case Geometries & Setups)

---

## PROTOCOL & DATA (Figure 5)

### **50_binary_protocol_diagram.png**
- **Purpose:** Binary I/O protocol specification (v2)
- **Content:**
  - 52-byte header: magic, fileType, version, nRecords, time, dt, keyMode, stepId
  - Variable-length data records: (int32 key, float64 value)
  - Protocol guarantees: atomic writes, stepId tracking, endianness notes
- **Audience:** Backend implementers, protocol integrators
- **Use in report:** Section 5 (Python Backend & I/O Protocol)

---

## VALIDATION RESULTS (Figures 6-7)

### **20_validation_campaign_results.png**
- **Purpose:** High-level validation campaign pass/fail summary
- **Content:**
  - Lumped case: 5 forward tests (all PASS)
  - Distributed case: 5 forward tests (all PASS)
  - Visual checkmark indicators
- **Audience:** Stakeholders, project managers
- **Use in report:** Section 6 (Validation Results) - Summary view

### **21_detailed_validation_metrics.png**
- **Purpose:** Comprehensive validation metrics and statistics
- **Content:**
  - Test results with detailed breakdown
  - Q_sum_check time series (when data available)
  - Summary statistics: adiabatic energy RMSE, interface temps, equivalence metrics
  - Cell counts, mesh sizes, computation overhead
- **Audience:** Technical leads, validators
- **Use in report:** Section 6 (Validation Results) - Detailed analysis

---

## PERFORMANCE & SCALING (Figures 8-10)

### **30_heat_generation_timeseries.png**
- **Purpose:** Temporal evolution of heat generation
- **Content:**
  - Lumped case: Q_sum_check over ~30s with uncertainty band
  - Distributed case: Q_sum_check over 300s with uncertainty band
  - Shows coupling stability and ECM responsiveness
- **Audience:** Validation engineers, CFD analysts
- **Use in report:** Section 6 (Validation Results) - Thermal transient

### **60_mesh_convergence_analysis.png**
- **Purpose:** Mesh refinement convergence study
- **Content:**
  - Left: Cell counts for coarse (2mm), base (1mm), fine (0.5mm) meshes
  - Right: Temperature convergence at t=5.9s (ΔT = 0.005 K = converged)
  - Demonstrates numerical stability and mesh independence
- **Audience:** CFD analysts, method validation
- **Use in report:** Section 6 (Validation Results) - Mesh convergence

### **70_coupling_modes_comparison.png**
- **Purpose:** Characteristics of different coupling modes
- **Content:**
  - Four modes: Lumped, ElementWise, Binary Pipe, JSON Wrapper
  - Comparison metrics: ECM calls, cells/call, I/O overhead, computation cost
  - Use cases for each mode
- **Audience:** Users selecting coupling strategy
- **Use in report:** Section 3 (C++ Coupling Modes)

### **80_performance_profiles.png**
- **Purpose:** Detailed performance benchmarks
- **Content:**
  - I/O latency comparison (Binary direct 5.2ms vs JSON wrapper 120ms)
  - Scaling: ECM cost vs mesh cell count (linear O(N))
  - Cumulative wall-time for 300s simulation runs
  - Overhead percentage relative to solver-only baseline
- **Audience:** Performance engineers, resource planners
- **Use in report:** Section 7 (Performance Profiles)

---

## SUMMARY TABLE

| # | Figure | Type | Size | Key Insight |
|---|--------|------|------|-------------|
| 01 | Architecture Diagram | System Design | Full-page | Complete system overview |
| 02 | Coupling Sequence | Detailed Flow | Full-page | Step-by-step timestep loop |
| 03 | Mesh Partition Structure | Domain Setup | Two-panel | Lumped vs distributed organization |
| 04 | Binary Protocol | Data Format | Full-page | Wire format specification |
| 05 | Validation Summary | Results | Two-panel | High-level pass/fail (10/10) |
| 06 | Detailed Validation | Results | Multi-panel | Deep metrics + time series |
| 07 | Heat Generation | Transient | Two-panel | Temporal stability |
| 08 | Mesh Convergence | Convergence | Two-panel | ΔT = 0.005 K at t=5.9s |
| 09 | Coupling Modes | Comparison | Four-panel | Mode selection guide |
| 10 | Performance Profiles | Benchmarks | Four-panel | Detailed wall-time analysis |

---

## USAGE NOTES

### For Internal Documentation Report
1. **Section 2 (Architecture):** Use 01, 02, 04
2. **Section 3 (C++ Core):** Use 02, 09
3. **Section 4 (Cases):** Use 03
4. **Section 6 (Validation):** Use 05, 06, 07, 08
5. **Section 7 (Performance):** Use 10
6. **Appendix (Coupling Modes):** Use 09

### For Client-Facing Document
- **Recommend:** 01, 05, 07, 08, 10 (focus on results & performance)
- **Conditional:** 02 (if explaining architecture detail)
- **Skip:** 04 (too technical for non-specialists)

### High-Resolution Output
- All figures generated at **300 DPI**
- PNG format for document embedding
- Dimensions: typically 1200-1400 × 800-1000 px
- File sizes: 50-200 KB (suitable for PDF embedding)

---

## NEXT STEPS

1. **Review all figures** for technical accuracy and completeness
2. **Identify any missing visualizations** (e.g., temperature field slices, mapping weights)
3. **Request modifications** to specific figures (colors, layout, annotations)
4. **Approve finalized set** for inclusion in full internal documentation report

