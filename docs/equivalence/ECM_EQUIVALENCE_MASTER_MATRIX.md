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
| GEO-011 | Top Cap height = 4.6787 mm | `cap_rotated/polyMesh/points` | 4.6787 mm | T06 EndPlate: 0.059504 mm thick; +EndPlate minimum distance from JR top = 2.385496 mm (STEP audit) | STEP audit | OPEN | Effective top thermal resistance wrong; Cap thermal mass wrong | STAR material mapping to top stack (B route) or Cap-equivalent geometry (A route) | S0-C; or TBM Cap geometry | S0-C |
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
| GEO-023 | Can thermal volume = 1.06776×10⁻⁶ m³ | `openfoam_thermal_operator.json` | 1.06776×10⁻⁶ m³ | T06 Can: ~6.202×10⁻⁶ m³ (6202 mm³ from STEP audit; wrong radial/axial dimensions) | STEP + json | OPEN | Wrong Can thermal mass | Resolves when GEO-002, GEO-003, GEO-006, GEO-010 met | RAD-D1 + GEO-AX | GEO-002,003,006,010 |
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
| SRC-004 | **LUMPED track:** Spatially uniform heat deposition q = Q_total/V_JR; **DISTRIBUTED track:** spatially varying q(x,t) per partition as confirmed in OF distributed reference | LUMPED: `wedge_2170` `selectionMode all`, `lumpedOutput totalPower`; DIST: `validation_distributed_paramset_21p09x70p02` ecm_state `prev_qvol_by_ecmid` varies ~10× | LUMPED: uniform q; DIST: per-partition q, ~10× variation confirmed | LUMPED STAR: uniform deposition expected from 0D mode; DIST STAR: spatially varying q expected from RCRTable 3D | OF both modes confirmed; STAR not run | PARTIAL | Misidentifying the track conflates two distinct behaviors; STAR Test A-LUMP uses uniform source; Test C/D-DIST verifies spatial variation | LUMPED track: Test A-LUMP; DIST track: Test C/D | Test A-LUMP; Test C | — |
| SRC-005 | **LUMPED track:** Single heat-source zone = all JR cells; **DISTRIBUTED track:** per-partition ECM IDs (axial6_radial3 = 18 partitions) via `elementMappingFile` | LUMPED: `selectionMode all` single zone; DIST: `mapping_table_axial6_radial3_2170mesh.csv`, 18 ecmCellIds | LUMPED: one zone; DIST: 18 spatial partitions confirmed | Not tested in STAR for either track | OF both confirmed | PARTIAL | Sub-zoning semantics differ between tracks; must not conflate them when designing STAR tests | LUMPED: Test A-LUMP; DIST: Test C confirms 18-partition-equivalent behavior | Test A-LUMP; Test C | — |
| SRC-006 | Heat source drives enthalpy field h (not T directly) | OF `fvOptions ecmHeatSource` on `h` | Enthalpy source | STAR uses its own thermal energy solver | OF confirmed | NOT TESTED | Formulation difference should be equivalent; verify energy balance | Energy balance check in Test A | Test A | — |
| SRC-007 | V_JR for volumetric source = 2.17583×10⁻⁵ m³ (full 360° cylinder, totalVolumeScale=1) | OF `ecmCoupling`; json | 2.17583×10⁻⁵ m³ | Wrong until GEO-001/005 met | json confirmed; TBM OD wrong | OPEN | Wrong volumetric heat density if V_JR wrong | Resolves with GEO-001, GEO-005 | RAD-D1/D2 | GEO-001, GEO-005 |
| SRC-008 | Direct ECM heat: JR = 100%, Can = 0%, Cap = 0% | `fvOptions/jellyRoll_rotated` (ecmHeatSource present); `fvOptions/shell_rotated` (no ecmHeatSource); `fvOptions/cap_rotated` (no ecmHeatSource) | 100% JR, 0% Can, 0% Cap | REFERENCE RESOLVED from OF executable case. Some stale documents cite f_cap=0.034 — that is a documentation cleanup item (see C01), NOT an open requirement. Test A must use 100% JR / 0% Can / 0% Cap. | OF fvOptions confirmed | **SATISFIED** | Requirement resolved. Stale doc contradiction in C01 must not be used as a TBM or test-design input. | Ensure Test A uses 100% JR heat only | — | — |

