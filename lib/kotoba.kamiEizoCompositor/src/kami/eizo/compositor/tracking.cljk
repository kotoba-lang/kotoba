(ns kami.eizo.compositor.tracking
  "2D point-tracking data model: a track is an ordered series of
  {:frame :x :y :confidence} samples. `position-at` interpolates a
  tracked position at an arbitrary frame between samples (linear
  interpolation in v0 — documented, not spline/kalman-smoothed).")

(defn make-track
  "Constructs a track from a sequence of samples, sorted by :frame.
  Returns nil if samples is empty or has duplicate frames (ambiguous)."
  [samples]
  (let [sorted (vec (sort-by :frame samples))]
    (when (and (seq sorted)
               (= (count sorted) (count (distinct (map :frame sorted)))))
      sorted)))

(defn position-at
  "Interpolates [x y] at `frame`. Exact match returns that sample's
  position. Before the first sample or after the last, clamps to the
  nearest endpoint (holds the edge value rather than extrapolating).
  Between two samples, linearly interpolates x/y (confidence is not
  interpolated — returns the confidence of the earlier sample, since
  confidence is a discrete per-sample quality signal, not a
  continuous quantity)."
  [track frame]
  (let [n (count track)]
    (cond
      (zero? n) nil
      (<= frame (:frame (first track))) (let [{:keys [x y]} (first track)] [x y])
      (>= frame (:frame (last track))) (let [{:keys [x y]} (last track)] [x y])
      :else
      (loop [i 0]
        (let [a (nth track i)
              b (nth track (inc i))]
          (cond
            (= frame (:frame a)) [(:x a) (:y a)]
            (and (< (:frame a) frame) (< frame (:frame b)))
            (let [t (/ (double (- frame (:frame a))) (- (:frame b) (:frame a)))]
              [(+ (:x a) (* t (- (:x b) (:x a))))
               (+ (:y a) (* t (- (:y b) (:y a))))])
            :else (recur (inc i))))))))
