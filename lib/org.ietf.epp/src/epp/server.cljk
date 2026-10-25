(ns epp.server
  "An EPP session as a pure function: session state + frame → session state +
  response frame.

  There is no socket here and no clock. `handle` takes the session, the raw
  XML of one frame, an `srs` registry and `now`, and returns the next session,
  the next registry, the response XML and the `srs` events. A JVM or Node
  socket layer is then a loop that reads frames with `epp.transport` and calls
  this — and a test is the same loop over a vector of strings.

  ## What the session is actually for

  It is tempting to treat login as bookkeeping and put the authorization on the
  registry. That inverts the trust boundary. `srs.core/execute` takes a
  `:command/registrar` and checks that registrar sponsors the object — but it
  has no way to know whether the caller *is* that registrar. The session is the
  only thing that knows, because it is the only thing that saw the password. So
  the registrar is taken from the session and **overwrites** anything the frame
  claimed:

      (assoc command :command/registrar (:session/registrar session))

  A server that trusted the `clID` in the frame would let any authenticated
  registrar act as any other, which is the whole game.

  ## Command-before-login

  RFC 5730 §2.9.1.1: only `<hello>` and `<login>` are valid before
  authentication. Everything else is 2002 (command use error) — not 2200
  (authentication error), which would tell an unauthenticated peer that the
  command *would* have worked."
  (:require [epp.command :as command]
            [epp.response :as response]
            [epp.xmlns :as xmlns]
            [srs.core :as srs]))

(def default-objects
  ["urn:ietf:params:xml:ns:domain-1.0"
   ;; Advertised only once srs.host exists to back it. The greeting is a
   ;; contract — a server that advertises a mapping it cannot serve will be
   ;; sent commands it must then refuse, which is worse than not offering it.
   "urn:ietf:params:xml:ns:host-1.0"])

(def default-extensions
  ["urn:ietf:params:xml:ns:rgp-1.0"])

(defn new-session
  "A session that has not yet authenticated. `:session/greeted?` exists because
  RFC 5730 §2.3 has the *server* speak first: a client connecting is owed a
  greeting before it sends anything."
  [& [{:keys [server-id]}]]
  {:session/state :unauthenticated
   :session/registrar nil
   :session/server-id (or server-id "srs")
   :session/greeted? false
   :session/tx-count 0})

(defn authenticated? [session] (= :authenticated (:session/state session)))

(defn- reply [session registry code opts events]
  {:session session
   :registry registry
   :response (response/response code opts)
   :events (vec events)})

(def ^:private pre-login-allowed
  #{:session/hello :session/login :session/logout})

(defn- sv-trid
  "A server transaction id that is unique within the session and carries the
  session's own count, so a registrar quoting one back can be matched against a
  server log without a database lookup."
  [session]
  (str (:session/server-id session) "-" (:session/tx-count session)))

(defn greeting
  "The frame a server sends on connect, and the answer to `<hello>`."
  [session now]
  (response/greeting {:server-id (:session/server-id session)
                      :now now
                      :objects default-objects
                      :extensions default-extensions}))

(defn handle
  "Process one inbound frame.

  `authenticate` is `(fn [clID pw] -> true/false)`, injected rather than
  implemented: credentials are the operator's, and a library that owned them
  would need somewhere to keep them. Omitting it refuses every login, which is
  the safe default — a server that authenticated everyone because its operator
  forgot to pass a function is the failure mode worth designing out."
  [session registry xml-string now & [{:keys [authenticate]}]]
  (let [session (update session :session/tx-count inc)
        frame (xmlns/parse xml-string)
        cmd (command/parse frame)
        tx-id (:command/tx-id cmd)
        opts {:cl-trid tx-id :sv-trid (sv-trid session)}
        kind (:command/kind cmd)]
    (cond
      (:error cmd)
      (reply session registry (or (get-in cmd [:error :error/code]) 2001)
             (assoc opts :message (get-in cmd [:error :error/message])
                    :cl-trid (get-in cmd [:error :error/tx-id]))
             [])

      (= kind :session/hello)
      {:session (assoc session :session/greeted? true)
       :registry registry
       :response (greeting session now)
       :events []}

      (= kind :session/login)
      (cond
        (authenticated? session)
        (reply session registry 2002 (assoc opts :message "Already logged in") [])

        (not (and authenticate (authenticate (:registrar cmd) (:password cmd))))
        ;; 2501 rather than 2200: RFC 5730 §2.9.1.1 has the server close the
        ;; connection on a failed login, and saying so in the code is what lets
        ;; a client stop retrying on the same connection.
        (reply (assoc session :session/state :closed) registry 2501
               (assoc opts :message "Authentication failed") [])

        ;; The greeting advertised a service menu; §2.9.1.1 makes login's
        ;; <svcs> a subset of it. A registrar asking for a mapping this server
        ;; does not serve must be refused now rather than at first use.
        (seq (remove (set default-objects) (:objects cmd)))
        (reply session registry 2307
               (assoc opts :message
                      (str "Unsupported object service: "
                           (first (remove (set default-objects) (:objects cmd)))))
               [])

        :else
        (reply (assoc session :session/state :authenticated
                      :session/registrar (:registrar cmd))
               registry 1000 opts []))

      (= kind :session/logout)
      (reply (assoc session :session/state :closed :session/registrar nil)
             registry 1500 opts [])

      (not (authenticated? session))
      (reply session registry 2002
             (assoc opts :message "Command requires an authenticated session") [])

      ;; ── authenticated object commands ─────────────────────────────────
      (= kind :domain/check)
      {:session session
       :registry registry
       :response (response/check-response
                  (for [n (:command/names cmd)]
                    (let [avail (srs/available? registry n)]
                      {:name n :available? avail
                       :reason (when-not avail
                                 (if (srs/in-namespace? registry n)
                                   "In use"
                                   "Not a name this registry serves"))}))
                  cmd {:sv-trid (sv-trid session)})
       :events []}

      (= kind :domain/info)
      (if-let [d (srs/info registry (:command/name cmd) now)]
        {:session session :registry registry
         :response (response/response 1000 (assoc opts :res-data (response/infData d)))
         :events []}
        (reply session registry 2303
               (assoc opts :message (str "Object does not exist: " (:command/name cmd))) []))

      (= kind :domain/transfer-query)
      (if-let [d (srs/domain registry (:command/name cmd))]
        {:session session :registry registry
         :response (response/response (if (:domain/transfer d) 1000 2301)
                                      (cond-> opts
                                        (:domain/transfer d)
                                        (assoc :res-data (response/trnData d :pending))))
         :events []}
        (reply session registry 2303 (assoc opts :message "Object does not exist") []))

      :else
      (let [cmd' (assoc cmd :command/registrar (:session/registrar session))
            result (srs/execute registry cmd' now)]
        {:session session
         :registry (if (:ok? result) (:registry result) registry)
         :response (response/from-srs result cmd' {:sv-trid (sv-trid session)})
         :events (vec (:events result))}))))

(defn closed? [session] (= :closed (:session/state session)))
