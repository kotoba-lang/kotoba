(ns websocket.bytes
  "The byte/text conversions `frame` and `handshake` both need, in one place
  so the two cannot drift apart.

  Everything here is written per-runtime deliberately. UTF-8 is
  `String.getBytes` on the JVM and `TextEncoder` under ClojureScript; radix
  conversion is a static two-arg method on one and an instance method on the
  other. Writing only the ClojureScript form of either compiles cleanly and
  fails at runtime on the JVM, which is why this library ships two test
  runners rather than one."
  (:require [kotoba.lang.text :as str]))

(defn string->bytes
  "UTF-8 encode to a vector of bytes 0..255."
  [s]
  #?(:clj (mapv #(bit-and % 0xFF) (.getBytes ^String s "UTF-8"))
     :cljs (vec (array-seq (.encode (js/TextEncoder.) s)))))

(defn bytes->string
  "UTF-8 decode a vector of bytes 0..255."
  [bs]
  #?(:clj (String. (byte-array (map unchecked-byte bs)) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js (vec bs))))))

(defn hex
  "Lowercase hex, for reading a frame in a test failure."
  [bs]
  (str/join (map (fn [b]
                   (let [s #?(:clj (Integer/toString (int b) 16)
                              :cljs (.toString b 16))]
                     (if (= 1 (count s)) (str "0" s) s)))
                 bs)))
