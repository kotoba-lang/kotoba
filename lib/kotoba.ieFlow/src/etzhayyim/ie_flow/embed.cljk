(ns etzhayyim.ie-flow.embed
  "ie-flow.embed — the system-of-systems entry point: how EVERY actor embeds the information-energy
  flow lifecycle. ADR-2606211200.

  The user asked for this loop to be built into each actor so the colony of actors is a SYSTEM OF
  SYSTEMS — each one measuring its own flow, reasoning (co-scientist) about how to keep its flow
  paying while returning order, and persisting to its own kotoba ledger. Rather than fork the loop
  into ~80 actors, the loop is ONE shared library and each actor embeds it with three lines:

    (require '[etzhayyim.ie-flow.embed :as ie])
    (ie/record! \"<actor>\" measured-events {:as-of n})   ; feed the flow ledger
    (ie/beat! \"<actor>\" {:as-of n})                       ; run one co-scientist ReAct beat

  An actor may register a per-actor intervention catalog extension (its own aligned ways of acting
  on society) in `actor-registry` — but the SAFETY vocabulary (aligned/forbidden mechanisms, the
  gates) is shared and unforkable, so the system-of-systems shares one charter-clean safety property.

  Paths default under the DataLad data root `80-data/ie-flow/<actor>/` (real-world data as EDN,
  measured, content-addressed). Deterministic, no-server-key. Stdlib + ie-flow.{ledger,lifecycle}."
  (:require [kotoba.lang.text :as str]
            [etzhayyim.ie-flow.coscientist :as cosci]
            [etzhayyim.ie-flow.ledger :as ledger]
            [etzhayyim.ie-flow.lifecycle :as lifecycle]
            [etzhayyim.ie-flow.metrics :as metrics]
            [kotoba.datom :as kd]))

(def data-root "80-data/ie-flow")

;; ── the actor registry (data — who has embedded the substrate) ──────────────
;; Each entry may carry a per-actor :catalog (aligned-only) extension. The registry is the
;; system-of-systems roster; new adopters append a line. Loaded lazily so the lib stays pure.

(def actor-registry
  "Actors that embed the IE-flow lifecycle. :catalog (optional) extends the shared co-scientist
  catalog with the actor's own ALIGNED interventions (the generator stays a charter-clean catalog)."
  {"ibuki"   {:note "the artificial organism — its metabolism IS an information-energy flow"}
   "tsumugi" {:note "power-entity 取-concentration mirror → release is its negentropy export"}
   "shionome" {:note "cross-asset capital-flow observatory — flow is literally its substrate"}
   "kaname"  {:note "system-of-systems leverage synthesizer — IE-flow over the multiplex graph"}
   "okaimono" {:note "provisioning commons — checkout flow, value returned to members"}})

;; ── path resolution ─────────────────────────────────────────────────────────

(defn flow-log [actor] (str data-root "/" actor "/flow.kotoba.edn"))
(defn loop-log [actor] (str data-root "/" actor "/loop.kotoba.edn"))

(defn actor-catalog
  "The full co-scientist catalog for `actor` = the shared default + the actor's aligned extension,
  or nil to use the shared default unchanged."
  [actor]
  (when-let [c (get-in actor-registry [actor :catalog])]
    (vec (concat cosci/default-catalog c))))

;; ── the three embedding verbs ───────────────────────────────────────────────

#?(:clj
   (defn record!
     "Append a batch of measured flow EVENTS to `actor`'s flow ledger. Real-world measurement in,
     content-addressed (idempotent-by-content). Returns the append result."
     [actor events {:keys [as-of tx-id]}]
     (ledger/record-events! events {:log-path (flow-log actor)
                                    :as-of (or as-of "as-of:record")
                                    :tx-id (or tx-id (str actor "-flow"))})))

#?(:clj
   (defn measure
     "Fold `actor`'s flow ledger into the current IE-flow state vector (net-gain / order-index /
     agent-efficiency). Pure read."
     [actor]
     (metrics/flow-state (ledger/read-events (kd/read-log (flow-log actor))))))

#?(:clj
   (defn beat!
     "Run one IE-flow co-scientist ReAct beat for `actor` over its own flow ledger + loop log.
     `:infer` (optional) is the Murakumo narrator. Returns the lifecycle status map."
     [actor {:keys [as-of tx-id infer]}]
     (lifecycle/beat {:log-path (loop-log actor)
                      :flow-log (flow-log actor)
                      :catalog (actor-catalog actor)
                      :infer infer
                      :as-of as-of :tx-id tx-id})))
