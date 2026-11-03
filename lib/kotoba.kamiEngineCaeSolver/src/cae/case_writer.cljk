(ns cae.case-writer
  "Clean-room writers for interoperable OpenFOAM and CalculiX case inputs."
  (:require [kotoba.lang.text :as str]))

(defn- lines [& xs] (str (str/join "\n" xs) "\n"))

(defn openfoam-control-dict [{:keys [application end-time delta-t write-interval]}]
  (lines "FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }"
         (str "application " (or application "rhoPimpleFoam") ";")
         (str "startFrom startTime; startTime 0;")
         (str "stopAt endTime; endTime " (or end-time 1.0) ";")
         (str "deltaT " (or delta-t 0.001) ";")
         (str "writeControl timeStep; writeInterval " (or write-interval 100) ";")))

(defn openfoam-transport-properties [{:keys [kinematic-viscosity]}]
  (lines "FoamFile { version 2.0; format ascii; class dictionary; object transportProperties; }"
         (str "nu [0 2 -1 0 0 0 0] " (or kinematic-viscosity 1e-5) ";")))

(defn openfoam-case [{:keys [control transport]}]
  {"system/controlDict" (openfoam-control-dict control)
   "constant/transportProperties" (openfoam-transport-properties transport)})

(defn calculix-input [{:keys [nodes elements material youngs-modulus poisson-ratio loads fixed-nodes]}]
  (let [node-lines (map (fn [[id x y z]] (str id ", " x ", " y ", " z)) nodes)
        element-lines (map (fn [[id type & ids]] (str id ", " (or type "C3D4") ", " (str/join ", " ids))) elements)
        fixed-lines (map #(str % ", 1, 3") fixed-nodes)
        load-lines (map (fn [[id dof value]] (str id ", " dof ", " dof ", " value)) loads)]
    (str/join "\n" (concat ["*HEADING" "KOTOBA CLEAN-ROOM CALCULIX INPUT" "*NODE"] node-lines
                             ["*ELEMENT, TYPE=C3D4" ] element-lines
                             ["*MATERIAL, NAME=" (or material "MATERIAL-1") "*ELASTIC" (str (or youngs-modulus 1e9) ", " (or poisson-ratio 0.3))
                              "*BOUNDARY"] fixed-lines
                             ["*CLOAD"] load-lines ["*STEP" "*STATIC" "*END STEP"]))))
