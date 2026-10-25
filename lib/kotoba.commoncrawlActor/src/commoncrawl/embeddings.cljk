(ns commoncrawl.embeddings
  "Client for the self-hosted murakumo embedding engine
  (ADR-2607192200 2026-07-19 addendum): `POST https://api.murakumo.cloud/
  v1/embeddings`, an OpenAI-Embeddings-compatible verbatim proxy in front
  of murakumo's `:llamacpp-embed` head (BGE-M3-class, ~1024-dim dense
  pooling), gated behind the SAME bearer-token auth as `/v1/messages`
  (`local-murakumo.worker/auth-ok?` — `x-api-key` or `Authorization:
  Bearer <token>`).

  Pure orchestration + response parsing only — no IO. `embed-fn` is the
  ONLY injected capability: `(fn [text] -> response-map | nil)`, where
  `response-map` is the ALREADY-JSON-parsed OpenAI Embeddings response
  shape (`{:data [{:embedding [...]}] ...}`) — tests inject a fn returning
  a canned map; the real nbb implementation
  (`commoncrawl.live-http/embed-fn`) does the actual curl POST + JSON
  parse."
  (:require [kotoba.lang.text :as str]))

(def default-model
  "murakumo's embeddings route is a single fixed self-hosted head (no
  model-name routing table the way /v1/messages resolves `murakumo-main` —
  see local-murakumo.worker/embeddings-route, a verbatim proxy with no
  `:model` dispatch), but the OpenAI Embeddings request shape still expects
  a `model` field; llama-server's OpenAI-compatible server accepts any
  non-blank value here and ignores it for routing (the model actually
  served is whatever `--embedding` head is running), so this is
  informational/logging value, not a live routing key."
  "murakumo-embed")

(defn build-request
  "text -> the OpenAI Embeddings request body map (`{:model :input}`)."
  [text]
  {:model default-model :input (str text)})

(defn- finite-number? [v]
  (and (number? v) (not (boolean? v))
       #?(:clj (Double/isFinite (double v)) :cljs (js/Number.isFinite v))))

(defn parse-response
  "Already-JSON-parsed OpenAI Embeddings response -> the first result's
  embedding vector (a vector of finite numbers), or nil when the shape
  doesn't match (missing/empty :data, embedding not a vector of numbers,
  an {:error ...} response, ...). Never throws."
  [response]
  (try
    (let [emb (some-> response :data first :embedding)]
      (when (and (sequential? emb) (seq emb) (every? finite-number? emb))
        (mapv double emb)))
    (catch #?(:clj Exception :cljs :default) _ nil)))

(defn embed
  "`embed-fn` (`(fn [text] -> response-map | nil)`) + text -> embedding
  vector, or nil when the call fails or the response doesn't parse to a
  usable vector. Never throws — the `:advise` node treats a nil embedding
  as 'no vector for this page', which `commoncrawl.kotobase`'s ingest
  payload builder simply omits (additive `embedding?` field, ADR-2607192200 —
  absent embedding never blocks ingest of the token-searchable fields)."
  [embed-fn text]
  (when (seq (str/trim (str text)))
    (try
      (parse-response (embed-fn text))
      (catch #?(:clj Exception :cljs :default) _ nil))))
