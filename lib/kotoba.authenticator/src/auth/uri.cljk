(ns auth.uri
  "Parse and build `otpauth://` URIs — the de-facto Key URI Format that QR codes
  in Google Authenticator / Authy encode. Pure .cljc, no host URL libraries.

    otpauth://TYPE/LABEL?secret=BASE32&issuer=...&algorithm=...&digits=...&period=...&counter=...

  LABEL is `Issuer:account` (issuer prefix optional). Percent-decoding here is
  byte-level ASCII (sufficient for the issuer/account labels seen in practice);
  full UTF-8 multi-byte percent sequences are not reconstructed."
  (:require [kotoba.lang.text :as str]))

(def ^:private prefix "otpauth://")

;; Host-agnostic char handling: on the JVM a "char" is Character, on
;; ClojureScript it is a 1-char string. Going through (str c) + lookup avoids
;; host-specific integer coercion.
(def ^:private hex-digits "0123456789abcdef")

(defn- hex->int [c]
  (str/index-of hex-digits (str/lower (str c))))

(defn- char-code [c]
  #?(:clj (int c) :cljs (.charCodeAt (str c) 0)))

(defn percent-decode [s]
  (loop [cs (seq s) out []]
    (if (empty? cs)
      (apply str out)
      (let [c (first cs)]
        (if (and (= c \%) (>= (count cs) 3))
          (let [h (hex->int (nth cs 1)), l (hex->int (nth cs 2))]
            (if (and h l)
              (recur (drop 3 cs) (conj out (char (+ (* 16 h) l))))
              (recur (rest cs) (conj out c))))
          (recur (rest cs) (conj out (if (= c \+) \space c))))))))

(defn percent-encode
  "Percent-encodes the reserved set used in otpauth labels/params (ASCII)."
  [s]
  (apply str
    (for [c (str s)
          :let [code (char-code c)]]
      (if (or (and (>= code 48) (<= code 57))   ; 0-9
              (and (>= code 65) (<= code 90))   ; A-Z
              (and (>= code 97) (<= code 122))  ; a-z
              (contains? #{45 95 46 126} code)) ; - _ . ~
        (str c)
        (let [h #?(:clj (Integer/toString code 16) :cljs (.toString code 16))]
          (str "%" (str/upper (if (= 1 (count h)) (str "0" h) h))))))))

(defn- parse-query [q]
  (if (str/blank? q)
    {}
    (into {}
      (for [pair (str/split q #"&")
            :let [[k v] (str/split pair #"=" 2)]
            :when (seq k)]
        [(str/lower k) (percent-decode (or v ""))]))))

(defn- ->int [s default]
  (if (and s (re-matches #"\d+" s)) #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10)) default))

(defn parse
  "Parses an otpauth URI into an account map (auth.db schema keys), or nil if
  it is not an otpauth URI or has no secret."
  [uri]
  (when (and (string? uri) (str/starts-with? (str/lower uri) prefix))
    (let [body        (subs uri (count prefix))
          qpos        (str/index-of body "?")
          path        (if qpos (subs body 0 qpos) body)
          query       (if qpos (subs body (inc qpos)) "")
          slashpos    (str/index-of path "/")
          type-str    (str/lower (if slashpos (subs path 0 slashpos) path))
          label-raw   (if slashpos (subs path (inc slashpos)) "")
          label       (percent-decode label-raw)
          colon       (str/index-of label ":")
          label-iss   (when colon (str/trim (subs label 0 colon)))
          account     (str/trim (if colon (subs label (inc colon)) label))
          params      (parse-query query)
          secret      (get params "secret")]
      (when (seq secret)
        {:account/type      (if (= type-str "hotp") :hotp :totp)
         :account/name      account
         :account/issuer    (or (get params "issuer") label-iss)
         :account/secret    (str/upper (str/replace secret #"\s" ""))
         :account/algorithm (keyword (str/lower (get params "algorithm" "sha1")))
         :account/digits    (->int (get params "digits") 6)
         :account/period    (->int (get params "period") 30)
         :account/counter   (->int (get params "counter") 0)}))))

(defn build
  "Builds an otpauth URI from an account map. Inverse of `parse`."
  [{:account/keys [type name issuer secret algorithm digits period counter]}]
  (let [typ   (clojure.core/name (or type :totp))
        label (if (seq issuer)
                (str (percent-encode issuer) ":" (percent-encode name))
                (percent-encode name))
        ps    (cond-> [(str "secret=" secret)]
                (seq issuer)        (conj (str "issuer=" (percent-encode issuer)))
                algorithm           (conj (str "algorithm=" (str/upper (clojure.core/name algorithm))))
                digits              (conj (str "digits=" digits))
                (= type :totp)      (conj (str "period=" (or period 30)))
                (= type :hotp)      (conj (str "counter=" (or counter 0))))]
    (str prefix typ "/" label "?" (str/join "&" ps))))
