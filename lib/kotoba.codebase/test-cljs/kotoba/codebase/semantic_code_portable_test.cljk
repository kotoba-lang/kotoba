(ns kotoba.codebase.semantic-code-portable-test
  (:require [kotoba.codebase.semantic-code :as semantic]))

(def expected-cid
  "bafyreidtfrwb5wpqubiti2cwqkgjb5d3daaqoppmnrznunr5qcpk343p3a")

;; Regenerated at VC4 (ADR-kotoba-canonical-value-codec): literals now carry
;; kotoba.value.v1 forms and the contract identity names the codec, so every
;; definition CID moved. The first vector is a SET literal, which is exactly
;; what the unsigned-byte ordering fix changed -- if the sort still leaked the
;; platform's byte signedness, this vector would disagree between the two
;; runtimes rather than merely having moved.
(def parity-vectors
  [{:forms '[(def value #{:a :b :c})]
    :expected {"value" "bafyreifdhxz73mrgsk6bzpdt4dibpsu2hx7zzj65cgkxwtg7u53fcomrkm"}}
   {:forms '[(defn helper [x] (+ x 1)) (defn main [x] (helper x))]
    :expected {"helper" "bafyreidtfrwb5wpqubiti2cwqkgjb5d3daaqoppmnrznunr5qcpk343p3a"
               "main" "bafyreidrkaz6vglwxm7hhrsylxrw6s5jgqzbf52z5k6c3hzgr7f5mwhrza"}}
   {:forms '[(defn even-a [x] (odd-a x)) (defn odd-a [x] (even-a x))]
    :expected {"even-a" "bafyreickb3rmiqruhnyabrvzjznkv2pmib2nnth2ujswyjjz62cmmyaze4"
               "odd-a" "bafyreie2qnf2tuc4vfj6urqivjyhglyfx73k4uxrxs4i3u6gxbrpfhvkxu"}}])

(defn -main []
  (let [a (semantic/compile-definitions '[(defn f [x] (+ x 1))])
        b (semantic/compile-definitions '[(defn renamed [value] (+ value 1))])
        a-cid (-> a :definitions vals first :cid)
        b-cid (-> b :definitions vals first :cid)]
    (when-not (= expected-cid a-cid b-cid)
      (throw (js/Error.
              (str "semantic CID differs across CLJS/JVM or alpha rename: "
                   a-cid " / " b-cid))))
    (doseq [{:keys [forms expected]} parity-vectors]
      (let [actual (into {}
                         (map (fn [[name definition]]
                                [(str name) (:cid definition)]))
                         (:definitions (semantic/compile-definitions forms)))]
        (when-not (= expected actual)
          (throw (js/Error. (str "semantic parity vector mismatch: "
                                 expected " / " actual))))))
    (println "semantic CLJS/JVM CID parity:" a-cid
             "(" (count parity-vectors) "adversarial vectors)")))

(set! *main-cli-fn* -main)
