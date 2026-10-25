# ADR 0001: kiyaku — kotoba-lang customer accounts + returns/RMA domain lane

- **Status**: accepted — landed (2026-06-30), tests green
- **Date**: 2026-06-30
- **Deciders**: Jun Kawasaki
- **Related**: `90-docs/adr/2607010850-kotoba-lang-ec-domain-lanes.md`, `orgs/kotoba-lang/chobo`, `orgs/kotoba-lang/shitsuke`

## 背景

customer accounts（アドレス帳/ウォレット/決済手段）+ returns/RMA が kotoba-lang に共通ライブラリとして無かった。chobo.tenant は operator 側で end-customer では無い。

## 決定

`kiyaku`（客）を portable `.cljc` ライブラリとして起こす。lanes `:customer` + `:returns`。CustomerAccount（アドレス帳/payment-method refs/wallet）+ ReturnRequest/RMA 状態機械（requested→approved→shipped→received→refunded|rejected）。end-customer 側（chobo.tenant = operator と対）。re-frame portable 7-fn subset + 純 hiccup + SSR parity。account/return event は chobo.ledger activity に投影。

## 契約

1. dual-render。2. portable re-frame 7-fn subset。3. chobo.ledger 投影（lanes :customer/:returns）。4. 純粋 state。

## Consequences

- 正: end-customer アカウント + 返品/RMA が共有化。EC サイトの「マイアカウント/返品」が kiyaku で立つ。
- 負: v1 は純粋モデル（認証/決済手段 vault/返品送料計算は follow-up）。

## References

- `docs/design.md`, `orgs/kotoba-lang/chobo/docs/adr/0001-chobo-services-ec.md`
