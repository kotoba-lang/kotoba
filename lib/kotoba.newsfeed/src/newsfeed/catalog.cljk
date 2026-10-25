(ns newsfeed.catalog
  "Read the source catalog, and re-join its editorial fields onto ledger
   articles at query time.

   The ledger records what was observed; the catalog records what we currently
   think of the observer. Credibility, source class and rights policy belong to
   the second — they are revised as we learn — and an append-only ledger cannot
   be revised. An article ingested before a source's class existed carries no
   class forever, so reading those fields off the stored record means catalog
   edits silently do not apply to anything already ingested. (Measured
   2026-08-03: adding `:news.source/class` changed nothing until this join
   existed, because every article in the ledger predated the field.)

   The ingest still writes its snapshot of these fields into the ledger. That
   is provenance — what was believed at the time — and the join below always
   wins over it.

   Pure `.cljc`."
  (:require [kotoba.lang.text :as str]))

(defn by-source-id [catalog]
  (into {} (map (juxt :news.source/sourceId identity)) (:sources catalog)))

(defn channel
  "Look up a channel by :channel/id, accepting a keyword or its name."
  [catalog id]
  (let [k (keyword (name (if (keyword? id) id (str id))))]
    (first (filter #(= k (:channel/id %)) (:channels catalog)))))

(defn channel-ids [catalog] (mapv :channel/id (:channels catalog)))

(defn enrich
  "Overlay the catalog's current editorial fields onto each article."
  [articles catalog]
  (let [srcs (by-source-id catalog)]
    (mapv (fn [a]
            (if-let [s (get srcs (:news/sourceId a))]
              (cond-> a
                (:news.source/class s)         (assoc :news/sourceClass (:news.source/class s))
                (:news.source/credibility s)   (assoc :news/credibility (:news.source/credibility s))
                (:news.source/rightsPolicy s)  (assoc :news/rightsPolicy (:news.source/rightsPolicy s))
                (:news.source/name s)          (assoc :news/sourceName (:news.source/name s)))
              a))
          articles)))

(defn for-channel
  "Articles from the sources this channel declares.

   The declaration is honoured rather than advisory. A channel that quietly
   drew from feeds it does not list could not be reviewed by reading its
   definition, and `:channel/sources` would be decoration. Sources may appear
   in more than one channel — that is how one outlet covering two beats is
   expressed — and the keyword gate decides what each channel takes from it."
  [articles channel]
  (if-let [allowed (some-> (:channel/sources channel) set)]
    (filterv #(allowed (:news/sourceId %)) articles)
    (vec articles)))

(defn unknown-sources
  "Source ids a channel names that the catalog does not define. A typo here
   silently shrinks a channel's pool, so it is worth saying out loud."
  [catalog channel]
  (let [known (set (keys (by-source-id catalog)))]
    (vec (remove known (:channel/sources channel)))))
