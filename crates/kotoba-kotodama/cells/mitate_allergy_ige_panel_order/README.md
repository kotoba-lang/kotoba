# mitate_allergy_ige_panel_order — Pregel cell for View39-equivalent IgE panel ordering

Per **ADR-2605260115 §Decision 2** (condition 1 — allergic rhinitis perennial: IgE panel routing).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **naphtali** (procurement / 検体 cold-chain logistics leader).

Order routing: external clinical lab (DID-registered), antigen scope = perennial set
(Dermatophagoides-farinae / Dermatophagoides-pteronyssinus / Fel-d-1 / Can-f-1 /
Aspergillus / Alternaria / Cladosporium / Penicillium + 季節性 reference Cry-j-1/2 / Hag-r-1 等).

G2 mandatory: `mitate.diagnosticResult` returned in XChaCha20-Poly1305 envelope, sealed-recipient = patient
+ Council medical advisory + licensed MD-in-loop DID.

G4 mandatory (R2+): licensed MD attestation co-sign on order issuance.
