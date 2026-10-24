(ns uptime.core
  "Observations of a service -> a statement about its availability. Pure.

  Written because the alternative is a status page that asserts. A page saying
  *all systems operational* with nothing behind it is worse than no page: it is
  read as a measurement, it is quoted back in a contract dispute, and it is
  right by construction — it says the same thing during an outage.

  So the whole library is organised around one distinction that assertion-based
  status pages do not have:

  ## Unobserved is not up

  A window nobody probed produces `:unobserved`, never 100%. This is the same
  rule as `authn.usage`'s unmeasured month and it is the same failure: silence
  and success are indistinguishable on the output, and they mean opposite
  things. A prober that dies quietly then reads as perfect availability, which
  is exactly backwards — the moment you can least trust the number is the
  moment it looks best.

  ## A prober that could not run is not an outage either

  Three outcomes, not two. `:up` and `:down` are claims about the service;
  `:inconclusive` is a claim about the probe — DNS failed on the prober's own
  network, the laptop was asleep, the token expired. Counting those as downtime
  understates the service and, worse, teaches everyone to ignore the number.
  Counting them as uptime is the lie in the other direction. They are excluded
  from the ratio and reported separately, so the reader can see how much of the
  window was actually observed.

  ## Coverage is part of the statement

  `:availability/coverage` is the fraction of the window that produced a
  conclusive observation. An availability of 100% over 4% coverage is not a
  good month; it is an unmonitored one, and the statement says so rather than
  leaving the reader to notice."
  (:require [kotoba.lang.text :as str]))

