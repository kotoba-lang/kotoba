(ns aiueos.verify-value-runtime-entry
  (:require [aiueos.verify-value-runtime-dispatch :as dispatch]
            [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]))

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-runtime-entry))))

(defn- lane [profile divisor]
  (bit-and (quot profile divisor) 65535))

(defn- entry-profile-valid? [profile]
  (and (pos? profile)
       (<= (lane profile 1) 3992)
       (<= 1 (lane profile 65536) 32767)
       (= 4096 (lane profile 4294967296))
       (= 104 (lane profile 281474976710656))))

(defn- dispatcher-profile [domain]
  (+ 4096 (* 96 65536) (* 4096 4294967296)
     (* domain 281474976710656)))

(defn- verify-vectors! [vectors]
  (doseq [{:keys [name entry-profile raw capability arena expected]} vectors]
    (let [normalizable? (and (entry-profile-valid? entry-profile)
                             (:suffix-zero? raw))
          request (assoc (:request raw) :canonical?
                         (get-in raw [:request :canonical-prefix?]))
          admitted-capability (assoc capability :handle (:capability-handle raw))
          [_ actual] (if normalizable?
                       (dispatch/dispatch-model
                        arena (dispatcher-profile (lane entry-profile 65536))
                        admitted-capability request)
                       [arena 0])]
      (when-not (= (:result expected) actual)
        (fail! "entry semantic vector mismatch"
               {:vector name :expected (:result expected) :actual actual}))
      (when (and normalizable? (:normalized-zero-range expected)
                 (not= [56 96] (:normalized-zero-range expected)))
        (fail! "invalid normalized zero-range receipt"
               {:vector name :expected (:normalized-zero-range expected)}))))
  (count vectors))

(defn- flattened [value]
  (tree-seq coll? seq value))

(defn -main [& [arena-source sha-source digest-source cas-source transport-source dispatch-source entry-source contract-path]]
  (when-not (and arena-source sha-source digest-source cas-source transport-source dispatch-source entry-source contract-path)
    (fail! "usage: <arena> <sha> <digest> <cas> <transport> <dispatch> <entry> <contract>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        sources {'aiueos.value-handle-arena (slurp arena-source)
                 'aiueos.sha256 (slurp sha-source)
                 'aiueos.digest-equal (slurp digest-source)
                 'aiueos.value-runtime-cas-verify (slurp cas-source)
                 'aiueos.value-runtime-provider-transport (slurp transport-source)
                 'aiueos.value-runtime-dispatch (slurp dispatch-source)
                 'aiueos.value-runtime-entry (slurp entry-source)}
        result (compiler/compile-project sources 'aiueos.value-runtime-entry
                                         :x86_64-aiueos-kernel-v1)
        object (:object result)
        code (get-in result [:artifact :code])
        opcode (get-in contract [:native :required-opcode])
        values (flattened (:kir result))
        required-ops (set (get-in contract [:native :required-operations]))
        present-ops (set (filter symbol? values))
        vector-count (verify-vectors! (:vectors contract))]
    (when-not (= (get-in contract [:native :export]) (:export object))
      (fail! "native export mismatch" {:object (select-keys object [:export :abi])}))
    (when-not (= (get-in contract [:native :imports]) (:imports object))
      (fail! "native object unexpectedly imports foreign code" {:imports (:imports object)}))
    (when-not (every? present-ops required-ops)
      (fail! "linked KIR is missing entry memory operations"
             {:required required-ops
              :present (set (filter present-ops required-ops))}))
    (when-not (every? (set values) (get-in contract [:native :required-provider-wires]))
      (fail! "linked KIR is missing provider route wire IDs"
             {:required (get-in contract [:native :required-provider-wires])}))
    (when-not (some #{opcode} (partition (count opcode) 1 code))
      (fail! "native object does not contain LOCK CMPXCHG" {:opcode opcode}))
    (println (pr-str {:format :aiueos.value-runtime-entry/verification-v1
                      :modules (get-in result [:project :kotoba.module/order])
                      :vectors vector-count :export (:export object)
                      :imports (:imports object) :normalized-copy [0 56]
                      :normalized-zero [56 96] :atomic-opcode opcode
                      :status :passed}))))
