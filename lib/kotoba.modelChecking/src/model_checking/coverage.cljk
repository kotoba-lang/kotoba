(ns model-checking.coverage
  "Coverage collection and reporting (line/toggle/branch/condition/FSM/
  functional) with cross-bin support. Restored from kami-verify's
  `coverage` module (deleted PR #82).")

(def coverage-types #{:line :toggle :branch :condition :fsm :functional})

(defn coverage-point [name cov-type hit hit-count]
  {:name name :cov-type cov-type :hit hit :hit-count hit-count})

(defn cross-bin [name dimensions hit] {:name name :dimensions dimensions :hit hit})

(defn coverage-group [name points cross-bins] {:name name :points (vec points) :cross-bins (vec cross-bins)})

(defn coverage-report [groups] {:groups (vec groups)})

(defn total-coverage
  "Overall coverage percentage (0.0-100.0) across all points and cross
  bins. 100.0 if there are none."
  [report]
  (let [items (mapcat (fn [g] (concat (:points g) (:cross-bins g))) (:groups report))
        total (count items)
        hit (count (filter :hit items))]
    (if (zero? total) 100.0 (* (/ (double hit) total) 100.0))))

(defn coverage-by-type
  "Coverage percentage for `cov-type` (points only, cross bins excluded).
  100.0 if there are no points of that type."
  [report cov-type]
  (let [points (filter #(= (:cov-type %) cov-type) (mapcat :points (:groups report)))
        total (count points)
        hit (count (filter :hit points))]
    (if (zero? total) 100.0 (* (/ (double hit) total) 100.0))))

(defn uncovered-points
  "All coverage points across all groups that are not hit."
  [report]
  (vec (remove :hit (mapcat :points (:groups report)))))
