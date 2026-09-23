# ECM Equivalence Master Requirement Matrix

**Date:** 2026-09-23
**Branch:** claude/openfoam-star-equivalence-2026-09-17
**Authority:** `cases/wedge_2170` raw polyMesh/boundary/T files outrank all narrative summaries. Machine-readable form: `data/equivalence/openfoam_thermal_operator.json`.
**Status vocabulary:** SATISFIED | PARTIAL | OPEN | CONTRADICTED | NOT TESTED | SUPERSEDED

Columns: `ID | Requirement | Auth source | OF/reference target | Current TBM/STAR state | Evidence | Status | Operator consequence if unmet | Resolution path | Required test | Dependency`

---

## GEO — Geometry / Dimensions

### Radial

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| GEO-001 | JR OD = 20.6274 mm | `jellyRoll_rotated/polyMesh/points` | 20.6274 mm (radius 10.31368 mm) | T06: 17.881 mm | STEP audit | OPEN | Wrong JR thermal mass; wrong radial contact geometry | RAD-C confirms RMAP-1; RAD-D sets target OD | RAD-C, RAD-D1 | — |
| GEO-002 | Can ID = 20.6274 mm (= JR OD) | `shell_rotated/polyMesh/points` | 20.6274 mm | T06: 18.0 mm | STEP audit | OPEN | Radial gap exists; affects contact topology | RAD-A identifies operative Can-ID field | RAD-A | — |
| GEO-003 | Can OD = 21.09 mm | `shell_rotated/polyMesh/points` | 21.09 mm | T06: 20.9 mm | STEP audit | OPEN | Wrong outer BC area (~1%); wrong Can wall thickness | RAD-B confirms RMAP-2 | RAD-B | — |
| GEO-004 | Can radial wall thickness = 0.23132 mm | Derived from GEO-001/003 | 0.23132 mm | T06: 1.45 mm | STEP audit | OPEN | Wrong Can thermal mass | Resolves with GEO-001 + GEO-003 | RAD-D1 | GEO-001, GEO-002, GEO-003 |
| GEO-005 | JR is a full solid cylinder to axis (no central void) | `polyMesh/points`; json domains.JellyRoll | Solid cylinder r=0..10.31368 mm | T06: annular JR + 3 mm Mandrel | STEP audit | OPEN | Wrong JR thermal mass in central zone; correct heat-source coverage requires full volume | STAR-002/STAR-003 (Mandrel mapped to JR); or Mandrel removal via TBM field | S0-A, S0-B, S0-C | STAR-001 |
| GEO-006 | Integral Can bottom disc, thickness = 0.23132 mm | `shell_rotated/polyMesh/points`; json shape | Solid disc r=0..10.545, z=0..0.23132 mm | T06: no Can bottom disc; annular tube only | STEP audit | OPEN | No direct JR-bottom-to-Can-bottom heat path; bottom interface area wrong | TBM bottom-disc geometry or STAR Option D equivalent | S0-B, S0-D; GEO-AX tests | GEO-002 |
| GEO-007 | JR↔Can radial gap = 0 (coincident surfaces) | OF mesh; `OPENFOAM_ECM_EQUIVALENCE_TARGET.md` | Gap = 0; JR OD = Can ID | T06: 0.059504 mm gap | STEP audit | OPEN | Radial contact area reduced or absent; wrong interface operator | RAD-D2 (geometry route after GEO-001/002); or S0-B STAR gap-bridging route | RAD-D2, S0-B | GEO-001, GEO-002 |

### Axial

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| GEO-008 | JR height = 65.11 mm | `jellyRoll_rotated/polyMesh/points` | 65.11 mm | T06: 65.11 mm | STEP audit | **SATISFIED** | — | — | — | — |
| GEO-009 | JR axial z-range = 0.23132..65.34130 mm in cell frame | `polyMesh/points` bounding box | z_bot=0.23132 mm, z_top=65.3413 mm | T06: z=0..65.11 mm (symmetric, no Can bottom offset) | STEP audit | OPEN | JR bottom face not at z=0.23132 mm; bottom contact geometry differs | Axial envelope correction; resolves with Can-bottom disc (GEO-006) | GEO/AX axial test | GEO-006 |
| GEO-010 | Can axial z-range = 0..65.34130 mm | `shell_rotated/polyMesh/points` | z=0 (bottom outer face) to z=65.3413 mm | T06: -2.445..67.555 mm (symmetric overhang) | STEP audit | OPEN | Symmetric Can overhang drives mirrored end stacks; wrong axial placement | Axial envelope TBM field identification | GEO/AX axial test | — |
| GEO-011 | Top Cap height = 4.6787 mm | `cap_rotated/polyMesh/points` | 4.6787 mm | T06 EndPlate: 0.059504 mm (26.5 mm axially above JR) | STEP audit | OPEN | Effective top thermal resistance wrong; Cap thermal mass wrong | STAR material mapping to top stack (B route) or Cap-equivalent geometry (A route) | S0-C; or TBM Cap geometry | S0-C |
| GEO-012 | Cap z-range = 65.34130..70.02 mm | `cap_rotated/polyMesh/points` | 65.3413..70.02 mm | T06: EndPlate at 67.495..67.555 mm | STEP audit | OPEN | Top thermal path length differs | S0-C material mapping or geometry | S0-C | GEO-010 |
| GEO-013 | Can radial wall top flush with JR top (z=65.3413 mm); no Can overhang above JR | `shell_rotated` region stops at Cap; OF mesh | Can top = z=65.3413 mm | T06: Can top = 67.555 mm (2.445 mm above JR) | STEP audit | OPEN | Drives 5-body top end-stack structure | Axial envelope field identification | GEO/AX test | — |
| GEO-014 | Can bottom outer face at z=0; JR bottom face at z=0.23132 mm (Can bottom disc below JR) | OF mesh geometry | z_JR_bot = 0.23132 mm | T06: z_JR_bot = 0 mm; Can bottom = -2.445 mm | STEP audit | OPEN | Bottom contact interface position wrong | Can-bottom disc; axial placement field | GEO-AX test | GEO-006 |

