(ns secret-resolve.sources
  "Concrete `secret-resolve.resolver` source functions: environment
  variables, the 1Password CLI (`op`), and macOS Keychain
  (`security find-generic-password`). All subprocess calls go through
  `secret-resolve.exec/sh`, which is what actually fixes the stderr-leak
  and hang bugs — this ns only shapes the args and parses the output."
  (:require [kotoba.lang.text :as str]
            [secret-resolve.exec :as exec]))

(defn env
  "ref: an environment variable name (string), or nil to skip this source."
  [ref]
  (when ref
    (let [v (aget js/process.env ref)]
      (when-not (str/blank? v) v))))

(defn onepassword
  "ref: an `op://vault/item/field` path. Requires the `op` CLI to be
  signed in already — this never prompts (a stale/expired session times
  out via secret-resolve.exec's 5s default rather than hanging)."
  [ref]
  (when ref
    (let [{:keys [exit out]} (exec/sh "op" ["read" ref])]
      (when (zero? exit) (str/trim out)))))

(defn keychain
  "ref: {:service \"svc\" :field :password|:account :account \"explicit\"}.

  :field :password (default) — `security find-generic-password -s svc
  [-a account] -w`. Covers both the \"combined\" single-item layout
  (account = the other field, omitted here) and the \"separate item per
  field\" layout (explicit :account names which item to read).

  :field :account — `security find-generic-password -s svc -g`, parsed
  for just the `acct` attribute. `-g` prints the item's PASSWORD in
  cleartext as part of its human-readable dump (confirmed empirically —
  this exact behavior is what leaked a B2 application key to a chat
  transcript in the session that created this library, ADR-2607152322).
  That raw dump is captured (not inherited — see secret-resolve.exec) into
  a local string, regex-parsed for the one attribute this fn returns, and
  never logged or returned in full."
  [{:keys [service account field] :or {field :password}}]
  (when service
    (case field
      :account
      (let [{:keys [exit out]} (exec/sh "security" ["find-generic-password" "-s" service "-g"])]
        (when (zero? exit)
          (some-> (re-find #"\"acct\"<blob>=\"([^\"]*)\"" out) second)))

      :password
      (let [args (cond-> ["find-generic-password" "-s" service] account (into ["-a" account]))
            {:keys [exit out]} (exec/sh "security" (conj args "-w"))]
        (when (zero? exit) (str/trim out))))))

(def default-sources
  {:env env
   :1password onepassword
   :keychain keychain})
