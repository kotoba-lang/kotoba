(ns kotoba.property.plane-export
  "Turn collected stores into the newline-EDN corpora the workspace query plane
   loads (see `manifest/edn-query.cljs` in the superproject).

   Two shapes exist in this repo and they are not interchangeable:

   - `var/` holds a collector's *working store*: a single EDN map keyed by
     record id, rewritten in place on every refresh, and git-ignored. It is a
     cache, not a publication.
   - `data/` holds a *published projection*: newline-EDN, one record per line,
     committed, and readable by anything that can read EDN lines without
     holding the whole file in memory.

   Only projections that pass the publication review in DATA-GOVERNANCE.md may
   be written to `data/` — today that is public-body property claims and
   corporate identity records, neither of which contains natural-person data."
  (:require [kotoba.lang.text :as str]))

(def ownership-dataset "property-ownership")

(defn ownership-manifest
  [{:keys [observed-at sources record-count]}]
  (cond-> {:corpus/manifest true
           :corpus/format :edn-lines
           :source/dataset ownership-dataset
           :source/observed-at observed-at}
    (seq sources) (assoc :source/authorities (vec (sort sources)))
    record-count (assoc :corpus/record-count record-count)))

(defn claim->record
  "One ownership claim from a collector store -> one plane record.

   Keeps the `:ownership/*` contract names (`kotoba.property.ownership`) so the
   Datalog queries this repo already ships run unchanged against the plane, and
   adds `:property/jurisdiction` derived from the parcel id so that a query can
   ask for a jurisdiction without string-matching the parcel."
  [claim]
  (when (and (:ownership/id claim) (:ownership/parcel claim))
    (let [parcel (:ownership/parcel claim)
          jurisdiction (first (str/split parcel #":"))]
      (cond-> (into {} (filter (fn [[k _]] (= "ownership" (namespace k)))) claim)
        (not (str/blank? jurisdiction))
        (assoc :property/jurisdiction jurisdiction)))))

(defn store->records
  "Collector store map -> sorted, deduplicated plane records.

   Sorted by claim id so that re-running the export on unchanged input
   produces a byte-identical file: an export whose line order wanders makes
   every refresh look like a data change in review."
  [store]
  (->> (vals (:ownership-records store))
       (keep claim->record)
       (sort-by :ownership/id)
       vec))

(defn store-sources [store]
  (into #{} (keep :ownership/source) (vals (:ownership-records store))))
