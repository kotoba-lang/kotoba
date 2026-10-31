(ns cae.result-reader
  "Small, format-oriented readers for host solver result interchange."
  (:require [kotoba.lang.text :as str]))

(defn- number [s]
  #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s)))

(defn scalar-values
  "Extract scalar tokens from an OpenFOAM uniform/nonuniform field body."
  [text]
  (->> (re-seq #"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?" (str text))
       (map number)
       vec))

(defn openfoam-field [{:keys [name location dimensions text]}]
  {:field (keyword name) :location (keyword (or location :cell)) :dimensions dimensions :values (scalar-values text) :format :openfoam-scalar-v1})

(defn calculix-table [{:keys [name columns text]}]
  (let [rows (->> (str/split-lines (str text))
                  (keep (fn [line]
                          (let [xs (->> (re-seq #"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?" line) (map number) vec)]
                            (when (seq xs) xs))))) ]
    {:table (keyword name) :columns (vec columns) :rows (vec rows) :format :calculix-table-v1}))

(defn result-manifest [{:keys [backend case-id files]}]
  {:backend (keyword backend) :case/id case-id :files (vec files) :format :cae-result-manifest-v1})

(defn vtk-legacy [{:keys [text]}]
  (let [tokens (str/split (str text) #"\s+")
        find-index (fn [needle] (or (first (keep-indexed (fn [i v] (when (= v needle) i)) tokens)) -1))
        point-at (find-index "POINTS")
        scalar-at (find-index "SCALARS")
        npoints (if (pos? point-at) (long (number (nth tokens (inc point-at)))) 0)
        point-start (+ point-at 3)
        points (if (pos? point-at) (vec (map number (take (* 3 npoints) (drop point-start tokens)))) [])
        scalar-name (when (pos? scalar-at) (nth tokens (inc scalar-at)))
        scalar-start (+ scalar-at 4)
        scalars (if (pos? scalar-at) (vec (map number (take npoints (drop scalar-start tokens)))) [])]
    {:format :vtk-legacy-ascii :points (vec (partition 3 points)) :scalars {scalar-name scalars} :point-count npoints}))