(def outcomes
  "What one probe can conclude. `:inconclusive` is about the PROBE, not the
  service — see the namespace docstring."
  #{:up :down :inconclusive})

(defn observation
  "One probe result. `at` is epoch milliseconds; `target` names what was probed.

  `:detail` is free text and is carried through to the statement's incident
  list, because an outage line with no reason attached is one nobody can act on."
  [{:keys [target at outcome status latency-ms detail]}]
  (cond-> {:observation/target target
           :observation/at at
           :observation/outcome (if (contains? outcomes outcome) outcome :inconclusive)}
    status (assoc :observation/status status)
    latency-ms (assoc :observation/latency-ms latency-ms)
    detail (assoc :observation/detail detail)))

(defn problems
  "What is wrong with an observation, as data. Empty means usable.

  An observation missing its clock is refused rather than defaulted to `now`:
  a defaulted timestamp lands the reading in whichever window happened to be
  open when it was parsed, which is a quiet way to move an outage into the
  previous month."
  [{:observation/keys [target at outcome]}]
  (cond-> []
    (not (and (string? target) (seq target)))
    (conj {:uptime.problem/code :no-target})

    (not (and (number? at) (pos? at)))
    (conj {:uptime.problem/code :no-timestamp})

    (not (contains? outcomes outcome))
    (conj {:uptime.problem/code :unknown-outcome :outcome outcome})))

(defn- within? [{:observation/keys [at]} from to]
  (and (>= at from) (< at to)))

;; ── the statement ───────────────────────────────────────────────────────────

(defn statement
  "Observations over `[from, to)` -> what may honestly be said about a target.

    {:availability/target      the target
     :availability/window      [from to]
     :availability/observed    conclusive probes in the window
     :availability/inconclusive probes that could not conclude
     :availability/up          conclusive probes that found it up
     :availability/ratio       up / conclusive, or nil when nothing concluded
     :availability/coverage    conclusive / expected, or nil when expected is unknown
     :availability/status      :available | :degraded | :unavailable | :unobserved
     :availability/incidents   the down runs, each with its first and last probe}

  `expected` is how many probes the schedule should have produced in this
  window. Supplying it is what turns 'nothing went wrong' into 'we were
  watching' — without it, coverage is nil and the statement says so instead of
  implying full observation.

  `:unobserved` beats every other status. A window with no conclusive probe has
  no availability, not 100%."
  ([target observations from to] (statement target observations from to nil))
  ([target observations from to {:keys [expected degraded-below]
                                 :or {degraded-below 1.0}}]
   (let [in-window (->> observations
                        (filter #(= target (:observation/target %)))
                        (filter #(within? % from to))
                        (sort-by :observation/at))
         conclusive (remove #(= :inconclusive (:observation/outcome %)) in-window)
         inconclusive (filter #(= :inconclusive (:observation/outcome %)) in-window)
         up (filter #(= :up (:observation/outcome %)) conclusive)
         n (count conclusive)
         ratio (when (pos? n) (/ (double (count up)) n))
         coverage (when (and expected (pos? expected))
                    (min 1.0 (/ (double n) expected)))
         ;; Down runs, not down probes: three consecutive failures at one-minute
         ;; spacing is one incident a reader can act on, and three lines is not.
         incidents (->> conclusive
                        (partition-by :observation/outcome)
                        (filter #(= :down (:observation/outcome (first %))))
                        (mapv (fn [run]
                                {:incident/from (:observation/at (first run))
                                 :incident/to (:observation/at (last run))
                                 :incident/probes (count run)
                                 :incident/detail (some :observation/detail run)})))]
     {:availability/target target
      :availability/window [from to]
      :availability/observed n
      :availability/inconclusive (count inconclusive)
      :availability/up (count up)
      :availability/ratio ratio
      :availability/coverage coverage
      :availability/incidents incidents
      :availability/status (cond
                             (zero? n) :unobserved
                             (zero? (count up)) :unavailable
                             (< ratio degraded-below) :degraded
                             :else :available)})))

;; ── promising something ─────────────────────────────────────────────────────

(defn slo-verdict
  "Does a statement meet a target, e.g. 0.999?

  Three answers and not two. `:cannot-say` is returned when coverage is below
  `min-coverage` (default 0.9) or nothing was observed — because a ratio
  computed from four probes in a month is not evidence about that month, and
  reporting it as `:met` is how an SLO becomes decoration.

  The failure this prevents is specific: a prober quietly stops, the handful of
  probes that did land all succeeded, and the month reports as met. Every
  incentive points at not noticing."
  ([stmt target] (slo-verdict stmt target nil))
  ([{:availability/keys [ratio coverage status]} target {:keys [min-coverage]
                                                         :or {min-coverage 0.9}}]
   (cond
     (= :unobserved status)
     {:slo/verdict :cannot-say :slo/reason :unobserved}

     (and coverage (< coverage min-coverage))
     {:slo/verdict :cannot-say :slo/reason :insufficient-coverage
      :slo/coverage coverage :slo/required min-coverage}

     (nil? coverage)
     ;; No expectation was supplied, so there is no way to know whether the
     ;; probes present are all the probes there should have been.
     {:slo/verdict :cannot-say :slo/reason :coverage-unknown}

     (>= ratio target) {:slo/verdict :met :slo/ratio ratio :slo/target target}
     :else {:slo/verdict :missed :slo/ratio ratio :slo/target target})))

;; ── saying it in words ──────────────────────────────────────────────────────

(defn- pct [x] (when x (str (-> (* 100 x) (* 1000) Math/round (/ 1000.0)) "%")))

(defn describe
  "One sentence a person can read, generated from the same values the verdict
  uses — so a published statement cannot drift from what was measured."
  [{:availability/keys [target observed inconclusive ratio coverage status incidents] :as stmt}]
  (case status
    :unobserved
    (str target ": not observed in this window — no availability is claimed"
         (when (pos? inconclusive)
           (str " (" inconclusive " probe(s) could not conclude)")))

    (str target ": " (pct ratio) " over " observed " probe(s)"
         (when coverage (str ", " (pct coverage) " of the expected schedule"))
         (when (pos? inconclusive) (str ", " inconclusive " inconclusive"))
         (when (seq incidents) (str ", " (count incidents) " incident(s)"))
         (case status
           :available ""
           :degraded " — degraded"
           :unavailable " — unavailable"
           ""))))
