(ns comfyui.workflow
  "Workflow data model — ComfyUI **API format** compatible.

  A workflow is a map of node-id (string) → node instance:

    {\"1\" {:class_type \"Primitive\" :inputs {:value 2}}
     \"2\" {:class_type \"Primitive\" :inputs {:value 3}}
     \"3\" {:class_type \"Add\" :inputs {:a [\"1\" 0] :b [\"2\" 0]}}}

  An input value is either a constant or a link [node-id output-index]
  — exactly ComfyUI's JSON prompt format with EDN keys."
  (:require [comfyui.node :as node]))

(defn link?
  "[node-id output-index]?"
  [v]
  (and (vector? v) (= 2 (count v)) (string? (first v)) (nat-int? (second v))))

(defn dependencies
  "Node ids this node links from."
  [workflow node-id]
  (->> (get-in workflow [node-id :inputs])
       vals
       (filter link?)
       (map first)
       distinct
       vec))

(defn topo-sort
  "Topological order of the workflow's node ids (deterministic:
  lexicographic among ready nodes). Throws on cycles."
  [workflow]
  (let [ids (sort (keys workflow))]
    (loop [order [], done #{}, remaining (vec ids)]
      (if (empty? remaining)
        order
        (let [ready (filter (fn [id]
                              (every? done (dependencies workflow id)))
                            remaining)]
          (when (empty? ready)
            (throw (ex-info "Cycle in workflow" {:remaining remaining})))
          (recur (into order ready)
                 (into done ready)
                 (vec (remove (set ready) remaining))))))))

(defn ancestors-of
  "node-id plus all its transitive dependencies."
  [workflow node-id]
  (loop [seen #{} frontier [node-id]]
    (if (empty? frontier)
      seen
      (let [fresh (remove seen frontier)]
        (recur (into seen fresh)
               (vec (mapcat #(dependencies workflow %) fresh)))))))

(defn validate
  "Validates a workflow against a node registry. Returns
  {:valid? bool :errors [{:node id :error kw …} …]}. Checks: known
  class_type, links point at existing nodes/outputs, link types match
  declared input types (\"*\" is a wildcard), required inputs present,
  constant values structurally match, no cycles."
  [reg workflow]
  (let [errors
        (vec
         (concat
          (mapcat
           (fn [[id {:keys [class_type inputs]}]]
             (if-let [t (node/get-type reg class_type)]
               (concat
                ;; required inputs present
                (for [[in-name _] (node/required-inputs t)
                      :when (not (contains? inputs in-name))]
                  {:node id :error :missing-input :input in-name})
                ;; each provided input
                (for [[in-name v] inputs
                      :let [spec (get-in t [:inputs in-name])
                            err
                            (cond
                              (nil? spec)
                              {:error :unknown-input :input in-name}

                              (link? v)
                              (let [[src idx] v
                                    src-type (node/get-type reg (get-in workflow [src :class_type]))]
                                (cond
                                  (not (contains? workflow src))
                                  {:error :dangling-link :input in-name :link v}

                                  (>= idx (count (:outputs src-type)))
                                  {:error :no-such-output :input in-name :link v}

                                  (let [ot (get-in src-type [:outputs idx :type])]
                                    (and ot (:type spec)
                                         (not= "*" ot) (not= "*" (:type spec))
                                         (not= ot (:type spec))))
                                  {:error :type-mismatch :input in-name :link v
                                   :expected (:type spec)
                                   :actual (get-in src-type [:outputs idx :type])}))

                              (not (node/validate-type (:type spec) v))
                              {:error :bad-value :input in-name :value v
                               :expected (:type spec)})]
                      :when err]
                  (assoc err :node id)))
               [{:node id :error :unknown-class :class_type class_type}]))
           workflow)
          (try (topo-sort workflow) []
               (catch #?(:clj Exception :cljs :default) e
                 [{:error :cycle :nodes (:remaining (ex-data e))}]))))]
    {:valid? (empty? errors) :errors errors}))

(defn output-nodes
  "Ids of nodes whose type declares :output-node? true."
  [reg workflow]
  (vec (for [[id {:keys [class_type]}] (sort-by key workflow)
             :when (:output-node? (node/get-type reg class_type))]
         id)))
