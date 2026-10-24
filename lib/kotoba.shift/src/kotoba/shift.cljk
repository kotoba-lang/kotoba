(ns kotoba.shift
  "Attendance: punches, shifts, rosters, coverage — pure data contracts.

  A kotoba-lang capability library for the 打刻 / rostering half of
  workforce management (the UKG / Dayforce / ADP / Deputy / QuickBooks
  Time category), covering what those products call time & attendance:
  turning clock events into worked spans, planned shifts into a roster,
  and demand into coverage.

  It is the sibling of `kotoba.activity`, and the difference is what the
  data means rather than how it is shaped. Activity capture SAMPLES —
  it asks 'what was in front of you just now' many times. Attendance
  RECORDS — a punch is a deliberate assertion that a shift began. So
  activity segments a stream and undercounts by a sample interval; this
  pairs discrete events and refuses to complete an unpaired one.

  The statutory side is not here. `kotoba.worklaw` holds the
  jurisdiction rules, because they apply to worked time from any source,
  not just from punches.

  One invariant runs through all of it, and it is the same one
  `kotoba.activity` holds for a different reason:

    An unpaired punch is never completed. A missing clock-out does not
    become 'end of shift', 'end of day' or 'now'. It becomes an anomaly
    with no worked time attached, because the alternative is inventing
    the most consequential number on the timesheet.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

(def ^:private ms-per-hour 3600000)

;; ---------------------------------------------------------------------------
;; Punches
;; ---------------------------------------------------------------------------

(def punch-kinds #{:in :out :break-start :break-end})

(defn punch
  "Construct a clock event. Returns nil for an unknown kind."
  [person at kind & {:keys [source note]}]
  (when (contains? punch-kinds kind)
    {:punch/person person
     :punch/at     at
     :punch/kind   kind
     :punch/source (or source :terminal)
     :punch/note   note}))

(defn- worked-span [in out breaks]
  (let [span (- (:punch/at out) (:punch/at in))
        break-ms (reduce + 0 (map (fn [[bs be]] (- (:punch/at be) (:punch/at bs))) breaks))]
    {:worked/person   (:punch/person in)
     :worked/start    (:punch/at in)
     :worked/end      (:punch/at out)
     :worked/gross-ms span
     :worked/break-ms break-ms
     :worked/ms       (- span break-ms)}))

(defn pair-punches
  "Fold one person's punches into worked spans and anomalies.

  Returns `{:worked [...] :anomalies [{:anomaly/rule :anomaly/at ...}]}`.

  Anomalies, none of which produce worked time:
    :double-in       — a second :in while already clocked in
    :out-without-in  — an :out with no open :in
    :missing-out     — the day ends with an :in still open
    :break-outside   — a break punch while clocked out
    :double-break    — a :break-start while already on break
    :unclosed-break  — a :break-start with no :break-end before the :out

  Punches at the same instant are ordered :out, :break-end, :break-start,
  :in — so a shift that ends exactly as the next begins pairs correctly
  instead of reading as a double clock-in. The consequence, which is a
  real one: an :in and an :out stamped at the SAME instant read as
  `:out-without-in` followed by `:missing-out`, not as a zero-length
  shift. Both readings say the terminal recorded something impossible;
  this one says it without having to invent an ordering the data does
  not contain.

  A shift with an unclosed break is NOT silently credited the whole span:
  the break is dropped from the pairing and the span is reported as an
  anomaly instead, since 'how long was the break' is exactly the number
  nobody can reconstruct after the fact."
  [punches]
  (let [sorted (sort-by (juxt :punch/at #(case (:punch/kind %) :out 0 :break-end 1 :break-start 2 :in 3))
                        (filter #(contains? punch-kinds (:punch/kind %)) punches))]
    (-> (reduce
         (fn [{:keys [open breaks pending-break] :as acc} p]
           (case (:punch/kind p)
             :in
             (if open
               (update acc :anomalies conj {:anomaly/rule :double-in :anomaly/at (:punch/at p)})
               (assoc acc :open p :breaks [] :pending-break nil))

             :out
             (cond
               (nil? open)
               (update acc :anomalies conj {:anomaly/rule :out-without-in :anomaly/at (:punch/at p)})

               pending-break
               (-> acc
                   (update :anomalies conj {:anomaly/rule :unclosed-break
                                            :anomaly/at (:punch/at pending-break)
                                            :anomaly/start (:punch/at open)})
                   (assoc :open nil :breaks [] :pending-break nil))

               :else
               (-> acc
                   (update :worked conj (worked-span open p breaks))
                   (assoc :open nil :breaks [] :pending-break nil)))

             :break-start
             (cond
               (nil? open)
               (update acc :anomalies conj {:anomaly/rule :break-outside :anomaly/at (:punch/at p)})
               pending-break
               (update acc :anomalies conj {:anomaly/rule :double-break :anomaly/at (:punch/at p)})
               :else (assoc acc :pending-break p))

             :break-end
             (cond
               (nil? open)
               (update acc :anomalies conj {:anomaly/rule :break-outside :anomaly/at (:punch/at p)})
               (nil? pending-break)
               (update acc :anomalies conj {:anomaly/rule :break-outside :anomaly/at (:punch/at p)})
               :else (-> acc
                         (update :breaks conj [pending-break p])
                         (assoc :pending-break nil)))))
         {:worked [] :anomalies [] :open nil :breaks [] :pending-break nil}
         sorted)
        ((fn [{:keys [open] :as acc}]
           (cond-> acc
             open (update :anomalies conj {:anomaly/rule :missing-out
                                           :anomaly/at (:punch/at open)}))))
        (select-keys [:worked :anomalies]))))

(defn worked-ms
  "Total worked milliseconds across spans, breaks already deducted."
  [worked]
  (reduce + 0 (map :worked/ms worked)))

(defn worked-hours [worked]
  (/ (double (worked-ms worked)) ms-per-hour))

(defn ->timesheet-entries
  "Roll worked spans into `:ts/*` entries — the shape `kotoba.labor`,
  `kotoba.psa` and `kotoba.activity` all read. `date-of` maps an epoch
  instant to a date string; the caller owns the timezone, same as in
  `kotoba.activity`.

  Attendance is recorded to the exact minute, so unlike activity capture
  there is no rounding here at all. A payroll increment, if one is
  wanted, is a decision for the layer that applies it."
  [worked date-of]
  (->> worked
       (group-by #(date-of (:worked/start %)))
       (map (fn [[date spans]]
              {:ts/worker (:worked/person (first spans))
               :ts/date   date
               :ts/hours  (/ (double (reduce + 0 (map :worked/ms spans))) ms-per-hour)}))
       (sort-by :ts/date)
       vec))

;; ---------------------------------------------------------------------------
;; Shifts and rosters
;; ---------------------------------------------------------------------------

(defn shift
  "A planned shift: `person` covering `role` over `[start end]`."
  [id person role start end]
  {:shift/id id :shift/person person :shift/role role
   :shift/start start :shift/end end})

(defn- overlap-ms [[a b] [c d]] (max 0 (- (min b d) (max a c))))

(defn demand
  "A staffing requirement: `headcount` people in `role` over `[from to]`."
  [role from to headcount]
  {:demand/role role :demand/from from :demand/to to :demand/headcount headcount})

(defn coverage
  "Compare a roster against one demand window.

  Reports the gap; never closes it. A rostering tool that quietly
  reassigns someone to fill a hole is how a person ends up working a
  shift they never agreed to, so this returns the shortfall and stops."
  [roster {:keys [:demand/role :demand/from :demand/to :demand/headcount] :as d}]
  (let [covering (filter #(and (= role (:shift/role %))
                               (pos? (overlap-ms [(:shift/start %) (:shift/end %)] [from to])))
                         roster)
        ;; A shift only counts as covering the window if it spans all of
        ;; it. Partial cover is listed separately rather than counted as
        ;; a fraction of a person, which no shift can be staffed with.
        full (filter #(and (<= (:shift/start %) from) (>= (:shift/end %) to)) covering)
        n (count full)]
    {:coverage/demand   d
     :coverage/staffed  n
     :coverage/gap      (max 0 (- headcount n))
     :coverage/surplus  (max 0 (- n headcount))
     :coverage/partial  (mapv :shift/id (remove (set full) covering))}))

(defn variance
  "Planned shift against what was actually worked. Matches by person and
  overlap; a shift nobody worked is `:absent`, worked time under no shift
  is `:unrostered`."
  [roster worked]
  (let [{:keys [rows matched]}
        (reduce
         (fn [acc s]
           (let [w (first (filter #(and (= (:shift/person s) (:worked/person %))
                                        (not (contains? (:matched acc) %))
                                        (pos? (overlap-ms [(:shift/start s) (:shift/end s)]
                                                          [(:worked/start %) (:worked/end %)])))
                                  worked))]
             (if w
               (-> acc
                   (update :matched conj w)
                   (update :rows conj {:variance/shift          (:shift/id s)
                                       :variance/person         (:shift/person s)
                                       :variance/kind           :worked
                                       :variance/start-delta-ms (- (:worked/start w) (:shift/start s))
                                       :variance/end-delta-ms   (- (:worked/end w) (:shift/end s))
                                       :variance/worked-ms      (:worked/ms w)}))
               (update acc :rows conj {:variance/shift  (:shift/id s)
                                       :variance/person (:shift/person s)
                                       :variance/kind   :absent}))))
         {:rows [] :matched #{}}
         roster)]
    (into rows
          (for [w worked :when (not (contains? matched w))]
            {:variance/person    (:worked/person w)
             :variance/kind      :unrostered
             :variance/worked-ms (:worked/ms w)
             :variance/start     (:worked/start w)}))))

(defn describe-anomalies
  "One-line human summary of pairing anomalies; empty string when there
  were none, so a caller never prints a reassuring all-clear."
  [{:keys [anomalies]}]
  (str/join "; "
            (for [[rule items] (sort-by key (group-by :anomaly/rule anomalies))]
              (str (count items) "× " (name rule)))))

;; ---------------------------------------------------------------------------
;; Availability
;;
;; Everything below turns on this. A roster generator that does not know
;; when someone is unavailable is a roster generator that will schedule
;; them anyway, so availability is a first-class declaration and the
;; absence of one is NOT treated as "available".
;; ---------------------------------------------------------------------------

(defn availability
  "`person` is available for `role` over `[from to]`. Declared, not
  inferred: nobody is available by default."
  [person role from to]
  {:avail/person person :avail/role role :avail/from from :avail/to to})

(defn available?
  "Is `person` declared available for the whole of `[from to]` in `role`,
  and not already rostered or on leave across it?"
  [availabilities roster leave person role [from to]]
  (boolean
   (and (some #(and (= person (:avail/person %))
                    (= role (:avail/role %))
                    (<= (:avail/from %) from)
                    (>= (:avail/to %) to))
              availabilities)
        (not-any? #(and (= person (:shift/person %))
                        (pos? (overlap-ms [(:shift/start %) (:shift/end %)] [from to])))
                  roster)
        (not-any? #(and (= person (:leave/person %))
                        (= :approved (:leave/status %))
                        (pos? (overlap-ms [(:leave/from %) (:leave/to %)] [from to])))
                  leave))))

;; ---------------------------------------------------------------------------
;; Leave and accrual
;; ---------------------------------------------------------------------------

(defn leave-request
  "A request for leave. Status starts `:requested`; nothing here approves
  it, because approving your own leave is not a thing a library does."
  [id person kind from to]
  {:leave/id id :leave/person person :leave/kind kind
   :leave/from from :leave/to to :leave/status :requested})

(defn accrual-policy
  "`hours` of `kind` leave accrue per `per-hours` worked, capped at
  `cap-hours`. `:carry-over` is how much may cross a policy year.

  Deliberately expressed as accrual PER HOURS WORKED rather than per
  calendar month: a part-timer accrues in proportion to what they
  actually worked, which is what most statutory schemes require and what
  a monthly grant quietly gets wrong."
  [kind hours per-hours & {:keys [cap-hours carry-over]}]
  {:accrual/kind kind :accrual/hours hours :accrual/per-hours per-hours
   :accrual/cap-hours cap-hours :accrual/carry-over carry-over})

(defn accrued
  "Leave accrued from `worked` under `policy`, minus leave already taken.

  `:balance/accrued` is capped by the policy; `:balance/forfeited` says
  how much the cap swallowed rather than letting it vanish silently — a
  worker who lost 12 hours to a cap should be able to see the 12 hours."
  [policy worked taken-hours]
  (let [wh (worked-hours worked)
        raw (* (:accrual/hours policy) (/ wh (:accrual/per-hours policy)))
        cap (:accrual/cap-hours policy)
        capped (if cap (min raw cap) raw)]
    {:balance/kind      (:accrual/kind policy)
     :balance/worked-hours wh
     :balance/accrued   capped
     :balance/forfeited (- raw capped)
     :balance/taken     taken-hours
     :balance/available (- capped taken-hours)}))

(defn leave-hours
  "Hours of approved leave in `[from to]` for one person, counted at
  `day-hours` per whole day of leave."
  [leave person [from to] day-hours]
  (reduce + 0.0
          (for [l leave
                :when (and (= person (:leave/person l))
                           (= :approved (:leave/status l)))]
            (* day-hours (/ (double (overlap-ms [(:leave/from l) (:leave/to l)] [from to]))
                            86400000)))))

;; ---------------------------------------------------------------------------
;; Shift swap
;; ---------------------------------------------------------------------------

(defn swap-proposal
  "`from-person` asks `to-person` to take `shift-id`. A proposal, and it
  stays one until both sides accept."
  [id shift-id from-person to-person]
  {:swap/id id :swap/shift shift-id
   :swap/from from-person :swap/to to-person
   :swap/accepted-by #{}})

(defn accept-swap [proposal person]
  (update proposal :swap/accepted-by conj person))

(defn swap-ready?
  "Both named parties have accepted. Neither side alone is enough: a
  swap one person can impose on another is not a swap, it is a
  reassignment with extra steps."
  [{:swap/keys [from to accepted-by]}]
  (boolean (and (contains? accepted-by from) (contains? accepted-by to))))

(defn apply-swap
  "Rewrite the roster so the swapped shift belongs to `:swap/to`.

  Returns `{:roster [...] :applied? bool :reason kw}`. Refuses, without
  changing anything, when the swap is not accepted by both, when the
  shift does not exist, or when the receiving person is not available for
  it — the availability check is the point, because a swap is exactly
  where a person quietly ends up working a shift that clashes with their
  leave."
  [roster availabilities leave proposal]
  (let [s (first (filter #(= (:swap/shift proposal) (:shift/id %)) roster))]
    (cond
      (not (swap-ready? proposal))
      {:roster roster :applied? false :reason :not-accepted-by-both}

      (nil? s)
      {:roster roster :applied? false :reason :no-such-shift}

      (not= (:swap/from proposal) (:shift/person s))
      {:roster roster :applied? false :reason :not-their-shift}

      (not (available? availabilities (remove #{s} roster) leave
                       (:swap/to proposal) (:shift/role s)
                       [(:shift/start s) (:shift/end s)]))
      {:roster roster :applied? false :reason :receiver-unavailable}

      :else
      {:roster (mapv #(if (= (:shift/id s) (:shift/id %))
                        (assoc % :shift/person (:swap/to proposal))
                        %)
                     roster)
       :applied? true})))

;; ---------------------------------------------------------------------------
;; Roster generation
;; ---------------------------------------------------------------------------

(defn propose-roster
  "Propose shifts to close a demand's coverage gap.

  Returns `{:proposed [...] :still-short n :candidates-considered n}`.

  This is the one place `coverage`'s 'report the gap, never close it'
  needs care, and the resolution is that a PROPOSAL is not a closure.
  Nothing here mutates a roster: it names people who have DECLARED
  availability for exactly this window and are not already rostered or
  on leave, and it stops when it runs out of them. A gap that cannot be
  filled from declared availability stays a gap — `:still-short` — rather
  than being filled by whoever is least likely to object.

  Candidates are taken in the order given. Deliberately not 'fairest' or
  'cheapest': ranking people for shift assignment is a policy decision
  with consequences for whose weekend gets taken, and it belongs to the
  operator who can be held to it, not to a default buried in a library."
  [roster availabilities leave demand-record candidates next-id]
  (let [{:demand/keys [role from to]} demand-record
        gap (:coverage/gap (coverage roster demand-record))
        pick (loop [cs candidates, acc [], r roster, n gap]
               (if (or (zero? n) (empty? cs))
                 acc
                 (let [p (first cs)]
                   (if (available? availabilities r leave p role [from to])
                     (let [s (shift (next-id (count acc)) p role from to)]
                       (recur (rest cs) (conj acc s) (conj r s) (dec n)))
                     (recur (rest cs) acc r n)))))]
    {:proposed (vec pick)
     :still-short (- gap (count pick))
     :candidates-considered (count candidates)}))
