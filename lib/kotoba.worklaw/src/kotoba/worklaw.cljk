(ns kotoba.worklaw
  "Statutory working-time limits, by jurisdiction — pure data contracts.

  A kotoba-lang capability library for the 各国労働法 half of workforce
  management. It answers one question: does this worked time break a
  statutory limit in this jurisdiction?

  NOT LEGAL ADVICE. This is a mechanism plus a cited rule set. It is
  deliberately incomplete, and its most important behaviour is what it
  does about that.

  ## The invariant: silence is never compliance

  Every other check here is ordinary arithmetic. This one is the reason
  the library exists:

      an unchecked jurisdiction NEVER returns 'no violations'

  `check` reports `:worklaw/coverage` as `:full`, `:partial` or `:none`,
  and `:worklaw/unevaluated` for rules whose window is longer than the
  period examined. A caller reading `:worklaw/violations` without
  reading those two is reading a number that may mean 'we looked and
  found nothing' or 'we did not look'. The two are different and this
  library refuses to let them share a representation.

  ## Jurisdictions are paths, and the path is legal hierarchy

  `[:jp]`, `[:us]`, `[:us :ca]`, `[:eu]`, `[:eu :fr]`, `[:eu :de]`.
  Rules attach at a level and a worker is checked against every level
  for which rules exist, with the rest listed in `:worklaw/unchecked`.

  The path is the hierarchy of instruments, not geography. A French
  worker is `[:eu :fr]` — the Working Time Directive is the floor and
  the Code du travail layers on top — so `[:fr]` alone resolves to
  coverage `:none`. That is deliberate: a bare country code would have
  to be guessed into a hierarchy, and this library does not guess.

  The mechanism exists because of a specific trap. US federal law has
  no daily overtime; California does. A checker keyed on 'US' that
  returned 'compliant' for a twelve-hour day would be confidently wrong
  for a worker in San Jose.

  ## Windows

  Rules carry a window — `:day`, `:week`, `:month`, `:year`,
  `:rolling-months`. A rule whose window is longer than the period
  handed to `check` is NOT evaluated and says so. Checking one week
  tells you nothing about an annual cap, and this refuses to imply
  otherwise.

  Rules over `:month` and longer generally count STATUTORY OVERTIME
  rather than raw hours, which needs the week and month a span falls
  in. The caller supplies `:week-of` / `:month-of` in `opts` for the
  same reason it supplies `:date-of`: the answer depends on a calendar
  and a timezone this library will not assume.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

(def ^:private ms-per-hour 3600000)
(def ^:private ms-per-day 86400000)

;; ---------------------------------------------------------------------------
;; Rule vocabulary
;; ---------------------------------------------------------------------------

(def window-of-kind
  "How long a period a rule needs before it can be judged. `check` marks
  anything longer than the period it was given as unevaluated."
  {:daily-hours-max                :day
   :break-min                      :day
   :daily-rest-min                 :day
   :daily-overtime-from            :day
   :daily-double-time-from         :day
   :weekly-hours-max               :week
   :weekly-overtime-from           :week
   :weekly-rest-min                :week
   :consecutive-days-max           :week
   :monthly-overtime-max           :month
   :annual-overtime-max            :year
   :months-over-monthly-limit-max  :year
   :rolling-average-overtime-max   :rolling-months})

(def ^:private window-days
  {:day 0 :week 7 :month 28 :rolling-months 56 :year 365})

(def priced-kinds
  "Violation kinds where the statute PRICES the hours rather than
  forbidding them. An overtime premium is lawful and expensive; a missed
  rest period is not lawful at any price. Consumers are expected to
  route the two differently."
  #{:overtime-due :double-time-due})

;; ---------------------------------------------------------------------------
;; Rules
;;
;; Each rule carries the provision it comes from; each jurisdiction the
;; date it was recorded. A reader can check them rather than trust them,
;; and a stale rule set shows up as a stale date rather than as a
;; confident answer.
;; ---------------------------------------------------------------------------

(def rules
  "Rule sets by jurisdiction path. Recorded 2026-07-31; verify against
  the current statute before relying on any of it."
  {[:jp]
   {:law/name "労働基準法"
    :law/as-of "2026-07-31"
    :law/overtime-baseline {:daily 8 :weekly 40}
    :law/rules
    [{:rule/id :jp-daily-8 :rule/kind :daily-hours-max :rule/hours 8
      :rule/citation "労働基準法 第32条第2項"
      :rule/note "法定労働時間。36協定があれば時間外として超過しうるが、超過自体は記録される"}
     {:rule/id :jp-weekly-40 :rule/kind :weekly-hours-max :rule/hours 40
      :rule/citation "労働基準法 第32条第1項"}
     {:rule/id :jp-break-45 :rule/kind :break-min :rule/over-hours 6 :rule/minutes 45
      :rule/citation "労働基準法 第34条第1項"}
     {:rule/id :jp-break-60 :rule/kind :break-min :rule/over-hours 8 :rule/minutes 60
      :rule/citation "労働基準法 第34条第1項"}
     {:rule/id :jp-weekly-rest :rule/kind :weekly-rest-min :rule/hours 24
      :rule/citation "労働基準法 第35条第1項"
      :rule/note "毎週少なくとも1回の休日。4週4日の変形休日制（第35条第2項）は本ルールでは扱わない"}
     ;; ---- 36協定 (時間外労働の上限規制) ----
     {:rule/id :jp-36-monthly-45 :rule/kind :monthly-overtime-max :rule/hours 45
      :rule/citation "労働基準法 第36条第4項"
      :rule/note "限度時間。特別条項があれば年6回まで超えられる（:jp-36-months-over-6 を参照）"}
     {:rule/id :jp-36-annual-360 :rule/kind :annual-overtime-max :rule/hours 360
      :rule/citation "労働基準法 第36条第4項"}
     {:rule/id :jp-36-special-monthly-100 :rule/kind :monthly-overtime-max :rule/hours 100
      :rule/citation "労働基準法 第36条第6項第2号"
      :rule/note "特別条項があっても超えられない絶対上限（単月100時間未満、休日労働を含む）。本ルールは休日労働を分離して数えないため、休日労働がある月では過小評価しうる"}
     {:rule/id :jp-36-special-annual-720 :rule/kind :annual-overtime-max :rule/hours 720
      :rule/citation "労働基準法 第36条第5項"}
     {:rule/id :jp-36-rolling-80 :rule/kind :rolling-average-overtime-max :rule/hours 80
      :rule/months 2
      :rule/citation "労働基準法 第36条第6項第3号"
      :rule/note "2〜6か月平均で80時間以内（休日労働を含む）。本ルールは2か月平均のみを検査する"}
     {:rule/id :jp-36-months-over-6 :rule/kind :months-over-monthly-limit-max
      :rule/limit-hours 45 :rule/times 6
      :rule/citation "労働基準法 第36条第5項"
      :rule/note "月45時間を超えられるのは年6回まで"}]}

   [:us]
   {:law/name "Fair Labor Standards Act (federal)"
    :law/as-of "2026-07-31"
    :law/rules
    [{:rule/id :us-weekly-ot-40 :rule/kind :weekly-overtime-from :rule/hours 40
      :rule/citation "29 U.S.C. §207(a)(1)"
      :rule/note "1.5× over 40 hours in a workweek for non-exempt employees"}]
    :law/absent
    ;; Named explicitly. A reader who sees no daily rule should know that
    ;; is the statute's silence, not this library's gap — and should also
    ;; know that several states fill that silence.
    [{:absent/kind :daily-hours-max
      :absent/note "federal law sets no daily hour cap and no daily overtime; several states do — see [:us :ca]"}
     {:absent/kind :break-min
      :absent/note "federal law mandates no meal or rest break; many states do"}]}

   [:us :ca]
   {:law/name "California Labor Code / IWC Wage Orders"
    :law/as-of "2026-07-31"
    :law/rules
    [{:rule/id :ca-daily-ot-8 :rule/kind :daily-overtime-from :rule/hours 8
      :rule/citation "Cal. Lab. Code §510(a)"
      :rule/note "1.5× beyond 8 hours in a workday — the daily overtime federal law does not have"}
     {:rule/id :ca-daily-dt-12 :rule/kind :daily-double-time-from :rule/hours 12
      :rule/citation "Cal. Lab. Code §510(a)"
      :rule/note "2× beyond 12 hours in a workday"}
     {:rule/id :ca-meal-30 :rule/kind :break-min :rule/over-hours 5 :rule/minutes 30
      :rule/citation "Cal. Lab. Code §512(a); §226.7"
      :rule/note "waivable by mutual consent when the day does not exceed 6 hours — the waiver is not modelled, so a waived day reads as a violation. The statutory remedy is one hour of premium pay, but this is modelled as a prohibition rather than a price: an employer cannot systematically buy out meal periods"}
     {:rule/id :ca-day-of-rest :rule/kind :weekly-rest-min :rule/hours 24
      :rule/citation "Cal. Lab. Code §551, §552"
      :rule/note "one day's rest in seven"}
     {:rule/id :ca-seventh-day :rule/kind :consecutive-days-max :rule/days 6
      :rule/citation "Cal. Lab. Code §510(a)"
      :rule/note "the seventh consecutive day in a workweek is paid at 1.5× for the first 8 hours and 2× beyond — the premium is not computed here, only the fact that a seventh day occurred"}]}

   [:eu]
   {:law/name "Directive 2003/88/EC (Working Time Directive)"
    :law/as-of "2026-07-31"
    :law/rules
    [{:rule/id :eu-weekly-48 :rule/kind :weekly-hours-max :rule/hours 48
      :rule/citation "Directive 2003/88/EC Art. 6(b)"
      :rule/note "average over a reference period, including overtime. This library checks a single week, which is stricter than the directive requires"}
     {:rule/id :eu-daily-rest-11 :rule/kind :daily-rest-min :rule/hours 11
      :rule/citation "Directive 2003/88/EC Art. 3"}
     {:rule/id :eu-break-6 :rule/kind :break-min :rule/over-hours 6 :rule/minutes 0
      :rule/citation "Directive 2003/88/EC Art. 4"
      :rule/note "a break is required but its length is left to member states, so the minimum here is 0 and the rule only records that one must exist"}
     {:rule/id :eu-weekly-rest-24 :rule/kind :weekly-rest-min :rule/hours 24
      :rule/citation "Directive 2003/88/EC Art. 5"
      :rule/note "in addition to the 11-hour daily rest"}]
    :law/note "a directive binds member states, not employers directly. Member states appear as sub-levels ([:eu :fr], [:eu :de]) because national law layers on top of the directive floor"}

   [:eu :fr]
   {:law/name "Code du travail"
    :law/as-of "2026-07-31"
    :law/overtime-baseline {:weekly 35}
    :law/rules
    [{:rule/id :fr-weekly-ot-35 :rule/kind :weekly-overtime-from :rule/hours 35
      :rule/citation "Code du travail Art. L3121-27"
      :rule/note "durée légale — hours beyond it are heures supplémentaires, not a prohibition"}
     {:rule/id :fr-daily-10 :rule/kind :daily-hours-max :rule/hours 10
      :rule/citation "Code du travail Art. L3121-18"
      :rule/note "derogations to 12h exist by agreement or authorisation and are not modelled"}
     {:rule/id :fr-weekly-48 :rule/kind :weekly-hours-max :rule/hours 48
      :rule/citation "Code du travail Art. L3121-20"}
     {:rule/id :fr-daily-rest-11 :rule/kind :daily-rest-min :rule/hours 11
      :rule/citation "Code du travail Art. L3131-1"}
     {:rule/id :fr-weekly-rest-35 :rule/kind :weekly-rest-min :rule/hours 35
      :rule/citation "Code du travail Art. L3132-2"
      :rule/note "24h consécutives plus les 11h de repos quotidien"}]
    :law/absent
    [{:absent/kind :rolling-average-overtime-max
      :absent/note "the 44h average over 12 consecutive weeks (Art. L3121-22) is not modelled — it needs a 12-week window this rule set does not carry"}]}

   [:eu :de]
   {:law/name "Arbeitszeitgesetz (ArbZG)"
    :law/as-of "2026-07-31"
    :law/rules
    [{:rule/id :de-daily-8 :rule/kind :daily-hours-max :rule/hours 8
      :rule/citation "ArbZG §3"
      :rule/note "extendable to 10h if the average over six months stays at 8h — the averaging window is not modelled, so a 9h day reads as a violation that the six-month average may in fact permit"}
     {:rule/id :de-break-30 :rule/kind :break-min :rule/over-hours 6 :rule/minutes 30
      :rule/citation "ArbZG §4"}
     {:rule/id :de-break-45 :rule/kind :break-min :rule/over-hours 9 :rule/minutes 45
      :rule/citation "ArbZG §4"}
     {:rule/id :de-daily-rest-11 :rule/kind :daily-rest-min :rule/hours 11
      :rule/citation "ArbZG §5"}]}})

(defn known-jurisdictions [] (set (keys rules)))

(defn- levels-of
  "Every prefix of a jurisdiction path, longest last: [:us :ca] ->
  ([:us] [:us :ca])."
  [j]
  (for [n (range 1 (inc (count j)))] (vec (take n j))))

;; ---------------------------------------------------------------------------
;; Overtime baseline
;; ---------------------------------------------------------------------------

(defn- hours [ms] (/ (double ms) ms-per-hour))

(defn statutory-overtime
  "Hours beyond the statutory baseline, computed the way the longer-window
  caps count them: daily excess first, then whatever weekly excess the
  remaining regular hours produce. Counting both in full would
  double-count the same hour.

  `baseline` is `{:daily n :weekly n}`; either may be absent."
  [day-hours-by-week {:keys [daily weekly]}]
  (reduce
   (fn [total day-hours]
     (let [daily-ot (if daily (reduce + 0.0 (map #(max 0.0 (- % daily)) day-hours)) 0.0)
           regular  (if daily
                      (reduce + 0.0 (map #(min % daily) day-hours))
                      (reduce + 0.0 day-hours))
           weekly-ot (if weekly (max 0.0 (- regular weekly)) 0.0)]
       (+ total daily-ot weekly-ot)))
   0.0
   day-hours-by-week))

;; ---------------------------------------------------------------------------
;; Grouping
;; ---------------------------------------------------------------------------

(defn- totals-by [worked key-fn]
  (into {} (for [[k spans] (group-by #(key-fn (:worked/start %)) worked)]
             [k (hours (reduce + 0 (map :worked/ms spans)))])))

(defn- day-hours-per-week
  "[[d1 d2 ...] ...] — one vector of day totals per week."
  [worked date-of week-of]
  (for [[_ wspans] (sort-by key (group-by #(week-of (:worked/start %)) worked))]
    (vec (vals (totals-by wspans date-of)))))

;; ---------------------------------------------------------------------------
;; Per-window checks
;; ---------------------------------------------------------------------------

(defn breaks-known?
  "Does this day's data say anything about breaks at all?

  `:worked/break-ms` absent means the SOURCE does not record breaks — a
  planned roster says `09:00–17:00` and nothing about whether anyone
  stopped for lunch. `:worked/break-ms 0` means the source does record
  them and there were none, which is a real finding.

  nil is not zero. Asserting a missed break from a roster would be
  claiming to have seen something the data never contained, and every
  full-day planned shift would read as unlawful."
  [spans]
  (every? #(some? (:worked/break-ms %)) spans))

(defn- check-daily [rule day-key spans]
  (let [total-ms (reduce + 0 (map :worked/ms spans))
        break-ms (reduce + 0 (map #(or (:worked/break-ms %) 0) spans))
        h (hours total-ms)]
    (case (:rule/kind rule)
      :daily-hours-max
      (when (> h (:rule/hours rule))
        {:violation/rule rule :violation/day day-key
         :violation/actual h :violation/limit (:rule/hours rule)
         :violation/detail (str h "h worked, limit " (:rule/hours rule) "h")})

      :daily-overtime-from
      (when (> h (:rule/hours rule))
        {:violation/rule rule :violation/day day-key :violation/kind :overtime-due
         :violation/actual h :violation/limit (:rule/hours rule)
         :violation/detail (str (- h (:rule/hours rule)) "h beyond " (:rule/hours rule)
                                "h attract the daily overtime premium")})

      :daily-double-time-from
      (when (> h (:rule/hours rule))
        {:violation/rule rule :violation/day day-key :violation/kind :double-time-due
         :violation/actual h :violation/limit (:rule/hours rule)
         :violation/detail (str (- h (:rule/hours rule)) "h beyond " (:rule/hours rule)
                                "h attract double time")})

      :break-min
      (when (and (breaks-known? spans)
                 (> h (:rule/over-hours rule))
                 (< (/ break-ms 60000.0) (:rule/minutes rule)))
        {:violation/rule rule :violation/day day-key
         :violation/actual (/ break-ms 60000.0) :violation/limit (:rule/minutes rule)
         :violation/detail (str (/ break-ms 60000.0) " min break on a " h "h day, minimum "
                                (:rule/minutes rule) " min")})
      nil)))

(defn- check-weekly [rule worked date-of]
  (let [h (hours (reduce + 0 (map :worked/ms worked)))]
    (case (:rule/kind rule)
      :weekly-hours-max
      (when (> h (:rule/hours rule))
        {:violation/rule rule :violation/actual h :violation/limit (:rule/hours rule)
         :violation/detail (str h "h in the week, limit " (:rule/hours rule) "h")})

      :weekly-overtime-from
      (when (> h (:rule/hours rule))
        {:violation/rule rule :violation/actual h :violation/limit (:rule/hours rule)
         :violation/kind :overtime-due
         :violation/detail (str (- h (:rule/hours rule)) "h beyond " (:rule/hours rule)
                                "h attract the statutory overtime premium")})

      :consecutive-days-max
      (let [n (count (distinct (map #(date-of (:worked/start %)) worked)))]
        (when (> n (:rule/days rule))
          {:violation/rule rule :violation/kind :overtime-due
           :violation/actual n :violation/limit (:rule/days rule)
           :violation/detail (str n " consecutive worked days; day "
                                  (inc (:rule/days rule)) " onward carries a premium")}))
      nil)))

(def period-dependent-rules
  "Rules that cannot be evaluated without the period's bounds. A week
  with Monday to Friday worked and nothing after it does not say whether
  the weekend was a day off or simply outside the data, and guessing
  either way is wrong in a different direction."
  #{:weekly-rest-min})

(defn- rest-gaps
  "Gaps between consecutive worked spans, plus — when a period is given —
  the gap before the first span and after the last.

  Edge gaps may only be used to SATISFY a rule, never to violate one. A
  window that happens to start at midnight before an 09:00 shift shows a
  nine-hour leading gap that is an artifact of where the query was cut,
  not a rest period anyone was denied. So they are returned separately
  and only the rules that look for a long-enough gap consult them."
  [worked period]
  (let [sorted (sort-by :worked/start worked)
        inner (map (fn [[a b]] {:from (:worked/end a) :to (:worked/start b)
                                :hours (hours (- (:worked/start b) (:worked/end a)))})
                   (partition 2 1 sorted))
        [pf pt] period
        edges (when (and pf pt (seq sorted))
                [{:from pf :to (:worked/start (first sorted))
                  :hours (hours (- (:worked/start (first sorted)) pf))}
                 {:from (:worked/end (last sorted)) :to pt
                  :hours (hours (- pt (:worked/end (last sorted))))}])]
    {:inner (vec inner) :edges (vec edges)}))

(defn- check-rest [rule worked period]
  (let [{:keys [inner edges]} (rest-gaps worked period)]
    (case (:rule/kind rule)
      :daily-rest-min
      (keep (fn [g]
              (when (< (:hours g) (:rule/hours rule))
                {:violation/rule rule :violation/actual (:hours g)
                 :violation/limit (:rule/hours rule)
                 :violation/detail (str (:hours g) "h rest between shifts, minimum "
                                        (:rule/hours rule) "h")}))
            inner)

      :weekly-rest-min
      (let [all (concat inner edges)]
        (when (and period (seq all)
                   (not (some #(>= (:hours %) (:rule/hours rule)) all)))
          [{:violation/rule rule
            :violation/actual (apply max (map :hours all))
            :violation/limit (:rule/hours rule)
            :violation/detail (str "no rest period of " (:rule/hours rule)
                                   "h in the period; longest was "
                                   (apply max (map :hours all)) "h")}]))
      nil)))

(defn- check-long-window
  "Monthly / annual / rolling rules, which count STATUTORY OVERTIME
  rather than raw hours."
  [rule ot-by-month]
  (let [months (sort-by key ot-by-month)
        vals* (mapv val months)]
    (case (:rule/kind rule)
      :monthly-overtime-max
      (seq (for [[m ot] months :when (> ot (:rule/hours rule))]
             {:violation/rule rule :violation/month m
              :violation/actual ot :violation/limit (:rule/hours rule)
              :violation/detail (str m ": " ot "h の時間外、上限 " (:rule/hours rule) "h")}))

      :annual-overtime-max
      (let [total (reduce + 0.0 vals*)]
        (when (> total (:rule/hours rule))
          [{:violation/rule rule :violation/actual total :violation/limit (:rule/hours rule)
            :violation/detail (str "年間 " total "h の時間外、上限 " (:rule/hours rule) "h")}]))

      :months-over-monthly-limit-max
      (let [n (count (filter #(> % (:rule/limit-hours rule)) vals*))]
        (when (> n (:rule/times rule))
          [{:violation/rule rule :violation/actual n :violation/limit (:rule/times rule)
            :violation/detail (str "月" (:rule/limit-hours rule) "h 超が " n " 回、上限 "
                                   (:rule/times rule) " 回")}]))

      :rolling-average-overtime-max
      (let [n (:rule/months rule)]
        (seq (for [window (partition n 1 months)
                   :let [avg (/ (reduce + 0.0 (map val window)) n)]
                   :when (> avg (:rule/hours rule))]
               {:violation/rule rule
                :violation/months (mapv key window)
                :violation/actual avg :violation/limit (:rule/hours rule)
                :violation/detail (str (mapv key window) " の平均 " avg
                                       "h、上限 " (:rule/hours rule) "h")})))
      nil)))

;; ---------------------------------------------------------------------------
;; check
;; ---------------------------------------------------------------------------

(defn- period-days [[from to]] (when (and from to) (/ (double (- to from)) ms-per-day)))

(defn- evaluable?
  "Can this rule's window be judged over a period this long? A rule whose
  window is longer than what was observed is not evaluated."
  [rule days]
  (let [needed (get window-days (get window-of-kind (:rule/kind rule) :day) 0)]
    (or (zero? needed) (and days (>= days needed)))))

(defn check
  "Check one person's worked spans against `jurisdiction`.

  `worked` is a collection of `kotoba.shift` worked spans (or anything
  with `:worked/start :worked/end :worked/ms` and optionally
  `:worked/break-ms`). `date-of` maps an instant to a day key — the
  caller owns the timezone, and in this domain that is not a detail:
  which side of midnight a night shift falls on decides whether a daily
  cap was broken.

  `opts`:
    :period   [from to]  bounds of the period examined
    :week-of  fn         instant -> week key   (long-window rules)
    :month-of fn         instant -> month key  (long-window rules)

  Returns

    {:worklaw/coverage    :full | :partial | :none
     :worklaw/checked     [[:us] ...]      levels that had rules
     :worklaw/unchecked   [[:us :ca] ...]  levels that had none
     :worklaw/unevaluated [{:rule/id :jp-36-annual-360
                            :unevaluated/reason :window-longer-than-period} ...]
     :worklaw/violations  [...]
     :worklaw/citations   [...]}

  `:unevaluated/reason` is one of

    :window-longer-than-period  inherent — a week cannot judge an annual
                                cap, and no caller can fix that
    :missing-period             the caller gave no `:period`
    :missing-calendar           the caller gave no `:week-of`/`:month-of`

  The last two are caller errors and the first is not, which is why they
  are distinguished rather than pooled.

  Read `:worklaw/coverage` and `:worklaw/unevaluated` before
  `:worklaw/violations`. An empty violation list under coverage `:none`
  means nothing was checked, and one with a non-empty `:unevaluated`
  means part of the statute was skipped."
  ([worked jurisdiction date-of] (check worked jurisdiction date-of {}))
  ([worked jurisdiction date-of opts]
   (let [{:keys [period week-of month-of]} opts
         days (period-days (or period [nil nil]))
         levels (levels-of jurisdiction)
         {checked true unchecked false} (group-by #(contains? rules %) levels)
         applicable (mapcat #(get-in rules [% :law/rules]) checked)
         ;; The baseline for statutory overtime comes from the most
         ;; specific level that declares one — a French week starts at
         ;; 35h, a Japanese one at 40h.
         baseline (or (some #(get-in rules [% :law/overtime-baseline]) (reverse checked))
                      {:daily 8 :weekly 40})
         by-day (group-by #(date-of (:worked/start %)) worked)
         long-window? #(contains? #{:month :year :rolling-months}
                                  (get window-of-kind (:rule/kind %) :day))
         ot-by-month (when (and week-of month-of)
                       (into {} (for [[m spans] (group-by #(month-of (:worked/start %)) worked)]
                                  [m (statutory-overtime
                                      (day-hours-per-week spans date-of week-of) baseline)])))
         ;; Why a rule could not be judged, or nil when it can. The two
         ;; kinds are not the same and consumers route them differently:
         ;; :window-longer-than-period is inherent (a week cannot judge an
         ;; annual cap, and no caller can fix that), while the others mean
         ;; the caller did not supply what the check needs.
         blocked (fn [r]
                   (cond
                     ;; Checked first on purpose: over seven days an annual
                     ;; cap is unjudgeable whether or not a calendar was
                     ;; supplied, and reporting that as a caller error
                     ;; would send someone looking for a fix that does not
                     ;; exist.
                     (and days (not (evaluable? r days)))
                     :window-longer-than-period

                     ;; No bounds at all is a caller error, not an inherent
                     ;; limit — every windowed rule is blocked, and saying
                     ;; "window longer than period" about a period nobody
                     ;; gave would point at the wrong fix.
                     (and (nil? days) (not (evaluable? r days)))
                     :missing-period

                     (and (contains? period-dependent-rules (:rule/kind r)) (nil? period))
                     :missing-period

                     (and (long-window? r) (nil? ot-by-month))
                     :missing-calendar))
         by-blocked (group-by blocked applicable)
         yes (get by-blocked nil [])
         ;; A break rule over a day whose source records no breaks is not
         ;; satisfied and not violated — it was not evaluated, and saying
         ;; so is the whole point of this library.
         break-days-unknown (remove #(breaks-known? (val %)) by-day)
         no  (vec (concat
                   (for [[reason rs] by-blocked :when reason, r rs]
                     {:rule/id (:rule/id r) :unevaluated/reason reason})
                   (when (seq break-days-unknown)
                     (for [r yes :when (= :break-min (:rule/kind r))]
                       {:rule/id (:rule/id r)
                        :unevaluated/reason :missing-break-data
                        :unevaluated/days (mapv key break-days-unknown)}))))
         daily (for [r yes [day spans] by-day :let [v (check-daily r day spans)] :when v] v)
         weekly (keep #(check-weekly % worked date-of) yes)
         rest-v (mapcat #(or (check-rest % worked period) []) yes)
         long-v (when ot-by-month
                  (mapcat #(or (check-long-window % ot-by-month) []) (filter long-window? yes)))]
     {:worklaw/coverage    (cond (empty? checked)   :none
                                 (seq unchecked)    :partial
                                 :else              :full)
      :worklaw/checked     (vec checked)
      :worklaw/unchecked   (vec unchecked)
      :worklaw/unevaluated no
      :worklaw/violations  (vec (concat daily weekly rest-v long-v))
      :worklaw/citations   (vec (distinct (map :rule/citation applicable)))})))

;; ---------------------------------------------------------------------------
;; Reading a result
;; ---------------------------------------------------------------------------

(defn priced
  "Findings where the statute prices the hours (an overtime or
  double-time premium)."
  [result]
  (filterv #(contains? priced-kinds (:violation/kind %)) (:worklaw/violations result)))

(defn prohibitions
  "Findings that forbid rather than price. A missed rest period is not
  lawful at any price; overtime is."
  [result]
  (filterv #(not (contains? priced-kinds (:violation/kind %))) (:worklaw/violations result)))

(defn compliant?
  "True only when the jurisdiction was FULLY covered, every rule could be
  evaluated, and nothing fired.

  Deliberately not `(empty? violations)`. A partially covered
  jurisdiction, or one where a rule was skipped for want of a long
  enough period, is not compliant; it is unknown, and this predicate
  says false so that a caller who reaches for the convenient boolean
  gets the conservative answer rather than the flattering one."
  [result]
  (and (= :full (:worklaw/coverage result))
       (empty? (:worklaw/unevaluated result))
       (empty? (:worklaw/violations result))))

(defn describe
  "Human summary. Always states coverage first, so a report can never
  read as an all-clear it did not earn."
  [result]
  (let [{:worklaw/keys [coverage violations unchecked unevaluated]} result]
    (str (case coverage
           :none    (str "NOT CHECKED — no rules for " (pr-str unchecked))
           :partial (str "PARTIALLY CHECKED — no rules for " (pr-str unchecked))
           :full    "checked")
         (when (seq unevaluated)
           (str "; NOT EVALUATED: "
                (str/join ", " (for [[reason rs] (sort-by key (group-by :unevaluated/reason unevaluated))]
                                 (str (mapv :rule/id rs) " (" (name reason) ")")))))
         (if (seq violations)
           (str "; " (count violations) " violation(s): "
                (str/join ", " (map #(name (get-in % [:violation/rule :rule/id])) violations)))
           (if (and (= :full coverage) (empty? unevaluated)) "; no violations" "")))))

(defn absences
  "What a jurisdiction's statute is recorded as NOT regulating, and what
  this rule set is recorded as not modelling. Distinct from a missing
  rule set: `[:us]` has no daily hour cap because federal law sets none,
  and a caller building a roster tool should surface that rather than
  infer it."
  [jurisdiction]
  (vec (mapcat #(get-in rules [% :law/absent]) (levels-of jurisdiction))))
