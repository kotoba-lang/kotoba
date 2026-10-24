(ns iceberg.table-test
  "What can be checked without a network or a reference implementation.

  `test/fixtures/verify_with_pyiceberg.py` is the oracle and this is not a
  substitute for it: nothing here can tell whether pyiceberg accepts the
  bytes. What these do is pin the things that oracle proved were load-bearing,
  so a change that breaks one fails here in seconds instead of only in the
  python run -- above all the field ids, which are the specification's and not
  this repo's to choose."
  (:require [avro.file :as avro]
            [clojure.test :refer [deftest is testing]]
            [iceberg.manifest :as manifest]
            [iceberg.metadata :as md]
            [iceberg.schema :as s]
            [iceberg.table :as table]
            [json.core :as json]))

(def ^:private schema (s/schema [(s/field 1 "id" :string) (s/field 2 "n" :long)]))

(def ^:private data-files
  [{:file-path "file:///w/t/data/part-0.parquet" :record-count 3 :file-size-bytes 700}])

(defn- committed [& {:as opts}]
  (table/append (merge {:location "file:///w/t" :schema schema
                        :data-files data-files
                        :table-uuid "11111111-2222-4333-a444-555555555555"
                        :snapshot-id 1234 :timestamp-ms 1700000000000}
                       opts)))

;; ---------------------------------------------------------------------------
;; Field ids are the specification's.
;; ---------------------------------------------------------------------------

