# ADR 0001: soko — kotoba-lang warehouse / logistics domain lane

- **Status**: accepted — landed (2026-06-30), tests green
- **Date**: 2026-06-30
- **Deciders**: Jun Kawasaki
- **Related**: `90-docs/adr/2607010850-kotoba-lang-ec-domain-lanes.md`, `orgs/kotoba-lang/chobo`, `orgs/kotoba-lang/shitsuke`, `orgs/kotoba-lang/mise`

## 背景

warehouse / logistics（多地点在庫/出荷/fulfillment）が kotoba-lang に共通ライブラリとして無かった。mise.inventory は単一 {sku→qty} で多地点非対応。mise.pricing の IShipping は運費計算 stub のみ。

## 決定

`soko`（倉庫）を portable `.cljc` ライブラリとして起こす。lane `:warehouse`。多地点 Stock（sku×wh→qty）+ transfer + Shipment 状態機械（pending→…→delivered）+ fulfillment plan（pick-list + 按分庫 shipment, first-fit）。mise に依存（inventory 連携）。`soko.projection` で mise.order → fulfillment plan 投影。re-frame portable 7-fn subset + 純 hiccup + SSR parity。warehouse event は chobo.ledger activity に投影。

## 契約

1. dual-render。2. portable re-frame 7-fn subset。3. chobo.ledger 投影（lane :warehouse）。4. 純粋 state。5. mise 連携（`soko.projection` で order→fulfillment-plan）。

## Consequences

- 正: 多地点在庫/出荷/fulfillment が共有化。mise の order が soko の fulfillment に直結可能。
- 負: v1 は純粋モデル（in-transit transfer/3PL API/WMS 連携は follow-up）。

## References

- `docs/design.md`, `orgs/kotoba-lang/mise/docs/adr/0001-mise-ec-system.md`
