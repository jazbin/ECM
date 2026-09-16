# Three-region OpenFOAM-equivalent topology + native distributed RCR feasibility

**Date:** 2026-09-16  
**Branch:** `tbm-rcr-modelmap-fix-exec`  
**Status:** Engineering decision / qualification plan

## Governing requirements

The production STAR-CCM+ solution must simultaneously satisfy both requirements:

1. reproduce the OpenFOAM-ECM **macro thermal topology** as closely as STAR permits:
   - `Can`
   - `Cap`
   - `JellyRoll`
2. use a **genuinely spatially distributed electrical ECM** in the jelly roll, driven by the About-Energy RCR tables **natively inside STAR-CCM+**, with no OpenFOAM/Python/external runtime coupling.

A single whole-cell / whole-jelly-roll 0D RCR state is not acceptable.

---

# Executive conclusion

## A. Native distributed RCR from TBM, with no runtime scripts

**Feasibility: YES — this is a vendor-intended STAR/BDS workflow.**

Siemens STAR-CCM+ documentation states that:

- 3D battery cells with the **3D RCR model** are imported from Simcenter Battery Design Studio via `.tbm`;
- the imported cell exposes a `Unit Cell Model` plus cylindrical-cell `Specified Electrical Mesh Dimensions`, read-only `Actual Electrical Mesh Dimensions`, and `Number of Spokes`;
- STAR explicitly says the computed `Actual Electrical Mesh Dimensions` are the resolution it uses;
- the IET model describes the electronic and thermal behavior, and STAR supports the RCR IET model;
- STAR interprets RCR data from `.tbm` files and populates RCR parameter tables;
- RCR tables support indexed `Rp[n]` / `Tau[n]` branches, including `Rp0`, `Rp1`, `Tau0`, `Tau1`, matching the two-RC About-Energy data format.

Siemens' Battery Design Studio material additionally describes the recommended workflow as: fit/generate an RCR 3D empirical model in BDS, export through TBM, and use that model for 3D electrothermal pack behavior in STAR-CCM+.

Therefore no external Python ECM is conceptually required at runtime. Our remaining work is **qualification of our hand-authored TBM**, not invention of a new coupling architecture.

Current candidate direction remains:

```text
MODELMAP IET       = RCRTable 3D
Thermal            = Distributed
m_bOnly1D          = 0
m_nRCRParameterSets = 3
m_nXGridPoints      = 7
m_nYGridPoints      = 7
m_nVirtualCells     = 1
m_bSpecifyCapacity  = 1
m_dAhCell            = 5.0
```

The exact production candidate still needs STAR runtime proof that the intended RCR tables and distributed electrical mesh are active.

## B. Literal three-CAD-solid cell from the native cylindrical BDS builder

**Feasibility: NOT SUPPORTED by current evidence, and it should no longer be the primary target.**

The native cylindrical 3D battery workflow is intentionally more detailed than the OpenFOAM thermal CAD model. Siemens' cylindrical import workflow exposes objects such as positive/negative EndPlate, Internal-Post, Tab Root, Tab Stem, Washer, Can and Mandrel. STAR's 3D module model separately expects:

```text
Core Parts
+ Tab Parts
- Tab Parts
```

Our returned client STEP campaign independently reproduces the same architecture: all 17 successful STEP files contain the same 13 named solids:

```text
Mandrel
Jellyroll
Can
+Ve Tab Root
+Ve Tab Stem
-Ve Tab Root
-Ve Tab Stem
+Ve Washer
-Ve Washer
+Ve EndPlate
-Ve EndPlate
+Ve Internal-Post
-Ve Internal-Post
```

This stable match to the vendor workflow indicates that these bodies are not random CAD debris. At least some of them participate in the terminal/current path required by the native 3D battery model.

Therefore deleting/avoiding all auxiliary bodies merely to force the CAD tree to contain exactly three solids risks destroying the distributed electrical model we actually need.

## C. Three OpenFOAM-equivalent thermal regions while retaining STAR's electrical subparts

**Feasibility: STRONGLY PLAUSIBLE and this is now the preferred architecture to qualify.**

STAR separates two concepts:

1. battery-module electrical associations (`Core Parts`, `+ Tab Parts`, `- Tab Parts`), which reference geometry parts;
2. `Assign Parts to Regions`, which maps geometry parts into computational regions.

The normal STAR Parts-to-Regions workflow explicitly permits multiple selected geometry parts to be assigned to one region. Therefore the 13 BDS parts can potentially remain intact for STAR's native electrical bookkeeping while being grouped into **three thermal/computational regions** corresponding to the OpenFOAM model.

Conceptual target:

