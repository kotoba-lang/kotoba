(ns kami.modeling.collaboration
  "Content-addressed semantic operation history for online/offline CAD editing."
  (:require [kami.modeling.document :as document]))

(defn operation [id actor logical-time parent-revision command path value expected]
  (when-not (and (uuid? id) (string? actor) (integer? logical-time) (not (neg? logical-time))
                 (string? parent-revision) (#{:assoc :dissoc} command) (vector? path) (seq path))
    (throw (ex-info "invalid collaboration operation" {:id id :actor actor :path path})))
  {:operation/id id :operation/actor actor :operation/logical-time logical-time
   :operation/parent parent-revision :operation/command command :operation/path path
   :operation/value value :operation/expected expected})

(defn apply-operation [doc op]
  (when-not (= (:document/revision doc) (:operation/parent op))
    (throw (ex-info "operation parent does not match document" {:expected (:document/revision doc)
                                                                 :actual (:operation/parent op)})))
  (let [path (:operation/path op) actual (get-in doc path ::missing)]
    (when-not (= actual (:operation/expected op))
      (throw (ex-info "operation precondition failed" {:path path :expected (:operation/expected op)
                                                        :actual actual})))
    (document/transact doc (:operation/actor op)
                       {:command (:operation/command op) :operation/id (:operation/id op)
                        :logical-time (:operation/logical-time op) :path path}
                       #(case (:operation/command op)
                          :assoc (assoc-in % path (:operation/value op))
                          :dissoc (update-in % (pop path) dissoc (peek path))))))

(defn history [base-document]
  {:history/base base-document :history/head base-document :history/operations []
   :history/snapshots {(:document/revision base-document) base-document}})

(defn append-operation [history op]
  (let [next (apply-operation (:history/head history) op)]
    (-> history (assoc :history/head next) (update :history/operations conj op))))

(defn append-operation-idempotent [history op]
  (if (some #(= (:operation/id op) (:operation/id %)) (:history/operations history))
    (assoc history :history/last-delivery {:status :duplicate :operation (:operation/id op)})
    (assoc (append-operation history op) :history/last-delivery {:status :applied :operation (:operation/id op)})))

(defn checkpoint [history]
  (assoc-in history [:history/snapshots (get-in history [:history/head :document/revision])] (:history/head history)))

(defn replay [base operations]
  (reduce apply-operation base operations))

(defn branch [history]
  {:branch/base-revision (get-in history [:history/head :document/revision])
   :branch/base-document (:history/head history) :branch/operations [] :branch/head (:history/head history)})

(defn branch-append [branch actor logical-time command path value]
  (let [head (:branch/head branch)
        op (operation (random-uuid) actor logical-time (:document/revision head) command path value (get-in head path ::missing))
        next (apply-operation head op)]
    (-> branch (assoc :branch/head next) (update :branch/operations conj op))))

(defn- changes-from [base head]
  (letfn [(walk [path a b]
            (cond
              (= a b) []
              (and (map? a) (map? b))
              (mapcat (fn [k] (walk (conj path k) (get a k ::missing) (get b k ::missing)))
                      (sort-by str (into (set (keys a)) (keys b))))
              :else [{:path path :base a :value b}]))]
    (remove #(#{:document/revision :document/provenance} (first (:path %))) (walk [] base head))))

(defn merge-branches [left right actor logical-time]
  (when-not (= (:branch/base-revision left) (:branch/base-revision right))
    (throw (ex-info "branches do not share a base revision" {})))
  (let [base (:branch/base-document left) left-changes (changes-from base (:branch/head left))
        right-changes (changes-from base (:branch/head right))
        left-by-path (into {} (map (juxt :path identity) left-changes))
        right-by-path (into {} (map (juxt :path identity) right-changes))
        paths (sort-by pr-str (into (set (keys left-by-path)) (keys right-by-path)))
        conflicts (vec (keep (fn [path]
                               (let [l (get left-by-path path) r (get right-by-path path)]
                                 (when (and l r (not= (:value l) (:value r)))
                                   {:conflict/kind :concurrent-semantic-edit :conflict/path path
                                    :conflict/base (:base l) :conflict/left (:value l) :conflict/right (:value r)}))) paths))]
    (if (seq conflicts) {:merge/status :conflict :merge/conflicts conflicts}
      (let [merged-values (mapv (fn [path] (or (get left-by-path path) (get right-by-path path))) paths)
            merged (reduce (fn [doc {:keys [path value]}]
                             (if (= value ::missing) (update-in doc (pop path) dissoc (peek path))
                               (assoc-in doc path value)))
                           (dissoc base :document/revision :document/provenance) merged-values)
            parents [(get-in left [:branch/head :document/revision]) (get-in right [:branch/head :document/revision])]
            with-provenance (assoc merged :document/provenance {:parents parents :actor actor
                                                                 :operation {:command :merge :logical-time logical-time}})
            result (assoc with-provenance :document/revision (document/revision-id with-provenance))]
        {:merge/status :merged :merge/document result :merge/paths paths}))))

(defn resolve-conflict [merge-result conflict-index choice actor]
  (when-not (= :conflict (:merge/status merge-result)) (throw (ex-info "merge has no conflicts" {})))
  (let [conflict (nth (:merge/conflicts merge-result) conflict-index)]
    {:resolution/path (:conflict/path conflict) :resolution/value
     (case choice :left (:conflict/left conflict) :right (:conflict/right conflict)
           :base (:conflict/base conflict) (throw (ex-info "invalid conflict choice" {:choice choice})))
     :resolution/actor actor}))

(defn inverse-operation [doc-before op actor logical-time]
  (operation (random-uuid) actor logical-time (:document/revision (apply-operation doc-before op))
             :assoc (:operation/path op) (:operation/expected op) (:operation/value op)))

(defn audit [history]
  {:audit/operation-count (count (:history/operations history))
   :audit/actors (frequencies (map :operation/actor (:history/operations history)))
   :audit/head (get-in history [:history/head :document/revision])
   :audit/replay-valid? (= (:history/head history)
                           (replay (:history/base history) (:history/operations history)))})

(def permissions
  {:viewer #{} :commenter #{:comment} :editor #{:assoc :dissoc :comment}
   :reviewer #{:assoc :dissoc :comment :merge :release} :owner #{:assoc :dissoc :comment :merge :release :admin}})

(defn access-policy [document-id members]
  (when-not (and (uuid? document-id) (map? members)
                 (every? string? (keys members)) (every? permissions (vals members)))
    (throw (ex-info "invalid collaboration access policy" {})))
  {:policy/document document-id :policy/members members})

(defn authorized? [policy actor command]
  (contains? (get permissions (get-in policy [:policy/members actor]) #{}) command))

(defn operation-payload [op]
  ;; Stable canonical payload; signature bytes/strings are deliberately outside it.
  (pr-str (document/canonical-form (dissoc op :operation/signature :operation/signature-envelope))))

(defn sign-operation [op signer]
  (when-not (ifn? signer) (throw (ex-info "signature adapter must be callable" {})))
  (let [signature (signer (:operation/actor op) (operation-payload op))]
    (when-not (and (string? signature) (seq signature))
      (throw (ex-info "signature adapter returned invalid signature" {})))
    (assoc op :operation/signature signature)))

(defn verify-operation [op verifier]
  (and (string? (:operation/signature op))
       (boolean (verifier (:operation/actor op) (operation-payload op) (:operation/signature op)))))

(defn append-signed-operation [history policy op verifier]
  (when-not (authorized? policy (:operation/actor op) (:operation/command op))
    (throw (ex-info "operation is not authorized" {:actor (:operation/actor op)
                                                     :command (:operation/command op)})))
  (when-not (verify-operation op verifier)
    (throw (ex-info "operation signature verification failed" {:operation (:operation/id op)})))
  (append-operation-idempotent history op))

(defn revoke-member [policy actor revoker]
  (when-not (authorized? policy revoker :admin)
    (throw (ex-info "member revocation requires owner" {:revoker revoker})))
  (update policy :policy/members dissoc actor))

(defn permission-audit [policy operations]
  (let [entries (mapv (fn [op]
                        {:operation (:operation/id op) :actor (:operation/actor op)
                         :command (:operation/command op)
                         :authorized? (authorized? policy (:operation/actor op) (:operation/command op))}) operations)]
    {:permission-audit/entries entries
     :permission-audit/violations (vec (remove :authorized? entries))
     :permission-audit/valid? (every? :authorized? entries)}))

(defn replica [id history]
  (when-not (uuid? id) (throw (ex-info "replica id must be UUID" {})))
  {:replica/id id :replica/history history :replica/known-operations
   (set (map :operation/id (:history/operations history)))})

(defn sync-replicas
  "Deterministically exchange operation sets. Linear operations replay when
  their parents are present; divergent heads are preserved as explicit
  branches for semantic merge instead of last-writer-wins data loss."
  [a b]
  (let [all-ops (->> (concat (get-in a [:replica/history :history/operations])
                             (get-in b [:replica/history :history/operations]))
                     (reduce (fn [m op] (assoc m (:operation/id op) op)) {}) vals
                     (sort-by (juxt :operation/logical-time :operation/actor (comp str :operation/id))))
        base (get-in a [:replica/history :history/base])]
    (when-not (= (:document/revision base) (get-in b [:replica/history :history/base :document/revision]))
      (throw (ex-info "replicas do not share a base" {})))
    (loop [heads {(:document/revision base) base} pending (vec all-ops) applied []]
      (let [[heads' pending' applied' progressed?]
            (reduce (fn [[hs wait done progressed] op]
                      (if-let [parent (get hs (:operation/parent op))]
                        (let [next (apply-operation parent op)]
                          [(assoc hs (:document/revision next) next) wait (conj done op) true])
                        [hs (conj wait op) done progressed]))
                    [heads [] applied false] pending)]
        (if progressed? (recur heads' pending' applied')
          (let [child-parents (set (map :operation/parent applied'))
                tips (into {} (remove (comp child-parents key) heads'))
                result {:sync/status (cond (seq pending') :missing-parent (> (count tips) 1) :diverged :else :converged)
                        :sync/tips tips :sync/applied applied' :sync/pending pending'}]
            [(assoc a :replica/known-operations (set (map :operation/id applied')) :replica/sync result)
             (assoc b :replica/known-operations (set (map :operation/id applied')) :replica/sync result)]))))))

(defn resume-sync
  "Retry a prior missing-parent sync after either replica received more ops."
  [a b]
  (sync-replicas (dissoc a :replica/sync) (dissoc b :replica/sync)))

(defn presence [replica-id actor cursor selection timestamp]
  {:presence/replica replica-id :presence/actor actor :presence/cursor cursor
   :presence/selection selection :presence/timestamp timestamp :presence/ephemeral? true})

(defn canonical-history? [x]
  ;; Presence must never enter revisions, operations or snapshots.
  (and (nil? (:history/presence x))
       (not-any? #(contains? % :presence/ephemeral?) (:history/operations x))))

(defn public-key-record [key-id actor algorithm public-key created]
  (when-not (and (uuid? key-id) (string? actor) (#{:ed25519 :ecdsa-p256} algorithm)
                 (some? public-key) (integer? created))
    (throw (ex-info "invalid public key record" {:key-id key-id :actor actor :algorithm algorithm})))
  {:key/id key-id :key/actor actor :key/algorithm algorithm :key/public public-key
   :key/created created :key/status :active})

(defn keyring [records]
  {:keyring/keys (into {} (map (juxt :key/id identity) records))})

(defn rotate-key [keyring actor new-record]
  (when-not (= actor (:key/actor new-record)) (throw (ex-info "rotation actor mismatch" {})))
  (-> keyring
      (update :keyring/keys (fn [keys]
                              (into {} (map (fn [[id record]]
                                              [id (if (and (= actor (:key/actor record)) (= :active (:key/status record)))
                                                    (assoc record :key/status :retired) record)]) keys))))
      (assoc-in [:keyring/keys (:key/id new-record)] new-record)))

(defn revoke-key [keyring key-id reason logical-time]
  (when-not (get-in keyring [:keyring/keys key-id]) (throw (ex-info "key not found" {:key-id key-id})))
  (update-in keyring [:keyring/keys key-id] assoc :key/status :revoked
             :key/revocation-reason reason :key/revoked-at logical-time))

(defn sign-operation-with-key [op key-record signer]
  (when-not (and (= :active (:key/status key-record)) (= (:operation/actor op) (:key/actor key-record)))
    (throw (ex-info "operation cannot use inactive or foreign key" {:key (:key/id key-record)})))
  (let [payload (operation-payload op)
        signature (signer key-record payload)]
    (when-not (and (string? signature) (seq signature)) (throw (ex-info "key signer returned invalid signature" {})))
    (assoc op :operation/signature-envelope {:signature/key-id (:key/id key-record)
                                              :signature/algorithm (:key/algorithm key-record)
                                              :signature/value signature})))

(defn verify-operation-with-keyring [op keyring verifier]
  (let [{:signature/keys [key-id algorithm value]} (:operation/signature-envelope op)
        record (get-in keyring [:keyring/keys key-id])]
    (and record (= :active (:key/status record)) (= algorithm (:key/algorithm record))
         (= (:operation/actor op) (:key/actor record))
         (boolean (verifier record (operation-payload op) value)))))

(defn append-keyring-operation [history policy op keyring verifier]
  (when-not (authorized? policy (:operation/actor op) (:operation/command op))
    (throw (ex-info "operation is not authorized" {:actor (:operation/actor op)})))
  (when-not (verify-operation-with-keyring op keyring verifier)
    (throw (ex-info "keyring signature verification failed" {:operation (:operation/id op)})))
  (append-operation-idempotent history op))
