(ns saifu.address
  "bech32（BIP-173）とチェーンアドレスの導出。**純粋関数だけ。**

  ## この ns がハッシュを実装しない理由

  Cosmos のアドレスは `bech32(hrp, ripemd160(sha256(compressed-pubkey)))`。
  このうち **ripemd160 / sha256 は暗号プリミティブ = 機構(mechanism)** であって
  判断を含まない（ADR-2607241100 の decision-free mechanism / ADR-2608039900）。
  自前実装は事故の定番なので、**この ns は 20 byte のハッシュを受け取る**形にし、
  ハッシュ自体はレビュー済み実装（JDK / @noble/hashes / kagi）に委ねる。

  結果として **address 層は資金も暗号実装も無しに正しさを証明できる** ——
  テストベクタが (address, hash160) の対を与えるので、bech32 の encode/decode が
  実チェーンの実在口座を再現するかだけを見ればよい。saifu の実装順が
  『address → policy → tx → sign → broadcast』なのはこのため。

  ## bech32 と bech32m を混ぜない

  Cosmos は **bech32（チェックサム定数 1）**。bech32m（0x2bc830a3、BIP-350）は
  Segwit v1+ 用。**混ぜると検査を通る別のアドレスが出る**ので定数を明示する。"
  (:require [kotoba.lang.text :as str]))

(def charset
  "bech32 のデータ文字。1/b/i/o は視認性のため除外されている（BIP-173）。"
  "qpzry9x8gf2tvdw0s3jn54khce6mua7l")

(def ^:private charset-index
  (into {} (map-indexed (fn [i c] [c i]) charset)))

(def ^:private generator
  [0x3b6a57b2 0x26508e6d 0x1ea119fa 0x3d4233dd 0x2a1462b3])

(def bech32-const
  "bech32 のチェックサム定数。bech32m は 0x2bc830a3 で **別物**。"
  1)

(defn- char-codes [s]
  #?(:clj (mapv int s)
     :cljs (mapv #(.charCodeAt s %) (range (count s)))))

(defn- polymod [values]
  (reduce
   (fn [chk v]
     (let [b (bit-shift-right chk 25)
           chk' (bit-xor (bit-shift-left (bit-and chk 0x1ffffff) 5) v)]
       (reduce (fn [c i] (if (bit-test b i) (bit-xor c (nth generator i)) c))
               chk' (range 5))))
   1 values))

(defn- expand-hrp [hrp]
  (let [cs (char-codes hrp)]
    (concat (map #(bit-shift-right % 5) cs) [0] (map #(bit-and % 31) cs))))

(defn- verify-checksum [hrp data]
  (= bech32-const (polymod (concat (expand-hrp hrp) data))))

(defn- create-checksum [hrp data]
  (let [pm (bit-xor (polymod (concat (expand-hrp hrp) data [0 0 0 0 0 0])) bech32-const)]
    (mapv (fn [i] (bit-and (bit-shift-right pm (* 5 (- 5 i))) 31)) (range 6))))

(defn convert-bits
  "`from` bit 幅の値列を `to` bit 幅へ。`pad?` が真なら末尾を 0 埋め。

   → 値の vector、または **nil**（変換不能）。

   nil を空 vector や 0 にしない —— 『変換できなかった』と『空だった』を同じ値で
   表すと、**壊れたアドレスが空アドレスとして通る**。decode 側で長さを見ても
   気付けない種類の不具合になる。"
  [values from to pad?]
  (let [maxv (dec (bit-shift-left 1 to))]
    (loop [acc 0 bits 0 out [] vs (seq values)]
      (if vs
        (let [v (first vs)]
          (if (or (neg? v) (pos? (bit-shift-right v from)))
            nil
            (let [acc (bit-or (bit-shift-left acc from) v)
                  bits (+ bits from)
                  [bits' out'] (loop [b bits o out]
                                 (if (>= b to)
                                   (let [b' (- b to)]
                                     (recur b' (conj o (bit-and (bit-shift-right acc b') maxv))))
                                   [b o]))]
              (recur acc bits' out' (next vs)))))
        (cond
          pad? (if (pos? bits)
                 (conj out (bit-and (bit-shift-left acc (- to bits)) maxv))
                 out)
          ;; padding 無しなら、余りビットは to 未満かつ全て 0 でなければならない
          (>= bits from) nil
          (not (zero? (bit-and (bit-shift-left acc (- to bits)) maxv))) nil
          :else out)))))

(defn encode
  "hrp + 8bit byte 列 → bech32 文字列、または nil。"
  [hrp bytes]
  (when-let [d (convert-bits bytes 8 5 true)]
    (str hrp "1" (apply str (map #(nth charset %) (concat d (create-checksum hrp d)))))))

(defn decode
  "bech32 文字列 → `{:hrp s :bytes [..]}`、不正なら nil。

   **大文字小文字の混在は拒否する**（BIP-173）。許すと見た目の違う 2 つの文字列が
   同じアドレスになり、目視確認が意味を失う。"
  [s]
  (when (and (string? s) (seq s) (<= (count s) 90)
             (or (= s (str/lower s)) (= s (str/upper s))))
    (let [s (str/lower s)
          pos (str/last-index-of s "1")]
      (when (and pos (>= pos 1) (<= (+ pos 7) (count s)))
        (let [hrp (subs s 0 pos)
              dpart (subs s (inc pos))]
          (when (every? charset-index dpart)
            (let [data (mapv charset-index dpart)]
              (when (verify-checksum hrp data)
                (when-let [b (convert-bits (subvec data 0 (- (count data) 6)) 5 8 false)]
                  {:hrp hrp :bytes b})))))))))

(def account-hash-length
  "Cosmos のアカウントアドレスは 20 byte。19 byte でも bech32 としては正しい
   文字列になるので、**長さを見ないと検査を通る別人のアドレスが出る**。"
  20)

(defn from-hash160
  "20 byte のアカウントハッシュ + hrp → アドレス、または nil。"
  [hrp hash160]
  (let [b (vec hash160)]
    (when (= account-hash-length (count b))
      (encode hrp b))))

(defn hash160-of
  "アドレス → 20 byte、または nil（hrp 不一致・長さ不正を含む）。"
  [expected-hrp addr]
  (let [{:keys [hrp bytes]} (decode addr)]
    (when (and hrp (= expected-hrp hrp) (= account-hash-length (count bytes)))
      bytes)))

(defn belongs-to?
  "`addr` が `hrp` のチェーンのものか。**hrp が違えば別チェーンの別人**なので、
   送金前に必ず通す。"
  [hrp addr]
  (= hrp (:hrp (decode addr))))