### Negative Requirements (what must NOT exist)

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| GEO-015 | No Mandrel domain in thermal model | OF `regionProperties` | 3 regions; no Mandrel | T06: Mandrel is 13th BDS body → STAR Region | `regionProperties`; STEP | OPEN | Mandrel adds wrong central topology unless mapped to JR | S0-C maps Mandrel to JR props; or TBM Mandrel suppression | S0-B, S0-C | STAR-001 |
| GEO-016 | No bottom Cap domain | OF mesh | No bottom-cap region | T06: −EndPlate is Cap-OD disc 2.39 mm below JR bottom | STEP | OPEN | Bottom-cap body adds wrong thermal mass below cell | S0-D bottom-stack suppression; or TBM topology change | S0-D | — |
| GEO-017 | No free axial void/gap layer between JR and any solid domain | OF mesh; zero gaps | Zero gaps at all 4 interfaces | T06: void space above/below JR (2.445 mm each end) | STEP | OPEN | Free void would require STAR to model air gap; adds wrong thermal resistance | End-stack mapping (Option D) or geometry fix | S0-B; GEO-AX | GEO-006, GEO-013 |
| GEO-018 | No EndPlate domain in thermal model | OF mesh | No EndPlate | T06: ±EndPlate in STAR as separate Regions | STEP | OPEN | EndPlate provides wrong thermal path unless mapped | S0-C maps EndPlate to Cap material | S0-C | STAR-001 |
| GEO-019 | No Washer / Internal-Post / Tab Root / Tab Stem auxiliary bodies in thermal model | OF mesh | None | T06: all 8 of these in STAR | STEP | OPEN | Each body adds wrong thermal path unless mapped or suppressed | S0-C/D for each body | S0-C, S0-D | STAR-001 |
| GEO-020 | No Can/EndPlate volumetric overlap | OF mesh (planar annulus, zero overlap) | Zero overlap | T06: 5.272 mm³ per end overlap | STEP B-Rep | OPEN | Overlap creates ambiguous thermal volume for Can/EndPlate | S0-A resolves whether STAR clips it | S0-A | — |
| GEO-021 | No symmetric top/bottom end-stack (top-only Cap in OF) | OF mesh | Top-only; no bottom cap equiv | T06: mirror-symmetric ±stacks | STEP | OPEN | Bottom stack has no OF domain target; adds spurious thermal mass | Option D suppression or geometry change | S0-D | — |

### Volumes

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| GEO-022 | JR thermal volume = 2.17583×10⁻⁵ m³ | `openfoam_thermal_operator.json` | 2.17583×10⁻⁵ m³ | T06 JR+Mandrel combined: ~2.513×10⁻⁵ m³ (wrong OD/ID) | STEP + json | OPEN | Wrong total JR thermal mass; wrong heat-source volumetric density | Resolves when GEO-001 and GEO-005 met | RAD-D1/D2 | GEO-001, GEO-005 |
| GEO-023 | Can thermal volume = 1.06776×10⁻⁶ m³ | `openfoam_thermal_operator.json` | 1.06776×10⁻⁶ m³ | T06 Can: ~6.202×10⁻³ m³ (wrong radial/axial dimensions) | STEP + json | OPEN | Wrong Can thermal mass | Resolves when GEO-002, GEO-003, GEO-006, GEO-010 met | RAD-D1 + GEO-AX | GEO-002,003,006,010 |
| GEO-024 | Cap thermal volume = 1.63444×10⁻⁶ m³ | `openfoam_thermal_operator.json` | 1.63444×10⁻⁶ m³ | T06 top stack: far from target | STEP + json | OPEN | Wrong Cap thermal mass | Resolves with geometry or material-mapping solution | Test A | GEO-011 |

---

