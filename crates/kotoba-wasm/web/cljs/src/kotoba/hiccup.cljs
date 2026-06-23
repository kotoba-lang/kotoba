(ns kotoba.hiccup
  "Tiny dependency-free hiccup → DOM renderer (no React/Reagent). Enough for the
   sovereign editor UI to be written as Clojure data:

     [:input#title.big {:placeholder \"…\" :value v :oninput f} children…]

   - tag shorthand: :tag#id.class1.class2
   - attrs map (optional 2nd element): :value sets the property; :onX adds an event
     listener for event X (e.g. :onclick → \"click\"); others → setAttribute
   - children: strings/numbers, nested vectors, seqs, nils (skipped)."
  (:require [clojure.string :as str]))

(defn- parse-tag [t]
  (let [s (name t)
        dot (str/split s #"\.")
        tag+id (first dot)
        classes (rest dot)
        hash (str/split tag+id #"#")]
    [(first hash) (second hash) (vec classes)]))

(declare ->dom)

(defn- append-child! [^js node child]
  (cond
    (nil? child) nil
    (seq? child) (doseq [c child] (append-child! node c))
    :else (.appendChild node (->dom child))))

(defn ->dom
  "Render a hiccup form to a DOM Node."
  [form]
  (cond
    (string? form) (js/document.createTextNode form)
    (number? form) (js/document.createTextNode (str form))
    (nil? form)    (js/document.createTextNode "")
    (vector? form)
    (let [[t & more] form
          [tag id classes] (parse-tag t)
          [attrs children] (if (map? (first more)) [(first more) (rest more)] [nil more])
          node (js/document.createElement tag)]
      (when id (set! (.-id node) id))
      (when (seq classes) (set! (.-className node) (str/join " " classes)))
      (doseq [[k v] attrs]
        (let [kn (name k)]
          (cond
            (nil? v) nil
            (and (fn? v) (str/starts-with? kn "on"))
            (.addEventListener node (subs kn 2) v)
            (= :value k) (set! (.-value node) (or v ""))
            :else (.setAttribute node kn (str v)))))
      (doseq [c children] (append-child! node c))
      node)
    :else (js/document.createTextNode (str form))))

(defn mount!
  "Replace the contents of `target` (id string or Node) with the rendered hiccup."
  [target form]
  (let [t (if (string? target) (js/document.getElementById target) target)]
    (set! (.-innerHTML t) "")
    (.appendChild t (->dom form))
    t))
