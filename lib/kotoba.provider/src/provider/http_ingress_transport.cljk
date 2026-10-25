(ns provider.http-ingress-transport
  "Production **ingress** transport for the bounded HTTP ingress capability
  kit (`provider.http-ingress`, W5 family-3), backed by a real `node:http`
  server on `:cljs`.

  This is the ingress-side sibling of `provider.http-transport` (ADR 0066 /
  ADR 0117), which is the *egress* transport for `provider.http`. Read that
  namespace first: the shape of the problem and the house limits are the
  same, only the direction is reversed.

      provider.http.cljc            bounded egress capability   (guest calls out)
      provider.http-transport.cljc  java.net.http / node child  (ADR 0066/0117)

      provider.http-ingress.cljc            bounded ingress capability  (guest is called)
      provider.http-ingress-transport.cljc  node:http server            <- THIS FILE

  ## What was missing

  `http_ingress.cljc` already defines the whole guest-facing contract --
  host-owned queue, accept-then-reply pairing, bounded typed request and
  response, canonical i64 status. What it never had was anything that binds
  it to a socket: `enqueue!` was only ever called by test harnesses. The
  capability was therefore unreachable in production, and hosts that needed
  to serve HTTP kept reaching for an ambient socket instead. This namespace
  is the missing binding, and nothing else.

  ## It does not redesign, fork, or weaken the capability

  This namespace defines **no new capability, no new queue, no new pairing
  rule and no new types**, and it does not modify `http_ingress.cljc`. It
  calls `ingress/create-provider`, uses that kit's own `enqueue!`, and hands
  the guest that kit's own `:invoke` functions -- each *wrapped* by a
  function that delegates first and only then observes the outcome:

  - the accept wrapper calls the real accept, and when (and only when) the
    real accept returns the option's `some` arm, moves the head of this
    namespace's parallel socket FIFO into the in-flight slot;
  - the reply wrapper calls the real reply -- so every bound in
    `http_ingress.cljc` (status range, header count/uniqueness/size, body
    size, `reply requires a prior accept`) runs first and throws first --
    and writes to the socket only if the real reply returned `true`.

  ## Correlation, and how it is kept honest

  Position in the FIFO is what says which socket a reply belongs to, so the
  FIFO has to mean exactly the same thing as the kit's queue. Two things make
  that true, and a third catches it when it is not:

  1. Everything that enqueues through this listener -- a socket request, or a
     host calling the listener's own `:enqueue!` -- appends to the FIFO. A
     socketless host injection appends the marker `:detached`, so it still
     occupies its position; its reply is counted (`:detached-replies`) and
     dropped rather than written anywhere.
  2. Accept pops the FIFO head only when the kit's accept returned the `some`
     arm, so the two move together.
  3. Before every accept, the FIFO's length is compared against the kit's own
     `:queued`. A host that reaches past this listener for the kit's raw
     `enqueue!` desynchronizes them, and from that moment position no longer
     identifies a socket. The transport does not guess: it counts
     `:desync-events`, answers every socket still in its FIFO with 503, drops
     the FIFO, and treats replies it cannot correlate as `:desynced-replies`.
     Once the kit's queue drains, the two agree again and routing resumes.

  Point 3 exists because an earlier version of this namespace only marked
  `:detached` when its FIFO happened to be *empty*, which is not the same
  question. The socket test caught it doing exactly what this section
  promises it will not: with a host injection sitting between two socket
  requests, the second client received the host's reply body and status.

  ## The guest never receives a socket

  Nothing that crosses to the guest is or contains a `net.Socket`, an
  `http.IncomingMessage`, an `http.ServerResponse`, a stream, a promise or a
  host exception. The guest sees exactly the two bounded typed values
  `http_ingress.cljc` defines: `[:option incoming-request]` out of accept,
  and a `:bool` out of reply. Socket handles live only in this namespace's
  own state atom, keyed by position in the FIFO.

  ## Bounds are enforced at the host, before the queue

  A request that violates a bound is answered by the *host* with a proper
  HTTP status and never enters the queue, so an over-limit request cannot
  consume queue depth or reach the guest at all:

      request target over `:max-path-bytes` (4096)        -> 414
      more than `:max-headers` (32) headers               -> 431
      header name over 512 B / value over 65536 B         -> 431
      header name outside the RFC 9110 token charset      -> 431
      declared or streamed body over `:max-body-bytes`    -> 413
      queue already at `:max-queue-depth` (8)             -> 503
      any other host-side rejection from `enqueue!`       -> 400
      guest did not reply within `:reply-timeout-ms`      -> 504
      listener stopped with the request outstanding       -> 503

  The value bounds are `http_ingress.cljc`'s own constants
  (`max-path-bytes`, `max-headers`, `max-body-bytes`, and
  `kotoba.kir.value`'s keyword/string byte limits, which are what its
  `validate-headers!` checks against), not a second set invented here; the
  restricted response-header set mirrors
  `http-transport/restricted-header-names` for the same reason it exists
  there -- framing belongs to the host, not to the peer that supplied the
  headers.

  ## Backpressure is explicit, never silent

  When the host-owned queue is already at `:max-queue-depth`, the request is
  **not** enqueued, **not** dropped silently, and **not** buffered somewhere
  else: the host answers `503 Service Unavailable` with `Retry-After: 0` and
  ends the response. That is the only backpressure signal, and it is visible
  both to the HTTP client (as a status) and to the operator (as the
  `:queue-full` counter in `snapshot`). `:max-queue-depth` is passed
  straight through to `ingress/create-provider`, so the depth the client is
  bounded by and the depth the guest sees are the same number.

  A request that is enqueued but never accepted, or accepted but never
  replied to, would otherwise hold its socket forever. `:reply-timeout-ms`
  (default 30000, matching `http/max-timeout-ms` on the egress side) bounds
  that: the host answers 504 and marks the entry answered. The entry is
  deliberately left in the queue as a tombstone -- removing it would mean
  reaching into the kit's queue, which is exactly the fork this namespace
  refuses -- so the guest can still accept and reply to it later; that late
  reply is counted (`:dropped-replies`) and discarded instead of being
  written onto a socket that already carries a 504.

  ## Status is canonical i64

  `http.cljc`'s docstring explains why: on `:cljs` a plain number fails
  `typed-cap-call` result validation and makes range checks unreliable when
  mixed with bigint, so the canonical representation of an `:i64` field is a
  JS `bigint`. The status the guest supplies to `:http/reply` is therefore a
  bigint; `http_ingress.cljc` has already range-checked it into [100, 599]
  by the time this namespace sees it, and `js/Number` on a bigint in that
  range is exact.

  ## `:cljs` only

  The socket half of this file is `#?(:cljs ...)` on purpose. There is no
  JVM listener here and no third-party dependency anywhere: this repository
  has none, deliberately. The classification and canonicalization helpers
  above the socket section are portable `.cljc` so they can be reasoned
  about, and tested, without binding a port."
  (:require [kotoba.lang.text :as string]
            [provider.http-ingress :as ingress]
            [kotoba.kir.value :as value]
            #?@(:cljs [[kotoba.kir.cljs-i64 :as i64]])))

;; ---------------------------------------------------------------------------
;; limits -- every one of these is `http_ingress.cljc`'s own constant, or
;; `kotoba.kir.value`'s, re-exported under a `default-` name so a host can
;; lower them per listener (never raise them past the capability's bound).
;; ---------------------------------------------------------------------------

(def default-host "127.0.0.1")
(def default-port 0)

(def default-max-body-bytes
  "Bodies over this are answered 413 by the host and never enqueued. Same
  number `http_ingress.cljc` would throw on (`max-body-bytes`, 65536), and
  the same number `http-transport`'s `hop-script` truncates a response body
  at -- enforced here *before* the queue so the guest's own bound is never
  the thing that has to throw."
  ingress/max-body-bytes)

(def default-max-headers
  "Header count ceiling (`ingress/max-headers`, 32). Same as
  `http/max-headers` on the egress side."
  ingress/max-headers)

(def max-header-name-bytes
  "`validate-headers!` puts every header name through
  `value/bounded-keyword!` at this limit; checking it here means an
  over-long name is a 431 rather than a thrown ex-info inside `enqueue!`."
  value/keyword-value-byte-limit)

(def max-header-value-bytes
  "As above, for `value/bounded-string!` on the header value.

  Measured 2026-08-18: at node's DEFAULT `maxHeaderSize` of 16 KiB, this
  65536-byte bound is unreachable over a socket -- node's own parser refuses
  the request (and resets the connection) long before `classify-request` is
  called, so the 431 a client sees for an enormous header value comes from
  node, not from here. The check is kept because it is the capability's own
  bound (`validate-headers!` puts every header value through
  `value/bounded-string!` at exactly this limit) and because a host that
  raises `:max-header-size` past 64 KiB makes it the operative one. Do not
  read it as 'this namespace is what refuses a 70 KB header on a default
  listener' -- it is not."
  value/string-value-byte-limit)

(def default-max-path-bytes
  "Request-target ceiling (`ingress/max-path-bytes`, 4096). Same number
  `http/max-url-bytes` uses for an outbound URL."
  ingress/max-path-bytes)

(def default-reply-timeout-ms
  "How long a socket waits for the guest to accept *and* reply before the
  host answers 504 on its behalf. 30000 matches `http/max-timeout-ms`, the
  egress side's ceiling for one bounded call."
  30000)

(def restricted-response-header-names
  "Response headers the host owns and the guest may not set.
  `content-length` is computed here from the actual reply body;
  `connection`, `transfer-encoding`, `keep-alive` and `upgrade` are
  connection framing. Same rationale as
  `http-transport/restricted-header-names`: a header the transport must
  control is dropped quietly rather than allowed to fail the whole call from
  deep inside the runtime."
  #{"connection" "content-length" "transfer-encoding" "keep-alive" "upgrade"})

;; ---------------------------------------------------------------------------
;; portable classification -- no sockets, no I/O, no host types
;; ---------------------------------------------------------------------------

(def header-token-pattern
  "RFC 9110 `token`: the only characters admitted in a header field name.
  Node's own parser already rejects malformed names, so this is defensive
  depth -- but it also guarantees the name survives the round trip through
  `keyword`, which is how `http_ingress.cljc` types it."
  #"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")

(defn header-name-ok?
  [n]
  (and (string? n) (boolean (re-matches header-token-pattern n))))

(defn header-value-safe?
  "A header value carrying CR, LF or NUL is a request/response splitting
  vector. Rejected outright rather than sanitized: silently rewriting a
  peer's bytes is how splitting bugs hide."
  [v]
  (and (string? v) (not (boolean (re-find #"[\r\n\x00]" v)))))

(defn method-keyword
  "`\"GET\"` -> `:http/get`. Namespaced so the guest's `case`/`=` on the
  method reads as HTTP's method and cannot collide with an unrelated bare
  keyword. Well under `value/keyword-value-byte-limit` for every method."
  [method]
  (keyword "http" (string/lower (str method))))

(defn- reject [status reason message]
  {:tag :reject :status status :reason reason :message message})

(defn classify-request
  "Decide, from the *bounded* facts of an inbound request, whether it may be
  enqueued. Pure: `headers` is a seq of `[name value]` string pairs, `path`
  is the raw request target, `body-bytes` is the declared or observed body
  size (or nil when not yet known). Returns
  `{:tag :accept :method :path :headers}` -- headers as a keyword->string
  map, the shape `ingress/enqueue!` accepts -- or
  `{:tag :reject :status ... :reason ... :message ...}`."
  [{:keys [method path headers body-bytes]}
   {:keys [max-path-bytes max-headers max-body-bytes]
    :or {max-path-bytes default-max-path-bytes
         max-headers default-max-headers
         max-body-bytes default-max-body-bytes}}]
  (cond
    (or (not (string? path)) (zero? (count path)))
    (reject 400 :empty-path "request target is empty")

    (> (value/utf8-byte-count! path) max-path-bytes)
    (reject 414 :path-too-long
            (str "request target exceeds " max-path-bytes " bytes"))

    (> (count headers) max-headers)
    (reject 431 :too-many-headers
            (str "more than " max-headers " request headers"))

    (and (number? body-bytes) (> body-bytes max-body-bytes))
    (reject 413 :body-too-large
            (str "request body exceeds " max-body-bytes " bytes"))

    :else
    (or (some (fn [[n v]]
                (cond
                  (not (header-name-ok? n))
                  (reject 431 :bad-header-name
                          "header name is not an RFC 9110 token")
                  (> (value/utf8-byte-count! n) max-header-name-bytes)
                  (reject 431 :header-name-too-long
                          (str "header name exceeds " max-header-name-bytes " bytes"))
                  (not (header-value-safe? v))
                  (reject 431 :bad-header-value
                          "header value contains CR, LF or NUL")
                  (> (value/utf8-byte-count! v) max-header-value-bytes)
                  (reject 431 :header-value-too-long
                          (str "header value exceeds " max-header-value-bytes " bytes"))
                  :else nil))
              headers)
        {:tag :accept
         :method (method-keyword method)
         :path path
         :headers (reduce (fn [m [n v]] (assoc m (keyword n) v)) {} headers)})))

(defn reply-headers
  "Fold the guest's typed header set (`[[header-type name value] ...]`,
  already validated by `http_ingress.cljc`'s `validate-headers!`) into an
  ordinary name->value map for the socket, dropping host-owned framing
  headers and anything that would not survive as a header field. Never
  throws: a header this cannot represent is dropped, the response is not."
  [headers]
  (reduce (fn [m [_ n v]]
            (let [field (name n)
                  lower (string/lower field)]
              (if (and (header-name-ok? field)
                       (header-value-safe? v)
                       (not (contains? restricted-response-header-names lower)))
                (assoc m lower v)
                m)))
          {}
          headers))

(defn status->number
  "Canonical i64 status -> a plain number for the socket. On `:cljs` the
  value is a JS bigint (see `http.cljc`'s docstring on why an `:i64` field
  is never a plain cljs number); `http_ingress.cljc` has already checked it
  is in [100, 599], where `js/Number` is exact."
  [status]
  #?(:clj status
     :cljs (js/Number (i64/->bigint status))))

;; ---------------------------------------------------------------------------
;; socket half -- `:cljs` only
;; ---------------------------------------------------------------------------

#?(:cljs
   (def ^:private zero-counters
     {:received 0
      :enqueued 0
      :rejected 0
      :queue-full 0
      :replied 0
      :timed-out 0
      :stopped-open 0
      :dropped-replies 0
      :detached-replies 0
      :desynced-replies 0
      :desync-events 0}))

#?(:cljs
   (defn- bump! [state k]
     (swap! state update-in [:counters k] inc)))

#?(:cljs
   (defn- write-response!
     "Write one response onto one `http.ServerResponse`, exactly once. The
     `:done` atom is the single-answer latch: whichever of the guest reply,
     the reply timeout, or listener shutdown gets there first wins, and the
     losers are counted rather than throwing or writing twice."
     [entry status headers body]
     (when (compare-and-set! (:done entry) false true)
       (try
         (let [res (:res entry)
               buf (.from js/Buffer (str body) "utf8")
               hdrs (clj->js (assoc headers "content-length"
                                    (str (.-length buf))))]
           (.writeHead res status hdrs)
           (.end res buf)
           true)
         (catch :default _
           ;; The socket died under us (client hung up mid-write). There is
           ;; nothing to report to the guest -- it holds no socket -- and
           ;; nothing to retry.
           (try (.destroy (:res entry)) (catch :default _ nil))
           false)))))

#?(:cljs
   (defn- host-reject!
     "Answer a bounded rejection from the host itself. Body is plain text and
     deliberately terse: it names the bound, never the guest's state."
     [state entry status reason message]
     (bump! state :rejected)
     (write-response! entry status
                      {"content-type" "text/plain; charset=utf-8"
                       "connection" "close"
                       "x-kotoba-ingress-reject" (name reason)}
                      (str message "\n"))))

#?(:cljs
   (defn- arm-timeout!
     [state entry timeout-ms]
     (when (and (number? timeout-ms) (pos? timeout-ms))
       (let [t (js/setTimeout
                (fn []
                  (when-not @(:done entry)
                    (bump! state :timed-out)
                    (write-response!
                     entry 504
                     {"content-type" "text/plain; charset=utf-8"
                      "x-kotoba-ingress-reject" "reply-timeout"}
                     "guest did not reply within the ingress reply timeout\n")))
                timeout-ms)]
         ;; A pending reply timer must not be the reason node stays alive:
         ;; the listening server already holds the loop open, and once it is
         ;; closed a straggling timer should not keep the process running.
         (when (fn? (.-unref t)) (.unref t))
         (swap! state assoc-in [:timers (:id entry)] t)))))

#?(:cljs
   (defn- clear-timeout! [state entry]
     (when-let [t (get-in @state [:timers (:id entry)])]
       (js/clearTimeout t)
       (swap! state update :timers dissoc (:id entry)))))

;; --- provider wrappers -----------------------------------------------------

#?(:cljs
   (defn- desync!
     "Correlation is lost: the FIFO's length no longer matches the kit's
     queue, so position no longer identifies a socket. Fail closed -- answer
     every socket still held here with 503 and drop the FIFO -- rather than
     hand one client's response to another. Self-healing: once the kit's
     queue drains, an empty FIFO and an empty queue agree again."
     [state]
     (bump! state :desync-events)
     (doseq [entry (:queue @state)]
       (when (and (map? entry) (not @(:done entry)))
         (bump! state :stopped-open)
         (write-response!
          entry 503
          {"content-type" "text/plain; charset=utf-8"
           "connection" "close"
           "x-kotoba-ingress-reject" "correlation-lost"}
          "ingress lost track of which reply belongs to this request\n")))
     (swap! state assoc :queue [])))

#?(:cljs
   (defn- wrap-accept
     "Delegate to the kit's real accept, then -- only on the `some` arm --
     move this namespace's FIFO head into the in-flight slot. The returned
     value is the kit's, byte for byte; nothing is added to it and nothing
     socket-shaped can reach the guest through it."
     [state kit accept-provider]
     (assoc accept-provider :invoke
            (fn [request]
              ;; Sampled BEFORE delegating, because accept pops the kit's
              ;; queue: after the call the two counts differ by one by
              ;; construction and the comparison would say nothing.
              (let [queued-before (:queued ((:snapshot kit)))
                    shadow (:queue @state)
                    correlated? (= (count shadow) queued-before)
                    result ((:invoke accept-provider) request)]
                (when (true? (second result))
                  (if correlated?
                    (let [head (first shadow)]
                      (swap! state assoc
                             :queue (vec (rest shadow))
                             :inflight (if (map? head) head :detached)))
                    (do (desync! state)
                        (swap! state assoc :inflight :desynced))))
                result)))))

#?(:cljs
   (defn- wrap-reply
     "Delegate to the kit's real reply -- which is where every bound and the
     accept-then-reply pairing rule are enforced, and which throws before
     this wrapper observes anything -- then write the guest's response onto
     the socket that produced the in-flight request."
     [state reply-provider]
     (assoc reply-provider :invoke
            (fn [[_ status [_ headers] body :as request]]
              (let [ok ((:invoke reply-provider) request)]
                (when (true? ok)
                  (let [entry (:inflight @state)]
                    (swap! state assoc :inflight nil)
                    (cond
                      (= :desynced entry)
                      (bump! state :desynced-replies)

                      (or (nil? entry) (= :detached entry))
                      (bump! state :detached-replies)

                      @(:done entry)
                      ;; Already answered by the reply timeout or by
                      ;; shutdown. The guest's reply is late, not wrong.
                      (bump! state :dropped-replies)

                      :else
                      (do (clear-timeout! state entry)
                          (bump! state :replied)
                          (write-response! entry
                                           (status->number status)
                                           (reply-headers headers)
                                           body)))))
                ok)))))

