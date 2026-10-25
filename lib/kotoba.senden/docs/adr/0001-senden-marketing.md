# ADR 0001: senden — kotoba-lang marketing domain lane

- **Status**: accepted — landed (2026-06-30), tests green
- **Date**: 2026-06-30
- **Deciders**: Jun Kawasaki
- **Related**: `90-docs/adr/2607010850-kotoba-lang-ec-domain-lanes.md`, `orgs/kotoba-lang/chobo`, `orgs/kotoba-lang/shitsuke`

## 背景

EC/業務ドメインの marketing（campaign/funnel/attribution）が kotoba-lang に共通ライブラリとして無かった。chobo.ledger EAVT 基底の上の lane として切り出す。

## 決定

`senden`（宣伝）を portable `.cljc` ライブラリとして起こす。lane `:marketing`。campaign 状態機械 + funnel conversion + attribution モデル。re-frame portable 7-fn subset + 純 hiccup views（shitsuke 上）+ SSR parity。campaign/metering event は chobo.ledger activity に投影。

## 契約

1. dual-render（SSR `shitsuke.hiccup/->html` ‖ reagent cljs）。2. portable re-frame 7-fn subset。3. chobo.ledger 投影（lane :marketing）。4. 純粋 state（campaign 状態遷移は純関数）。

## Consequences

- 正: marketing ドメインが共有化。新規 EC サイトの campaign/帰属測定が senden で立つ。
- 負: v1 は純粋モデルのみ（広告プラットフォーム API 連携は follow-up）。

## Alternatives Considered

- サイト内直書き: 却下（共有化不可）。
- Shopify marketing API 模倣: 却下（cljc/kotoba 体制に合わない）。

## References

- `docs/design.md`, `orgs/kotoba-lang/chobo/docs/adr/0001-chobo-services-ec.md`
