(ns provider.secret-transport
  "Production-ish secret fetch transports for `provider.secret` (ADR 0145/0146).

  Does NOT define a new capability. Builds `(fn [{:keys [name]}] -> reply)`
  for injection as `:fetch`.

  ## No ambient secret authority

  - **No keychain dump / list-all / security dump-keychain**
  - **No full process env scan**
  - Host supplies an explicit map of secret-name → source

  ## Sources

  ### `map-fetch`
  Static `{name secret}` — tests and sealed host config.

  ### `env-fetch`
  `{secret-name env-var-name}` — reads only those env vars via
  `System/getenv` / `js/process.env` for the single requested name.
  Never enumerates all environment keys.

  ### `fn-fetch`
  Host one-shot getter. Wraps `(fn [name] string-or-nil)` so kagi,
  1Password, or a sealed compartment can supply values without the
  provider knowing about unlock policy. Never lists store contents.

  ### `keychain-fetch` (JVM)
  `{secret-name {:service s :account a}}` — single-item
  `security find-generic-password -s s -a a -w` only. Never uses
  `-g` (attribute dump can leak the password onto stderr). No
  dump-keychain / find-generic-password without -s."
  (:require [kotoba.lang.text :as str]
            [provider.secret :as secret])
  #?(:clj (:require [clojure.java.shell :as sh])))

(defn map-fetch
  "Host-sealed map of secret name → value."
  [m]
  (secret/mem-fetch m))

(defn- read-env
  "Read a single env var by exact name. Never lists the environment."
  [env-name]
  #?(:clj (System/getenv ^String env-name)
     :cljs (when (exists? js/process)
             (let [v (aget js/process.env env-name)]
               (when (some? v) (str v))))))

(defn env-fetch
  "Build a fetch transport from `{secret-name env-var-name}`.

  Only env vars named in the map are ever read. Unknown secret names
  return not-found (provider allowlist should already reject them)."
  [name->env]
  (when-not (and (map? name->env) (seq name->env)
                 (every? string? (keys name->env))
                 (every? string? (vals name->env)))
    (throw (ex-info "secret-transport/env-fetch requires non-empty string map"
                    {:phase :secret-transport})))
  (doseq [[n e] name->env]
    (when-let [err (secret/validate-name n)]
      (throw (ex-info "secret-transport secret name fails policy"
                      {:phase :secret-transport :name n :error err})))
    (when (or (str/blank? e) (str/includes? e "*"))
      (throw (ex-info "secret-transport env var name invalid"
                      {:phase :secret-transport :env e}))))
  (fn [{:keys [name]}]
    (if-let [env-name (get name->env name)]
      (if-let [v (read-env env-name)]
        (if (str/blank? v)
          {:tag :error :code :secret/empty :message "env secret empty"}
          {:tag :value :value v})
        {:tag :error :code :secret/not-found :message "env not set"})
      {:tag :error :code :secret/not-found :message "no env mapping"})))

