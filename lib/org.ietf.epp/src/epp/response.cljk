(ns epp.response
  "Build EPP response and greeting frames from `srs` results.

  Two rules shape everything here.

  **The result code is the interface.** RFC 5730 §3 gives a registrar's client
  a numeric code it can branch on; the `<msg>` is for a human reading a log.
  A server that returns 2400 (\"command failed\") for everything has moved the
  entire diagnosis into prose, and prose is what clients cannot read. `srs`
  already carries the specific code — 2302 for a name taken, 2301 for nothing
  to approve, 2304 with the actual blocking statuses — so this namespace is
  a projection rather than a decision.

  **`clTRID` is echoed, always.** EPP is a pipelined protocol: a registrar can
  have many commands in flight, and the client transaction id is the only thing
  tying a response to the command that caused it (RFC 5730 §2.5). Dropping it on
  the error path — the usual omission, because the error path is written
  second — makes exactly the failures you need to debug the ones you cannot
  attribute."
  (:require [epp.xmlns :as xmlns]
            [srs.time :as t]
            [xml.core :as xc]))

(def messages
  "RFC 5730 §3. Present in full rather than as the handful this server emits:
  the table is the specification's, and a partial copy is a copy that will be
  wrong the first time a new code is used."
  {1000 "Command completed successfully"
   1001 "Command completed successfully; action pending"
   1300 "Command completed successfully; no messages"
   1301 "Command completed successfully; ack to dequeue"
   1500 "Command completed successfully; ending session"
   2000 "Unknown command"
   2001 "Command syntax error"
   2002 "Command use error"
   2003 "Required parameter missing"
   2004 "Parameter value range error"
   2005 "Parameter value syntax error"
   2100 "Unimplemented protocol version"
   2101 "Unimplemented command"
   2102 "Unimplemented option"
   2103 "Unimplemented extension"
   2104 "Billing failure"
   2105 "Object is not eligible for renewal"
   2106 "Object is not eligible for transfer"
   2200 "Authentication error"
   2201 "Authorization error"
   2202 "Invalid authorization information"
   2300 "Object pending transfer"
   2301 "Object not pending transfer"
   2302 "Object exists"
   2303 "Object does not exist"
   2304 "Object status prohibits operation"
   2305 "Object association prohibits operation"
   2306 "Parameter value policy error"
   2307 "Unimplemented object service"
   2308 "Data management policy violation"
   2400 "Command failed"
   2500 "Command failed; server closing connection"
   2501 "Authentication error; server closing connection"
   2502 "Session limit exceeded; server closing connection"})

(defn success? [code] (< code 2000))

(defn- epp-frame [& children]
  (into [:epp {"xmlns" xmlns/epp-uri}] children))

(defn- ns-attrs
  "The `xmlns:` declaration an object-mapping element needs. Declared on the
  element itself rather than hoisted to the root, because a response may carry
  more than one object mapping and hoisting makes the frame's namespaces
  depend on what happens to be in it."
  [canonical]
  {(str "xmlns:" (xmlns/canonical-prefix canonical))
   (xmlns/object-uri canonical)})

(defn- trID [cl-trid sv-trid]
  [:trID
   (when cl-trid [:clTRID cl-trid])
   [:svTRID (or sv-trid "srs-0000000000")]])

(defn- compact
  "Drop nils so an absent optional element emits nothing rather than an empty
  tag. `<domain:registrant/>` is not the same as no registrant — it asserts
  the registrant is the empty string."
  [form]
  (if (vector? form)
    (into [] (comp (remove nil?) (map compact)) form)
    form))

;; ── resData bodies ────────────────────────────────────────────────────────

(defn creData [d]
  [:domain/creData (ns-attrs "domain")
   [:domain/name (:domain/name d)]
   [:domain/crDate (t/iso8601 (:domain/created-at d))]
   (when (:domain/expires-at d) [:domain/exDate (t/iso8601 (:domain/expires-at d))])])

(defn renData [d]
  [:domain/renData (ns-attrs "domain")
   [:domain/name (:domain/name d)]
   [:domain/exDate (t/iso8601 (:domain/expires-at d))]])

(defn trnData
  "RFC 5731 §3.2.4. `trStatus` is where a registrar learns whether the transfer
  it just asked for is pending or already done — the auto-approve window means
  both are ordinary outcomes."
  [d status]
  (let [x (:domain/transfer d)]
    [:domain/trnData (ns-attrs "domain")
     [:domain/name (:domain/name d)]
     [:domain/trStatus (name status)]
     (when x [:domain/reID (:transfer/gaining-registrar x)])
     (when x [:domain/reDate (t/iso8601 (:transfer/requested-at x))])
     (when x [:domain/acID (:transfer/losing-registrar x)])
     (when (:domain/expires-at d) [:domain/exDate (t/iso8601 (:domain/expires-at d))])]))

(defn infData
  "The `<domain:infData>` of RFC 5731 §3.1.2. Statuses are the *projected* set
  from `srs.core/info`, so what a registrar reads here is what the lifecycle
  will actually enforce — not a stored copy that can disagree with the dates."
  [d]
  (into [:domain/infData (ns-attrs "domain")
         [:domain/name (:domain/name d)]
         [:domain/roid (str (:domain/name d) "-SRS")]]
        (concat
         (for [s (sort (:domain/statuses d))] [:domain/status {"s" (name s)}])
         [(when (:domain/registrant d) [:domain/registrant (:domain/registrant d)])]
         (when (seq (:domain/nameservers d))
           [(into [:domain/ns] (for [h (:domain/nameservers d)] [:domain/hostObj h]))])
         [[:domain/clID (:domain/registrar d)]
          (when (:domain/created-at d) [:domain/crDate (t/iso8601 (:domain/created-at d))])
          (when (:domain/expires-at d) [:domain/exDate (t/iso8601 (:domain/expires-at d))])
          (when (:domain/updated-at d) [:domain/upDate (t/iso8601 (:domain/updated-at d))])
          (when (:domain/transferred-at d) [:domain/trDate (t/iso8601 (:domain/transferred-at d))])])))

(defn chkData
  "`<domain:chkData>` — availability. `avail=\"0\"` carries a `<domain:reason>`,
  which is the difference between \"taken\" and \"not a name this registry
  serves\": both are unavailable and a registrar needs to act differently."
  [results]
  (into [:domain/chkData (ns-attrs "domain")]
        (for [{:keys [name available? reason]} results]
          [:domain/cd
           [:domain/name {"avail" (if available? "1" "0")} name]
           (when (and (not available?) reason) [:domain/reason reason])])))

(def res-data
  "Command kind → the `resData` builder it produces, if any. Info, create,
  renew, transfer and check answer with data; delete and update answer with a
  bare result, which is correct and not an omission."
  {:domain/create creData
   :domain/renew renData
   :domain/info infData})

;; ── frames ────────────────────────────────────────────────────────────────

(defn response
  "Build a response frame.

  `opts` may carry `:res-data` (a hiccup form), `:statuses` (for a 2304, so the
  `<extValue>` names the blocking statuses rather than making a registrar
  guess), `:cl-trid` and `:sv-trid`."
  [code {:keys [message res-data cl-trid sv-trid statuses]}]
  (xc/compact
   (compact
    (epp-frame
     [:response
      (into [:result {"code" (str code)}
             [:msg (or message (get messages code) "Command failed")]]
            ;; RFC 5730 §2.6: extValue carries machine-usable detail alongside
            ;; the human message. The blocking statuses are exactly that — a
            ;; registrar can clear a `client*` lock itself and cannot clear a
            ;; `server*` one, and only the specific status says which.
            (for [s statuses]
              [:extValue
               [:value [:domain/status (merge (ns-attrs "domain") {"s" (name s)})]]
               [:reason (str "Prohibited by " (name s))]]))
      (when res-data [:resData res-data])
      (trID cl-trid sv-trid)]))))

(defn from-srs
  "Project an `srs.core/execute` result onto an EPP response.

  This is the only place the two vocabularies meet, and it is intentionally
  thin: `srs` already decided the outcome and the code, so a bug here can
  garble a response but cannot change what the registry did."
  [{:keys [ok? domain error]} {:keys [command/kind command/tx-id]} & [{:keys [sv-trid]}]]
  (if-not ok?
    (response (or (:error/code error) 2400)
              {:message (:error/message error)
               :statuses (:error/statuses error)
               :cl-trid tx-id :sv-trid sv-trid})
    (let [build (res-data kind)
          pending? (and (= kind :domain/transfer-request) (:domain/transfer domain))]
      (response
       (if pending? 1001 1000)
       {:res-data (cond
                    build (build domain)
                    (#{:domain/transfer-request :domain/transfer-approve
                       :domain/transfer-reject :domain/transfer-cancel} kind)
                    (trnData domain (case kind
                                      :domain/transfer-request (if pending? :pending :clientApproved)
                                      :domain/transfer-approve :clientApproved
                                      :domain/transfer-reject  :clientRejected
                                      :domain/transfer-cancel  :clientCancelled))
                    :else nil)
        :cl-trid tx-id :sv-trid sv-trid}))))

