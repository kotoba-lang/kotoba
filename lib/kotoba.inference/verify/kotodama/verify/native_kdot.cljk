(ns kotodama.verify.native-kdot
  (:require [kotodama.inference.host.native-kdot :as native])
  (:import (java.nio.file Files OpenOption)))

(defn- hex->bytes [s]
  (byte-array (map (fn [[a b]] (unchecked-byte (Integer/parseInt (str a b) 16)))
                   (partition 2 s))))

(def q4 "f516b322fefdfffdfdfefcffeeceefcf4095ea4f94e93e84d92e83d82d73c81d62b71c61b60b51a6fb50a5fa4f95ea3fd82d72c71c62c71c61b60b51a6fb50a5fa4f94e93e94e93e83d82d73c82d72c751a6fb4095ea4f95ea3f84d92e74c92e73c81d62b71c62b70c51a6fb41a6fb40d92e73c82d73c81d62b71c62b70c51a6fb4196eb4095ea3f84d93e84d92e73c8")
(def q6 "3085aa0f6387dc3055ba1e3287eb00655702ce7925f0ac5713ce7a45f1ac68133189c1146ca4e63f87c9115aace43c7f0a2ea3385cd1658a0e83a73cb0d569ee9c1743ce4a65f17c9813aeca45c1fc78ec3186ca1f54a7ec3175ca0f5297ec208bb6015e89e3306bb6033e98e5106bb802ce7925f0ac5713ce7a45f1ac6813ceec3542ef35429f35429f38429fe8429f17ca6017ca6117cabd17cabd14cabd20db06b1db0671dc0671ec0671ac0b71ac28825f28855f28f55f28f55228f58228837f6d81887c806e7f847b7f6d81857cb08a")
(def input (mapv (fn [i] (* (- (mod i 31) 15) 0.0625)) (range 256)))

(defn- bits [x] (Float/floatToRawIntBits (float x)))

(defn -main [& _]
  (native/load-library!)
  (let [q4-bytes (hex->bytes q4)
        q4-actual (ffirst (native/matvec-bytes 12 q4-bytes 1 256 [input]))
        q6-actual (ffirst (native/matvec-bytes 14 (hex->bytes q6) 1 256 [input]))
        q4-expected (Float/parseFloat "-0x1.d8f678p+1")
        q6-expected (Float/parseFloat "-0x1.da38b2p+1")]
    (when-not (= (bits q4-expected) (bits q4-actual))
      (throw (ex-info "native Q4_K dot differs from official ggml" {:expected q4-expected :actual q4-actual})))
    (when-not (= (bits q6-expected) (bits q6-actual))
      (throw (ex-info "native Q6_K dot differs from official ggml" {:expected q6-expected :actual q6-actual})))
    (let [path (Files/createTempFile "kotodama-kdot-" ".gguf-row" (make-array java.nio.file.attribute.FileAttribute 0))]
      (try
        (Files/write path q4-bytes (make-array OpenOption 0))
        (let [mapped (ffirst (native/matvec-mapped 12 (str path) 0 (alength q4-bytes)
                                                   1 256 [input]))]
          (when-not (= (bits q4-expected) (bits mapped))
            (throw (ex-info "mmap native Q4_K dot differs from official ggml"
                            {:expected q4-expected :actual mapped}))))
        (finally (Files/deleteIfExists path))))
    (prn {:kotodama/native-kdot :ok
          :q4-k q4-actual
          :q6-k q6-actual
          :library (native/default-library-path)})))
