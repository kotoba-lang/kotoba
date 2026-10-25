(ns kotoba.securities.pricing
  "Optional bridge to `cloud-itonami-isic-6311` (the multi-asset market-
  data actor: MarketData-LLM sealed advisor ⊣ MarketDataGovernor) for a
  reference price to feed into `kotoba.securities`' pure position/trade/
  NAV functions.

  `kotoba.securities` itself carries no real market data, price feed or
  custody integration by design (README: 'an operator supplies their own
  licensed data/custody providers'). This namespace is ONE way an
  operator can supply that feed as an OSS option instead of rolling their
  own -- it is entirely optional (requires this namespace explicitly;
  `kotoba.securities`/`kotoba.securities.export`/`kotoba.securities.ui`
  have zero compile-time or runtime dependency on it, same isolation
  shape as `cloud-itonami-isic-6910`'s `formation.corporate-intel` ->
  `cloud-itonami-isic-8291` cross-reference). A securities deployment that
  never requires `kotoba.securities.pricing` runs exactly as before,
  offline, with zero network calls.

  Querying a reference price still goes through the real
  MarketDataGovernor -- a subscriber tenant/tier contract is required, a
  request for a halted/circuit-broken instrument escalates to a human, a
  request beyond your tier's columns is over-disclosure. There is no
  'internal caller' bypass: `reference-price` is the same
  `:disclosure/query` op any other subscriber would send, just wired in
  from securities' side."
  (:require [langgraph.graph :as g]
            [marketdata.report :as report]
            [kotoba.securities :as sec]))

(defn reference-price
  "Queries `actor` (a compiled cloud-itonami-isic-6311 OperationActor --
  `(marketdata.operation/build db)`) for `instrument-id`'s latest governed
  price under `context` (a subscriber context,
  `{:actor-id .. :actor-role :subscriber :tenant ..}` -- the same
  MarketDataGovernor-checked context any other `:disclosure/query` caller
  supplies).

  Returns the price (a number), or nil when the governor holds the query
  (no active contract for `:tenant`, the instrument is halted/circuit-
  broken and escalates to a human, etc.) -- callers must treat nil as 'no
  governed price available right now', never assume a licensed feed is
  always live. `db` is the same market-data Store `actor` was built over
  (needed to render the approved columns after a successful query)."
  [actor db instrument-id context]
  (let [res (g/run* actor
                    {:request {:op :disclosure/query :subject instrument-id
                               :instrument-id instrument-id}
                     :context context}
                    {:thread-id (str "securities-pricing-" instrument-id "-" (gensym))})]
    (when (= :commit (get-in res [:state :disposition]))
      (:price (report/render-quote db instrument-id [:price])))))

(defn position-with-market-price
  "Convenience: builds a `kotoba.securities/position` using
  `reference-price` for `:price` instead of a caller-supplied literal.

  Returns nil (never a position with a fabricated/zero price) when no
  governed price is available -- the caller decides the fallback (reject
  the position build, use a cached/last-known price, escalate to a
  human); this fn never silently defaults an unpriced position."
  [actor db id holder instrument-id quantity context & {:keys [currency]}]
  (when-let [price (reference-price actor db instrument-id context)]
    (sec/position id holder instrument-id quantity :currency currency :price price)))
