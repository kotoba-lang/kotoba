(ns kasane.schema
  "malli schema = SSoT for the common :kasane/doc model (ADR-2606272100).
   Validation/generation only — kept out of the WASM (kotoba-clj) path.
   Requires metosin/malli (see deps.edn :malli alias)."
  (:require [malli.core :as m]))

(def Transform [:maybe [:vector {:min 6 :max 6} number?]])
(def BBox      [:maybe [:vector {:min 4 :max 4} number?]])
(def CID       [:maybe :string])

(def Node
  [:schema {:registry
            {::node
             [:map
              [:node/id :string]
              [:node/kind [:enum :group :page :artboard :raster :vector :text
                           :smart-object :adjustment :clip-mask]]
              [:node/name {:optional true} :string]
              [:node/visible? {:optional true} :boolean]
              [:node/opacity {:optional true} [:and number? [:>= 0] [:<= 1]]]
              [:node/blend {:optional true} :keyword]
              [:node/bbox {:optional true} BBox]
              [:node/transform {:optional true} Transform]
              [:node/children {:optional true} [:vector [:ref ::node]]]
              [:text/runs {:optional true} [:vector [:map [:text :string]]]]
              [:vector/paths {:optional true} [:vector :any]]
              [:raster/blob {:optional true} [:map [:cid CID]]]]}}
   ::node])

(def Doc
  [:map
   [:kasane/format [:enum :psd :pdf :ai]]
   [:kasane/canvas [:map
                    [:width number?] [:height number?]
                    [:unit :keyword] [:dpi {:optional true} number?]
                    [:color-mode {:optional true} :any]]]
   [:kasane/nodes [:vector Node]]
   [:kasane/resources {:optional true} :map]
   [:kasane/meta {:optional true} :map]])

(defn validate [doc] (m/validate Doc doc))
(defn explain  [doc] (m/explain  Doc doc))
