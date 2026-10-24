(ns quarantine.core
  "Reversible removal, the pure half.

  The idea this library exists to make reusable: **a tool that removes things
  chosen by a heuristic should not have a delete opcode.** It moves them into a
  per-run vault together with a manifest sufficient to put them back exactly,
  and destroying those bytes is a separate, later, explicitly acknowledged
  operation gated on a retention floor.

  This namespace holds the manifest schema, retention arithmetic and receipt
  construction. It performs no IO — `quarantine.host` does that — so the rules
  about what is allowed to be destroyed are testable without a filesystem.

  Extracted from gftdcojp/ai-gftd-misogi, where it was verified by a real
  filesystem round trip asserting mode and mtime survive."
  (:require [kotoba.lang.text :as str]))

(def ^:const manifest-schema "quarantine.manifest.v1")
(def ^:const receipt-schema "quarantine.receipt.v1")
(def ^:const day-ms 86400000)

(def ^:const default-retention-days
  "How long a vault run is protected from purging. Long enough that a wrong
  removal is noticed by ordinary use before the bytes are gone."
  7)

;; ---------------------------------------------------------------------------
;; run identity
;; ---------------------------------------------------------------------------

(defn run-id
  "Sortable, collision-resistant run id. `now-ms` is passed in rather than read
  from the clock so a run is reproducible in tests."
  [now-ms]
  (str "run-" (-> (str #?(:clj (java.time.Instant/ofEpochMilli (long now-ms))
                          :cljs (.toISOString (js/Date. now-ms))))
                  (str/replace #"[:.]" "-")
                  (str/replace #"Z$" ""))))

;; ---------------------------------------------------------------------------
;; manifest
;; ---------------------------------------------------------------------------

(defn item
  "One quarantined item. Everything needed to restore it byte-for-byte at its
  original path, plus the provenance of why it was moved."
  [{:keys [index original-path vault-path bytes mode mtime-ms rule-id rules]}]
  (cond-> {:index index
           :original-path original-path
           :vault-path vault-path
           :bytes (or bytes 0)}
    mode (assoc :mode mode)
    mtime-ms (assoc :mtime-ms mtime-ms)
    rule-id (assoc :rule/id rule-id)
    (seq rules) (assoc :rules (vec rules))))

(defn manifest
  [{:keys [run-id created-ms policy-id plan-id items]}]
  {:vault/schema manifest-schema
   :vault/run-id run-id
   :vault/created-ms created-ms
   :policy/id policy-id
   :plan/id plan-id
   :vault/items (vec items)})

(defn run-age-days [manifest now-ms]
  (quot (- now-ms (:vault/created-ms manifest 0)) day-ms))

(defn purged? [manifest] (some? (:vault/purged-ms manifest)))

(defn total-bytes [manifest]
  (reduce + 0 (map #(:bytes % 0) (:vault/items manifest))))

(defn mark-purged
  "A purged run keeps its manifest and loses its items. A run that was purged
  must remain visible as having existed — otherwise the only irreversible
  operation in the system is also the only untraceable one."
  [manifest now-ms]
  (assoc manifest :vault/purged-ms now-ms :vault/items []))

;; ---------------------------------------------------------------------------
;; the purge gate — the one place irreversibility is decided
;; ---------------------------------------------------------------------------

(defn purge-verdict
  "May this run be destroyed? Returns {:allowed? bool :reason kw ...}.

  Pure, and deliberately the only place that says yes. `quarantine.host/purge!`
  calls it and refuses on anything but `:allowed`, so a caller cannot reach
  destruction by passing a different argument shape."
  [manifest {:keys [now-ms retention-days acknowledged?]}]
  (let [retention (or retention-days default-retention-days)]
    (cond
      (nil? manifest)
      {:allowed? false :reason :no-such-run}

      (purged? manifest)
      {:allowed? false :reason :already-purged}

      (not acknowledged?)
      {:allowed? false :reason :not-acknowledged}

      (< (run-age-days manifest now-ms) retention)
      {:allowed? false :reason :within-retention
       :age-days (run-age-days manifest now-ms)
       :retention-days retention}

      :else
      {:allowed? true :reason :allowed
       :age-days (run-age-days manifest now-ms)
       :retention-days retention
       :item-count (count (:vault/items manifest))
       :bytes (total-bytes manifest)})))

(defn purgeable?
  "Whether a run has aged past the floor — the listing-level question, which is
  not the same as being allowed to purge (that also needs acknowledgement)."
  [manifest {:keys [now-ms retention-days]}]
  (and (not (purged? manifest))
       (>= (run-age-days manifest now-ms)
           (or retention-days default-retention-days))))

;; ---------------------------------------------------------------------------
;; receipts
;; ---------------------------------------------------------------------------

(defn- receipt [kind run-id now-ms extra]
  (merge {:receipt/schema receipt-schema
          :receipt/kind kind
          :receipt/run-id run-id
          :receipt/at-ms now-ms}
         extra))

(defn quarantine-receipt
  [{:keys [run-id now-ms vault-path moves failures]}]
  (receipt :quarantine run-id now-ms
           {:quarantine/vault-path vault-path
            :quarantine/moved-count (count moves)
            :quarantine/moved-bytes (reduce + 0 (map #(:bytes % 0) moves))
            :quarantine/failure-count (count failures)
            :quarantine/failures (vec failures)
            :quarantine/reversible? true}))

(defn restore-receipt
  [{:keys [run-id now-ms vault-path restored failures]}]
  (receipt :restore run-id now-ms
           {:restore/vault-path vault-path
            :restore/restored-count (count restored)
            :restore/failure-count (count failures)
            :restore/failures (vec failures)}))

(defn purge-receipt
  "The only receipt that records irreversible loss. Carries the retention proof
  and whether the bytes were overwritten, so a purge that happened too early or
  claimed a secure erase it did not perform stays visible forever."
  [{:keys [run-id now-ms vault-path verdict overwrite-passes overwritten?]}]
  (receipt :purge run-id now-ms
           {:purge/vault-path vault-path
            :purge/age-days (:age-days verdict)
            :purge/retention-days (:retention-days verdict)
            :purge/purged-count (:item-count verdict)
            :purge/purged-bytes (:bytes verdict)
            :purge/overwritten? (boolean overwritten?)
            :purge/overwrite-passes (or overwrite-passes 0)
            :purge/reversible? false}))

(defn refusal-receipt
  "Recorded when the library declines to act. A refusal that leaves no trace is
  indistinguishable from a tool that quietly failed."
  [{:keys [run-id now-ms reason detail]}]
  (receipt :refusal run-id now-ms
           {:refusal/reason reason :refusal/detail detail}))
