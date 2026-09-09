# Lumped Electrical RCR Configuration Evidence Note
Date: 2026-09-09
Branch: tbm-rcr-modelmap-fix-exec

---

## Objective

Determine whether STAR-CCM+ supports a "lumped-electrical" configuration that uses
the SAME About-Energy two-RC `RCRTable 3D` model as one whole-cell electrical ECM
state (single cell-level temperature → single heat source), while keeping
`Thermal = Distributed` unchanged.

Desired A/B pair:

  Distributed (approved candidate):
    electrical: spatially resolved RCRTable 3D per mesh element
    thermal:    STAR Distributed (3D heat diffusion within cell)

  Lumped-electrical target:
    electrical: one whole-cell About-Energy RCR state (single T in, single Q out)
    thermal:    STAR Distributed (unchanged)

This note documents empirical corpus evidence for all candidate electrical-lumping
mechanisms and concludes on each.

---

## Corpus source

Branch `tbm-siemens-reference-corpus` (SHA `b0be477f19bf16eaff92eafd9f3ba07fb6f3152d`)
worktree at `/tmp/ecm-siemens-corpus`.

Files inspected: all files under `tbm_validation/siemens_reference_corpus/`.

---

## Our approved distributed candidate — baseline for comparison

File: `out/rcr_candidate/hp2170-rcr-v1-tabs-on-sameFace.tbm`
SHA:  `7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940`

MODELMAP:
  IET     = RCRTable 3D
  Thermal = Distributed

RCRTable 3D SIMMOD (active block):
  m_bLumpedEnergyBalance = 0
  m_bOnly1D              = 0
  m_nRCRParameterSets    = 3
  m_nXGridPoints         = 7
  m_nYGridPoints         = 7
  m_nVirtualCells        = 1
  m_bSpecifyCapacity     = 1
  m_dAhCell              = 5.0

---

## Mechanism 1: m_bOnly1D = 1

### What it does

`m_bOnly1D = 1` in the active SIMMOD enables a 1D spatial approximation for the
electrochemical model. Rather than computing ECM state at each 3D mesh element, the
model is reduced to a 1D column, which is a form of electrical spatial reduction.

### Corpus evidence

Files with `m_bOnly1D = 1` in the active SIMMOD block:

| File                                | IET          | Thermal     | Provenance |
|-------------------------------------|--------------|-------------|------------|
| hp18650Spiral-RCR25deg.tbm          | RCRTable 3D  | (blank)     | BDS install|
| High_Power_18650_RCR.tbm (tutorial) | RCRTable 3D  | Distributed | BDS tutorial|
| hp18650Spiral1-1D.tbm (GapExample)  | Distributed 3D | Distributed | BDS install|
| DIST1D-FIT.tbm / DIST1D-BESTFIT.tbm | Distributed 3D | (varied) | BDS sample|

All three STAR-provenance files (validationBattery.tbm, testTBM.tbm, LiIonSpiral.tbm)
have `m_bOnly1D = 0` in their active SIMMOD block.

### STAR validation status

STAR-REJECTED. Robert's STAR-CCM+ import of an earlier candidate with `m_bOnly1D = 1`
returned the explicit error:
  "m_bOnly1D option is not supported"
This is a hard blocker. `m_bOnly1D = 1` is BDS-valid but STAR-unqualified.

---

## Mechanism 2: m_bLumpedEnergyBalance = 1 in the active RCRTable 3D SIMMOD

### What it means (interpretation)

`m_bLumpedEnergyBalance` controls whether the electrochemical model computes its energy
balance using a single cell-averaged temperature or resolves it per spatial element. A
value of 1 would mean the ECM receives a single volume-averaged temperature and returns
a single aggregate heat source — which is the "lumped-electrical" behavior sought.

### Corpus evidence — active SIMMOD only