---

## IC — Initial Conditions

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| IC-001 | Initial temperature T_0 = 298.15 K uniform across all regions | `0/*/T` initial fields; json `initial_conditions` | 298.15 K uniform | Must be set in STAR; not verified | OF confirmed | NOT TESTED | Wrong T_0 shifts whole transient; wrong RCR temperature interpolation at t=0 | Set in STAR Test A/B/C/D and verify | Test A | — |

---

## LUMP — Lumped Equivalence Track (OF lumped ↔ STAR 0D whole-cell RCR)

**OF lumped reference:** `cases/wedge_2170` (`couplingMode lumped`, `lumpedOutput totalPower`) and `cases/validation_lumped_paramset_21p09x70p02` (`couplingMode lumped`). Both use a single scalar ECM state (one q_ah, one v_rc vector, one hysteresis value — no spatial partitioning). Heat deposition is uniform across all JR cells.

**STAR target:** native 0D/lumped whole-cell RCR mode.

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| LUMP-001 | OF lumped couplingMode confirmed: single scalar ECM state, uniform deposition | `cases/wedge_2170/system/controlDict`; `cases/validation_lumped_paramset_21p09x70p02/system/controlDict` | `couplingMode lumped`; single `state.q_ah`, `state.v_rc`, `state.hysteresis` | Confirmed from both cases | controlDict + ecm_state.json | **SATISFIED** | Reference confirmed; lumped track defined | — | — | — |
| LUMP-002 | STAR native 0D/lumped whole-cell RCR mode available and selectable | NEXTSESSION final requirement | Native STAR 0D RCR; IET selectable | Not yet tested in STAR; TBM design supports it via IET field | NEXTSESSION | PARTIAL | Lumped track cannot be validated if STAR lacks native 0D RCR mode | Verify during Test B (lumped variant) | Test B-LUMP | — |
| LUMP-003 | V(t) match: STAR lumped vs OF lumped for same AE characterization + current profile + SOC₀ + T₀ | `cases/wedge_2170` V(t) output; `cases/validation_lumped_paramset_21p09x70p02` postProcessing | V(t) time series from wedge_2170 (lumped run) | Not yet compared | OF lumped reference run available | NOT TESTED | Primary electrical validation for lumped track | Test D-LUMP | Test D-LUMP | LUMP-002, LUMP-006, LUMP-007 |
| LUMP-004 | SOC(t) match: STAR lumped vs OF lumped | Same cases | SOC(t) time series | Not yet compared | OF lumped reference available | NOT TESTED | SOC tracking equivalence | Test D-LUMP | Test D-LUMP | LUMP-002 |
| LUMP-005 | Total Qdot(t) match: STAR lumped vs OF lumped | Same cases | Qdot(t) total heat (lumpedOutput totalPower) | Not yet compared | OF lumped output available | NOT TESTED | Energy balance equivalence; total heat determines thermal response | Common Test A (fixed heat source), Test D-LUMP (coupled) | Test A | LUMP-002 |
| LUMP-006 | T_JR_mean(t) match: STAR lumped vs OF lumped | Same cases | T_JR_mean(t) transient | Not yet compared | OF lumped reference available | NOT TESTED | Thermal response equivalence under lumped load | Common Test A | Test A | LUMP-002, LUMP-005 |
| LUMP-007 | Same About-Energy characterization data used in both OF lumped and STAR lumped runs | NEXTSESSION; `cases/wedge_2170/constant/electrical_inputs_from_validation.csv` | AE RCR tables; same SOC₀, T₀, current profile | In TBM design; wedge_2170 uses electrical_inputs_from_validation.csv | NEXTSESSION; wedge_2170 | PARTIAL | Different characterization data would make comparison meaningless | Confirm STAR uses same AE tables before Test D-LUMP | Pre-Test-D-LUMP | — |

---

