# tenken (点検)

**tenken は web-service 設定 (wrangler / Cloudflare) を点検する lib。** 設定 1 件を
宣言的な EDN に正規化し、policy 違反を後から宣言的に評価する。AIaC — 設定のコード化と
宣言的評価の 2 面を 1 repo に持つ。

正本: **ADR-2809151400** (root `90-docs/adr/2809151400-tenken-declarative-config.kotoba`)。
先行例の一般化: `scripts/verify-awai-state-store-policy.cljk` (kbb, fail-closed,
SCANNED 行, exit 0/1/2, gate `root-awai-state-store-policy`) は tenken の 1 policy の
単一実装である。

## 4 層

| 層 | namespace | 責務 |
|---|---|---|
| model | `tenken.model` | wrangler 設定 1 件 (.json/.jsonc/.toml) を EDN map へ。未知 shape は nil に握り潰さず `:unreadable` を返す |
| policy | `tenken.policy` | 設定制約の宣言面。規則の literal・`:nature` (性質/実装状態)・`:fail-closed` を必ず持つ |
| eval | `tenken.eval` | 実測設定 × policy の全束を評価し SCANNED / VIOLATED / UNVERIFIED / SUMMARY を出す |
| (test) | `test/tenken_test.cljk` | 両方向検査。clean 1 件 + 違反 3 形 + fail-closed 1 件 |

## 判定語彙

```
SATISFIED   policy 要求を満たす (理由つき)
VIOLATED    policy 違反 (規則の literal + 対象キーつき)
UNVERIFIED  読めない / 未知 shape (fail-closed: 緑にしない)
```

**理由の無い合格は合格と扱わない** (検査の 8 問、repo-wide mandatory)。

## 使い方

```bash
cd orgs/kotoba-lang/tenken

# 両方向検査 (18 case)
kbb --backend sci --classpath src test/tenken_test.cljk

# superproject の wrangler 設定全走査 × awai state-store policy
# (SCANNED と SUMMARY を出し、0 件走査・読めない設定は FAIL)
kbb --backend sci --classpath src src/tenken/eval.cljk --root <superproject-root> --policy awai-no-single-vendor-state
```

## 実測 (2026-09-15)

- superproject root の wrangler 設定 **542 件**、うち network-awai 配下 37 件
- network-awai 37 件 × awai policy: **VIOLATED 14 / SATISFIED 23 / UNVERIFIED 0**
- **参照 parity: awai checker の VIOLATION 14 path と集合一致** (両方向)
- 既存 checker が grep で済ませている trailing comma (cloud-murakumo/wrangler.jsonc)
  を tenken は正規化して parse する (`strip-trailing-commas`)

## 現在地 / 制約

- `.cljk` + kbb (SCI) 対応。`.kotoba` 移行は言語側 readiness 追随 (暫定制約 —
  撤去条件: amu compile が本 lib の shape を admit したら)。
- policy は 1 種 (`awai-no-single-vendor-state`)。追加 policy は
  `tenken.policy` に predicate を足すだけで eval 側は無変更。
- jsonc の行/ブロック comment・trailing comma を正規化。toml は 1 段
  (table 配下の keyval を `dotted.key` 形で 1 map に落とす — binding 存在判定に
  足りる深さ)。

## 落とし穴 (実測)

- この SCI 環境 (kbb/nbb) では `str/last-index-of` と `.lastIndexOf` が**異常に
  動く実測**がある (nil を渡すと `Cannot read properties of null`)。toml の table
  行は末尾の `]` を count から剥がす実装にした (line 末尾は必ず `]`)。
- `str/starts-with?` は nil に渡すと同様に落ちる — model は nil key を
  assoc 前に排除する。
- `recur` は `try` を跨げない (SCI/nbb 実測) — `step` 関数に切り出す。