;; --- inbound request handling ---------------------------------------------

#?(:cljs
   (defn- node-headers
     "Node hands `req.headers` back as a lowercase-keyed object whose values
     are strings, or arrays for repeated fields. Take the first occurrence,
     the same rule `http-transport`'s `hop-script` uses when folding a
     response's headers."
     [req]
     (->> (js/Object.entries (.-headers req))
          (map (fn [pair]
                 (let [k (aget pair 0)
                       v (aget pair 1)]
                   [(str k) (str (if (array? v) (aget v 0) v))])))
          (vec))))

#?(:cljs
   (defn- handle-request!
     [state kit opts req res]
     (let [id (:next-id (swap! state update :next-id inc))
           entry {:id id :res res :done (atom false)}
           limits (select-keys opts [:max-path-bytes :max-headers :max-body-bytes])
           max-body (get opts :max-body-bytes default-max-body-bytes)
           headers (node-headers req)
           declared (let [cl (get (into {} headers) "content-length")]
                      (when cl (js/Number cl)))]
       (bump! state :received)
       (if (:stopped? @state)
         (do (.resume req)
             (host-reject! state entry 503 :stopped "listener is stopping"))
         (let [verdict (try
                         (classify-request {:method (.-method req)
                                            :path (.-url req)
                                            :headers headers
                                            :body-bytes declared}
                                           limits)
                         (catch :default e
                           ;; `value/utf8-byte-count!` fails closed on
                           ;; malformed UTF-16; that is a bad request, not a
                           ;; listener crash.
                           {:tag :reject :status 400 :reason :unrepresentable
                            :message (str "request is not representable: "
                                          (.-message e))}))]
           (if (= :reject (:tag verdict))
             (do (.resume req)          ;; drain, never read an over-limit body
                 (host-reject! state entry (:status verdict)
                               (:reason verdict) (:message verdict)))
             ;; Body is read with a running byte count so an *undeclared*
             ;; (chunked) over-limit body is refused at the host too, not
             ;; only one that announced itself in content-length.
             (let [chunks (atom [])
                   total (atom 0)
                   over? (atom false)]
               (.on req "data"
                    (fn [chunk]
                      (when-not @over?
                        (swap! total + (.-length chunk))
                        (if (> @total max-body)
                          (do (reset! over? true)
                              (reset! chunks [])
                              (host-reject! state entry 413 :body-too-large
                                            (str "request body exceeds "
                                                 max-body " bytes"))
                              ;; Drain rather than `req.destroy()`: destroying
                              ;; the request destroys the socket, which
                              ;; discards the 413 we just queued on it. The
                              ;; response already carries `connection: close`,
                              ;; so node ends the connection once the client
                              ;; has finished sending.
                              (.resume req))
                          (swap! chunks conj chunk)))))
               (.on req "aborted"
                    (fn [] (reset! (:done entry) true)))
               (.on req "end"
                    (fn []
                      (when-not @over?
                        (let [body (.toString (.concat js/Buffer (into-array @chunks))
                                              "utf8")]
                          (cond
                            (:stopped? @state)
                            (host-reject! state entry 503 :stopped
                                          "listener is stopping")

                            ;; Backpressure. The queue is the host's, and it
                            ;; is full: say so with a status instead of
                            ;; dropping the request on the floor.
                            (>= (:queued ((:snapshot kit)))
                                (:max-queue-depth kit))
                            (do (bump! state :queue-full)
                                (write-response!
                                 entry 503
                                 {"content-type" "text/plain; charset=utf-8"
                                  "retry-after" "0"
                                  "x-kotoba-ingress-reject" "queue-full"}
                                 "ingress queue is full\n"))

                            :else
                            (let [enqueued?
                                  (try
                                    ((:enqueue! kit) (:method verdict)
                                                     (:path verdict)
                                                     (:headers verdict)
                                                     body)
                                    (catch :default e
                                      (host-reject! state entry 400 :rejected
                                                    (str "host refused the request: "
                                                         (.-message e)))
                                      false))]
                              (when enqueued?
                                ;; Only now does the socket join the FIFO,
                                ;; in exactly the order the kit's own queue
                                ;; received it.
                                (bump! state :enqueued)
                                (swap! state update :queue conj entry)
                                (arm-timeout! state entry
                                              (get opts :reply-timeout-ms
                                                   default-reply-timeout-ms))))))))))))))))

