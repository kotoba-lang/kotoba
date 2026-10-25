(ns perfgate.core
  "The gate a performance claim has to pass before anyone may act on it.

  `layout`, `traversal`, `paging` and `ioplan` all produce plans with printed
  cost models. A model is an argument, not a measurement, and the gap between
  the two is where optimization fossils come from: a number that was true on
  the machine someone benchmarked once, kept as a constant, and quietly wrong
  everywhere after.

  So a plan may not be *claimed* on evidence it does not have. This namespace
  is the refusal:

  - **fewer samples than the policy demands** → not qualified;
  - **noise wider than the policy tolerates** → not qualified;
  - **no baseline to beat** → not qualified, because \"fast\" is not a
    property of one measurement;
  - **an improvement inside the combined noise** → not qualified, however
    large the ratio looks;
  - **arms measured on different machines, or against different metrics** →
    not qualified, and this is the one that catches real mistakes;
  - **a machine descriptor weaker than `:measured`** → not qualified. A claim
    resting on `machine.core/portable-64` rests on numbers nobody read off a
    device.

  And once qualified, a claim carries the fingerprint of the machine it was
  measured on, so `stale-on?` can answer the question that actually retires an
  optimization: *is this still the hardware you proved it on?*

  The statistics here are deliberately modest — mean, sample standard
  deviation, median, p95 — and the separation test is \"the gap exceeds the
  summed standard deviations\", which is a stated heuristic and not a p-value.
  Claiming a significance test this does not implement would be the same
  failure one level up.

  Pure `.cljc`. Depends only on `kotoba-lang/machine`."
  (:require [machine.core :as m]))

(def format-id :kotoba.perfgate/v1)
(def observation-format :kotoba.perfgate.observation/v1)
(def claim-format :kotoba.perfgate.claim/v1)

;; ── statistics ───────────────────────────────────────────────────────────

(defn- mean [xs] (if (seq xs) (/ (reduce + 0.0 xs) (count xs)) 0.0))

