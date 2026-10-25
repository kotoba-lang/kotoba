(ns computeruse.mail
  "IMail host-capability — programmatic mail retrieval as an injected
  I/O boundary, parallel to IComputer.

  The agent model NEVER sees the IMAP credential. The `fetch_mail`
  tool resolves an app password through computeruse.vault/IVault inside
  its :fn and passes it to the IMail impl only as the curl `--user`
  argument; the tool returns parsed mail (subject/from/date/body),
  never the password. The Datomic action log (computeruse.agent/log-action!)
  records only the model's {:limit N} input and the parsed-mail result.

  Why IMAP and not screen-driving the browser: ADR-0009 forbids the
  agent from performing Google password sign-in (even via computer-use
  / 1Password). An app password is a non-interactive IMAP credential
  (`curl imaps:// --user`), not a browser sign-in, so it stays on the
  right side of that boundary and is far more reliable than pixel
  clicking. The curl-IMAPS model is borrowed from manimani's
  channels.email/curl-imap-fetch — zero third-party deps."
  (:require [kotoba.lang.text :as str]
            [computeruse.vault :as vault]))

(defprotocol IMail
  (-fetch! [m opts]
    "Fetch messages. opts: {:account :password :mailbox :host :limit :search}.
     Returns a seq of {:uid :from :subject :date :message-id :body}.
     The :password is consumed here (e.g. curl --user) and MUST NEVER
     appear in the returned messages."))

;; ───────────────────────── parser (no deps) ─────────────────────────

(defn- header [s re]
  (some-> (re-find re s) second str/trim))

(defn parse-message
  "Parse one RFC822-ish message blob (curl BODY[] output) into
  {:uid :from :subject :date :message-id :body}. `uid` is optional
  (the caller knows it from the SEARCH; pass nil to omit).

  Splits on the first blank line; headers are matched case-insensitively
  across lines (manimani channels.email/header pattern)."
  ([blob] (parse-message blob nil))
  ([blob uid]
   (let [[hdr body] (str/split blob #"\r?\n\r?\n" 2)]
     {:uid         uid
      :from        (or (header hdr #"(?im)^From:\s*(.+)$") "")
      :subject     (or (header hdr #"(?im)^Subject:\s*(.+)$") "(no subject)")
      :date        (or (header hdr #"(?im)^Date:\s*(.+)$") "")
      :message-id  (header hdr #"(?im)^Message-ID:\s*(.+)$")
      :body        (str/trim (or body ""))})))

;; ───────────────────────── mock (all hosts) ─────────────────────────

(defn mock-mail
  "Deterministic IMail for tests. `messages` is a seq of
  {:uid :from :subject :date :body} maps. Returns {:mail IMail :state atom};
  the atom records every (-fetch! opts) call — including the :password it
  was handed — so a test can assert the secret reached the impl without
  being returned. Honors :limit when present."
  [messages]
  (let [state (atom {:calls [] :messages messages})]
    {:state state
     :mail (reify IMail
             (-fetch! [_ opts]
               (swap! state update :calls conj opts)
               (let [lim (:limit opts)]
                 (if (or (nil? lim) (neg? lim))
                   messages
                   (take lim messages)))))}))

;; ───────────────────────── curl IMAPS (JVM host) ─────────────────────────

(def default-imap-host "imap.gmail.com")

#?(:clj
   (do

(defn- sh
  "ProcessBuilder shell-out returning {:exit :out :err} — mirrors
  clojure.java.shell/sh's result shape so a caller can inject a fake."
  [& args]
  (let [pb (doto (ProcessBuilder. ^java.util.List (vec args))
             (.redirectErrorStream false))
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    {:exit code :out out :err err}))

(defn- parse-uids [search-out]
  (->> (re-seq #"\* SEARCH([0-9 ]*)" (str search-out)) first second
       (#(when % (remove str/blank? (str/split (str/trim %) #"\s+"))))
       (vec)))

(defn curl-imap-mail
  "JVM IMail impl over `curl imaps://`. Construction opts:
    {:host default-imap-host :mailbox \"INBOX\" :sh sh}
  `:sh` is injectable (returns {:exit :out :err}) for fake-able tests.

  (-fetch! opts): {:account :password :mailbox :host :limit :search}.
  Searches UNSEEN by default; pass :search \"ALL\" to list everything.
  The :password is used ONLY in curl's --user and never appears in the
  returned messages."
  [& [{:keys [host mailbox sh]
       :or {host default-imap-host mailbox "INBOX" sh sh}}]]
  (reify IMail
    (-fetch! [_ opts]
      (let [{:keys [account password limit search]} opts
            lim (or limit 10)
            search* (or search "UNSEEN")
            host* (or (:host opts) host)
            mb* (or (:mailbox opts) mailbox)
            base (format "imaps://%s/%s" host* mb*)
            auth (str account ":" password)
            {:keys [exit out]} (sh "curl" "-sS" "--max-time" "30"
                                   "--url" (str base "?" search*)
                                   "--user" auth)
            uids (if (zero? exit) (parse-uids out) [])]
        (->> (take lim uids)
             (keep (fn [uid]
                     (let [{:keys [exit out]}
                           (sh "curl" "-sS" "--max-time" "30"
                               "--url" (str base ";UID=" uid)
                               "--user" auth)]
                       (when (zero? exit)
                         (parse-message out uid)))))
             vec)))))

   ))

;; ───────────────────────── fetch_mail tool ─────────────────────────

(defn fetch-mail-tool
  "langchain extra-tool: fetch messages via an IMail and return them as
  EDN ({:from :subject :date :body} per message; :uid/:message-id dropped
  to keep the model's context small). The app password is resolved from
  `vault` via `secret-ref` inside :fn and handed to mail/-fetch! only as
  the IMAP credential — it never reaches the model, the message history,
  or the Datomic action log (which records only the model's {:limit N}
  input and the parsed-mail result).

  Construction opts (captured in the closure):
    {:mail IMail  :vault IVault  :secret-ref ref
     :account \"<addr>\"  :mailbox \"INBOX\"
     :host default-imap-host  :limit 10  :search \"UNSEEN\"}
  The model may override :limit per call ({:limit N})."
  [{:keys [mail vault secret-ref account mailbox host limit search]
    :or {mailbox "INBOX" limit 10 search "UNSEEN"}}]
  {:name "fetch_mail"
   :description
   (str "Fetch recent messages from the user's mailbox via IMAP and return "
        "them as EDN: [{:from :subject :date :body}]. Use this to READ mail "
        "only — never send, delete, or change settings. Pass {:limit N} to "
        "control how many (default " limit ").")
   :schema {:type "object"
            :properties {:limit {:type "integer"
                                 :description "Max messages to fetch."}}
            :required []}
   :fn (fn [args]
         (try
           (let [pw (vault/-resolve vault secret-ref)
                 msgs (-fetch! mail
                        {:account account :password pw
                         :mailbox mailbox :host host
                         :limit (or (:limit args) limit)
                         :search search})]
             (pr-str (map #(dissoc % :uid :message-id) msgs)))
           (catch #?(:clj Exception :cljs js/Error) e
             (str "fetch_mail failed: "
                  #?(:clj (.getMessage e) :cljs (.-message e))))))})
