# loop-maturity-audit

**`manifest/repo-maturity.edn` の鮮度を所有する continuous orchestrator。**
propose-only — publish 権限は持たない。

```text
observe (repo-maturity.edn の computed-at と west.yml の project 数を測る)
  -> evaluate (stale 判定: 30 日 / entity 欠落)
  -> decide (再生成が必要か、部分再スコアで足りるか)
  -> act (生成コマンドを「提案」として出す — 実行はしない)
  -> record-evidence (append-only ledger)
```

## なぜ在るか

実測（2026-09-05）: repo-maturity.edn が 1 ヶ月 stale で **302 件の kotoba-lang path
が欠落していた**（amu/inga/kotoba-vm/machine/ioplan/vmm を含む — 改名・新規登録が
最終生成後）。maturity スコアに基づく判断が全て古い値で行われていた。この gap は
ADR-2809050100 の gap-1 として closed したが、**再発防止の構造が無かった**。
この loop がその構造。

## 鮮度の判定規則

| 測定 | stale 判定 |
|---|---|
| `:maturity/computed-at` が 30 日より古い | stale-by-age |
| west.yml の project 数 > edn の entity 数 | stale-by-drift（欠落あり） |
| どちらでもない | fresh |

**測れなかった測定を成功として報告しない**: 読めない/parse 失敗は
`:unmeasured` を返す。

## Run it

```bash
# superproject root から
kbb -Sdeps '{:paths ["../loop-maturity-audit/src"]}' \
  -M ../loop-maturity-audit/bin/audit.cljs
```

出力: fresh / stale-by-age / stale-by-drift + 欠落 repo 数 + 提案コマンド。
再生成は `kbb --backend sci scripts/repo-maturity.cljk`（GraphQL 214 バッチ、単独タスク）—
**この loop は実行しない**、提案だけ。

## 非目標

- 生成器の実行（GraphQL 全走査は時間がかかるため、恒久承認の下でも単独タスク）
- スコア軸の変更（それは scripts/repo-maturity.cljs の owner が行う）
