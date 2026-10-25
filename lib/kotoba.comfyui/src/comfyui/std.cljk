(ns comfyui.std
  "Standard node pack — pure-data primitives (the engine demo set;
  heavy media nodes belong to host-specific packs that close over
  injected capabilities, see `host-fn-node`)."
  (:require [kotoba.lang.text :as str]))

(def primitive-int
  {:type "PrimitiveInt" :category "primitive"
   :inputs {:value {:type "INT" :default 0}}
   :outputs [{:name "value" :type "INT"}]
   :fn (fn [{:keys [value]}] [value])})

(def primitive-float
  {:type "PrimitiveFloat" :category "primitive"
   :inputs {:value {:type "FLOAT" :default 0.0}}
   :outputs [{:name "value" :type "FLOAT"}]
   :fn (fn [{:keys [value]}] [value])})

(def primitive-string
  {:type "PrimitiveString" :category "primitive"
   :inputs {:value {:type "STRING" :default ""}}
   :outputs [{:name "value" :type "STRING"}]
   :fn (fn [{:keys [value]}] [value])})

(def add
  {:type "Add" :category "math"
   :inputs {:a {:type "INT" :default 0} :b {:type "INT" :default 0}}
   :outputs [{:name "sum" :type "INT"}]
   :fn (fn [{:keys [a b]}] [(+ a b)])})

(def multiply
  {:type "Multiply" :category "math"
   :inputs {:a {:type "INT" :default 1} :b {:type "INT" :default 1}}
   :outputs [{:name "product" :type "INT"}]
   :fn (fn [{:keys [a b]}] [(* a b)])})

(def divmod
  {:type "DivMod" :category "math"
   :inputs {:a {:type "INT"} :b {:type "INT" :default 1}}
   :outputs [{:name "quot" :type "INT"} {:name "rem" :type "INT"}]
   :fn (fn [{:keys [a b]}] [(quot a b) (rem a b)])})

(def concat-text
  {:type "ConcatText" :category "text"
   :inputs {:a {:type "STRING" :default ""}
            :b {:type "STRING" :default ""}
            :separator {:type "STRING" :default "" :optional true}}
   :outputs [{:name "text" :type "STRING"}]
   :fn (fn [{:keys [a b separator]}] [(str a separator b)])})

(def upper-case-text
  {:type "UpperCase" :category "text"
   :inputs {:text {:type "STRING"}}
   :outputs [{:name "text" :type "STRING"}]
   :fn (fn [{:keys [text]}] [(str/upper text)])})

(def format-text
  {:type "FormatText" :category "text"
   :inputs {:template {:type "STRING"}
            :a {:type "*" :optional true}
            :b {:type "*" :optional true}}
   :outputs [{:name "text" :type "STRING"}]
   :fn (fn [{:keys [template a b]}]
         [(-> template
              (str/replace "{a}" (str a))
              (str/replace "{b}" (str b)))])})

(def preview
  "OUTPUT_NODE equivalent — marks a result as a workflow output."
  {:type "Preview" :category "output"
   :output-node? true
   :inputs {:value {:type "*"}}
   :outputs [{:name "value" :type "*"}]
   :fn (fn [{:keys [value]}] [value])})

(defn host-fn-node
  "Wraps an injected host capability as a node type — the langchain-clj
  pattern for I/O-bound or heavy work (image decode, diffusion sampler,
  …). `f` receives the resolved input map, returns the outputs vector.

    (host-fn-node {:type \"LoadImage\" :category \"image\"
                   :inputs {:path {:type \"STRING\"}}
                   :outputs [{:name \"image\" :type \"IMAGE\"}]}
                  host-load-image)"
  [node-type f]
  (assoc node-type :fn f))

(def all
  [primitive-int primitive-float primitive-string
   add multiply divmod
   concat-text upper-case-text format-text
   preview])
