(ns epp.command
  "Parse an EPP command frame into the command map `srs.core/execute` takes.

  The mapping is deliberately total in one direction and partial in the other:
  every EPP domain command this library understands becomes an `srs` command,
  and anything it does not understand becomes an explicit `:error` rather than
  a silently dropped element. An EPP server that ignores an element it did not
  recognize has told a registrar their command succeeded when part of it did
  not happen.

  Frames arrive here already canonicalized by `epp.xmlns/parse`, so matching is
  on resolved namespaces rather than on whatever prefix the client chose.

  ## Where the restore commands come from

  RGP restore is not an EPP command. It is an `<update>` carrying an RGP
  extension (RFC 3915 §4.1), and the difference between requesting a restore
  and filing the report is an attribute on that extension. So `:domain/update`
  and `:domain/restore` and `:domain/restore-report` all arrive as the same
  `<update>` element, and this namespace is where they are told apart — which
  is why the extension is read before the update body rather than after."
  (:require [kotoba.lang.text :as str]
            [srs.time :as t]
            [xml.parse :as xp]))

(defn- text [el] (some-> el xp/el-text str/trim not-empty))

(defn- child-text [el tag] (text (xp/find-child el tag)))

(defn- err [code message]
  {:error {:error/code code :error/message message}})

;; ── the object-mapping bodies ─────────────────────────────────────────────

