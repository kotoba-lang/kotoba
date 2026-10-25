(ns svg.core
  "EDN-first SVG document helpers.

  The canonical element shape is Hiccup-like:

    [:svg {:viewBox \"0 0 10 10\"} [:rect {:width 10 :height 10}]]

  This namespace renders that shape deterministically and keeps the data small
  enough to pass through kotoba CLJ/EDN pipelines."
  (:require [kotoba.lang.text :as str]))

(def svg-ns "http://www.w3.org/2000/svg")

(def void-tags
  "SVG elements that are conventionally emitted without children when empty."
  #{:path :rect :circle :ellipse :line :polyline :polygon :use :image :stop})

(defn element?
  "True when x has the canonical [:tag attrs? child*] element shape."
  [x]
  (and (vector? x)
       (keyword? (first x))
       (not= :svg/raw (first x))))

(defn- parse-tag
  "':g.layer#main' -> [:g {:class \"layer\" :id \"main\"}]."
  [kw]
  (let [s (name kw)
        id (second (re-find #"#([^.#]+)" s))
        classes (map second (re-seq #"\.([^.#]+)" s))
        tag (or (second (re-find #"^([^.#]+)" s)) "g")]
    [(keyword tag)
     (cond-> {}
       (seq classes) (assoc :class (str/join " " classes))
       id (assoc :id id))]))

(defn class-str [v]
  (cond
    (string? v) v
    (coll? v) (str/join " " (map #(if (keyword? %) (name %) (str %)) (filter identity v)))
    (keyword? v) (name v)
    :else (str v)))

(defn attrs
  "Return the attribute map for an element, or {} when absent."
  [el]
  (let [[_ sugar] (parse-tag (first el))
        x (second el)]
    (merge-with (fn [a b] (str (class-str a) " " (class-str b)))
                sugar
                (if (map? x) x {}))))

(defn children
  "Return element children, skipping the optional attrs map."
  [el]
  (let [xs (next el)]
    (if (map? (first xs)) (rest xs) xs)))

(defn el
  "Construct an SVG element. Attrs are optional."
  [tag & body]
  (let [[a cs] (if (map? (first body))
                 [(first body) (rest body)]
                 [{} body])]
    (into [(keyword tag) a] cs)))

(defn svg
  "Construct a root SVG element. Adds xmlns when absent."
  [attrs & children]
  (into [:svg (merge {:xmlns svg-ns} attrs)] children))

(defn esc
  "Escape &, <, >, \" for safe SVG/XML text or attributes."
  [s]
  (-> (str s)
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")
      (str/replace "\"" "&quot;")))

(defn- escape-text [s]
  (-> (str s)
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")))

(defn- kebab-name [k]
  (-> (name k)
      (str/replace #"([a-z0-9])([A-Z])" "$1-$2")
      (str/lower)))

(def ^:private case-sensitive-attrs
  #{:attributeName :attributeType :baseFrequency :calcMode :clipPathUnits
    :diffuseConstant :edgeMode :filterUnits :glyphRef :gradientTransform
    :gradientUnits :kernelMatrix :kernelUnitLength :keyPoints :keySplines
    :keyTimes :lengthAdjust :limitingConeAngle :markerHeight :markerUnits
    :markerWidth :maskContentUnits :maskUnits :numOctaves :pathLength
    :patternContentUnits :patternTransform :patternUnits :pointsAtX
    :pointsAtY :pointsAtZ :preserveAlpha :preserveAspectRatio
    :primitiveUnits :refX :refY :repeatCount :repeatDur :requiredExtensions
    :requiredFeatures :specularConstant :specularExponent :spreadMethod
    :startOffset :stdDeviation :stitchTiles :surfaceScale :systemLanguage
    :tableValues :targetX :targetY :textLength :viewBox :xChannelSelector
    :yChannelSelector})

(defn- valid-attr-name?
  "True when `s` is safe to splice directly into `<tag NAME=\"value\">` markup.
  Letters/digits/`_`/`-`/`.`/`:` cover every real SVG/HTML attribute name
  (including namespaced ones like `xlink:href`) while excluding whitespace,
  `\"` `'` `=` `<` `>` `/` -- the characters that would let an attribute
  NAME (as opposed to its value, which `esc` already covers) break out of
  the attribute/tag syntax and inject arbitrary additional markup."
  [s]
  (boolean (re-matches #"[A-Za-z0-9_:.-]+" s)))

(defn- attr-name [k]
  (let [n (if (contains? case-sensitive-attrs k) (name k) (kebab-name k))]
    (when-not (valid-attr-name? n)
      (throw (ex-info "svg: attribute name contains characters unsafe to
                        splice into markup (only letters/digits/_-.: allowed)"
                       {:name n})))
    n))

(defn style
  "Render an EDN style map to CSS declaration text."
  [m]
  (->> m
       (remove (comp nil? val))
       (remove (comp false? val))
       (map (fn [[k v]] (str (kebab-name k) ":" v ";")))
       (str/join "")))

(defn attr-value [v]
  (cond
    (keyword? v) (name v)
    :else v))

(defn normalize-attrs
  "Drop nil/false attrs and render style maps. Boolean true becomes the attr name."
  [m]
  (into (sorted-map)
        (keep (fn [[k v]]
                (cond
                  (or (nil? v) (false? v)) nil
                  (= k :class) [k (class-str v)]
                  (= k :style) [k (if (map? v) (style v) v)]
                  (true? v) [k (name k)]
                  :else [k (attr-value v)])))
        m))

(declare render-node)

(defn render-attrs [m]
  (let [pairs (normalize-attrs m)]
    (if (empty? pairs)
      ""
      (str " "
           (str/join " "
                     (map (fn [[k v]]
                            (str (attr-name k) "=\"" (esc v) "\""))
                          pairs))))))

(defn render-node
  "Render a text node or element to SVG/XML."
  [node]
  (cond
    (nil? node) ""
    (and (vector? node) (= :svg/raw (first node)))
    (str (second node))
    (and (vector? node) (vector? (first node)))
    (apply str (map render-node node))
    (element? node)
    (let [[tag _] (parse-tag (first node))
          as (attrs node)
          cs (remove nil? (children node))
          open (str "<" (name tag) (render-attrs as))]
      (if (empty? cs)
        (if (contains? void-tags tag)
          (str open "/>")
          (str open "></" (name tag) ">"))
        (str open ">"
             (apply str (map render-node cs))
             "</" (name tag) ">")))
    :else (escape-text node)))

(defn render
  "Render an SVG EDN tree to XML text."
  [doc]
  (render-node doc))

(defn walk
  "Depth-first walk over element nodes."
  [f node]
  (when (element? node)
    (f node)
    (doseq [c (children node)]
      (walk f c))))

(defn elements
  "Return all element nodes in depth-first order."
  [doc]
  (let [acc (atom [])]
    (walk #(swap! acc conj %) doc)
    @acc))

(defn validate
  "Return {:valid? boolean :errors [...]}. This is structural validation, not
  full SVG schema validation."
  [doc]
  (let [errors (cond-> []
                 (not (element? doc))
                 (conj {:path [] :error :expected-element})

                 (and (element? doc) (not= :svg (first doc)))
                 (conj {:path [] :error :expected-root-svg})

                 (and (element? doc) (not= svg-ns (:xmlns (attrs doc))))
                 (conj {:path [] :error :missing-svg-xmlns}))]
    {:valid? (empty? errors)
     :errors errors}))

(defn datafy
  "Normalize a tree to explicit attrs maps and normalized root xmlns."
  [node]
  (cond
    (element? node)
    (let [[tag _] (parse-tag (first node))
          as (if (= :svg tag)
               (merge {:xmlns svg-ns} (attrs node))
               (attrs node))]
      (into [tag as] (map datafy (children node))))
    :else node))
