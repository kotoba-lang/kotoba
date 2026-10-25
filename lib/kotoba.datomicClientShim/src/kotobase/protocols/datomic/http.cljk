(ns kotobase.protocols.datomic.http
  "Ring-shaped request/response plumbing shared by every protocol
  surface in this repo. Vendored byte-for-byte from
  kotoba-lang/kotobase-protocols's kotobase.protocols.http — same
  vendoring discipline `org-ietf-webdav`/`org-oci-distribution`/
  `org-ietf-sftp` use (ADR-2607172210), continued here per
  ADR-2607172300: new per-protocol repos vendor/reuse this tiny
  primitive rather than depending on kotobase-protocols as a library
  or reinventing it — update by re-vendoring from upstream, not by
  independent edits, so the shape stays identical across every
  protocol surface in the kotobase family.

  NAMESPACED UNDER `datomic` (ADR-2608039970 follow-up): it used to be
  `kotobase.protocols.http`, the SAME name as the upstream copy and as the
  copies in the other query-surface repos. One namespace, several different
  files -- invisible while each repo builds alone, silently wrong the moment
  a deploy shell puts two of them on one classpath. Vendoring is fine;
  vendoring under the upstream's name is not.

  A request is plain data:
    {:method  :post                       ; datomic.cljc only ever
                                           ; handles POST /api/query
     :host    \"datomic.kotobase.net\"    ; optional (router uses it)
     :path    \"/bucket/key\"
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
