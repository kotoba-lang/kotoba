(ns code-graph.evidence
  "The evidence planes for the records this repository writes.

  `kotobase.evidence` lifts a plane's records onto a versioned contract under
  one rule: the supplement a caller passes must be exactly the fields the
  source does not carry. It registers the planes whose records *kotobase*
  writes. These two are written here, and a carrier for them could not live
  there — this repository depends on kotobase, so it would be either a
  dependency cycle or a copy of these shapes, and a copy of a shape is what
  that namespace exists to stop being necessary.

  So they are defined where the records are written, and handed in."
  (:require [kotobase.evidence :as evidence]))

(defn- reject! [reason data]
  (throw (ex-info "code-graph evidence rejected"
                  (assoc data :code-graph.evidence/reason reason))))

(defn- non-empty-string? [value]
  (and (string? value) (seq value)))

(defn- query-carried
  "A query receipt read with the execution identity that binds it.

  The identity is not optional, and the binding is rechecked here even though
  the write path checks it: a record only its author ever checked is checked
  once. What the record answers is the version 1 receipt it embeds — every
  field of it — because a read that produced no such receipt is not one this
  plane can be evidence of."
  [{:keys [receipt execution-identity] :as source}]
  (when-not (and (map? source)
                 (= #{:receipt :execution-identity} (set (keys source)))
                 (map? receipt) (map? execution-identity))
    (reject! :unreadable-source {:plane :code-graph-query}))
  (when-not (contains? (set (:host-receipt-cids execution-identity))
                       (:cid receipt))
    (reject! :receipt-not-bound-by-identity {:receipt-cid (:cid receipt)}))
  (when-not (= (:basis receipt) (:db-basis execution-identity))
    (reject! :basis-mismatch {:receipt (:basis receipt)
                              :identity (:db-basis execution-identity)}))
  (when-not (= (:policy-cid receipt) (:policy-cid execution-identity))
    (reject! :policy-mismatch {:receipt (:policy-cid receipt)
                               :identity (:policy-cid execution-identity)}))
  (let [embedded (:execution-receipt receipt)]
    (when-not (map? embedded)
      (reject! :unreadable-source {:plane :code-graph-query
                                   :field :execution-receipt}))
    (when-not (= (:result-cid receipt) (:result/root embedded))
      (reject! :result-root-mismatch {}))
    (when-not (= (:plan-cid execution-identity) (:query/plan-digest embedded))
      (reject! :plan-digest-mismatch {}))
    (select-keys embedded (evidence/answerable :query-execution))))

(defn- execution-carried
  "What a code-graph execution receipt answers about the build it recorded.

  The action is a constant because the record exists only when an artifact was
  built from an admitted code graph, so `:build` and `:allow` are what its
  existence means rather than fields it forgot to carry. Its output roots are
  the outcome."
  [record]
  (when-not (and (map? record)
                 (non-empty-string? (:artifact-cid record))
                 (non-empty-string? (:package-lock-cid record))
                 (non-empty-string? (:policy-cid record))
                 (set? (:granted-effects record))
                 (vector? (:output-root-cids record))
                 (seq (:output-root-cids record))
                 (every? non-empty-string? (:output-root-cids record)))
    (reject! :unreadable-source {:plane :code-graph-execution}))
  {:authority/decision :allow
   :effect/action :build
   :effect/resource (:artifact-cid record)
   :code/lock (:package-lock-cid record)
   :effect/granted (:granted-effects record)
   :authority/policy (:policy-cid record)
   :outcome/roots (:output-root-cids record)})

(def query-plane
  "A query receipt with its execution identity, as a query execution."
  {:subject :query-execution :carry query-carried})

(def execution-plane
  "One artifact build, as an authorised effect."
  {:subject :authorised-effect :carry execution-carried})
