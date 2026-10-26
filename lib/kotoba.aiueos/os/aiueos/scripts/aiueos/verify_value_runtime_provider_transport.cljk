(ns aiueos.verify-value-runtime-provider-transport
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler])
  (:import [java.security MessageDigest]))

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-runtime-provider-transport))))

(defn- hex-bytes [s]
  (byte-array (map #(unchecked-byte (Integer/parseInt (apply str %) 16))
                   (partition 2 s))))

(defn- submit [state route domain cap-handle digest]
  (if (or (:locked? state) (not (contains? #{14 15} route))
          (not (<= 1 domain 32767)) (not (pos? cap-handle))
          (not= 64 (count digest)) (= 7 (count (:requests state))))
    [state 0]
    (let [ticket (if (= 4294967295 (:ticket state))
                   0 (inc (:ticket state)))]
      (if (zero? ticket)
        [state 0]
      [(-> state
           (assoc :ticket ticket)
           (assoc-in [:requests ticket]
                     {:route route :domain domain :cap-handle cap-handle
                      :digest digest :state :pending}))
       ticket]))))

(defn- claim [state]
  (if (:locked? state)
    [state 0]
    (if-let [[ticket request]
             (first (sort-by key (filter #(= :pending (:state (val %)))
                                         (:requests state))))]
      [(assoc-in state [:requests ticket :state] :claimed)
       (+ ticket (* (:route request) 4294967296)
          (* (:domain request) 1099511627776))]
      [state 0])))

(defn- complete [state ticket route domain block-hex descriptor]
  (let [request (get-in state [:requests ticket])]
    (if (or (:locked? state) (not (pos? descriptor))
            (not= :claimed (:state request))
            (not= route (:route request)) (not= domain (:domain request))
            (not (MessageDigest/isEqual
                  (hex-bytes (:digest request))
                  (.digest (MessageDigest/getInstance "SHA-256")
                           (hex-bytes block-hex)))))
      [state 0]
      [(update state :requests dissoc ticket) 1])))

(defn- step [[state results] [op & args]]
  (case op
    :submit (let [[state result] (apply submit state args)]
              [state (conj results result)])
    :claim (let [[state result] (claim state)]
             [state (conj results result)])
    :complete (let [[state result] (apply complete state args)]
                [state (conj results result)])
    :fill (let [n (first args)
                digest "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
                [state _] (reduce (fn [[s _] i] (submit s 14 4 (inc i) digest))
                                  [state nil] (range n))]
            [state (conj results (count (:requests state)))])
    (fail! "unknown transport vector operation" {:operation op})))

(defn- verify-vectors! [vectors]
  (doseq [{:keys [name locked? initial-ticket steps expected]} vectors]
    (let [[_ actual] (reduce step [{:locked? locked?
                                    :ticket (or initial-ticket 0) :requests {}} []] steps)]
      (when-not (= expected actual)
        (fail! "provider transport vector mismatch"
               {:vector name :expected expected :actual actual}))))
  (count vectors))

(defn- flattened [value]
  (tree-seq coll? seq value))

(defn -main [& [arena-source sha-source digest-source cas-source transport-source contract-path]]
  (when-not (and arena-source sha-source digest-source cas-source transport-source contract-path)
    (fail! "usage: <arena> <sha> <digest> <cas> <transport> <contract>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        result (compiler/compile-project
                {'aiueos.value-handle-arena (slurp arena-source)
                 'aiueos.sha256 (slurp sha-source)
                 'aiueos.digest-equal (slurp digest-source)
                 'aiueos.value-runtime-cas-verify (slurp cas-source)
                 'aiueos.value-runtime-provider-transport (slurp transport-source)}
                'aiueos.value-runtime-provider-transport
                :x86_64-aiueos-kernel-v1)
        values (flattened (:kir result))
        present-ops (set (filter symbol? values))
        native (:native contract)
        code (get-in result [:artifact :code])
        exports (set (keys (get-in result [:artifact :exports])))]
    (verify-vectors! (:vectors contract))
    (when-not (every? exports (:exports native))
      (fail! "provider transport export absent"
             {:required (:exports native) :actual exports}))
    (when-not (every? present-ops (:required-operations native))
      (fail! "provider transport operation absent"
             {:required (:required-operations native)}))
    (doseq [[label opcode] [[:queue (:queue-opcode native)]
                            [:arena (:arena-opcode native)]
                            [:scratch (:scratch-opcode native)]
                            [:atomic (:atomic-opcode native)]]]
      (when-not (some #{opcode} (partition (count opcode) 1 code))
        (fail! "provider transport opcode absent" {:operation label :opcode opcode})))
    (when-not (empty? (get-in result [:object :imports]))
      (fail! "provider transport imports foreign code"
             {:imports (get-in result [:object :imports])}))
    (println (pr-str {:format :aiueos.value-runtime-provider-transport/verification-v1
                      :vectors (count (:vectors contract)) :queue-slots 7
                      :imports [] :foreign-code false :status :passed}))))
