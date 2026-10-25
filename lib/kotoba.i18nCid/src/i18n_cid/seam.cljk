(ns i18n-cid.seam
  "Piece 2: bridge content-addressed catalogs into `i18n.core` / `defmessages`.

  `register-from-block!` is the runtime path: fetch the catalog block by CID
  from any block store and merge it into `i18n.core` under its locale. This
  replaces the TM service's ExportMessages call with a kotobase as-of query
  when catalogs live on the datom plane — same `register!` merge semantics
  (later calls win), so static resources and CID catalogs coexist.

  `write-catalog-resource!` is the build-time path: materialize a catalog
  block's EDN to a classpath resource file so `i18n.messages/defmessages`
  reads it at macroexpansion time. JVM-only (file I/O). The generated file is
  a build artifact: commit it, and the compile-time key checking works exactly
  as documented in `i18n.messages`. This keeps the Unison-like identity (the
  block CID names the catalog) without asking the macro to fetch anything."
  (:require [i18n.core :as i18n]
            [i18n-cid.core :as cid]))

(defn register-from-block!
  "Fetch catalog at `cid` via `get-fn` and `(i18n/register! locale cat)`.
  Returns the merged catalog."
  [get-fn cid locale]
  (let [catalog (cid/dag->catalog get-fn cid)]
    (i18n/register! locale catalog)
    catalog))

(defn register-index!
  "Fetch a project index block and register every locale catalog it links.
  Returns `{\"ja\" <catalog> ...}`. Falls back per-locale: a missing catalog
  block is skipped, never guessed (i18n.core falls back to the source locale
  for missing keys at lookup time)."
  [get-fn index-cid]
  (let [{:keys [locales]} (cid/index->locales get-fn index-cid)]
    (into {}
          (keep (fn [[loc cid-str]]
                  (try
                    [loc (register-from-block! get-fn cid-str (keyword loc))]
                    (catch #?(:clj Exception :cljs js/Error) _
                      nil))))
          locales)))

(defn write-catalog-resource!
  "JVM-only. Write the catalog at `cid` as pretty EDN to
  `<resource-dir>/i18n/messages/<locale>.edn` so `defmessages` can consume it
  at macroexpansion. Creates parent dirs. Returns the written path."
  [get-fn cid locale resource-dir]
  (let [catalog (cid/dag->catalog get-fn cid)
        path (str resource-dir "/i18n/messages/" (name locale) ".edn")
        body (binding [*print-length* nil *print-level* nil]
               (pr-str catalog))]
    (clojure.java.io/make-parents path)
    (spit path body)
    path))

(defn write-index-manifest!
  "Write the index node as EDN for build tooling and human review. Returns
  the written path."
  [get-fn index-cid resource-dir]
  (let [{:keys [project locales]} (cid/index->locales get-fn index-cid)
        path (str resource-dir "/i18n/" project "-locales.edn")
        body (binding [*print-length* nil *print-level* nil]
               (pr-str {:format "i18n-catalog/1"
                        :project project
                        :locales locales}))]
    (clojure.java.io/make-parents path)
    (spit path body)
    path))
