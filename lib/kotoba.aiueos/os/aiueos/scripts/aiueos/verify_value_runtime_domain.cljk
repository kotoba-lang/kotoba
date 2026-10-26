(ns aiueos.verify-value-runtime-domain
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]))

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-runtime-domain))))

(defn -main [& [source-path contract-path]]
  (when-not (and source-path contract-path)
    (fail! "usage: <source> <contract>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        result (compiler/compile-project
                {'aiueos.value-runtime-domain (slurp source-path)}
                'aiueos.value-runtime-domain :x86_64-aiueos-kernel-v1)
        code (get-in result [:artifact :code])
        store [0x45 0x89 0x91 0x10 0x01 0x00 0x00]]
    (when-not (= 272 (get-in contract [:publication :destination :offset]))
      (fail! "contract context offset drift" {}))
    (when-not (some #{store} (partition (count store) 1 code))
      (fail! "native image lacks current-domain publication store" {}))
    (when-not (empty? (get-in result [:binary :imports]))
      (fail! "domain publisher imports foreign code"
             {:imports (get-in result [:binary :imports])}))
    (println (pr-str {:format :aiueos.value-runtime-domain/verification-v1
                      :context-offset 272 :imports [] :foreign-code false
                      :status :passed}))))
