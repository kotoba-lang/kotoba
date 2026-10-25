(ns kotoba.lang.kami-nv-compat.kotoba-datomic-nucleus.client
  "kotoba-datomic-nucleus — omni.client-style API over the versioned store.
  Portable .cljc port of src/kotoba-datomic-nucleus/client.ts. Wave 28.

  Mirrors the documented omni.client surface (stat / list / read-file /
  write-file! / copy! / delete! / create-checkpoint! / get-checkpoints /
  subscribe!) used to talk to a Nucleus server, returning :result codes.
  URLs are `omniverse://<server>/<path>` (the server segment is a logical
  mount name; one client-held store backs all servers here).

  ADR-2605261800 SD6 / D10.4 kotoba-datomic-nucleus."
  (:require [kotoba.lang.text :as str]
            [kotoba.lang.kami-nv-compat.kotoba-datomic-nucleus.store :as store]))

(defn parse-url
  "Parse `omniverse://server/path` -> {:server :path}. A bare `/path` (no
  scheme) is accepted with server \"\" for convenience. nil if neither
  form matches."
  [url]
  (cond
    (str/starts-with? url "omniverse://")
    (let [rest-url (subs url (count "omniverse://"))
          slash (str/index-of rest-url "/")]
      (if (nil? slash)
        {:server rest-url :path "/"}
        {:server (subs rest-url 0 slash) :path (subs rest-url slash)}))

    (str/starts-with? url "/")
    {:server "" :path url}

    :else nil))

(defn- url-key
  [url]
  (when-let [u (parse-url url)]
    (str (:server u) (:path u))))

(defn make-client
  "An omni.client-compatible client over a NucleusStore (a fresh one by default)."
  ([] (make-client (store/make-store)))
  ([nucleus-store] {:store nucleus-store}))

(defn stat
  [client url]
  (if-let [k (url-key url)]
    (if-let [h (store/head (:store client) k)]
      {:result :ok :info {:cid (:cid h) :version (:index h) :size (count (:content h))}}
      {:result :error-not-found})
    {:result :error-invalid-url}))

(defn read-file
  [client url]
  (if-let [k (url-key url)]
    (if-let [content (store/read-content (:store client) k)]
      {:result :ok :content content}
      {:result :error-not-found})
    {:result :error-invalid-url}))

(defn write-file!
  [client url content]
  (if-let [k (url-key url)]
    {:result :ok :version (store/write! (:store client) k content)}
    {:result :error-invalid-url}))

(defn copy!
  [client src-url dst-url]
  (let [s (url-key src-url)
        d (url-key dst-url)]
    (if (or (nil? s) (nil? d))
      {:result :error-invalid-url}
      {:result (if (store/copy! (:store client) s d) :ok :error-not-found)})))

(defn delete!
  [client url]
  (if-let [k (url-key url)]
    {:result (if (store/delete! (:store client) k) :ok :error-not-found)}
    {:result :error-invalid-url}))

(defn list-entries
  [client url]
  (if-let [u (parse-url url)]
    (let [prefix (str (:server u) (:path u))
          entries (for [path (store/list-paths (:store client) prefix)
                        :let [h (store/head (:store client) path)]
                        :when h]
                    {:relative-path (subs path (count prefix)) :cid (:cid h) :version (:index h)})]
      {:result :ok :entries (vec entries)})
    {:result :error-invalid-url :entries []}))

;; ── checkpoints (Nucleus versioning) ─────────────────────────────────────

(defn create-checkpoint!
  [client url message]
  (if-let [k (url-key url)]
    (if-let [content (store/read-content (:store client) k)]
      {:result :ok :version (store/write! (:store client) k content message)}
      {:result :error-not-found})
    {:result :error-invalid-url}))

(defn get-checkpoints
  [client url]
  (if-let [k (url-key url)]
    (let [h (store/history (:store client) k)]
      {:result (if (seq h) :ok :error-not-found) :checkpoints h})
    {:result :error-invalid-url :checkpoints []}))

(defn restore!
  [client url version]
  (if-let [k (url-key url)]
    (if-let [v (store/restore! (:store client) k version)]
      {:result :ok :version v}
      {:result :error-not-found})
    {:result :error-invalid-url}))

(defn subscribe!
  "Subscribe to changes at a URL (exact path, or `.../` prefix)."
  [client url cb]
  (if-let [u (parse-url url)]
    (store/subscribe! (:store client) (str (:server u) (:path u)) cb)
    (fn [])))
