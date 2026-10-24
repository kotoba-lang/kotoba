(ns kotoba.activity
  "Automatic work-time capture — pure data contracts.

  A kotoba-lang capability library for the class of product the fleet had
  no answer to: automatic timesheet capture (the Timely / Memtime / Rize /
  Clockk / DeskTime / RescueTime category). The pipeline is

      observations -> sessions -> attribution -> timesheet entries

  where each arrow is a pure function of its input. No network, no I/O, no
  clock — every function that needs the current time takes it from its
  caller, so a run is reproducible from its observations alone.

  `kotoba.labor` is the sibling that PRICES work time (contracts, wages,
  payroll). This library only ever says how much time was OBSERVED and
  what it was for; `->timesheet-entries` emits `:ts/*` maps shaped exactly
  like `kotoba.labor/timesheet` so the two compose without either
  depending on the other.

  Three invariants hold throughout and are what make the output usable as
  a billing basis rather than a guess:

    1. Time is never extrapolated. A session ends at its last observation,
       not at the next one's start and not at 'now'. Capture therefore
       undercounts by at most one sample interval per session, which is
       the safe direction.
    2. Unattributed time stays unattributed. Nothing in here spreads
       leftover minutes across projects to make a day add up.
    3. Rounding only ever goes down or to nearest. There is deliberately
       no :ceil — rounding up bills time nobody observed.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Observation — one sample of what the worker was doing at one instant
;; ---------------------------------------------------------------------------

(def sources
  "Where a sample came from. :app and :window are polled from the desktop,
  :calendar and :vcs are derived from records the worker already produces,
  :manual is a human-entered span."
  #{:app :window :calendar :vcs :manual})

(defn observation
  "Construct one activity observation. `at` is epoch milliseconds, `source`
  one of `sources`, `subject` the coarse thing being worked in (an app
  name, a calendar, a repository). `:detail` is the fine-grained label —
  window title, event summary, branch — and is the privacy-sensitive part;
  see `redact`. `:idle?` marks a sample taken while the worker was away.

  Returns nil for an unknown source, mirroring `kotoba.labor/contract`."
  [at source subject & {:keys [detail idle?]}]
  (when (contains? sources source)
    {:obs/at      at
     :obs/source  source
     :obs/subject subject
     :obs/detail  detail
     :obs/idle?   (boolean idle?)}))

(defn valid-observation?
  "An observation is usable if it has a numeric instant, a known source and
  a non-blank subject."
  [m]
  (boolean
   (and (map? m)
        (number? (:obs/at m))
        (contains? sources (:obs/source m))
        (string? (:obs/subject m))
        (not (str/blank? (:obs/subject m))))))

(defn redact
  "Strip `:obs/detail` from observations. Window titles and document names
  are the part of a capture stream that is nobody else's business; subject
  and timing are enough to segment and to attribute by rule. Anything
  leaving the worker's own device should go through here first."
  [observations]
  (mapv #(assoc % :obs/detail nil) observations))

;; ---------------------------------------------------------------------------
;; Segmentation — samples to sessions
;; ---------------------------------------------------------------------------

(def default-segmentation
  "gap-ms: a silence longer than this closes the session (5 min).
   min-ms: sessions shorter than this are dropped as noise (1 min)."
  {:gap-ms 300000 :min-ms 60000})

(defn- session-key [{:keys [:obs/source :obs/subject :obs/detail]}]
  [source subject detail])

(defn- ->session [samples]
  (let [f (first samples)
        l (last samples)]
    {:session/start       (:obs/at f)
     :session/end         (:obs/at l)
     :session/duration-ms (- (:obs/at l) (:obs/at f))
     :session/source      (:obs/source f)
     :session/subject     (:obs/subject f)
     :session/detail      (:obs/detail f)
     :session/samples     (count samples)}))

(defn segment
  "Group observations into sessions. Samples join the running session when
  they carry the same [source subject detail] key AND follow the previous
  sample by no more than `:gap-ms`; anything else starts a new one. Idle
  and invalid samples are discarded first — an idle stretch therefore
  shows up as a gap, which is what closes the session around it.

  A session's duration is `end - start`, i.e. the span actually observed.
  The dwell after the final sample is NOT extrapolated, so a session
  polled every 60s runs about one interval short of wall clock. That
  understates the day on purpose; the alternative inflates every session
  by however long the poller happened to sleep.

  Sessions are returned in start order, shortest ones dropped per
  `:min-ms`. Pass `{:min-ms 0}` to keep them all."
  ([observations] (segment observations default-segmentation))
  ([observations opts]
   (let [{:keys [gap-ms min-ms]} (merge default-segmentation opts)
         usable (->> observations
                     (filter valid-observation?)
                     (remove :obs/idle?)
                     (sort-by :obs/at))]
     (->> usable
          (reduce
           (fn [{:keys [done open]} obs]
             (if (and (seq open)
                      (= (session-key (peek open)) (session-key obs))
                      (<= (- (:obs/at obs) (:obs/at (peek open))) gap-ms))
               {:done done :open (conj open obs)}
               {:done (cond-> done (seq open) (conj open)) :open [obs]}))
           {:done [] :open []})
          ((fn [{:keys [done open]}] (cond-> done (seq open) (conj open))))
          (map ->session)
          (filter #(>= (:session/duration-ms %) min-ms))
          (sort-by :session/start)
          vec))))

(defn observed-ms
  "Total observed milliseconds across sessions. Sessions never overlap
  within one capture stream, so this is a plain sum."
  [sessions]
  (reduce + 0 (map :session/duration-ms sessions)))

;; ---------------------------------------------------------------------------
;; Attribution — sessions to projects, by declared rule
;; ---------------------------------------------------------------------------

(defn rule
  "Construct an attribution rule. Every clause supplied must match for the
  rule to fire (AND); a rule with no clause matches nothing, so an
  accidental catch-all cannot be written by omission.

  Clauses: `:source`, `:subject-is`, `:subject-contains`,
  `:detail-contains`. `:weight` (0.0-1.0, default 0.8) becomes the
  attribution's confidence when this rule wins."
  [id project & {:keys [source subject-is subject-contains detail-contains weight]}]
  {:rule/id               id
   :rule/project          project
   :rule/source           source
   :rule/subject-is       subject-is
   :rule/subject-contains subject-contains
   :rule/detail-contains  detail-contains
   :rule/weight           (or weight 0.8)})

(defn- clauses-of [r]
  (cond-> []
    (:rule/source r)           (conj [:source (:rule/source r)])
    (:rule/subject-is r)       (conj [:subject-is (:rule/subject-is r)])
    (:rule/subject-contains r) (conj [:subject-contains (:rule/subject-contains r)])
    (:rule/detail-contains r)  (conj [:detail-contains (:rule/detail-contains r)])))

(defn- clause-matches? [session [kind v]]
  (case kind
    :source           (= v (:session/source session))
    :subject-is       (= v (:session/subject session))
    :subject-contains (str/includes? (or (:session/subject session) "") v)
    :detail-contains  (str/includes? (or (:session/detail session) "") v)
    false))

(defn matches?
  "Does `r` fire for `session`? False for a rule with no clauses."
  [session r]
  (let [cs (clauses-of r)]
    (and (seq cs) (every? #(clause-matches? session %) cs))))

(defn attribute
  "Attribute one session using ordered `rules`. The highest-weight match
  wins. If the top weight is shared by rules naming different projects the
  session is left unattributed and flagged `:attribution/ambiguous? true`
  rather than resolved by rule order — a tie is a real question about the
  worker's day, and answering it by list position would hide that.

  A session matched by nothing is returned with project nil and confidence
  0.0. That is a first-class outcome: see `coverage`."
  [session rules]
  (let [hits (filterv #(matches? session %) rules)
        top  (when (seq hits) (apply max (map :rule/weight hits)))
        best (filterv #(= top (:rule/weight %)) hits)
        projects (into #{} (map :rule/project) best)
        ambiguous? (> (count projects) 1)]
    {:attribution/project    (when (and (seq best) (not ambiguous?))
                               (:rule/project (first best)))
     :attribution/confidence (if (or (empty? best) ambiguous?) 0.0 top)
     :attribution/evidence   (mapv :rule/id best)
     :attribution/ambiguous? ambiguous?}))

(defn attribute-all
  "Attribute every session, returning `[{:session ... :attribution ...}]`."
  [sessions rules]
  (mapv (fn [s] {:session s :attribution (attribute s rules)}) sessions))

;; ---------------------------------------------------------------------------
;; Admission — the boundary an LLM proposal has to cross
;; ---------------------------------------------------------------------------

(def default-confidence-floor 0.6)

(defn admit
  "Check an externally produced attribution proposal (typically an LLM's)
  against what was actually observed. The model is allowed to LABEL time;
  it is never allowed to create, lengthen or reassign it.

  `proposal` is `{:session/start n :session/end n :project p :confidence n}`;
  `sessions` is the observed set and `projects` the declared project set.
  Returns `{:admit/ok? bool :admit/errors [{:rule kw :detail str}]}`.

  Rejections:
    :no-session         — cites a span that was not observed
    :unknown-project    — names a project outside the declared set. A nil
                          project is not a rejection: it asserts nothing,
                          and 'observed but nobody knows what for' is the
                          honest answer the second invariant protects.
    :duration-mismatch  — restates a duration other than the observed one
    :bad-confidence     — confidence outside 0.0-1.0
    :low-confidence     — below `:confidence-floor` (an admission failure,
                          not a hold: the caller decides what to do with a
                          proposal the model itself is unsure of)"
  ([proposal sessions projects] (admit proposal sessions projects {}))
  ([proposal sessions projects opts]
   (let [floor (:confidence-floor opts default-confidence-floor)
         match (first (filter #(and (= (:session/start %) (:session/start proposal))
                                    (= (:session/end %) (:session/end proposal)))
                              sessions))
         conf  (:confidence proposal)
         errors
         (cond-> []
           (nil? match)
           (conj {:rule :no-session
                  :detail (str "observed sessions contain no span "
                               (:session/start proposal) "–" (:session/end proposal))})

           ;; A nil project asserts nothing and is a first-class outcome
           ;; (invariant 2): the span was observed, nobody knows what for.
           ;; Only a NAMED project has to be one that exists.
           (and (some? (:project proposal))
                (not (contains? (set projects) (:project proposal))))
           (conj {:rule :unknown-project
                  :detail (str "undeclared project: " (pr-str (:project proposal)))})

           (and match (:duration-ms proposal)
                (not= (:duration-ms proposal) (:session/duration-ms match)))
           (conj {:rule :duration-mismatch
                  :detail (str "proposed " (:duration-ms proposal) "ms ≠ observed "
                               (:session/duration-ms match) "ms")})

           (not (and (number? conf) (<= 0.0 conf 1.0)))
           (conj {:rule :bad-confidence :detail (str "confidence " (pr-str conf))})

           (and (number? conf) (<= 0.0 conf 1.0) (< conf floor))
           (conj {:rule :low-confidence
                  :detail (str "confidence " conf " < floor " floor)}))]
     {:admit/ok? (empty? errors) :admit/errors errors})))

;; ---------------------------------------------------------------------------
;; Coverage — what the day did and did not account for
;; ---------------------------------------------------------------------------

(defn coverage
  "Split observed time into attributed and unattributed. Reported rather
  than reconciled: a day that is 60% attributed should read as 60%, not as
  a full day with the remainder quietly folded into the biggest project."
  [attributed]
  (let [total (reduce + 0 (map (comp :session/duration-ms :session) attributed))
        att   (reduce + 0 (map (comp :session/duration-ms :session)
                               (filter (comp :attribution/project :attribution) attributed)))]
    {:coverage/observed-ms     total
     :coverage/attributed-ms   att
     :coverage/unattributed-ms (- total att)
     :coverage/ratio           (if (zero? total) 0.0 (double (/ att total)))}))

;; ---------------------------------------------------------------------------
;; Timesheet emission
;; ---------------------------------------------------------------------------

(def ^:private ms-per-hour 3600000)

(defn- round-ms [ms increment-ms mode]
  (if (or (nil? increment-ms) (zero? increment-ms))
    ms
    (let [q (/ (double ms) increment-ms)]
      (* increment-ms
         (long (case mode
                 :nearest (Math/round q)
                 (Math/floor q)))))))

(def default-emission
  "increment-ms: billing granularity (15 min).
   rounding: :floor (default) or :nearest. There is no :ceil."
  {:increment-ms 900000 :rounding :floor})

(defn ->timesheet-entries
  "Roll attributed sessions into per-project timesheet entries for one
  worker and one date. `date-of` maps a session start (epoch ms) to the
  date string the entry should carry — supplied by the caller because the
  right answer depends on a timezone this library refuses to guess.

  Unattributed sessions are dropped, not bundled under a catch-all: use
  `coverage` to see what was left out. Entries whose rounded time is zero
  are dropped too.

  Emits `{:ts/worker :ts/date :ts/hours :ts/project :ts/observed-ms}` —
  the first three keys are exactly `kotoba.labor/timesheet`'s shape, so
  `kotoba.labor/wages-for` prices these unchanged.

  With the default `:floor` rounding, total emitted hours are guaranteed
  ≤ observed hours."
  ([worker date-of attributed] (->timesheet-entries worker date-of attributed default-emission))
  ([worker date-of attributed opts]
   (let [{:keys [increment-ms rounding]} (merge default-emission opts)]
     (->> attributed
          (filter (comp :attribution/project :attribution))
          (group-by (fn [{:keys [session attribution]}]
                      [(date-of (:session/start session))
                       (:attribution/project attribution)]))
          (map (fn [[[date project] items]]
                 (let [raw     (reduce + 0 (map (comp :session/duration-ms :session) items))
                       rounded (round-ms raw increment-ms rounding)]
                   {:ts/worker      worker
                    :ts/date        date
                    :ts/project     project
                    :ts/hours       (/ (double rounded) ms-per-hour)
                    :ts/observed-ms raw})))
          (remove #(zero? (:ts/hours %)))
          (sort-by (juxt :ts/date :ts/project))
          vec))))

(defn total-hours
  "Sum `:ts/hours` across entries. Same shape as `kotoba.labor/total-hours`
  and included so a caller can assert the emission invariant without
  pulling in the pricing library."
  [entries]
  (reduce + 0 (map :ts/hours entries)))