```text
BDS geometry/electrical objects            OpenFOAM-equivalent thermal role
-----------------------------------------  --------------------------------
Jellyroll                                  JellyRoll
Can                                        Can
end/tab/post/washer structures             Cap
[Mandrel: mapping still to be decided]     JellyRoll or explicit equivalent treatment
```

This mapping is a hypothesis to qualify, not yet a production prescription. In particular:

- `Cap := all end/tab/post/washer structures` must be checked against the OpenFOAM cap volume, mass, heat capacity, conductivity and contact path;
- the Mandrel treatment must be chosen from the actual OpenFOAM reference geometry rather than guessed;
- positive and negative terminal objects may remain separate **Parts** for the electrical solver even if they share one thermal `Cap` region/continuum;
- grouping must not break `Core Parts`, `+ Tab Parts`, `- Tab Parts`, connector current paths, or native electrical-mesh generation.

The correct acceptance criterion is therefore **three-region thermal equivalence + distributed native electrical behavior**, not literal equality of the CAD body count.

---

# Why this architecture fits STAR rather than fighting it

STAR documentation for cylindrical 3D cells exposes:

```text
Specified Electrical Mesh Dimensions
Actual Electrical Mesh Dimensions
Number of Spokes
```

and states that the computed actual electrical mesh resolution is what STAR uses. This is direct evidence that the native 3D cell contains a separate distributed electrical discretization; it is not merely a single RCR state attached to one thermal solid.

STAR also stores `Core Parts`, `+ Tab Parts`, and `- Tab Parts` on each 3D battery-module cell. Connector setup uses the jellyroll/core for the battery-cell current report and cylindrical end-plate/post intersections for current transfer. This explains why forcing away every terminal subpart is structurally risky.

The practical solution should therefore preserve STAR's native electrical topology while matching the OpenFOAM model at the thermal-region/equivalent-property level.

---

# Geometry status from the 2026-09-16 client return

The client return does **not** invalidate this architecture.

It established that the previous full-2170 F-series failure came from incorrect radial-field semantics, not from an inability of the BDS builder to make the distributed cell.

Observed successful STEP mapping is approximately:

```text
Package m_dintDiameter      -> generated Can OD
m_dRepCanXDim/YDim          -> generated Can ID
m_dJellyrollThickness_mm    -> generated JR OD
```

The next radial-only DOE must still establish the correct production mapping for:

```text
Can OD = 21.09 mm
Can ID = 20.6274 mm
JR OD  = 20.6274 mm
```

using the proven-safe T06-like axial/root geometry.

Until this radial DOE succeeds, zero-gap OpenFOAM-equivalent JR/Can contact remains a geometry item to qualify.

---

# Decisive STAR runtime qualification

A production candidate should not be called qualified merely because `Create from Tbm` succeeds or because the CAD looks correct. The client STAR run must prove all of the following.

## Gate 1 — native RCR model imported from TBM

After `Create from Tbm`, record/screenshoot the imported battery-cell properties:

```text
TBM File
Unit Cell Model
Specified Electrical Mesh Dimensions
Actual Electrical Mesh Dimensions
Number of Spokes
```

Expected:

- Unit Cell Model identifies the RCR/RCRTable 3D model selected in the TBM;
- electrical mesh dimensions are nontrivial (> one whole-cell state);
- a valid spoke count is present;
- no `m_bOnly1D` rejection or fallback occurs.

Also inspect/tabulate the imported RCR data and confirm:

- 3 temperature parameter sets: 288.15, 298.15, 308.15 K;
- the intended SOC coordinates;
- `Ro`;
- first RC branch (`Rp0`, `Tau0` or STAR-equivalent naming);
- second RC branch (`Rp1`, `Tau1` or STAR-equivalent naming);
- 5 Ah capacity handling;
- entropy/dUdT handling once that production flag is resolved.

No Python/OpenFOAM/external ECM is to be used for this run.

## Gate 2 — distributed electrical behavior, not just a distributed mesh label

Run a short single-cell transient entirely within STAR with a deliberately nonuniform thermal condition across the cell.

The proof required is that the electrical solution contains multiple spatially resolved elements/states and that local electrothermal behavior responds to the local temperature field. Capture any available local electrical quantities/heat-source distribution on the battery electrical mesh.

The test fails the project requirement if STAR uses only one whole-cell temperature/state and merely spreads one total heat value into the thermal mesh.

## Gate 3 — preserve electrical assignments after three-region thermal grouping

With all electrically necessary BDS geometry parts retained, create the proposed three thermal groups/regions and verify that the battery module still has valid:

```text
Core Parts
+ Tab Parts
- Tab Parts
Battery Cell
```

