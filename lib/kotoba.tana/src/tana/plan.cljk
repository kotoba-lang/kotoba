(ns tana.plan
  "Predicate in, byte ranges out — without opening an object.

  `columnar.plan` answers *which chunks of this file* and reads them.
  This answers *which bytes of which objects*, and reads nothing: the caller
  is handed ranges and fetches them however its host fetches (an S3 GET with
  a `Range` header, an R2 binding, a CARv2 frame, a browser `fetch`).

  ## The pruning rule is borrowed, never copied

  `columnar.stats/skip?` decides. It is required here rather than
  reimplemented, because a second copy of a pruning rule drifts in the worst
  direction: fetching too few ranges throws (loud), while pruning by a stale
  copy of the rule reads chunks the real planner would have skipped and
  **returns the correct answer** — the bug is invisible in every result and
  visible only in the bill. `net-kotobase/lake` states the same rule for the
  trampoline, and this is the same seam one level up.

  ## Three outcomes per chunk, and they must stay distinguishable

  - **pruned** — statistics proved no row can match.
  - **read** — statistics could not rule it out.
  - **undecidable** — the chunk records no bounds for a predicate column, so
    it is read. This is *not* a prune and must never be counted as one: a
    planner that reports `0 read` because it could not decide anything looks
    exactly like a planner that pruned everything.

  ## Pruning decides what to read, never what matches

  Bounds may be wider than the data. Every fetched chunk still has the
  predicate applied exactly, by whatever engine decodes it. This plan is a
  fetch list, not an answer."
  (:require [columnar.stats :as stats]))

