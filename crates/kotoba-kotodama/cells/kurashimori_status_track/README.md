# kurashimori_status_track — kurashimori (R0 scaffold)

track a dispatched remedy's outcome — merchant response / refund / window-expiry
clock; on stall, flag for escalation → `statusTrack`.

Per ADR-2605312500. R0 scaffold — `cell.py` raises at import time until R2.

- **Actor**: kurashimori (暮らし守) — `did:web:kurashimori.etzhayyim.com`
- **Murakumo node (proposed)**: naphtali
- **Gates**: G6 (outcome PII encrypted) + G10/G11 (track only, no harassment follow-up)
- **Output Lexicon(s)**: com.etzhayyim.kurashimori.statusTrack
- **Ceiling**: PII only in com.etzhayyim.encrypted.* (ADR-2605181100) · TRACK-ONLY / NON-HARASSMENT · Murakumo-only (ADR-2605215000)
