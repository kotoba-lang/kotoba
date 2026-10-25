(ns swap.thorchain
  "Native cross-chain rail (BTC <-> ETH and friends) over THORChain.

  Shape of the whole thing: a swap out of Bitcoin is an ORDINARY BTC TRANSFER to
  a vault address, with a memo. That is why this rail can be native — no wrapped
  asset, no custodian, no smart contract on the Bitcoin side (there is no such
  thing) — and why the fee is easy: the affiliate name and basis points ride in
  the memo and the network skims them on-chain.

  So the plan this driver emits is one `:native-transfer` step for a UTXO-chain
  inbound, or one `:evm-call` (via the router) for an EVM inbound. The executor
  signs it with `btc-crypto` or `eth-crypto` respectively; nothing here holds a
  key.

  Amount units, and why they are annoying: THORChain expresses every amount in
  1e8 fixed point regardless of the asset's native decimals, but a BTC transfer
  must be built in satoshis (also 1e8 — same number) while an ETH transfer needs
  wei (1e18). So the quote's 1e8 amount and the transfer's native amount are
  different numbers for the same value, and this namespace keeps them apart
  explicitly rather than hoping they coincide."
  (:require [erc20.core :as erc20]
            [swap.core :as core]
            [swap.fee :as fee]
            [thorchain.memo :as tc-memo]
            [thorchain.quote :as tc-quote]))