## TOP — Contact Topology

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| TOP-001 | JR↔Can radial: coincident cylindrical surface at r=10.31368 mm, z=0.23132..65.3413 mm | `OPENFOAM_GEOMETRY_TOPOLOGY_TARGET.md`; mesh area | Coincident, zero gap | T06: 0.059504 mm gap; different radii | STEP; OF mesh | OPEN | Radial coupling path absent or wrong area | GEO-001/002/007; S0-B | RAD-D2; S0-B | GEO-001,002,007 |
| TOP-002 | JR↔Can radial interface area = 4.214×10⁻³ m² (mesh: 4.21395×10⁻³ m²) | Raw mesh face integration | 4.21395×10⁻³ m² | Not yet established; depends on GEO-001/007/009 | Mesh area from target | OPEN | Wrong conductive coupling area | GEO-001, GEO-007, GEO-009 | RAD-D1/D2 | GEO-001,007,009 |
| TOP-003 | JR↔Can bottom: coincident planar disc at z=0.23132 mm, r=0..10.31368 mm | OF mesh; area = 3.325×10⁻⁴ m² | Full-disc area 3.325×10⁻⁴ m² | T06: no Can bottom disc; only −Tab Root touches JR bottom (localized) | STEP audit | OPEN | Bottom contact area wrong/absent; bottom resistance layer not reproducible | GEO-006 (Can bottom disc); or S0-B/D Option D | S0-B, S0-D; GEO-AX | GEO-006, GEO-014 |
| TOP-004 | JR↔Can bottom interface area = 3.325×10⁻⁴ m² | Raw mesh face integration | 3.325×10⁻⁴ m² (= JR cross-section) | Not established | Mesh area | OPEN | Bottom resistance layer effect wrong if area incorrect | Resolves with TOP-003 | GEO-AX test | TOP-003 |
| TOP-005 | JR↔Cap top: coincident planar disc at z=65.3413 mm, r=0..10.31368 mm | OF mesh | Full-disc area 3.325×10⁻⁴ m² | T06: +Tab Root touches JR (localized, zero B-Rep common-face area) | STEP audit | OPEN | Top heat path from JR to Cap-zone bottlenecked at Root contact area | S0-B Root-JR interface area; or full-disc geometry | S0-B | GEO-013 |
| TOP-006 | JR↔Cap top interface area = 3.325×10⁻⁴ m² | Raw mesh face integration | 3.325×10⁻⁴ m² | Not established | Mesh area | OPEN | Effective JR→Cap thermal conductance wrong | S0-B quantitative area; or geometry fix | S0-B | TOP-005 |
| TOP-007 | Can↔Cap: planar annulus at z=65.3413 mm, r=10.31368..10.545 mm | OF mesh patches (confirmed planar) | Planar annulus, area 1.508×10⁻⁵ m² | T06: EndPlate overlaps Can; planar annulus not reproduced | STEP; `OPENFOAM_GEOMETRY_TOPOLOGY_TARGET.md` | OPEN | Can→Cap conduction path structurally different | S0-C maps EndPlate/Can to correct materials; overlap resolved by S0-A | S0-A, S0-C | GEO-003,010,020 |
| TOP-008 | Can↔Cap interface area = 1.508×10⁻⁵ m² | Raw mesh face integration | 1.508×10⁻⁵ m² | Not established | Mesh area | NOT TESTED | Cap annulus conduction affected if area wrong | Resolves with geometry or S0-A/C mapping | S0-A/C | TOP-007 |
| TOP-009 | All 4 interfaces have zero geometric gap (coincident faces) | OF mesh | Zero gap at all interfaces | T06: 0.059504 mm JR-Can radial gap; missing bottom disc; localized Root contacts | STEP | OPEN | Any gap → either missing interface in STAR or wrong contact resistance | GEO-001/002/006/007 resolution; S0-B | RAD-D2; S0-B | GEO-001,002,006,007 |
| TOP-010 | Exactly 3 thermal regions: jellyRoll_rotated, shell_rotated, cap_rotated | `regionProperties` | 3 regions | T06: STAR creates 13 Regions | Test plan confirmed | OPEN | 13-Region model must reduce to 3-zone thermal operator via mapping | Full material/interface mapping; S0-C/D | Test A | STAR-001 |
| TOP-011 | No Mandrel thermal region in operative model | `regionProperties` | No Mandrel | T06: Mandrel is STAR Region | STEP/confirmed | OPEN | Mandrel must be mapped to JR or suppressed | S0-C maps Mandrel to JR; or remove from TBM | S0-B, S0-C | GEO-005, GEO-015 |
| TOP-012 | No bottom-Cap equivalent thermal region | OF mesh | No bottom domain | T06: −EndPlate + stack at bottom | STEP | OPEN | Must be suppressed or mapped to zero thermal mass | S0-D bottom suppression | S0-D | GEO-016, GEO-021 |
| TOP-013 | JR top contact is full-disc (not localized) | OF mesh; area = TOP-006 | Full-disc 3.325×10⁻⁴ m² | T06: only Root touches JR (localized, zero common-face area in STEP) | STEP B-Rep | OPEN | Top thermal coupling bottlenecked if contact area << full disc | S0-B quantitative check; or geometry fix | S0-B | TOP-005 |
| TOP-014 | JR bottom contact is full-disc (not localized) | OF mesh; area = TOP-004 | Full-disc 3.325×10⁻⁴ m² | T06: only Root touches JR bottom (localized, symmetric to top) | STEP B-Rep | OPEN | Bottom contact resistance cannot be reproduced correctly if area wrong | S0-B quantitative check; or Can-bottom disc geometry | S0-B | TOP-003 |
| TOP-015 | Can↔Cap interface is a planar annulus (not axial cylindrical band) | Raw mesh patch coordinates; `OPENFOAM_GEOMETRY_TOPOLOGY_TARGET.md` | Planar annulus confirmed | T06: not reproduced (EndPlate structure is different) | Raw mesh data; corrected description | OPEN | Wrong Can↔Cap coupling geometry | S0-A/C mapping | S0-A | GEO-003,010 |

---