(defn fn-fetch
  "Wrap a host one-shot getter as a secret `:fetch` transport.

  `getter` is `(fn [name] string-or-nil)`. Throws are mapped to
  `:secret/fetch`. Blank/nil → `:secret/not-found`.

  Use this to inject kagi / 1Password / sealed compartment get-only
  without importing those stacks into the provider:

      (fn-fetch (fn [n]
                  (when-let [ref (get name->ref n)]
                    (kagi.secret-store/get-secret store ref {}))))

  Optional `allowed` set — when provided, names outside the set are
  rejected here too (defense in depth; provider allowlist is primary)."
  ([getter]
   (fn-fetch getter nil))
  ([getter allowed]
   (when-not (fn? getter)
     (throw (ex-info "secret-transport/fn-fetch requires a getter fn"
                     {:phase :secret-transport})))
   (when (and (some? allowed)
              (not (and (set? allowed) (every? string? allowed))))
     (throw (ex-info "secret-transport/fn-fetch :allowed must be string set"
                     {:phase :secret-transport})))
   (when allowed
     (doseq [n allowed]
       (when-let [err (secret/validate-name n)]
         (throw (ex-info "secret-transport/fn-fetch allowed name fails policy"
                         {:phase :secret-transport :name n :error err})))))
   (fn [{:keys [name]}]
     (cond
       (and allowed (not (contains? allowed name)))
       {:tag :error :code :secret/not-allowed :message "name not in fn-fetch allowed"}

       :else
       (try
         (let [v (getter name)]
           (cond
             (nil? v)
             {:tag :error :code :secret/not-found :message "getter returned nil"}

             (and (string? v) (str/blank? v))
             {:tag :error :code :secret/empty :message "getter returned blank"}

             :else
             {:tag :value :value (str v)}))
         (catch #?(:clj Throwable :cljs :default) e
           {:tag :error
            :code :secret/fetch
            :message (or #?(:clj (.getMessage e) :cljs (.-message e))
                         "getter failed")}))))))

(defn- valid-keychain-ref?
  "Exact service+account only — no wildcards, no blank."
  [ref]
  (and (map? ref)
       (string? (:service ref))
       (not (str/blank? (:service ref)))
       (not (str/includes? (:service ref) "*"))
       (string? (:account ref))
       (not (str/blank? (:account ref)))
       (not (str/includes? (:account ref) "*"))))

#?(:clj
   (defn- keychain-get-one
     "Single-item password read. Uses `-w` only (never `-g` attribute dump)."
     [service account sh-fn]
     (let [{:keys [exit out err]}
           (sh-fn "security" "find-generic-password"
                  "-s" service "-a" account "-w")]
       (cond
         (zero? exit)
         (let [v (str/trim-newline (or out ""))]
           (if (str/blank? v)
             {:tag :error :code :secret/empty :message "keychain secret empty"}
             {:tag :value :value v}))

         ;; security exits non-zero when the item is missing
         :else
         {:tag :error
          :code :secret/not-found
          :message (or (not-empty (str/trim (str err)))
                       "keychain item not found")}))))

#?(:clj
   (defn keychain-fetch
     "Build a fetch transport from `{secret-name {:service s :account a}}`.

     Each get reads exactly one generic-password item by service+account.
     Never enumerates the keychain. Never uses `security dump-keychain` or
     `find-generic-password -g` (attribute dumps can leak the password).

     opts:
       :sh-fn  optional shell fn (default clojure.java.shell/sh) for tests."
     ([name->ref]
      (keychain-fetch name->ref {}))
     ([name->ref {:keys [sh-fn] :or {sh-fn sh/sh}}]
      (when-not (and (map? name->ref) (seq name->ref)
                     (every? string? (keys name->ref))
                     (every? valid-keychain-ref? (vals name->ref)))
        (throw (ex-info "secret-transport/keychain-fetch requires name→{:service :account}"
                        {:phase :secret-transport})))
      (doseq [[n _] name->ref]
        (when-let [err (secret/validate-name n)]
          (throw (ex-info "secret-transport secret name fails policy"
                          {:phase :secret-transport :name n :error err}))))
      (fn [{:keys [name]}]
        (if-let [{:keys [service account]} (get name->ref name)]
          (try
            (keychain-get-one service account sh-fn)
            (catch Exception e
              {:tag :error
               :code :secret/fetch
               :message (or (.getMessage e) "keychain fetch failed")}))
          {:tag :error :code :secret/not-found :message "no keychain mapping"})))))

#?(:cljs
   (defn keychain-fetch
     "cljs gap — macOS keychain is JVM/host-only in ADR 0146."
     ([_name->ref]
      (keychain-fetch _name->ref {}))
     ([_name->ref _opts]
      (throw (ex-info "secret-transport/keychain-fetch is JVM-only in ADR 0146"
                      {:phase :secret-transport})))))
