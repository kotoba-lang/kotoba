(ns com-backblaze-secure.credentials
  "Resolves per-bucket B2 credentials via kotoba-lang/secret-resolve
  (ADR-2607161000) — env → 1Password → Keychain, in that order, the same
  shape/precedence as this workspace's `manifest/repos.edn` `:b2
  :credentials`. This ns previously carried its own copy of that
  resolution logic, with the same stderr-leak (`security -g` printing the
  resolved secret in cleartext via Node's default stdio inheritance) and
  `op read` hang bugs independently found in the superproject's
  `scripts/b2-creds.cljs` — both now depend on the same shared library
  instead of each carrying a hand-copied, independently-bitrotting fix."
  (:require [secret-resolve.resolver :as resolver]
            [secret-resolve.sources :as sources]))

(defn- keychain-ref
  "This repo's config (config/example.edn) always uses the single
  \"combined\" Keychain item layout: account = key-id, password = app-key."
  [cred field]
  (when-let [service (get-in cred [:keychain :service])]
    (case field
      :app-key {:service service}
      :key-id  {:service service :field :account}
      nil)))

(defn- field-spec [cred field]
  {:order (:order cred)
   :env (get-in cred [:env field])
   :1password (get-in cred [:1password field])
   :keychain (keychain-ref cred field)})

(defn resolve-credentials
  "`cred` is one bucket's `:credentials` map from config/*.edn: {:order
  [...] :env {:key-id \"ENV_NAME\" :app-key \"ENV_NAME\"} :1password {:key-id
  \"op://...\" :app-key \"op://...\"} :keychain {:service \"b2:<name>\"}}.
  Returns {:key-id :app-key}. Throws ex-info (never returns partial/
  placeholder secret material) if either field cannot be resolved from any
  configured source."
  [cred]
  (resolver/resolve-map sources/default-sources
                         {:key-id  (field-spec cred :key-id)
                          :app-key (field-spec cred :app-key)}))
