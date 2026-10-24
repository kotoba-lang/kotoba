(ns afdx.bag
  "Bandwidth Allocation Gap: the minimum time, in milliseconds, an End
  System must leave between two consecutive frames it transmits on the
  same Virtual Link — the mechanism ARINC 664 P7 uses to bound each VL's
  worst-case bandwidth (and, network-wide, to make AFDX's end-to-end
  latency analytically computable, which is the point of a deterministic
  Ethernet profile in the first place).

  This namespace is deliberately pure predicates over caller-supplied
  timestamps — it has no clock, no scheduler, no IO, and does not itself
  transmit anything; a real End System's traffic shaper is out of scope,
  same as `com-aviation-ia-arinc-429` does not implement a bus
  controller.

  Confidence: the allowed BAG value set (`allowed-ms`, powers of two from
  1 to 128 ms) is widely and consistently repeated across public AFDX
  material. The default jitter tolerance (`default-jitter-ms`, 0.5 ms =
  500 microseconds) is also a commonly cited figure in that literature,
  but — same caveat as the rest of this library — neither number has
  been checked against the paid ARINC 664 P7 text itself, and
  `conforms-to-bag?`/`first-violation` take `jitter-ms` as an explicit
  argument rather than hiding the default inside the check.")

(def allowed-ms
  "The BAG values ARINC 664 P7 defines: powers of two, 1..128 ms."
  #{1 2 4 8 16 32 64 128})

(def default-jitter-ms 0.5)

(defn valid-bag-ms?
  [ms]
  (contains? allowed-ms ms))

(defn bag->frames-per-second
  "The maximum sustained frame rate a BAG of `bag-ms` permits."
  [bag-ms]
  (/ 1000.0 bag-ms))

(defn inter-frame-gaps-ms
  "`[t0 t1 t2 ...]` (strictly increasing transmit timestamps, in ms) ->
  `[t1-t0 t2-t1 ...]`, the consecutive gaps. Empty or single-element
  input yields an empty gap vector — there is nothing to check."
  [timestamps-ms]
  (vec (map - (rest timestamps-ms) timestamps-ms)))

(defn first-violation
  "The first consecutive pair in `timestamps-ms` whose gap is smaller
  than `bag-ms` minus `jitter-ms` — i.e. transmitted closer together
  than the BAG allows, even accounting for jitter — as `{:index i :gap
  g :minimum-allowed m}`, or `nil` if every gap conforms."
  [timestamps-ms bag-ms jitter-ms]
  (let [minimum (- bag-ms jitter-ms)
        gaps (inter-frame-gaps-ms timestamps-ms)]
    (first (keep (fn [i] (when (< (nth gaps i) minimum)
                            {:index i :gap (nth gaps i) :minimum-allowed minimum}))
                 (range (count gaps))))))

(defn conforms-to-bag?
  "True when every consecutive gap in `timestamps-ms` is >= `bag-ms` -
  `jitter-ms`. A pure predicate: no side effects, no default jitter."
  [timestamps-ms bag-ms jitter-ms]
  (nil? (first-violation timestamps-ms bag-ms jitter-ms)))
