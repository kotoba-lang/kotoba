(ns kotodama.verify.metal-kdot-worker
  (:require [kotodama.inference.host.metal-kdot :as metal]
            [kotodama.verify.native-kdot :as fixture])
  (:import (java.nio.file Files OpenOption)
           (java.nio.file.attribute FileAttribute)))

(defn- hex->bytes [s]
  (byte-array (map (fn [[a b]] (unchecked-byte (Integer/parseInt (str a b) 16)))
                   (partition 2 s))))
(defn- bits [x] (Float/floatToRawIntBits (float x)))

(defn -main [& _]
  (let [q4 (hex->bytes fixture/q4)
        q6 (hex->bytes fixture/q6)
        all (byte-array (+ (alength q4) (alength q6)))
        path (Files/createTempFile "kotodama-metal-kdot-" ".bin" (make-array FileAttribute 0))
        worker (metal/start-worker)]
    (System/arraycopy q4 0 all 0 (alength q4))
    (System/arraycopy q6 0 all (alength q4) (alength q6))
    (try
      (Files/write path all (make-array OpenOption 0))
      (let [q4-out (ffirst (metal/matvec worker 12 (str path) 0 (alength q4) :q4 1 256 [fixture/input]))
            q6-out (ffirst (metal/matvec worker 14 (str path) (alength q4) (alength q6) :q6 1 256 [fixture/input]))
            [[q4-many] [q6-many]]
            (metal/matvec-many
             worker (str path)
             [{:tensor-type 12 :rows 1 :cols 256 :tensor-offset 0
               :tensor-bytes (alength q4) :cache-key :q4}
              {:tensor-type 14 :rows 1 :cols 256 :tensor-offset (alength q4)
               :tensor-bytes (alength q6) :cache-key :q6}]
             [fixture/input])]
        (when-not (= (bits (Float/parseFloat "-0x1.d8f678p+1")) (bits q4-out))
          (throw (ex-info "JVM Metal worker Q4 mismatch" {:actual q4-out})))
        (when-not (= (bits (Float/parseFloat "-0x1.da38b2p+1")) (bits q6-out))
          (throw (ex-info "JVM Metal worker Q6 mismatch" {:actual q6-out})))
        (when-not (= [(bits q4-out) (bits q6-out)]
                     [(bits (first q4-many)) (bits (first q6-many))])
          (throw (ex-info "Metal multi-matvec differs from single requests"
                          {:single [q4-out q6-out]
                           :multi [(first q4-many) (first q6-many)]})))
        (prn {:kotodama/metal-kdot-worker :ok :q4-k q4-out :q6-k q6-out
              :multi-projection :ok}))
      (finally
        (metal/close-worker! worker)
        (Files/deleteIfExists path)))))