## MAT — Material Properties

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| MAT-001 | JR ρ = 2660.7 kg/m³ | `thermophysicalProperties`; json | 2660.7 kg/m³ | In TBM design (BDS_TO_OPENFOAM mapping: YES) | Thermal operator inventory | PARTIAL | Wrong JR thermal mass timescale | Verify STAR assigns this when JR Region selected | Test A | — |
| MAT-002 | JR Cp tabulated: (250K,835.55), (500K,1585.55) J/kgK; linear ≈980+3·(T−298K) | `thermophysicalProperties`; json | Piecewise-linear Cp(T) | In TBM design | Thermal operator inventory | PARTIAL | Wrong JR thermal mass vs T; wrong transient T-rise | Verify STAR table assignment | Test A | — |
| MAT-003 | JR kr = 1.4 W/mK (radial conductivity) | `thermophysicalProperties`; json | 1.4 W/mK | In TBM design | Thermal operator inventory | PARTIAL | Wrong radial JR heat spreading | Verify STAR anisotropic assignment | Test A | MAT-006 |
| MAT-004 | JR kθ = 1.4 W/mK (azimuthal conductivity) | `thermophysicalProperties`; json | 1.4 W/mK | In TBM design | Thermal operator inventory | PARTIAL | Wrong azimuthal JR heat spreading | Verify STAR anisotropic assignment | Test A | MAT-006 |
| MAT-005 | JR kz = 29 W/mK (axial conductivity) | `thermophysicalProperties`; json | 29 W/mK | In TBM design | Thermal operator inventory | PARTIAL | Wrong axial JR heat spreading (dominant path) | Verify STAR anisotropic assignment | Test A | MAT-006 |
| MAT-006 | JR k tensor is anisotropic cylindrical (r,θ,z), NOT isotropic | `tabulatedAnIso`; cylindrical coordinateSystem | Anisotropic cylindrical | Must be assigned in STAR physics continuum | Thermal operator inventory | NOT TESTED | Isotropic assignment would incorrectly equate kr=kz; wrong temperature distribution | Verify STAR permits cylindrical anisotropic k for JR Region | Test A (material check) | — |
| MAT-007 | Can ρ = 8000 kg/m³ | `thermophysicalProperties`; json | 8000 kg/m³ | BDS_TO_OPENFOAM mapping: −Tab Root mapped to Can props | Thermal operator inventory | PARTIAL | Wrong Can thermal mass | Verify in Test A | Test A | — |
| MAT-008 | Can Cp = 500 J/kgK (constant) | `thermophysicalProperties`; json | 500 J/kgK | In TBM design intent | Thermal operator inventory | PARTIAL | Wrong Can thermal capacitance | Verify in Test A | Test A | — |
| MAT-009 | Can k = 16 W/mK (isotropic) | `thermophysicalProperties`; json | 16 W/mK isotropic | In TBM design intent | Thermal operator inventory | PARTIAL | Wrong Can conduction | Verify in Test A | Test A | — |
| MAT-010 | Cap ρ = 1447.2 kg/m³ | `thermophysicalProperties`; json | 1447.2 kg/m³ | Top-stack bodies mapped to Cap props | Thermal operator inventory | PARTIAL | Wrong Cap thermal mass | Verify in Test A | Test A | — |
| MAT-011 | Cap Cp = 500 J/kgK (constant) | `thermophysicalProperties`; json | 500 J/kgK | In TBM design intent | Thermal operator inventory | PARTIAL | Wrong Cap capacitance | Verify in Test A | Test A | — |
| MAT-012 | Cap k: kr=0.01, kθ=0.01, kz=0.1 W/mK (anisotropic cylindrical) | `thermophysicalProperties`; json | (0.01,0.01,0.1) cylindrical | Must be assigned for top-stack bodies; anisotropic | Thermal operator inventory | NOT TESTED | Isotropic or wrong tensor → wrong cap heat spreading | Verify STAR anisotropic assignment for top-stack Regions | Test A | MAT-006 |
| MAT-013 | No Mandrel material separate from JR in operative model | OF mesh (no Mandrel region) | No separate Mandrel | T06: Mandrel has own Region | STEP/confirmed | OPEN | Mandrel must get JR material; separate material would give wrong central heat capacity | S0-C | S0-C | GEO-015 |
| MAT-014 | No EndPlate/Tab/Washer/Post native BDS material in operative thermal model | OF mesh | No such materials | T06: all 8 bodies have BDS default materials | STAR import default | OPEN | BDS metallic conductivities would create wrong thermal shortcuts | S0-C/D remapping | S0-C, S0-D | GEO-018, GEO-019 |

---

## IFC — Interface Conditions

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| IFC-001 | JR↔Can radial: ideal contact (zero resistance) | `0/*/T` boundary files; json | No thicknessLayers/kappaLayers → zero resistance | T06: 0.059504 mm physical gap; STAR interface capability unknown | OF confirmed; STAR not run | OPEN | Radial thermal resistance non-zero if gap not bridged | S0-B (gap-bridging STAR interface); RAD-D2 (geometry route) | S0-B; RAD-D2 | TOP-001, GEO-007 |
| IFC-002 | JR↔Can bottom: explicit thin-layer resistance; R_specific = 6.015×10⁻⁷ m²K/W (thicknessLayers=6.015×10⁻⁷ m, kappaLayers=1) | `0/jellyRoll_rotated/T` bottom patch | 6.015×10⁻⁷ m²K/W specific resistance | No Can bottom contact exists in T06 | OF confirmed; STEP audit | OPEN | Bottom resistance layer absent or wrong; bottom T-differential wrong | Can-bottom disc (GEO-006) + S0-D explicit resistance | S0-D; GEO-AX test | TOP-003, GEO-006 |
| IFC-003 | JR↔Cap top: ideal contact (zero resistance) | `0/*/T` top patch | No resistance | T06: localized Root contact; full-disc ideal contact not established | OF confirmed; STAR not run | OPEN | Top thermal coupling limited by Root contact area | S0-B quantitative area; or geometry fix | S0-B; TOP-013 | TOP-005 |
| IFC-004 | Can↔Cap planar annulus: ideal contact (zero resistance) | `0/*/T` patches | No resistance | Not established in STAR | OF confirmed | NOT TESTED | Outer-rim Can↔Cap coupling absent | S0-C/A mapping | S0-A, Test A | TOP-007 |
| IFC-005 | No radiation on any internal interface (qr=none) | `0/*/T` boundary files | qr none on all coupled patches | Not tested in STAR | OF confirmed | NOT TESTED | Radiation would add nonphysical heat exchange between regions | Confirm in Test A setup | Test A | — |
| IFC-006 | Interface areas match TOP-002, TOP-004, TOP-006, TOP-008 | OF mesh face integration | Areas as specified in TOP rows | Not established | Mesh areas confirmed for OF | OPEN | Wrong areas → wrong thermal coupling coefficients | Resolves with geometry (GEO-001..007) | RAD-D1/D2; S0-B | GEO-001,002,006,007 |

---

