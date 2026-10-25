(ns com-backblaze-secure.redact
  "Recursively strip credential-shaped values out of arbitrary EDN data
  before it is ever returned from an MCP tool or written to the audit
  ledger. Pure, no I/O — this is the single invariant this whole project
  exists to enforce (ADR-2607152322: an unredacted `b2 account authorize`
  JSON blob leaked an applicationKey/applicationKeyId into a chat
  transcript in the session that led to this repo). Every caller in
  com-backblaze-secure.b2-cli MUST route its parsed subprocess output
  through `redact` before returning it up the call stack."
  (:require [kotoba.lang.text :as str]))

(def denylist-key-substrings
  "Lower-cased, separator-stripped substrings of a map key's name that mark
  its value as credential-shaped, at any nesting depth. Written without
  `-`/`_` because `normalize-key` strips those from the candidate key
  before matching, so `app-key`, `app_key`, `APP_KEY`, and `appKey` all
  compare equal to `appkey`."
  ["applicationkey" "applicationkeyid" "accountauthtoken" "secretaccesskey"
   "accesskeyid" "appkey" "keyid" "authtoken" "password" "secret" "token"])

(def redacted-marker "«redacted»")

(defn- key-name [k]
  (cond
    (keyword? k) (name k)
    (string? k)  k
    :else        (str k)))

(defn- normalize-key [k]
  (-> (key-name k) str/lower (str/replace #"[-_]" "")))

(defn sensitive-key?
  [k]
  (let [kn (normalize-key k)]
    (boolean (some #(str/includes? kn %) denylist-key-substrings))))

(defn redact
  "Walk `data` (nested maps/vectors/lists), replacing the value of any map
  entry whose key matches `sensitive-key?` with `redacted-marker` regardless
  of nesting depth. Strings/numbers/keywords/nil pass through unchanged
  (there is no reliable way to pattern-match a bare secret string without a
  key to key off of — this is a deliberate, documented scope limit: callers
  must never place secret material outside a value slot of a denylisted
  key)."
  [data]
  (cond
    (map? data)
    (into (empty data)
          (map (fn [[k v]]
                 [k (if (sensitive-key? k) redacted-marker (redact v))]))
          data)

    (sequential? data)
    (into (empty data) (map redact) data)

    :else data))
