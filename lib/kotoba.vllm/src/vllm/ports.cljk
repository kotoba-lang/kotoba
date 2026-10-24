(ns vllm.ports
  "Host-injected transport for vllm-clj. The kernel speaks only EDN and
  string-keyed maps; the actual HTTP (and JSON (de)serialization) is the host's
  job — it injects an `ITransport` built on whatever client it likes (clj-http,
  http-kit, hato, js/fetch, …). This keeps vllm-clj a zero-dep `.cljc` core.

  - `ITransport`       — one request/response round-trip.
  - `IStreamTransport` — *optional* SSE streaming (token deltas).

  A request spec is a plain map:
    {:url \"…/v1/chat/completions\" :method :post
     :headers {\"content-type\" \"application/json\"}
     :body <string-keyed map>}            ; host serializes to JSON

  A response is a plain map:
    {:status 200 :body <parsed JSON map>} ; host parses from JSON
  ")

(defprotocol ITransport
  "A single HTTP round-trip. `body` is a string-keyed map (host serializes);
  the returned `:body` is the parsed JSON map (host deserializes)."
  (request! [this req-spec]
    "Perform the request, returning `{:status int :body map}` (or `{:error …}`)."))

(defprotocol IStreamTransport
  "Optional server-sent-events streaming."
  (stream! [this req-spec on-chunk]
    "Open an SSE stream, calling `(on-chunk parsed-chunk-map)` per event;
    returns when the stream closes."))

(def no-transport
  "A transport that refuses to send — the default. vllm-clj does no network I/O
  on its own; a host must inject a real `ITransport`."
  (reify ITransport
    (request! [_ req-spec]
      (throw (ex-info "no ITransport bound — inject a host HTTP client"
                      {:vllm/req-spec req-spec})))))

(defn fn-transport
  "Build an `ITransport` from a plain `(fn [req-spec] -> response-map)`. Handy
  for tests and thin host adapters."
  [f]
  (reify ITransport
    (request! [_ req-spec] (f req-spec))))
