(ns msgpack.bytes
  "Byte/text and byte/float conversions, written per-runtime.

  UTF-8 is `String.getBytes` on the JVM and `TextEncoder` under
  ClojureScript; IEEE 754 is `Double/doubleToLongBits` on one and a
  `DataView` on the other. Writing only one form compiles cleanly and fails
  at runtime on the other host, which is why this library ships two test
  runners rather than one."
  (:require [kotoba.lang.text :as str]))

(defn string->bytes
  "UTF-8 encode to a vector of bytes 0..255."
  [s]
  #?(:clj (mapv #(bit-and % 0xFF) (.getBytes ^String s "UTF-8"))
     :cljs (vec (array-seq (.encode (js/TextEncoder.) s)))))

(defn bytes->string
  "UTF-8 decode a Sequential of bytes 0..255."
  [bs]
  #?(:clj (String. (byte-array (map unchecked-byte bs)) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js (vec bs))))))

(defn f64->bytes
  "IEEE 754 binary64, big-endian."
  [x]
  #?(:clj (let [bits (Double/doubleToLongBits (double x))]
            (mapv (fn [shift] (bit-and (unsigned-bit-shift-right bits shift) 0xFF))
                  [56 48 40 32 24 16 8 0]))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 8))]
             (.setFloat64 dv 0 x false)
             (mapv #(.getUint8 dv %) (range 8)))))

(defn bytes->f64
  "Inverse of `f64->bytes`."
  [bs]
  #?(:clj (Double/longBitsToDouble
           (reduce (fn [acc b] (bit-or (bit-shift-left acc 8) (long b))) 0 bs))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 8))]
             (dotimes [i 8] (.setUint8 dv i (nth (vec bs) i)))
             (.getFloat64 dv 0 false))))

(defn bytes->f32
  "IEEE 754 binary32, big-endian, widened to a double.

  Decode only: nothing here ever emits a float32, because narrowing a value
  the caller handed us as a double would lose bits it did not ask to lose."
  [bs]
  #?(:clj (double (Float/intBitsToFloat
                   (unchecked-int (reduce (fn [acc b] (bit-or (bit-shift-left acc 8) (long b))) 0 bs))))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 4))]
             (dotimes [i 4] (.setUint8 dv i (nth (vec bs) i)))
             (.getFloat32 dv 0 false))))

(defn hex
  "Lowercase hex, for reading bytes in a test failure."
  [bs]
  (str/join (map (fn [b]
                   (let [s #?(:clj (Integer/toString (int b) 16)
                              :cljs (.toString b 16))]
                     (if (= 1 (count s)) (str "0" s) s)))
                 bs)))

(defn unhex
  "Parse lowercase hex back to a byte vector, for loading reference vectors."
  [s]
  (mapv (fn [pair] #?(:clj (Integer/parseInt (apply str pair) 16)
                      :cljs (js/parseInt (apply str pair) 16)))
        (partition 2 s)))
