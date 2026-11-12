# oracle/ — .cljc ファイルシステム・オラクル（使い捨て計測）

このディレクトリは使い捨ての計測オラクルです。CI・gate・ビルド・パッケージング・実行経路に組み込まないでください。native の結果がこのオラクルに黙って戻る fallback は作りません。

## 構成

- [fs_datom_adapter.cljc](fs_datom_adapter.cljc) — ファイルシステム形 API（read/write/list/exists/delete）を datom plane で提供する正本。`kotoba.lang.fs` の `IFilesystem` と同じ形で、読みは検証済みブロックの range-pruned index から返す設計です。本番の配線は `ayatori.remote/open-snapshot` + `q`/`q-async`（可視性 `visible?` は呼び出し側が明示）で、このファイルは依存を持ちません。
- [fs_bench.mjs](fs_bench.mjs) — 旧ハーネス（shell-git arm）。記録は残すが、bench 用途では後継に置換済み。新規実行は下の kgit 版を使うこと。
- [kgit_adapter.cljc](kgit_adapter.cljc) — kotobase/awai-fs 前提の git（blob/tree/commit、in-process、spawn ゼロ、digest ピン留め読み）。bonsai（`git_object`/`git_codec`）を縫い目とし、bb/nbb 下で動く依存なし `.cljc` に最小移植したもの。
- [fs_bench_kgit.mjs](fs_bench_kgit.mjs) — 正規ハーネス。git arm を kgit に置換済み（既定）。旧 shell-git arm は `KGIT_REAL=1` でのみ control として実行する。XCHECK（kgit OID・bytes と real git の照合）は既定で小 n のみ、`KGIT_XCHECK=1` で全サイズに強制する。
- [RESULTS-20261108.md](RESULTS-20261108.md) — 実行記録（コマンド・版・入出力・日付）。

## scope 決定（2026-11-08、JUN-1037）

- bench 用途の git arm は kgit が正規。shell-git は control（`KGIT_REAL=1`）のみに格下げする。
- gc / pack-expiry は scope 外。oracle は op 単位の等価性と費用の計測であり、lifecycle 機構を持たない。各 run は scratch で、保持は到達可能性に任せる想定のため。
- 3-way content merge は scope 外。merge は parents vector（0/1/N）による表現可能性までで、algorithm は持たない。必要になれば別 issue 化する。

## 4 バックエンドの対応（発見ベース）

1. host：mac 実ファイルシステム（`node:fs`）。`kotoba.lang.fs-host/host-filesystem` の考え方（`:root` に拘束）と同じです。
2. awai：`network-awai-apex` に単体の fs 名前空間は見つかりませんでした（`awai.apex.db` はアプリ状態）。共有アーキテクチャ契約（origin は静的な検証済み成果物の配布のみ）に従い、sha256 ピン留め読みの overlay として模しています。ギャップとして残します。
3. datom：本タスクの新規実装（この `oracle/` の adapter 移植）。datom は `{:s path :p :fs/path/:fs/content :o ...}` で、読みは `:fs/path` index の 1 round trip、list は prefix range scan の 1 round trip です。`kotobase.query.bridge` の契約（呼びの言語が Datalog 形なら Datalog が正しい frontend）に沿い、`ayatori.remote/q` が適合します。`kotobase.core` / `datomic.client.api` の該当実装は ayatori・kotobase の src に見つからなかったため、`ayatori.remote` 経路を正とし、ギャップとして残します。
4. git：`git-workspace` は repo/forge カタログの read-model で fs 機構ではありませんでした。機構自体（`git hash-object -w` / `git cat-file -p` の実バイナリ）を数えています。ギャップとして残します。

## 実行

```sh
node oracle/fs_bench_kgit.mjs --sizes=16
```

正規ハーネスは kgit 版（git arm = kgit が既定）。旧 `oracle/fs_bench.mjs`
は記録として不変で、新規実行には使わない。

主要指標は操作/round-trip 数です。wall clock は負荷のかかった機械の数値であり、輸送の評価には使いません（`bench/fitness.cljk`・`bench/benchmark.edn` v1 の除外と同じ）。

## コード優先の報告

- ドキュメントとコードの不一致：`kotoba.lang.fs` README は「every namespace is `.cljc`」と書いていますが、実コードは `src/kotoba/lang/fs.cljk`（`.cljk`）です。コードを優先し、adapter は `.cljc` オラクルとして `oracle/` 直下に置いています（native が `.cljc` を受け付けるのは project 直下 `oracle/` のみ、という規則に従います）。
