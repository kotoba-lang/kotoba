(ns dango.cid
  "CIDv1, dag-cbor, sha2-256, as a base32 `b` multibase string."
  (:require [clojure.string :as str]
            [dango.bytes :as b]
            [sha2.core :as sha2]))

(def ^:private alphabet "abcdefghijklmnopqrstuvwxyz234567")

(defn- pow2 [n] (reduce * 1 (repeat n 2)))

(defn- base32 [ints]
  (loop [xs (seq ints) acc 0 bits 0 out []]
    (cond
      (>= bits 5) (let [r (- bits 5)
                        d (quot acc (pow2 r))]
                    (recur xs (- acc (* d (pow2 r))) r (conj out (nth alphabet d))))
      xs (recur (next xs) (+ (* acc 256) (first xs)) (+ bits 8) out)
      (pos? bits) (recur nil (* acc (pow2 (- 5 bits))) 5 out)
      :else (apply str out))))

(defn- unbase32 [s]
  (loop [cs (seq s) acc 0 bits 0 out []]
    (if cs
      (let [i (str/index-of alphabet (str (first cs)))]
        (when-not i (throw (ex-info "dango.cid: not base32" {:char (str (first cs))})))
        (let [acc (+ (* acc 32) i) bits (+ bits 5)]
          (if (>= bits 8)
            (let [r (- bits 8) p (pow2 r) d (quot acc p)]
              (recur (next cs) (- acc (* d p)) r (conj out d)))
            (recur (next cs) acc bits out))))
      out)))

(defn bytes->cid [ints] (str "b" (base32 ints)))

(defn cid-bytes
  "The binary CID inside a `b` string, as ints."
  [cid]
  (let [v (unbase32 (subs cid 1))]
    (when-not (= cid (bytes->cid v))
      (throw (ex-info "dango.cid: not canonical base32" {:cid cid})))
    v))

(defn cidv1-dag-cbor [bs]
  (bytes->cid (into [0x01 0x71 0x12 0x20] (map #(bit-and % 0xff)) (sha2/sha256 (b/->vec bs)))))
