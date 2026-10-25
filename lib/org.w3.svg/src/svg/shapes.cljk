(ns svg.shapes
  "Small SVG hiccup constructors. These return EDN vectors; render with
  svg.core/render or pass directly to reagent-like consumers."
  (:require [svg.core :as svg]))

(defn group [& body]
  (into [:g {}] body))

(defn rect
  ([x y width height] (rect x y width height {}))
  ([x y width height attrs]
   [:rect (merge {:x x :y y :width width :height height} attrs)]))

(defn circle
  ([cx cy r] (circle cx cy r {}))
  ([cx cy r attrs]
   [:circle (merge {:cx cx :cy cy :r r} attrs)]))

(defn line
  ([x1 y1 x2 y2] (line x1 y1 x2 y2 {}))
  ([x1 y1 x2 y2 attrs]
   [:line (merge {:x1 x1 :y1 y1 :x2 x2 :y2 y2} attrs)]))

(defn text
  ([x y s] (text x y s {}))
  ([x y s attrs]
   [:text (merge {:x x :y y} attrs) s]))

(defn path [d attrs]
  [:path (merge {:d d} attrs)])

(defn svg-symbol [id attrs & body]
  (into [:symbol (merge {:id id} attrs)] body))

(defn use-ref [href attrs]
  [:use (merge {:href href} attrs)])

(defn doc [attrs & body]
  (apply svg/svg attrs body))
