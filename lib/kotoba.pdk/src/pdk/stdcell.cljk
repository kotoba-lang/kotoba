(ns pdk.stdcell
  "Standard cell library (generic ~20-cell library generator). Restored
  from kami-pdk's `stdcell` module (deleted PR #82)."
  (:require [kotoba.lang.text :as str]
            [pdk.technology :as tech]))

(defn- node->debug-str
  "Mirrors Rust's `{:?}` Debug output for the TechNode enum (e.g. :n7 -> \"N7\")."
  [node]
  (str/upper (name node)))

(def cell-functions
  #{:inv :nand2 :nand3 :nor2 :nor3 :and2 :or2 :xor2
    :buf :dff :latch :mux2 :aoi21 :oai21 :tie-hi :tie-lo})

(defn find-by-function [lib func] (filterv #(= (:function %) func) (:cells lib)))

(defn cells-sorted-by-area [lib] (vec (sort-by :area (:cells lib))))

(defn- cell [name func drive base-area inputs outputs scale]
  {:name name :function func :drive-strength drive
   :area (* base-area scale scale)
   :input-pins (vec inputs) :output-pins (vec outputs)})

(defn create-generic-lib
  "A generic standard cell library with ~20 cells at realistic areas,
  scaled from N7 reference by `node`'s feature size."
  [node]
  (let [scale (/ (tech/feature-nm node) 7.0)
        c (fn [name func drive base-area inputs outputs]
            (cell name func drive base-area inputs outputs scale))]
    {:name (str "etzhayyim_GENERIC_" (node->debug-str node))
     :tech-node node
     :cells
     [(c "INV_X1" :inv 1 0.798 ["A"] ["Y"])
      (c "INV_X2" :inv 2 1.064 ["A"] ["Y"])
      (c "INV_X4" :inv 4 1.596 ["A"] ["Y"])
      (c "BUF_X1" :buf 1 1.596 ["A"] ["Y"])
      (c "BUF_X2" :buf 2 2.128 ["A"] ["Y"])
      (c "NAND2_X1" :nand2 1 1.064 ["A" "B"] ["Y"])
      (c "NAND2_X2" :nand2 2 1.596 ["A" "B"] ["Y"])
      (c "NAND3_X1" :nand3 1 1.330 ["A" "B" "C"] ["Y"])
      (c "NOR2_X1" :nor2 1 1.064 ["A" "B"] ["Y"])
      (c "NOR2_X2" :nor2 2 1.596 ["A" "B"] ["Y"])
      (c "NOR3_X1" :nor3 1 1.330 ["A" "B" "C"] ["Y"])
      (c "AND2_X1" :and2 1 1.596 ["A" "B"] ["Y"])
      (c "OR2_X1" :or2 1 1.596 ["A" "B"] ["Y"])
      (c "XOR2_X1" :xor2 1 2.660 ["A" "B"] ["Y"])
      (c "AOI21_X1" :aoi21 1 1.330 ["A" "B" "C"] ["Y"])
      (c "OAI21_X1" :oai21 1 1.330 ["A" "B" "C"] ["Y"])
      (c "MUX2_X1" :mux2 1 2.660 ["A" "B" "S"] ["Y"])
      (c "DFF_X1" :dff 1 4.256 ["D" "CK"] ["Q"])
      (c "LATCH_X1" :latch 1 3.192 ["D" "G"] ["Q"])
      (c "TIEHI_X1" :tie-hi 1 0.798 [] ["Y"])
      (c "TIELO_X1" :tie-lo 1 0.798 [] ["Y"])]}))
