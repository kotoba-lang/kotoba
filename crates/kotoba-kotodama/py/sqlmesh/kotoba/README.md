# kotoba view registry (RW materialized-view replacement)

`views.edn` is the kotoba-native replacement for the 610 RisingWave materialized
views under `../models/*.sql`, per **ADR-2605262130** (no projection layer) +
**ADR-2605312345** (the Datom log is first-class canonical state).

A RisingWave MV is a *derived read*, not state. Under kotoba the read path is
`kotoba-query` arrangements (EAVT / AEVT / AVET / VAET) run **directly over the
canonical Datom log** — so each MV becomes a **view** = a Datalog
`[:find … :where …]` query, materialized on demand by kqe rather than maintained
as a separate streaming table.

## Generation

```
python3 ../sqlmesh_to_kotoba.py        # regenerate views.edn (idempotent)
python3 ../sqlmesh_to_kotoba.py --print # print to stdout, no write
```

The converter parses every model's `MODEL(...)` header (preserving
name / kind / grain / tags / description / source deps) and the `SELECT` body.

## Coverage (honest)

| `:view/translation` | count | meaning |
|---|---|---|
| `:auto` | **274** | single-source projection or single-source GROUP BY aggregate — Datalog emitted under `:view/query`, ready for kqe |
| `:manual` | **336** | JOINs, UNION, DISTINCT-ON, subqueries, or computed SELECT expressions — original SQL preserved verbatim under `:view/sql-source` + `:view/manual-reason`. **R1 targets**, never a pretended translation |

`:manual` breakdown: ~95 multi-source JOIN (→ multi-clause kqe rules), 27 UNION
(→ rule disjunction), the remainder single-source aggregates with computed/DISTINCT
inner expressions or `::`/`||`/`CASE` projections.

Source-table names map to the same attribute namespaces the substrate client uses
(`kotodama.kotoba_datomic.table_attr_namespace`): `vertex_actor` → `vertex.actor`,
column `did` → `:vertex.actor/did`.

## Each entry

```clojure
{:view/name "mv_actor_count_by_status"
 :view/kind :full
 :view/grain ["status"]
 :view/tags ["actor" "count" "monitoring"]
 :view/description "Actor row count per status value from vertex_actor."
 :view/sources ["vertex.actor"]
 :view/translation :auto
 :view/query "[:find ?status (count ?e) :where [?e :vertex.actor/status ?status]]"}
```

`:manual` entries replace `:view/query` with `:view/manual-reason` + `:view/sql-source`.

## Status

R0: registry generated + validated (round-trips through the repo EDN reader); the
`:auto` queries are emitted but not yet wired into a live kqe endpoint (deferred to
the Phase 2.5 read-path migration in ADR-2605262130). The legacy `../models/*.sql`
stay in place until that cutover.
