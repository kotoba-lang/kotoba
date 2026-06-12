# pharma_chiral_resolution cell

Pregel cell for enantiomeric separation (chiral resolution). Wave 1c flagship: omeprazole S-enantiomer isolation.

## Input Lexicon

`com.etzhayyim.pharma.purificationAttestation` with `scheme` in:
- `crystalline-resolution-mandelate` — L-mandelic acid salt crystallization (industrial precedent)
- `prep-hplc-chiral` — preparative HPLC with chiral stationary phase (Chiralcel OD-H, etc.)
- `SFC-supercritical` — supercritical fluid chromatography (deferred Wave 1c+)

## Output Lexicon

`com.etzhayyim.pharma.purificationAttestation` attestation with:
- `enantiomeric_purity_bp`: ≥ 9950 (99.50% target enantiomer, ≤ 0.50% unwanted enantiomer)
- `recovery_yield_bp`: typically 70-95% depending on method
- `outcome`: `"ok"` / `"rework-required"` / `"scrapped"`

## State Schema

```jsonschema
{
  "type": "object",
  "properties": {
    "methodDevelopmentStatus": { "type": "string", "enum": ["pending", "baseline-established", "scaling-qualified"] },
    "qualificationBatches": { "type": "integer", "minimum": 0, "description": "Minimum 3 batches for method equivalence proof" },
    "enantiomericPurityHistogram": { "type": "array", "items": { "type": "number" } }
  }
}
```

## Constitutional Gates (inherited from ADR-2605250500)

| Gate | Application |
|---|---|
| G2 (ICH Q3/M7) | Enantiomeric purity ≥ 99.5% (pharmacopoeial); unwanted enantiomer ≤ 0.5% (ICH M7 Class 5) |
| G3 (silen-pharma Council review) | scope: `wave-1c-chiral-resolution-baseline` required for R1 activation |
| G9 (witness N≥2) | operator DID + witness (QC analyst or sensor) |

## R0 Status

**Import-time RuntimeError gated** (silicon Wave 1 pattern). Activation requires:
- `COUNCIL_ATTESTATION_TX_HASH` → Council Lv6+ ≥ 3 multisig tx hash
- `SILEN_PHARMA_BASELINE_REVIEW_CID` → com.etzhayyim.pharma.silenPharmaReview record CID with verdict="approve" + scope="wave-1c-chiral-resolution-baseline"

## API References

### Wave 1c flagship: omeprazole

- CAS: 73590-58-6
- Molecular formula: C₁₇H₁₉N₃O₃S
- Racemate precursor synthesis: per Astra-Zeneca 1988 route (US Patent 4,058,635, expired)
- Target enantiomer: S-form (R-form inactive, ≤ 0.5% tolerance)
- Crystalline resolution: L-mandelic acid salt, ~70% yield fractional recrystallization (EtOH/H₂O)
- Prep-HPLC: Chiralcel OD-H, hexane/IPA (9:1), 20 min separation, ~98% purity

### Future Wave 1c+ candidates

- **levocetirizine** (S-isomer of cetirizine, more potent)
- **levofloxacin** (S-isomer of ofloxacin, topical/ophthalmic)

---

Per ADR-2605250615 §Decision 3.
