# ADR 0001: chobo — kotoba-lang services-EC foundation (itonami business model 共通化)

- **Status**: accepted — landed (2026-06-30), tests green
- **Date**: 2026-06-30
- **Deciders**: Jun Kawasaki
- **Context tags**: ec, services-ec, subscription, ledger, cljc, itonami
- **Related**: `90-docs/adr/<ts>-kotoba-lang-chobo-services-ec.md` (superproject),
  `orgs/kotoba-lang/mise`, `orgs/kotoba-lang/shitsuke`,
  `orgs/gftdcojp/cloud-itonami`, `orgs/gftdcojp/cloud-itonami-6310`,
  `orgs/gftdcojp/ai-gftd-apex`

## 背景

`cloud-itonami` は業務 OS（manimani の企業版）で、EAVT（activity/artifact/relation/
decision/effect）の監査台帳を主体に sales/contract/billing/erp/plm/mes の lane を
持つ。`ai-gftd-apex` は Proton 型サブスクリプション商品設計（tier/entitlement/quota/
overage/metering）を持つ。これらは「サービス型 EC」の語彙だが、`mise`（小売 EC:
cart/SKU/checkout）とは別系統で再利用されていない。

`mise` vs Shopify は小売 EC 機能カバー ~15–20%（cart/checkout/order/inventory/pricing
の純粋骨格のみ）。一方 itonami 系のサブスクリプション/計量/請求/監査台帳は kotoba-lang
に共通ライブラリとして無い。両者を共通化するため、itonami の業務モデルから EC 関連
部分（監査台帳 + サブスクリプション/計量 + 請求）を抽出し `chobo`（帳簿）として
kotoba-lang に置く。

## 決定

`chobo` を portable `.cljc` ライブラリ（runtime dep は shitsuke のみ）として起こす。
mise（小売）と itonami（サービス）が同じ台帳/請求/サブスクリプション基盤を共有する。

### 層

| 層 | 役割 |
|---|---|
| `chobo.ledger` | EAVT activity/artifact/relation/decision/effect + append-only log + `ILedgerStore` |
| `chobo.subscription` | plan/tier/entitlement/quota/metering/overage |
| `chobo.invoice` | invoice + lines + status statechart + dunning + `IInvoiceStore` |
| `chobo.tenant` | tenant + capabilities + operator trust levels |
| `chobo.events` | re-frame events/subs (portable 7-fn subset via shitsuke) |
| `chobo.views` | 純 hiccup: ledger-entry / meter-gauge / plan-status / invoice-card / tenant-badge |
| `chobo.ssr` | SSR parity |

### 契約（authoritative）

1. **dual-render**: 同じ `.cljc` 純 hiccup view を SSR（`shitsuke.hiccup/->html`）と reagent
   （cljs）の両方へ（shitsuke/mise と同契約）。
2. **portable re-frame subset**: `chobo.events` は `shitsuke.re-frame.core` に 7 関数のみで
   登録。effect/cofx/interceptor/chaining 使わず。
3. **注入 port**: `ILedgerStore`, `IInvoiceStore`（mock 同梱）。Datomic/D1/kotoba-server
   adapter は follow-up。
4. **純粋 state**: ledger/subscription/invoice の状態遷移はすべて純関数。台帳は append-only
   （レコード追加のみ、状態変化は新レコード）。
5. **mise 連携**: `mise.order → chobo.ledger` activity 投影（`mise.ledger` stub）。
   `mise.pricing` totals → `chobo.invoice` line。v1 は投影 stub のみ（実連携は follow-up）。
6. **itonami 由来**: EAVT schema は itonami の `:itonami.activity/*` が起源。subscription
   model は ai-gftd-apex 設計が起源。chobo は両者の portable 抽出。

## Consequences

- **正向**: サービス型 EC（subscription/metering/監査台帳）と小売 EC（mise）が
  共通基盤で共有化。新規 SaaS/サブスクリプション商品は chobo + shitsuke で立ち上がる。
  itonami の lane も chobo.ledger に載せ替え可能。
- **負向**: v1 は mock adapter のみ（Datomic/D1 未統合）。mise との実連携（order→invoice→
  ledger の実際の自動投影）は follow-up stub のみ。
- **移行**: mise は `mise.ledger` stub で chobo に依存（pin 前進）。itonami 本体の chobo
  載せ替えは別 follow-up。

## Alternatives Considered

- **itonami に EC 関連を直書き**: 却下。mise（小売）と共有できず、shitsuke/mise の
  共通化方針と対にならない。
- **mise に subscription を拡張**: 却下。小売 EC とサービス EC は関心事が違う。
  chobo として独立させ mise が依存する方がクリーン。
- **Shopify のサブスクリプション API を模倣**: 却下。gftd. の cljc/kotoba 体制
  （ポータブル・データ主権・監査台帳）に合わない。

## References

- `orgs/gftdcojp/cloud-itonami/src/cloud_itonami/schema.cljc`（EAVT 由来）
- `orgs/gftdcojp/ai-gftd-apex/docs/products/ai-gftd-apex/business-operating-design.md`
  （subscription/entitlement/quota/overage 設計由来）
- `90-docs/adr/2606301900-kotoba-lang-shitsuke-design-system.md`
- `orgs/kotoba-lang/mise/docs/adr/0001-mise-ec-system.md`
