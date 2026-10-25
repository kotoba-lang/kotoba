(ns srs.time
  "Proleptic Gregorian civil-date arithmetic on epoch milliseconds, in pure
  portable integer math.

  Why hand-rolled rather than `java.time`: a registration term is a *calendar*
  term. A domain created 2024-02-29 for one year expires 2025-02-28, not
  2025-02-28T‌…-plus-drift, and a domain created 2024-01-31 for one month is
  not 2024-03-02. Approximating a year as 365 days puts the expiry date on the
  wrong day for every domain whose term spans a leap day — which after ten
  years is most of them. So the arithmetic has to be real, and it has to run
  everywhere this library runs (`java.time` is JVM-only; `js/Date` is CLJS-only
  and does local-timezone arithmetic unless you are careful), so it is written
  once here in integer math that has no host at all.

  The algorithm is Howard Hinnant's `days_from_civil` / `civil_from_days`
  (http://howardhinnant.github.io/date_algorithms.html), which is exact for the
  proleptic Gregorian calendar over the whole range we care about. It shifts
  the year to start in March so the leap day lands at the end of the cycle and
  falls out of the integer division.

  Everything here is UTC. Registry dates are UTC by definition (RFC 5731 uses
  `dateTime` values and every registry publishes in Z), and introducing a local
  zone would make the same domain expire on different days for different
  operators."
  (:require [kotoba.lang.text :as str])
  (:refer-clojure :exclude [second]))

(def ^:const ms-per-second 1000)
(def ^:const ms-per-minute (* 60 ms-per-second))
(def ^:const ms-per-hour (* 60 ms-per-minute))
(def ^:const ms-per-day (* 24 ms-per-hour))

(defn- floor-div
  "Integer division rounding toward negative infinity. `quot` truncates toward
  zero, which is wrong for pre-1970 instants — and a registry does carry them
  (a `crDate` imported from a legacy registry, a test fixture at the epoch
  boundary). Getting this wrong shifts exactly the dates nobody tests."
  [a b]
  (let [q (quot a b)]
    (if (and (neg? (bit-xor a b)) (not= (* q b) a)) (dec q) q)))

(defn- floor-mod [a b] (- a (* b (floor-div a b))))

(defn days-from-civil
  "Days since 1970-01-01 for a proleptic Gregorian y-m-d. `m` is 1-12."
  [y m d]
  (let [y (if (<= m 2) (dec y) y)
        era (floor-div (if (>= y 0) y (- y 399)) 400)
        yoe (- y (* era 400))                                  ; [0, 399]
        doy (+ (floor-div (+ (* 153 (+ m (if (> m 2) -3 9))) 2) 5) (dec d))
        doe (+ (* yoe 365) (floor-div yoe 4) (- (floor-div yoe 100)) doy)]
    (+ (* era 146097) doe -719468)))

(defn civil-from-days
  "Inverse of `days-from-civil`: days since 1970-01-01 → `[y m d]`."
  [z]
  (let [z (+ z 719468)
        era (floor-div (if (>= z 0) z (- z 146096)) 146097)
        doe (- z (* era 146097))                               ; [0, 146096]
        yoe (floor-div (- doe (floor-div doe 1460) (- (floor-div doe 36524))
                          (floor-div doe 146096))
                       365)                                     ; [0, 399]
        y (+ yoe (* era 400))
        doy (- doe (+ (* 365 yoe) (floor-div yoe 4) (- (floor-div yoe 100))))
        mp (floor-div (+ (* 5 doy) 2) 153)                      ; [0, 11]
        d (inc (- doy (floor-div (+ (* 153 mp) 2) 5)))
        m (+ mp (if (< mp 10) 3 -9))]
    [(if (<= m 2) (inc y) y) m d]))

(defn leap-year? [y]
  (and (zero? (mod y 4)) (or (not (zero? (mod y 100))) (zero? (mod y 400)))))

(def ^:private month-lengths [31 28 31 30 31 30 31 31 30 31 30 31])

(defn days-in-month [y m]
  (if (and (= m 2) (leap-year? y)) 29 (nth month-lengths (dec m))))

(defn ms->civil
  "Epoch ms → `{:year :month :day :ms-of-day}` in UTC."
  [ms]
  (let [d (floor-div ms ms-per-day)
        [y m dd] (civil-from-days d)]
    {:year y :month m :day dd :ms-of-day (floor-mod ms ms-per-day)}))

(defn civil->ms
  "`{:year :month :day :ms-of-day}` in UTC → epoch ms."
  [{:keys [year month day ms-of-day]}]
  (+ (* (days-from-civil year month day) ms-per-day) (or ms-of-day 0)))

(defn plus-days [ms n] (+ ms (* n ms-per-day)))

(defn same-day?
  "Do two instants fall on the same UTC calendar day? Protocol fields that are
  `xs:date` rather than `xs:dateTime` — EPP's `curExpDate` is the one that
  matters — have to be compared this way. Comparing them as instants rejects
  every valid value whose counterpart is not exactly midnight."
  [a b]
  (and (some? a) (some? b) (= (floor-div a ms-per-day) (floor-div b ms-per-day))))

(defn plus-years
  "Anniversary arithmetic: the same month and day, `n` years later, preserving
  the time of day.

  Feb 29 has no anniversary in a common year. Registry practice (and every
  major registry's actual behaviour) is to clamp to Feb 28 rather than roll
  forward to Mar 1 — rolling forward would move the domain into a later month
  and, compounded over a 10-year term, silently gift a day. `days-in-month`
  makes the clamp explicit instead of letting it fall out of a normalization
  nobody reads."
  [ms n]
  (let [{:keys [year month day ms-of-day]} (ms->civil ms)
        y' (+ year n)
        d' (min day (days-in-month y' month))]
    (civil->ms {:year y' :month month :day d' :ms-of-day ms-of-day})))

