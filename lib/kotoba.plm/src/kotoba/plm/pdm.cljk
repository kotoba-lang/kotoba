(ns kotoba.plm.pdm
  "PDM (Product Data Management) — document/version attachments on items
   (CAD/drawing/spec/STEP references + checksum + version). Pure domain data;
   no release-approval workflow lives here. Release approval is a governance
   concern and is implemented in cloud-itonami's activity/decision/effect
   facade (ADR-2607141000), keeping kotoba.plm governance-free per
   ADR-2607106100's org taxonomy."
  (:require [kotoba.plm.db :as db]))

(defn doc
  "Build a document tx map attached to `item` (\"<part>@<rev>\")."
  [{:keys [id item kind version checksum uri] :or {kind :spec}}]
  {:plm.doc/id       id
   :plm.doc/item     [:plm.item/id item]
   :plm.doc/kind     kind
   :plm.doc/version  version
   :plm.doc/checksum checksum
   :plm.doc/uri      uri})

(defn docs-for-item
  "Documents attached to `iid` as [{:id :kind :version :checksum :uri} ...],
   sorted by id."
  [d iid]
  (->> (db/q '[:find ?id ?kind ?version ?checksum ?uri
               :in $ ?iid
               :where
               [?i :plm.item/id ?iid]
               [?dc :plm.doc/item ?i]
               [?dc :plm.doc/id ?id]
               [?dc :plm.doc/kind ?kind]
               [?dc :plm.doc/version ?version]
               [?dc :plm.doc/checksum ?checksum]
               [?dc :plm.doc/uri ?uri]]
             d iid)
       (map (fn [[id kind version checksum uri]]
              {:id id :kind kind :version version :checksum checksum :uri uri}))
       (sort-by :id)
       vec))
