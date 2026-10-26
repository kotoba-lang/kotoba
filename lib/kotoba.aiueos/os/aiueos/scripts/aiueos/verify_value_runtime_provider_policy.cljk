(ns aiueos.verify-value-runtime-provider-policy
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]))

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-runtime-provider-policy))))

(defn- handle [slot generation rights]
  (+ slot (* generation 65536) (* 2 4294967296)
     (* rights 281474976710656)))

(defn- model [{:keys [generation active?]} [action slot table-generation rights owner]]
  (if (and (= action 1) active? (<= 1 generation 65535)
           (contains? #{1 4 5} rights) (<= 1 slot 255)
           (<= 1 owner 32767) (= table-generation 0))
    (handle slot 1 rights)
    0))

(defn -main [& [table-source policy-source contract-path]]
  (when-not (and table-source policy-source contract-path)
    (fail! "usage: <table-source> <policy-source> <contract>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        result (compiler/compile-project
                {'aiueos.value-runtime-capability-table (slurp table-source)
                 'aiueos.value-runtime-provider-policy (slurp policy-source)}
                'aiueos.value-runtime-provider-policy
                :x86_64-aiueos-kernel-v1)
        code (get-in result [:artifact :code])
        exports (get-in result [:artifact :exports])]
    (doseq [{:keys [name status grant expected]} (:vectors contract)]
      (let [actual (model status grant)]
        (when-not (= expected actual)
          (fail! "provider policy vector mismatch"
                 {:vector name :expected expected :actual actual}))))
    (doseq [name ['aiueos-value-runtime-provider-status
                  'aiueos-value-runtime-capability-grant]]
      (when-not (contains? exports name)
        (fail! "provider policy export absent" {:export name})))
    (doseq [[label opcode] [[:publish (get-in contract [:native :publish-opcode])]
                            [:read (get-in contract [:native :read-opcode])]]]
      (when-not (some #{opcode} (partition (count opcode) 1 code))
        (fail! "provider status mechanism absent" {:operation label})))
    (when-not (empty? (get-in result [:object :imports]))
      (fail! "provider policy imports foreign code"
             {:imports (get-in result [:object :imports])}))
    (println (pr-str {:format :aiueos.value-runtime-provider-policy/verification-v1
                      :vectors (count (:vectors contract)) :imports []
                      :foreign-code false :status :passed}))))
