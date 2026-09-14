# STAR-CCM+ TBM Import Error Database — Runtime Addendum 2026-09-14

**Project:** hp2170 NCA / STAR-CCM+ native distributed battery TBM  
**Parent canonical register:** `tbm_validation/STAR_IMPORT_ERROR_DATABASE.md`  
**Purpose:** record runtime evidence received after the 2026-09-11 ROOT_A/ROOT_B experiment was prepared, and supersede stale `RUNTIME_PENDING` language for H004-6.

---

## Runtime event `R007` — 2026-09-13/14 — ROOT_A / ROOT_B axial-clearance discriminators

### ROOT_A

**File:** `ROOT_A_AXIAL_CLEARANCE_0p10.tbm`  
**SHA-256:** `c6db74313e675b618f2fb51d371e51231f9e0a2a9f26ca5bdc1f1bde48390343`

**Controlled delta from immutable R005:**

```text
Package m_dintHeight: 65.11 -> 65.21 mm
Package - negative-electrode axial margin: 0.00 -> +0.10 mm
```

**Observed client runtime log:**

```text
Read 5550 lines from F:\About-Energy\20260911\hp2170NCA-STAR-E004-ROOT-CLEARANCE-diagnostic-20260911\ROOT_A_AXIAL_CLEARANCE_0p10.tbm

Read 5550 lines from F:\About-Energy\20260911\hp2170NCA-STAR-E004-ROOT-CLEARANCE-diagnostic-20260911\ROOT_A_AXIAL_CLEARANCE_0p10.tbm

Feature execution failed.

Electrode Root 1 : Extrusion distance can not be 0.

Command: CreateFromTbm

   error: Server Error
```

**Observed error class:** `E004`.

### ROOT_B

**File:** `ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm`  
**SHA-256:** `59f83aa875415d946b1ccb2b6f880a3a98a036e631e3d78993d14edfbbc9ee36`

**Controlled delta from immutable R005:**

```text
Package m_dintHeight: 65.11 -> 65.81 mm
Package - negative-electrode axial margin: 0.00 -> +0.70 mm
```

**Observed client runtime log:**

```text
Read 5550 lines from F:\About-Energy\20260911\hp2170NCA-STAR-E004-ROOT-CLEARANCE-diagnostic-20260911\ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm

Read 5550 lines from F:\About-Energy\20260911\hp2170NCA-STAR-E004-ROOT-CLEARANCE-diagnostic-20260911\ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm

Feature execution failed.

Electrode Root 1 : Extrusion distance can not be 0.

Command: CreateFromTbm

   error: Server Error
```

**Observed error class:** `E004`.

### Runtime conclusion

ROOT_A and ROOT_B both produced the **identical E004**. Therefore:

- increasing only `Package m_dintHeight` enough to create **+0.10 mm** or **+0.70 mm** package-to-negative-electrode axial clearance is `PROVEN_INSUFFICIENT` to eliminate E004;
- the narrow form of H004-6 — *"the exact zero margin is itself the cause, and a small positive clearance should clear E004"* — is disproven;
- this does **not** prove that all package/layer axial-headroom relationships are irrelevant, because the new runtime-working reference below has much larger margins (+6/+8/+9 mm relative to separator/negative/positive layers).

Do **not** record H004-6 as globally `DISPROVEN_FOR_E004`. Correct status is:

```text
H004-6A_SMALL_POSITIVE_CLEARANCE = DISPROVEN / PROVEN_INSUFFICIENT
H004-6B_BROADER_AXIAL_STACK_OR_LARGE_HEADROOM_INTERACTION = UNRESOLVED
```

---

## `R008` — runtime-working client reference: `validationBattery21700.tbm`

The client supplied a TBM reported to work in STAR-CCM+:

```text
validationBattery21700.tbm
```

Local source SHA-256 used for the derived diagnostic campaign:

```text
41c23e28ef4548e1d74e487f48e5cc96fcfb0626df3792ebfa8ec7b09efc704a
```

This file is a high-value runtime control because it already uses the required active architecture:

```text
IET         = RCRTable 3D
Thermal     = Distributed
Electrolyte = General Electrolyte
Builder     = Detailed Builder
```

