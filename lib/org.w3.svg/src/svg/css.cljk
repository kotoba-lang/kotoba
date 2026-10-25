(ns svg.css
  "CSS as EDN for SVG. Similar to kami.css / shadow-css authoring: style maps,
  rules, @keyframes, and inline <style> hiccup."
  (:require [kotoba.lang.text :as str]))

(def unitless
  #{:opacity :fill-opacity :stroke-opacity :stop-opacity :font-weight
    :line-height :z-index :order :flex :flex-grow :flex-shrink})

(defn prop-name [p]
  (name p))

(defn value
  "Render a CSS value. Numbers become px except for unitless props and 0."
  [prop v]
  (cond
    (nil? v) nil
    (false? v) nil
    (number? v) (if (or (unitless prop) (zero? v)) (str v) (str v "px"))
    (keyword? v) (name v)
    (vector? v) (str/join " " (keep #(value prop %) v))
    :else (str v)))

(defn style
  "Inline cssText from an EDN map."
  [m]
  (->> m
       (keep (fn [[k v]]
               (when-let [vv (value k v)]
                 (str (prop-name k) ": " vv ";"))))
       (str/join " ")))

(defn rule [selector m]
  (str selector " { " (style m) " }"))

(defn kf [name frames]
  (str "@keyframes " (clojure.core/name name) " { "
       (str/join " "
                 (for [[at m] frames]
                   (str at "% { " (style m) " }")))
       " }"))

(defn css
  "Render a stylesheet from {:rules {selector decls} :keyframes {name frames}}."
  [{:keys [rules keyframes]}]
  (str/join "\n"
            (concat
             (for [[sel m] rules] (rule sel m))
             (for [[nm frames] keyframes] (kf nm frames)))))

(defn style-node [sheet]
  [:style [:svg/raw (css sheet)]])
