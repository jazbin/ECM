ROOT CLEARANCE DIAGNOSTIC EXPERIMENT — hp2170 NCA / STAR-CCM+ TBM
Generated: 2026-09-11
Branch: tbm-rcr-modelmap-fix-exec
Contact: Bojan Vidovic / ECM Developer

==========================================================================
BACKGROUND
==========================================================================

Every TBM we have sent so far produces the same fatal error in STAR-CCM+:

    Electrode Root 1 : Extrusion distance can not be 0.
    Command: CreateFromTbm
    error: Server Error

The latest leading hypothesis (2026-09-11) is that STAR's internal electrode-root
construction requires a finite axial space between the package internal height
and the widest wound component (the negative electrode/collector at 65.11 mm).

In the R005 baseline (the last file you tested):

    Package m_dintHeight    = 65.11 mm
    Negative electrode width = 65.11 mm
    Package-to-negative clearance = 0.00 mm

The hypothesis: this exact-zero axial clearance collapses the extrusion distance
to zero, producing E004.

==========================================================================
THIS PACKAGE IS DIAGNOSTIC ONLY
==========================================================================

ROOT_A and ROOT_B are single-variable perturbation experiments.
They are NOT the production geometry.
Do not use either file for any purpose other than diagnosing E004.
If either passes CreateFromTbm, we will conduct a separate step to determine
the correct production package height before considering it final.

==========================================================================
IMMUTABLE BASELINE
==========================================================================

File: BASELINE_2c89d2d9.tbm (included for reference)
SHA-256: 2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5

This is the exact file from R005 (2026-09-10). Every other field in ROOT_A
and ROOT_B is byte-identical to this baseline.

==========================================================================
ROOT_A — FILE: ROOT_A_AXIAL_CLEARANCE_0p10.tbm
==========================================================================

SHA-256: c6db74313e675b618f2fb51d371e51231f9e0a2a9f26ca5bdc1f1bde48390343

Single change from baseline:
    Package m_dintHeight: 65.11 → 65.21 mm

Resulting axial margins (package internal height minus layer width):
    Package - Separator  = 65.21 - 67.11 = -1.90 mm  (separator protrudes, as intended)
    Package - Negative   = 65.21 - 65.11 = +0.10 mm  (was 0.00, now 0.10)
    Package - Positive   = 65.21 - 64.11 = +1.10 mm

Purpose: Test whether removing the exact-zero package-to-negative clearance
is sufficient to allow Electrode Root 1 to obtain a finite extrusion distance.

==========================================================================
ROOT_B — FILE: ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm
==========================================================================

SHA-256: 59f83aa875415d946b1ccb2b6f880a3a98a036e631e3d78993d14edfbbc9ee36

Single change from baseline:
    Package m_dintHeight: 65.11 → 65.81 mm

Resulting axial margins:
    Package - Separator  = 65.81 - 67.11 = -1.30 mm
    Package - Negative   = 65.81 - 65.11 = +0.70 mm
    Package - Positive   = 65.81 - 64.11 = +1.70 mm

These margins reproduce the package/layer proportions of the Siemens HE18650
reference cell while retaining our actual separator and electrode widths.
Purpose: If ROOT_A still fails, this tests whether a larger clearance (matching
a known-working reference geometry) can clear the blocker.

==========================================================================
WHAT TO DO
==========================================================================

Step 1: Run "Create from Tbm" on ROOT_A_AXIAL_CLEARANCE_0p10.tbm.

Step 2: Report the complete console/error output, including any messages
        before and after the Feature execution line.

    If ROOT_A passes CreateFromTbm:
        Proceed to the generated-part selection screen.
        Export the generated geometry or STEP file so we can inspect the
        JellyRoll, Can, and Cap relationships.
        No need to test ROOT_B yet.

    If ROOT_A reaches a DIFFERENT downstream error (not "Electrode Root 1"):
        Report the new error text. This also means E004 is cleared for ROOT_A.
        Proceed to ROOT_B only if we specifically ask.

    If ROOT_A produces the identical "Electrode Root 1 : Extrusion distance
    can not be 0" error:
        Test ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm and report its output.

Step 3: Return the complete STAR console/error text for each file tested.

==========================================================================
INTERPRETATION WE WILL APPLY
==========================================================================

ROOT_A passes:
    Strong evidence that exact-zero package-to-negative axial clearance
    collapses the electrode root construction.
    Next: determine the correct production package height; 65.21 mm is NOT yet
    approved as the final value.

ROOT_A fails, ROOT_B passes:
    The root requires a finite minimum construction allowance greater than
    0.10 mm. A bounded threshold search between 0.10 and 0.70 mm follows.

Both ROOT_A and ROOT_B fail with identical E004:
    The package-internal-height hypothesis is substantially downgraded.
    Next tests will be the Siemens-transplant discriminators already in the
    E004 campaign: C12 and C13.

==========================================================================
MANIFEST
==========================================================================

See ROOT_CLEARANCE_MANIFEST.csv for machine-readable field deltas and SHAs.