| File                   | IET          | Thermal     | lumped=? | m_bOnly1D | Provenance   |
|------------------------|--------------|-------------|----------|-----------|--------------|
| validationBattery.tbm  | RCRTable 3D  | Distributed | 0        | 0         | STAR install |
| testTBM.tbm            | RCRTable 3D  | Distributed | 0        | 0         | STAR install |
| LiIonSpiral.tbm        | Distributed 3D | Distributed| 1       | 0         | STAR install |
| Kim_RCR1D-Rev1.tbm     | RCRTable 3D  | (absent)    | 1        | 0         | BDS sample   |
| High_Power_18650_RCR   | RCRTable 3D  | Distributed | 0        | 1         | BDS tutorial |
| hp18650Spiral-RCR25deg | RCRTable 3D  | (blank)     | 0        | 1         | BDS install  |

Notes:
- `LiIonSpiral.tbm` has `m_bLumpedEnergyBalance = 1` in its active `Distributed 3D`
  SIMMOD (a different IET family — this may be a Distributed-model-specific flag).
- `Kim_RCR1D-Rev1.tbm` has `m_bLumpedEnergyBalance = 1` in its active `RCRTable 3D`
  SIMMOD. This is the ONLY BDS/STAR corpus file that shows this combination for RCRTable 3D.

### Critical observations

1. Both STAR-provenance RCRTable 3D files (validationBattery, testTBM) have
   `m_bLumpedEnergyBalance = 0` in the active RCRTable 3D block.

2. The sole file with `m_bLumpedEnergyBalance = 1` in an active `RCRTable 3D` block
   (Kim_RCR1D-Rev1) is a BDS sample project file, not a STAR-CCM+ validated example.
   It also has `Thermal = ` (absent), so it does NOT demonstrate the Thermal=Distributed
   combination we need.

3. The combination `RCRTable 3D + m_bLumpedEnergyBalance=1 + Thermal=Distributed + m_bOnly1D=0`
   does NOT appear in any corpus file. It is untested against STAR.

4. Given that STAR explicitly rejects `m_bOnly1D = 1`, the possibility that STAR also
   has a blocked-flag list covering `m_bLumpedEnergyBalance = 1` in the active RCR
   block cannot be ruled out from corpus evidence alone.

### STAR validation status

UNKNOWN — no STAR-sourced file validates `m_bLumpedEnergyBalance = 1` in an active
`RCRTable 3D` SIMMOD. The flag is present only in one BDS sample file without the
required `Thermal = Distributed` combination. Cannot be classified as supported.

---

## Mechanism 3: IET = R 1D

### Model family

`R 1D` is a lumped network-resistance model with these fields:
  m_dNegPostR_ohm, m_dNegTabR_ohm, m_dNegTerminalR_ohm
  m_dPosPostR_ohm, m_dPosTabR_ohm, m_dPosTerminalR_ohm
  m_dNegNodes, m_nPosNodes, m_nSepNodes
  m_dHeatTransferArea_m2

The `R 1D` SIMMOD has NO:
  - OCV vs SOC lookup table
  - Temperature-dependent R0/Rp/tau lookup tables
  - m_nRCRParameterSets field
  - RC time constants

### Corpus evidence

`Kim_RCR1D.tbm` (older version of Kim pouch demo): MODELMAP `IET = R 1D`.
The `R 1D` SIMMOD contains transmission-line node counts (NegNodes=10, PosNodes=10,
SepNodes=6), not tabular ECM parameters.

### Compatibility with our two-RC data

NOT compatible. The `R 1D` model cannot represent:
  - OCV(SOC) tables
  - Temperature-dependent R0/Rp/Rp1 tables
  - RC time constants (tau, tau1)
  - Three-temperature-set structure

Data translation from `RCRTable 3D` → `R 1D` would not preserve the same electrical
model — it is a fundamentally different and simpler model family.

---

## Mechanism 4: IET = RCR 1D

### Model family

`RCR 1D` (seen in Kim_RCR1D.tbm as an available SIMMOD) has these fields:
  nRoEqnFitType, nRpEqnFitType, ntauEqnFitType
  m_dAfactor_m2, m_dCapacity_Coulsqm