;; --- listener --------------------------------------------------------------

#?(:cljs
   (defn start-listener!
     "Bind a real `node:http` server and make the HTTP ingress capability
     reachable from it. Returns a promise of a listener map.

     Options (all optional):

       :host             interface to bind, default \"127.0.0.1\"
       :port             TCP port, default 0 (kernel-assigned; read `:port`
                         off the returned map -- never hardcode one)
       :max-queue-depth  passed straight to `ingress/create-provider`,
                         default `ingress/default-max-queue-depth` (8)
       :max-body-bytes   default `ingress/max-body-bytes` (65536)
       :max-headers      default `ingress/max-headers` (32)
       :max-path-bytes   default `ingress/max-path-bytes` (4096)
       :reply-timeout-ms host answers 504 after this, default 30000;
                         a non-positive value disables the timer
       :max-header-size  node's own parser bound on the TOTAL size of a
                         request's header block. Left at node's default
                         (16 KiB) when unset -- see the note on
                         `max-header-value-bytes` for why that default means
                         node, not this namespace, is what a very large
                         header actually meets first
       :kit              an existing `ingress/create-provider` result to bind
                         to, instead of creating one

     Returns (in the promise):

       :providers  the map to hand the guest: {17 accept, 18 reply}. These
                   are the kit's own providers, wrapped to observe outcomes;
                   the queue, the pairing rule and the types are the kit's.
       :kit        the underlying `ingress/create-provider` result
       :enqueue!   host-side injection with no socket behind it. It takes
                   its place in the FIFO like any other request, so a reply
                   that follows it is recognised as socketless -- counted as
                   `:detached-replies` and discarded -- instead of being
                   written to the next client's socket. Use THIS, not
                   `(:enqueue! (:kit listener))`; see 'Correlation' above.
       :port       the port actually bound
       :host       the interface actually bound
       :server     the `node:http` server, for hosts that must attach their
                   own listeners. Never handed to the guest.
       :snapshot   fn -> the kit's snapshot merged with transport counters
       :stop!      fn -> promise; answers every outstanding request 503,
                   then closes the server"
     ([] (start-listener! {}))
     ([opts]
      (let [http (js/require "node:http")
            kit (or (:kit opts)
                    (ingress/create-provider
                     (select-keys opts [:max-queue-depth])))
            state (atom {:queue []
                         :inflight nil
                         :timers {}
                         :next-id 0
                         :stopped? false
                         :sockets #{}
                         :counters zero-counters})
            server (.createServer
                    http
                    (if-let [mhs (:max-header-size opts)]
                      #js {:maxHeaderSize mhs}
                      #js {})
                    (fn [req res]
                      (handle-request! state kit opts req res)))
            host (get opts :host default-host)
            port (get opts :port default-port)]
        (.on server "connection"
             (fn [socket]
               (swap! state update :sockets conj socket)
               (.on socket "close"
                    (fn [] (swap! state update :sockets disj socket)))))
        (js/Promise.
         (fn [resolve reject]
           (.once server "error" reject)
           (.listen server port host
                    (fn []
                      (let [addr (.address server)
                            bound (.-port addr)
                            outstanding
                            (fn []
                              (let [{:keys [queue inflight]} @state]
                                (remove #(or (nil? %) (= :detached %))
                                        (conj (vec queue) inflight))))
                            stop!
                            (fn []
                              (swap! state assoc :stopped? true)
                              (doseq [[_ t] (:timers @state)] (js/clearTimeout t))
                              (swap! state assoc :timers {})
                              (doseq [entry (outstanding)]
                                (when-not @(:done entry)
                                  (bump! state :stopped-open)
                                  (write-response!
                                   entry 503
                                   {"content-type" "text/plain; charset=utf-8"
                                    "connection" "close"
                                    "x-kotoba-ingress-reject" "listener-stopped"}
                                   "ingress listener stopped\n")))
                              (js/Promise.
                               (fn [done _]
                                 (.close server (fn [] (done true)))
                                 ;; keep-alive sockets would otherwise hold
                                 ;; `close` open for keepAliveTimeout; the
                                 ;; responses above are already flushed by
                                 ;; the time this fires.
                                 (let [sweep (js/setTimeout
                                              (fn []
                                                (doseq [s (:sockets @state)]
                                                  (try (.destroy s)
                                                       (catch :default _ nil))))
                                              25)]
                                   (when (fn? (.-unref sweep)) (.unref sweep))))))]
                        (resolve
                         {:providers
                          {ingress/accept-capability-id
                           (wrap-accept state kit
                                        (get (:providers kit)
                                             ingress/accept-capability-id))
                           ingress/reply-capability-id
                           (wrap-reply state (get (:providers kit)
                                                  ingress/reply-capability-id))}
                          :kit kit
                          ;; NOT the kit's raw `enqueue!`: a host injection
                          ;; still has to take its place in the FIFO, or the
                          ;; reply that follows it would be handed to
                          ;; whichever socket happened to be next.
                          :enqueue!
                          (fn [method path headers body]
                            (let [ok ((:enqueue! kit) method path headers body)]
                              (when ok
                                (swap! state update :queue conj :detached))
                              ok))
                          :port bound
                          :host host
                          :server server
                          :snapshot (fn []
                                      (merge ((:snapshot kit))
                                             {:transport (:counters @state)
                                              :sockets-queued (count (:queue @state))
                                              :inflight? (some? (:inflight @state))
                                              :stopped? (:stopped? @state)}))
                          :stop! stop!}))))))))))
