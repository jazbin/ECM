# T06 Input Provenance — S0 Robert Package

**Date established:** 2026-09-18

## Identified file

`T06_TARGET_AXIAL_SURPLUS_2p00.tbm`

**SHA256:** `433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71`
**Size:** 204547 bytes

Copied unmodified into `artifacts/equivalence/robert_s0/input/T06_TARGET_AXIAL_SURPLUS_2p00.tbm`.

## Source locations (all byte-identical, verified by SHA256)

| Location | SHA256 |
|---|---|
| `in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip` → `hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914/T06_TARGET_AXIAL_SURPLUS_2p00.tbm` | `433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71` |
| `in/20260914/client_v2/T06_TARGET_AXIAL_SURPLUS_2p00.tbm` | `433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71` |
| `in/20260914/root_surrogate_30case/T06_TARGET_AXIAL_SURPLUS_2p00.tbm` | `433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71` |

All three copies of the TBM are the same file — no ambiguity between the two
loose `in/20260914/` directories and the processed zip; they all trace to one
canonical TBM.

## Relationship to the returned T06 STEP used in the exact B-Rep audit

The same processed zip also contains
`T06_TARGET_AXIAL_SURPLUS_2p00.step` (SHA256
`c17506dc5aab108fd11dd47390a2eb0ab79c2ce5c6c8654f5544f83dc75831dd`,
136340 bytes) as a matched pair alongside the TBM above, both inside the same
zip entry directory. This is the exact STEP geometry used for the B-Rep
overlap audit in `docs/equivalence/T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`
(referenced there as extracted "from
`in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip`
(client-returned, not regenerated)"). The `.tbm` copied into this package is
the TBM that generated that STEP — i.e. this is the exact known-good input
that produced the returned geometry already analyzed, not a re-derivation.

## Not regenerated

This TBM was not modified, rebuilt, or re-exported for this package. It is a
direct byte copy of the file already present in the repository's client-return
archive.
