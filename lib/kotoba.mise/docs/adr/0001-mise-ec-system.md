# ADR 0001: mise — kotoba-lang shared e-commerce system

- **Status**: accepted — landed (2026-06-30), tests green
- **Date**: 2026-06-30
- **Deciders**: Jun Kawasaki
- **Context tags**: ec, commerce, cljc, reframe, fashion, portable
- **Related**: `90-docs/adr/<ts>-kotoba-lang-mise-ec-system.md` (superproject),
  `orgs/kotoba-lang/shitsuke`, `orgs/kotoba-lang/slides`,
  `orgs/gftdcojp/ai-gftd-fashion`,
  https://www.fashionsnap.com/article/2018-04-20/gifted-hatra/

## 背景

`fashion.gftd.ai` にファッションブランド **gftd.** の EC サイトを立てる（シード:
2018-04-20 fashionsnap 記事「感覚過敏の人に向けたファッションブランド『ギフテッド』始動、
第1弾はハトラとコラボ」#パーカ, Image by: gftd.）。gftdcojp/kotoba-lang 配下に既存の
EC/cart/checkout/order/inventory ライブラリは無く（調査済）、EC system は net-new。
直前の `shitsuke`（design system）+ `slides`（dual-render re-frame 移行）のパターンを踏襲し、
EC system を共通ライブラリ `mise`（店）として kotoba-lang に置く。最初の利用者は
`ai-gftd-fashion`（gftdcojp, fashion.gftd.ai）。

## 決定

`mise` を portable `.cljc` ライブラリ（runtime dep は shitsuke のみ）として起こし、以下の
層 + EC components を束ねる。host 効果（決済・永続化）は注入 port（mock adapter 同梱）。

### 層

| 層 | 役割 |
|---|---|
| `mise.catalog` | Product/SKU/Catalog model (EDN) + query fns |
| `mise.pricing` | Price math + totals; `IDiscount`/`ITax`/`IShipping` ports |
| `mise.cart` | Cart line items + invariants (pure) |
| `mise.inventory` | Stock levels + reserve/restock (pure) |
| `mise.checkout` | checkout state machine + `IPaymentPort` (mock adapter) |
| `mise.order` | Order record + status statechart + `IOrderStore` (mock) |
| `mise.events` | re-frame events/subs (portable 7-fn subset via shitsuke) |
| `mise.views` | 純 hiccup EC components on shitsuke.components |
| `mise.ssr` | SSR parity via shitsuke.hiccup/->html |

### 契約（authoritative）

1. **dual-render**: 同じ `.cljc` 純 hiccup view を SSR（`shitsuke.hiccup/->html`）と reagent
   （cljs）の両方へ（shitsuke/slides と同契約）。view は reagent import しない。
2. **portable re-frame subset**: `mise.events` は `shitsuke.re-frame.core` に 7 関数のみで
   登録。effect/cofx/interceptor/chaining 使わず（JVM SSR / WASM で動かないため）。
3. **注入 port**: 決済 `IPaymentPort`（authorize/capture）、永続化 `IOrderStore`、割引 `IDiscount`、
   税 `ITax`、配送 `IShipping`。v1 は mock adapter のみ（Stripe/D1 adapter は follow-up）。
4. **純粋 state**: cart/checkout/order の状態遷移はすべて純関数（host app-db が所有）。
5. **shitsuke 再利用**: views は `shitsuke.components` と `shitsuke.style/class-name`（`mise__*`）
   の上に積む。token `:root` vars は consumer の `:pages` build が前置。

### 最初の利用者

`ai-gftd-fashion`（gftdcojp, fashion.gftd.ai）。shadow-cljs `:worker :esm` + `:app :browser`
（reagent/re-frame）で gftd. ブランドのカタログ（シード: GIFTED×HATRA パーカ）+ cart/checkout
SPA を構築。Cloudflare Workers deploy（wrangler.jsonc scaffold、実プロビジョニングは owner）。

## Consequences

- **正向**: EC の純粋データモデル + re-frame subset + 純 hiccup component が kotoba-lang で
  共有化。新規 EC サイト（gftd. 以外のブランド）は mise + shitsuke を require するだけで
  立ち上がる。決済/永続化は port 差替えで本番化可能。
- **負向**: v1 は mock adapter のみ（Stripe/D1 未統合）。live deploy は owner follow-up。
- **移行**: ai-gftd-fashion の実装は別 repo/PR。mise の manifest pin 前進は正経路（API single-entry）。

## Alternatives Considered

- **既存 EC SaaS / Stripe Checkout 直叩き**: 却下。gftd. ブランドの cljc/kotoba 体制に合わ
  ない（ポータブル・データ主権・actor 台帳の方針から外れる）。mise は port で Stripe を後付け可能。
- **サイト repo 内に EC を直書き**: 却下。複数ブランド/サイトで共有できず、shitsuke の
  design-system 共有と対にならない。kotoba-lang は関心事単位 repo 慣例。
- **real re-frame のみ（mini runtime 無し）**: 却下。JVM SSR / babashka / WASM で動かない。
  shitsuke の compat-namespace パターン（wasm-ui 由来）を採用。

## References

- `90-docs/adr/2606301900-kotoba-lang-shitsuke-design-system.md`（design system 前提）
- `orgs/kotoba-lang/shitsuke/docs/design.md`（shitsuke API）
- `orgs/kotoba-lang/slides/src/slides/web/events.cljc`（re-frame portable subset 実績）
- `orgs/gftdcojp/ai-gftd-fashion`（最初の利用者）
