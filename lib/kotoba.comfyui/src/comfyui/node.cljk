(ns comfyui.node
  "Node-type registry — the ComfyUI NODE_CLASS_MAPPINGS equivalent.

  A node type is a plain map (INPUT_TYPES / RETURN_TYPES / FUNCTION /
  CATEGORY in ComfyUI terms):

    {:type     \"Add\"                       ; class_type
     :category \"math\"
     :inputs   {:a {:type \"INT\" :default 0}
                :b {:type \"INT\" :default 0}
                :note {:type \"STRING\" :optional true}}
     :outputs  [{:name \"result\" :type \"INT\"}]
     :output-node? false                     ; OUTPUT_NODE
     :fn (fn [{:keys [a b]}] [(+ a b)])}     ; returns a vector of outputs

  `:fn` receives the resolved input map and returns the outputs as a
  vector (ComfyUI returns tuples); a non-vector return is wrapped as a
  single output. Heavy host work (diffusion, image codecs, …) follows
  the langchain-clj pattern: close over injected host capabilities
  when constructing the node type."
  (:require [kotoba.lang.text :as str]))

(defn registry
  "Creates a node-type registry (atom of type-name → node-type)."
  ([] (registry []))
  ([node-types]
   (let [reg (atom {})]
     (doseq [t node-types] (swap! reg assoc (:type t) t))
     reg)))

(defn register!
  "Registers one node type (or a sequence — a \"node pack\")."
  [reg node-type-or-pack]
  (doseq [t (if (sequential? node-type-or-pack) node-type-or-pack [node-type-or-pack])]
    (when-not (and (string? (:type t)) (ifn? (:fn t)))
      (throw (ex-info "Node type needs :type (string) and :fn" {:node-type t})))
    (swap! reg assoc (:type t) t))
  reg)

(defn get-type [reg type-name]
  (get @reg type-name))

(defn object-info
  "Registry as data — the /object_info endpoint equivalent
  (everything except :fn, keyed by class_type)."
  [reg]
  (into (sorted-map)
        (map (fn [[k v]] [k (dissoc v :fn)]))
        @reg))

(defn categories [reg]
  (->> (vals @reg) (keep :category) distinct sort vec))

(defn required-inputs [node-type]
  (into {}
        (remove (fn [[_ spec]] (or (:optional spec) (contains? spec :default))))
        (:inputs node-type)))

(defn output-types [node-type]
  (mapv :type (:outputs node-type)))

(defn validate-type
  "Cheap structural check of a constant value against a ComfyUI type
  string. Unknown types (and \"*\") always pass."
  [type-str v]
  (case type-str
    "INT" (int? v)
    "FLOAT" (number? v)
    "STRING" (string? v)
    "BOOLEAN" (boolean? v)
    true))
