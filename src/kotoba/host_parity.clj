(ns kotoba.host-parity
  "Launcher-side host import parity matrix (ADR-2607180900 P1).

  Vendored host-parity.edn under resources/kotoba/lang/ — same catalog as
  kotoba-lang/lang/host-parity.edn."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]))

(def ^:private catalog*
  (delay
    (let [c (or (io/resource "kotoba/lang/host-parity.edn")
                (io/resource "lang/host-parity.edn"))]
      (if c
        (with-open [r (io/reader c)]
          (edn/read (java.io.PushbackReader. r)))
        {:imports {}
         :acceptance {:browser-linkable-statuses #{:yes} :min-browser-ratio 0.0}}))))

(defn catalog [] @catalog*)

(defn matrix
  []
  (mapv (fn [[id row]]
          {:import id
           :jvm (:jvm row)
           :browser (:browser row)
           :node (:node row)
           :wasm-field (:wasm-field row)
           :note (:note row)})
        (sort-by (comp name key) (:imports (catalog) {}))))

(defn score
  []
  (let [c (catalog)
        statuses (get-in c [:acceptance :browser-linkable-statuses] #{:yes})
        min-ratio (get-in c [:acceptance :min-browser-ratio] 0.0)
        rows (matrix)
        n (count rows)
        yes (count (filter #(contains? statuses (:browser %)) rows))
        ratio (if (pos? n) (double (/ yes n)) 0.0)]
    {:total n
     :browser-yes yes
     :browser-no (- n yes)
     :ratio ratio
     :min-ratio min-ratio
     :ok? (>= ratio min-ratio)
     :missing (mapv :import (remove #(contains? statuses (:browser %)) rows))}))

(defn report
  []
  {:level :l5-partial
   :status (if (:ok? (score)) :meets-threshold :below-threshold)
   :score (score)
   :matrix (matrix)})
