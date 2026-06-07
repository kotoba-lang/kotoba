# kizashi_signal_fusion — kizashi (R0 scaffold)

fuse per-modality observations into a transient feature representation for the
attribution cell. Holds features transient-only; never writes plaintext feature
vectors to disk.

Per ADR-2605312700. R0 scaffold — `cell.py` raises at import time until R1
(Council Lv6+ ≥3 + encrypted-envelope backend live + modality ledger attested).

- **Actor**: kizashi (兆) — `did:web:kizashi.etzhayyim.com`
- **Murakumo node (proposed)**: gad
- **Gates**: G2 (biometric = 要配慮 PII, encrypted I/O) + G10 (only ledgered modalities fused) + G14 (Murakumo-only)
- **Output**: transient fused feature vector (consumed by kizashi_attribution)
- **Ceiling**: ENCRYPTED-ENVELOPE (G2, com.etzhayyim.encrypted.*, ADR-2605181100; no plaintext biometric flow) · Murakumo-only inference (ADR-2605215000)
