(ns iceberg.rest
  "The Iceberg REST catalog protocol, as request and response *data*.

  This performs no I/O, for the same reason `iceberg.table` writes no files:
  the part that has to be exactly right is the shape of the commit, and a
  namespace that also owned a socket could only be tested with one. `request`
  values go to whatever the caller uses to make HTTP calls -- `fetch` on a
  Worker, `curl`, an nbb http client -- and responses come back as parsed
  JSON.

  ## A commit is a compare-and-set, and the requirements are the compare

  `POST /v1/namespaces/{ns}/tables/{t}` carries two lists. `updates` say what
  to change. `requirements` say what the caller believed when it decided --
  `assert-ref-snapshot-id` names the snapshot the caller read. If another
  writer committed in between, the catalog rejects with 409 and nothing is
  lost; without it, two concurrent appends silently keep only one.

  **The requirement is not optional in practice.** Writing it as a defaulted
  argument would make the dangerous call the short one, so `commit` takes
  `:requirements` explicitly and `append-requirements` builds the right ones.

  ## Every path but /v1/config carries a prefix the catalog assigns

  `GET /v1/config?warehouse=...` answers with `overrides.prefix`, and the rest
  of the API lives under `/v1/{prefix}/`. Measured against Cloudflare R2 Data
  Catalog: without the warehouse parameter `/v1/config` is 400, and every
  path without the prefix is **404 with an empty body** -- which reads like a
  missing table rather than a malformed URL, so it is worth knowing before
  spending an hour on the table name.

  ## Snapshot ids do not survive JSON.parse, and the compare-and-set is made of one

  Measured against the live catalog: `current-snapshot-id` 7788483499493485286
  comes back from `JSON.parse` as 7788483499493486000. Off by 714, silently,
  because JavaScript numbers carry 53 bits and Iceberg ids are 64. A
  requirement built from the parsed value asserts a snapshot that never
  existed -- the commit fails with a message about a snapshot id nobody
  recognises, or, against a lenient catalog, is simply not the check it
  claimed to be.

  So ids travel as **strings of digits** here, extracted from the response
  text rather than from the parsed object (`current-snapshot-id-of`), and
  spliced into the request body unquoted (`int-literal`). Passing a plain
  number that cannot round-trip is refused rather than rounded.

  ## The token is a header, never a URL

  A token in a query string ends up in proxy logs and shell history. It goes
  in `Authorization`, and this namespace never puts it in `:url`."
  (:require [kotoba.lang.text :as str]
            [json.core :as json]))

(defn base-url
  "Cloudflare R2 Data Catalog's URI shape. Any Iceberg REST catalog works;
  this is the one this workspace uses."
  [account bucket]
  (str "https://catalog.cloudflarestorage.com/" account "/" bucket))

(defn- headers [token]
  {"Authorization" (str "Bearer " token)
   "Content-Type" "application/json"
   "Accept" "application/json"})

(defn warehouse-name
  "Cloudflare names a warehouse `<account>_<bucket>`."
  [account bucket] (str account "_" bucket))

(defn prefix-of
  "The prefix out of a parsed `/v1/config` response."
  [config-response] (get-in config-response ["overrides" "prefix"]))

(defn- v1 [uri prefix & parts]
  (apply str uri "/v1/" (when prefix (str prefix "/")) parts))

(def ^:private literal-prefix "@@iceberg-int:")

(defn int-literal
  "Marks `digits` to be emitted as a JSON number, not a string.

  JSON has one number type and this runtime cannot hold a 64-bit one, so an
  exact id has to reach the body as text and stop being text at the last
  moment.

  The marker is plain ASCII deliberately: a NUL-prefixed one was the first
  attempt and it does not survive `json/encode`, which escapes it to
  \\u0000 so the substitution silently matches nothing and the id ships as a
  quoted string. Measured."
  [digits]
  (str literal-prefix digits))

;; Can this runtime hold the value as a number without rounding? Split rather
;; than branched inside one body: on the JVM the argument is genuinely unused,
;; because a long holds any Iceberg id exactly and there is nothing to check.
#?(:clj  (defn- exact? [_] true)
   :cljs (defn- exact? [n]
           (and (js/Number.isFinite n)
                (<= (js/Math.abs n) js/Number.MAX_SAFE_INTEGER))))

(defn- encode-body
  "`json/encode`, then unquote anything `int-literal` marked."
  [x]
  (str/replace (json/encode x)
               (re-pattern (str "\"" literal-prefix "(-?[0-9]+)\""))
               "$1"))

