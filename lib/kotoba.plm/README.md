# kotoba PLM

Open-source PLM workbench as EDN data + portable CLJC lifecycle engine.

This repository follows the kotoba industrial-app pattern:

- `resources/plm/domain.edn` is the data registry.
- `src/kotoba/plm/core.cljk` is the pure portable domain engine.
- `src/kotoba/plm/runner.cljk` is a conservative host dry-run runner.
- `docs/index.html` is the GitHub Pages workbench.

Pages: https://kotoba-lang.github.io/plm/

## Scope

This is an OSS workbench skeleton for 製品ライフサイクル管理. It does not claim proprietary compatibility with commercial systems. It focuses on open artifact registries, policy-gated runners, coverage/maturity scoring, and EDN handoff.

## Inventory has two registers

`:erp.inventory/qty-on-hand` is **custody** — what is on the floor and can be
consumed, and the basis `mrp/plan` nets against. `:erp.inventory/qty-accounting`
is **ownership**. They are equal for every ordinary movement and differ for the
cases one column cannot express:

| movement | custody | ownership | example |
|---|---|---|---|
| `transfer` | moves | moves | ordinary purchase or sale |
| `transferCustody` | moves | — | consignment stock, subcontract material |
| `transferAllRights` | — | moves | title sale, sale in transit, drop-ship |

Which register a movement touches is read from the pinned
[Valueflows](https://www.valueflo.ws/) action behaviour table
([`ws-valueflo-vocabulary`](https://github.com/kotoba-lang/ws-valueflo-vocabulary)),
not restated here.

```clojure
(require '[kotoba.plm.registers :as reg])

(reg/posting d "INV-X" :transferCustody 5M {:side :receiver})
;=> {:ok? true :tx {:erp.inventory/id "INV-X" :erp.inventory/qty-on-hand 15M}}
;;   ownership untouched — consignment does not inflate the balance sheet

(reg/divergence d ["INV-A" "INV-B"])   ; held-not-owned / owned-not-held rows
```

Rows written before the second register existed have no accounting quantity.
`reg/accounting-or-onhand` returns `{:value 7M :source :onhand-fallback}` rather
than a bare number, because a legacy row and a row whose registers happen to
agree are different facts.

## Verify

```sh
kbb -M -e '(load-file "src/kotoba/plm/core.cljk") (println :ok)'
python3 -m http.server 8765 --directory docs
```

## kotoba.plm.* — PLM × ERP thread domain (merged from cloud-itonami kyber-plm)

The pure PLM/ERP/MRP domain formerly living in `gftdcojp/cloud-itonami` as
`kyber-plm.*` (ADR-2606171400 lineage; merged per the ADR-2607020100 addendum
— コードは kotoba-lang、商売は cloud-itonami):

- `kotoba.plm.item` — item master / BOM edges / change orders (pure
  constructors + queries; was `kyber-plm.plm`)
- `kotoba.plm.schema` — the three-layer graph schema (plm.* / erp.* / ocel.*)
- `kotoba.plm.erp` — chart of accounts, balanced GL journals, rolled-cost
  snapshots, OCEL events
- `kotoba.plm.cost` — standard-cost roll-up over the released MBOM
- `kotoba.plm.mrp` — MBOM demand explosion → net requirements → auto POs
- `kotoba.plm.production` — production completion (backflush) into WIP/GL
- `kotoba.plm.thread` — the PLM→ERP reactive thread (one logical commit per fn)
- `kotoba.plm.db` / `kotoba.plm.store` — Store protocol + kotoba-datomic XRPC
  backend (transport injected); `kotoba.plm.store-datomic` is the Datomic
  Local dev/test backend, **opt-in via `:datomic` / `:test` alias** so the
  core stays dependency-free
- `kotoba.plm.demo` — end-to-end PLM→ERP demo

Business-side projections (kotobase `kg.ingest` payloads, live ops CLI)
remain in `gftdcojp/cloud-itonami` (`cloud-itonami.kotobase-kg` /
`cloud-itonami.plm-export`).

```bash
kbb -M:test   # 9 tests (phase2 + thread) against Datomic Local
```
