# mitate_medication_history_audit — Pregel cell for OTC vasoconstrictor connect-the-dots

Per **ADR-2605260175** (condition 5 rhinitis medicamentosa) +
**ADR-2605260100 §Decision 8** (yakushi cross-actor lexicon emit boundary).

Paired actor: [mitate](../../mitate/) ↔ yakushi.

Murakumo node (proposed): **levi** (audit pattern, mirror of yakushi adverseEventReport).

Detection logic:

- 血管収縮 INN (naphazoline / oxymetazoline / tramazoline / phenylephrine) ≥ 7 日連用 → 条件 5 flag = true
- ≥ 14 日連用 → severity = "high"、即離脱支援 prioritized advisory
- yakushi-produced lot detected (lot ID match) → aggregated signal feed to yakushi `pharma_post_market_surveillance`
  (G7 + G10 enforcement — no individual patient identity in feed)

Constitutional invariant: **yakushi side label warning 強化 trigger の唯一の input data path** ―
religious-corp 内 self-care substrate の最初の完結した closed-loop (ADR-2605260175 Decision 4).