(defn- period
  "`<domain:period unit=\"y\">2</domain:period>`.

  A month unit is legal EPP and is refused rather than converted: 18 months is
  not 1 year and is not 2, and a registry that rounds has mispriced the
  registration in the registrant's disfavour or its own. `srs` terms are whole
  years, so a month period is a policy error with a reason attached."
  [el]
  (when-let [p (xp/find-child el :domain/period)]
    (let [unit (or (xp/el-attr p "unit") "y")
          v (text p)
          n #?(:clj #(try (Long/parseLong %) (catch Exception _ nil))
               :cljs #(let [x (js/parseInt % 10)] (when-not (js/isNaN x) x)))]
      (cond
        (not= unit "y") {:error (:error (err 2306 (str "Unsupported period unit '" unit
                                                       "'; this registry registers in whole years")))}
        (nil? (n v)) {:error (:error (err 2005 (str "Malformed period: " v)))}
        :else {:years (n v)}))))

(defn- nameservers
  "`<domain:ns>` holds either `<domain:hostObj>` (a reference to a host object)
  or `<domain:hostAttr>` (an inline name with optional glue). Both are read;
  `srs` stores nameservers as names, so glue addresses are carried alongside
  rather than dropped, for a caller that maintains the zone."
  [el]
  (when-let [ns-el (xp/find-child el :domain/ns)]
    (let [objs (mapv text (xp/find-children ns-el :domain/hostObj))
          attrs (mapv (fn [ha]
                        {:name (child-text ha :domain/hostName)
                         :addrs (mapv text (xp/find-children ha :domain/hostAddr))})
                      (xp/find-children ns-el :domain/hostAttr))]
      (cond-> {}
        (seq objs) (assoc :nameservers objs)
        (seq attrs) (assoc :nameservers (mapv :name attrs)
                           :glue attrs)))))

(defn- auth-info
  "`<domain:authInfo><domain:pw>…</domain:pw></domain:authInfo>` — the shared
  secret that stands for the registrant's consent to a transfer."
  [el]
  (some-> (xp/find-child el :domain/authInfo)
          (xp/find-child :domain/pw)
          text))

(defn- statuses [el tag]
  (mapv #(keyword (xp/el-attr % "s")) (xp/find-children el tag)))

;; ── per-command parsing ───────────────────────────────────────────────────

(defn- parse-create [body]
  (let [p (period body)]
    (or (when (:error p) p)
        (merge {:command/kind :domain/create
                :command/name (child-text body :domain/name)
                :registrant (child-text body :domain/registrant)
                :auth-info (auth-info body)}
               (select-keys p [:years])
               (nameservers body)))))

(defn- parse-renew [body]
  (let [p (period body)
        cur (child-text body :domain/curExpDate)]
    (or (when (:error p) p)
        (if (and cur (nil? (t/parse-date cur)))
          (err 2005 (str "Malformed curExpDate: " cur))
          (merge {:command/kind :domain/renew
                  :command/name (child-text body :domain/name)
                  :current-expires-at (t/parse-date cur)}
                 (select-keys p [:years]))))))

(defn- parse-delete [body]
  {:command/kind :domain/delete :command/name (child-text body :domain/name)})

(defn- parse-transfer
  "`op` is an attribute on the *core* `<transfer>` element, not on the object
  mapping (RFC 5730 §2.5). Reading it from the wrong element is why some
  implementations treat every transfer as a request."
  [body op]
  (let [kind (case op
               "request" :domain/transfer-request
               "approve" :domain/transfer-approve
               "reject"  :domain/transfer-reject
               "cancel"  :domain/transfer-cancel
               "query"   :domain/transfer-query
               nil)]
    (if-not kind
      (err 2005 (str "Unknown transfer op: " op))
      (merge {:command/kind kind
              :command/name (child-text body :domain/name)
              :auth-info (auth-info body)}
             (select-keys (or (period body) {}) [:years])))))

(defn- parse-update [body]
  (let [add (xp/find-child body :domain/add)
        rem (xp/find-child body :domain/rem)
        chg (xp/find-child body :domain/chg)]
    (cond-> {:command/kind :domain/update
             :command/name (child-text body :domain/name)}
      add (assoc :add-statuses (statuses add :domain/status))
      rem (assoc :remove-statuses (statuses rem :domain/status))
      chg (cond->
            (child-text chg :domain/registrant) (assoc :registrant (child-text chg :domain/registrant))
            (auth-info chg) (assoc :auth-info (auth-info chg)))
      ;; An update that names nameservers replaces the set. EPP's add/rem model
      ;; is incremental, so the caller is handed both halves and `srs` is given
      ;; the resolved set only when one is unambiguous.
      (and add (seq (:nameservers (nameservers add))))
      (assoc :add-nameservers (:nameservers (nameservers add)))
      (and rem (seq (:nameservers (nameservers rem))))
      (assoc :remove-nameservers (:nameservers (nameservers rem))))))

(defn- rgp-restore
  "The RGP extension on an `<update>`, if present (RFC 3915 §4.1/§4.2).
  Returns `:request`, `:report`, or nil."
  [command-el]
  (some-> (xp/find-child command-el :extension)
          (xp/find-child :rgp/update)
          (xp/find-child :rgp/restore)
          (xp/el-attr "op")
          (case "request" :request "report" :report nil)))

;; ── session commands ──────────────────────────────────────────────────────

(defn- parse-login [body]
  {:command/kind :session/login
   :registrar (child-text body :clID)
   :password (child-text body :pw)
   :new-password (child-text body :newPW)
   :versions (mapv text (xp/find-all body :version))
   :languages (mapv text (xp/find-all body :lang))
   :objects (mapv text (some-> (xp/find-child body :svcs) (xp/find-children :objURI)))
   :extensions (mapv text (some-> (xp/find-child body :svcs)
                                  (xp/find-child :svcExtension)
                                  (xp/find-children :extURI)))})

;; ── entry point ───────────────────────────────────────────────────────────

(defn- host-body
  "The `host-1.0` half of a command element, if present. Checked *after* the
  domain mapping so a frame carrying both — which is malformed — resolves the
  same way every time rather than depending on map ordering."
  [core tag]
  (xp/find-child core (get {:create :host/create :update :host/update
                            :delete :host/delete :info :host/info
                            :check :host/check}
                           tag)))

(defn- parse-host-create
  "`<host:create>` (RFC 5732 §3.2.1). Addresses carry an `ip` attribute of
  `v4`/`v6`; the default when absent is **v4** (§4.2), not \"guess from the
  string\" — a v6 address sent without the attribute is a malformed frame and
  guessing would accept it and store it under the wrong family."
  [body]
  {:command/kind :host/create
   :command/name (child-text body :host/name)
   :addresses (mapv (fn [a]
                      {:address (text a)
                       :family (case (or (xp/el-attr a "ip") "v4")
                                 "v6" :v6 :v4)})
                    (xp/find-children body :host/addr))})

(defn- parse-host-update [body]
  (let [add (xp/find-child body :host/add)
        rem (xp/find-child body :host/rem)
        chg (xp/find-child body :host/chg)]
    (cond-> {:command/kind :host/update
             :command/name (child-text body :host/name)}
      add (assoc :add-addresses (mapv text (xp/find-children add :host/addr))
                 :add-statuses (statuses add :host/status))
      rem (assoc :remove-addresses (mapv text (xp/find-children rem :host/addr))
                 :remove-statuses (statuses rem :host/status))
      (and chg (child-text chg :host/name))
      (assoc :new-name (child-text chg :host/name)))))

(def ^:private object-body
  "Which object-mapping element carries the body of each core command."
  {:create :domain/create
   :renew  :domain/renew
   :delete :domain/delete
   :transfer :domain/transfer
   :update :domain/update
   :info   :domain/info
   :check  :domain/check})

(defn parse
  "A canonicalized EPP frame → a command map, or `{:error {…}}`.

  The returned map is what `srs.core/execute` accepts, plus `:command/tx-id`
  (the client transaction id, RFC 5730 §2.5) which must be echoed in the
  response so a registrar can correlate a reply with the command that caused
  it — the one field that makes an asynchronous EPP session debuggable."
  [frame]
  (cond
    (nil? frame) (err 2001 "Empty or unparseable frame")
    (= :hello (xp/el-tag frame)) {:command/kind :session/hello}
    (not= :epp (xp/el-tag frame)) (err 2001 (str "Not an EPP frame: " (xp/el-tag frame)))

    :else
    (if-let [hello (xp/find-child frame :hello)]
      (do hello {:command/kind :session/hello})
      (if-let [cmd (xp/find-child frame :command)]
        (let [tx-id (child-text cmd :clTRID)
              core (first (keep #(xp/find-child cmd %)
                                [:login :logout :poll :create :renew :delete
                                 :transfer :update :info :check]))
              core-tag (some-> core xp/el-tag)
              body (some-> core (xp/find-child (object-body core-tag)))
              restore (rgp-restore cmd)
              result
              (case core-tag
                :login  (parse-login core)
                :logout {:command/kind :session/logout}
                :poll   {:command/kind :session/poll
                         :op (or (xp/el-attr core "op") "req")
                         :msg-id (xp/el-attr core "msgID")}
                nil     (err 2000 "No recognized command element")
                ;; Object commands need a body in a namespace we serve.
                (if (nil? body)
                  ;; No domain mapping — try the host one before refusing, so a
                  ;; registrar provisioning nameservers is not told the object
                  ;; class does not exist.
                  (if-let [hb (host-body core core-tag)]
                    (case core-tag
                      :create (parse-host-create hb)
                      :update (parse-host-update hb)
                      :delete {:command/kind :host/delete :command/name (child-text hb :host/name)}
                      :info   {:command/kind :host/info :command/name (child-text hb :host/name)}
                      :check  {:command/kind :host/check
                               :command/names (mapv text (xp/find-children hb :host/name))}
                      (err 2101 (str "<" (name core-tag) "> is not defined for host objects")))
                    (err 2101 (str "Unsupported object mapping for <"
                                   (name core-tag) ">; this server serves domain and host objects")))
                  (case core-tag
                    :create (parse-create body)
                    :renew  (parse-renew body)
                    :delete (parse-delete body)
                    :transfer (parse-transfer body (xp/el-attr core "op"))
                    :update (case restore
                              :request {:command/kind :domain/restore
                                        :command/name (child-text body :domain/name)}
                              :report  {:command/kind :domain/restore-report
                                        :command/name (child-text body :domain/name)}
                              (parse-update body))
                    :info   {:command/kind :domain/info
                             :command/name (child-text body :domain/name)
                             :auth-info (auth-info body)}
                    :check  {:command/kind :domain/check
                             :command/names (mapv text (xp/find-children body :domain/name))})))]
          (if (:error result)
            (assoc-in result [:error :error/tx-id] tx-id)
            (cond-> (assoc result :command/tx-id tx-id)
              ;; Drop keys the caller did not send rather than passing nils
              ;; through — `srs` distinguishes "not supplied" from "supplied
              ;; empty", and a nil authInfo that looked supplied would fail a
              ;; transfer for the wrong reason.
              true (->> (remove (comp nil? val)) (into {})))))
        (err 2001 "Frame contains neither <hello> nor <command>")))))
