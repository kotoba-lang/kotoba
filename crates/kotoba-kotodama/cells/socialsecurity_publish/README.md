# socialsecurity_publish - §1.16 Social Security pipeline (R0 scaffold)

Stage 4 (PUBLISH). Publish to atproto MST (ADR-2605231902): (a) minimal PII-free member record; (b) the **aggregate** Social-Security Metric (no PII); (c) the §1.16.9 public declaration as a durable record.

Per ADR-2605302358 (metric extends ADR-2605261000 §4 + 2605301020 §5). R0 scaffold — `cell.py` raises at import time until R2 (Council Lv7+ §1.16 ratify + feed-post membrane projection DID).

- **Pipeline group**: 産土 (ubusuna)
- **Murakumo node (proposed)**: naphtali
- **Gates**: G12 (aggregate-only, no leaderboard) · G6 (PII-free public artifacts) · G2 (kotoba-native read) · G13 (Transparent audit datom) · G11 (published=false pre-ratify)
- **Output Lexicon(s)**: com.etzhayyim.socialsecurity.metricReport (+ feed-post records)
- **Ceiling**: public artifacts are aggregate-only + PII-free; every publish audited (Transparent Force §1.12).
