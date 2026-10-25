# ADR-0001: kagitaba architecture(1Password 互換キーチェーンデータモデル)

**Status**: accepted · **Date**: 2026-07-02 · **Deciders**: Jun Kawasaki

正本は superproject の `90-docs/adr/2607023000-kagitaba-1password-keychain-cljc.md`。
本書はリポ内サマリ。

## Decision

1. **kagi(-clj)と分離**: PQC crypto / governed vault actor は kagi に残す。kagitaba は
   「1Password と構造的に互換な item をどう表現するか」だけを担う zero-dep `.cljc`
   ライブラリ。kagi は kagitaba item を `pr-str` して自分の DEK 封緘パイプラインに
   通すだけで、kagitaba 自身は crypto/store に一切依存しない。
2. **category taxonomy**(`kagitaba.category`): `categoryUuid`(1Password 001〜114)
   ⇄ 正準 keyword。公式ドキュメントは `001`(Login)の例しか公開していないため、
   実 export + 独立 OSS 1PUX パーサ実装(`import-1p-to-pass` の `src/category.rs` 等)
   と突き合わせて検証。未知 uuid は `:category/<uuid>` にフォールバックし、
   データを絶対に落とさない。
3. **field 型システム**(`kagitaba.field`): 1PUX の tagged-union value(`{"concealed":
   "..."}` 等)をそのまま正準 keyword 化。`sensitive-types` =
   `#{:concealed :totp :credit-card-number :ssh-key}` を機微フィールドの判定基準にし、
   呼び出し側(kagi)の暗号化境界と揃える。
4. **item shape**(`kagitaba.item`): overview/details/sections/fields を素の EDN に
   フラット化。`valid?` は最小限の構造検証のみ(spec ライブラリ非依存)。
5. **1PUX import**(`kagitaba.import.onepux` + `onepux-file`): 変換ロジックは
   IO を持たない純粋 `.cljc`(`onepux.cljc`)と、zip/JSON を読む JVM 専用 IO 層
   (`onepux_file.clj`)に分離。**単一不変条件**: import は絶対にデータを黙って
   落とさない — 未知 category/field は保持したまま `item-warnings` で警告するのみ。
6. **op CLI import は非スコープ**: `.1pux` ファイルを第一実装とし、`op item
   list/get --format json` 経由のライブ import は将来 phase の TODO として設計だけ
   残す(op CLI のインストール/ログイン/リアルタイム同期という別の運用面の複雑さを
   持ち込むため、今回は範囲外)。

## Seams

- `kagitaba.import.onepux/parse-export-data`(純粋、JSON keyword 化済み map → item 群)
- `kagitaba.import.onepux-file/load-1pux`(JVM IO 越し、上記へ委譲)
- 将来 CLJS/op-CLI import はこの 2 段構造(pure transform ⟂ IO adapter)を踏襲する。

## Consequences

- **+** kagi 以外の消費者(将来の kagitaba GUI、Bitwarden 互換 export 等)が
  crypto に触れずに item モデルだけ再利用できる。
- **+** import 変換が純粋関数なので contract test だけで正しさを検証できる
  (実 `.1pux` バイナリ fixture が無くても、キーワード化済み JSON map で足りる)。
- **−** category uuid テーブルは 1Password 非公式ソースの突き合わせ検証であり、
  1Password 自身が将来 categoryUuid を追加/変更した場合は追従が必要。
- **−** `files/` 添付のパス構造は非公開のため best-effort 実装(未検証)。
- **−** op CLI 経由の import は未実装(設計のみ)。

## Non-goals

- kagitaba は vault の永続化・暗号化・共有・監査を一切行わない(kagi の責務)。
- 1Password の全カテゴリの正式フィールドテンプレートを完全再現しない
  (`kagitaba.schema` は新規作成時の雛形目的の best-effort であり、import の
  正しさには影響しない)。
