(ns kotoba.nyc-runtime-test
  (:require [cljs.test :refer [deftest is]]
            [kotoba.property.nyc-runtime :as nyc]))

(deftest normalizes-public-agency-records
  (let [claim (nyc/normalize-record "2026-07-10T00:00:00.000Z"
                                    {:bbl "1017900009.0" :agency "HPD"})]
    (is (= "nyc-owned-properties:1017900009.0" (:ownership/id claim)))
    (is (= :public-body (:ownership/holder-kind claim)))))
