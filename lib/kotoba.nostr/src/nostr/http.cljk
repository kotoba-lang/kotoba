(ns nostr.http
  "Ring-shaped request/response plumbing for nostr.blossom, matching the
  house convention this workspace's kotobase-protocols repo established
  (kotobase.protocols.http): this repo does not depend on that repo — this
  is a small, independent implementation of the same trivial glue.

  A request is plain data:
    {:method  :get|:put|:delete
     :path    \"/upload\"
     :headers {\"authorization\" \"Nostr ...\"}   ; lower-case string keys
     :body    \"...\"}                              ; string body (v0.1;
                                                    ; binary is a follow-up,
                                                    ; same documented
                                                    ; limitation as
                                                    ; kotobase-protocols'
                                                    ; http.cljc)

  A response is {:status int :headers {...} :body string-or-nil}."
  (:require [kotoba.lang.text :as str]))

(defn header [req k] (get (:headers req) (str/lower k)))

(defn response
  ([status headers body] {:status status :headers headers :body body})
  ([status body] (response status {} body)))

(defn text [status body]
  (response status {"content-type" "text/plain; charset=utf-8"} body))

(defn json-response [status edn-body encode-fn]
  (response status {"content-type" "application/json"} (encode-fn edn-body)))

(defn not-found
  ([] (not-found "not found"))
  ([msg] (text 404 msg)))

(defn unauthorized [msg] (text 401 (or msg "unauthorized")))
(defn bad-request [msg] (text 400 (or msg "bad request")))
(defn method-not-allowed [] (text 405 "method not allowed"))
