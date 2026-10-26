(ns kotoba.capability.data.json.provider
  "Portable reference host provider for actor:host fields
  \"json_encode\" and \"json_extract_field\".

  Pure surfaces:
  - encode flat key\tvalue / LF pairs as a JSON object of string→string
  - extract a string-valued field via bounded `\"field\":\"value\"` scan
  ABI matches capability_contract.edn; memory wiring is the embedder's job.

  Q9 whole-component migration: ported from provider.clj (JVM/Java interop)
  to portable .cljc — runs JVM-free via nbb/CLJS and amu --jvm-free.
  Public exports preserved: parse-pairs, encode-object, encode-pairs-wire,
  extract-field, host-exports."
  (:require [kotoba.lang.text :as str]))

(defn parse-pairs
  [wire]
  (into []
        (keep (fn [line]
                (when-not (or (nil? line) (zero? (count line)))
                  (let [tab (str/index-of line "\t")]
                    (when (neg? tab)
                      (throw (ex-info "pair missing tab" {:line line})))
                    [(subs line 0 tab) (subs line (inc tab))])))
              (str/split wire #"\n" -1))))

(defn- json-escape
  [s]
  (apply str
         (map (fn [ch]
                (case ch
                  \" "\\\""
                  \\ "\\\\"
                  \newline "\\n"
                  \return "\\r"
                  \tab "\\t"
                  ch))
              s)))

(defn encode-object
  "JSON object of string keys/values (insertion order)."
  [pairs]
  (let [parts (map (fn [[idx [k v]]]
                     (str (when (pos? idx) ",")
                          "\"" (json-escape (str k)) "\":\""
                          (json-escape (str v)) "\""))
                   (map-indexed vector pairs))]
    (str "{" (apply str parts) "}")))

(defn encode-pairs-wire
  [wire]
  (encode-object (parse-pairs wire)))

(defn- skip-ws
  [s i]
  (loop [j i]
    (if (>= j (count s))
      j
      (let [c (nth s j)]
        (if (or (= c \space) (= c \tab) (= c \newline) (= c \return))
          (recur (inc j))
          j)))))

(defn- unescape-json-string
  "Read a JSON string body starting at index `start` (first char after opening
  quote). Returns [value end-index-after-closing-quote] or nil."
  [json start]
  (let [n (count json)]
    (loop [i start, acc ""]
      (when (< i n)
        (let [c (nth json i)]
          (cond
            (= c \")
            [acc (inc i)]

            (= c \\)
            (when (< (inc i) n)
              (let [e (nth json (inc i))
                    ch (case e
                         \" \"
                         \\ \\
                         \n \newline
                         \r \return
                         \t \tab
                         \/ \/
                         nil)]
                (when ch
                  (recur (+ i 2) (str acc ch)))))

            :else
            (recur (inc i) (str acc c))))))))

(defn extract-field
  "Bounded scan for `\"field\"` then optional whitespace, `:`, optional
  whitespace, `\"value\"`. Returns the unescaped value string or nil."
  [json field]
  (let [needle (str "\"" field "\"")
        start (str/index-of json needle)]
    (when-not (nil? start)
      (let [j (skip-ws json (+ start (count needle)))]
        (when (and (< j (count json)) (= (nth json j) \:))
          (let [k (skip-ws json (inc j))]
            (when (and (< k (count json)) (= (nth json k) \"))
              (first (unescape-json-string json (inc k))))))))))

(defn host-exports
  "Both actor:host fields for data/json."
  []
  [{:module "kotoba"
    :field "json_encode"
    :params [:i32 :i32 :i32 :i32]
    :result :i32
    :fn encode-pairs-wire}
   {:module "kotoba"
    :field "json_extract_field"
    :params [:i32 :i32 :i32 :i32 :i32 :i32]
    :result :i32
    :fn extract-field}])
