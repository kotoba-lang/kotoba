(ns dango.bytes
  "The two byte shapes dango moves between: the platform byte array and the
  vector of ints the portable crypto computes on. Nothing else here touches a
  host type."
  (:refer-clojure :exclude [bytes?]))

(defn bytes? [x]
  #?(:clj (clojure.core/bytes? x)
     :cljs (or (instance? js/Uint8Array x) (instance? js/Int8Array x))))

(defn ->bytes
  "A sequence of 0-255 ints to the platform byte array."
  [v]
  #?(:clj (byte-array (map unchecked-byte v))
     :cljs (js/Uint8Array.from (clj->js (vec v)))))

(defn ->vec
  "The platform byte array to a vector of 0-255 ints."
  [b]
  #?(:clj (mapv #(bit-and % 0xff) b)
     :cljs (mapv #(bit-and % 0xff) (js/Array.from b))))

(defn size [b]
  #?(:clj (alength ^bytes b) :cljs (.-length b)))

(defn utf8 [s]
  #?(:clj (mapv #(bit-and % 0xff) (.getBytes ^String s "UTF-8"))
     :cljs (mapv identity (js/Array.from (.encode (js/TextEncoder.) s)))))

(defn from-utf8 [ints]
  #?(:clj (String. ^bytes (->bytes ints) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8" #js {:fatal true}) (->bytes ints))))
