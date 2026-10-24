# kami-mangaka-qa

> **Standalone SSoT.** Path: `orgs/kotoba-lang/kami-mangaka-qa`。
> ADR-2607165100（superproject `90-docs/adr/`）が設計正本。

Work-agnostic **manga QA / perception** — 退役 Python runtime（lg_mangaka の
`jump_benchmark_qa`、ghosthacker v10 世代）が持っていた有用資産の**可搬な正本**を
portable `.cljc` に移植した純粋レイヤ。I/O ゼロ、VLM 呼び出しは
`vision-fn (fn [prompt image-b64] → parsed-map|nil)` を注入する
langchain-clj 流の host-capability 方式。JVM / cljs / nbb で同じコードが動く。

## Namespaces

| ns | 中身 |
|---|---|
| `kami.mangaka.qa.axes` | QA 軸レジストリ: `:rubric8`（composeScene3d 由来 8 軸 + 知覚 `:facePresence`、0-1）/ `:heuristic`（v10 決定論 13 軸、0-10）/ `:jump`（Jump 誌基準 VLM 審査 8 軸、0-10）。`from-v10` / `->v10-key` で v10 score JSON（実サンプル: `mangaka-data/ghosthacker/resources/v10/v10-p00-score.json`、total 79.1「mid-tier (人気作)」）と相互運用。 |
| `kami.mangaka.qa.perception` | VLM prompt + parser: 顔カウント（実測で動く既定経路）/ 顔ボックス（backend の grounding 力に依存 — 量子化 gemma4 は空配列を返しがち、docstring 参照）/ コマ境界検出。 |
| `kami.mangaka.qa.geometry` | 純幾何: `overlap-area` / `bubble-clearance`（吹き出しが顔を覆っていないか — VLM 検出でも authored gaze box でも同じ式）/ `face-presence-axis` / `reading-order-violations`（右→左・上→下の読み順 QA）。 |
| `kami.mangaka.qa.score` | 集約: `aggregate-score`（0-1 軸 → 0-100、品質ループの `:panel/score` と同スケール）/ `mean10` / `merge-perception-axes`。 |

## 移植方針（正直な範囲宣言）

- **移植した**: 軸の意味・scale・キー対応（snake→kebab）、score record の互換
  正規化、知覚 prompt + parser、幾何 QA、集約。
- **移植していない**: Python 側のピクセル heuristic 実装（`brightness_avg` 等の
  計測）と v10 の重み付き合成（重み定義は退役 runtime と共に失われた —
  **保存された total は素通しし、重みを捏造しない**）。計測値は consumer が
  供給する。
- 消費者第 1 号は `gftdcojp/ai-gftd-mangaka`（`mangaka.perception` が本 lib に
  委譲、品質ループの `:facePresence` 軸・`detectFaces` NSID）。

## Dev

```bash
kbb -M:test   # cognitect test-runner
kbb -M:lint   # clj-kondo
```

Sibling: `kami-mangaka-expression` / `-text` / `-page` / `-scene` / `-render` / `-reader`。
