(ns kotobase.protocols.cypher.http
  "Ring-shaped request/response plumbing for the cypher.kotobase.net
  surface.

  VENDORED, not a dependency: ADR-2607172300's dependency table lists only
  `kotoba-lang/kotobase-query` as this repo's dependency (not
  `kotoba-lang/kotobase-protocols`) — this namespace is copied from
  `kotobase-protocols`' `kotobase.protocols.http` rather than pulled in as a
  git dependency on a whole sibling protocols repo just for this one file.
  Keep in sync by hand if that version changes in a way that matters here.

  NAMESPACED UNDER `cypher` (ADR-2608039970 follow-up). It used to be
  `kotobase.protocols.http` -- the SAME name the upstream copy uses, and so
  did the copies in the other query-surface repos. Four files, four
  different contents, one namespace: invisible while each repo builds
  alone, and silently wrong the moment a deploy shell puts two of them on
  one classpath, because whichever copy is found first wins for everyone
  and they are not identical (upstream is 39 lines, this one is not).
  Vendoring is fine; vendoring under the upstream's name is not.

  A request is plain data:
    {:method  :get|:put|:post|:head|:delete
     :host    \"cypher.kotobase.net\"        ; optional (router uses it)
     :path    \"/db/data/transaction/commit\"
     :query   {\"prefix\" \"a/\"}          ; string keys, string values
     :headers {\"content-type\" \"...\"}   ; lower-case string keys
     :body    \"...\"}                      ; string body (v0.1; binary is a follow-up)

  A response is {:status int :headers {...} :body string-or-nil}.
  Handlers are pure: (handle ctx req) → resp, where ctx carries the
  injected kotobase.store/IStore under :store (LocalStore standalone,
  KotobaseStore against kotobase.net — the store seam never leaks into
  handler logic)."
  (:require [kotoba.lang.text :as str]))

(defn segments
  "Path → vector of decoded, non-empty segments: \"/a//b\" → [\"a\" \"b\"]."
  [path]
  (->> (str/split (or path "") #"/")
       (remove str/blank?)
       vec))

(defn query-param [req k] (get (:query req) k))

(defn header [req k] (get (:headers req) (str/lower k)))

(defn response
  ([status headers body] {:status status :headers headers :body body})
  ([status body] (response status {} body)))

(defn text [status body]
  (response status {"content-type" "text/plain; charset=utf-8"} body))

(defn not-found
  ([] (not-found "not found"))
  ([msg] (text 404 msg)))

(defn method-not-allowed [] (text 405 "method not allowed"))

(defn xml-escape [s]
  (-> (str s)
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")
      (str/replace "\"" "&quot;")))
