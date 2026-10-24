(ns iceberg.table
  "Assembling one append into the set of files a commit consists of.

  An Iceberg commit is not a mutation. It is: write the data files, write a
  manifest naming them, write a manifest list naming that manifest, write a
  new `metadata.json` naming that list, and then -- atomically, somewhere else
  -- point the catalog at the new metadata. This namespace does the first four
  and produces bytes; it performs no I/O and talks to no catalog, so the part
  that needs a network is the caller's and the part that must be exactly right
  is testable without one.

  ## Appending needs the previous snapshots, and says so

  `append` takes `:previous`, the parsed metadata of the table as it stands.
  Passing nil creates the table. Passing the wrong thing -- an older metadata
  than the table's real head -- produces a commit that silently drops whatever
  snapshots came between, which is why the catalog step is a compare-and-set
  on the metadata location rather than a write."
  (:require [iceberg.manifest :as manifest]
            [iceberg.metadata :as md]))

(defn- ->bytes-count [bs] (count bs))

(defn append
  "-> `{:files {path bytes} :metadata <data> :metadata-json string
        :snapshot-id n}`.

  `:data-files` are files ALREADY WRITTEN by the caller (Parquet, via
  org-apache-parquet or anything else) described by path, row count and byte
  size. This does not write them: a table format's job is to say which files
  are in the table, and inventing their contents here would confuse the two."
  [{:keys [location schema data-files previous table-uuid snapshot-id
           timestamp-ms]
    :or {}}]
  (let [prev-snapshots (vec (get previous "snapshots" []))
        parent-id (get previous "current-snapshot-id")
        seq-num (inc (get previous "last-sequence-number" 0))
        snapshot-id (or snapshot-id (md/random-snapshot-id))
        table-uuid (or table-uuid (get previous "table-uuid") (md/random-uuid-string))
        timestamp-ms (or timestamp-ms #?(:clj (System/currentTimeMillis)
                                         :cljs (.getTime (js/Date.))))
        entries (mapv manifest/data-file data-files)
        rows (reduce + 0 (map #(get % "record_count") entries))
        manifest-path (str location "/metadata/" snapshot-id "-m0.avro")
        manifest-bytes (manifest/write-manifest
                        {:schema schema :snapshot-id snapshot-id
                         :sequence-number seq-num :data-files entries})
        list-path (str location "/metadata/snap-" snapshot-id "-1.avro")
        list-bytes (manifest/write-manifest-list
                    {:snapshot-id snapshot-id
                     :parent-snapshot-id parent-id
                     :sequence-number seq-num
                     :entries [(manifest/manifest-file-entry
                                {:manifest-path manifest-path
                                 :manifest-length (->bytes-count manifest-bytes)
                                 :snapshot-id snapshot-id
                                 :sequence-number seq-num
                                 :added-files (count entries)
                                 :added-rows rows})]})
        snap (md/snapshot {:snapshot-id snapshot-id
                           :parent-snapshot-id parent-id
                           :sequence-number seq-num
                           :timestamp-ms timestamp-ms
                           :manifest-list list-path
                           :schema-id (get schema "schema-id" 0)
                           :summary {"added-data-files" (str (count entries))
                                     "added-records" (str rows)}})
        metadata (md/table-metadata {:table-uuid table-uuid
                                     :location location
                                     :schema schema
                                     :snapshots (conj prev-snapshots snap)
                                     :current-snapshot-id snapshot-id
                                     :last-sequence-number seq-num
                                     :last-updated-ms timestamp-ms})]
    {:snapshot-id snapshot-id
     :metadata metadata
     :metadata-json (md/json-of metadata)
     :manifest-path manifest-path
     :manifest-list-path list-path
     :files {manifest-path manifest-bytes
             list-path list-bytes}}))