## ELEC — ECM / RCR Electrical Behaviour (DISTRIBUTED track: OF elementWise ↔ STAR distributed 3D RCR)

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| ELEC-001 | IET = RCRTable 3D (DISTRIBUTED track only; lumped track uses different IET setting — OPEN) | NEXTSESSION protected parameters (distributed track) | RCRTable 3D for distributed; lumped-track IET not yet established | REFERENCE RESOLVED for distributed (OF elementWise → STAR RCRTable 3D equivalent). STAR STATIC CONFIG PRESENT in T06 TBM. STAR RUNTIME VERIFIED: NOT YET. | NEXTSESSION; OF distributed reference | PARTIAL | Distributed mode requires RCRTable 3D; lumped-track package must not fail because it uses a different IET setting | Verify STAR distributed run with RCRTable 3D active (Test B-DIST); identify lumped-track IET setting | Test B | — |
| ELEC-002 | Thermal = Distributed (DISTRIBUTED track only; lumped track Thermal setting OPEN) | NEXTSESSION protected parameters (distributed track) | Distributed for DIST track; lumped-track Thermal setting not yet established | REFERENCE RESOLVED for distributed. STAR STATIC CONFIG PRESENT. STAR RUNTIME VERIFIED: NOT YET. | NEXTSESSION | PARTIAL | Non-distributed Thermal disables spatial coupling for DIST track; setting is intentionally different in lumped track | Verify in Test B/C (DIST track); identify lumped-track value separately | Test B | — |
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

## DIST — Distributed Electrical Semantics (OF elementWise ↔ STAR distributed 3D RCR)

**OF distributed reference:** `cases/validation_distributed_paramset_21p09x70p02` (`couplingMode elementWise`, `ECM_DISTRIBUTED_ELECTRICAL_MODE=parallel2rc`). ECM state file confirms 18 spatial partitions, each with independent q_ah, v_rc (2 RC elements), hysteresis. Heat `prev_qvol_by_ecmid` and `dqdt_by_ecmid` vary by approximately 10× between central partitions (~957 kW/m³) and outer-edge partitions (~16 MW/m³). Uses `elementMappingFile mapping_table_axial6_radial3_2170mesh.csv` (6 axial × 3 radial = 18 partitions). Spatial state field `stField ecmST`.

**STAR target:** native distributed 3D RCR mode (IET=RCRTable 3D, Thermal=Distributed). **Spatial resolution:** OF uses 18 partitions (6 axial × 3 radial). STAR is NOT required to use exactly 18 electrical zones. Equivalence is operator/response equivalence — STAR must produce spatially varying electrical state under non-uniform T, but the internal discretization need not match OF's partition count. Test C comparison strategy (how many STAR zones and how to compare against OF's 18 partitions) is OPEN and must be designed as part of Test C preparation.

