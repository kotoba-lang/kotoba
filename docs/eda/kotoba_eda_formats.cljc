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

(defn workflow-inputs
  "Return the file-format ids expected around a workbench stage."
  [registry stage direction]
  (->> (by-stage registry stage)
       (filter #(or (= direction (:eda.format/direction %))
                    (= :input-output (:eda.format/direction %))))
       (mapv :eda.format/id)))

(defn manufacturing-formats
  [registry]
  (->> (formats registry)
       (filter #(some #{(:eda.format/kind %)} [:layout :test-pattern :report]))
       (filter #(some #{:tapeout :mask :probe :final} (:eda.format/stages %)))
       (mapv :eda.format/id)))
