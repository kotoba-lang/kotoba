(ns aiueos.verify-value-runtime-syscall-plan
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]
            [kotoba.kir :as kir]))

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-runtime-syscall-plan))))

(defn- model [[number domain pointer user-rip user-rsp]]
  (let [canonical? #(<= 1 % 140737488355327)
        offset (bit-and pointer 4095)]
    (if (and (= number 5) (<= 1 domain 32767)
             (canonical? pointer) (<= offset 3992)
             (canonical? user-rip) (canonical? user-rsp))
      (+ offset (* domain 65536) (* 4096 4294967296)
         (* 104 281474976710656))
      0)))

(defn -main [& [source-path contract-path]]
  (when-not (and source-path contract-path)
    (fail! "usage: <source.kotoba> <contract.edn>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        result (compiler/compile-source (slurp source-path)
                                        :x86_64-aiueos-kernel-v1)
        object (:object result)]
    (when-not (= (get-in contract [:native :export]) (:export object))
      (fail! "native export mismatch" {:actual (:export object)}))
    (when-not (= (get-in contract [:native :imports]) (:imports object))
      (fail! "native object imports foreign code" {:imports (:imports object)}))
    (doseq [{:keys [name args expected]} (:vectors contract)]
      (let [interpreted (kir/execute (:kir result)
                                     'aiueos-value-runtime-syscall-plan args)
            modelled (model args)]
        (when-not (= expected interpreted modelled)
          (fail! "syscall admission vector mismatch"
                 {:vector name :expected expected
                  :interpreted interpreted :modelled modelled}))))
    (println (pr-str {:format :aiueos.value-runtime-syscall-plan/verification-v1
                      :vectors (count (:vectors contract))
                      :export (:export object) :imports (:imports object)
                      :status :passed}))))