(defn- ids-of [avro-schema]
  (into {} (map (juxt #(get % "name") #(get % "field-id"))) (get avro-schema "fields")))

(deftest manifest-entry-field-ids-are-pinned
  (testing "a reader resolves by id; renaming one makes the field invisible"
    (let [top (ids-of (s/manifest-entry-schema []))]
      (is (= {"status" 0 "snapshot_id" 1 "sequence_number" 3
              "file_sequence_number" 4 "data_file" 2}
             top)))
    (let [df (ids-of (get (first (filter #(= "data_file" (get % "name"))
                                         (get (s/manifest-entry-schema []) "fields")))
                          "type"))]
      (is (= {"content" 134 "file_path" 100 "file_format" 101 "partition" 102
              "record_count" 103 "file_size_in_bytes" 104
              "column_sizes" 108 "value_counts" 109 "null_value_counts" 110
              "lower_bounds" 125 "upper_bounds" 128}
             df)))))

(deftest the-statistics-maps-carry-their-own-key-and-value-ids
  (testing "Iceberg assigns them separately from the map's own field id"
    (let [df (get (first (filter #(= "data_file" (get % "name"))
                                 (get (s/manifest-entry-schema []) "fields")))
                  "type")
          ids (fn [nm]
                (let [f (first (filter #(= nm (get % "name")) (get df "fields")))
                      arr (second (get f "type"))]
                  [(get arr "logicalType")
                   (mapv #(get % "field-id") (get (get arr "items") "fields"))]))]
      (is (= ["map" [117 118]] (ids "column_sizes")))
      (is (= ["map" [119 120]] (ids "value_counts")))
      (is (= ["map" [121 122]] (ids "null_value_counts")))
      (is (= ["map" [126 127]] (ids "lower_bounds")))
      (is (= ["map" [129 130]] (ids "upper_bounds"))))))

(deftest bounds-are-little-endian-because-readers-compare-them-as-bytes
  (testing "big-endian longs sort wrongly against each other and prune silently"
    (is (= [1 0 0 0 0 0 0 0] (manifest/bound-bytes :long 1)))
    (is (= [0 1 0 0 0 0 0 0] (manifest/bound-bytes :long 256)))
    (is (= [1 0 0 0] (manifest/bound-bytes :int 1)))
    (is (= [104 105] (manifest/bound-bytes :string "hi")))
    (is (= [1] (manifest/bound-bytes :boolean true)))
    (testing "high bytes are not copies of the low ones -- bit-shift-right is 32-bit on cljs"
      (is (= [0 0 0 0 1 0 0 0] (manifest/bound-bytes :long 4294967296))))
    (testing "negatives are two's complement, not a truncated magnitude"
      (is (= [255 255 255 255 255 255 255 255] (manifest/bound-bytes :long -1)))
      (is (= [255 255 255 255] (manifest/bound-bytes :int -1))))
    (is (thrown? #?(:clj Exception :cljs js/Error)
                 (manifest/bound-bytes :timestamptz 0)))))

(deftest statistics-are-omitted-rather-than-invented
  (testing "unknown is a truthful answer; a wrong narrow bound deletes rows"
    (let [df (manifest/data-file {:file-path "f" :record-count 1 :file-size-bytes 2})]
      (doseq [k ["column_sizes" "value_counts" "null_value_counts"
                 "lower_bounds" "upper_bounds"]]
        (is (nil? (get df k)) k)))))

(deftest supplied-statistics-become-key-value-records
  (let [df (manifest/data-file {:file-path "f" :record-count 1 :file-size-bytes 2
                                :null-counts {1 0 2 3}
                                :lower-bounds {1 (manifest/bound-bytes :long 5)}})]
    (is (= [{"key" 1 "value" 0} {"key" 2 "value" 3}] (get df "null_value_counts")))
    (is (= [{"key" 1 "value" [5 0 0 0 0 0 0 0]}] (get df "lower_bounds")))))

(deftest manifest-file-field-ids-are-pinned
  (is (= {"manifest_path" 500 "manifest_length" 501 "partition_spec_id" 502
          "content" 517 "sequence_number" 515 "min_sequence_number" 516
          "added_snapshot_id" 503 "added_files_count" 504
          "existing_files_count" 505 "deleted_files_count" 506
          "added_rows_count" 512 "existing_rows_count" 513
          "deleted_rows_count" 514 "partitions" 507 "key_metadata" 519}
         (ids-of s/manifest-file-schema))))

(deftest the-partitions-array-declares-its-element-id
  (testing "pyiceberg refuses an array without one"
    (let [f (first (filter #(= "partitions" (get % "name"))
                           (get s/manifest-file-schema "fields")))
          arr (second (get f "type"))]
      (is (= "array" (get arr "type")))
      (is (= 508 (get arr "element-id"))))))

;; ---------------------------------------------------------------------------
;; The files a commit produces.
;; ---------------------------------------------------------------------------

(deftest a-manifest-is-a-readable-avro-file-with-iceberg-metadata
  (let [{:keys [files manifest-path]} (committed)
        bs (get files manifest-path)
        m (avro/metadata bs)]
    (is (= 1 (avro/record-count bs)))
    (testing "the metadata a manifest is not a manifest without"
      (is (= "2" (get m "format-version")))
      (is (= "data" (get m "content")))
      (is (= "0" (get m "partition-spec-id")))
      (is (= schema (json/decode (get m "schema")))))
    (testing "and the entry describes the data file"
      (let [e (first (avro/records bs))
            df (get e "data_file")]
        (is (= manifest/status-added (get e "status")))
        (is (= 1234 (get e "snapshot_id")))
        (is (= "file:///w/t/data/part-0.parquet" (get df "file_path")))
        (is (= 3 (get df "record_count")))
        (is (= "PARQUET" (get df "file_format")))
        (is (= {} (get df "partition")) "unpartitioned is an empty struct, not absent")))))

(deftest a-manifest-list-names-the-manifest-and-counts-its-rows
  (let [{:keys [files manifest-list-path manifest-path]} (committed)
        bs (get files manifest-list-path)
        e (first (avro/records bs))]
    (is (= 1 (avro/record-count bs)))
    (is (= manifest-path (get e "manifest_path")))
    (is (= (count (get files manifest-path)) (get e "manifest_length")))
    (is (= 1 (get e "added_files_count")))
    (is (= 3 (get e "added_rows_count")))
    (is (= 1234 (get e "added_snapshot_id")))
    (is (= "2" (get (avro/metadata bs) "format-version")))))

;; ---------------------------------------------------------------------------
;; metadata.json.
;; ---------------------------------------------------------------------------

(deftest metadata-states-the-whole-table
  (let [{:keys [metadata metadata-list-path]} (committed)
        _ metadata-list-path]
    (is (= 2 (get metadata "format-version")))
    (is (= 1234 (get metadata "current-snapshot-id")))
    (is (= {"snapshot-id" 1234 "type" "branch"} (get-in metadata ["refs" "main"])))
    (is (= 2 (get metadata "last-column-id")))
    (is (= [{"spec-id" 0 "fields" []}] (get metadata "partition-specs")))
    (is (= 999 (get metadata "last-partition-id")))
    (testing "one snapshot, with no parent, on a table that did not exist before"
      (let [snaps (get metadata "snapshots")]
        (is (= 1 (count snaps)))
        (is (nil? (get (first snaps) "parent-snapshot-id")))
        (is (= "append" (get-in (first snaps) ["summary" "operation"])))))))

(deftest a-name-mapping-is-set-because-plain-parquet-carries-no-ids
  (let [{:keys [metadata]} (committed)
        mapping (json/decode (get-in metadata ["properties" "schema.name-mapping.default"]))]
    (is (= [{"field-id" 1 "names" ["id"]} {"field-id" 2 "names" ["n"]}] mapping))))

(deftest appending-to-a-table-carries-its-history-forward
  (let [first-commit (committed)
        second-commit (committed :previous (:metadata first-commit)
                                 :snapshot-id 5678)
        snaps (get (:metadata second-commit) "snapshots")]
    (is (= 2 (count snaps)) "the metadata restates the table, it is not a delta")
    (is (= 1234 (get (second snaps) "parent-snapshot-id")))
    (is (= 2 (get (second snaps) "sequence-number")))
    (is (= 5678 (get (:metadata second-commit) "current-snapshot-id")))
    (testing "and keeps the table's identity"
      (is (= (get (:metadata first-commit) "table-uuid")
             (get (:metadata second-commit) "table-uuid"))))))

;; ---------------------------------------------------------------------------
;; Refusals.
;; ---------------------------------------------------------------------------

(deftest an-unmappable-column-type-is-refused
  (testing "a missing key beats a plausible neighbour"
    (is (thrown? #?(:clj Exception :cljs js/Error) (s/field 1 "t" :timestamp-nanos)))))

(deftest snapshot-ids-stay-inside-exact-json-range
  (dotimes [_ 50]
    (let [id (md/random-snapshot-id)]
      (is (pos? id))
      (is (<= id 2147483647)))))
