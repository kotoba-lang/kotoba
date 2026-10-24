(ns openapi.validate
  "Structural validation of an OpenAPI-3-as-EDN model. Pure: returns a vector of
  problem maps `{:openapi/severity :error|:warn :openapi/code … :openapi/id … :openapi/msg …}`
  so a caller decides how to surface them. `valid?` is true iff there are no
  :error-level problems (warnings are advisory)."
  (:require [kotoba.lang.text :as str]
            [openapi.model :as m]))

(defn- problem [severity code id msg]
  {:openapi/severity severity :openapi/code code :openapi/id id :openapi/msg msg})

(defn problems
  "Return a vector of structural problems with `model`."
  [model]
  (let [ops (m/operations model)
        ps  (transient [])]

    ;; 1. Duplicate operationId across all operations -> :error
    (let [seen (atom #{})]
      (doseq [{:keys [op]} ops]
        (when-let [oid (:openapi/operation-id op)]
          (if (contains? @seen oid)
            (conj! ps (problem :error :op/duplicate-id oid
                               (str "duplicate operationId: " oid)))
            (swap! seen conj oid)))))

    ;; 2. Every {param} in path template must be declared as in:path required parameter -> :error
    (doseq [{:keys [path method op]} ops]
      (let [tpl-params      (m/path-params path)
            declared-names  (->> (m/parameters-for op)
                                 (filter #(= :path (:openapi/in %)))
                                 (map :openapi/name)
                                 set)
            op-id           (get op :openapi/operation-id (str (name method) " " path))]
        (doseq [pp tpl-params]
          (when-not (contains? declared-names pp)
            (conj! ps (problem :error :param/undeclared-path-param op-id
                               (str "path param {" pp "} in " path
                                    " not declared as in:path parameter")))))))

    ;; 3. Each operation has >=1 response -> :error
    (doseq [{:keys [path method op]} ops]
      (when (empty? (:openapi/responses op))
        (conj! ps (problem :error :op/no-responses
                           (get op :openapi/operation-id (str (name method) " " path))
                           (str "operation " (name method) " " path " has no responses")))))

    ;; 4. Local $ref "#/components/..." resolves -> :error if not found
    ;; 5. External $ref (not starting with "#") -> :warn
    (doseq [{:keys [op]} ops]
      (doseq [param (m/parameters-for op)]
        (when-let [ref (get param :$ref)]
          (cond
            (str/starts-with? ref "#/")
            (let [parts (str/split (subs ref 2) #"/")
                  val   (get-in model (mapv keyword parts))]
              (when (nil? val)
                (conj! ps (problem :error :ref/unresolved ref
                                   (str "$ref " ref " not found in model")))))

            (not (str/starts-with? ref "#"))
            (conj! ps (problem :warn :ref/external ref
                               (str "external $ref cannot be resolved locally: " ref)))))))

    (persistent! ps)))

(defn errors
  "Return only the :error-severity problems."
  [model]
  (filterv #(= :error (:openapi/severity %)) (problems model)))

(defn valid?
  "True iff `model` has no :error-level structural problems."
  [model]
  (empty? (errors model)))
