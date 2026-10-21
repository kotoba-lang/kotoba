(ns kotoba.lang.time
  "Instant / Duration for the kotoba foundational stdlib. Layer 3 (I/O).

  An instant is epoch-milliseconds wrapped in a map. A duration is a count of
  milliseconds. All arithmetic and comparison is pure. Wall-clock comes from a
  HOST-INJECTED `clock` capability: `(now clock)` calls `(clock)` for the
  current epoch-millis. The library never reads the OS clock itself — a
  capability-confined kotoba cell receives time only if the host granted a clock.

  UTC-only ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) is provided for wire formats; no
  timezone database, to keep the lib portable and dependency-free.

  Zero third-party runtime deps; .cljc (JVM / SCI / CLJS / GraalVM / kotoba-WASM)."
  (:refer-clojure :exclude [second]))

(def ^:private msecs-per-second 1000)
(def ^:private msecs-per-minute (* 60 msecs-per-second))
(def ^:private msecs-per-hour   (* 60 msecs-per-minute))
(def ^:private msecs-per-day    (* 24 msecs-per-hour))

;; ---------- constructors ----------

(defn instant
  "Construct an instant from epoch-milliseconds."
  [ms]
  {:time/instant (long ms)})

(defn duration
  "Construct a duration from a count of milliseconds."
  [ms]
  {:time/duration (long ms)})

(defn millis     [n] (duration n))
(defn seconds    [n] (duration (* n msecs-per-second)))
(defn minutes    [n] (duration (* n msecs-per-minute)))
(defn hours      [n] (duration (* n msecs-per-hour)))
(defn days       [n] (duration (* n msecs-per-day)))

;; ---------- accessors / arithmetic ----------

(defn instant-millis [i] (:time/instant i))
(defn duration-millis [d] (:time/duration d 0))

(defn add
  "Add a duration to an instant (or two durations). Returns the same shape."
  [a b]
  (cond
    (and (:time/instant a) (:time/duration b)) (instant (+ (:time/instant a) (:time/duration b)))
    (and (:time/duration a) (:time/duration b)) (duration (+ (:time/duration a) (:time/duration b)))
    (and (:time/instant a) (:time/instant b))  (instant (+ (:time/instant a) (:time/instant b)))
    :else (throw (ex-info "time/add: incompatible operands" {:a a :b b}))))

(defn sub
  "Subtract b from a. Instant - duration -> instant; instant - instant -> duration."
  [a b]
  (cond
    (and (:time/instant a) (:time/duration b)) (instant (- (:time/instant a) (:time/duration b)))
    (and (:time/instant a) (:time/instant b))  (duration (- (:time/instant a) (:time/instant b)))
    (and (:time/duration a) (:time/duration b)) (duration (- (:time/duration a) (:time/duration b)))
    :else (throw (ex-info "time/sub: incompatible operands" {:a a :b b}))))

(defn before? [a b] (< (:time/instant a) (:time/instant b)))
(defn after?  [a b] (> (:time/instant a) (:time/instant b)))

(defn between
  "Duration between two instants (a - b)."
  [a b] (sub a b))

;; ---------- host-injected clock ----------

(defn now
  "Return the current instant using a HOST-INJECTED `clock` fn. `(clock)` must
  return epoch-millis. Without a clock capability, a cell has no time —
  deny-by-default."
  [clock]
  (instant (clock)))

;; ---------- UTC ISO-8601 (portable, no tz) ----------

(defn- pad2 [n] (let [s (str n)] (if (< (count s) 2) (str "0" s) s)))
(defn- pad4 [n] (let [s (str n)] (str (apply str (repeat (- 4 (count s)) \0)) s)))