;; UTXO chains that take a plain transfer + OP_RETURN memo, vs EVM chains whose
;; inbound must go through THORChain's Router contract.
(def evm-inbound-chains #{"ETH" "AVAX" "BSC" "BASE"})

(def thorchain-decimals 8)

(defn quote-request
  "Build a THORNode `/thorchain/quote/swap` request for this intent.

  `base-url` is REQUIRED — the caller's own node. There is no default, because as
  of 2026-07-26 there is no public THORNode host a programmatic client can
  actually use: ninerealms no longer resolves and thorswap answers a Cloudflare
  bot interstitial (`thorchain.quote/known-endpoints` records the measurements).
  A default pointing at a dead host would fail at the moment someone is moving
  funds and look like a bug here."
  [{:keys [from to amount destination taker slippage-bps fee-bps fee-recipient]}
   {:keys [base-url affiliate streaming-interval streaming-quantity]}]
  (let [amount-1e8 (erc20/->units amount thorchain-decimals)
        req (cond-> {:from-asset (:asset from)
                     :to-asset (:asset to)
                     :amount amount-1e8
                     :destination destination
                     :tolerance-bps slippage-bps}
              taker (assoc :refund-address taker)
              (and fee-bps (pos? fee-bps))
              (assoc :affiliate (or affiliate fee-recipient) :affiliate-bps fee-bps)
              streaming-interval (assoc :streaming-interval streaming-interval)
              streaming-quantity (assoc :streaming-quantity streaming-quantity))]
    {:method :get
     :provider :thorchain
     :url (tc-quote/url base-url (tc-quote/swap-quote-request req))
     :headers {}
     :verify-with req
     :amount-1e8 amount-1e8}))

(defn- native-amount
  "The amount to actually send on the inbound chain, in ITS units — satoshis for
  BTC (1e8), wei for ETH (1e18). Derived from the human amount, not converted
  from the 1e8 quote amount, so an 18-decimal asset does not lose 10 decimal
  places on the way through THORChain's fixed point."
  [{:keys [from]} amount]
  (erc20/->units amount (:decimals from)))

(defn parse-quote
  "THORNode response -> normalized `swap.core` quote with an execution plan.

  VERIFIES THE RETURNED MEMO before building any step. A quote returns both the
  vault address and the memo, and the memo says where the output goes — so an
  unverified memo is a remote server with authority over the user's funds.
  `thorchain.quote/verify-memo` re-checks destination, asset, affiliate and total
  basis points; a mismatch throws here rather than becoming a transfer."
  [{:keys [from to amount fee-bps fee-recipient] :as intent}
   {:keys [verify-with]}
   body]
  (let [q (tc-quote/parse-swap-quote body)
        verdict (tc-quote/verify-memo verify-with (:memo q))]
    (when-not (:ok? verdict)
      (throw (ex-info (str "swap/thorchain: the quote's memo does not match what was"
                           " requested — refusing to build a transfer. "
                           (pr-str (:problems verdict)))
                      {:problems (:problems verdict) :memo (:memo q)})))
    (when-not (:inbound-address q)
      (throw (ex-info "swap/thorchain: quote has no inbound_address" {:raw body})))
    (let [amount-native (native-amount intent amount)
          evm-inbound? (contains? evm-inbound-chains (:chain from))
          why (str "send " amount " " (:symbol from (:chain from))
                   " to the THORChain vault to receive at least "
                   (:expected-amount-out q) " (1e8) of " (:asset to)
                   (when (pos? (or fee-bps 0))
                     (str "; " (/ (double fee-bps) 100.0) "% affiliate fee to "
                          fee-recipient " is skimmed on-chain by the network")))
          step (if evm-inbound?
                 {:step/kind :evm-call
                  :step/why why
                  :chain (:chain from)
                  :chain-id (:chain-id from)
                  :to (or (:router q) (:inbound-address q))
                  ;; The EVM inbound goes through THORChain's Router contract
                  ;; (depositWithExpiry) rather than a plain transfer, so the
                  ;; router address and its calldata must come from the node's
                  ;; own response; this driver does not synthesize router
                  ;; calldata from a hard-coded ABI.
                  :router (:router q)
                  :vault (:inbound-address q)
                  :memo (:memo q)
                  :amount amount-native
                  :value (if (:address from) "0" amount-native)
                  :needs-router-calldata? true}
                 {:step/kind :native-transfer
                  :step/why why
                  :chain (:chain from)
                  :to (:inbound-address q)
                  :amount amount-native
                  :memo (:memo q)})]
      {:rail :thorchain
       :provider :thorchain
       :expected-out (:expected-amount-out q)
       ;; The memo's limit field IS this rail's on-chain min-out guard, so it is
       ;; surfaced as the normalized min-out and held to the same standard as the
       ;; aggregator rail. Deliberately NOT defaulted to expected-out when the
       ;; memo carries no limit: that would report a guard that the network is not
       ;; enforcing. nil here makes swap.core/check raise :missing-min-out, which
       ;; is the truth — request a tolerance so the node emits a limit.
       :min-out (:limit (tc-memo/parse (:memo q)))
       :fee-bps (or fee-bps 0)
       :fee-mechanism (:mechanism (fee/quote-fee intent :protocol-affiliate))
       :expires-at (:expiry q)
       :inbound-address (:inbound-address q)
       :memo (:memo q)
       :outbound-delay-seconds (:outbound-delay-seconds q)
       :total-swap-seconds (:total-swap-seconds q)
       :warning (:warning q)
       :dust-threshold (:dust-threshold q)
       :recommended-min-amount-in (:recommended-min-amount-in q)
       :steps [step]
       :raw body})))

(defn preflight
  "Checks that only make sense for this rail, given a parsed inbound_addresses
  map. Returns a problem list (empty = fine).

  - the inbound chain must not be halted (a halted chain still publishes a vault
    address, so paying it means waiting for the halt to lift or a refund);
  - the amount must clear the chain's dust threshold;
  - the amount should clear the quote's `recommended_min_amount_in`, below which
    fixed outbound fees eat a large fraction of the swap."
  [{:keys [from]} quote inbound]
  (let [chain (:chain from)]
    (cond-> []
      (not (tc-quote/chain-sendable? inbound chain))
      (conj {:problem :chain-not-sendable :chain chain
             :inbound (get inbound chain)})

      (let [amt (:amount (first (:steps quote)))]
        (and (:dust-threshold quote) amt
             (not (core/amount< (:dust-threshold quote) amt))))
      (conj {:problem :below-dust-threshold
             :amount (:amount (first (:steps quote)))
             :dust-threshold (:dust-threshold quote)
             :note "a transfer at or below the vault's dust threshold is ignored"})

      (let [amt (:amount (first (:steps quote)))]
        (and (:recommended-min-amount-in quote) amt
             (core/amount< amt (:recommended-min-amount-in quote))))
      (conj {:problem :below-recommended-minimum
             :amount (:amount (first (:steps quote)))
             :recommended (:recommended-min-amount-in quote)
             :note "fixed outbound fees eat a large fraction of a swap this small"})

      (:warning quote)
      (conj {:problem :provider-warning :warning (:warning quote)}))))
