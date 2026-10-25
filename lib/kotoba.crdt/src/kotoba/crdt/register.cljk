(ns kotoba.crdt.register
  "LWW-Register: a single field that concurrent writers race on. Merge keeps
  whichever write has the later kotoba.crdt.clock stamp. This is the
  intentional, documented limit of this package: concurrent writes to the
  SAME field of the SAME entity are not merged character-by-character (no
  RGA/OT) — one write wins and the other is discarded. Concurrent writes to
  DIFFERENT fields (kotoba.crdt.doc) or DIFFERENT entities (kotoba.crdt.orset)
  never collide.

  ## Where the rule lives

  `init`, `write`, `value` and `merge-register` do not compute anything here.
  They convert host values into the guest ABI, run
  `src/kotoba/crdt/register.kotoba` — compiled, shipped as
  `resources/kotoba/crdt/oracle/register.kir.edn`, executed by
  `kotoba.crdt.kotoba-oracle` — and convert the answer back.

  One of those four is the decision and three are the shape, and it is worth
  saying which. `merge-register` is the rule: later stamp wins, ties keep the
  left register. The shipped artifact is `register.kotoba` linked against
  `clock.kotoba`, so the stamp comparison that settles the race is the same
  `before?` the clock ships — the tiebreak is not restated here, or anywhere
  else. `write`, `value` and `init` carry the register's shape instead: which
  field holds the content, which holds the stamp, and that absence is `nil`.
  They are delegated too, because a substituted core that got any of them
  wrong is a thing the delegation gate should catch.

  ## Why merging is delegable when `doc` and `orset` are not

  `merge-register` is handed exactly two registers, whatever the size of the
  document they came out of, so one decision's worth of data is a constant.
  `orset` and `doc` hold collections that grow with the document and are
  refused by the interpreter's node limit well below a realistic document; the
  numbers are recorded in `kotoba.crdt.kotoba-oracle`. `doc.cljc` reaches this
  namespace once per field, which is how a document whose state cannot cross
  still has its per-field winner decided by the shipped core.

  ## The value/stamp boundary, stated

  `register.kotoba` types values `:string` and stamps `:i64`; this namespace has
  always accepted any value and any comparable actor id, and `doc`'s README
  stores `1.5` under a string actor. Delegating unconditionally would narrow
  that public API, so it is conditional: when a call's values are ones the guest
  can hold, the shipped core answers, and otherwise the host path answers with
  exactly the behaviour it had before. Which path runs is decided by the DATA,
  never by whether the artifact loaded — a missing artifact throws rather than
  falling back.

  A register also has to cross back whole. Unlike a clock, which is a host map
  the guest decides one field of, a register IS the guest value, so a map
  carrying anything beyond the fields the artifact declares is left to the host
  path rather than silently returned without them.

  Two consequences worth saying out loud:

  - A non-string value, or a non-integer actor, is served by host code that no
    `.kotoba` checks. `register-test` covers that path and
    `register-kotoba-parity-test` covers the overlap, but the host path is not
    derived from the guest and will not be until values and actors are.
  - `:string` is bounded at 65536 UTF-8 bytes on the guest side. A longer value
    takes the host path rather than raising, since a document field is allowed
    to be longer than the guest can hold.

  ## ClojureScript hosts must register the KIR

  There is no classpath to read the artifact from, so a ClojureScript host has
  to `kotoba.crdt.kotoba-oracle/register-kir!` before a string-valued register
  will work; without it these throw. See the same note on `kotoba.crdt.clock`."
  (:require [kotoba.crdt.clock :as clock]
            [kotoba.crdt.kotoba-oracle :as oracle]))

;; ── the host <-> guest ABI ───────────────────────────────────────────
;;
;; Every type is READ BACK from the shipped artifact rather than written out
;; here, so the record's fields and — the part that matters for a positional
;; ABI — their declared order come from the source of the rule. Delays, not
;; defs: on a runtime with no classpath the artifact arrives via
;; `register-kir!`, which cannot have happened while this namespace loaded.

(def ^:private register-type (delay (:result (oracle/signature :register 'write))))
(def ^:private stamp-type (delay (second (oracle/param-types :register 'write))))
(def ^:private option-type (delay (:result (oracle/signature :register 'init))))

(defn- host-key
  "Guest field name -> the key a kotoba.crdt host map holds it under. The one
  piece of vocabulary the two sides do not share."
  [field]
  (keyword "crdt" (name field)))

;; A register nests a stamp, so these three walk the declared type rather than
;; mapping one conversion over a flat field list the way `clock` can.

(defn- crossable?
  "Whether `v` can cross as `type` without changing what it means.

  A record has to match EXACTLY — every declared field present and crossable,
  and no other key — because the guest returns only what it declared, so a map
  with more in it could not be rebuilt from the answer."
  [type v]
  (case type
    :i64 (oracle/fits-i64? v)
    :string (oracle/fits-string? v)
    (let [fields (oracle/record-fields type)]
      (and (map? v)
           (= (count v) (count fields))
           (every? (fn [[field field-type]]
                     (and (contains? v (host-key field))
                          (crossable? field-type (get v (host-key field)))))
                   fields)))))

(defn- ->guest [type v]
  (case type
    :i64 (oracle/i64 v)
    :string v
    (oracle/record type (map (fn [[field field-type]]
                               (->guest field-type (get v (host-key field))))
                             (oracle/record-fields type)))))

(defn- <-guest [type v]
  (case type
    :i64 (oracle/i64-value v)
    :string v
    (into {} (map (fn [[field field-type] field-value]
                    [(host-key field) (<-guest field-type field-value)])
                  (oracle/record-fields type)
                  (oracle/record-values v)))))

(defn- ->guest-option [register]
  (if (nil? register)
    (oracle/option-none @option-type)
    (oracle/option-some @option-type (->guest @register-type register))))

(defn- <-guest-option [guest-option]
  (some->> (oracle/option-value guest-option) (<-guest @register-type)))

(defn- crossable-option?
  "Absence crosses as `none`; anything else has to be a whole register."
  [register]
  (or (nil? register) (crossable? @register-type register)))

;; ── the four the shipped core decides ────────────────────────────────

(defn init []
  ;; No arguments, so nothing to be conditional on: the guest answers `none`
  ;; and absence is `nil` on this side.
  (<-guest-option (oracle/call :register 'init [])))

(defn write [value stamp]
  (if (and (oracle/fits-string? value) (crossable? @stamp-type stamp))
    (<-guest @register-type
             (oracle/call :register 'write [value (->guest @stamp-type stamp)]))
    {:crdt/value value :crdt/stamp stamp}))

(defn value [register]
  (if (crossable? @register-type register)
    (oracle/call :register 'value [(->guest @register-type register)])
    (:crdt/value register)))

(defn merge-register
  "Deterministic under any arrival order: the register with the later stamp
  always wins, whichever side of the merge it's passed as."
  [a b]
  (if (and (crossable-option? a) (crossable-option? b))
    (<-guest-option (oracle/call :register 'merge-register
                                 [(->guest-option a) (->guest-option b)]))
    (cond
      (nil? a) b
      (nil? b) a
      (clock/before? (:crdt/stamp a) (:crdt/stamp b)) b
      :else a)))
