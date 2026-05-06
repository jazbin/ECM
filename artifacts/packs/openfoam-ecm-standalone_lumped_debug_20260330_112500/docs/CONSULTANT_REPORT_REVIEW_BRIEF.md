# Consultant Report Review Brief

## Purpose

This pack is for reviewing how to turn the current OpenFOAM↔ECM project evidence into a strong comprehensive internal report, and then later into a cleaner client-facing report.

The main need is not more raw data generation. The main need is figure and narrative curation.

## What We Need From Review

Please review the included code, logs, report drafts, and curated image set, and provide recommendations on:

1. Which figures should appear in the main report body.
2. Which figures should be moved to appendices only.
3. Which figures should be dropped entirely.
4. What additional plots or section types are still missing.
5. How the report should explain:
   - lumped vs distributed comparison
   - accepted shared-state distributed baseline
   - overlap-weighted mapping
   - time stepping / interpolation / applied-source smoothing
   - runtime/performance engineering decisions
6. How to restructure the current internal-style body into a more polished client-facing report later.

## Important Context

- The accepted comparison baseline is the distributed **shared-state** model, not the earlier rejected per-partition electrical formulation.
- The overlap-weighted mapping work is newer than the accepted forward-validation baseline and should be presented clearly as newer work, not blended carelessly into the validated baseline story.
- The client is technically strong and is expected to want mapping and implementation detail, but still in a curated and interpretable form.

## Known Figure Problems

These are the current known problems that should be kept in mind during review:

1. Some section views normal to the cylinder axis were initially chosen at poor heights and therefore cut through regions with no meaningful support for the plotted field.
2. Some mapping images were technically correct but visually unhelpful because they showed raw implementation detail without enough explanatory value.
3. One earlier time-stepping/interpolation figure over-emphasized the older problematic subcycling mode instead of the currently accepted implementation.

## Included Material

This pack includes:

- report structure and draft text
- key status/assumption files
- accepted validation summaries
- selected session/chat context
- key solver/coupler logs
- figure-generation scripts
- key coupling code paths
- a curated report image set with stable names and a manifest

## Desired Output

Please provide:

- a recommended final figure list
- a recommended appendix figure list
- a drop list
- any missing figure recommendations
- any changes you would make to the report story/order
- any specific comments on how to explain the mapping and time-stepping behavior clearly

