# pharma_tablet_manufacture — Pregel cell for non-sterile oral solid manufacture

Per **ADR-2605250600 Wave 1b** §Decision 2 (new dosage form: oral tablet / capsule).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **joseph** (commissioning leader; non-sterile clean room class C — sterile fill-finish の一段低い grade).

Scope:
- Oral immediate-release tablet (uncoated, film-coated, enteric-coated)
- Hard gelatin capsule (Wave 1b 内 deferred unless adherent demand)

Wave 1b API → tablet product:
- Acetaminophen 500 mg tablet
- Aspirin 325 mg / 500 mg tablet
- Ibuprofen 200 mg / 400 mg tablet
- Diphenhydramine HCl 25 mg / 50 mg tablet
- Cetirizine 2HCl 10 mg tablet
- Loratadine 10 mg tablet
- Famotidine 10 mg / 20 mg tablet

Process: pre-blending → granulation (wet / dry) → drying → milling → final blending →
compression → coating (optional) → blistering / bottling.

Annex 1 G8 sterile process validation 適用外 (non-sterile dosage form)。
代わりに USP <61>/<62> microbial limit + <701> disintegration + <711> dissolution +
<905> content uniformity + <1216> friability の non-sterile QC suite が
`pharma_qc` cell 内で auto dispatch される。

Constitutional gate G11 (wellbecoming label) は API ごとに差異あり:
- acetaminophen: hepatotoxicity warning (single-dose 4 g cap)
- aspirin: Reye 症候群 (< 18 yr) 警告
- ibuprofen: GI / renal / 妊娠後期 動脈管警告
- diphenhydramine: sedation / 運転禁止 警告
- cetirizine / loratadine: drowsiness possible (2nd gen 低 sedation)
- famotidine: H2 antagonist long-term use 警告 (B12 absorption etc.)