(defn iso8601
  "UTC instant as an XML Schema `dateTime` — the form EPP puts on the wire
  (RFC 5731 uses `xs:dateTime`) and RDAP puts in JSON (RFC 9083 §3 requires
  RFC 3339). Always `Z`, always second precision, since neither protocol
  carries anything finer and emitting milliseconds makes responses that differ
  byte-for-byte between hosts for the same instant."
  [ms]
  (let [{:keys [year month day ms-of-day]} (ms->civil ms)
        s (floor-div ms-of-day ms-per-second)
        pad (fn [n w] (let [s (str n)]
                        (str (apply str (repeat (max 0 (- w (count s))) "0")) s)))]
    (str (pad year 4) "-" (pad month 2) "-" (pad day 2) "T"
         (pad (floor-div s 3600) 2) ":"
         (pad (floor-mod (floor-div s 60) 60) 2) ":"
         (pad (floor-mod s 60) 2) "Z")))

(defn date-only
  "An `xs:date` — the form EPP uses for `curExpDate` (RFC 5731 §3.2.3) and for
  the `exDate` it echoes back."
  [ms]
  (subs (iso8601 ms) 0 10))

(defn parse-date
  "Parse an `xs:date` (`YYYY-MM-DD`) to the epoch ms of its UTC midnight.
  Separate from `parse-iso8601` because the two are different types on the
  wire, and accepting a bare date where a dateTime was required would let a
  caller silently lose the time of day."
  [s]
  (when (string? s)
    (when-let [[_ y m d] (re-matches #"(\d{4})-(\d{2})-(\d{2})" (str/trim s))]
      (let [n #?(:clj #(Long/parseLong %) :cljs #(js/parseInt % 10))]
        (* (days-from-civil (n y) (n m) (n d)) ms-per-day)))))

(defn parse-iso8601
  "Parse the `xs:dateTime`/RFC 3339 subset EPP and RDAP actually emit —
  `YYYY-MM-DDThh:mm:ss` with an optional fractional part and an optional
  offset. Returns epoch ms, or nil if the shape does not match.

  Deliberately not a general RFC 3339 parser: accepting more than the protocols
  emit would mean silently accepting a date this library cannot round-trip."
  [s]
  (when (string? s)
    (let [m (re-matches
             #"(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(?:[Zz]|([+-])(\d{2}):(\d{2}))?"
             s)]
      (when m
        (let [[_ y mo d h mi se frac sign oh om] m
              n #?(:clj #(Long/parseLong %) :cljs #(js/parseInt % 10))
              frac-ms (if frac
                        (let [f (subs (str frac "000") 0 3)] (n f))
                        0)
              base (+ (* (days-from-civil (n y) (n mo) (n d)) ms-per-day)
                      (* (n h) ms-per-hour) (* (n mi) ms-per-minute)
                      (* (n se) ms-per-second) frac-ms)
              offset (if sign
                       (* (if (= sign "-") -1 1)
                          (+ (* (n oh) ms-per-hour) (* (n om) ms-per-minute)))
                       0)]
          (- base offset))))))