(defn- stdev
  "Sample standard deviation (n-1). Zero for a single sample, which is
  honest: one measurement carries no information about its own spread, and
  the gate refuses single samples anyway."
  [xs]
  (let [n (count xs)]
    (if (< n 2)
      0.0
      (let [mu (mean xs)]
        (Math/sqrt (/ (reduce + 0.0 (map #(let [d (- % mu)] (* d d)) xs))
                      (dec n)))))))

(defn- percentile [xs p]
  (if (empty? xs)
    0.0
    (let [sorted (vec (sort xs))
          idx (min (dec (count sorted))
                   (int (Math/floor (* p (count sorted)))))]
      (nth sorted idx))))

(defn summarize
  "Mean, spread and tail of a sample set."
  [xs]
  (let [xs (vec xs)
        mu (mean xs)
        sd (stdev xs)]
    {:n (count xs)
     :mean mu
     :stdev sd
     :relative-stdev (if (pos? mu) (/ sd mu) 0.0)
     :median (percentile xs 0.5)
     :p95 (percentile xs 0.95)
     :min (if (seq xs) (apply min xs) 0.0)
     :max (if (seq xs) (apply max xs) 0.0)}))

;; ── observations ─────────────────────────────────────────────────────────

(defn observation
  "One measured arm.

  `source` must say how the numbers were produced — the command, the harness,
  the counter. An observation whose provenance is unwritable is an
  observation nobody can repeat, and it is refused rather than accepted with
  an empty string."
  [{:keys [id plan-id machine metric unit samples source lower-is-better?]
    :or {lower-is-better? true}}]
  (when-not (and (string? source) (seq source))
    (throw (ex-info "an observation needs a non-empty source"
                    {:phase :perfgate/observation :id id})))
  (when-not (and (sequential? samples) (seq samples) (every? number? samples))
    (throw (ex-info "an observation needs at least one numeric sample"
                    {:phase :perfgate/observation :id id :samples samples})))
  (when-not (keyword? metric)
    (throw (ex-info "an observation needs a metric keyword"
                    {:phase :perfgate/observation :id id :metric metric})))
  (m/validate! machine)
  {:format observation-format
   :observation/id id
   :observation/plan-id plan-id
   :observation/machine-id (:machine/id machine)
   :observation/machine-fingerprint (m/fingerprint machine)
   :observation/machine-provenance (:machine/provenance machine)
   :observation/metric metric
   :observation/unit unit
   :observation/samples (vec samples)
   :observation/source source
   :observation/lower-is-better? lower-is-better?
   :observation/summary (summarize samples)})

;; ── policy ───────────────────────────────────────────────────────────────

(def default-policy
  {:policy/id :kotoba.perfgate.policy/default-v1
   :policy/min-samples 5
   :policy/max-relative-stdev 0.10
   :policy/min-improvement 0.05
   :policy/require-provenance :measured
   :policy/require-baseline? true})

;; ── qualification ────────────────────────────────────────────────────────

(defn- arm-reasons [label o policy]
  (let [{:keys [n relative-stdev]} (:observation/summary o)]
    (cond-> []
      (< n (:policy/min-samples policy))
      (conj {:reason :insufficient-samples :arm label
             :n n :required (:policy/min-samples policy)})

      (> relative-stdev (:policy/max-relative-stdev policy))
      (conj {:reason :too-noisy :arm label
             :relative-stdev relative-stdev
             :allowed (:policy/max-relative-stdev policy)})

      (not (m/at-least-as-strong? (:observation/machine-provenance o)
                                  (:policy/require-provenance policy)))
      (conj {:reason :provenance-too-weak :arm label
             :provenance (:observation/machine-provenance o)
             :required (:policy/require-provenance policy)
             :note "a claim resting on assumed hardware numbers rests on nothing measured"}))))

(defn qualify
  "Does this candidate beat this baseline hard enough to be claimed?

  Returns `{:qualified? … :reasons […] :improvement … :separation …}`. The
  reasons are the whole output when it fails — a bare `false` cannot be acted
  on, and the specific refusal is usually the instruction (\"take more
  samples\", \"you measured two different machines\")."
  ([candidate baseline] (qualify candidate baseline default-policy))
  ([candidate baseline policy]
   (let [policy (merge default-policy policy)
         reasons
         (cond-> (vec (concat (arm-reasons :candidate candidate policy)
                              (when baseline (arm-reasons :baseline baseline policy))))

           (and (:policy/require-baseline? policy) (nil? baseline))
           (conj {:reason :no-baseline
                  :note "\"fast\" is not a property of a single measurement"})

           (and baseline (not= (:observation/metric candidate)
                               (:observation/metric baseline)))
           (conj {:reason :metric-mismatch
                  :candidate (:observation/metric candidate)
                  :baseline (:observation/metric baseline)})

           (and baseline (not= (:observation/machine-fingerprint candidate)
                               (:observation/machine-fingerprint baseline)))
           (conj {:reason :machine-mismatch
                  :note "the two arms were measured on different hardware; the
                         difference between them is not the change you made"
                  :candidate (:observation/machine-id candidate)
                  :baseline (:observation/machine-id baseline)}))

         better? (:observation/lower-is-better? candidate)
         cs (:observation/summary candidate)
         bs (:observation/summary baseline)
         improvement (when baseline
                       (let [b (:mean bs) c (:mean cs)]
                         (cond
                           (not (pos? b)) 0.0
                           better? (/ (- b c) b)
                           :else (/ (- c b) (max b 1e-12)))))
         gap (when baseline (Math/abs (- (:mean bs) (:mean cs))))
         noise (when baseline (+ (:stdev bs) (:stdev cs)))
         separated? (when baseline (> gap noise))
         reasons
         (cond-> reasons
           (and baseline improvement (< improvement (:policy/min-improvement policy)))
           (conj {:reason :improvement-below-threshold
                  :improvement improvement
                  :required (:policy/min-improvement policy)})

           ;; Deliberately independent of the ratio. A 40% "win" whose arms
           ;; overlap within one standard deviation is a 40% description of
           ;; noise, and reporting the ratio without this check is how a
           ;; benchmark becomes folklore.
           (and baseline (not separated?))
           (conj {:reason :not-separated-from-noise
                  :gap gap :summed-stdev noise
                  :note "the arms are closer together than their own spread"}))]
     {:format format-id
      :qualified? (empty? reasons)
      :reasons reasons
      :improvement improvement
      :separation (when baseline {:gap gap :summed-stdev noise :separated? separated?})
      :policy policy
      :candidate (:observation/id candidate)
      :baseline (:observation/id baseline)})))

;; ── claims ───────────────────────────────────────────────────────────────

(defn claim
  "Seal a qualified result so it can be recorded and later re-checked.

  Refuses to seal an unqualified one. The point of the gate is that the
  unqualified case has no artifact at all — an artifact marked
  `:qualified? false` gets copied into a slide deck within the week."
  [verdict candidate baseline]
  (when-not (:qualified? verdict)
    (throw (ex-info "refusing to seal an unqualified result"
                    {:phase :perfgate/claim :reasons (:reasons verdict)})))
  (let [body {:format claim-format
              :claim/plan-id (:observation/plan-id candidate)
              :claim/metric (:observation/metric candidate)
              :claim/unit (:observation/unit candidate)
              :claim/improvement (:improvement verdict)
              :claim/machine-id (:observation/machine-id candidate)
              :claim/machine-fingerprint (:observation/machine-fingerprint candidate)
              :claim/policy-id (get-in verdict [:policy :policy/id])
              :claim/candidate candidate
              :claim/baseline baseline}]
    (assoc body :claim/fingerprint (m/fingerprint body))))

(defn verify-claim
  "Recompute the claim's fingerprint and its verdict from the arms it carries.

  A claim that no longer qualifies under its own policy — because someone
  edited a sample, or the policy tightened — is not a claim."
  [c]
  (let [body (dissoc c :claim/fingerprint)]
    (when-not (= (:claim/fingerprint c) (m/fingerprint body))
      (throw (ex-info "claim fingerprint does not match its contents"
                      {:phase :perfgate/verify :claim/plan-id (:claim/plan-id c)})))
    (let [verdict (qualify (:claim/candidate c) (:claim/baseline c)
                           (assoc default-policy :policy/id (:claim/policy-id c)))]
      (when-not (:qualified? verdict)
        (throw (ex-info "claim no longer qualifies"
                        {:phase :perfgate/verify :reasons (:reasons verdict)})))
      c)))

(defn stale-on?
  "Does this claim still describe the machine in front of you?

  This is the question that actually retires an optimization. A claim proved
  on one cache geometry says nothing about another, and the honest answer to
  \"is this still worth having\" is usually \"nobody has measured it since the
  hardware changed\"."
  [c machine]
  (not= (:claim/machine-fingerprint c) (m/fingerprint machine)))

(defn applicable
  "Split claims into those still valid for `machine` and those gone stale,
  with the reason attached. Useful as a startup check: a system that carries
  its own list of retired optimizations does not accumulate fossils."
  [claims machine]
  (let [fp (m/fingerprint machine)]
    {:machine-id (:machine/id machine)
     :machine-fingerprint fp
     :applicable (filterv #(= fp (:claim/machine-fingerprint %)) claims)
     :stale (mapv (fn [c] {:claim/plan-id (:claim/plan-id c)
                           :measured-on (:claim/machine-id c)
                           :reason :machine-changed})
                  (remove #(= fp (:claim/machine-fingerprint %)) claims))}))

(defn explain
  "The verdict as lines a human can read in a CI log."
  [verdict]
  (into [(str (if (:qualified? verdict) "QUALIFIED" "REFUSED") ": "
              (:candidate verdict) " against " (:baseline verdict)
              (when-let [i (:improvement verdict)]
                (str " (" (Math/round (* 100.0 i)) "% improvement)")))]
        (mapv (fn [r] (str "  - " (name (:reason r))
                           (when (:note r) (str ": " (:note r)))))
              (:reasons verdict))))

;; ── before the experiment ────────────────────────────────────────────────
;;
;; Everything above judges a result after it exists. That is one turn too
;; late for a common and expensive mistake: running an experiment whose
;; effect is smaller than its own noise, then reading the sign off the means
;; anyway. Three consecutive runs of one such experiment produced +3%, +31%
;; and -22% before the gate was consulted at all.
;;
;; The arithmetic is the same in both directions. `qualify` requires the gap
;; to exceed the summed standard deviations; run that backwards and it gives
;; the smallest improvement this gate could ever pass.

(defn minimum-detectable-improvement
  "The smallest improvement these two arms' noise would let `qualify` pass.

  Derived from the separation rule rather than added on top of it: qualifying
  needs `mean_b - mean_c > sd_b + sd_c`, so the improvement must exceed
  `(sd_b + sd_c) / mean_b` — and never less than the policy's floor."
  ([baseline candidate] (minimum-detectable-improvement baseline candidate default-policy))
  ([baseline candidate policy]
   (let [policy (merge default-policy policy)
         bs (:observation/summary baseline)
         cs (:observation/summary candidate)
         noise-floor (if (pos? (:mean bs))
                       (/ (+ (:stdev bs) (:stdev cs)) (:mean bs))
                       ##Inf)]
     (max (:policy/min-improvement policy) noise-floor))))

(defn detectable?
  "Could an improvement of `expected` survive this gate, given this noise?

  Call it with pilot samples before committing to a long run. An experiment
  that answers `false` here cannot produce a qualifying result no matter how
  many times it is run — running it anyway produces a number with a sign, and
  the sign is the noise's."
  ([baseline candidate expected] (detectable? baseline candidate expected default-policy))
  ([baseline candidate expected policy]
   (let [floor (minimum-detectable-improvement baseline candidate policy)]
     {:expected-improvement expected
      :minimum-detectable floor
      :detectable? (> expected floor)
      :shortfall (when (<= expected floor) (- floor expected))
      :remedy (when (<= expected floor)
                (str "reduce noise or raise the effect: at this spread the gate cannot "
                     "pass anything under " (Math/round (* 100.0 floor)) "%"))})))

(defn samples-needed
  "Roughly how many samples would bring the noise floor under `expected`.

  Standard error shrinks with the square root of the count, so the sample
  count scales with the square of how far short you are. Rough on purpose —
  it assumes the spread itself does not change with more sampling, which is
  false whenever the noise is a scheduler moving threads between core types
  rather than ordinary jitter. Use it to decide between 'take more samples'
  and 'this harness cannot answer the question'."
  ([baseline candidate expected] (samples-needed baseline candidate expected default-policy))
  ([baseline candidate expected policy]
   (let [floor (minimum-detectable-improvement baseline candidate policy)
         n (:n (:observation/summary candidate))]
     (if (> expected floor)
       {:needed n :note "already detectable at the current sample count"}
       {:needed (long (Math/ceil (* n (Math/pow (/ floor (max expected 1e-9)) 2))))
        :note "assumes the spread is sampling jitter; it is not, if the machine is migrating threads"}))))
