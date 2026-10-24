(ns secret-resolve.core
  "Public entry point: resolve one or more credential fields via
  env → 1Password → macOS Keychain, in that order, using the exact spec
  shape already established by this workspace's `manifest/repos.edn`
  `:b2 :credentials`.

  Usage:

    (require '[secret-resolve.core :as sr])

    (sr/resolve1 {:order [:env :1password :keychain]
                  :env \"B2_KEY_ID\"
                  :1password \"op://gftdcojp/com-junkawasaki.b2_annex/keyID\"
                  :keychain {:service \"b2:gftdcojp-m365-annex\" :field :account}})
    ;=> \"004d9f6c0ba12580000000009\" (or throws-free nil if unresolved)

    (sr/resolve-map! {:key-id  {:order [...] :env \"B2_KEY_ID\" ...}
                       :app-key {:order [...] :env \"B2_APP_KEY\" ...}})
    ;=> {:key-id \"...\" :app-key \"...\"} — throws ex-info naming the field
    ;   and source order if any field can't be resolved from anything."
  (:require [secret-resolve.resolver :as resolver]
            [secret-resolve.sources :as sources]))

(defn resolve1
  "Resolve a single field spec against the default (env/1password/keychain)
  sources. Returns the value or nil (never throws — see resolve-map! for
  the throwing, multi-field convenience)."
  [spec]
  (resolver/resolve1 sources/default-sources spec))

(defn resolve-map!
  "fields: {field-key spec}. Returns {field-key value}. Throws ex-info
  (never partial secret material — only which field/source-order failed)
  for the first field that resolves to nil from every configured source."
  [fields]
  (resolver/resolve-map sources/default-sources fields))
