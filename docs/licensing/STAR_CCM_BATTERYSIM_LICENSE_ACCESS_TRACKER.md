# STAR-CCM+ Batteries / `batterysim` Licence Access Tracker

**Purpose:** Track every attempt to obtain short-term commercial access to Simcenter STAR-CCM+ with the **Batteries / `batterysim`** entitlement required for the TBM validation campaign.

**Last updated:** 2026-10-01

## Hard requirement

Generic STAR-CCM+ access is **not sufficient**.

The required access must allow, at minimum:

- full interactive STAR-CCM+ GUI;
- STAR-CCM+ Batteries / Battery Simulation functionality enabled;
- `batterysim` licence feature available;
- import/use of our own Battery Design Studio `.tbm` file;
- generation of the corresponding battery geometry/model;
- STEP export;
- enough access time for a short validation campaign and a minimal runtime test.

Preferred duration: **a few hours to one working day**.

The current BLOCK 01 radial campaign is already prepared offline; licence access is the only external blocker.

---

## Current status

### Flowthermolab — FAILED / REFUND INITIATED

Flowthermolab was asked **before purchase** whether its hourly STAR-CCM+ POD access included the Batteries / `batterysim` feature.

The requirement was repeated explicitly before pricing:

> STAR-CCM+ with the required Batteries / Battery Simulation functionality enabled.

Flowthermolab then offered:

- Option 1: STAR-CCM+ licence only — USD 30/hour;
- minimum initial allocation: 10 hours;
- licence usable on our own machine.

A quote was issued and paid.

After access was provisioned, STAR-CCM+ showed that the Battery model was unavailable because the required Battery licence was missing.

Flowthermolab subsequently confirmed that its current licence does **not** include the Battery module. It stated that Siemens requires a significant additional purchase and at least **100 hours** of usage to add the required functionality. Flowthermolab initiated a full refund.

**Outcome:** unusable for this project under their current entitlement.

**Important commercial lesson:** Never accept a provider's statement that it offers "STAR-CCM+ POD" as sufficient. Require explicit written confirmation that the actual entitlement contains **Batteries / `batterysim`**.

---

## Outreach log

| Date | Provider / Route | Status | What was asked / learned | Next action |
|---|---|---|---|---|
| 2026-09-xx to 2026-10-01 | **Flowthermolab** | **FAILED / refund initiated** | Explicitly requested STAR-CCM+ POD with Batteries / `batterysim`. Provider quoted 10 h access, but supplied entitlement without Battery. After checking with Siemens, provider said adding Battery requires significant additional cost and at least 100 h. | Do not rely on this route unless Flowthermolab reverses position and supplies the originally requested entitlement. |
| 2026-10-01 | **Rescale** | **NO — route closed** | Rescale was contacted specifically about its provided STAR-CCM+ On-Demand licence and whether it includes the Batteries / `batterysim` entitlement. The response did not provide a usable Batteries-enabled route for this project. | Do not spend more time on Rescale for the current TBM campaign unless their licensing offering changes. |
| Prior research | **ITCR, Zagreb** | Researched; no confirmed successful entitlement | Identified as a local Siemens/Simcenter route. | Revisit only with an explicit written `batterysim` entitlement question. |
| Prior research | **Volupe** | Researched | Siemens simulation partner; possible trial/evaluation route. | Contact if Rescale cannot provide Batteries. |
| Prior research | **TechSim Engineering CEE** | Researched | Regional Siemens/Simcenter route. | Contact if needed. |
| 2026-10-01 | **TrampoCFD** | **EMAIL SENT — awaiting response** | Asked about short-term STAR-CCM+ access and specifically whether the supplied entitlement includes the Batteries / `batterysim` feature required for the TBM workflow. | Await explicit written confirmation of `batterysim` entitlement and any minimum purchase / pricing conditions. |
| Prior research | **Rescale** | Now contacted | Public documentation indicates Rescale-provided STAR-CCM+ On-Demand licensing exists, but Batteries entitlement is not publicly confirmed. | See 2026-10-01 outreach above. |
| Prior research | **Siemens direct** | Not yet exhausted | Potential route for a Batteries-enabled evaluation entitlement or referral to an authorized provider. | Use if Rescale does not confirm suitable access. |

---

## Rescale enquiry — 2026-10-01

**To:** `sales@rescale.com`  
**CC:** `support@rescale.com`

**Subject:** Simcenter STAR-CCM+ On-Demand access with Batteries / `batterysim`

The enquiry asks Rescale to confirm specifically whether its **Rescale-provided STAR-CCM+ On-Demand licence** includes the **Batteries add-on / `batterysim`** feature.

It also asks whether:

- our own `.tbm` file can be uploaded and used;
- the workstation exposes the full interactive STAR-CCM+ GUI;
- short-duration usage is possible;
- there is any minimum licence purchase or commitment;
- software and compute are charged separately and at what approximate rates.

**Outcome:** Rescale did not provide a usable Batteries / `batterysim` route. Marked closed for the current campaign.

---

## Qualification rule for any future provider

A provider is **not qualified** merely because it offers:

- STAR-CCM+;
- STAR-CCM+ POD;
- STAR-CCM+ Power Session;
- an interactive STAR workstation;
- Battery Design Studio;
- a generic STAR trial.

Before paying or provisioning, obtain explicit written confirmation equivalent to:

> The supplied STAR-CCM+ entitlement includes the Batteries / Battery Simulation add-on and the `batterysim` licence feature required to use the native battery workflow and import/create from the supplied `.tbm` file.

If the provider cannot confirm this exact point, mark the route **UNVERIFIED**.

---

## Preferred acquisition paths

1. **Rescale-provided STAR-CCM+ On-Demand + interactive workstation**, if `batterysim` is included.
2. **Siemens direct evaluation entitlement** with Batteries explicitly enabled.
3. **Established Siemens simulation partner** willing to issue a short Batteries-enabled evaluation licence.
4. Another legitimate PAYG provider only after explicit written confirmation of `batterysim`.

Avoid spending time on generic STAR-CCM+ trial offers unless Batteries is confirmed in advance.

---

## Immediate next action

Wait for **TrampoCFD**.

If TrampoCFD confirms Batteries / `batterysim`:
- verify GUI + `.tbm` import capability;
- obtain exact pricing/minimum commitment;
- run a minimal entitlement smoke test before starting the prepared 23-case BLOCK 01 campaign.

If TrampoCFD cannot provide `batterysim`:
- contact Siemens directly and request a short Batteries-enabled evaluation entitlement;
- in parallel contact one or more established Siemens simulation partners with the same gating question.

---

## Evidence to preserve

For every provider, save:

- initial enquiry;
- exact entitlement confirmation;
- quotation;
- licence terms / minimum commitment;
- payment proof if applicable;
- screenshot/log showing whether Battery is enabled;
- support case/reference number;
- final outcome.

This tracker should be updated immediately after every new provider reply or licence test.
