(ns kotoba.package-registry-test
  "Launcher-side package registry resolve + admission."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.test :refer [deftest is]]
            [kotoba.lang.package-registry :as package-registry]
            [kotoba.package-admission :as package-admission]))

(def example-registry
  (edn/read-string
   (slurp (io/resource "kotoba/lang/package-registry/example-registry.edn"))))

(deftest registry-resolve-then-admit
  (let [result (package-admission/resolve-lock-with-registry
                {:registry example-registry
                 :requests [{:name "kotoba-lang/json"
                             :version "0.1.0"
                             :capabilities [:graph-read]}]
                 :trust {:declared-capabilities [:graph-read]}})]
    (is (true? (:kotoba.admission/ok? result))
        (str result))
    (is (= :package-verified (:kotoba.admission/code result)))
    (is (true? (get-in result [:kotoba.admission/receipt :kotoba.package/verified?])))
    (is (= 1 (count (get-in result [:kotoba.admission/lock :deps]))))))

(deftest registry-missing-package-fails-closed
  (let [result (package-admission/resolve-lock-with-registry
                {:registry example-registry
                 :requests [{:name "nope/missing" :version "0.0.1"}]
                 :trust {:declared-capabilities []}})]
    (is (false? (:kotoba.admission/ok? result)))
    (is (= :package/registry-resolve-failed (:kotoba.admission/code result)))))

(deftest version-only-is-not-directly-admissible
  (is (true? (package-registry/version-only-request?
              {:dep/name "kotoba-lang/json" :dep/version "0.1.0"})))
  (let [receipt (package-admission/verify-lock
                 {:lock {:kotoba.lock/version 1
                         :deps [{:dep/name "kotoba-lang/json"
                                 :dep/version "0.1.0"}]}
                  :trust {:declared-capabilities [:graph-read]}})]
    (is (false? (:kotoba.package/verified? receipt))
        "name+version alone must not pass admission without registry resolve")))
