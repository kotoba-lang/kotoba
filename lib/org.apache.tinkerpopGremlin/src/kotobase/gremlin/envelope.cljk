(ns kotobase.gremlin.envelope
  "GraphSON RequestMessage/ResponseMessage codec and request dispatch —
  everything about the Gremlin wire that is NOT a socket.

  Split out of `kotobase.gremlin.wire` (2026-07-30) so this half can run
  somewhere `node:net` cannot. `wire.cljs` owns the RFC 6455 handshake and
  frame codec over raw `node:net` and stays `.cljs` for exactly the reason
  its docstring gives; but a Cloudflare Worker gets its WebSocket frames
  already decoded from `WebSocketPair`, so it needs the envelope and the
  dispatch and none of the transport. Requiring `wire` there would pull
  `node:net`/`node:crypto` into a bundle that has neither.

  Nothing moved changed semantics. `wire` now requires this namespace and
  re-exports the same vars under the same names, so every existing caller
  and its tests keep working unmodified.

  `.cljc` rather than `.cljs` because none of it is host-specific once the
  three places that were (`js/Date`, `catch :default`, `.-message`) are
  written portably. The scope notes in `wire`'s docstring — no GraphSON
  typed `@type`/`@value` wrappers, `op` must be `\"bytecode\"`, no
  `\"eval\"` — are unchanged and still the honest description of this
  subset."
  (:require [kotobase.gremlin.json :as json]
            [kotobase.gremlin.traversal :as traversal]))

(defn bytecode-json->edn
  "GraphSON-approximation `args.gremlin` JSON value (a JSON array of JSON
  arrays, e.g. `[[\"V\"] [\"hasLabel\" \"users\"] [\"values\" \"name\"]]`,
  already JSON-parsed to EDN vectors of STRINGS by `kotobase.gremlin.json`)
  -> `kotobase.gremlin.traversal`'s bytecode shape (vectors whose first
  element is a KEYWORD step name, see that ns's docstring)."
  [gremlin]
  (when-not (sequential? gremlin)
    (throw (ex-info "args.gremlin must be a JSON array of [step, ...args] arrays"
                    {:gremlin/code :gremlin/malformed-request})))
  (mapv (fn [tup]
          (when-not (and (sequential? tup) (seq tup) (string? (first tup)))
            (throw (ex-info (str "each args.gremlin entry must be a non-empty array whose"
                                 " first element is a step-name string -- got " (pr-str tup))
                            {:gremlin/code :gremlin/malformed-request})))
          (into [(keyword (first tup))] (rest tup)))
        gremlin))

(defn request-message->bytecode
  "Parsed RequestMessage JSON (string keys) -> `[request-id bytecode]`, or
  throws (`(:gremlin/code (ex-data e))` = `:gremlin/malformed-request`) for
  anything outside the v0.1 wire subset."
  [{:strs [requestId op args]}]
  (when-not (string? requestId)
    (throw (ex-info "RequestMessage missing string \"requestId\"" {:gremlin/code :gremlin/malformed-request})))
  (when (not= "bytecode" op)
    (throw (ex-info (str "unsupported \"op\": " (pr-str op)
                         " -- v0.1 only supports \"op\": \"bytecode\" (no \"eval\", ADR-2607172500)")
                    {:gremlin/code :gremlin/malformed-request})))
  (when-not (map? args)
    (throw (ex-info "RequestMessage missing \"args\" object" {:gremlin/code :gremlin/malformed-request})))
  [requestId (bytecode-json->edn (get args "gremlin"))])

(defn encode-request
  "Build a GraphSON RequestMessage JSON string for `bytecode` (this repo's
  own EDN bytecode shape, see `kotobase.gremlin.traversal` ns docstring).

  The one-arity form generates a request id from the clock, which is a
  test/demo convenience — real clients supply their own unique id, and a
  caller that needs a reproducible envelope must use the two-arity form."
  ([bytecode]
   (encode-request bytecode (str "req-" #?(:clj (System/currentTimeMillis)
                                           :cljs (.now js/Date)))))
  ([bytecode request-id]
   (json/encode {"requestId" request-id
                 "op" "bytecode"
                 "processor" "traversal"
                 "args" {"gremlin" (mapv (fn [[step & args]] (into [(name step)] args)) bytecode)}})))

(defn- status-code->message [code]
  (case code 200 "" ""))

(defn encode-response
  "Build a GraphSON ResponseMessage JSON string. `result` -> `{:data [...]}`
  on success (`code` 200); `error` -> `{:message \"...\"}` on failure (`code`
  597 or 598)."
  [request-id code {:keys [data message]}]
  (json/encode {"requestId" request-id
                "status" {"code" code "message" (or message (status-code->message code)) "attributes" {}}
                "result" {"data" (if (= code 200) data nil) "meta" {}}}))

(defn decode-response
  "Parse a ResponseMessage JSON string (test/client convenience) ->
  `{:request-id :code :message :data}`."
  [s]
  (let [{:strs [requestId status result]} (json/parse s)]
    {:request-id requestId
     :code (get status "code")
     :message (get status "message")
     :data (get result "data")}))

(defn handle-request-text
  "One incoming WebSocket text-frame payload (a GraphSON RequestMessage
  JSON string) -> a GraphSON ResponseMessage JSON string. Pure w.r.t. `ctx`
  (`{:store :vertex-colls :visible?}`, passed straight to
  `kotobase.gremlin.traversal/execute`) — no socket concepts in this fn, which
  is why it is the half a Worker can host.

  Never throws: a malformed request, an unsupported `op`, or a traversal
  error all come back as a ResponseMessage with a Gremlin status code, because
  a transport that closes the socket on a bad query tells the client nothing
  it can act on."
  [ctx text]
  (let [parsed (try (json/parse text)
                    (catch #?(:clj Exception :cljs :default) _ ::parse-error))]
    (if (= parsed ::parse-error)
      (encode-response "" 598 {:message "malformed JSON request body"})
      (let [request-id (get parsed "requestId" "")]
        (try
          (let [[request-id bytecode] (request-message->bytecode parsed)
                data (traversal/execute ctx bytecode)]
            (encode-response request-id 200 {:data data}))
          (catch #?(:clj Exception :cljs :default) e
            (let [ed (ex-data e)
                  code (if (= :gremlin/malformed-request (:gremlin/code ed)) 598 597)
                  msg (or (:gremlin/message ed) (ex-message e) (str e))]
              (encode-response request-id code {:message msg}))))))))