## BC — External Boundary Conditions

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| BC-001 | Can outer wall: h = 160 W/m²K, T_amb = 298.15 K, convection mode | `0/shell_rotated/T`; json | h=160, T_amb=298.15 K | Must be set in STAR; not yet verified | OF confirmed; STAR not run | NOT TESTED | Wrong Can surface cooling → wrong T distribution | Set in STAR Test A; verify against OF | Test A | — |
| BC-002 | Cap outer surface: h = 160 W/m²K, T_amb = 298.15 K, convection mode | `0/cap_rotated/T`; json | h=160, T_amb=298.15 K | Must be set in STAR; not verified | OF confirmed; STAR not run | NOT TESTED | Wrong Cap surface cooling | Set in STAR Test A | Test A | — |
| BC-003 | No fixed-T BC on any external surface | OF case | No Dirichlet T at boundary | Not tested in STAR | OF confirmed | NOT TESTED | Fixed-T would incorrectly decouple outer surface T from thermal mass | Verify in Test A setup | Test A | — |
| BC-004 | No radiation BC on any external surface | OF case | No radiation BC | Not tested in STAR | OF confirmed | NOT TESTED | Radiation would add wrong heat-loss path | Verify in Test A setup | Test A | — |
| BC-005 | Identical h and T_amb on Can and Cap exposed surfaces | OF case | Both h=160, T_amb=298.15 K | Not tested | OF confirmed | NOT TESTED | Different BCs would change top/bottom asymmetry | Verify in Test A | Test A | — |

---

## SRC — Heat Source Mapping

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| SRC-001 | 100% of ECM heat deposited in JellyRoll only | `fvOptions/jellyRoll_rotated`; json | 100% JR | STAR battery model deposits heat in Core Parts; Core Parts = JR + Mandrel in T06 | OF confirmed; STAR not run | OPEN | Heat in Mandrel rather than full-JR volume if Mandrel separate from Core Parts | Map Mandrel to Core Parts or suppress separately | S0-C; Test A | GEO-005, GEO-015 |
| SRC-002 | Zero direct heat in Can | OF case (no Can fvOptions) | 0 W | No Can fvOptions in OF | OF confirmed | NOT TESTED | Direct Can heating would add spurious energy source | Verify STAR assigns no direct heat to Can Region | Test A | — |
| SRC-003 | Zero direct heat in Cap | OF case (no Cap fvOptions) | 0 W | No Cap fvOptions in OF | OF confirmed | NOT TESTED | Direct Cap heating spurious | Verify STAR assigns no direct heat to Cap-mapped Regions | Test A | — |
| SRC-004 | Spatially uniform heat deposition across all JR cells | `selectionMode all`; json | Uniform q(x)=Q_total/V_JR | STAR RCRTable 3D should give spatially varying q(x,t) coupled to local T | OF confirmed; distributed mode expected to vary | PARTIAL | OF uses lumped uniform deposition; STAR distributed mode varies spatially — intrinsic difference between lumped OF ECM and distributed STAR | Test A uses no-ECM fixed heat source for thermal baseline; Test D compares full coupled behavior | Test A (uniform source), Test D (coupled) | — |
| SRC-005 | No axial or radial sub-zoning of heat source within JR | `selectionMode all` | Single zone = all JR | STAR distributed mode inherently zones heat by local SOC/T | OF confirmed; STAR expected to differ | PARTIAL | Spatial heat distribution differs between OF lumped and STAR distributed — acceptable difference for Test D but must be documented | Document in Test D comparison | Test D | — |
| SRC-006 | Heat source drives enthalpy field h (not T directly) | OF `fvOptions ecmHeatSource` on `h` | Enthalpy source | STAR uses its own thermal energy solver | OF confirmed | NOT TESTED | Formulation difference should be equivalent; verify energy balance | Energy balance check in Test A | Test A | — |
| SRC-007 | V_JR for volumetric source = 2.17583×10⁻⁵ m³ (full 360° cylinder, totalVolumeScale=1) | OF `ecmCoupling`; json | 2.17583×10⁻⁵ m³ | Wrong until GEO-001/005 met | json confirmed; TBM OD wrong | OPEN | Wrong volumetric heat density if V_JR wrong | Resolves with GEO-001, GEO-005 | RAD-D1/D2 | GEO-001, GEO-005 |
| SRC-008 | f_cap = 0 in executable OF case (NOT f_cap = 0.034 per documentation) | `fvOptions` files (no Cap source); json `documented_vs_implemented_conflict` | 0% Cap heat | OF executable: 0% Cap. Some docs say 0.034 — CONTRADICTED | json unknown flag; `SOURCE_INVENTORY.md` discrepancy #1 | **CONTRADICTED** | STAR Test A must match the executable OF, not the documented fraction; using f_cap=0.034 in STAR would give wrong comparison | Resolve conflict by checking OF source code; use executable-confirmed 0% | Test A design (use 0% Cap heat) | — |

---

## IC — Initial Conditions

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| IC-001 | Initial temperature T_0 = 298.15 K uniform across all regions | `0/*/T` initial fields; json `initial_conditions` | 298.15 K uniform | Must be set in STAR; not verified | OF confirmed | NOT TESTED | Wrong T_0 shifts whole transient; wrong RCR temperature interpolation at t=0 | Set in STAR Test A/B/C/D and verify | Test A | — |

---

