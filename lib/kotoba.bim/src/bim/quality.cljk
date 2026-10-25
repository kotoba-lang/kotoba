(ns bim.quality
  "IDS validation and BCF review pipeline shared by BIM editor, CI, and
  cloud-itonami."
  (:require [bim.integration :as integration]
            [ifc.ids :as ids]
            [kotoba.issue.bcf :as bcf]))

(def contract-version 1)

(defn validate-project
  "Evaluate a BIM project through its canonical IFC exchange representation."
  [project ids-document]
  (ids/validate (integration/export-ifc project) ids-document))

(defn review
  "Validate a project and turn object-level failures into BCF topics."
  [project ids-document topic-options]
  (let [report (validate-project project ids-document)]
    {:bim.quality/version contract-version
     :bim.quality/pass? (:ids.report/pass? report)
     :bim.quality/ids-report report
     :bim.quality/bcf-topics (bcf/ids-report->topics report topic-options)}))

(defn- project-elements [project]
  (for [site (:sites project)
        building (:buildings site)
        storey (:storeys building)
        element (:elements storey)]
    [storey element]))

(defn element-by-global-id [project global-id]
  (some (fn [[storey element]]
          (when (= global-id (:global-id element))
            {:storey/id (:id storey) :element element}))
        (project-elements project)))

(defn viewpoint-editor-context
  "Resolve a BCF viewpoint into editor selection and camera state. Unknown
  external IFC components remain listed instead of being silently discarded."
  [project viewpoint]
  (let [components (:bcf.viewpoint/selected-components viewpoint)
        resolved (mapv (fn [component]
                         (assoc component :bim/resolution
                                (element-by-global-id project (:ifc-guid component))))
                       components)]
    {:bim.quality/viewpoint-guid (:bcf.viewpoint/guid viewpoint)
     :bim.quality/camera (:bcf.viewpoint/camera viewpoint)
     :bim.quality/selection
     (mapv #(get-in % [:bim/resolution :element :id])
           (filter :bim/resolution resolved))
     :bim.quality/storeys
     (mapv #(get-in % [:bim/resolution :storey/id])
           (filter :bim/resolution resolved))
     :bim.quality/unresolved-components
     (mapv #(dissoc % :bim/resolution) (remove :bim/resolution resolved))
     :bim.quality/default-visibility (:bcf.viewpoint/default-visibility viewpoint)
     :bim.quality/visibility-exceptions (:bcf.viewpoint/visibility-exceptions viewpoint)
     :bim.quality/clipping-planes (:bcf.viewpoint/clipping-planes viewpoint)}))

(defn topic-editor-context [project topic]
  {:bim.quality/topic-guid (:bcf.topic/guid topic)
   :bim.quality/title (:bcf.topic/title topic)
   :bim.quality/status (:bcf.topic/status topic)
   :bim.quality/viewpoints
   (mapv #(viewpoint-editor-context project %) (:bcf.topic/viewpoints topic))})
