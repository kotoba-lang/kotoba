# kotoba-pedigree

[![CI](https://github.com/kotoba-lang/pedigree/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/pedigree/actions/workflows/ci.yml)

**Material pedigree / certificate-of-conformance, in pure Clojure.**
The cross-cutting [kotoba-lang](https://github.com/kotoba-lang)
capability that closes a real gap in the `cloud-itonami-*` fleet
(ADR-2607999950): every `cloud-itonami-isic-*` open business is built
on a strict "pure data + pure functions -- no I/O, no network"
discipline, and until this library existed that meant every ISIC
vertical was a complete data-graph silo -- an upstream actor's real,
simulation-derived quality telemetry had no honest way to reach a
downstream actor's governor.

This library is the shared EDN interchange schema that closes that
gap **without** a live network call between actors: an upstream
actor's `export` namespace packages a pedigree record from data it
already has on file, a downstream actor's intake operation accepts it
as a plain data argument (never an HTTP fetch), and the downstream
governor independently re-verifies the pedigree's own shape and
claims before trusting it -- the same "ground truth, not self-report"
discipline every governor in this fleet already applies within a
single actor, now extended *across* actors.

Pilot: `cloud-itonami-isic-2410` (basic iron and steel) issues a
pedigree from a real `physics-2d`-simulated steel-coupon tensile-test
reading; `cloud-itonami-isic-2930` (auto parts) independently verifies
it before accepting the heat as feedstock for a structural weld/
fastener joint.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 33 assertions, all green |
| Dependencies | zero |

## Contract

```clojure
(require '[kotoba.pedigree :as pedigree])

(pedigree/claim "PEDIGREE-heat-1" "heat-1" "cloud-itonami-isic-2410"
                 {:tensile-test-load-n 5000.0}
                 :evidence-basis ["steelworks.robotics/run-tensile-test (physics-2d simulation)"]
                 :issued-at "2026-07-15")
;; => {:pedigree/id "PEDIGREE-heat-1" :pedigree/subject-lot-id "heat-1" ...}

(pedigree/valid? *1) ; => true -- shape/type validation a downstream governor calls
(pedigree/claim-value *2 :tensile-test-load-n) ; => 5000.0
```

## Schema

```clojure
{:pedigree/id             "..."                  ; issuing lot/certificate id, string
 :pedigree/subject-lot-id "..."                  ; the upstream lot/batch this pedigree is about
 :pedigree/issuing-actor  "cloud-itonami-isic-2410" ; business-id of the issuing actor
 :pedigree/claims         {:tensile-test-load-n 480.0 ...} ; verified, NUMERIC claims only -- never a self-reported string
 :pedigree/evidence-basis ["source citation" ...] ; non-empty vector of source citations
 :pedigree/issued-at      "2026-07-15"}           ; ISO date string
```

This library does not know what any particular claim key means, or
what acceptance threshold a downstream actor should require -- that
judgment belongs entirely to the downstream actor's own governor
(mirrors `kotoba.robotics/gate` not knowing which safety classes an
operator allows). This library only guarantees the record's *shape*
is honest: required fields present, claims numeric, evidence
non-empty.

## Why

An LLM-driven advisor inside any `cloud-itonami-isic-*` actor should
never invent an upstream supplier's material properties, and should
never trust an upstream actor's self-report at face value either --
the same "ground truth, not self-report" invariant that makes every
governor in this fleet safe to operate within one actor. `kotoba-
pedigree` is the pure-data layer that lets that invariant extend
*across* actors, without ever breaking the fleet's "no I/O, no
network" discipline: the data moves as a function argument (test/
demo/orchestration-script-level wiring), never as a live RPC.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