## ELEC — ECM / RCR Electrical Behaviour

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| ELEC-001 | IET = RCRTable 3D | NEXTSESSION protected parameters | RCRTable 3D | In T06 TBM; STAR not yet run | NEXTSESSION | PARTIAL | Lumped mode would not give distributed electrical response | Verify STAR runs with RCRTable 3D active | Test B | — |
| ELEC-002 | Thermal = Distributed | NEXTSESSION protected parameters | Distributed | In T06 TBM design | NEXTSESSION | PARTIAL | Non-distributed mode disables spatial thermal-electrical coupling | Verify in Test B/C | Test B | — |
| ELEC-003 | m_bOnly1D = 0 in all SIMMOD blocks | NEXTSESSION; TBM_HYPOTHESIS_LEDGER R004 | 0 | Confirmed set; R004 cleared warning | R004 result; NEXTSESSION | **SATISFIED** | 1D mode disables distributed operation | — | — | — |
| ELEC-004 | m_dAhCell = 5.0 Ah | NEXTSESSION protected | 5.0 Ah | In TBM; NEXTSESSION protected | NEXTSESSION | **SATISFIED** | Wrong capacity shifts SOC-normalized RCR response | — | — | — |
| ELEC-005 | m_nRCRParameterSets = 3 | NEXTSESSION protected | 3 sets | In TBM; NEXTSESSION protected | NEXTSESSION | **SATISFIED** | Fewer sets degrades T-interpolation | — | — | — |
| ELEC-006 | RCR tables from About-Energy characterization at 3 temperature levels | NEXTSESSION; About-Energy data | AE characterization data | In TBM design | NEXTSESSION | PARTIAL | Wrong RCR tables → wrong V(t)/SOC(t)/heat | Verify data embedded in TBM matches AE source | Test B/C | ELEC-005 |
| ELEC-007 | Initial SOC defined per test protocol | Test plan | To be specified per run | Not yet set for STAR | Test plan | NOT TESTED | Wrong SOC start shifts V(t) and heat | Set in Test B/C/D | Test B | — |
| ELEC-008 | Current/load history from electrical_inputs_from_validation.csv | OF case; test plan | time, current_A profile | File exists; not yet applied to STAR | OF confirmed | NOT TESTED | Wrong current → wrong heat profile | Apply to STAR Test C/D | Test C/D | — |
| ELEC-009 | Terminal voltage V(t) output | Test plan; OF reference | V(t) time series | Not yet produced by STAR | OF reference: ECM output exists | NOT TESTED | V(t) cannot be compared without STAR output | Test D | Test D | ELEC-001 |
| ELEC-010 | SOC(t) output | Test plan | SOC(t) time series | Not yet produced | OF reference available | NOT TESTED | SOC(t) cannot be compared | Test D | Test D | ELEC-001 |
| ELEC-011 | m_bLumpedEnergyBalance = 0 | NEXTSESSION protected | 0 | In TBM; NEXTSESSION protected | NEXTSESSION | **SATISFIED** | Lumped energy balance disables correct distributed thermal coupling | — | — | — |
| ELEC-012 | No external Python/OpenFOAM/FMU/Java-per-timestep ECM runtime in final STAR model | NEXTSESSION governing objective | Native STAR only | TBM design intent: native STAR battery model | NEXTSESSION | PARTIAL | External coupling would require infrastructure not deliverable as standalone STAR model | Verify Test B native battery run requires no external process | Test B | — |

---

## DIST — Distributed Electrical Semantics

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| DIST-001 | Local electrical state (SOC, polarization) must vary spatially within JR when temperature gradient exists | Test plan (Test C PASS criterion) | SOC(x,t) ≠ constant when T(x,t) spatially varying | Not yet demonstrated in STAR | Test plan | NOT TESTED | Lumped behavior would defeat the purpose of distributed RCR mode | Test C PASS criterion | Test C | ELEC-001, ELEC-002 |
| DIST-002 | Local heat deposition q(x,t) must differ at spatially separated JR points when T(x,t) differs | Test plan (Test C) | q(x_A,t) ≠ q(x_B,t) when T(x_A) ≠ T(x_B) | Not tested | Test plan | NOT TESTED | Spatially uniform heat regardless of T gradient → lumped behavior | Test C | Test C | DIST-001 |
| DIST-003 | Local current density responds to local RCR state | Test plan | Local J(x,t) governed by local SOC, polarization | Not tested | Test plan | NOT TESTED | Global current density ignores local state → wrong spatial heat pattern | Test C | Test C | DIST-001 |
| DIST-004 | RCR response at a spatial point governed by local T (not global mean T) | Test plan | RCR(x,t) = f(T_local(x,t)) | Not tested | Test plan | NOT TESTED | Global-T interpolation would give same RCR everywhere | Test C | Test C | DIST-001, ELEC-006 |
| DIST-005 | Simultaneous T_A ≠ T_B at two probes implies electrical_state_A(t) ≠ electrical_state_B(t) | Test plan (Test C formal PASS criterion) | Demonstrated at ≥ 2 probes with ~20 K gradient | Not tested | Test plan | NOT TESTED | Required to prove distributed semantics are operative | Test C | Test C | DIST-001..004 |

---

