# loop-os-stack-observe

**OS スタックの成熟度を毎週 3 索引で再測定し、hardware spec を検証済み datom として
`machine` / `ioplan` に取り込み、ADR-2809050100 の gap ledger を所有する continuous
orchestrator。propose-only — publish 権限は持たない。**

```text
observe (3 索引: concept-lookup / repo-search / repo-maturity)
  -> evaluate (gap ledger の :gap/status 遷移判定)
  -> decide (1 件の次の tranche を選ぶ)
  -> act (descriptor 生成 + machine.core/validation-errors round-trip)
  -> record-evidence (append-only ledger)
```

`loop-*` per `kotoba-lang/loop-ux-kaizen` `resources/repository-rules.edn`
taxonomy: この repo は ordering と gap ledger を所有する。**hardware facts の正本は
`kotoba-lang/machine`（T5 contract）と `kotoba-lang/ioplan`** — ここでは複製しない。

## なぜ在るか

ADR-2809050100 が OS+browser stack の計画を gap ledger に置いた。gap の在り方は
3 索引（`kbb --backend sci scripts/concept-lookup.cljk` / `kbb --backend sci scripts/repo-search.cljk` /
`manifest/repo-maturity.edn`）を引いて初めて測定できる — prose の「探してから結論
せよ」を機械化したのがこの loop である。実測（2026-09-04、規則が生まれた日）では
agent が 3 回「無い」と誤答し、3 回とも 1 コマンドで見つかった。

## Gap ledger

`resources/gaps/gap-ledger.edn` — ADR-2809050100 §6 の依存順:

| gap | status | 備考 |
|---|---|---|
| repo-maturity 再生成 | :closed | 2026-09-05, 4264/4264 (superproject `b596f2d`) |
| UEFI/NVMe/USB/Wi-Fi/ext4 specs | :closed | 2026-09-05 tranche 1 (machine `d045768`) |
| Wayland protocol corpus | :open | 0 repo 測定済み |
| Unicode normalization + text shaping | :open | 0 repo |
| linker/ELF surface | :open | kotoba-native 0.935 は隣接だが別層 |
| Wi-Fi chipset 個別 probe | :open | 802.11ax 汎用は :assumed、実 chipset は host probe 待ち |

`closing requires the three-index re-run to show a hit` — 閉じるには再測定で
hit が出ることが条件。

## Tranche 1 の手本（機構）

descriptor 生成は `machine.core` の閉じた key set に従い、**provenance を捏造しない**:

```clojure
{:format :kotoba.machine/v1
 :machine/id "reference-x86-64-nvme"
 :machine/provenance :vendor-declared   ;; 規範値。spec 内で選んだら :assumed
 :machine/source "NVM Express 2.0 §3.1.2 logical block 4KiB; §4.6 queue pairs"
 ...}
```

1 回目の生成は `machine.core/validation-errors` で 3–5 件弾かれた — それが検査が
機能している証拠。全件 `:VALID` になってから着地する。

## Run it

```bash
# west workspace で machine が sibling として checkout されていること
kbb --backend sci --classpath "../machine/src:src" bin/run.cljk
```

observe は superproject ルートの 3 索引を実行し、evaluate は gap ledger を読み、
act は次の open gap の tranche 1 descriptor を生成して validation まで回す。
結果は `ledger/` の append-only ledger に積む。

## 非目標

- publish 権限（governor 迂回は禁じられている — 提案までで止める）
- host probe の実行（それは host effect であり machine がそれを拒む設計）
- machine/ioplan のロジック複製
