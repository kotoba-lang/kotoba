# mitate_paranasal_ct_route — Pregel cell for 副鼻腔 CT 外部 facility routing

Per **ADR-2605260145 §Decision 3** (condition 3 — chronic sinusitis CT routing).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **simeon** (commissioning leader; imaging facility coordination).

CT 機器は mitate community center に無し ― 外部 imaging facility (放射線科 / 耳鼻科 connected clinic)
への routing。Order payload via `mitate.diagnosticOrder` lexicon、DICOM 受領 → XChaCha20-Poly1305
envelope (G2)。Lund-Mackay スコア (0-24) を licensed MD が attestation で記入。

Jurisdiction-aware (PMDA / FDA / EMA で imaging facility 規制差) ― initial deploy = JP only。
