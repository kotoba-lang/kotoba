(ns kotoba.eda.formats
  "Data-driven EDA file-format registry.

  This follows kotoba-lang repositories such as kasane, utsushi, bpmn, openapi,
  ddl, statechart and vllm: file formats are described as EDN data, while CLJC
  provides pure query/normalization functions. Parsers and external tools are
  host-injected adapters, not hidden side effects."
  (:require [clojure.string :as str]))

(def empty-registry
  {:schema 1
   :classes []})

(defn formats
  [registry]
  (:classes registry))

(defn software
  [registry]
  (:software registry))

(defn operations
  [registry]
  (:operations registry))

(defn converters
  [registry]
  (:converter-pipelines registry))

(defn by-id
  [coll id-key id]
  (first (filter #(= id (id-key %)) coll)))

(defn format-by-id
  [registry format-id]
  (by-id (formats registry) :eda.format/id format-id))

(defn software-by-id
  [registry software-id]
  (by-id (software registry) :eda.software/id software-id))

(defn operation-by-id
  [registry operation-id]
  (by-id (operations registry) :eda.operation/id operation-id))

(defn converter-by-id
  [registry converter-id]
  (by-id (converters registry) :eda.converter/id converter-id))

(defn extension
  [path]
  (let [name (last (str/split (str path) #"/"))
        i (.lastIndexOf name ".")]
    (when (pos? i)
      (str/lower-case (subs name i)))))

(defn by-extension
  [registry ext-or-path]
  (let [ext (if (str/starts-with? (str ext-or-path) ".")
              (str/lower-case (str ext-or-path))
              (extension ext-or-path))]
    (filter #(some #{ext} (:eda.format/extensions %)) (formats registry))))

(defn by-stage
  [registry stage]
  (filter #(some #{stage} (:eda.format/stages %)) (formats registry)))

(defn by-kind
  [registry kind]
  (filter #(= kind (:eda.format/kind %)) (formats registry)))

(defn operation-applies?
  [format-id operation]
  (some #{format-id} (:eda.operation/applies-to operation)))

(defn converter-applies?
  [format-id converter]
  (some #{format-id} (:eda.converter/formats converter)))

(defn operations-for-format
  [registry format-id]
  (filter #(operation-applies? format-id %) (operations registry)))

(defn converters-for-format
  [registry format-id]
  (filter #(converter-applies? format-id %) (converters registry)))

(defn software-for-format
  [registry format-id]
  (let [converter-software (->> (converters-for-format registry format-id)
                                (mapcat :eda.converter/software)
                                distinct
                                vec)
        op-ids (set (map :eda.operation/id (operations-for-format registry format-id)))
        fallback-software (->> (software registry)
                               (filter (fn [sw]
                                         (some op-ids (:eda.software/operations sw))))
                               (map :eda.software/id)
                               distinct
                               vec)
        ids (if (seq converter-software) converter-software fallback-software)]
    (keep #(software-by-id registry %) ids)))

(defn format-manifest
  "Create the EDN manifest datom for one external EDA artifact.
  `cid` is supplied by the kotoba object store / multiformats layer."
  [registry {:keys [path cid bytes sha256 role]}]
  (let [matches (vec (by-extension registry path))
        fmt (first matches)]
    {:eda.artifact/path path
     :eda.artifact/cid cid
     :eda.artifact/bytes bytes
     :eda.artifact/sha256 sha256
     :eda.artifact/role role
     :eda.artifact/format (:eda.format/id fmt)
     :eda.artifact/format-candidates (mapv :eda.format/id matches)
     :eda.artifact/canonical-edn (:eda.format/canonical-edn fmt)
     :eda.artifact/parser (:eda.format/parser fmt)
     :eda.artifact/policy (:eda.format/policy fmt)
     :eda.artifact/datoms (:eda.format/datoms fmt)}))

(defn edn-hub-conversion-plan
  "Plan how an artifact enters the kotoba EDA EDN hub.
  Returns data only. Hosts turn :eda.plan/software and :eda.plan/steps into
  sandboxed tool executions."
  [registry artifact]
  (let [manifest (format-manifest registry artifact)
        format-id (:eda.artifact/format manifest)
        fmt (format-by-id registry format-id)
        convs (vec (converters-for-format registry format-id))
        sw (vec (software-for-format registry format-id))]
    (assoc manifest
           :eda.plan/hub :edn
           :eda.plan/format fmt
           :eda.plan/software (mapv :eda.software/id sw)
           :eda.plan/operations (mapv :eda.operation/id (operations-for-format registry format-id))
           :eda.plan/converters (mapv :eda.converter/id convs)
           :eda.plan/canonical-edn (:eda.format/canonical-edn fmt)
           :eda.plan/default-result (:eda.converter/result (first convs)))))

(defn converter-expanded
  [registry converter-id]
  (let [conv (converter-by-id registry converter-id)]
    (assoc conv
           :eda.converter/software*
           (mapv #(software-by-id registry %) (:eda.converter/software conv))
           :eda.converter/steps*
           (mapv #(operation-by-id registry %) (:eda.converter/steps conv)))))

(defn workflow-inputs
  "Return the file-format ids expected around a workbench stage."
  [registry stage direction]
  (->> (by-stage registry stage)
       (filter #(or (= direction (:eda.format/direction %))
                    (= :input-output (:eda.format/direction %))))
       (mapv :eda.format/id)))

(defn stage-operation-matrix
  [registry stage]
  (->> (by-stage registry stage)
       (map (fn [fmt]
              [(:eda.format/id fmt)
               {:software (mapv :eda.software/id (software-for-format registry (:eda.format/id fmt)))
                :operations (mapv :eda.operation/id (operations-for-format registry (:eda.format/id fmt)))
                :converters (mapv :eda.converter/id (converters-for-format registry (:eda.format/id fmt)))}]))
       (into {})))

(defn manufacturing-formats
  [registry]
  (->> (formats registry)
       (filter #(some #{(:eda.format/kind %)} [:layout :test-pattern :report]))
       (filter #(some #{:tapeout :mask :probe :final} (:eda.format/stages %)))
       (mapv :eda.format/id)))