## STAR — STAR-CCM+ Capability Requirements

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| STAR-001 | STAR `Create from Tbm` creates one Region per BDS body → 13 Regions from T06 | `STAR_CLIENT_EQUIVALENCE_TEST_PLAN.md` | 13 Regions | Confirmed from prior STAR import experience | Test plan confirmed | **SATISFIED** | — | — | — | — |
| STAR-002 | Mandrel Region thermal material independently assignable (not locked to electrical model) | Test plan S0-C | Must accept JR material | Unknown | Not tested | NOT TESTED | If Mandrel material cannot be changed → Mandrel must be geometrically removed | S0-C | S0-C | STAR-001 |
| STAR-003 | STAR builds Mandrel↔JR thermal interface (cylindrical face contact) | Test plan S0-B | Interface exists with settable coupling | Unknown | Not tested | NOT TESTED | No interface → no thermal coupling between Mandrel and JR | S0-B | S0-B | STAR-001 |
| STAR-004 | JR Region (Core Part) thermal material assignable to anisotropic cylindrical properties | Test plan S0-C | Accept JR material with (1.4,1.4,29) cylindrical k | STAR standard battery physics — likely; not confirmed | Not tested | NOT TESTED | Must confirm STAR supports cylindrical anisotropic k on Core Part | S0-C; Test A setup | Test A | — |
| STAR-005 | Top-stack Regions (+Ve Tab Root/Stem/Washer/Post/EndPlate) retain electrical +Tab role while assigned Cap thermal material | Test plan S0-C | Electrical role preserved + thermal material changed | Unknown — core S0-C question | Not tested | NOT TESTED | If electrical role reverts on thermal change → cannot map top stack to Cap material while preserving battery model | S0-C | S0-C | STAR-001 |
| STAR-006 | Bottom-stack Regions (−Ve Tab Stem/Washer/Post/EndPlate) thermal path suppressible while electrical −Tab role preserved | Test plan S0-D | Thermal path suppressed; electrical role intact | Unknown — core S0-D question | Not tested | NOT TESTED | If suppression invalidates electrical model → Option D fails; geometry change required | S0-D | S0-D | STAR-001 |
| STAR-007 | STAR builds Can↔Jellyroll thermal interface despite 0.059504 mm radial gap | Test plan S0-B item 1 | Interface exists and coupling settable | Unknown — depends on STAR gap tolerance threshold | Not tested | NOT TESTED | If no interface → radial coupling absent unless gap closed via TBM geometry | S0-B | S0-B | GEO-007 |
| STAR-008 | STAR resolves Can body overlap with JR-occupied space (clips or preserves) | Test plan S0-A | Resolution mode determines whether 3-way Can piecewise split is needed | Unknown | Not tested | NOT TESTED | If STAR preserves overlap → 3-way piecewise split required (untested capability); if clips → sub-volume mapping possible | S0-A | S0-A | GEO-020 |
| STAR-009 | STAR resolves Can↔EndPlate volumetric overlap (5.272 mm³ per end) | Test plan S0-A | Clip or preserve; determines EndPlate thermal volume in STAR | Unknown | Not tested | NOT TESTED | If preserved, EndPlate thermal volume includes Can overlap; if clipped, volumes change | S0-A | S0-A | GEO-020 |
| STAR-010 | +Tab Root ↔ Jellyroll interface: STAR-assigned area | Test plan S0-B | Need quantitative area (not just existence) to assess equivalence with full-disc OF interface | Unknown; STEP common-face area = 0 | STEP B-Rep | NOT TESTED | If area << 3.325×10⁻⁴ m² → top coupling cannot be full-disc equivalent | S0-B (must request area, not just existence) | S0-B | STAR-001 |
| STAR-011 | −Tab Root ↔ Jellyroll interface: STAR-assigned area | Test plan S0-B | Need quantitative area | Unknown; symmetric to STAR-010 | STEP B-Rep | NOT TESTED | Same as STAR-010 for bottom | S0-B (area request) | S0-B | STAR-001 |
| STAR-012 | STAR supports piecewise (3-way) material assignment within one CAD body (Can body) | Test plan Test A | 3 material zones: JR-equivalent, Can-equivalent, bottom-undefined | Unknown; not standard STAR workflow | Not tested | NOT TESTED | If not supported → hard STOP on Test A (per test plan); cannot average | Test A / S0-A (if S0-A shows sub-volumes) | Test A | S0-A |
| STAR-013 | Explicit interface thermal resistance settable on a specific internal face | Test plan S0-D | R_specific = 6.015×10⁻⁷ m²K/W at Can-JR bottom | Unknown | Not tested | NOT TESTED | Cannot reproduce OF bottom resistance layer | S0-D | S0-D | TOP-003 |
| STAR-014 | Core Part electrical assignment remains valid while non-default thermal conductivity is assigned | Test plan S0-C | Electrical Core Part + Cap-equivalent thermal material coexist | Unknown | Not tested | NOT TESTED | If STAR couples electrical role to thermal material type → material mapping fails | S0-C | S0-C | ELEC-001 |

---

## VAL — Validation Observables

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| VAL-001 | Terminal voltage V(t) — full transient time series | OF ECM output; Test D | V(t) from `electrical_inputs_from_validation.csv` run | Not produced by STAR | OF ECM exists | NOT TESTED | Cannot validate electrical equivalence | Test D | Test D | ELEC-001,008 |
| VAL-002 | SOC(t) — full transient time series | OF ECM output; Test D | SOC(t) | Not produced by STAR | OF ECM exists | NOT TESTED | Cannot validate SOC tracking | Test D | Test D | ELEC-001,007 |
| VAL-003 | Total ECM heat Qdot(t) — time history | OF `ecmQdot` function output; Test A/D | Q_total(t) time series | Not produced by STAR | OF file exists | NOT TESTED | Cannot check energy balance | Test A/D | Test A | SRC-001 |
| VAL-004 | JR mean temperature T_JR_mean(t) | OF postProcessing; `wedge_2170_thermal_qualification` | T_JR_mean(t) CSV | Not produced; OF reference at `reference_thermal_transient.csv` | OF regenerated (thermal qual case) | NOT TESTED | Primary comparison metric | Test A (thermal baseline); Test D (full coupled) | Test A | — |
| VAL-005 | JR max temperature T_JR_max(t) | OF postProcessing | T_JR_max(t) | Not produced | OF reference available | NOT TESTED | Peak temperature metric | Test A | Test A | — |
| VAL-006 | Radial probe: JR centerline z=32.79 mm, r=0 | Test plan probe definition | T(0, 32.79mm, t) | Not produced | Test plan defined | NOT TESTED | Spatial resolution of axial heat spreading | Test A | Test A | — |
| VAL-007 | Radial probe: JR outer edge z=32.79 mm, r=10.31 mm | Test plan probe definition | T(10.31mm, 32.79mm, t) | Not produced | Test plan defined | NOT TESTED | Radial T gradient | Test A | Test A | — |
| VAL-008 | Can outer wall probe z=32.79 mm, r=10.545 mm | Test plan probe definition | T(10.545mm, 32.79mm, t) | Not produced | Test plan defined | NOT TESTED | Can surface T | Test A | Test A | — |
| VAL-009 | Cap top-center probe z=70.02 mm, r=0 | Test plan probe definition | T(0, 70.02mm, t) | Not produced | Test plan defined | NOT TESTED | Top BC cooling | Test A | Test A | — |
| VAL-010 | Can temperature history T_Can(t) | Test plan | T_Can(t) | Not produced | Test plan defined | NOT TESTED | Structural temperature | Test A | Test A | — |
| VAL-011 | Top-end temperature T_top(t) | Test plan | T at top end (Cap/EndPlate region) | Not produced | Test plan defined | NOT TESTED | Top thermal management | Test A | Test A | — |
| VAL-012 | Bottom-end temperature T_bottom(t) | Test plan | T at bottom end (Can-bottom / −Ve stack) | Not produced | Test plan defined | NOT TESTED | Bottom thermal management | Test A | Test A | — |
| VAL-013 | Top-end ≠ Bottom-end temperature (asymmetry) | OF geometry (asymmetric top/bottom); Test plan | T_top(t) ≠ T_bottom(t) due to asymmetric OF geometry | Not tested; T06 geometry symmetric → would give equal ends | Test plan | OPEN | Symmetric T06 geometry would produce T_top=T_bottom; fails this observable | GEO-010..014 geometry correction; or Option D asymmetric mapping | Test A; GEO/AX test | GEO-009,010,014 |
| VAL-014 | Stored thermal energy E_stored(t) | Test plan | ∫ρCp·T dV over all regions | Not produced | Test plan | NOT TESTED | Energy balance check | Test A | Test A | MAT-001..011 |
| VAL-015 | External heat rejection Q_ext(t) | Test plan | ∫h·(T−T_amb) dA over exposed surfaces | Not produced | Test plan | NOT TESTED | Thermal balance closure | Test A | Test A | BC-001,002 |
| VAL-016 | Spatial heat deposition map q(x,t) — coarse-grained JR | Test D | Spatial q(x,t) in JR | Not produced | Test plan | NOT TESTED | Verify distributed RCR deposits heat spatially | Test D | Test D | DIST-001..005 |
| VAL-017 | OF reference: `cases/wedge_2170_thermal_qualification` CSV exports | OF case; Test plan Phase 6 | Regenerated clean reference transient at `reference_thermal_transient.csv` | Available at `cases/wedge_2170_thermal_qualification/reference_thermal_transient.csv` | OF case exists | PARTIAL | Without clean OF reference, Test A has no comparison baseline | Reference exists; verify not stale before Test A | Before Test A | — |

