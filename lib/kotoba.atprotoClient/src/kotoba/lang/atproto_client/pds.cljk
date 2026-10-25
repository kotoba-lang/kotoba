(ns kotoba.lang.atproto-client.pds
  "PDS session + record read/write helpers -- PURE core over an injected
  IHttp transport (via kotoba.lang.atproto-client.atproto).

  Every function is expressed purely in terms of atproto/xrpc (which drives
  the agent's IHttp); none touch the network directly. Functions that build
  an agent (create-account, login, get-agent, health) take an `:http` (IHttp)
  so the transport is always host-injected. resolve-pds takes `http` directly.
  Request/response maps keep the same camelCase keyword keys as the wire JSON.

  Scoped out (see README): AtpAgent's automatic 401 -> refreshSession retry
  is not reimplemented; callers re-login/re-get-agent on auth failure."
  (:require [kotoba.lang.atproto-client.atproto :as atproto]
            [kotoba.lang.text :as str]
            #?(:clj [json.data-json :as json])))

(def default-pds
  "Default PDS service endpoint, matching pds.ts's DEFAULT_PDS."
  "https://pds.aozora.app")

;; ─── Session ──────────────────────────────────────────────────────────────

(defn create-account
  "Create a new account. Returns {:did :handle :accessJwt :refreshJwt}.
  opts: {:http <IHttp> :service? :handle :email :password :inviteCode?}"
  [opts]
  (let [service (or (:service opts) default-pds)
        agent (atproto/create-agent {:service service :http (:http opts) :headers (:headers opts)})
        body (cond-> {:handle (:handle opts) :email (:email opts) :password (:password opts)}
               (:inviteCode opts) (assoc :inviteCode (:inviteCode opts)))
        res (atproto/xrpc agent :post "com.atproto.server.createAccount" body)]
    (select-keys res [:did :handle :accessJwt :refreshJwt])))

(defn login
  "Log in with identifier (handle/DID) + password. Returns {:did :handle
  :accessJwt :refreshJwt}. Wire call: POST com.atproto.server.createSession.
  opts: {:http <IHttp> :service? :identifier :password}"
  [opts]
  (let [service (or (:service opts) default-pds)
        agent (atproto/create-agent {:service service :http (:http opts) :headers (:headers opts)})
        res (atproto/xrpc agent :post "com.atproto.server.createSession"
                          {:identifier (:identifier opts) :password (:password opts)})]
    (select-keys res [:did :handle :accessJwt :refreshJwt])))

(defn get-agent
  "Get an authenticated agent. cfg: {:http <IHttp> :service?} & ({:handle
  :password} | {:session {...}}). On :session, verifies via getSession."
  [cfg]
  (let [service (or (:service cfg) default-pds)
        base (atproto/create-agent {:service service :http (:http cfg) :headers (:headers cfg)})]
    (if-let [session (:session cfg)]
      (let [agent0 (assoc base :session session)
            verified (atproto/xrpc agent0 :get "com.atproto.server.getSession")]
        (assoc agent0 :session (merge session (select-keys verified [:did :handle]))))
      (let [session (login {:http (:http cfg) :service service
                            :identifier (:handle cfg) :password (:password cfg)})]
        (assoc base :session session)))))

;; ─── Records ──────────────────────────────────────────────────────────────

(defn create-record
  "Create an AT Record. Returns {:uri :cid}. $type = collection is merged in."
  ([agent did collection record] (create-record agent did collection record nil))
  ([agent did collection record rkey]
   (let [body (cond-> {:repo did :collection collection
                       :record (assoc record :$type collection)}
                rkey (assoc :rkey rkey))
         res (atproto/xrpc agent :post "com.atproto.repo.createRecord" body)]
     (select-keys res [:uri :cid]))))

(defn get-record
  "Read one record. Returns {:uri :cid :value} or nil if not found."
  [agent did collection rkey]
  (try
    (let [res (atproto/xrpc agent :get "com.atproto.repo.getRecord"
                            {:repo did :collection collection :rkey rkey})]
      (select-keys res [:uri :cid :value]))
    (catch #?(:clj Exception :cljs :default) e
      (let [msg (or (ex-message e) "")]
        (if (or (str/includes? msg "not found") (str/includes? msg "Record not found"))
          nil
          (throw e))))))

