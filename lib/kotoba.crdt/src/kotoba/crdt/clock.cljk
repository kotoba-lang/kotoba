(ns kotoba.crdt.clock
  "Lamport logical clocks: {:crdt/counter n :crdt/actor id} stamps with a
  total order every replica agrees on regardless of message arrival order.
  Every primitive in kotoba.crdt uses a clock stamp as its merge tiebreak, so
  merge stays commutative, associative, and idempotent — the three properties
  that make convergence independent of network/delivery order.

  ## Where the rules live

  `init`, `tick`, `observe` and `before?` do not compute anything here. They
  convert a host map into the guest ABI, run `src/kotoba/crdt/clock.kotoba` —
  compiled, shipped as `resources/kotoba/crdt/oracle/clock.kir.edn`, executed
  by `kotoba.crdt.kotoba-oracle` — and convert the answer back. The receive
  rule `max(local, received) + 1` and the counter-then-actor total order are
  stated once, in the `.kotoba`, and `clock-kotoba-parity-test` no longer binds
  two implementations because there is one.

  `stamp`, `after?` and `max-stamp` have no Kotoba counterpart and still
  compute here. That is a gap in the port, named rather than hidden.

  ## The i64 boundary, stated

  `clock.kotoba` types actors and counters as `:i64`. This namespace has always
  accepted any comparable actor id — a did:key, a session uuid — and `doc`'s
  own README opens with `(clock/init \"alice\")`. Delegating unconditionally
  would narrow that public API to integers, so it is conditional: when every
  field a call needs is an integer the shipped core answers, and when it is not
  the host path answers, with exactly the behaviour it had before. Which path
  ran is decided by the data, never by whether the artifact loaded — a missing
  artifact throws rather than falling back.

  Two consequences worth saying out loud rather than letting a reader find:

  - A non-integer actor is served by host code that no `.kotoba` checks. The
    two paths agree by construction on integers (`clock-kotoba-parity-test`),
    and `clock-test` covers the string-actor path, but the host path is not
    derived from the guest and never will be until actors are.
  - At the extreme edge of `:i64` the two paths differ: the guest wraps modulo
    2^64 where `inc` on a JVM `long` throws. A Lamport counter does not reach
    2^63, and pretending otherwise would mean writing a host-side range rule —
    another rule kept in the wrong place.

  ## ClojureScript hosts must register the KIR

  There is no classpath to read the artifact from, so a ClojureScript host has
  to `kotoba.crdt.kotoba-oracle/register-kir!` before an integer-actor clock
  will work; without it these four throw. Non-integer actors are unaffected,
  since they never reach the guest. This is a real narrowing on that runtime,
  and it is the price of the rules having one home."
  (:require [kotoba.crdt.kotoba-oracle :as oracle]))

;; ── the host ↔ guest ABI ─────────────────────────────────────────────
;;
;; Both record types are READ BACK from the shipped artifact rather than
;; written out here. The artifact is `clock.kotoba` compiled, so the record's
;; name, its fields and — the part that matters for a positional ABI — their
;; declared order come from the source of the rule. Delays, not defs: on a
;; runtime with no classpath the artifact arrives via `register-kir!`, which
;; cannot have happened while this namespace was being loaded.

(def ^:private clock-type (delay (first (oracle/param-types :clock 'tick))))
(def ^:private stamp-type (delay (second (oracle/param-types :clock 'observe))))

(defn- host-key
  "Guest field name -> the key a kotoba.crdt host map holds it under. The one
  piece of vocabulary the two sides do not share, and the only reason this
  conversion is not entirely mechanical."
  [field]
  (keyword "crdt" (name field)))

(defn- crossable?
  "Whether `m` carries every field of `record-type` as a value that can cross
  as `:i64` without changing what it means."
  [record-type m]
  (every? (fn [[field _type]] (oracle/fits-i64? (get m (host-key field))))
          (oracle/record-fields record-type)))

(defn- ->guest [record-type m]
  (oracle/record record-type
                 (map (fn [[field _type]] (oracle/i64 (get m (host-key field))))
                      (oracle/record-fields record-type))))

(defn- <-guest
  "Guest record -> the fields it carries, as a host map. Callers `into` this
  over the map they were given, so a clock a host has hung extra keys on keeps
  them: the guest decides the counter, not what else a host may be tracking."
  [record-value]
  (into {} (map (fn [[field _type] v] [(host-key field) (oracle/i64-value v)])
                (oracle/record-fields (first record-value))
                (oracle/record-values record-value))))

;; ── the four the shipped core decides ────────────────────────────────

(defn init
  "A fresh clock for `actor` (any comparable id: a did:key, a session uuid...)."
  [actor]
  (if (oracle/fits-i64? actor)
    (<-guest (oracle/call :clock 'init [(oracle/i64 actor)]))
    {:crdt/counter 0 :crdt/actor actor}))

(defn tick
  "Advance the clock for a locally-originated event."
  [clock]
  (if (crossable? @clock-type clock)
    (into clock (<-guest (oracle/call :clock 'tick [(->guest @clock-type clock)])))
    (update clock :crdt/counter inc)))

(defn stamp
  "The causal stamp to attach to an event originated at `clock`."
  [clock]
  (select-keys clock [:crdt/counter :crdt/actor]))

(defn observe
  "Advance `clock` to be strictly after a stamp received from another replica
  (Lamport's receive rule: local counter becomes max(local, received) + 1)."
  [clock received-stamp]
  (if (and (crossable? @clock-type clock)
           (crossable? @stamp-type received-stamp))
    (into clock (<-guest (oracle/call :clock 'observe
                                      [(->guest @clock-type clock)
                                       (->guest @stamp-type received-stamp)])))
    (update clock :crdt/counter
            (fn [c] (inc (max c (:crdt/counter received-stamp 0)))))))

(defn before?
  "Total order over stamps: counter first, actor id breaks ties. This is a
  deterministic tiebreak for concurrent events, not a causality test — two
  concurrent stamps still get a consistent (arbitrary) order every replica
  agrees on, which is exactly what LWW-Register merge needs."
  [a b]
  (if (and (crossable? @stamp-type a) (crossable? @stamp-type b))
    (oracle/call :clock 'before? [(->guest @stamp-type a) (->guest @stamp-type b)])
    (let [ca (:crdt/counter a 0) cb (:crdt/counter b 0)]
      (or (< ca cb)
          (and (= ca cb) (neg? (compare (:crdt/actor a) (:crdt/actor b))))))))

;; ── and the three the port has not reached ───────────────────────────

(defn after? [a b] (before? b a))

(defn max-stamp [a b] (if (before? a b) b a))
