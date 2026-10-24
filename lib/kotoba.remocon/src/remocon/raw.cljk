(ns remocon.raw
  "Raw IR burst model: the microsecond mark/space time series one IR signal is.

  A burst is a sequence of [:mark n] / [:space n] pairs, in the order the IR
  receiver saw them (mark = carrier present, space = carrier absent). The
  convention is `remocon.raw`'s only authority; converters to and from other
  representations (Pronto hex, protocol frames) live in sibling namespaces.

  Invariants (all fail closed):
  - a burst always starts with a :mark and ends with a :space
  - marks and spaces strictly alternate
  - durations are positive integers (microseconds)
  - :trailing markers carry no time and never appear alone")

(defn burst?
  "True when `xs` satisfies the mark/space alternating-burst invariant."
  [xs]
  (boolean
   (and (sequential? xs)
        (pos? (count xs))
        (even? (count xs))
        (every? #(and (vector? %)
                      (= 2 (count %))
                      (#{:mark :space} (first %))
                      (pos? (second %))
                      (integer? (second %)))
                xs)
        (every? (fn [[a b]]
                  (and (= :mark (first a)) (= :space (first b))))
                (partition 2 xs))
        (= :mark (first (first xs)))
        (= :space (first (last xs))))))

(defn burst-error
  "Human-readable reason `xs` is not a valid burst, or nil when it is."
  [xs]
  (cond
    (not (sequential? xs)) "not sequential"
    (empty? xs) "empty burst"
    (odd? (count xs)) "burst must end with a :space (even pair count)"
    :else (or (some (fn [[a b]]
                      (cond
                        (not (and (vector? a) (vector? b))) "non-pair element"
                        (not= :mark (first a)) "burst must start with :mark"
                        (not= :space (first b)) "marks and spaces must alternate"
                        (not (pos? (second a))) "mark duration must be positive"
                        (not (pos? (second b))) "space duration must be positive"))
                    (partition 2 xs))
              (when-not (and (vector? (first xs)) (= :mark (first (first xs))))
                "burst must start with :mark")
              (when-not (and (vector? (last xs)) (= :space (first (last xs))))
                "burst must end with :space"))))

(defn assert-burst!
  "Returns `xs` when it is a valid burst, else throws with the reason."
  [xs]
  (if (burst? xs)
    xs
    (throw (ex-info (str "invalid IR burst: " (burst-error xs))
                    {:reason (burst-error xs)}))))

(defn burst-duration-us
  "Total time of the burst in microseconds (sum of all segments)."
  [xs]
  (reduce + 0 (map second xs)))

(defn mark-spaces
  "Flat [mark-us space-us mark-us space-us ...] vector."
  [xs]
  (mapv second xs))

(defn burst-from-flat
  "Inverse of `mark-spaces`: [m s m s ...] -> burst."
  [flat]
  (->> flat
       (partition 2)
       (mapv (fn [[m s]] [[:mark m] [:space s]]))
       (apply concat)
       vec))

(defn truncate-suffix
  "Drop a final gap (the last :space) plus any extra trailing pairs whose
  durations exceed `max-us` each — receivers commonly append a long silence.
  Returns a burst (still :mark-first / :space-last)."
  [xs max-us]
  (let [pairs (partition 2 xs)
        pairs (if (and (seq pairs)
                       (> (second (last (last pairs))) max-us))
                (butlast pairs)
                pairs)]
    (vec (apply concat (mapv (fn [[m s]] [m s]) pairs)))))
