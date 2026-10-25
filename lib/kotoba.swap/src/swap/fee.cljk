(ns swap.fee
  "How the fee is taken, and how it gets booked.

  THREE MECHANISMS, IN PREFERENCE ORDER — this is the whole commercial question
  of a MetaMask-style wallet, so the trade-offs are stated here rather than
  implied by whichever one got implemented first:

  1. `:protocol-affiliate` — the aggregator or cross-chain network skims the fee
     ON-CHAIN and pays a named recipient as part of the swap (0x's
     `swapFeeRecipient`/`swapFeeBps`, THORChain's affiliate memo field). One
     transaction, no custody, no contract to deploy or audit. **Use this.**
     MetaMask's own 0.875% works this way — it is embedded in the quote, not a
     second transfer, and the gas the user pays goes to validators, not to
     MetaMask.

  2. `:separate-transfer` — swap, then transfer the fee to the treasury in a
     second transaction. Trivial to implement and available on any provider, but
     it doubles gas, and the two transactions are not atomic: the swap can land
     and the fee transfer fail (or be front-run into a different price), leaving
     the books and the chain disagreeing. Supported here because sometimes a
     provider offers nothing better — never as a default.

  3. A custom fee-router contract — one transaction, fee and swap atomic, and
     total control. Also: a new contract that custodies third-party funds, which
     means an audit, a deployment key, an upgrade story, and a permanent
     liability. `kotoba-lang/engi-witness-escrow` is this workspace's precedent
     for writing Solidity at all, and it is explicitly marked local-test-only.
     Not implemented here, on purpose.

  BOOKING: fee events are recorded through `kotoba-lang/treasury`, which already
  has the no-custody append-only ledger shape the rest of this workspace uses —
  pending until the transaction is confirmed on-chain, only then confirmed. A fee
  that is booked before confirmation is a fee that can be booked and never
  received."
  (:require [treasury.core :as treasury]))

(def mechanisms #{:protocol-affiliate :separate-transfer :none})

(def preferred-mechanism :protocol-affiliate)

(defn bps->frac
  "Basis points -> fraction, for `treasury/fee-split`. 30 bps -> 0.003."
  [bps]
  (/ (double bps) 10000.0))

(defn split
  "USD notional + our bps -> `{:usd :fee :net}` via `treasury/fee-split`, so swap
  fees and every other fee in this workspace are computed by one function."
  [usd bps]
  (treasury/fee-split usd (bps->frac bps)))

(defn quote-fee
  "Describe the fee attached to a quote, without touching amounts: which
  mechanism carries it, how many basis points, and to whom.

  `:mechanism :none` with a non-zero `:bps` is the dangerous combination — the
  swap looks fee-bearing and earns nothing. `swap.core/check` treats it as a
  hard problem; this function just reports it faithfully."
  [{:keys [fee-bps fee-recipient]} mechanism]
  {:bps (or fee-bps 0)
   :mechanism (if (and fee-bps (pos? fee-bps)) mechanism :none)
   :recipient fee-recipient
   :preferred? (= mechanism preferred-mechanism)})

;; ── is the fee recipient actually THERE? ──────────────────────────────────

(defn recipient-code-request
  "An `eth_getCode` request for the fee recipient, as data (no I/O in this library).
  Hand the result to `verify-recipient`.

  WHY THIS EXISTS: a Safe or any other contract recipient is deployed PER CHAIN. An
  address being unoccupied on another chain does not mean the Safe is there, and a
  fee paid to an address with no code on that chain cannot be moved by anyone. This
  is not hypothetical — a real Safe measured on 2026-07-26 existed on Ethereum and
  had NO code on BSC, Avalanche, Base, Polygon, Arbitrum or Optimism, while
  `treasury` was at the time advising exactly that switch to a cheaper L2 without
  changing the recipient."
  [{:keys [fee-recipient]}]
  (treasury/code-request fee-recipient))

(defn verify-recipient
  "Check that the fee recipient exists on the chain the fee will be paid on.
  `code-result` is what `eth_getCode` returned for `recipient-code-request`.

  Only meaningful when the recipient is a CONTRACT — an EOA legitimately has no
  code, which is why `intent` carries `:fee-recipient-contract?` rather than this
  function guessing."
  [{:keys [fee-recipient fee-recipient-contract?] :as intent} code-result]
  (treasury/verify-recipient-deployed
   {:address fee-recipient
    :chain (or (get-in intent [:to :chain]) (get-in intent [:from :chain]))
    :expect-contract? (boolean fee-recipient-contract?)}
   code-result))

(defn pending-entry
  "A ledger entry for a fee whose swap has been submitted but NOT confirmed.
  `usd` is the notional the fee was computed on (the caller owns pricing — this
  library never invents a USD rate). `:bps` is accepted but unused: a pending
  entry records only that a claim exists, and the fee/net split is not computed
  until the transaction confirms."
  [{:keys [payer usd chain tx-id]}]
  (treasury/pending-entry :swap-fee payer usd tx-id (or chain "ethereum")))

(defn confirmed-entry
  "A ledger entry for a fee whose swap is confirmed on-chain."
  [{:keys [payer usd bps chain tx-id]}]
  (treasury/confirmed-entry :swap-fee payer usd (bps->frac bps) tx-id
                            (or chain "ethereum")))