### Key working PCD relationships

```text
Package m_dintHeight                 = 65.00 mm
SeparatorList1_Separator m_dWidth_mm = 59.00 mm
-Electrode m_dWidth                  = 57.00 mm
+Electrode m_dWidth                  = 56.00 mm

Package - Separator = +6.00 mm
Package - Negative  = +8.00 mm
Package - Positive  = +9.00 mm
```

### Key working tab / Builder values

```text
+Electrode Tab m_dLength_mm          = 65 mm
-Electrode Tab m_dLength_mm          = 65 mm
+Electrode m_dS3                     = 5
m_dSepFeedLength_mm                  = 10
m_dSepTailLength_mm                  = 85
m_dElectrodeOverlapAtStart_mm        = 3
m_dElectrodeOverlapAtEnd_mm          = 40
m_dJellyrollThickness_mm             = 17.9
m_dMandrelWidth_mm                   = 0
m_nNegTabVertOrientation             = 1
```

### Immediate implications

1. `+Electrode m_dS3 = 5` exists in both the working reference and failed R005 lineage. It is not a useful discriminator for current E004 localization.
2. ROOT_B tested only +0.70 mm package-to-negative clearance, while the working reference has +8.00 mm. Therefore ROOT_A/B eliminate only the **small-clearance** version of H004-6.
3. The working reference has 65-mm tab lengths with 56/57-mm electrodes, whereas R005 has 60-mm tab lengths with 64.11/65.11-mm electrodes. This is a root-specific correlation worth controlled runtime testing, but public evidence does not prove `Tab m_dLength_mm - Electrode m_dWidth` is the proprietary extrusion formula.
4. The working reference provides a better base for reverse testing than a broad Siemens Builder transplant: start from a known-working TBM and introduce failing-project fields one at a time.

---

# Updated `E004` hypothesis ledger

| Hypothesis | New runtime evidence | Updated status |
|---|---|---|
| `H004-1` start overlap zero / insufficient overlap | prior 8-mm candidate still failed | `PROVEN_INSUFFICIENT_AS_SOLE_CAUSE` |
| `H004-2` `+Electrode m_dS3` | working reference also uses `+S3 = 5`; R005 failed at 5 | `DISPROVEN_AS_DISCRIMINATOR` |
| `H004-3` Transport Number sets | note cleared, E004 remained | `DISPROVEN_FOR_E004` |
| `H004-4` JR/can radial mismatch | exact-contact R005 still failed | `DISPROVEN_AS_SIMPLE_MISMATCH_CAUSE`; exact-equality interaction remains separately testable |
| `H004-5` separator feed/tail 0/0 | valid HP18650/HE18650 references allow 0/0; runtime-working 21700 uses 10/85 | `DOWNGRADED / CONTROLLED_RUNTIME_TEST_PENDING` |
| `H004-6A` exact-zero package/negative clearance fixed by small positive gap | ROOT_A +0.10 and ROOT_B +0.70 both fail identically | **`DISPROVEN / PROVEN_INSUFFICIENT`** |
| `H004-6B` broader axial-stack or large-headroom interaction | working reference has +6/+8/+9-mm margins; not yet isolated | **`UNRESOLVED / HIGH-VALUE CONTROLLED_TEST`** |
| `H004-7` tab/root dimensional relation | working ref: tabs 65, electrodes 56/57; R005: tabs 60, electrodes 64.11/65.11 | `UNRESOLVED / CONTROLLED_TEST_PENDING` |
| `H004-8` multi-field Detailed-Builder interaction | multiple visible Builder fields differ between working and failing TBMs | `UNRESOLVED / DOE_PENDING` |
| `H004-9` PCD/Builder/radial interaction | individual fields may be valid while their combination is not | `UNRESOLVED / DOE_PENDING` |

---

# Updated current blocker state