(defn- ->ymd
  "Inverse civil-from-days (Howard Hinnant's algorithm). `days-since-epoch`
  (1970-01-01 == 0) → [year month day], all 1-based. Pure integer math, no
  Date/Calendar, so it runs on kotoba-WASM."
  [days-since-epoch]
  (let [z   (+ days-since-epoch 719468)
        era (if (pos? z) (quot z 146097) (quot (dec z) 146097))
        doe (- z (* era 146097))                         ; [0, 146096]
        yoe (quot (+ doe (- (quot doe 1460)) (quot doe 36524) (- (quot doe 146096))) 365) ; [0, 399]
        y   (+ (* era 400) yoe)
        doy (- doe (* 365 yoe) (quot yoe 4) (- (quot yoe 100)))       ; [0, 365]
        mp  (quot (+ (* 5 doy) 2) 153)                   ; [0, 11]
        d   (+ (- doy (quot (+ (* 153 mp) 2) 5)) 1)     ; [1, 31]
        m   (if (< mp 10) (+ mp 3) (- mp 9))            ; [1, 12]
        y   (if (<= m 2) (inc y) y)]
    [y m d]))

(defn- floor-div
  "Integer division that floors toward negative infinity (unlike `quot`,
  which truncates toward zero) -- consistent with `mod`, which Clojure
  already defines as floored (result always has the sign of `b`). Derived
  from that floored `mod` so the two never disagree: `a = b*floor-div +
  floor-mod` exactly, with no separate rounding rule to drift out of sync."
  [a b]
  (quot (- a (mod a b)) b))

(defn ->iso8601
  "Format an instant as UTC `YYYY-MM-DDTHH:MM:SSZ`. No fractional seconds."
  [i]
  (let [ms    (:time/instant i)
        secs  (floor-div ms 1000)
        day   (floor-div secs 86400)
        rem-s (mod secs 86400)
        hour  (quot rem-s 3600)
        min   (quot (mod rem-s 3600) 60)
        sec   (mod rem-s 60)
        [y mo d] (->ymd day)]
    (str (pad4 y) "-" (pad2 mo) "-" (pad2 d) "T"
         (pad2 hour) ":" (pad2 min) ":" (pad2 sec) "Z")))

(defn iso8601->instant
  "Parse a UTC `YYYY-MM-DDTHH:MM:SSZ` (or with fractional/.ms) string into an
  instant. Throws on malformed input."
  [^String s]
  (let [n (count s)]
    (when (< n 20)
      (throw (ex-info "time/iso8601->instant: too short" {:input s})))
    (let [parse-int (fn [start len]
                      (try
        #?(:clj  (Long/parseLong (subs s start (+ start len)))
           :cljs (js/parseInt (subs s start (+ start len)) 10))
        (catch #?(:clj Throwable :cljs :default) _
          (throw (ex-info "time/iso8601->instant: bad number" {:input s})))))
          y (parse-int 0 4)
          mo (parse-int 5 2)
          d (parse-int 8 2)
          h (parse-int 11 2)
          mi(parse-int 14 2)
          se(parse-int 17 2)]
      (when (not= (.charAt s 4) \-)
        (throw (ex-info "time/iso8601->instant: expected - at 4" {:input s})))
      (when (not= (.charAt s 7) \-)
        (throw (ex-info "time/iso8601->instant: expected - at 7" {:input s})))
      (when (not= (.charAt s 10) \T)
        (throw (ex-info "time/iso8601->instant: expected T at 10" {:input s})))
      (when (not= (.charAt s 13) \:)
        (throw (ex-info "time/iso8601->instant: expected : at 13" {:input s})))
      (when (not= (.charAt s 16) \:)
        (throw (ex-info "time/iso8601->instant: expected : at 16" {:input s})))
      ;; days from civil (Hinnant), then to epoch-millis
      (let [y2  (if (<= mo 2) (dec y) y)
            era (if (neg? y2) (quot (- y2 399) 400) (quot y2 400))
            yoe (- y2 (* era 400))
            m2  (if (> mo 2) (- mo 3) (+ mo 9))
            doy (+ (quot (+ (* 153 m2) 2) 5) d -1)
            doe (+ (* yoe 365) (quot yoe 4) (- (quot yoe 100)) doy)
            days (+ (* era 146097) doe -719468)
            secs (+ (* days 86400) (* h 3600) (* mi 60) se)]
        (instant (* secs 1000))))))
