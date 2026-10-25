(ns vllm.core
  "Top-level vllm-clj operations: turn a `:vllm/*` request into a normalized
  result by sending it through a host-injected `vllm.ports/ITransport`. Pure
  orchestration — the only effect is the transport call the host supplies.

  The kernel builds the request spec (url, headers, string-keyed body), hands it
  to the transport, and normalizes the response. JSON (de)serialization and the
  socket both live in the host transport."
  (:require [vllm.request :as req]
            [vllm.wire :as wire]
            [vllm.validate :as validate]
            [vllm.ports :as ports]))

(def ^:private json-headers
  {"content-type" "application/json" "accept" "application/json"})

(defn request-spec
  "Build the transport request spec for `req` (url, :post, headers, body).
  `body` is a string-keyed map; the host transport serializes it. Pure."
  [request]
  {:url     (req/target-url request)
   :method  :post
   :headers json-headers
   :body    (wire/render request)})

(defn complete
  "Send `request` through `transport` and return a normalized result
  (see `vllm.wire/parse-response`). Validates first: on an :error-level problem
  it returns `{:vllm/error :validation :vllm/problems [...]}` without sending.
  On a non-2xx response it returns `{:vllm/error :http :vllm/status … :vllm/body …}`."
  [transport request]
  (let [probs (validate/problems request)]
    (if (some #(= :error (:vllm/severity %)) probs)
      {:vllm/error :validation :vllm/problems probs}
      (let [{:keys [status body error]} (ports/request! transport (request-spec request))]
        (cond
          error                       {:vllm/error :transport :vllm/cause error}
          (and status (<= 200 status 299)) (wire/parse-response body)
          :else                       {:vllm/error :http :vllm/status status
                                       :vllm/body body})))))

(defn chat
  "Convenience: build + send a chat request in one call.
  `(chat transport model messages)` or with an `opts` map."
  ([transport model messages] (chat transport model messages {}))
  ([transport model messages opts]
   (complete transport (req/chat model messages opts))))

(defn completion
  "Convenience: build + send a text-completion request in one call."
  ([transport model prompt] (completion transport model prompt {}))
  ([transport model prompt opts]
   (complete transport (req/completion model prompt opts))))

(defn stream
  "Stream `request` through an `IStreamTransport`, invoking `(on-delta text)`
  for each non-empty token delta. Requires `transport` to satisfy
  `IStreamTransport`; otherwise throws. Returns nil when the stream closes."
  [transport request on-delta]
  (when-not (satisfies? ports/IStreamTransport transport)
    (throw (ex-info "transport does not support streaming (IStreamTransport)"
                    {:vllm/request request})))
  (let [request (req/with-stream request true)]
    (ports/stream! transport (request-spec request)
                   (fn [chunk]
                     (let [{:vllm/keys [delta]} (wire/parse-chunk chunk)]
                       (when (seq delta) (on-delta delta)))))))