(def ^:private trusts
  {;; A root this process produced. Trusting your own output needs no
   ;; signature; trusting one that arrived over a wire does, which is the
   ;; distinction `:from-footers` alone could not express.
   :local        #{:from-footers :declared}
   :from-footers #{:from-footers}
   ;; A caller that trusts declared bounds trusts extracted ones too: the
   ;; extracted case is strictly the stronger claim.
   :declared     #{:from-footers :declared}
   ;; Trust nothing. The root is used for location only; every chunk is read.
   :location-only #{}})

(defn- pred-columns [predicates] (into #{} (map second) predicates))

(defn- decidable?
  "Does this chunk record bounds for every column the predicates mention?"
  [chunk predicates]
  (every? (fn [col]
            (let [s (get-in chunk [:columns col :stats])]
              (and (contains? s :min) (contains? s :max))))
          (pred-columns predicates)))

(defn- coalesce
  "Merge ranges within one object that touch, overlap, or sit within `gap`.

  Round trips are the cost being minimised, so two chunks 40 bytes apart are
  one request. The extra bytes are reported rather than hidden: `stats` on a
  pack store does the same, for the same reason — a caller cannot otherwise
  tell a plan that coalesced from one that fetched everything."
  [fetches gap]
  (->> (group-by :object fetches)
       (mapcat (fn [[object fs]]
                 (let [sorted (sort-by (comp first :range) fs)]
                   (reduce
                    (fn [acc f]
                      (let [[s e] (:range f)
                            prev (peek acc)
                            [ps pe] (:range prev)]
                        (if (and prev (<= (- s pe) gap))
                          (conj (pop acc)
                                (-> prev
                                    (assoc :range [ps (max pe e)])
                                    (update :covers conj (dissoc f :covers))))
                          (conj acc {:object object :range [s e]
                                     :covers [(dissoc f :covers)]}))))
                    [] sorted))))
       vec))

(defn select-manifests
  "Which manifests of a sharded `top` a query must fetch.

  -> `{:fetch [address ...] :manifests {:total :pruned :read :undecidable}}`.
  Pure: the caller does the fetching, then calls `plan` with the manifests it
  got back. Keeping IO out of here is what lets the same planner run in a
  Worker, a browser and a JVM test."
  [top {:keys [predicates trust] :as _query}]
  (when-not (contains? trusts trust)
    (throw (ex-info "a plan must say which bounds it trusts"
                    {:type :tana/no-trust :allowed (set (keys trusts)) :got trust})))
  (let [entries (vec (:manifests top))]
    (if (empty? entries)
      {:refused :no-manifests :table (:table top)}
      ;; A sharded top carries per-manifest bounds, so it is the same trust
      ;; question one level up: an unsigned top that arrived over a wire can
      ;; rule out a manifest whose members would have matched, and the reader
      ;; never fetches the bytes that would say so.
      (let [signed? (or (= :local trust) (some? (:table/verified-signer top)))
            trusted? (and signed? (contains? (trusts trust) (:bounds-authority top)))
            preds (if trusted? (vec predicates) [])
            acc (reduce
                 (fn [acc entry]
                   (let [stats-of (fn [col] (get-in entry [:bounds col]))]
                     (if (and (seq preds) (stats/skip? stats-of preds))
                       (update acc :pruned inc)
                       (let [undecided? (and (seq preds)
                                             (not (every? #(let [s (stats-of %)]
                                                             (and (contains? s :min)
                                                                  (contains? s :max)))
                                                          (pred-columns preds))))]
                         (cond-> (-> acc
                                     (update :read inc)
                                     (update :fetch conj (:manifest entry)))
                           undecided? (update :undecidable inc))))))
                 {:fetch [] :pruned 0 :read 0 :undecidable 0} entries)]
        {:fetch (:fetch acc)
         :manifests {:total (count entries) :pruned (:pruned acc)
                     :read (:read acc) :undecidable (:undecidable acc)}
         :pruning (cond trusted? :enabled
                        (not signed?) :disabled-unverified-root
                        :else :disabled-by-trust)}))))

(defn plan
  "A fetch plan for `query` over `root`.

  `query` is `{:columns [..] :predicates [..] :trust ..}`, plus optional
  `:coalesce-gap` (default 0) and `:readable-codecs` (a set; chunks outside
  it are refused before any byte is fetched).

  `:trust` is required and has no default — see `tana.table`. The failure it
  guards is silent: bounds narrower than the data delete rows from an answer
  that still looks like an answer."
  [root {:keys [columns predicates trust coalesce-gap readable-codecs]
         :or {coalesce-gap 0}}]
  (when-not (contains? trusts trust)
    (throw (ex-info "a plan must say which bounds it trusts"
                    {:type :tana/no-trust :allowed (set (keys trusts)) :got trust})))
  (let [members (vec (:members root))]
    (if (empty? members)
      ;; Evidence floor. A table with no members has not pruned anything, and
      ;; an empty fetch list is the same value a fully-pruned plan returns.
      {:refused :no-members :table (:table root)}
      (let [known (set (:columns root))
            unknown (remove known columns)
            _ (when (seq unknown)
                (throw (ex-info "column not in this table"
                                {:type :tana/unknown-column
                                 :columns (vec unknown) :table (:columns root)})))
            ;; A fetched root's bounds are only as good as its signature.
            ;; `:local` is the caller saying it made this root itself.
            signed? (or (= :local trust) (some? (:table/verified-signer root)))
            trusted? (and signed? (contains? (trusts trust) (:bounds-authority root)))
            preds (if trusted? (vec predicates) [])
            init {:fetch [] :refused [] :pruned 0 :read 0 :undecidable 0
                  :members-pruned 0 :chunks 0}
            acc
            (reduce
             (fn [acc member]
               (reduce
                (fn [acc chunk]
                  (let [acc (update acc :chunks inc)
                        stats-of (fn [col] (get-in chunk [:columns col :stats]))]
                    (cond
                      (and (seq preds) (stats/skip? stats-of preds))
                      (update acc :pruned inc)

                      :else
                      (let [undecided? (and (seq preds) (not (decidable? chunk preds)))
                            acc (cond-> (update acc :read inc)
                                  undecided? (update :undecidable inc))]
                        (reduce
                         (fn [acc col]
                           (let [c (get-in chunk [:columns col])]
                             (cond
                               (nil? c) acc          ; absent column: all-null
                               (and readable-codecs
                                    (not (contains? readable-codecs (:codec c))))
                               (update acc :refused conj
                                       {:object (:object member) :column col
                                        :codec (:codec c) :reason :unreadable-codec})
                               :else
                               (update acc :fetch conj
                                       {:object (:object member)
                                        :range (:range c)
                                        :column col
                                        :rows (:rows chunk)}))))
                         acc columns)))))
                acc (:chunks member)))
             init members)
            fetch (coalesce (:fetch acc) coalesce-gap)
            bytes (reduce + 0 (map (fn [{[s e] :range}] (- e s)) fetch))]
        {:fetch fetch
         :refused (:refused acc)
         ;; 1 for the root itself. It is a real request and hiding it would
         ;; make the comparison this library exists for dishonest.
         :rounds (inc (count fetch))
         :bytes bytes
         :chunks {:total (:chunks acc)
                  :pruned (:pruned acc)
                  :read (:read acc)
                  :undecidable (:undecidable acc)}
         :members {:total (count members)}
         :pruning (cond trusted? :enabled
                        (not signed?) :disabled-unverified-root
                        :else :disabled-by-trust)
         :trust trust
         :bounds-authority (:bounds-authority root)}))))
