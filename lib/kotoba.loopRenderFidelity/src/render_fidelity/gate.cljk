(ns render-fidelity.gate
  "Whether a run is better than the last one, or worse.

  ## Why a baseline and not a threshold

  There is no number of undrawn regions that is *correct*. What is knowable
  is whether today's run has more of them than yesterday's over the same
  corpus, and that comparison needs a recorded previous run rather than a
  constant somebody chose.

  So the gate is a **ratchet**: metrics that should only fall may not rise,
  metrics that should only rise may not fall, and anything else is
  reported without an opinion. A ratchet is also what makes the loop safe
  to run often — it cannot be satisfied by lowering a bar.

  ## The corpus moves, so rates are compared and counts are not

  Documents come and go from a local corpus — a file syncs, a cloud
  placeholder evicts. Comparing raw counts across runs would call that a
  regression. Rates over what was actually measured survive it, and the
  ratchet uses those; the counts go in the ledger for a person to read.

  One exception, and it is the important one: **invented characters are
  compared as a count, and the only acceptable count is zero.** A rate would
  let a hundred fabricated characters hide behind a bigger corpus."
  (:require [kotoba.lang.text :as str]))

(defn- fmt
  "A rate to three places, portably.

  `format` is JVM-only and this file is `.cljc` — a claim of portability
  that a linter checks and a test suite does not, because nothing here runs
  on ClojureScript yet. Same shape of mistake as a `:require` whose only
  entry is `:clj`."
  [x]
  (let [r (/ (Math/round (* 1000.0 (double x))) 1000.0)]
    (str r)))

(defn- rate
  "nil when nothing was measured, not 1.0.

  A run that measured nothing knows nothing, and calling that a perfect
  score records a bar no real run can clear. Demonstrated on this loop's
  own first run: an empty corpus set agreement to 1.000 and the next run —
  the first one with documents in it — was reported as a regression."
  [n d]
  (when (pos? (long d)) (/ (double n) (long d))))

(defn rates
  "The comparable shape of a summary."
  [s]
  {:oracle/agreement (rate (:oracle/agree s) (:oracle/comparable s))
   :undrawn-per-document (rate (reduce + 0 (vals (:undrawn s)))
                               (:documents/measured s))
   :measured (rate (:documents/measured s) (:documents/seen s))})

(def ^:private tolerance
  "How much a rate may drift without being called a regression.

  A corpus that changes by one document changes every rate a little, and a
  gate that fires on that is a gate people turn off. 1% is below any real
  regression this has seen and above the noise of a document appearing."
  0.01)

(defn verdict
  "`{:pass? :findings}` for a run against the previous one.

  A first run always passes and says so — there is nothing to ratchet
  against, and failing it would mean the loop can never be started."
  [current previous]
  (if-not (and previous (pos? (long (or (:documents/measured previous) 0))))
    {:pass? true
     :findings [{:kind :baseline
                 :message (str "No previous run with any documents in it — "
                               "nothing to ratchet against yet.")}]}
    (let [now (rates current) was (rates previous)
          worse (fn [k dir label]
                  (let [a (get now k) b (get was k)
                        ;; Either side unknown means there is nothing to
                        ;; compare, not that something got worse.
                        moved (when (and a b) (if (= dir :up) (- b a) (- a b)))]
                    (when (and moved (> moved tolerance))
                      {:kind :regression :metric k :was b :now a
                       :message (str label ": " (fmt b) " → " (fmt a))})))
          invented (:oracle/invented current)
          findings
          (cond-> (keep identity
                        [(worse :oracle/agreement :up "agreement with the independent reader fell")
                         (worse :undrawn-per-document :down "undrawn regions per document rose")])
            (pos? (long (or invented 0)))
            (conj {:kind :invention :count invented
                   :message (str invented " characters the independent reader did not see. "
                                 "The renderer may lose characters it cannot decode; "
                                 "it may never add ones nobody wrote.")}))]
      {:pass? (empty? findings)
       :findings (vec findings)})))

(defn targets
  "What to look at next, largest first.

  Not advice about how to fix anything — the loop does not know that. It is
  the list of what the renderer itself says it could not draw, ordered by
  how often it said so, because that ordering is the one piece of
  prioritisation a count can honestly provide."
  [summary]
  (->> (:undrawn summary)
       (sort-by (comp - val))
       (map (fn [[reason n]] {:reason reason :count n}))
       vec))

(defn render-report
  "The run as text, for a person."
  [{:keys [summary verdict targets]}]
  (str/join
   "\n"
   (concat
    [(str "documents: " (:documents/measured summary) " measured of "
          (:documents/seen summary) " seen")
     (str "marks: " (pr-str (:marks summary)) "  clips: " (:clips summary)
          "  chars: " (:chars summary))
     (str "oracle: " (:oracle/agree summary) "/" (:oracle/comparable summary)
          " pages agree · invented " (:oracle/invented summary)
          " · lost " (:oracle/lost summary))]
    (when (seq (:documents/errors summary))
      ;; Named, because "8 threw" is not something anybody can act on and
      ;; the messages are the whole difference between a broken renderer
      ;; and eight files that are not PDFs.
      (cons (str "errors: " (pr-str (:documents/errors summary)))
            (map (fn [[m n]] (str "  " n "  " m))
                 (sort-by (comp - val) (:documents/messages summary)))))
    (when (seq targets)
      (cons "undrawn, largest first:"
            (map #(str "  " (:count %) "  " (:reason %)) targets)))
    [""
     (if (:pass? verdict) "PASS" "FAIL")]
    (map #(str "  - " (:message %)) (:findings verdict)))))
