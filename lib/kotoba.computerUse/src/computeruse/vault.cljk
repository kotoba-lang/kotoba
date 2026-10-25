(ns computeruse.vault
  "Secret resolution as an injected host capability.

  The agent model NEVER sees or types raw credentials. Instead it emits
  a vault *reference* (e.g. {:item \"Vultr\" :field \"password\"}); the
  host resolves it through a vault CLI and the value is typed/pasted at
  the IComputer layer, so it never enters the prompt, the message
  history, or the Datomic action log (which records only the ref).

  IVault implementations:
    op-vault    1Password CLI  (`op read` / `op item get`)
    bw-vault    Bitwarden CLI  (`bw get`)
    kagi-vault  kagi-clj CLI   (`kagi get` — `op`-compatible PQC vault)
    mock-vault  deterministic map, for tests

  A reference is a map:
    {:ref  \"op://Private/Vultr/password\"}            ; explicit secret-reference URI
    {:item \"Vultr\" :field \"password\" :vault \"Private\"}
  String refs (\"op://…\", \"bw://item/field\") are also accepted."
  #?(:clj (:require [kotoba.lang.text :as str])))

(defprotocol IVault
  (-resolve [v reference]
    "Reference (map or string) → secret string. Throws if not found.
     The returned value must never be logged or sent to the model."))

#?(:clj
   (do

(defn- sh [& args]
  (let [p (.start (doto (ProcessBuilder. ^java.util.List (vec args))
                    (.redirectErrorStream false)))
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (when-not (zero? code)
      (throw (ex-info (str "vault command failed (exit " code ")")
                      ;; never include the resolved value; err may carry hints
                      {:exit code :stderr (subs err 0 (min 200 (count err)))})))
    (str/trim out)))

;; ───────────────────────── 1Password ─────────────────────────

(defn op-vault
  "1Password CLI vault. Requires `op` signed in (op signin) or a
  service-account token in OP_SERVICE_ACCOUNT_TOKEN.

  Resolves:
    {:ref \"op://Vault/Item/field\"}     → op read <ref>
    {:item .. :field .. :vault ..}       → op item get <item> --vault <v> --fields <field> --reveal"
  [& [{:keys [account]}]]
  (let [base (cond-> ["op"] account (conj "--account" account))]
    (reify IVault
      (-resolve [_ reference]
        (cond
          (string? reference)
          (apply sh (concat base ["read" reference]))

          (:ref reference)
          (apply sh (concat base ["read" (:ref reference)]))

          (:field reference)
          (apply sh (concat base
                            ["item" "get" (:item reference)]
                            (when-let [v (:vault reference)] ["--vault" v])
                            ["--fields" (:field reference) "--reveal"]))

          :else
          (throw (ex-info "op-vault: reference needs :ref or :item+:field"
                          {:reference (dissoc reference :value)})))))))

;; ───────────────────────── Bitwarden ─────────────────────────

(defn bw-vault
  "Bitwarden CLI vault. Requires `bw` unlocked: pass the session token
  (`bw unlock --raw`) as :session or via BW_SESSION.

  Resolves:
    {:ref \"bw://<item>/password\"} or {:ref \"bw://<item>/username\"}
    {:item .. :field ..}   field ∈ #{password username totp} or a custom field name"
  [& [{:keys [session]}]]
  (let [session (or session (System/getenv "BW_SESSION"))
        base (cond-> ["bw"] session (conj "--session" session))
        builtin #{"password" "username" "totp"}
        get1 (fn [item field]
               (if (builtin field)
                 (apply sh (concat base ["get" field item]))
                 ;; custom field: pull the item JSON and read the named field
                 (let [json (apply sh (concat base ["get" "item" item]))]
                   ;; tiny extractor — avoids a JSON dep in this cljc file
                   (or (second (re-find (re-pattern
                                         (str "\"name\":\"" (java.util.regex.Pattern/quote field)
                                              "\",\"value\":\"((?:[^\"\\\\]|\\\\.)*)\""))
                                        json))
                       (throw (ex-info "bw-vault: custom field not found"
                                       {:field field :item item}))))))]
    (reify IVault
      (-resolve [_ reference]
        (cond
          (or (string? reference) (:ref reference))
          (let [s (if (string? reference) reference (:ref reference))
                [item field] (-> s (str/replace #"^bw://" "") (str/split #"/" 2))]
            (get1 item (or field "password")))

          (:field reference)
          (get1 (:item reference) (:field reference))

          :else
          (throw (ex-info "bw-vault: reference needs :ref or :item+:field"
                          {:reference (dissoc reference :value)})))))))

;; ───────────────────────── kagi (PQC vault) ─────────────────────────

(defn kagi-vault
  "kagi-clj CLI vault — the self-sovereign PQC `op` replacement
  (see kagi-clj / ADR-2606272330). Requires the `kagi` CLI on PATH and
  the vault unlocked (master passphrase via KAGI_MASTER env or an
  OS-keychain unlock; see `kagi unlock-status`).

  kagi is `op`-compatible: `kagi get <item>` decrypts an item's primary
  secret to stdout. Resolves:
    {:item \"gmail-app-password\"}                 → kagi get <item>
    {:item .. :field ..}                           → kagi item get <item> --fields <field> --reveal
    {:ref \"kagi://<item>\"} / \"kagi://<item>\"   → kagi get <item>
    \"<item>\" (bare string)                       → kagi get <item>

  Prefer the bare {:item ..} form for app-password / token items; the
  :field form mirrors op-vault and assumes kagi's `op`-compatible
  `item get --fields` surface."
  [& [_opts]]
  (reify IVault
    (-resolve [_ reference]
      (cond
        (:field reference)
        (sh "kagi" "item" "get" (:item reference)
            "--fields" (:field reference) "--reveal")

        (or (string? reference) (:ref reference) (:item reference))
        (let [s (cond (string? reference) reference
                      (:ref reference) (:ref reference)
                      :else (:item reference))
              item (-> s (str/replace #"^kagi://" ""))]
          (sh "kagi" "get" item))

        :else
        (throw (ex-info "kagi-vault: reference needs :item (or :ref / string)"
                        {:reference (dissoc reference :value)}))))))

   ))

;; ───────────────────────── mock (all hosts) ─────────────────────────

(defn mock-vault
  "Deterministic vault for tests. `m` maps a canonical ref string to a
  secret; `ref->key` turns a reference map/string into that key
  (default: the :ref string, or \"<item>/<field>\")."
  [m & [{:keys [ref->key]
         :or {ref->key (fn [r] (if (string? r) r
                                   (or (:ref r) (str (:item r) "/" (:field r)))))}}]]
  (reify IVault
    (-resolve [_ reference]
      (let [k (ref->key reference)]
        (or (get m k)
            (throw (ex-info "mock-vault: no such secret" {:key k})))))))
