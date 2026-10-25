(ns kotoba.fabbers.stl-test
  (:require [clojure.test :refer [deftest is]] [kotoba.fabbers.stl :as stl]))

(def sample "solid wedge facet normal 0 0 1 outer loop vertex 0 0 0 vertex 1 0 0 vertex 0 1 0 endloop endfacet endsolid wedge")

(deftest ascii-intake
  (let [report (stl/inspect sample)]
    (is (:stl/ok? report))
    (is (= :ascii (:stl/format report)))
    (is (= 1 (get-in report [:stl/summary :facet-count])))
    (is (= [0.0 0.0 0.0] (get-in report [:stl/summary :bounds :min])))
    (is (= 0.5 (get-in report [:stl/summary :surface-area])))))

(deftest rejects-broken-facet
  (is (= :stl/facet-arity (:stl/error (stl/inspect "solid x facet normal 0 0 1 vertex 0 0 0 endfacet")))))