The `RCR 1D` SIMMOD uses EQUATION-FIT parameters for R0/Rp/tau (functional forms fit
to data), not lookup tables. It does NOT use the `m_nRCRParameterSets` tabular format.

### Compatibility with our two-RC data

NOT compatible. Our About-Energy RCR data is tabular (SOC/T-indexed lookup tables for
V, R0, Rp, Rp1, tau, tau1, dUdT). The `RCR 1D` model uses an equation-fit
parameterization that cannot represent this data format without a separate fitting step,
which would introduce approximation error and is not lossless.

---

## Mechanism 5: Reduce m_nXGridPoints / m_nYGridPoints to 1

### Hypothesis

Setting `nxgrid=1, nygrid=1` in the `RCRTable 3D` SIMMOD would reduce the spatial
ECM grid to a single point per cell, effectively making the electrical model lumped.

### Corpus evidence

No corpus file uses `nxgrid=1` or `nygrid=1` in an active `RCRTable 3D` SIMMOD.
All STAR-provenance RCRTable 3D files use 7×7 grids. The `Dual` SIMMOD (inactive,
observed in multiple files) has `nxgrid=1, nygrid=1`, but it is a different model
family entirely (charge-independent).

### STAR validation status

No corpus evidence. This would be a speculative configuration not validated by any
Siemens reference file. Cannot be confirmed as supported.

---

## Mechanism 6: m_nVirtualCells

All inspected files have `m_nVirtualCells = 1`. This field does not vary across
any file in the corpus. It does not provide a lumping mechanism based on available
evidence.

---

## STAR vs BDS provenance separation

The table below summarises all examined RCR-capable configurations, distinguished by
whether they have been tested in STAR-CCM+ (STAR install / validation files) or only
exist as BDS design-environment files.

| Mechanism                              | BDS evidence | STAR evidence | STAR import result |
|----------------------------------------|--------------|---------------|-------------------|
| RCRTable 3D / m_bOnly1D=0 (ours)      | yes          | yes (3 files) | PASS (approved)   |
| RCRTable 3D / m_bOnly1D=1             | yes (2 files)| none          | REJECTED          |
| RCRTable 3D / m_bLumpedEnergyBalance=1 | yes (1 file)| none          | unknown           |
| IET = R 1D                             | yes (1 file) | none          | n/a (diff model)  |
| IET = RCR 1D                           | yes (1 file) | none          | n/a (diff model)  |
| RCRTable 3D / nxgrid=1                 | none         | none          | untested          |

---

## Summary

The desired combination — `IET = RCRTable 3D` / `Thermal = Distributed` / `m_bOnly1D = 0` /
electrically lumped (one whole-cell ECM state) — has NO directly evidenced, STAR-tested
configuration in the corpus.

The three candidate paths are each blocked:

- **`m_bOnly1D = 1`**: BDS-documented but explicitly rejected by STAR import.
  Classification: `BDS_SUPPORTED_BUT_STAR_UNQUALIFIED`.

- **`m_bLumpedEnergyBalance = 1` in active RCRTable 3D block**: One BDS sample file
  (Kim_RCR1D-Rev1) but no STAR validation, not paired with `Thermal = Distributed`,
  and unknown import outcome. Classification: `BDS_ONLY_STAR_UNKNOWN`.

- **Alternative IET models (`R 1D`, `RCR 1D`)**: Incompatible model families; cannot
  preserve tabular two-RC electrical data. Classification: `INCOMPATIBLE_MODEL_FAMILY`.

- **Reduced grid (nxgrid=1, nygrid=1)**: No corpus precedent at all.
  Classification: `SPECULATIVE_NO_EVIDENCE`.

No STAR-defensible lumped-electrical candidate can be generated without independent
STAR qualification of one of the above mechanisms. Creating a file with any of these
configurations would require marking it `BDS_SUPPORTED_BUT_STAR_UNQUALIFIED` and
stopping for review, per the task specification.

---

LUMPED_ELECTRICAL_CONFIGURATION_UNRESOLVED