| ID | Requirement | Auth source | OF target | Current TBM/STAR state | Evidence | Status | Op consequence | Resolution | Required test | Dep |
|---|---|---|---|---|---|---|---|---|---|---|
| DIST-001 | OF distributed mode confirmed: local electrical state (SOC, polarization) varies spatially across 18 partitions | `cases/validation_distributed_paramset_21p09x70p02/ecm/ecm_state.json`; `controlDict couplingMode elementWise` | 18 independent ECM partition states with distinct q_ah, v_rc, hysteresis | Confirmed from ecm_state.json | ecm_state.json; controlDict | **SATISFIED** | OF distributed reference is confirmed and characterised | — | — | — |
| DIST-002 | Local heat deposition q(x,t) spatially varies across JR partitions in OF distributed mode | `cases/validation_distributed_paramset_21p09x70p02/ecm/ecm_state.json` `prev_qvol_by_ecmid` / `dqdt_by_ecmid` | q varies ~10× between central (partition 2: ~957 kW/m³) and outer-edge (partition 9: ~16 MW/m³) partitions | Confirmed from ecm_state.json | ecm_state.json | **SATISFIED** | OF distributed reference spatial variation confirmed | — | — | — |
| DIST-003 | STAR distributed 3D RCR must produce spatially varying local electrical state under non-uniform T (STAR internal discretization need not match OF's 18 partitions) | Test plan (Test C PASS criterion) | Per-region SOC/heat varying spatially when T spatially varying — analogous to OF distributed reference (DIST-001/002); no 18-zone match required | Not yet demonstrated in STAR | Test plan; DIST-001/002 confirmed; Test C spatial comparison strategy OPEN | NOT TESTED | Uniform electrical state → lumped behavior → distributed mode inoperative | Test C PASS criterion; Test C spatial comparison strategy to be designed | Test C | ELEC-001, ELEC-002 |
| DIST-004 | Local current density / heat at a spatial point governed by local T (not global mean T) in STAR | Test plan | RCR(x,t) = f(T_local(x,t)); analogous to OF elementWise partition-local T interpolation | Not tested in STAR | Test plan | NOT TESTED | Global-T interpolation → same RCR everywhere → lumped behavior in STAR | Test C | Test C | DIST-003, ELEC-006 |
| DIST-005 | Simultaneous T_A ≠ T_B at two representative JR probes → electrical_state_A(t) ≠ electrical_state_B(t) in STAR | Test plan (Test C formal PASS criterion); analogous behavior confirmed in OF distributed reference | ≥ 2 probe locations with ~20 K gradient showing independent electrical state evolution | Not yet demonstrated in STAR | DIST-001/002 confirm OF reference; STAR not run | NOT TESTED | Required formal proof that STAR distributed semantics are operative | Test C | Test C | DIST-003, DIST-004 |

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
| ~~STAR-008~~ | **SUPERSEDED — premise factually invalid.** Prior text assumed a BDS Can/Jellyroll body volumetric overlap. Exact B-Rep confirms: BDS Can ID = 18.000 mm, BDS JR OD = 17.881 mm, radial gap = 0.059504 mm — no BDS-body overlap exists. The 83.7% "JR" fraction (T06_GEOMETRIC_EQUIVALENCE_AUDIT.md) means the BDS Can solid intersects the *OpenFOAM JR reference domain* after coordinate registration; it does NOT mean the BDS Can physically overlaps the BDS Jellyroll body. The actual BDS-body overlap involving Can is Can↔±EndPlate (5.272 mm³ per end), covered by STAR-009/GEO-020. Can computational topology is covered by STAR-012. No replacement requirement. | — | — | — | — | SUPERSEDED | — | — | — | — |
| STAR-009 | STAR resolves Can↔EndPlate volumetric overlap (5.272 mm³ per end) | Test plan S0-A | Clip or preserve; determines EndPlate thermal volume in STAR | Unknown | Not tested | NOT TESTED | If preserved, EndPlate thermal volume includes Can overlap; if clipped, volumes change | S0-A | S0-A | GEO-020 |
| STAR-010 | +Tab Root ↔ Jellyroll interface: STAR-assigned area | Test plan S0-B | Need quantitative area (not just existence) to assess equivalence with full-disc OF interface | Unknown; STEP common-face area = 0 | STEP B-Rep | NOT TESTED | If area << 3.325×10⁻⁴ m² → top coupling cannot be full-disc equivalent | S0-B (must request area, not just existence) | S0-B | STAR-001 |
| STAR-011 | −Tab Root ↔ Jellyroll interface: STAR-assigned area | Test plan S0-B | Need quantitative area | Unknown; symmetric to STAR-010 | STEP B-Rep | NOT TESTED | Same as STAR-010 for bottom | S0-B (area request) | S0-B | STAR-001 |
| STAR-012 | S0-A establishes what computational structure STAR exposes for the imported Can body: one addressable Can Region/volume, or multiple separately addressable zones/components? If subdivided, record their actual geometry/extent. Note: STAR has no knowledge of OpenFOAM reference-domain boundaries; any observed subdivision cannot be assumed to correspond to OF material zones automatically. | Test plan S0-A | Can computational topology known (monolithic vs subdivided); actual structure recorded | Unknown | Not tested | NOT TESTED | Computational topology determines what material-assignment options are available for the Can body in Test A | S0-A (Can Region tree + volume report; two-question format: subdivision AND overlap-resolution status) | S0-A | GEO-020 |
| STAR-013 | STAR can assign thermal contact resistance (generic capability) to at least one internal interface | Test plan S0-D | Any R_specific settable on any interface | Unknown generic capability | Not tested | NOT TESTED | If generic resistance assignment is not available in STAR's interface model, Option D is impossible entirely | S0-D (test with any available internal interface; confirm settable) | S0-D | STAR-001 |
| STAR-014 | Core Part electrical assignment remains valid while non-default thermal conductivity is assigned | Test plan S0-C | Electrical Core Part + Cap-equivalent thermal material coexist | Unknown | Not tested | NOT TESTED | If STAR couples electrical role to thermal material type → material mapping fails | S0-C | S0-C | ELEC-001 |
| STAR-015 | If S0-A shows monolithic Can Region: STAR can assign distinct thermal material sub-zones within one Region. **Sub-zone geometry is final-dimension-dependent.** The "JR-equivalent annular inner zone" in prior versions was derived from T06 Can ID = 18.0 mm << OF JR OD = 20.627 mm; at that offset the Can wall occupies the OF JR reference domain. At final radial target (Can ID = JR OD = 20.627 mm), the corrected Can wall no longer occupies the OF JR reference domain — the 3-way split may reduce to a 2-zone or 1-zone assignment. The axial material-zone structure (Can-span vs Cap-zone vs bottom) still depends on final axial geometry; re-evaluate after RAD corrections are in place. | Gated on STAR-012 result AND final radial/axial geometry; test plan Test A hard STOP if needed | Number of needed Can sub-zones determined after final geometry; capability confirmed for actual required zone count | Unknown; zone count geometry-dependent | Gated — not testable until STAR-012 resolved AND final dimensions in place | NOT TESTED | If STAR-012 shows monolithic Region AND STAR-015 fails for the final zone count → hard STOP on Test A material mapping; Can geometry restructuring required | S0-A result → if monolithic with final geometry, escalate to dedicated STAR capability test for actual zone count | Test A / STAR capability test | STAR-012 |
| STAR-016 | STAR can assign R_specific = 6.015×10⁻⁷ m²K/W to the specific interface/path representing OF's JR↔Can-bottom coupling, while preserving −Tab Parts electrical roles (production applicability) | Test plan S0-D (production path); IFC-002 | R_specific at JR↔Can-bottom equivalent interface; path identified from S0-B topology + S0-D mechanism | Unknown; depends on which interface/path S0-B reveals as the Can-bottom equivalent in STAR | Not tested | NOT TESTED | If resistance cannot be applied to the correct production path, Option D bottom strategy fails; Can-bottom disc geometry required | S0-B (identify hookable interface/path) + S0-D (confirm resistance settable there while preserving electrical roles) | S0-D | STAR-013, TOP-003 |

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
| SRC | 8 | 1 | 2 | 1 | 0 | 4 | 0 |
| IC | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| LUMP | 7 | 1 | 2 | 0 | 0 | 4 | 0 |
| ELEC | 12 | 4 | 4 | 0 | 0 | 4 | 0 |
| DIST | 5 | 2 | 0 | 0 | 0 | 3 | 0 |
| STAR | 15 | 1 | 0 | 0 | 0 | 14 | 0 |
| VAL | 17 | 0 | 1 | 1 | 0 | 15 | 0 |
| RUN | 9 | 5 | 3 | 0 | 0 | 1 | 0 |
| **Total** | **138** | **15** | **20** | **38** | **0** | **65** | **0** |

**Note on two-track architecture:** LUMP (7 reqs) covers the lumped/0D equivalence track (OF `wedge_2170` / `validation_lumped_paramset_21p09x70p02` ↔ STAR 0D RCR). ELEC/DIST (17 reqs) cover the distributed equivalence track (OF `validation_distributed_paramset_21p09x70p02` ↔ STAR RCRTable 3D). Both tracks are required. DIST-001/002 SATISFIED from confirmed OF reference evidence. SRC-008 SATISFIED (requirement resolved; stale-doc cleanup item in C01 does not block any test). STAR-015/016 added as conditional requirements gated on S0-A and S0-B/S0-D results respectively.

**STAR-008 superseded (2026-09-23):** STAR-008 was removed from the active count after exact B-Rep audit confirmed the premise (BDS Can/JR body overlap) is factually invalid. BDS Can ID = 18.000 mm > BDS JR OD = 17.881 mm; no volumetric overlap exists between these two BDS bodies. The 83.7% "JR" fraction is intersection of the BDS Can solid with the *OpenFOAM JR reference domain* (a spatial zone from the OF mesh registration), not BDS-body overlap. STAR-009 covers the confirmed BDS-body overlaps (Can↔±EndPlate, 5.272 mm³ each). STAR-012 covers Can computational topology. Total active requirements: 138 (was 139).
