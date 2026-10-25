(ns annotation.core
  "EDN constructors for W3C Web Annotation documents.")

(def context-key (keyword "@context"))
(def anno-context "http://www.w3.org/ns/anno.jsonld")

(defn annotation
  [{:keys [id motivation body target creator created modified] :as props}]
  (cond-> (merge {context-key anno-context
                  :type "Annotation"}
                 (dissoc props :id :motivation :body :target :creator :created :modified))
    id (assoc :id id)
    motivation (assoc :motivation motivation)
    body (assoc :body body)
    target (assoc :target target)
    creator (assoc :creator creator)
    created (assoc :created created)
    modified (assoc :modified modified)))

(defn text-body
  ([value] (text-body value {}))
  ([value opts]
   (merge {:type "TextualBody" :value value} opts)))

(defn specific-resource
  [{:keys [source selector state style]}]
  (cond-> {:type "SpecificResource" :source source}
    selector (assoc :selector selector)
    state (assoc :state state)
    style (assoc :styleClass style)))

(defn fragment-selector [value]
  {:type "FragmentSelector" :value value})

(defn text-position-selector [start end]
  {:type "TextPositionSelector" :start start :end end})

(defn errors [x]
  (cond-> []
    (not (map? x)) (conj {:error :annotation/document-must-be-map})
    (and (map? x) (not= "Annotation" (:type x))) (conj {:error :annotation/type-must-be-annotation})
    (and (map? x) (nil? (:target x))) (conj {:error :annotation/missing-target})))

(defn validate [x]
  (let [es (errors x)]
    {:valid? (empty? es) :errors es}))
