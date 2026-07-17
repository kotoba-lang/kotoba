(ns kotoba.guest-grammar
  "Embedded loader for the shared guest-grammar catalog (ADR-2607180900).

  Prefers classpath `kotoba/lang/guest-grammar.edn` (vendored from
  kotoba-lang/lang/guest-grammar.edn) so emit/check work without waiting for
  a kotoba-lang git pin that includes `kotoba.lang.guest-grammar`."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]))

(def ^:private catalog*
  (delay
    (let [c (or (io/resource "kotoba/lang/guest-grammar.edn")
                (io/resource "lang/guest-grammar.edn")
                (let [f (io/file "lang/guest-grammar.edn")]
                  (when (.isFile f) f)))]
      (if c
        (with-open [r (io/reader c)]
          (edn/read (java.io.PushbackReader. r)))
        {:kotoba.lang.guest-grammar/version 0
         :kotoba.lang.guest-grammar/status :missing
         :forbidden-heads #{}
         :diagnostic-hints {}
         :string-head-host-ops #{}}))))

(defn catalog [] @catalog*)

(defn string-head-host-ops
  []
  (into #{} (map symbol) (map name (:string-head-host-ops (catalog) #{}))))

(defn diagnostic-hint
  [head]
  (let [k (cond (string? head) head
                (symbol? head) (name head)
                :else (str head))]
    (get (:diagnostic-hints (catalog) {}) k)))

(defn with-hint
  "Assoc :kotoba.lang/hint onto PROBLEM when HEAD has a catalog entry."
  [problem head]
  (if-let [hint (diagnostic-hint head)]
    (assoc problem :kotoba.lang/hint hint)
    problem))

(defn enhance-wasm-problem
  "Enrich a :kotoba.wasm/problem map with author hints when applicable."
  [problem]
  (let [op (or (:kotoba.wasm/op problem)
               (when-let [p (:problem problem)]
                 (:kotoba.wasm/op p)))
        core (if (:kotoba.wasm/problem problem) problem (:problem problem problem))]
    (cond
      (nil? op) problem
      (:kotoba.wasm/problem problem)
      (with-hint problem op)
      (:problem problem)
      (update problem :problem with-hint op)
      :else problem)))
