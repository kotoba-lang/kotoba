(ns ical.execute
  "Pure recurrence expansion for iCalendar events (RFC 5545 RRULE). No I/O, no
  third-party deps — portable .cljc (JVM, ClojureScript, SCI).

  Date arithmetic uses the Howard Hinnant proleptic-Gregorian day-number algorithm
  (days_from_civil / civil_from_days), which maps a (year, month, day) triple to/from
  a serial integer (days since 1970-01-01) and lets us add days and compute weekdays
  with pure integer math — no java.time, no js/Date.

  Entry point:

    (occurrences event from-dt to-dt)

  Returns a plain vector of `:ical/dtstart`-shaped maps `{:y :m :d :hh :mm}` for all
  occurrences of `event` whose date falls in `[from-dt, to-dt)`. A non-recurring event
  yields at most its dtstart. The :hh/:mm of the original dtstart are preserved on each
  returned occurrence."

  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Howard Hinnant day-number arithmetic (proleptic Gregorian calendar)
;; Reference: https://howardhinnant.github.io/date_algorithms.html
;; ---------------------------------------------------------------------------

(defn- days-from-civil
  "Map (year, month, day) → serial day number (days since 1970-01-01).
  Correct for any proleptic Gregorian date."
  [y m d]
  (let [y   (if (<= m 2) (dec y) y)
        era (quot (if (>= y 0) y (- y 399)) 400)
        yoe (- y (* era 400))
        doy (+ (quot (+ (* 153 (if (> m 2) (- m 3) (+ m 9))) 2) 5) (dec d))
        doe (+ (* yoe 365) (quot yoe 4) (- (quot yoe 100)) doy)]
    (+ (* era 146097) doe -719468)))

(defn- civil-from-days
  "Map serial day number → {:y year :m month :d day} (proleptic Gregorian)."
  [z]
  (let [z   (+ z 719468)
        era (quot (if (>= z 0) z (- z 146096)) 146097)
        doe (- z (* era 146097))
        yoe (quot (- doe (quot doe 1460) (- (quot doe 36524)) (quot doe 146096)) 365)
        y   (+ yoe (* era 400))
        doy (- doe (+ (* 365 yoe) (quot yoe 4) (- (quot yoe 100))))
        mp  (quot (+ (* 5 doy) 2) 153)
        d   (inc (- doy (quot (+ (* 153 mp) 2) 5)))
        m   (if (< mp 10) (+ mp 3) (- mp 9))
        y   (if (<= m 2) (inc y) y)]
    {:y y :m m :d d}))

(defn weekday-from-days
  "Return the day of week for serial day number `z`. Returns 0=Sun, 1=Mon, …, 6=Sat.
  Exported so callers / tests can do weekday sanity checks."
  [z]
  (if (>= z -4)
    (mod (+ z 4) 7)
    (+ (rem (+ z 5) 7) 6)))

;; ---------------------------------------------------------------------------
;; Date-map ↔ day-number helpers
;; ---------------------------------------------------------------------------

(defn- dt->n [dt] (days-from-civil (:y dt) (:m dt) (:d dt)))

(defn- n->dt
  "Combine a serial day number with an hh/mm to produce a dtstart-shaped map."
  [n hh mm]
  (assoc (civil-from-days n) :hh hh :mm mm))

;; ---------------------------------------------------------------------------
;; Month arithmetic helpers
;; ---------------------------------------------------------------------------

(defn- leap? [y]
  (and (zero? (mod y 4))
       (or (not (zero? (mod y 100)))
           (zero? (mod y 400)))))

(defn- days-in-month [y m]
  (nth [0 31 (if (leap? y) 29 28) 31 30 31 30 31 31 30 31 30 31] m))

;; ---------------------------------------------------------------------------
;; BYDAY weekday offset from Monday (ISO week, default WKST=MO)
;; ---------------------------------------------------------------------------

(def ^:private byday->mon-offset
  "Offset in days from the Monday of the ISO week."
  {:mo 0 :tu 1 :we 2 :th 3 :fr 4 :sa 5 :su 6})

(defn- monday-of-week
  "Return the serial day number of the Monday of the week containing day `n`.
  Uses ISO week convention (Monday = start of week)."
  [n]
  ;; weekday: 0=Sun 1=Mon … 6=Sat
  ;; days since Monday: Mon→0, Tue→1, … Sun→6
  (let [wd (weekday-from-days n)
        days-since-mon (mod (dec wd) 7)]      ; (wd - 1 + 7) mod 7 — clojure mod is always ≥0
    (- n days-since-mon)))

;; ---------------------------------------------------------------------------
;; RRULE expansion
;; ---------------------------------------------------------------------------

(defn- expand-daily
  [start-n hh mm interval cnt until-n from-n to-n]
  (let [max-n (or cnt 3650)]
    (loop [step 0 acc []]
      (if (>= step max-n)
        acc
        (let [day-n (+ start-n (* step interval))]
          (cond
            (> day-n (if until-n (min until-n (dec to-n)) (dec to-n)))
            acc
            (and (>= day-n from-n) (>= day-n start-n))
            (recur (inc step) (conj acc (n->dt day-n hh mm)))
            :else
            (recur (inc step) acc)))))))

(defn- expand-weekly
  [start-n hh mm interval byday cnt until-n from-n to-n]
  (let [base-mon (monday-of-week start-n)
        offsets  (if (seq byday)
                   (sort (map byday->mon-offset byday))
                   ;; No BYDAY: use the original weekday
                   [(- start-n base-mon)])]
    ;; `step` counts true series occurrences (independent of the query
    ;; window), mirroring expand-daily/expand-monthly's `step`. COUNT must
    ;; bound the real RRULE series, not how many occurrences happened to
    ;; land inside [from-n, to-n) -- otherwise a `from-n` that excludes an
    ;; early occurrence lets the loop run past the true end of the series
    ;; and emit a phantom extra occurrence to compensate.
    (loop [week 0 acc [] step 0]
      (let [week-mon (+ base-mon (* week interval 7))]
        (if (or (and cnt (>= step cnt))
                (> week-mon (+ (or until-n to-n) 7)))
          acc
          (let [[acc' step']
                (reduce (fn [[a s] off]
                          (if (and cnt (>= s cnt))
                            [a s]
                            (let [day-n (+ week-mon off)]
                              (cond
                                (< day-n start-n) [a s]              ; before dtstart: not in series
                                (and until-n (> day-n until-n)) [a s] ; past UNTIL: not in series
                                (and (>= day-n from-n) (< day-n to-n))
                                [(conj a (n->dt day-n hh mm)) (inc s)]
                                :else [a (inc s)]))))
                        [acc step]
                        offsets)]
            (recur (inc week) acc' step')))))))

(defn- expand-monthly
  [dtstart hh mm interval cnt until-n from-n to-n]
  (let [start-y (:y dtstart)
        start-m (:m dtstart)
        start-d (:d dtstart)
        max-n   (or cnt 1200)]
    (loop [step 0 acc []]
      (if (>= step max-n)
        acc
        (let [total-months (+ (dec start-m) (* step interval))
              y  (+ start-y (quot total-months 12))
              m  (inc (mod total-months 12))
              d  (min start-d (days-in-month y m))
              dt {:y y :m m :d d :hh hh :mm mm}
              n  (dt->n dt)]
          (cond
            (> n (if until-n (min until-n (dec to-n)) (dec to-n)))
            acc
            (and (>= n from-n) (>= n (dt->n dtstart)))
            (recur (inc step) (conj acc dt))
            :else
            (recur (inc step) acc)))))))

;; ---------------------------------------------------------------------------
;; Public API
;; ---------------------------------------------------------------------------

(defn occurrences
  "Return a vector of dtstart-shaped maps `{:y :m :d :hh :mm}` for all
  occurrences of `event` whose date falls in `[from-dt, to-dt)`.

  - Non-recurring event: yields [dtstart] if dtstart ∈ [from-dt, to-dt).
  - RRULE with FREQ :daily/:weekly/:monthly + :interval (default 1):
    - bounded by :count occurrences, or :until date (inclusive), or to-dt.
    - :byday for :weekly specifies which weekdays within the interval-th week to emit
      (both days are generated per interval, e.g. BYDAY=MO,WE gives Mon+Wed each week).
  - :yearly RRULE: treated as monthly with interval*12 (basic support)."
  [event from-dt to-dt]
  (let [dtstart  (get event :ical/dtstart)
        rrule    (get event :ical/rrule)
        hh       (get dtstart :hh 0)
        mm       (get dtstart :mm 0)
        start-n  (dt->n dtstart)
        from-n   (dt->n from-dt)
        to-n     (dt->n to-dt)]
    (if (nil? rrule)
      ;; Non-recurring
      (if (and (>= start-n from-n) (< start-n to-n))
        [dtstart]
        [])
      ;; Recurring
      (let [freq     (get rrule :ical/freq :weekly)
            interval (get rrule :ical/interval 1)
            cnt      (get rrule :ical/count)
            until    (get rrule :ical/until)
            byday    (get rrule :ical/byday)
            until-n  (when until (dt->n until))]
        (case freq
          :daily
          (expand-daily start-n hh mm interval cnt until-n from-n to-n)

          :weekly
          (expand-weekly start-n hh mm interval byday cnt until-n from-n to-n)

          :monthly
          (expand-monthly dtstart hh mm interval cnt until-n from-n to-n)

          :yearly
          (expand-monthly dtstart hh mm (* interval 12) cnt until-n from-n to-n)

          [])))))
