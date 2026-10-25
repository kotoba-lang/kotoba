# consumability

What makes a producer consumable, and how much of it a given producer has.

A producer is anything that publishes a surface others could call — a deployed
actor, a worker, an API. This library owns the **definition** and the **scoring**
and performs no I/O: a caller probes the world and hands the observations in, an
orchestrator decides what to do with the result.

That split is required, not stylistic. `manifest/repository-rules.edn` forbids a
`loop-*` from owning domain scoring truth, so the truth lives here where anything
can reuse it and a loop can only consume it — the same arrangement
`loop-system-dynamics` has with `kotoba-lang/dynamics`.

## The ladder

```
:addressed        declares an address at all
:reachable        answers at that address
:describable      serves a machine-readable contract saying what to call
:discoverable     announces itself where a stranger would look
:agent-callable   exposes a protocol an agent can drive (MCP or equivalent)
```

Each rung is only meaningful if the one below it holds. A contract on a producer
nobody can reach describes nothing. A discovery document pointing at a dead
address is *worse* than none, because it spends a consumer's attention before
failing.

**So the score is the highest rung reached, never a weighted average.** A
weighted average would report a producer as 60% consumable while it is
unreachable, and 60% of nothing is nothing. This is the most important decision
in the library: it is what stops the number from flattering the fleet.

`:describable` is where `consumable?` draws the line. Below it a consumer needs
the source, which makes them a reader of the repository rather than a consumer of
the surface.

## Unknown is not absent

A probe that could not run yields `:unknown`, never `false`. An unreachable
network and a producer that refuses are different facts, and collapsing them
reports an outage as a design gap. `assess` keeps them apart, `summary` counts
`:unmeasured` separately, and `gaps` excludes them — acting on an unmeasured rung
would "fix" something that may already work.

## Use

```clojure
(require '[consumability.core :as c])

(c/assess
  {:producer  "cloud-itonami-marketplace-order"
   :endpoint  "https://cloud-itonami-marketplace-order.04-feasts-minded.workers.dev"
   :health    {:path "/health" :status 200}
   :contract  {:path "/openapi.json" :status 404}
   :discovery [{:path "/llms.txt" :status 404}]
   :agent     {:path "/mcp" :status 404}})
;; => {:producer "cloud-itonami-marketplace-order"
;;     :reached  [:addressed :reachable]
;;     :rung     :reachable
;;     :gap      :describable
;;     :unknown  false
;;     :verdicts {...}}
```

`rank` orders gaps by leverage, **lowest rung first** and population second:

```clojure
(c/rank assessments)
;; => [{:rung :addressed :blocked 1199 :producers [...]}
;;     {:rung :describable :blocked 9 :producers [...]}]
```

Low-rung-first is the primary key on purpose. Sorting by population would rank
"add MCP to the 9 reachable actors" above "give the other 1,199 an address",
which optimises a number instead of the fleet — the 9 are already the only ones
anyone can use.

## Test

```bash
kbb --backend sci --classpath "src:test" test/run_tests.cljk
```

Pure `.cljc`, no dependencies, no I/O.
