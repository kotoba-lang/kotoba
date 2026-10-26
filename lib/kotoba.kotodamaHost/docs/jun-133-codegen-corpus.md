# JUN-133 item 2 — lexicon codegen 移行のためのコーパス調査（2026-10-20）

`src/generated/lexicon-nsid-types.ts` は compat stub（LEXICON_NSID は Proxy）。
契約テスト（>400 エントリ、型付き LexiconInput/Output）は**名前付き未達**。
codegen を kotodama-host に移行するためのコーパス調査結果。

## ローカルに存在する lexicon ルート（2026-10-20 実測）

| JSON 数 | パス |
|---|---|
| 154 | cloud-itonami/toritsugi/wire/lexicons |
| 62 | kotoba-lang/kotoba/lexicons |
| 62 | kotoba-lang/kotoba-server/workspace/lexicons |
| 58 | network-awai/kotobase-control-plane/contracts/lexicons |
| 50 | network-awai/app-aozora/00-contracts/lexicons |
| 46 | cloud-itonami/tsukuru-actor/wire/lexicons |
| 45 | cloud-itonami/omise/wire/contracts/lexicons |
| 30 | kotoba-lang/kotobase-messenger/lexicons |
| 16 | cloud-itonami/kakaku/wire/contracts/lexicons |
| 残り | sarutahiko / kuni-umi / kenchi / actor-hinagata / iso20022 / ooyake-wire 等 |

**合計は 500+ あり、400+ 契約は量として満たせる。**

## 未解決のギャップ（この調査で確定）

1. **host capability NSIDs がローカルに無い**:
   `com.etzhayyim.host.secrets.get` / `host.invoke.call` / `host.llm.converse` /
   `governance.registerManifest` を lexicon ディレクトリから検索したが
   **該当なし**（grep -rl で 0 件）。etzhayyim root monorepo
   （00-contracts/lexicons、ローカル未 checkout）にある可能性が高い。
   契約テストの冒頭 2 ケースはこの 4 NSID の存在を要求する。
2. **入力スキーマからの型生成が必要**: `LexiconInput<...secrets.get>` は
   `{key: string}` を要求（lexicon の input schema から導出）。
   generator は JSON schema → TS 型の最小写像（string/number/boolean/配列/
   オブジェクト/必須）を持つ必要がある。
3. **generator 本体の行方は未確認**（旧 monorepo 由来、split に取り残し）。
   写像規則を新規実装するか履歴から復元するかは次スライスで決定。

## 次スライスの計画

1. etzhayyim root monorepo の lexicon（host capability 4 NSID を含む）の
   在り処を特定（GitHub 検索 or 別 checkout）。
2. `scripts/gen-lexicon-nsid.mjs`（zero-dep node）を実装: ルート列（CLI 引数
   + 生成物ヘッダに provenance 記録）を走査し、各 lexicon の `id`（NSID）と
   kind（procedure/query/record）を抽出、input/output schema を最小 TS 型に
   写像して `src/generated/lexicon-nsid-types.ts` を生成。
3. `test/lexicon-nsid-types.test.ts` 全通過を確認して stub を差し替え。
