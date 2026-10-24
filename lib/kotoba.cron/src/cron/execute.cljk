(ns cron.execute
  "Pure cron next-fire evaluator. A datetime is a plain map {:y :m :d :hh :mm}.
  No java.time, no Date — all calendar arithmetic is done via a proleptic-Gregorian
  day-number helper (Howard Hinnant's days_from_civil / civil_from_days).

  Day-of-week convention: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
  (matches cron dow field from cron.model/parse).

  Key functions:
    days-from-civil (y m d) → integer day number  (Unix epoch = 0 = 1970-01-01)
    civil-from-days (n)     → [y m d]
    weekday         (y m d) → 0..6 (Sun..Sat)
    fires-at?       (cron dt) → boolean
    next-fire       (cron from-dt) → dt | nil  (strictly after from-dt; nil if > ~3 yr)")

;; ---------------------------------------------------------------------------
;; Proleptic-Gregorian day-number helpers (Howard Hinnant, days_from_civil)
;; Reference: https://howardhinnant.github.io/date_algorithms.html
;; ---------------------------------------------------------------------------

(defn days-from-civil
  "Return the integer serial day number for the proleptic Gregorian date (y m d).
  The Unix epoch (1970-01-01) maps to 0. Works for any year >= -32767."
  [y m d]
  (let [y   (long (if (<= m 2) (dec y) y))
        era (long (quot (if (>= y 0) y (- y 399)) 400))
        yoe (- y (* era 400))                                 ; [0, 399]
        doy (+ (quot (+ (* 153 (+ m (if (> m 2) -3 9))) 2) 5)
               d -1)                                          ; [0, 365]
        doe (+ (* yoe 365)
               (quot yoe 4)
               (- (quot yoe 100))
               doy)                                           ; [0, 146096]
        ]
    (- (+ (* era 146097) doe) 719468)))

(defn civil-from-days
  "Return [y m d] for the proleptic Gregorian date at serial day number n."
  [n]
  (let [z   (+ n 719468)
        era (long (quot (if (>= z 0) z (- z 146096)) 146097))
        doe (- z (* era 146097))                              ; [0, 146096]
        yoe (long (quot (- doe
                           (quot doe 1460)
                           (- (quot doe 36524))
                           (quot doe 146096))
                        365))                                 ; [0, 399]
        y   (+ yoe (* era 400))
        doy (- doe (+ (* 365 yoe)
                      (quot yoe 4)
                      (- (quot yoe 100))))                    ; [0, 365]
        mp  (long (quot (+ (* 5 doy) 2) 153))                ; [0, 11]
        d   (+ doy (- (quot (+ (* 153 mp) 2) 5)) 1)          ; [1, 31]
        m   (+ mp (if (< mp 10) 3 -9))                       ; [1, 12]
        y   (+ y (if (<= m 2) 1 0))]
    [y m d]))

(defn weekday
  "Return the day-of-week for (y m d): 0=Sun, 1=Mon, …, 6=Sat.
  Matches the cron dow convention (cron.model/parse :cron/dow)."
  [y m d]
  ;; 1970-01-01 is Thursday. days-from-civil(1970,1,1) = 0.
  ;; Thu in our SUN=0 convention is 4. So: (day# + 4) mod 7.
  (mod (+ (days-from-civil y m d) 4) 7))

;; ---------------------------------------------------------------------------
;; Datetime arithmetic
;; ---------------------------------------------------------------------------

(defn- advance-minute
  "Return the datetime exactly 1 minute after `dt`. Handles all rollovers
  (minute→hour→day→month→year) using days-from-civil / civil-from-days."
  [{:keys [y m d hh mm]}]
  (let [mm1 (inc mm)]
    (if (< mm1 60)
      {:y y :m m :d d :hh hh :mm mm1}
      (let [hh1 (inc hh)]
        (if (< hh1 24)
          {:y y :m m :d d :hh hh1 :mm 0}
          (let [[y2 m2 d2] (civil-from-days (inc (days-from-civil y m d)))]
            {:y y2 :m m2 :d d2 :hh 0 :mm 0}))))))

;; ---------------------------------------------------------------------------
;; Firing logic
;; ---------------------------------------------------------------------------

(defn fires-at?
  "Return true iff `cron` fires at the exact datetime `dt` ({:y :m :d :hh :mm}).

  Day-of-month / day-of-week OR semantics (classic Vixie cron):
  - Both dom-restricted? AND dow-restricted? → fires when dom OR dow matches.
  - Only dom-restricted?                    → dom must match.
  - Only dow-restricted?                    → dow must match.
  - Neither restricted                      → any day matches."
  [cron {:keys [y m d hh mm]}]
  (let [dow        (weekday y m d)
        dom-r?     (:cron/dom-restricted? cron)
        dow-r?     (:cron/dow-restricted? cron)
        day-match? (cond
                     (and dom-r? dow-r?)
                     (or (contains? (:cron/dom cron) d)
                         (contains? (:cron/dow cron) dow))
                     dom-r?
                     (contains? (:cron/dom cron) d)
                     dow-r?
                     (contains? (:cron/dow cron) dow)
                     :else true)]
    (and (contains? (:cron/minute cron) mm)
         (contains? (:cron/hour   cron) hh)
         (contains? (:cron/month  cron) m)
         day-match?)))

;; ---------------------------------------------------------------------------
;; Next-fire search
;; ---------------------------------------------------------------------------

(def ^:private max-steps
  "Bound the search to ~3 years of minutes (1,440 min/day × 365.25 × 3 ≈ 1,576,980)."
  1576980)

(defn next-fire
  "Return the next datetime STRICTLY after `from` at which `cron` fires, or nil
  if no firing occurs within ~3 years (~1,576,980 minutes).

  `from` is a datetime map {:y :m :d :hh :mm}. The returned value has the same shape."
  [cron from]
  (loop [dt    (advance-minute from)
         steps 0]
    (cond
      (>= steps max-steps) nil
      (fires-at? cron dt)  dt
      :else                (recur (advance-minute dt) (inc steps)))))
