(ns ifc.mvd
  "IFC exchange/model-view declaration profiles over Part 21 headers."
  (:require [kotoba.lang.text :as string]))

(def profiles
  {:coordination-view-2
   {:schemas #{"IFC2X3"} :token "CoordinationView_V2.0"}
   :reference-view
   {:schemas #{"IFC4" "IFC4X3" "IFC4X3_ADD2"} :token "ReferenceView"}
   :design-transfer-view
   {:schemas #{"IFC4" "IFC4X3" "IFC4X3_ADD2"} :token "DesignTransferView"}
   :alignment-based-reference-view
   {:schemas #{"IFC4X3" "IFC4X3_ADD2"} :token "AlignmentBasedReferenceView"}})

(defn- normalized-token [value]
  (some-> value string/lower (string/replace #"[^a-z0-9]" "")))

(defn detect-profile
  "Detect a known IFC model-view declaration from Part 21 descriptions."
  [descriptions]
  (let [description (string/join " " descriptions)
        declared (second (re-find #"(?i)ViewDefinition\s*\[([^]]+)\]" description))
        token (normalized-token declared)]
    (some (fn [[id profile]]
            (when (= token (normalized-token (:token profile))) id))
          profiles)))

(defn default-profile [schema]
  (if (= "IFC2X3" schema) :coordination-view-2 :design-transfer-view))

(defn compatible-profile?
  "True when a recognized profile is defined for the selected IFC schema."
  [schema profile]
  (boolean (contains? (get-in profiles [profile :schemas] #{}) schema)))

(defn header-description [schema profile]
  (let [profile (or profile (default-profile schema))
        definition (get profiles profile)]
    (when-not definition
      (throw (ex-info "unknown IFC model view" {:profile profile})))
    (when-not (compatible-profile? schema profile)
      (throw (ex-info "IFC model view is incompatible with schema"
                      {:profile profile :schema schema
                       :supported-schemas (:schemas definition)})))
    (str "ViewDefinition [" (:token definition) "]")))

(defn validate-declaration
  "Validate schema/profile/header agreement. This gate covers declaration and
  schema applicability; entity/rule conformance is delegated to an external
  schema/MVD validator."
  [{:keys [schema profile descriptions]}]
  (let [detected (detect-profile descriptions)
        expected (or profile detected)
        definition (get profiles expected)
        pass? (and definition (= expected detected)
                   (contains? (:schemas definition) schema))]
    {:mvd/pass? (boolean pass?)
     :mvd/profile expected :mvd/detected-profile detected
     :mvd/schema schema
     :mvd/schema-pass? (boolean (and definition
                                     (contains? (:schemas definition) schema)))
     :mvd/declaration-pass? (= expected detected)
     :mvd/conformance-scope :declaration-and-schema}))
