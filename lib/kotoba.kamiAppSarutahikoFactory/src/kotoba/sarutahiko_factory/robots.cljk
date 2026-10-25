(ns kotoba.sarutahiko-factory.robots
  "Construction-robot roster — ported from `scene.rs`'s `Robots` / `Robot`
  and the `get` lookup method.

  A `robots` value is a plain EDN map:

    :robots/robots  [{:robot/id :robot/name :robot/kind :robot/reach-m
                       :robot/base [x y] :robot/cycle-min :robot/mobile?
                       :robot/process :robot/maturity} ...]

  Pure: no I/O. See `kotoba.sarutahiko-factory.fixtures/robots` for this
  repo's synthetic test fixture."
  )

(defn all [robots] (:robots/robots robots))

(defn ids
  "The set of every robot id in the roster."
  [robots]
  (into #{} (map :robot/id) (all robots)))

(defn by-id
  "Look up a robot by id. `nil` if unknown."
  [robots id]
  (first (filter #(= id (:robot/id %)) (all robots))))

(defn mobile
  "Robots flagged `:robot/mobile? true`."
  [robots]
  (filter :robot/mobile? (all robots)))

(defn by-process
  "Robots whose `:robot/process` matches `process`."
  [robots process]
  (filter #(= process (:robot/process %)) (all robots)))
