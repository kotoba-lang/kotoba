(ns html.core
  "Dependency-free Hiccup-compatible EDN to HTML renderer."
  (:require [kotoba.lang.text :as str]))

(defn esc
  "Escape &, <, >, and double quotes for HTML text/attribute context."
  [s]
  (-> (str s)
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")
      (str/replace "\"" "&quot;")))

(def void-tags
  #{"area" "base" "br" "col" "embed" "hr" "img" "input"
    "link" "meta" "param" "source" "track" "wbr"})

(def raw-text-tags #{"script" "style"})

(def preserve-whitespace-tags
  "Elements whose content is whitespace-significant, so the pretty-printer must
  not indent their children.

  `<pre>` and `<textarea>` render whitespace literally (HTML Standard: both are
  styled `white-space: pre` and `<textarea>`'s content is its raw value). The
  block-children indentation below would otherwise turn

      [:pre [:code \"ipfs pin remote ls\"]]

  into `<pre>\\n  <code>…` — a leading blank line plus two spaces of indent that
  a reader sees, and that a copy-paste carries. Same for a `<textarea>` whose
  value would silently gain surrounding whitespace.

  This is about the RENDERER's own formatting only; children are still escaped
  and rendered normally, just without injected newlines."
  #{"pre" "textarea"})

(defn raw
  "Mark trusted markup as unescaped. Never pass untrusted input."
  [value]
  [:hiccup/raw (str value)])

(defn parse-tag
  [kw]
  (let [s (name kw)
        id (second (re-find #"#([^.#]+)" s))
        classes (map second (re-seq #"\.([^.#]+)" s))
        tag (or (second (re-find #"^([^.#]+)" s)) "div")]
    [tag (cond-> {}
           (seq classes) (assoc :class (str/join " " classes))
           id (assoc :id id))]))

(defn class-str [v]
  (cond
    (string? v) v
    (keyword? v) (name v)
    (symbol? v) (name v)
    (coll? v) (str/join " " (map class-str (filter identity v)))
    :else (str v)))

(defn style-map->css
  [m]
  (->> m
       (keep (fn [[k v]]
               (when (and v (not (false? v)))
                 (str (name k) ":" (if (true? v) "true" v) ";"))))
       (str/join "")))

(defn render-attrs [attrs]
  (->> attrs
       (keep (fn [[k v]]
               (when (and v (not (false? v)))
                 (let [k (name k)]
                   (cond
                     (= k "class")
                     (str " " k "=\"" (esc (class-str v)) "\"")
                     (and (= k "style") (map? v))
                     (str " " k "=\"" (esc (style-map->css v)) "\"")
                     (true? v)
                     (str " " k)
                     :else
                     (str " " k "=\"" (esc v) "\""))))))
       (apply str)))

(declare ->html)
(declare render-node)

(defn- element-node? [x]
  (when (and (vector? x)
             (keyword? (first x))
             (not= :hiccup/raw (first x)))
    (let [[tag] (parse-tag (first x))]
      (not (contains? void-tags tag)))))

(defn- block-children? [children]
  (and (seq children)
       (every? element-node? children)))

(defn render-node
  ([node sb] (render-node node sb 0))
  ([node sb ind]
  (cond
    (nil? node) sb
    (string? node) (conj! sb (esc node))
    (number? node) (conj! sb (str node))
    (and (vector? node) (= :hiccup/raw (first node))) (conj! sb (str (second node)))
    (and (vector? node) (= :<> (first node)))
    (reduce (fn [s c] (render-node c s ind)) sb (rest node))
    (and (vector? node) (seq node) (vector? (first node)))
    (reduce (fn [s c] (render-node c s ind)) sb node)
    (vector? node)
    (let [[t & body] node
          [tag base] (parse-tag t)
          [attrs children] (if (map? (first body))
                             [(first body) (rest body)]
                             [{} body])
          attrs (merge-with (fn [a b] (str (class-str a) " " (class-str b))) base attrs)
          sb (conj! sb (str "<" tag (render-attrs attrs) ">"))]
      (if (contains? void-tags tag)
        sb
        (let [sb (if (contains? raw-text-tags tag)
                   (let [content (apply str (map (fn [child]
                                                   (if (and (vector? child)
                                                            (= :hiccup/raw (first child)))
                                                     (str (second child))
                                                     (str child)))
                                                 children))]
                     ;; HTML RAWTEXT terminates at the first case-insensitive </tag.
                     (when (re-find (re-pattern (str "(?i)</" tag)) content)
                       (throw (ex-info (str "html: raw-text content for <" tag
                                            "> contains a closing-tag breakout")
                                       {:tag tag})))
                     (conj! sb content))
                   (if (and (block-children? children)
                            (not (contains? preserve-whitespace-tags tag)))
                     (let [sb (reduce (fn [s child]
                                       (render-node child
                                                    (conj! (conj! s "\n")
                                                           (apply str (repeat (inc ind) "  ")))
                                                    (inc ind)))
                                     sb children)]
                       (conj! (conj! sb "\n") (apply str (repeat ind "  "))))
                     (reduce (fn [s child] (render-node child s ind)) sb children)))]
          (conj! sb (str "</" tag ">")))))
    (seq? node) (reduce (fn [s c] (render-node c s ind)) sb node)
    :else (conj! sb (esc node)))))

(defn ->html
  [node]
  (str/join (persistent! (render-node node (transient [])))))

(def render ->html)

(defn html
  "Render one or more hiccup forms to an HTML fragment."
  [& forms]
  (str/join "\n" (map ->html forms)))

(defn html5
  "Render a full HTML document, prepending <!DOCTYPE html>."
  [& body]
  (str "<!DOCTYPE html>\n" (apply html body)))
