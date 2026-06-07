# mitate_emergency_screen — Pregel cell for G5 fail-safe emergency keyword detection

Per **ADR-2605260100 §Decision 3 G5** (emergency keyword detection → 即 ER routing fail-safe;
bypass 不可 architectural invariant).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **levi** (audit-tier critical path).

**Architectural invariant**: this cell MUST run between `mitate_rhinitis_intake` and any
triage / order / treatment cell. Bypassing via direct cell-to-cell wiring is a constitutional
violation per ADR-2605260100 §G5 (fail-safe inviolability).

Red-flag categories (multi-language regex + LLM second-pass via Murakumo only, G12):

- 急性アナフィラキシー徴候 (anaphylaxis): 喉頭浮腫 / 喘鳴 / 急速広範蕁麻疹 / 血圧低下
- 眼窩蜂窩織炎 (orbital cellulitis): 片側眼球突出 / 眼球運動制限 / 視力低下 / 発熱
- 鼻中隔膿瘍 (septal abscess): 鼻中隔膨隆 / 高熱 / 鼻中隔疼痛
- 髄膜炎徴候 (meningitis): 項部硬直 / 高熱 / 意識障害 / 光過敏
- 海綿静脈洞血栓症: 急性片側眼球症状 + 顔面感覚異常
- 視力低下 / 意識障害 / 突然の重度頭痛 (general red-flag)

False negative の adversarial testing baseline は R1 deploy 前 Council 必須 (cell.py gate).