(defn current-snapshot-id-of
  "The table's current snapshot id, as exact digits, out of the RAW response
  body.

  Takes text, not a parsed object, on purpose -- see the namespace docstring.
  Returns nil when the table has no snapshot, which is what a freshly created
  table looks like and is not an error."
  [response-text]
  (second (re-find #"\"current-snapshot-id\"\s*:\s*(-?[0-9]+)" response-text)))

(defn load-table
  "-> the request that reads a table's current metadata.

  The response's `metadata-location` is what a later commit compares against,
  and `metadata` is the parsed table metadata `iceberg.table/append` takes as
  `:previous`."
  [{:keys [uri prefix namespace table token]}]
  {:method :get
   :url (v1 uri prefix "namespaces/" namespace "/tables/" table)
   :headers (headers token)})

(defn config
  "-> `GET /v1/config?warehouse=...`. The call that must come first, because
  its answer contains the prefix every other path needs.

  It is also the cheapest check that the credential works on the metadata
  plane -- and it does NOT tell you whether it works on the storage plane: an
  OAuth session passes this and then fails to create a table. Measured, and
  the reason `datalake_catalog.py` refuses to fall back to one."
  [{:keys [uri token warehouse]}]
  {:method :get
   :url (str uri "/v1/config" (when warehouse (str "?warehouse=" warehouse)))
   :headers (headers token)})

;; ---------------------------------------------------------------------------
;; Commit.
;; ---------------------------------------------------------------------------

(defn append-requirements
  "What the caller must have been right about for this append to be valid.

  `current-snapshot-id` is the snapshot the caller READ. nil means the caller
  believes the table does not exist yet, which asserts exactly that -- not
  'no requirement'.

  Give it the digits from `current-snapshot-id-of`. A number is accepted only
  if this runtime can hold it exactly; otherwise it is refused, because the
  alternative is asserting a rounded id that names no snapshot."
  [current-snapshot-id]
  (cond
    (nil? current-snapshot-id) [{"type" "assert-create"}]
    (string? current-snapshot-id)
    [{"type" "assert-ref-snapshot-id" "ref" "main"
      "snapshot-id" (int-literal current-snapshot-id)}]
    (exact? current-snapshot-id)
    [{"type" "assert-ref-snapshot-id" "ref" "main"
      "snapshot-id" current-snapshot-id}]
    :else
    (throw (ex-info (str "iceberg: snapshot id " current-snapshot-id
                         " cannot be represented exactly here; pass the digits"
                         " from current-snapshot-id-of as a string")
                    {:type :iceberg/inexact-snapshot-id}))))

(defn append-updates
  "The update actions that add one snapshot and move `main` to it.

  Two actions, not one: Iceberg separates adding a snapshot from making it
  current, because a snapshot can exist on a branch that `main` does not
  point at. Emitting only `add-snapshot` produces a commit that succeeds and
  changes nothing a default reader can see."
  [snapshot]
  [{"action" "add-snapshot" "snapshot" snapshot}
   {"action" "set-snapshot-ref"
    "ref-name" "main"
    "type" "branch"
    "snapshot-id" (get snapshot "snapshot-id")}])

(defn commit
  "-> the request that commits `updates` if `requirements` still hold.

  A 409 from this is not an error to retry blindly: it means the table moved,
  so the caller must re-read, rebuild the snapshot against the new parent, and
  commit again. Retrying the same body would re-assert a snapshot id that is
  no longer current and fail identically."
  [{:keys [uri prefix namespace table token requirements updates]}]
  (when (nil? requirements)
    (throw (ex-info "iceberg: a commit without requirements is a blind overwrite"
                    {:type :iceberg/missing-requirements})))
  {:method :post
   :url (v1 uri prefix "namespaces/" namespace "/tables/" table)
   :headers (headers token)
   :body (encode-body {"requirements" requirements "updates" updates})})

(defn create-table
  "-> the request that creates a table with a schema and no snapshots.

  Separate from `commit` because Iceberg's create is a different endpoint with
  a different body; folding them together would hide which one a caller is
  about to do."
  [{:keys [uri prefix namespace table token schema location]}]
  {:method :post
   :url (v1 uri prefix "namespaces/" namespace "/tables")
   :headers (headers token)
   :body (encode-body (cond-> {"name" table "schema" schema}
                        location (assoc "location" location)))})
