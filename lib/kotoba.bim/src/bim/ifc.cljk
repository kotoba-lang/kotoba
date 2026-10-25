(ns bim.ifc
  "Compatibility facade. New consumers should require shared `ifc.core`."
  (:require [ifc.core :as ifc]
            [bim.integration :as integration]))

(def schema ifc/schema)
(defn write-spf [project] (ifc/write-spf (integration/export-ifc project)))
(defn write-standard-spf [project]
  (ifc/write-spf (update (integration/export-ifc project) :ifc/project dissoc :model)))
(def read-spf ifc/read-spf)
(def read-document ifc/read-document)
(def semantic-fingerprint ifc/semantic-fingerprint)
(def roundtrip-report ifc/roundtrip-report)
(def corpus-report ifc/corpus-report)
(def hybrid-roundtrip-report ifc/hybrid-roundtrip-report)
(def hybrid-corpus-report ifc/hybrid-corpus-report)
