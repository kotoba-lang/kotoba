# elv_parts_harvest — hodoki L3a (R0 scaffold)

Reusable parts identification + condition grading + IPFS-pinned bilingual parts catalog with VIN provenance.
Per ADR-2605261215 §6 L3a. R0 scaffold — `.solve()` raises until R1.

- **Murakumo node**: simeon
- **Lexicon (output)**: `com.etzhayyim.hodoki.partsHarvestCatalog`
- **Constraints**: **G12 RIGHT-TO-REPAIR INVARIANT (constitutional first)** — every part has part DID + VIN provenance + condition grade + bilingual description; G4 JP+EN bilingual; N8 chop-shop refusal (parts cannot be used to forge identity of a different vehicle)
