(ns kotobase.server.ipns
  "Pure decision logic for `com.etzhayyim.apps.kotoba.ipns.{head,publish}`
  (ADR-2607061800) -- UNAUTHENTICATED reads, signature-gated writes.
  Authority is the record's own Ed25519 signature (`kotobase.ipns/verify-
  head`, from `kotoba-lang/kotobase-client`), not a CACAO -- a genuinely
  different trust model from `kotobase.server.handler`'s `datomic.transact`
  surface, kept as its own namespace rather than another `handle` case.

  Deliberately does NOT read or write storage itself (unlike
  `kotobase.server.handler`'s `do-*` fns, which own their storage calls) --
  `verify-and-decide-publish` takes the CURRENT record (already fetched by
  the caller) as a plain argument and returns a pure decision. This keeps
  the actual read + conditional-write orchestration (R2's onlyIf, B2's
  equivalent, ...) entirely the caller's concern, matching how
  `do-transact`'s own head CAS is caller-orchestrated too.

  Extracted 2026-07-07 from `kotoba-lang/kotobase-cljc-worker`'s
  `worker.cljc` (`run-ipns-head`/`run-ipns-publish`), generalized away from
  R2 + js/Response construction.

  KNOWN LEXICON GAP, inherited unchanged (owner-confirmed in the source
  this was extracted from, not fixed here): records are keyed by the signed
  record's own `:name` field; a `graph` query param implying a graph-CID ->
  IPNS-name derivation is documented elsewhere but not implemented anywhere
  in this stack -- a separate, tracked follow-up."
  (:require [kotoba.lang.text :as str]
            [kotobase.ipns :as ipns]))

(defn- valid-sequence?
  "A `:sequence` value the rollback comparison below can safely `<=`.
  `(= x x)` is false for NaN on both JVM `Double` and JS `number` (IEEE-754
  self-inequality), so this catches NaN without a reader-conditional --
  needed because a non-numeric `:sequence` (e.g. a string) coerces to NaN
  under cljs's loose `<=`, and NaN compares false against everything, which
  silently disables the rollback guard rather than rejecting the write."
  [x]
  (and (number? x) (= x x)))

(defn head-response
  "Pure formatting for a `head` read: `record` is whatever the caller's
  storage returned for the queried `:name` (already JSON-decoded), or nil
  if absent. Returns `{:ok :status ...}`; `:ok true` responses include the
  record's own fields."
  [record]
  (if (nil? record)
    {:ok false :error "NotFound" :status 404}
    (assoc record :ok true :status 200)))

(defn verify-and-decide-publish
  "Pure decision for a `publish` write: verify `body`'s signature, then
  (if valid) reject a sequence rollback against `current` (the existing
  record for the same `:name`, or nil if this is the first publish).
  Returns `{:ok true}` (caller should proceed to the conditional write) or
  `{:ok false :error :status}` (caller should respond with that error,
  no write attempted)."
  [body current]
  (cond
    (not (:valid? (ipns/verify-head body)))
    {:ok false :error "InvalidSignature" :status 401}

    (not (valid-sequence? (:sequence body)))
    {:ok false :error "InvalidSequence" :status 400}

    (and current (not (valid-sequence? (:sequence current))))
    {:ok false :error "InvalidSequence" :status 400}

    (and current (<= (:sequence body) (:sequence current)))
    {:ok false :error "SequenceRollback" :status 409}

    :else {:ok true}))
