# kizashi_scan_session — kizashi (R0 scaffold)

orchestrate a non-invasive multimodal scan session — verify per-scan consent,
drive per-modality capture (R0..R2: non-ionizing non-regulated only), emit the
encrypted session attestation. **No hardware exists at R0/R1.**

Per ADR-2605312700. R0 scaffold — `cell.py` raises at import time until R2
(Council Lv6+ ≥4 + 30-day public + encrypted backend + medical-device
regulatory-pathway assessment filed).

- **Actor**: kizashi (兆) — `did:web:kizashi.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: G2 (biometric = 要配慮 PII, encrypted; 30-day rotating pseudonym DID) + G6 (per-scan consent, default-deny) + G4 (R0..R2 non-ionizing non-regulated only) + G11 (real scans = Council + licensed oversight + R3)
- **Output Lexicon(s)**: com.etzhayyim.kizashi.scanSessionAttestation
- **Ceiling**: ENCRYPTED-ENVELOPE (G2, ADR-2605181100) · CONSENT (G6) · DEVICE-BOUNDARY (G4) · Murakumo-only inference (ADR-2605215000)
