(ns kotoba.type-contract-adapter-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime]))

(def source
  "(ns type-contract-demo)
   (defn ^{:signature {:params [[:cap :host/ledger-append \"ledger:main\"]]
                       :returns :i64
                       :effects #{:host/ledger-append}}}
     main
     [^{:cap :host/ledger-append} cap]
     (host-i64-roundtrip-with cap (i64 41)))")

(def policy
  {:kotoba.policy/capabilities #{:ledger/append}})

(defn checked []
  (runtime/check (launcher/safe-analyzer-fact-classification)
                 {:kotoba.source/path "<type-contract-test>"
                  :kotoba.source/reader-target :kotoba}
                 (runtime/read-forms source :kotoba)
                 policy))

(deftest annotation-is-never-silently-ignored
  (let [result (checked)
        validator-present? (some? (try
                                    (requiring-resolve 'kotoba.lang.type-system/validate-forms)
                                    (catch java.io.FileNotFoundException _ nil)))]
    (testing "workspace development resolves the M2 authority; an older
              released pin must fail closed instead"
      (if validator-present?
        (is (:kotoba.runtime/ok? result))
        (is (= :type-contract-unavailable
               (:kotoba.runtime/problem
                (first (:kotoba.runtime/problems result)))))))))

(deftest region-escape-is-rejected-when-m2-authority-is-present
  (when (try
          (requiring-resolve 'kotoba.lang.type-system/validate-forms)
          (catch java.io.FileNotFoundException _ nil))
    (let [result (runtime/check
                  (launcher/safe-analyzer-fact-classification)
                  {:kotoba.source/path "<region-escape-test>"
                   :kotoba.source/reader-target :kotoba}
                  (runtime/read-forms
                   "(defn ^{:signature {:params [[:region r]] :returns [:region-ref r :i32] :effects #{}}} bad [r] 0)"
                   :kotoba)
                  policy)]
      (is (false? (:kotoba.runtime/ok? result)))
      (is (some #(= :region/escape
                    (get-in % [:kotoba.runtime/detail :problem]))
                (:kotoba.runtime/problems result))))))