---

## RUN — Runtime / Implementation Constraints

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| RUN-001 | No external Python/ECM/FMU/Java per-timestep coupling in final STAR model | NEXTSESSION governing objective | Native STAR battery runtime | TBM design intent; not yet run | NEXTSESSION | PARTIAL | External coupling would require infrastructure; delivery = standalone STAR sim | Verify in Test B | Test B | ELEC-012 |
| RUN-002 | Native STAR battery model only (IET=RCRTable 3D, SIMMOD) | NEXTSESSION | Native STAR | TBM design: native model | NEXTSESSION | PARTIAL | Non-native would require external infrastructure | Verify Test B native run | Test B | ELEC-001 |
| RUN-003 | Time step and end time matching OF reference for Test A/D comparison | Test plan | Match `wedge_2170_thermal_qualification` run configuration | Not yet set in STAR | Test plan | NOT TESTED | Mismatched time discretization would confound comparison | Set in Test A/D | Test A | VAL-017 |
| RUN-004 | STAR version documented (from S0-R0) | Test plan S0-R0 | Version string from Help→About | Not yet returned from Robert | S0 not run | NOT TESTED | Version affects gap-tolerance thresholds and feature availability | S0-R0 | S0-R0 | — |
| RUN-005 | m_dAhCell = 5.0 Ah | NEXTSESSION protected | 5.0 Ah | In TBM; NEXTSESSION protected | NEXTSESSION | **SATISFIED** | — | — | — | — |
| RUN-006 | RCR tables from AE characterization at 3 temperature points | NEXTSESSION protected | AE data | In TBM design | NEXTSESSION | PARTIAL | Wrong tables → wrong V/SOC/heat | Verify TBM tables match AE source | Test B | ELEC-006 |
| RUN-007 | m_bOnly1D = 0 in all SIMMOD blocks | NEXTSESSION; R004 | 0 | Confirmed | R004 | **SATISFIED** | — | — | — | — |
| RUN-008 | Transport number fields = 0 | R005 confirmed | 0 | Confirmed | R005 | **SATISFIED** | — | — | — | — |
| RUN-009 | +Electrode m_dS3 = 5 mm; −Electrode m_dS3 = 50 mm | NEXTSESSION protected; R005 | As specified | In TBM; NEXTSESSION protected | R005 | **SATISFIED** | — | — | — | — |

---

## Coverage check

| Family | Count | SATISFIED | PARTIAL | OPEN | CONTRADICTED | NOT TESTED | SUPERSEDED |
|---|---|---|---|---|---|---|---|
| GEO | 24 | 1 | 0 | 20 | 0 | 3 | 0 |
| TOP | 15 | 0 | 0 | 10 | 0 | 5 | 0 |
| MAT | 14 | 0 | 8 | 2 | 0 | 4 | 0 |
| IFC | 6 | 0 | 0 | 4 | 0 | 2 | 0 |
| BC | 5 | 0 | 0 | 0 | 0 | 5 | 0 |
| SRC | 8 | 0 | 2 | 1 | 1 | 4 | 0 |
| IC | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| ELEC | 12 | 4 | 4 | 0 | 0 | 4 | 0 |
| DIST | 5 | 0 | 0 | 0 | 0 | 5 | 0 |
| STAR | 14 | 1 | 0 | 0 | 0 | 13 | 0 |
| VAL | 17 | 0 | 1 | 1 | 0 | 15 | 0 |
| RUN | 9 | 5 | 3 | 0 | 0 | 1 | 0 |
| **Total** | **130** | **11** | **18** | **38** | **1** | **62** | **0** |
