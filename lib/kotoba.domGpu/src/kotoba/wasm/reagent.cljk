(ns kotoba.wasm.reagent
  "Small Reagent-shaped facade over kotoba.wasm.dom.
   It accepts ordinary Hiccup/Reagent-style vectors and produces a virtual DOM
   document that can be committed to a WASM host."
  (:refer-clojure :exclude [atom])
  (:require [kotoba.lang.text] [kotoba.wasm.dom :as dom]))

(defn atom
  ([] (clojure.core/atom nil))
  ([x] (clojure.core/atom x)))

(defn- attrs? [x]
  (map? x))

(defn- normalize-class [v]
  (cond
    (keyword? v) (name v)
    (sequential? v) (->> v (remove nil?) (map normalize-class) (kotoba.lang.text/join " "))
    :else v))

(defn- parse-tag [tag]
  (let [s (name tag)
        tag-name (or (second (re-find #"^([^.#]+)" s)) "div")
        id (second (re-find #"#([^.#]+)" s))
        classes (map second (re-seq #"\.([^.#]+)" s))]
    [(keyword tag-name)
     (cond-> {}
       id (assoc :id id)
       (seq classes) (assoc :class (kotoba.lang.text/join " " classes)))]))

(defn- merge-class [a b]
  (normalize-class (remove nil? [a b])))

(defn- merge-attrs [tag-attrs attrs]
  (-> (merge tag-attrs attrs)
      (cond-> (and (:class tag-attrs) (:class attrs))
        (assoc :class (merge-class (:class tag-attrs) (:class attrs))))))

(defn- add-attrs [document node-id attrs register-handler!]
  (reduce-kv
   (fn [document k v]
     (cond
       (= k :style) (dom/set-style document node-id v)
       (= k :class) (dom/set-attribute document node-id :class (normalize-class v))
       (and (keyword? k) (kotoba.lang.text/starts-with? (name k) "on-"))
       (let [handler-id (register-handler! v)]
         (dom/add-event-listener document node-id (subs (name k) 3) handler-id))
       :else (dom/set-attribute document node-id k v)))
   document
   attrs))

(declare render-node)

(defn- child-seq [children]
  (mapcat (fn [child]
            (cond
              (or (nil? child) (false? child)) []
              (seq? child) child
              :else [child]))
          children))

(defn- render-element [document register-handler! tag xs]
  (let [[tag tag-attrs] (parse-tag tag)
        [attrs children] (if (attrs? (first xs))
                           [(first xs) (rest xs)]
                           [nil xs])
        attrs (merge-attrs tag-attrs attrs)
        [node-id document] (dom/create-element document tag)
        document (if attrs (add-attrs document node-id attrs register-handler!) document)
        document (reduce
                  (fn [document child]
                    (let [[child-id document] (render-node document register-handler! child)]
                      (dom/append-child document node-id child-id)))
                  document
                  (child-seq children))]
    [node-id document]))

(defn render-node [document register-handler! node]
  (cond
    (nil? node) (dom/create-text-node document "")
    (string? node) (dom/create-text-node document node)
    (number? node) (dom/create-text-node document node)
    (keyword? node) (dom/create-text-node document (name node))
    (seq? node) (render-node document register-handler! (vec node))
    (vector? node)
    (let [head (first node)]
      (cond
        (keyword? head) (render-element document register-handler! head (rest node))
        (fn? head) (render-node document register-handler! (apply head (rest node)))
        :else (dom/create-text-node document (pr-str node))))
    :else (dom/create-text-node document (str node))))

(defn as-element [hiccup]
  hiccup)

(defn render
  "Render Hiccup/Reagent-style UI into a fresh virtual document.
   Returns {:document doc :handlers {handler-id f} :ops [...] :root id}."
  [hiccup]
  (let [handlers (clojure.core/atom {})
        next-handler-id (clojure.core/atom 1)
        register-handler! (fn [f]
                            (let [id @next-handler-id]
                              (swap! next-handler-id inc)
                              (swap! handlers assoc id f)
                              id))
        [root-id document] (render-node dom/empty-document register-handler! hiccup)
        document (dom/set-root document root-id)]
    {:document document
     :handlers @handlers
     :root root-id
     :ops (:ops document)}))
