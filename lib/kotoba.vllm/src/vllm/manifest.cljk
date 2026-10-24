(ns vllm.manifest
  "Content-addressed GGUF blob store with atomic JSON manifests."
  (:require [json.data-json :as json])
  (:import [java.nio.file Files Path Paths StandardCopyOption StandardOpenOption]
           [java.security MessageDigest]
           [java.time Instant]))

(defrecord Store [^Path root ^Path blobs ^Path manifests])

(defn store [root]
  (let [root (Paths/get (str root) (make-array String 0))
        blobs (.resolve root "blobs") manifests (.resolve root "manifests")]
    (Files/createDirectories blobs (make-array java.nio.file.attribute.FileAttribute 0))
    (Files/createDirectories manifests (make-array java.nio.file.attribute.FileAttribute 0))
    (->Store root blobs manifests)))

(defn- sha256 [^Path path]
  (let [digest (MessageDigest/getInstance "SHA-256") buffer (byte-array 1048576)]
    (with-open [input (Files/newInputStream path (make-array java.nio.file.OpenOption 0))]
      (loop []
        (let [n (.read input buffer)]
          (when (pos? n) (.update digest buffer 0 n) (recur)))))
    (apply str (map #(format "%02x" (bit-and 0xff %)) (.digest digest)))))

(defn- safe-name [name]
  (when-not (and (string? name) (re-matches #"[A-Za-z0-9._:-]+" name))
    (throw (ex-info "invalid model name" {:name name})))
  name)

(defn- manifest-path [store name] (.resolve ^Path (:manifests store) (str (safe-name name) ".json")))
(defn blob-path [store digest] (.resolve ^Path (:blobs store) (str "sha256-" digest)))

(defn import!
  "Import GGUF as a deduplicated blob and atomically point `name` at it."
  [store name source]
  (let [source (Paths/get (str source) (make-array String 0)) digest (sha256 source)
        blob (blob-path store digest) size (Files/size source)
        manifest {"name" (safe-name name) "digest" (str "sha256:" digest)
                  "size" size "modified_at" (str (Instant/now)) "format" "gguf"}
        destination (manifest-path store name)
        temporary (Files/createTempFile (:manifests store) ".manifest-" ".tmp"
                                        (make-array java.nio.file.attribute.FileAttribute 0))]
    (when-not (Files/exists blob (make-array java.nio.file.LinkOption 0))
      (let [blob-temp (Files/createTempFile (:blobs store) ".blob-" ".tmp"
                                            (make-array java.nio.file.attribute.FileAttribute 0))]
        (try
          (Files/copy source blob-temp (into-array StandardCopyOption
                                                   [StandardCopyOption/REPLACE_EXISTING]))
          (Files/move blob-temp blob (into-array StandardCopyOption
                                                 [StandardCopyOption/ATOMIC_MOVE]))
          (finally (Files/deleteIfExists blob-temp)))))
    (try
      (Files/writeString temporary (json/write-str manifest)
                         (into-array StandardOpenOption [StandardOpenOption/WRITE
                                                         StandardOpenOption/TRUNCATE_EXISTING]))
      (Files/move temporary destination
                  (into-array StandardCopyOption
                              [StandardCopyOption/ATOMIC_MOVE StandardCopyOption/REPLACE_EXISTING]))
      manifest
      (finally (Files/deleteIfExists temporary)))))

(defn show [store name]
  (let [path (manifest-path store name)]
    (when (Files/exists path (make-array java.nio.file.LinkOption 0))
      (json/read-str (Files/readString path)))))

(defn list-models [store]
  (with-open [stream (Files/list (:manifests store))]
    (->> (.toList stream)
         (map #(json/read-str (Files/readString ^Path %)))
         (sort-by #(get % "name")) vec)))

(defn model-path [store name]
  (when-let [model (show store name)]
    (blob-path store (subs (get model "digest") 7))))

(defn delete! [store name]
  (boolean (Files/deleteIfExists (manifest-path store name))))
