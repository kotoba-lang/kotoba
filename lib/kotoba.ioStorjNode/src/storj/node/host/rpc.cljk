(ns storj.node.host.rpc
  "A DRPC call on a verified Storj connection.

  The last joint. `storj.node.host.tls` produces a socket whose peer has been
  admitted by `storj.node.identity`; `drpc.client` says which packets a unary
  call is made of; this writes the one onto the other and reads the answer
  back.

  ## Why this is here and not in drpc

  `kotoba-lang/drpc` deliberately has no socket layer — it is bytes in, bytes
  out, so the same description drives a JVM stream, a Node socket, or a test
  that opens neither. Putting a reader loop there would give it a host layer
  and a reason to care about timeouts, which is the opposite of what makes it
  portable. What is here is the *joining*: a Storj TLS socket on one side and
  DRPC on the other, and both of those are already this repo's business.

  ## What it does not do

   answers calls on a socket the other way round, and it is
  the same shape: read, hand the decision somewhere else, write what comes
  back. Neither closes the socket.

  `serve-connection` answers calls on a socket the other way round, and it is
  the same shape: read, hand the decision somewhere else, write what comes
  back. Neither closes the socket.

  One call at a time, on a stream the caller names. DRPC multiplexes and this
  does not: a real node runs several calls over one connection and needs a
  reader that dispatches packets to whichever call is waiting. That is a
  scheduler, and writing one before there is a second caller would be
  guessing at what it needs."
  (:require [drpc.client :as c]
            [storj.node.protocols :as p]
            [drpc.server :as srv]
            [drpc.wire :as w]
            [storj.node.bytes :as b]
            #?(:cljs ["node:tls"]))
  #?(:clj (:import (java.net SocketTimeoutException))))

(def default-timeout-ms 20000)

(defn- fail [msg data]
  (throw (ex-info (str "storj.node.host.rpc: " msg) data)))

(defn call
  "Perform one unary DRPC call on `socket` and return the result.

      {:message bytes | nil
       :error   {:code n :message s} | nil
       :closed? bool
       :ignored [packets on other streams]}

  `opts`: `:rpc` (required), `:request` (encoded request bytes), `:stream`,
  `:metadata`, `:timeout-ms`.

  On cljs this returns a promise; on the JVM it blocks. Neither closes the
  socket — a connection outlives a call, and closing one here would make the
  common case (several calls to the same satellite) impossible to write."
  [socket {:keys [rpc request stream timeout-ms]
           :or   {stream c/first-stream timeout-ms default-timeout-ms}
           :as   opts}]
  (let [stream  stream
        payload (c/request (assoc opts :stream stream :rpc rpc
                                  :request (vec request)))]
    #?(:clj
       (let [out (.getOutputStream socket)
             in  (.getInputStream socket)]
         (.setSoTimeout socket (int timeout-ms))
         (.write out (b/->native payload))
         (.flush out)
         (loop [state (w/reader), seen []]
           (let [buf (byte-array 8192)
                 n   (try (.read in buf)
                          (catch SocketTimeoutException _
                            (fail "timed out waiting for a response"
                                  {:rpc rpc :timeout-ms timeout-ms})))]
             (if (neg? n)
               ;; the peer hung up: whatever arrived is the whole answer, and
               ;; `collect` will report it as closed with no message
               (c/collect seen stream)
               (let [fed  (w/feed state (take n (seq buf)))
                     seen (into seen (:packets fed))
                     r    (c/collect seen stream)]
                 (if (c/complete? r) r (recur (:state fed) seen)))))))

       :cljs
       (js/Promise.
        (fn [resolve reject]
          (let [state (atom (w/reader))
                seen  (atom [])
                timer (js/setTimeout
                       (fn [] (reject (try (fail "timed out waiting for a response"
                                                 {:rpc rpc :timeout-ms timeout-ms})
                                           (catch :default e e))))
                       timeout-ms)
                finish (fn [r] (js/clearTimeout timer) (resolve r))
                on-data (fn on-data [chunk]
                          ;; not `{:keys [state ...]}`: that binding would
                          ;; shadow the atom of the same name and `reset!`
                          ;; would be handed the map — a mistake this repo has
                          ;; already made once, on this exact shape
                          (let [fed (w/feed @state chunk)]
                            (reset! state (:state fed))
                            (swap! seen into (:packets fed))
                            (let [r (c/collect @seen stream)]
                              (when (c/complete? r)
                                (.removeListener socket "data" on-data)
                                (finish r)))))]
            (.on socket "data" on-data)
            (.once socket "end" #(finish (c/collect @seen stream)))
            (.once socket "error" (fn [e] (js/clearTimeout timer) (reject e)))
            (.write socket (b/->native payload))))))))

(defn -put-seed
  "Put a zero-length blob at `path`.

  A convenience for harnesses that need a node to *hold* something before any
  rpc that stores one exists. Named with a leading dash as a reminder that it
  is scaffolding, not part of how a node acquires pieces."
  [store path]
  (p/-put store path []))

(defn ok?
  "Whether a call returned a response rather than an error or a hangup."
  [result]
  (boolean (and (:message result) (nil? (:error result)))))

;; ── being asked ─────────────────────────────────────────────────────────────

(defn stream-call
  "Send several messages on one stream and read everything that comes back.

      (stream-call socket {:rpc upload-rpc :messages [limit chunk done]})

  Returns the same map `call` does, plus `:messages` — every response, in
  order, which is what a download is. `call` cannot be used for this: it
  stops at `complete?`, which is satisfied by the first message, so a
  download read through it returns one chunk and reports success.

  The sending side is closed after the last message and the receiving side is
  read until the peer says it is done — `drpc.client/stream-complete?`, which
  is `CloseSend` rather than a first response."
  [socket {:keys [rpc messages stream timeout-ms]
           :or   {stream c/first-stream timeout-ms default-timeout-ms}
           :as   opts}]
  (let [packets (concat (c/open (assoc opts :stream stream :rpc rpc))
                        (map-indexed (fn [i m] (c/message stream (+ i 2) (vec m)))
                                     messages)
                        [(c/close-send stream (+ (count messages) 2))])
        payload (mapcat #(w/encode-packet % w/default-frame-size) packets)]
    #?(:clj
       (let [out (.getOutputStream socket)
             in  (.getInputStream socket)]
         (.setSoTimeout socket (int timeout-ms))
         (.write out (b/->native (vec payload)))
         (.flush out)
         (loop [state (w/reader), seen []]
           (let [buf (byte-array 8192)
                 n   (try (.read in buf)
                          (catch SocketTimeoutException _
                            (fail "timed out waiting for a stream"
                                  {:rpc rpc :timeout-ms timeout-ms})))]
             (if (neg? n)
               (c/collect seen stream)
               (let [fed  (w/feed state (take n (seq buf)))
                     seen (into seen (:packets fed))
                     r    (c/collect seen stream)]
                 (if (c/stream-complete? r) r (recur (:state fed) seen)))))))

       :cljs
       (js/Promise.
        (fn [resolve reject]
          (let [state (atom (w/reader))
                seen  (atom [])
                timer (js/setTimeout
                       (fn [] (reject (try (fail "timed out waiting for a stream"
                                                 {:rpc rpc :timeout-ms timeout-ms})
                                           (catch :default e e))))
                       timeout-ms)
                finish (fn [r] (js/clearTimeout timer) (resolve r))]
            (.on socket "data"
                 (fn [chunk]
                   ;; not `{:keys [state ...]}` — that shadows the atom
                   (let [fed (w/feed @state chunk)]
                     (reset! state (:state fed))
                     (swap! seen into (:packets fed))
                     (let [r (c/collect @seen stream)]
                       (when (c/stream-complete? r) (finish r))))))
            (.once socket "error" reject)
            (.write socket (b/->native (vec payload)))))))))

(defn serve-connection
  "Answer calls on `socket` until the peer goes away.

  `handle` is called with `{:stream :rpc :request}` and returns
  `{:response bytes}` or `{:error {:code n :message s}}` —
  `storj.node.service/handle` has that shape. Whatever it returns is written
  back; whatever it throws is not, because a handler that takes the
  connection with it turns one bad request into a disconnected node.

  ## Streams

  `on-message`, if given, is called with each `{:stream :rpc :data}` as it
  arrives and returns `{:out [...]}` where an entry is `{:message bytes}`,
  `{:end true}` or `{:error {...}}` — `storj.node.transfer/message` has that
  shape, minus the state it threads, which is this function's to carry.

  Without it, `:messages` from `drpc.server/feed` were read and dropped.
  That was invisible: a unary call also produces a message, and its `:calls`
  entry arrives right behind, so everything unary worked and only a stream
  that never closes — an upload — went unanswered. `on-message` is therefore
  optional and the default is the old behaviour, which is what the check-in
  path still wants.

  A stream that `on-message` has ended is remembered, so the `:calls` entry
  that follows its `CloseSend` is not answered a second time. Two responses
  on one stream is worse than none: the client reads the first and the
  second becomes the head of whatever it reads next.

  Blocks on the JVM and returns a promise on cljs, and neither closes the
  socket: the peer decides when it is done."
  ([socket handle] (serve-connection socket handle nil))
  ([socket handle on-message]
   (let [;; framing lives here and nowhere else — `transfer` says what to
         ;; send, this says how it goes on the wire, and message ids advance
         ;; per stream because that is the rule the other direction follows
         emit (fn [ids stream out]
                (reduce (fn [[bs ids ended] o]
                          (let [n (inc (get ids stream 0))]
                            (cond
                              (:error o)
                              [(conj bs (srv/respond-error stream
                                                           (:code (:error o))
                                                           (:message (:error o))))
                               ids true]

                              (:end o)
                              [(conj bs (srv/end-response stream n))
                               (assoc ids stream n) true]

                              :else
                              [(conj bs (srv/send-message stream n (:message o)))
                               (assoc ids stream n) ended])))
                        [[] ids false]
                        out))]
     #?(:clj
        (let [in  (.getInputStream socket)
              out (.getOutputStream socket)
              write! (fn [bs] (.write out (b/->native bs)) (.flush out))]
          (loop [state (srv/incoming), answered 0, ids {}, done #{}]
            (let [buf (byte-array 8192)
                  n   (.read in buf)]
              (if (neg? n)
                answered
                (let [fed (srv/feed state (take n (seq buf)))
                      [ids done]
                      (if on-message
                        (reduce (fn [[ids done] m]
                                  (if (done (:stream m))
                                    [ids done]
                                    (let [{:keys [out]} (on-message m)
                                          [bs ids' ended] (emit ids (:stream m) out)]
                                      (doseq [b bs] (write! b))
                                      [ids' (cond-> done ended (conj (:stream m)))])))
                                [ids done]
                                (:messages fed))
                        [ids done])
                      unanswered (remove #(done (:stream %)) (:calls fed))]
                  (doseq [call unanswered]
                    (let [{:keys [response error]} (handle call)]
                      (write! (if error
                                (srv/respond-error (:stream call)
                                                   (:code error)
                                                   (:message error))
                                (srv/respond (:stream call) response)))))
                  (recur (:state fed)
                         (+ answered (count unanswered))
                         ids
                         ;; a stream that has been answered either way is
                         ;; finished; keeping it would grow without bound on a
                         ;; long-lived connection
                         (reduce disj done (map :stream (:calls fed)))))))))

        :cljs
        (js/Promise.
         (fn [resolve reject]
           (let [state (atom (srv/incoming))
                 answered (atom 0)
                 ids (atom {})
                 done (atom #{})]
             (.on socket "data"
                  (fn [chunk]
                    ;; not `{:keys [state ...]}` — that binding shadows the atom
                    (let [fed (srv/feed @state chunk)]
                      (reset! state (:state fed))
                      (when on-message
                        (doseq [m (:messages fed)
                                :when (not (@done (:stream m)))]
                          (let [{:keys [out]} (on-message m)
                                [bs ids' ended] (emit @ids (:stream m) out)]
                            (doseq [b bs] (.write socket (b/->native b)))
                            (reset! ids ids')
                            (when ended (swap! done conj (:stream m))))))
                      (doseq [call (:calls fed)
                              :when (not (@done (:stream call)))]
                        (let [{:keys [response error]} (handle call)]
                          (.write socket (b/->native (if error
                                                       (srv/respond-error (:stream call)
                                                                          (:code error)
                                                                          (:message error))
                                                       (srv/respond (:stream call) response))))
                          (swap! answered inc)))
                      (swap! done #(reduce disj % (map :stream (:calls fed)))))))
             (.once socket "end" #(resolve @answered))
             (.once socket "error" reject))))))))
