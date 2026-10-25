(ns kotobase.protocols.http
  "Ring-shaped request/response plumbing for the OCI Distribution Spec
  surface. Vendored verbatim from kotoba-lang/kotobase-protocols'
  http.cljc (ADR-2607172210 directs every new protocol repo to vendor
  this tiny primitive rather than depend on kotobase-protocols or
  reinvent it) — keep in sync by hand if the upstream shape changes.

  A request is plain data:
    {:method  :get|:put|:post|:head|:delete
     :host    \"oci.kotobase.net\"          ; optional (unused by this repo's handler)
     :path    \"/v2/<name>/manifests/<ref>\"
     :query   {\"digest\" \"sha256:...\"}  ; string keys, string values
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
