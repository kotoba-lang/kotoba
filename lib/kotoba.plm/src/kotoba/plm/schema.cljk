(ns kotoba.plm.schema
  "Datomic schema for the PLM × Kyber ERP thread (ADR-2606171400).

   Three layers in one connected graph so a single Datalog/pull can walk
   EBOM → MBOM → inventory → cost → GL:

     plm.*  — PLM core: item master, BOM edges, change orders (the upstream
              authority for parts, structure, revision and lifecycle).
     erp.*  — Kyber ERP targets: perpetual inventory, purchase orders,
              rolled standard cost, chart of accounts, journal (GL).
     ocel.* — OCEL 2.0 event log (the projector/audit thread, ADR-0025).

   NSID parity: these idents mirror the `ai.gftd.apps.kyber.*` collections of
   the deployed kyb3rerp worker — `:plm.item/*` ↔ `ai.gftd.apps.kyber.plm.item`,
   `:erp.inventory/*` ↔ `ai.gftd.apps.kyber.inventoryItem`, etc.

   Datomic Local requires :db/valueType + :db/cardinality on every attribute."
  (:require [datomic.client.api]))

(def schema
  [;; ─────────────────────────── PLM core: item master ──────────────────────
   {:db/ident :plm.item/id          :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity  :db/doc "Stable item key = \"<part-no>@<revision>\"."}
   {:db/ident :plm.item/part-no     :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/doc "Non-intelligent part number (meaning lives in attributes, not the number)."}
   {:db/ident :plm.item/revision    :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.item/name        :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.item/uom         :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc "Unit of measure, e.g. :ea :kg :m."}
   {:db/ident :plm.item/make-buy    :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":make (rolled from MBOM) | :buy (purchased, has std-unit-cost) | :phantom."}
   {:db/ident :plm.item/category    :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :plm.item/lifecycle   :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc "State machine: :draft → :in-review → :released → :obsolete. Only :released propagates to ERP."}
   {:db/ident :plm.item/std-unit-cost :db/valueType :db.type/bigdec :db/cardinality :db.cardinality/one
    :db/doc "Purchased standard unit cost for :buy items (input to cost roll-up)."}
   {:db/ident :plm.item/supersedes  :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one
    :db/doc "Prior released item revision this one supersedes."}
   {:db/ident :plm.item/package-ref :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/doc "Content hash of the manufacturing package (ADR-2604252100 product.manufacturing.json)."}
   {:db/ident :plm.item/released-at :db/valueType :db.type/instant :db/cardinality :db.cardinality/one}

   ;; ─────────────────────────── PLM core: BOM as edges ─────────────────────
   {:db/ident :plm.bom/id           :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity  :db/doc "Edge key = \"<parent>|<find>|<child>\"."}
   {:db/ident :plm.bom/parent       :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/child        :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/qty          :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/uom          :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/find-no      :db/valueType :db.type/long    :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/ref-designator :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/view         :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":ebom (design structure) | :mbom (plant build structure, drives cost & consumption)."}
   {:db/ident :plm.bom/eff-from     :db/valueType :db.type/instant :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/eff-to       :db/valueType :db.type/instant :db/cardinality :db.cardinality/one}
   {:db/ident :plm.bom/eco          :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}

   ;; ─────────────────────────── PLM core: change order ─────────────────────
   {:db/ident :plm.eco/id           :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity}
   {:db/ident :plm.eco/kind         :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":ecr (request) | :eco (order) | :ecn (notice)."}
   {:db/ident :plm.eco/state        :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":draft → :in-review → :released. Only :released revalues ERP."}
   {:db/ident :plm.eco/affected     :db/valueType :db.type/ref     :db/cardinality :db.cardinality/many}
   {:db/ident :plm.eco/disposition  :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":use-as-is | :rework | :scrap."}
   {:db/ident :plm.eco/new-unit-cost :db/valueType :db.type/bigdec :db/cardinality :db.cardinality/one
    :db/doc "New std-unit-cost applied to affected :buy items on release (cost-impact driver)."}
   {:db/ident :plm.eco/cost-impact  :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.eco/released-at  :db/valueType :db.type/instant :db/cardinality :db.cardinality/one}

   ;; ─────────────────────────── BOP: work center + routing ─────────────────
   {:db/ident :plm.wc/id           :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity  :db/doc "Work center key."}
   {:db/ident :plm.wc/name         :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.wc/rate         :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one
    :db/doc "Cost absorption rate, currency per hour (labor + overhead)."}

   {:db/ident :plm.op/id           :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity  :db/doc "Edge key = \"<item>|<seq>\"."}
   {:db/ident :plm.op/item         :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :plm.op/seq          :db/valueType :db.type/long    :db/cardinality :db.cardinality/one
    :db/doc "Routing step order, ascending."}
   {:db/ident :plm.op/name         :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.op/work-center  :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :plm.op/std-time-hr  :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one
    :db/doc "Run time per unit, hours."}
   {:db/ident :plm.op/setup-time-hr :db/valueType :db.type/bigdec :db/cardinality :db.cardinality/one
    :db/doc "Setup time per lot, hours (amortised per-unit by callers as needed)."}

   ;; ─────────────────────────── MPS: master production schedule ────────────
   {:db/ident :plm.mps/id          :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity  :db/doc "Edge key = \"<item>|<period-millis>\"."}
   {:db/ident :plm.mps/item        :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :plm.mps/period      :db/valueType :db.type/instant :db/cardinality :db.cardinality/one
    :db/doc "Time bucket start date."}
   {:db/ident :plm.mps/qty         :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.mps/kind        :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":forecast (planning estimate) | :firm (committed, MRP-eligible once :approved)."}
   {:db/ident :plm.mps/state       :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":draft → :approved. Only :approved lines feed MRP demand."}

   ;; ─────────────────────────── PDM: document / version ────────────────────
   {:db/ident :plm.doc/id          :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity}
   {:db/ident :plm.doc/item        :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :plm.doc/kind        :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":cad | :drawing | :spec | :step."}
   {:db/ident :plm.doc/version     :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.doc/checksum    :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :plm.doc/uri         :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}

   ;; ─────────────────────────── ERP: perpetual inventory ───────────────────
   {:db/ident :erp.inventory/id     :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity}
   {:db/ident :erp.inventory/item   :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   ;; TWO registers, per Valueflows: qty-on-hand is CUSTODY (what is on the
   ;; floor and can be consumed -- the basis MRP nets against), qty-accounting
   ;; is OWNERSHIP. They are equal for every ordinary movement and differ for
   ;; consignment stock (held, not owned) and title sales in transit (owned,
   ;; not held). A single column cannot tell those apart, and guessing either
   ;; way is wrong: one overstates the balance sheet, the other tells MRP to
   ;; buy material already in the building. See kotoba.plm.registers.
   {:db/ident :erp.inventory/qty-on-hand :db/valueType :db.type/bigdec :db/cardinality :db.cardinality/one}
   {:db/ident :erp.inventory/qty-accounting :db/valueType :db.type/bigdec :db/cardinality :db.cardinality/one}
   {:db/ident :erp.inventory/std-cost :db/valueType :db.type/bigdec :db/cardinality :db.cardinality/one
    :db/doc "Current standard unit cost backing on-hand valuation."}

   ;; ─────────────────────────── ERP: procurement ───────────────────────────
   {:db/ident :erp.po/id            :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity}
   {:db/ident :erp.po/item          :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :erp.po/qty           :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.po/unit-cost     :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.po/state         :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}

   ;; ─────────────────────────── ERP: rolled standard cost ──────────────────
   {:db/ident :erp.cost/id          :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity  :db/doc "One roll-up snapshot key = \"<item>@<asof-millis>\"."}
   {:db/ident :erp.cost/item        :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}
   {:db/ident :erp.cost/rolled      :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.cost/as-of       :db/valueType :db.type/instant :db/cardinality :db.cardinality/one}

   ;; ─────────────────────────── ERP: chart of accounts + GL ────────────────
   {:db/ident :erp.account/code     :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity}
   {:db/ident :erp.account/name     :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.account/type     :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":asset | :liability | :equity | :revenue | :expense."}

   {:db/ident :erp.journal/id       :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity}
   {:db/ident :erp.journal/date     :db/valueType :db.type/instant :db/cardinality :db.cardinality/one}
   {:db/ident :erp.journal/memo     :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.journal/lines    :db/valueType :db.type/ref     :db/cardinality :db.cardinality/many
    :db/isComponent true            :db/doc "Balanced debit/credit lines (component → cascades on retract)."}
   {:db/ident :erp.jline/account    :db/valueType :db.type/string  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.jline/debit      :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.jline/credit     :db/valueType :db.type/bigdec  :db/cardinality :db.cardinality/one}
   {:db/ident :erp.jline/item       :db/valueType :db.type/ref     :db/cardinality :db.cardinality/one}

   ;; ─────────────────────────── OCEL 2.0 audit thread ──────────────────────
   {:db/ident :ocel/id              :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/unique :db.unique/identity}
   {:db/ident :ocel/type            :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":item.released :inventory.registered :cost.rolledup :goods.received :eco.released :journal.posted ..."}
   {:db/ident :ocel/apqc            :db/valueType :db.type/string  :db/cardinality :db.cardinality/one
    :db/doc "APQC PCF L1, e.g. \"4.0\" Supply Chain, \"9.0\" Financial, \"10.0\" Asset Mgmt."}
   {:db/ident :ocel/at              :db/valueType :db.type/instant :db/cardinality :db.cardinality/one}
   {:db/ident :ocel/objects         :db/valueType :db.type/ref     :db/cardinality :db.cardinality/many
    :db/doc "Entities this event touches (items, inventory, journals)."}])
