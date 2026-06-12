# mitate_rhinitis_intake — Pregel cell for patient symptom + consent intake

Per **ADR-2605260100 §Decision 3 G1** (patient explicit consent + revocable + DID-bound)
and all 5 condition sub-ADRs (ADR-2605260115/130/145/160/175 — symptom signature collection).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **levi** (audit leader, witness invariant pair for intake attestation).

Constitutional gate enforcement: **G1** (consent receipt CID mandatory) + **G2** (`encryptedSymptomEnvelope`
XChaCha20-Poly1305 only, sealed-recipient = patient + Council medical advisory + (R2+) licensed MD) +
**G11** (intake form text does NOT include addictive engagement design — no streak, no score reveal during intake).