```text
ACTIVE_FATAL_BLOCKER = E004
MESSAGE = Electrode Root 1 : Extrusion distance can not be 0.
FIRST_OBSERVED = 2026-09-04
LAST_OBSERVED = 2026-09-14
RUNTIME_OCCURRENCES = multiple packages / multiple variants, including ROOT_A and ROOT_B
ROOT_CAUSE = UNRESOLVED
H004-6_SMALL_CLEARANCE_STATUS = PROVEN_INSUFFICIENT (+0.10 and +0.70 mm both identical E004)
BROADER_AXIAL_STACK_STATUS = UNRESOLVED
WORKING_RUNTIME_CONTROL = validationBattery21700.tbm
WORKING_CONTROL_SHA256 = 41c23e28ef4548e1d74e487f48e5cc96fcfb0626df3792ebfa8ec7b09efc704a
NEXT_METHOD = reverse DOE from runtime-working TBM toward R005
```

---

# `CAMPAIGN_PREPARED` — 2026-09-14 — 30-case high-resolution reverse diagnostic DOE

**Status:** PREPARED — runtime results pending.

**Source/control:** client-provided runtime-working `validationBattery21700.tbm`, SHA-256:

```text
41c23e28ef4548e1d74e487f48e5cc96fcfb0626df3792ebfa8ec7b09efc704a
```

**Package generated:**

```text
hp2170NCA-STAR-E004-30case-highres-diagnostic-20260914.zip
```

**Package SHA-256:**

```text
b76e4a610213bd3e86b2f337eefb64a392ca39eab61956b59f2f9842f70b66f9
```

### Design principle

All 30 diagnostics are generated independently from the **runtime-working file**. Each test moves one field or one carefully chosen interaction toward the failed R005 configuration. This reverses the earlier approach of modifying the failed project file toward Siemens values.

### Tier 1 — atomic PCD / envelope

- `A01` package internal height only
- `A02` separator width only
- `A03` negative electrode/coating/collector widths only
- `A04` positive electrode/coating/collector widths only
- `A05` positive tab length 65→60 only
- `A06` negative tab length 65→60 only
- `A07` both tab lengths 65→60
- `A08` external package height 70→70.02 only

### Tier 2 — axial/root interactions

- `I01` package + negative exact equality
- `I02` separator + negative
- `I03` negative + positive
- `I04` separator + negative + positive
- `I05` full project axial stack
- `I06` full axial stack + both 60-mm tabs
- `I07` package/negative equality + negative 60-mm tab
- `I08` full axial stack + external package height

### Tier 3 — atomic Builder tests

- `B01` feed 10→0 only
- `B02` tail 85→0 only
- `B03` feed/tail 10/85→0/0
- `B04` overlap start 3→8 only
- `B05` overlap end 40→20 only
- `B06` both overlaps 3/40→8/20
- `B07` mandrel width 0→6 only
- `B08` negative tab vertical orientation 1→0 only

### Tier 4 — radial tests

- `R01` package ID 20.9→20.6274 only
- `R02` JR diameter 17.9→20.6274 only
- `R03` exact `JR OD = package ID = 20.6274`
- `R04` package OD 21→21.09 only

### Tier 5 — composites

- `X01` full project radial group
- `X02` complete non-radial Builder-difference group

### Evidence rules for interpreting this campaign

- A single atomic failure is strong evidence that the changed field/relation is sufficient to reproduce E004 in the working template.
- Atomic passes plus an interaction failure localize E004 to that interaction, not to either field individually.
- If `R01` and `R02` pass but `R03` fails, exact radial equality is implicated.
- If all atomic Builder tests pass but `X02` fails, E004 is a Builder-field interaction.
- If all 30 diagnostics pass, the tested visible scalar geometry/Builder fields are insufficient to reproduce R005 E004; the next target becomes structural/context differences (block structure, duplicated Builder content, model sections, or hidden cross-block coupling).
- No diagnostic pass is automatically a production geometry solution.

---

## Supersession note

Where the parent canonical register still states:

```text
LEADING_HYPOTHESIS = H004-6
HYPOTHESIS_STATUS = CANDIDATE_PREPARED / RUNTIME_PENDING
```

that text is superseded by this addendum. ROOT_A and ROOT_B have now been runtime-tested and both failed with identical E004.

The narrow small-clearance formulation is disproven; broader axial/root/Builder interaction remains unresolved and is the subject of the 30-case reverse DOE.
