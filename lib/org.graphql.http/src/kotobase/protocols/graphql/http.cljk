(ns kotobase.protocols.graphql.http
  "Ring-shaped request/response plumbing for the graphql.kotobase.net
  surface.

  VENDORED, not a dependency: ADR-2607172500's dependency table lists only
  `kotoba-lang/graphql` and `kotoba-lang/kotobase-query` as this repo's
  dependencies (not `kotoba-lang/kotobase-protocols`) — this namespace is
  copied from `kotobase-protocols`' `kotobase.protocols.http` rather than
  pulled in as a git dependency on a whole sibling protocols repo just for
  this one file. Same vendoring choice `org-opencypher-cypher` already made
  (ADR-2607172300).

  NAMESPACED UNDER `graphql` (ADR-2608039970 follow-up): it used to be
  `kotobase.protocols.http`, the SAME name as the upstream copy and as the
  copies in the other query-surface repos. One namespace, several different
  files -- invisible while each repo builds alone, silently wrong the moment
  a deploy shell puts two of them on one classpath. Vendoring is fine;
  vendoring under the upstream's name is not.

  A request is plain data:
    {:method  :get|:put|:post|:head|:delete
     :host    \"graphql.kotobase.net\"       ; optional (router uses it)
     :path    \"/graphql\"
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
