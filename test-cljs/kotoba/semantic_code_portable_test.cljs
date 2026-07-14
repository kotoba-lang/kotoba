(ns kotoba.semantic-code-portable-test
  (:require [kotoba.semantic-code :as semantic]))

(def expected-cid
  "bafyreif5gkfsoabjcqgqwi3v7iordffqeidrswat3u4yfjcvydtn2u7cz4")

(def parity-vectors
  [{:forms '[(def value #{:a :b :c})]
    :expected {"value" "bafyreiblbefroocpif7wtm3ak7fyhhqehjquwzvcpfgvjsrihpv5usqmra"}}
   {:forms '[(defn helper [x] (+ x 1)) (defn main [x] (helper x))]
    :expected {"helper" "bafyreif5gkfsoabjcqgqwi3v7iordffqeidrswat3u4yfjcvydtn2u7cz4"
               "main" "bafyreihoa23b2wpgnxw4phqcivz5agnllgct2cvyqkd4wycwyeyoeoikz4"}}
   {:forms '[(defn even-a [x] (odd-a x)) (defn odd-a [x] (even-a x))]
    :expected {"even-a" "bafyreidzwuhmcogikksjcnr2rplgurwdn2dnx273faypworu5kdklvlmue"
               "odd-a" "bafyreifaw52gyls5dxo6octce3ca7srfxeynwycjyanujwqwnclj5evweq"}}])

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
