(ns kotoba.lang.kami-nv-compat.kami-usd.index
  "kami-usd — clean-room USD layer. Portable .cljc port of
  src/kami-usd/index.ts. Wave 30 (closes kami-usd).

  The canonical KAMI engine behind the nv-compat/omni-usd API-compat
  facade. Parses the USDA (ASCII USD) geometry subset and flattens it into
  kami-rt triangles + kami-rtx materials.

  Most of index.ts is TS re-export bookkeeping with no CLJC equivalent —
  callers require kami-usd.usda / kami-usd.geom directly. This namespace
  ports only the real logic: usda->flat-scene / usda->scene /
  usda->path-scene.

  ADR-2605261800 SD6 / D10.4 kami-usd."
  (:require [kotoba.lang.kami-nv-compat.kami-usd.usda :as usda]
            [kotoba.lang.kami-nv-compat.kami-usd.geom :as geom]
            [kotoba.lang.kami-nv-compat.kami-rt.index :as kami-rt]
            [kotoba.lang.kami-nv-compat.kami-rt.pathtrace :as pt]))

(defn usda->flat-scene
  "Parse a USDA document and flatten it to world-space triangles + materials."
  [text]
  (geom/flatten-stage (usda/parse-usda text)))

(defn usda->scene
  "Parse a USDA document into a kami-rt ray-trace Scene."
  [text]
  (kami-rt/build-scene (:triangles (usda->flat-scene text))))

(defn usda->path-scene
  "Parse a USDA document into a kami-rtx path-trace PathScene (geometry +
  materials)."
  [text]
  (let [flat (usda->flat-scene text)]
    (pt/build-path-scene (:triangles flat) (:materials flat))))
