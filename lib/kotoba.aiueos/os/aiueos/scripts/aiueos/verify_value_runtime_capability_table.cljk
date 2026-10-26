(ns aiueos.verify-value-runtime-capability-table
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]))

(defn- fail! [message data]
  (throw (ex-info message
                  (assoc data :phase :aiueos-value-runtime-capability-table))))

(defn- handle [slot generation rights]
  (+ slot (* generation 65536) (* 2 4294967296)
     (* rights 281474976710656)))

(defn- step [state [action slot expected grant owner]]
  (let [state (merge {:generation 0 :active? false :rights 0 :owner 0
                      :type 0 :lock 0} state)
        rights (bit-and grant 65535)
        provider-generation (bit-and (quot grant 65536) 65535)]
    (if (not= 0 (:lock state))
      [state 0]
      (case action
        1 (if (and (<= 1 slot 255) (not (:active? state))
                   (= expected (:generation state))
                   (<= 1 rights 7) (pos? provider-generation)
                   (<= 1 owner 32767))
            (let [generation (if (= 65535 expected) 1 (inc expected))]
              [(assoc state :generation generation :active? true
                      :rights rights :owner owner :type 2
                      :provider-generation provider-generation)
               (handle slot generation rights)])
            [state 0])
        2 (if (and (<= 1 slot 255) (:active? state)
                   (= expected (:generation state)) (= 2 (:type state))
                   (zero? grant) (= owner (:owner state)))
            [(assoc state :active? false :rights 0 :owner 0 :type 0) 1]
            [state 0])
        [state 0]))))

(defn- verify-vectors! [vectors]
  (reduce +
          (for [{:keys [name initial steps]} vectors]
            (do (reduce (fn [state {:keys [args expected]}]
                          (let [[next-state actual] (step state args)]
                            (when-not (= expected actual)
                              (fail! "semantic vector mismatch"
                                     {:vector name :args args
                                      :expected expected :actual actual}))
                            next-state))
                        initial steps)
                (count steps)))))

(defn -main [& [source-path contract-path]]
  (when-not (and source-path contract-path)
    (fail! "usage: <source> <contract>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        result (compiler/compile-source (slurp source-path)
                                        :x86_64-aiueos-kernel-v1)
        object (:object result)
        code (get-in result [:artifact :code])
        atomic (get-in contract [:native :atomic-opcode])
        private-table [0x4d 0x8d 0x91 0x00 0x10 0x00 0x00]
        vectors (verify-vectors! (:vectors contract))]
    (when-not (= (get-in contract [:native :export]) (:export object))
      (fail! "native export mismatch" {:actual (:export object)}))
    (when-not (empty? (:imports object))
      (fail! "capability mutator imports foreign code" {:imports (:imports object)}))
    (doseq [[label opcode] [[:private-table private-table] [:atomic-lock atomic]]]
      (when-not (some #{opcode} (partition (count opcode) 1 code))
        (fail! "native capability mechanism is absent"
               {:operation label :opcode opcode})))
    (println (pr-str {:format :aiueos.value-runtime-capability-table/verification-v1
                      :vectors vectors :export (:export object)
                      :imports [] :foreign-code false :status :passed}))))