(defn check-response
  [results {:keys [command/tx-id]} & [{:keys [sv-trid]}]]
  (response 1000 {:res-data (chkData results) :cl-trid tx-id :sv-trid sv-trid}))

(defn greeting
  "RFC 5730 §2.4. The `<svcMenu>` is a contract: it lists the object mappings
  and extensions this server will accept, and `<login>` is checked against it.
  A server that advertises a mapping it does not implement will be sent
  commands it cannot answer.

  The `<dcp>` (data collection policy) block is **required** by RFC 5730 §2.4 —
  a greeting without one is malformed, and some clients refuse the session. The
  values here are the honest ones for a registry: contact data is collected for
  the purpose of running the registry, and it is disclosed to the parties the
  protocol requires."
  [{:keys [server-id now objects extensions languages]}]
  (xc/compact
   (compact
    (epp-frame
     [:greeting
      [:svID (or server-id "srs")]
      [:svDate (t/iso8601 now)]
      ;; `<version>`, `<lang>` and `<objURI>` are siblings inside `<svcMenu>`,
       ;; repeated rather than wrapped (RFC 5730 §2.4). Spliced with `concat`
       ;; because hiccup has no fragment node and an invented wrapper element
       ;; would make the greeting fail schema validation.
       (into [:svcMenu [:version "1.0"]]
             (concat (for [l (or languages ["en"])] [:lang l])
                     (for [o objects] [:objURI o])
                     (when (seq extensions)
                       [(into [:svcExtension] (for [e extensions] [:extURI e]))])))
      [:dcp
       [:access [:all]]
       [:statement
        [:purpose [:admin] [:prov]]
        [:recipient [:ours] [:public]]
        [:retention [:stated]]]]]))))
