# ADR 0001: madoguchi — kotoba-lang customer support / CRM domain lane

- **Status**: accepted — landed (2026-06-30), tests green
- **Date**: 2026-06-30
- **Deciders**: Jun Kawasaki
- **Related**: `90-docs/adr/2607010850-kotoba-lang-ec-domain-lanes.md`, `orgs/kotoba-lang/chobo`, `orgs/kotoba-lang/shitsuke`

## 背景

customer support / CRM（ticket/SLA/customer 360）が kotoba-lang に共通ライブラリとして無かった。itonami の :inbox lane は triage のみでフルサポート台ではない。

## 決定

`madoguchi`（窓口）を portable `.cljc` ライブラリとして起こす。lane `:support`。ticket 状態機械（new→open→pending→resolved→closed, reopen）+ SLA breach + customer（tags/LTV/contact log）。re-frame portable 7-fn subset + 純 hiccup + SSR parity。ticket event は chobo.ledger activity に投影。

## 契約

1. dual-render。2. portable re-frame 7-fn subset。3. chobo.ledger 投影（lane :support）。4. 純粋 state。

## Consequences

- 正: support/CRM ドメインが共有化。SLA 監視付きのサポート台が madoguchi で立つ。
- 負: v1 は純粋モデル（ヘルプデスク統合・チャネル連携は follow-up）。

## References

- `docs/design.md`, `orgs/kotoba-lang/chobo/docs/adr/0001-chobo-services-ec.md`
