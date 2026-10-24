(ns catalog-maturity.core
  "Scoring truth for a reference CATALOG: how mature is it, where is it weakest,
  and what is the highest-leverage thing to do next.

  A library, not an orchestrator (see the workspace taxonomy in
  com-junkawasaki/root `manifest/repository-rules.edn`): it computes and ranks, it never fetches,
  writes, or schedules. `loop-*` repos own the running; this owns the meaning
  of the numbers, so the rubric can be tested and reused without standing up a
  runner.

  Every axis is computed from OBSERVED counts supplied by the caller. Nothing
  here estimates, extrapolates, or fills a missing input with a default that
  would flatter the score -- an axis with no observation returns
  `:unmeasured`, and an unmeasured axis is excluded from the total rather than
  scored as zero or as one. A catalog that cannot yet measure its own freshness
  should report that, not average it away.

  Motivation: the cloud-itonami-lei catalog reported '53 jurisdictions' while
  really covering 27 countries with the United States at 55% -- both numbers
  were arithmetically correct and together they were badly misleading. Breadth
  without concentration is a vanity metric, so concentration is a first-class
  axis here rather than a footnote.")

;; ── axes ────────────────────────────────────────────────────────────────────

(def axes
  "Each axis: an id, what it measures, and its weight in the total.

  Weights are deliberately NOT uniform. Breadth and concentration together
  decide whether the catalog is a world catalog or a regional one with a long
  tail, which is the question it exists to answer; provenance decides whether
  anything in it can be trusted at all. Reachability is useful but downstream
  of both -- a contact address for a company that should not be in the catalog
  is not progress."
  [{:id :breadth
    :doc "Distinct countries covered, against the target country set."
    :weight 0.25}
   {:id :concentration
    :doc "How far the catalog is from being dominated by one country. 1.0 when
          the largest country holds no more than its fair share; falls as one
          country's share grows."
    :weight 0.20}
   {:id :documentation
    :doc "Share of companies with at least one archived legal document."
    :weight 0.20}
   {:id :provenance
    :doc "Share of archived documents carrying BOTH a retrieval timestamp and a
          content hash. A document without provenance is an anecdote."
    :weight 0.20}
   {:id :reachability
    :doc "Share of companies with a published contact route."
    :weight 0.15}])

(def ^:private axis-weight (into {} (map (juxt :id :weight)) axes))

(defn- ratio
  "n/d clamped to [0,1], or `:unmeasured` when the denominator is absent or
  zero. Zero denominators are the common case for a young catalog and must not
  silently become 0.0 -- 'we have no companies yet' is not 'we scored zero on
  documentation'."
  [n d]
  (if (or (nil? n) (nil? d) (zero? d))
    :unmeasured
    (max 0.0 (min 1.0 (/ (double n) (double d))))))

(defn concentration-score
  "1.0 when no country exceeds `fair-share` of the catalog, falling linearly to
  0.0 as the largest country approaches the whole catalog.

  `fair-share` defaults to 1/8: a genuinely worldwide catalog should not have
  an eighth of itself in one country. Scored from the LARGEST share rather than
  an entropy measure on purpose -- the failure this guards against is one
  dominant country, and a single interpretable number ('the US is 55% of the
  catalog') is what makes that failure act-on-able."
  ([counts] (concentration-score counts 0.125))
  ([counts fair-share]
   (let [total (reduce + 0 (vals counts))]
     (if (or (zero? total) (empty? counts))
       :unmeasured
       (let [top (/ (double (apply max (vals counts))) (double total))]
         (cond
           (<= top fair-share) 1.0
           (>= top 1.0) 0.0
           :else (max 0.0 (/ (- 1.0 top) (- 1.0 fair-share)))))))))

(defn score-axes
  "Observation -> {axis-id score-or-:unmeasured}.

  OBS keys (all optional; anything missing yields :unmeasured for its axis):
    :companies          total company rows
    :country-counts     {country-code n}
    :target-countries   how many countries the catalog intends to cover
    :with-doc           companies having >=1 archived document
    :docs               total archived documents
    :docs-with-provenance  documents with BOTH retrieved-at and a hash
    :reachable          companies with a contact email or inquiry URL"
  [{:keys [companies country-counts target-countries with-doc docs
           docs-with-provenance reachable]}]
  {:breadth       (ratio (when country-counts (count country-counts)) target-countries)
   :concentration (if country-counts (concentration-score country-counts) :unmeasured)
   :documentation (ratio with-doc companies)
   :provenance    (ratio docs-with-provenance docs)
   :reachability  (ratio reachable companies)})

(defn maturity
  "Weighted total over the MEASURED axes only, renormalised by their weights.

  Excluding unmeasured axes rather than scoring them 0 keeps the number
  honest in both directions: a catalog is not penalised for a metric it cannot
  yet observe, and it cannot inflate its score by simply not measuring
  something. `:coverage` reports what fraction of the rubric's weight was
  actually observed, so a high score computed from one axis is visibly not the
  same as a high score computed from five."
  [scored]
  (let [measured (into {} (remove (comp #{:unmeasured} val)) scored)
        w (reduce + 0.0 (map axis-weight (keys measured)))]
    (if (zero? w)
      {:score :unmeasured :measured-weight 0.0 :axes scored}
      {:score (/ (reduce + 0.0 (map (fn [[k v]] (* v (axis-weight k))) measured)) w)
       :measured-weight w
       :axes scored})))

;; ── ranking the next action ─────────────────────────────────────────────────

(def ^:private axis->action
  {:breadth       {:action :acquire-new-country
                   :why "the catalog reaches fewer countries than it targets"}
   :concentration {:action :acquire-outside-dominant-country
                   :why "one country dominates the catalog, so more companies from it add size without adding reach"}
   :documentation {:action :archive-missing-documents
                   :why "companies are registered without the published document that justifies the entry"}
   :provenance    {:action :repair-document-provenance
                   :why "archived documents lack the timestamp or hash that makes them checkable"}
   :reachability  {:action :discover-contact-routes
                   :why "companies have no published contact route recorded"}})

(defn rank-actions
  "Weakest-first ranking of what to do next: shortfall x weight.

  Ranking by `(1 - score) * weight` rather than by raw score means a small
  deficit on a heavily-weighted axis can correctly outrank a large deficit on a
  minor one. Unmeasured axes are ranked ABOVE everything else -- not knowing a
  number is a worse position than knowing it is bad, because it cannot be
  acted on or even argued with."
  [scored]
  (->> scored
       (map (fn [[id v]]
              (merge {:axis id
                      :score v
                      :leverage (if (= :unmeasured v)
                                  ##Inf
                                  (* (- 1.0 v) (axis-weight id)))}
                     (axis->action id))))
       (sort-by :leverage >)
       vec))

(defn country-gaps
  "Target countries with no company yet, and the dominant country's share --
  the concrete inputs an acquisition step needs.

  Returns `:absent` sorted for stable output, so two runs over the same data
  produce the same plan and a diff between runs means the catalog changed, not
  that the ranking reshuffled."
  [country-counts target-country-set]
  (let [have (set (keys country-counts))
        total (reduce + 0 (vals country-counts))
        [top-c top-n] (when (seq country-counts) (apply max-key val country-counts))]
    {:absent (vec (sort (remove have target-country-set)))
     :present (count have)
     :target (count target-country-set)
     :dominant (when top-c {:country top-c :n top-n
                            :share (when (pos? total) (/ (double top-n) total))})}))

(defn plan
  "One cycle's evaluation: scores, maturity, ranked actions, and the country
  gaps. Pure -- the caller decides what, if anything, to run."
  [obs target-country-set]
  (let [scored (score-axes obs)]
    {:observed obs
     :axes scored
     :maturity (maturity scored)
     :actions (rank-actions scored)
     :gaps (country-gaps (or (:country-counts obs) {}) target-country-set)}))
