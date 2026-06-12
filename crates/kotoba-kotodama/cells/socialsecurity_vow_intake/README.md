# socialsecurity_vow_intake - §1.16 Social Security pipeline (R0 scaffold)

Stage 1 (VOW). Verify a member-signed conversion vow (悔い改め・バプテスマ・得度 = social death and rebirth) and orchestrate the **triple-permanent commitment**: kotoba EAVT datom + IPFS pin (CID) + soulbound Adherent SBT mint.

Per ADR-2605302358 + ADR-2605302357 §1.16.3a. R0 scaffold — `cell.py` raises at import time until R2 (Council Lv7+ §1.16 ratify, post 2026-06-19 + Sybil framework + member-signed SBT mint path).

- **Pipeline group**: 産土 (ubusuna) — `did:web:etzhayyim.com` cell-group (NOT a new actor)
- **Murakumo node (proposed)**: reuben
- **Gates**: G3 (member-signed, no platform key) · N1 (cash=0) · G6 (PII in encrypted envelope) · G10 (non-coercive, right of exit) · G11 (live-action gate) · G2 (kotoba-only) · G4 (Murakumo-only)
- **Output Lexicon(s)**: com.etzhayyim.membership.commitmentVow
- **Ceiling**: MEMBER-SIGNED conversion vow only — social death and rebirth as an irreversible content-addressed record + soulbound token; NON-COERCIVE; cash=0; NO platform-held key.