(defn list-records
  "List records with cursor pagination. Returns {:records [...] :cursor?}.
  opts: {:limit? :cursor? :reverse?}"
  ([agent did collection] (list-records agent did collection {}))
  ([agent did collection opts]
   (let [query (cond-> {:repo did :collection collection :limit (or (:limit opts) 50)}
                 (:cursor opts) (assoc :cursor (:cursor opts))
                 (contains? opts :reverse) (assoc :reverse (:reverse opts)))
         res (atproto/xrpc agent :get "com.atproto.repo.listRecords" query)]
     {:records (mapv #(select-keys % [:uri :cid :value]) (:records res))
      :cursor (:cursor res)})))

;; ─── Liveness ─────────────────────────────────────────────────────────────

(defn health
  "PDS liveness check via `http` (IHttp). Returns true on 2xx, false on error.
  ([http] uses default-pds.)"
  ([http] (health http nil))
  ([http service]
   (let [agent (atproto/create-agent {:service (or service default-pds) :http http})]
     (try
       (atproto/xrpc agent :get "_health")
       true
       (catch #?(:clj Exception :cljs :default) _ false)))))

;; ─── did:web resolution ───────────────────────────────────────────────────

(defn- did-web->url
  "did:web -> its .well-known/did.json URL (v0.1: did:web only; ':' after the
  prefix -> '/', no percent-decoding, same limitation as the original TS)."
  [did]
  (let [host (str/replace (subs did (count "did:web:")) ":" "/")]
    (str "https://" host "/.well-known/did.json")))

(defn- pick-pds-service
  "Find the AtprotoPersonalDataServer service entry in a did.json doc."
  [doc did]
  (->> (:service doc)
       (filter (fn [s] (or (= (:type s) "AtprotoPersonalDataServer")
                           (= (:id s) "#atproto_pds")
                           (= (:id s) (str did "#atproto_pds")))))
       first))

(defn- parse-json-kw [s]
  #?(:clj  (json/read-str s :key-fn keyword)
     :cljs (js->clj (js/JSON.parse s) :keywordize-keys true)))

#?(:clj
   (defn- fetch-json
     "Plain GET + JSON parse of an arbitrary (non-XRPC) URL via `http` (IHttp).
      Private; exercised in tests via a host-injected IHttp."
     [http url]
     (let [resp (atproto/-request http {:method :get :url url :headers {} :body nil})]
       {:ok (<= 200 (:status resp) 299)
        :status (:status resp)
        :body (when (seq (:body resp))
                (try (parse-json-kw (:body resp))
                     (catch Exception _ nil)))})))

#?(:cljs
   (defn- fetch-json
     "CLJS counterpart -- returns js/Promise of {:ok :status :body}."
     [http url]
     (-> (atproto/-request http {:method :get :url url :headers {} :body nil})
         (.then (fn [resp]
                  {:ok (<= 200 (:status resp) 299)
                   :status (:status resp)
                   :body (when (seq (:body resp))
                           (try (parse-json-kw (:body resp))
                                (catch :default _ nil)))})))))

#?(:clj
   (defn resolve-pds
     "Resolve a DID to its PDS endpoint via its DID document (v0.1: did:web
     only). `http` is the IHttp transport for the did.json fetch."
     [http did]
     (if-not (str/starts-with? did "did:web:")
       (throw (ex-info (str "[kotoba.lang.atproto-client/pds] resolvePds: did method not yet supported: "
                            did " (v0.1 = did:web only; did:plc next)") {:did did}))
       (let [url (did-web->url did)
             {:keys [ok body]} (fetch-json http url)]
         (when-not ok
           (throw (ex-info (str "[kotoba.lang.atproto-client/pds] resolvePds: did.json not reachable at " url)
                           {:did did :url url})))
         (if-let [pds (pick-pds-service body did)]
           (:serviceEndpoint pds)
           (throw (ex-info (str "[kotoba.lang.atproto-client/pds] resolvePds: no AtprotoPersonalDataServer service entry in " url)
                           {:did did :url url})))))))

#?(:cljs
   (defn resolve-pds
     "CLJS counterpart -- returns js/Promise of the PDS endpoint string."
     [http did]
     (if-not (str/starts-with? did "did:web:")
       (js/Promise.reject
        (js/Error. (str "[kotoba.lang.atproto-client/pds] resolvePds: did method not yet supported: "
                        did " (v0.1 = did:web only; did:plc next)")))
       (let [url (did-web->url did)]
         (-> (fetch-json http url)
             (.then (fn [{:keys [ok body]}]
                      (if-not ok
                        (throw (js/Error. (str "[kotoba.lang.atproto-client/pds] resolvePds: did.json not reachable at " url)))
                        (if-let [pds (pick-pds-service body did)]
                          (:serviceEndpoint pds)
                          (throw (js/Error. (str "[kotoba.lang.atproto-client/pds] resolvePds: no AtprotoPersonalDataServer service entry in " url))))))))))))
