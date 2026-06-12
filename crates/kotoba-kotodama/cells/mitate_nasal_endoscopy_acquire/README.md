# mitate_nasal_endoscopy_acquire — Pregel cell for Hanami robot 鼻内視鏡撮影

Per **ADR-2605260145 §Decision 2** (condition 3 — chronic sinusitis endoscopy) +
**ADR-2605260160 §Decision 2** (condition 4 — septal deviation endoscopy).

Paired actor: [mitate](../../mitate/).

Murakumo node (proposed): **joseph** (commissioning / sterile process leader).

Robotics class: **Hanami (鼻見, mitate-native R2+)** — 4mm 軟性スコープ + 6-DOF arm,
force-feedback ≤0.5N, autoclave 滅菌対応. R0 placeholder; R2 deploy 前に mechanical design +
safety validation + FDA Class I/II medical device 同等 attestation 必要.

Output:
- 4K image (multi-frame) + 30-sec video of中鼻道 + 鼻茸有無 + 粘膜性状 + 弯曲 + spur
- Preliminary image classification (Murakumo only G12, gemma4:e4b vision distill medical variant G13)
- Licensed MD (ENT specialist) final attestation (G4 R2+ mandatory)
