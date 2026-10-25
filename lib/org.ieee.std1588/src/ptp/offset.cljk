(ns ptp.offset
  "offsetFromMaster and meanPathDelay from the four two-way exchange
  timestamps, IEEE 1588-2019 clause 11.3 (the delay-request/delay-response
  mechanism).

    t1  Sync originTimestamp,   as measured by the master
    t2  the same Sync,          as received by the slave
    t3  Delay_Req,              as sent by the slave
    t4  the same Delay_Req,     as received by the master

  offsetFromMaster = ((t2 - t1) - (t4 - t3)) / 2
  meanPathDelay     = ((t2 - t1) + (t4 - t3)) / 2

  This is arithmetic on the two *differences*, not on t1..t4 directly. A
  PTP Timestamp's seconds field counts from the 1970-01-01 TAI epoch
  (clause 7.2.3), so turning t1 into a raw nanosecond count before
  subtracting — `t1.seconds * 1e9 + t1.nanoseconds` — already exceeds 1.7e18
  today, nowhere near JavaScript's 2^53 exact-integer ceiling, while
  `t2 - t1` is normally a few hundred microseconds. Every function here
  takes the difference in `{:seconds :nanoseconds}` space first and only
  turns the *difference* into a nanosecond integer, which is what actually
  stays small — the same reason `ptp.timestamp` never materializes a
  correctionField's full ±2^63 range.")

(defn- ts-diff-ns
  "a - b, in nanoseconds, where a and b are `{:seconds :nanoseconds}`.
  Exact as long as the difference itself fits inside 2^53 ns — about 104
  days — true for every legitimate PTP exchange, whose four timestamps are
  at most a few messages apart in real time."
  [a b]
  (+ (* 1000000000 (- (:seconds a) (:seconds b)))
     (- (:nanoseconds a) (:nanoseconds b))))

(defn offset-from-master
  "((t2-t1) - (t4-t3)) / 2, in nanoseconds. Assumes a symmetric path
  (clause 11.2) — this function does not check that assumption, it applies
  the formula the standard defines on top of it. A ratio (Clojure) or float
  (ClojureScript), since the true offset need not be a whole nanosecond."
  [t1 t2 t3 t4]
  (/ (- (ts-diff-ns t2 t1) (ts-diff-ns t4 t3)) 2))

(defn mean-path-delay
  "((t2-t1) + (t4-t3)) / 2, in nanoseconds."
  [t1 t2 t3 t4]
  (/ (+ (ts-diff-ns t2 t1) (ts-diff-ns t4 t3)) 2))
