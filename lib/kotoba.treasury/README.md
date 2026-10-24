# treasury

[![CI](https://github.com/kotoba-lang/treasury/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/treasury/actions/workflows/ci.yml)

**Domain-agnostic USDC payment quoting + on-chain verification + append-only
ledger entries, in pure Clojure/ClojureScript (`.cljc`).**

Extracted from `gftdcojp/local-murakumo`'s crypto top-up flow
(ADR-2607051621) so that any project needing "accept a stablecoin payment to
a treasury address, verify it on-chain, mint something once confirmed" can
depend on one tested implementation instead of re-deriving it. Pricing/units
(credits-per-usd, subscription plans, protocol-fee rate, …) are the
*consuming* project's concern — this library only knows USD, USDC, EVM
chains, and a signed append-only run-ledger shape.

```clojure
(require '[treasury.core :as treasury])

;; 1) quote a payment: how much USDC, on which chain, to which treasury
(treasury/crypto-quote 10 0.05 "0xYourSafeAddress")
;; => {:asset "USDC" :usd 10.0 :chain "ethereum" :treasury "0xYourSafeAddress"
;;     :amount 10.0 :fee 0.5 :net 9.5 ...}

;; 2) payer submits a tx hash -> record as pending (nothing minted yet)
(def pending (treasury/pending-entry :protocol-fee "did:key:zAlice" 10 "0xTX"))

;; 3) a verifier fetches the on-chain tx (RPC/indexer) and confirms
(treasury/verify-payment pending
                          {:to "0xYourSafeAddress" :amount 10 :confirmations 5}
                          {:treasury "0xYourSafeAddress" :fee-frac 0.05 :min-confirmations 3})
;; => {:ok? true :reason :confirmed :entry {...}}
```

## No custody

A payer sends USDC from their **own wallet** directly to a treasury address
the caller supplies (typically a Gnosis Safe multisig) — this library never
holds keys or moves funds. A ledger entry is produced only *after* on-chain
confirmation (`verify-payment`); an unverified claim stays `:pending`, so a
fake or underpaid tx hash can't mint or confirm anything.

## What's in scope / out of scope

- **In scope**: `chains` (Ethereum/Base/Arbitrum USDC contracts + explorer
  APIs), `fee-split`, `crypto-quote`, `pending-entry`/`confirmed-entry`,
  `verify-payment` (recipient/amount/confirmations checks),
  `pending-payments`, `payment-status`, `etherscan-row->onchain`.
- **Out of scope** (the consuming project's job): what a payment is *for*
  (credits, a subscription seat, a network-registry fee, …) beyond the
  opaque `kind` tag round-tripped through `pending-entry`/`confirmed-entry`;
  any actual RPC/indexer call to fetch on-chain data (`verify-payment` takes
  the on-chain record as a plain map so it stays unit-testable without a
  chain).

## Test

```bash
kbb -M:test
```
