# pharma_liquid_formulation cell

Pregel cell for oral liquid formulation (syrup, solution, suspension) fill-finish and packaging. Wave 1c scope: cough-expectorant (guaifenesin, benzonatate) syrups + laxative solutions.

## Input Lexicon

`com.etzhayyim.pharma.fillFinishAttestation` with `dosageForm` in:
- `oral-liquid-syrup` — cough-expectorant (guaifenesin 100 mg/5 mL, benzonatate suspension)
- `oral-suspension` — laxative solution (docusate, PEG 3350 post-reconstitution)

## Output Lexicon

`com.etzhayyim.pharma.fillFinishAttestation` attestation with:
- `unitsProduced`: number of bottles filled
- `outcome`: `"pass"` / `"fail"` / `"quarantined"`
- QC compliance: microbial limit USP <61>/<62>, viscosity, pH (if applicable)

## State Schema

```jsonschema
{
  "type": "object",
  "properties": {
    "fillLineStatus": { "type": "string", "enum": ["setup", "running", "cleaning", "idle"] },
    "productionLogs": { "type": "array", "items": { "type": "object" } },
    "viscosityHistogram": { "type": "array", "items": { "type": "number" } }
  }
}
```

## Constitutional Gates (inherited from ADR-2605250500)

| Gate | Application |
|---|---|
| G2 (ICH Q3/M7) | Guaifenesin / benzonatate purity ≥ 98% (pharmacopoeial); residual solvent ≤ Class 3 limits (ICH Q3C) |
| G3 (silen-pharma Council review) | scope: `wave-1c-cough-syrup-formulation-baseline` (cough) or `wave-1c-laxative-formulation-baseline` (laxative) |
| G9 (witness N≥2) | operator DID + QP-equivalent DID |
| G11 (wellbecoming subordination) | Label warnings: benzonatate chewing/sucking risk; laxative electrolyte loss warnings |

## Non-Sterile QC Requirements

- **Microbial limit** USP <61>/<62>: TAMC ≤ 10³ CFU/mL, TYMC ≤ 10² CFU/mL, no pathogens
- **Viscosity** (syrups): cone-plate rheometer at 25°C; typical 50-200 cP for cough syrups
- **pH** (solutions): typically pH 4-6 (guaifenesin), pH 5-7 (benzonatate suspension)
- **Appearance** (suspensions): no visible particles, uniform color, no phase separation after shake

## R0 Status

**Import-time RuntimeError gated** (silicon Wave 1 pattern). Activation requires:
- `COUNCIL_ATTESTATION_TX_HASH` → Council Lv6+ ≥ 3 multisig tx hash
- `SILEN_PHARMA_BASELINE_REVIEW_CID` → com.etzhayyim.pharma.silenPharmaReview record CID with verdict="approve" + scope in [wave-1c-cough-syrup-formulation-baseline, wave-1c-laxative-formulation-baseline]

## API References

### Cough-expectorant syrups (Wave 1c)

**Guaifenesin**
- CAS: 93-14-1
- Typical OTC formulation: 100 mg / 5 mL syrup (20 mg/mL)
- Excipients: glycerin, sorbitol, propylene glycol, FD&C colorants, water

**Benzonatate**
- CAS: 104-31-4
- Typical OTC formulation: 100-150 mg / 5 mL suspension (20-30 mg/mL)
- Excipients: xanthan gum (thickener), glycerin, sorbitol, water, flavoring

### Laxative solutions

**Polyethylene glycol 3350 (PEG 3350)**
- Typical OTC: 4 g / sachet, reconstituted in 240 mL water → 16.7 mg/mL final concentration
- Post-reconstitution fill-finish: N/A (end-user reconstitutes)

**Docusate sodium liquid**
- Typical OTC: 50-100 mg / 5 mL solution
- Excipients: glycerin, propylene glycol, purified water

---

Per ADR-2605250615 §Decision 4.
