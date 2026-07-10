(ns kotoba.wasm.bytes
  "Portable byte helpers for safe Kotoba → WASM AOT emit.

  Emit works on vectors of unsigned 0–255 integers so the same pure logic can
  run on JVM Clojure, nbb, or ClojureScript. Hosts that need a platform
  byte array (Chicory, Node Buffer, Uint8Array) convert at the edge."
  (:require [clojure.string :as str]))

(defn utf8-bytes
  "UTF-8 encode s into a vector of unsigned (0–255) byte values."
  [s]
  #?(:clj  (mapv #(bit-and % 0xff) (.getBytes (str s) "UTF-8"))
     :cljs (let [enc (js/TextEncoder.)
                 u8  (.encode enc (str s))]
             (vec (array-seq u8)))))

(defn pack-bytes
  "Platform bytes from an unsigned 0–255 integer vector.

  - :clj  → Java byte-array (signed bytes; bit-identical layout)
  - :cljs → js/Uint8Array"
  [unsigned-bytes]
  #?(:clj  (byte-array (map unchecked-byte unsigned-bytes))
     :cljs (js/Uint8Array. (clj->js unsigned-bytes))))

(defn magic?
  "True when bs starts with the WASM magic number \\0asm."
  [bs]
  (let [v (cond
            (vector? bs) bs
            #?@(:clj  [(bytes? bs) (mapv #(bit-and % 0xff) bs)]
                :cljs [(instance? js/Uint8Array bs) (vec (array-seq bs))])
            :else (vec bs))]
    (= [0 97 115 109] (vec (take 4 v)))))

(defn hex-sha256
  "Hex SHA-256 of unsigned byte vector. CLJ only (MessageDigest); cljs hosts
  should pass precomputed digests or inject their own hash."
  [unsigned-bytes]
  #?(:clj
     (let [md (java.security.MessageDigest/getInstance "SHA-256")
           digest (.digest md (byte-array (map unchecked-byte unsigned-bytes)))]
       (str/join (map #(format "%02x" %) digest)))
     :cljs
     (throw (js/Error. "kotoba.wasm.bytes/hex-sha256 is CLJ-only; use Web Crypto or inject"))))
