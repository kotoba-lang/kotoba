(ns aiueos.verify-value-runtime-dispatch
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]))

(def tag-unit 72057594037927936)

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-runtime-dispatch))))

(defn- lane [profile divisor]
  (bit-and (quot profile divisor) 65535))

(defn- profile-valid? [profile]
  (and (pos? profile)
       (= 4096 (lane profile 1))
       (= 96 (lane profile 65536))
       (= 4096 (lane profile 4294967296))
       (<= 1 (lane profile 281474976710656) 32767)))

(defn- capability-admitted? [profile required {:keys [handle entry] :as capability}]
  (let [{:keys [slot generation type rights active? owner]} entry
        stored-provider-generation (or (:provider-generation entry) 1)
        current-provider-generation (or (:provider-generation capability) 1)
        provider-active? (not= false (:provider-active? capability))
        expected (+ slot (* generation 65536) (* type 4294967296)
                    (* rights 281474976710656))]
    (and (not (:locked? capability)) provider-active? entry (pos? handle)
         (<= 1 slot 255) (pos? generation)
         (= 2 type) active? (= owner (lane profile 281474976710656))
         (= stored-provider-generation current-provider-generation)
         (<= 1 rights 7) (= required (bit-and rights required))
         (= handle expected))))

(defn- tagged [tag value]
  (if (<= 1 value 4294967295) (+ (* tag tag-unit) value) 0))

(defn- arena-step [state operation handle descriptor]
  (let [state (merge {:initialized? false :next-handle 1 :entries {}} state)]
    (case operation
      1 (let [value (bit-and descriptor 0xffffffff)
              cid (quot descriptor 4294967296)
              next-handle (:next-handle state)]
          (if (and (:initialized? state) (pos? value) (pos? cid)
                   (<= next-handle 4096) (< (count (:entries state)) 63))
            [(-> state
                 (assoc-in [:entries next-handle] {:value value :cid cid})
                 (update :next-handle inc))
             next-handle]
            [state 0]))
      2 [state (get-in state [:entries handle :value] 0)]
      3 [state (get-in state [:entries handle :cid] 0)]
      4 (if (contains? (:entries state) handle)
          [(update state :entries dissoc handle) 1]
          [state 0])
      [state 0])))

(defn dispatch-model [state profile capability request]
  (let [{:keys [operation phase handle descriptor canonical? digest?]} request]
    (if-not (and (profile-valid? profile) canonical? (<= 1 operation 5)
                 (<= 0 phase 1))
      [state 0]
      (if (<= operation 2)
        (let [required (if (= operation 1) 4 1)]
          (if (and (zero? handle)
                   (capability-admitted? profile required capability))
            (if (zero? phase)
              [state (if (zero? descriptor)
                       (tagged 2 1) 0)]
              [state 0])
            [state 0]))
        (if (and (zero? phase) (zero? descriptor) (not digest?)
                 (zero? (:handle capability)) (pos? handle))
          (let [[next-state result] (arena-step state (- operation 1) handle 0)]
            [next-state (tagged 1 result)])
          [state 0])))))

(defn- verify-case! [state profile capability request expected vector-name]
  (let [[next-state actual] (dispatch-model state profile capability request)]
    (when-not (= expected actual)
      (fail! "semantic vector mismatch"
             {:vector vector-name :request request :expected expected :actual actual}))
    next-state))

(defn- verify-vectors! [vectors]
  (reduce
   +
   (for [{:keys [name profile capability request expected arena steps]} vectors]
     (if (seq steps)
       (do (reduce (fn [state step]
                     (verify-case! state profile capability
                                   (:request step) (:expected step) name))
                   arena steps)
           (count steps))
       (do (verify-case! arena profile capability request expected name) 1)))))

(defn- flattened [value]
  (tree-seq coll? seq value))

(defn -main [& [arena-source sha-source digest-source cas-source transport-source dispatch-source contract-path]]
  (when-not (and arena-source sha-source digest-source cas-source transport-source dispatch-source contract-path)
    (fail! "usage: <arena> <sha> <digest> <cas> <transport> <dispatch> <contract>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        sources {'aiueos.value-handle-arena (slurp arena-source)
                 'aiueos.sha256 (slurp sha-source)
                 'aiueos.digest-equal (slurp digest-source)
                 'aiueos.value-runtime-cas-verify (slurp cas-source)
                 'aiueos.value-runtime-provider-transport (slurp transport-source)
                 'aiueos.value-runtime-dispatch (slurp dispatch-source)}
        result (compiler/compile-project sources 'aiueos.value-runtime-dispatch
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
      (fail! "linked KIR is missing required bounded-memory operations"
             {:required required-ops
              :present (set (filter present-ops required-ops))}))
    (when-not (every? (set values) (get-in contract [:native :required-provider-wires]))
      (fail! "linked KIR is missing provider route wire IDs"
             {:required (get-in contract [:native :required-provider-wires])}))
    (when-not (some #{opcode} (partition (count opcode) 1 code))
      (fail! "native object does not contain LOCK CMPXCHG" {:opcode opcode}))
    (println (pr-str {:format :aiueos.value-runtime-dispatch/verification-v1
                      :modules (get-in result [:project :kotoba.module/order])
                      :vectors vector-count :export (:export object)
                      :imports (:imports object) :provider-wires [14 15]
                      :atomic-opcode opcode :status :passed}))))