and that mesh generation / electrical initialization succeeds.

If grouping the detailed objects into three regions breaks these assignments, stop and determine the minimum region separation STAR actually requires. Do not fall back to 0D RCR.

## Gate 4 — OpenFOAM thermal equivalence

Once radial geometry is correct, compare a single-cell case with the existing OpenFOAM-ECM reference using the same load and thermal boundary conditions.

At minimum compare:

```text
cell voltage vs time
integrated electrical heat vs time
volume-average JellyRoll temperature
maximum JellyRoll temperature
Can temperature
Cap temperature
spatial JellyRoll temperature distribution
spatial heat-generation distribution
```

For the three thermal groups, match the OpenFOAM target's effective mass, rho*Cp, anisotropic/effective conductivity where applicable, interfaces and zero-contact-resistance assumptions. Auxiliary BDS solids must not introduce unaccounted thermal mass or artificial thermal resistance.

---

# Decision state

| Question | Current answer |
|---|---|
| Can STAR consume RCR tables from TBM natively? | **YES — documented STAR functionality.** |
| Is RCR intended for 3D electrothermal STAR battery simulation? | **YES — documented Siemens BDS/STAR workflow.** |
| Does the cylindrical 3D model have a distributed electrical mesh? | **YES — documented specified/actual electrical mesh + spokes.** |
| Is our exact hand-built 2170 RCR TBM already physics-qualified? | **NO — STAR runtime qualification still required.** |
| Can BDS natively generate literally only Can + Cap + JellyRoll while preserving the standard distributed electrical path? | **Not demonstrated; current evidence argues against making this the target.** |
| Can detailed BDS electrical parts plausibly be retained while mapping them into three OpenFOAM-equivalent thermal regions? | **YES, strongly plausible from STAR's separate part-assignment and Parts-to-Regions architecture; runtime test required.** |
| Is the exact OpenFOAM zero-gap radial geometry already achieved? | **NO — radial field DOE remains the next geometry experiment.** |

---

# Recommended production architecture

```text
About-Energy RCR tables
        |
        v
hand-authored/validated TBM
  MODELMAP: RCRTable 3D
  Thermal: Distributed
  m_bOnly1D = 0
        |
        v
STAR-CCM+ Create from Tbm
        |
        +--> native distributed cylindrical electrical mesh
        |      + Core Parts
        |      + +Tab Parts
        |      + -Tab Parts
        |      + RCR two-RC parameter tables
        |
        +--> BDS detailed geometry parts retained for solver bookkeeping
                 |
                 v
          thermal Parts-to-Regions mapping
                 |
                 +--> JellyRoll-equivalent region
                 +--> Can-equivalent region
                 +--> Cap-equivalent region
```

No external runtime ECM script is present in this architecture.

---

# Sources / evidence

Internal project evidence:

- `tbm_validation/CLIENT_RETURN_ANALYSIS_20260916.md`
- `tbm_validation/STEP_VISUAL_INSPECTION_20260916.md`
- `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`
- `tbm_validation/LUMPED_ELECTRICAL_RCR_EVIDENCE_20260909.md`
- `tbm_validation/RCR_MODELMAP_ENGINEERING_NOTE_20260909.md`
- `tbm_validation/STAR_IMPORT_SELECTION_ELECTRICAL_BEHAVIOR_NOTE_20260910.md`
- `NEXTSESSION`

External Siemens/STAR documentation consulted:

- Simcenter STAR-CCM+ 2406 Battery Cells Reference: `GUID-7DD0CD54-41B4-46D2-B398-06226A7F36C4`
- Simcenter STAR-CCM+ RCR Table Reference: `GUID-7E9EB630-15F7-40D5-B330-29FAD2EF2C7C`
- Simcenter STAR-CCM+ Battery Modules Reference: `GUID-83A7CDA4-8D4D-45AE-A4F7-8988BBF14AD6`
- Simcenter STAR-CCM+ Assign Parts to Regions Reference: `GUID-37027DA8-6A40-45E7-869E-27E2D97362B9`
- Siemens Simcenter Battery Design Studio overview/blog describing the RCR 3D -> TBM -> STAR-CCM+ electrothermal workflow.

---

## Bottom line

The project target is still technically credible, but the correct interpretation is:

> **Do not force STAR's native distributed cylindrical battery to have only three CAD bodies. Preserve the detailed electrical parts STAR expects, then make the thermal computational model equivalent to the OpenFOAM Can/Cap/JellyRoll topology. Drive the distributed ECM natively from the RCRTable 3D data contained in the TBM.**

The two remaining decisive experiments are the radial geometry DOE and the STAR three-region/distributed-RCR runtime qualification above.
