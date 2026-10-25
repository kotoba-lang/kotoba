# org-thorchain

[![CI](https://github.com/kotoba-lang/org-thorchain/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-thorchain/actions/workflows/ci.yml)

**THORChain swap-memo grammar, quote/inbound requests as data, and verification
of what a quote endpoint hands back. Pure `.cljc`, zero dependencies, no network
access.**

Part of the kotoba-lang swap plane (ADR-2607261500). This is the **native
BTC ↔ ETH rail**: no wrapped assets, no custody, and — the part that pays for a
wallet — an affiliate fee the network itself skims on-chain.

## Why THORChain is the rail for native BTC ↔ ETH

Bitcoin has no smart contracts, so a genuinely on-chain BTC ↔ ETH swap has only
three shapes: an HTLC atomic swap (trustless but needs your own counterparty
liquidity and has an unusable UX), a wrapped asset (WBTC/tBTC — which is really
an ERC-20 swap plus a custodian), or a native cross-chain liquidity network.

THORChain is the third. And it makes the fee question trivial: **you write your
affiliate name and basis points into the memo, and the network skims the fee and
pays you, on-chain, as part of the swap.** No fee-collecting contract to write,
deploy, audit, or custody funds in. A swap out of Bitcoin is an ordinary BTC
transfer to a vault address with a memo — nothing more.

## The memo *is* the transaction

```clojure
(require '[thorchain.memo :as memo])

(memo/build {:to-asset "ETH.ETH"
             :destination "0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0"
             :limit "10000000"          ; 1e8 fixed point, minimum output
             :streaming-interval 3      ; sub-swaps, to cut slippage
             :streaming-quantity 0
             :affiliate "kb"            ; your THORName
             :affiliate-bps 30})        ; your 0.30% — skimmed on-chain
;=> "=:ETH.ETH:0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0:10000000/3/0:kb:30"
```

Grammar (verified 2026-07-26 against **both** the THORNode parser source and the
published memo docs):

```
SWAP:ASSET:DESTADDR:LIM/INTERVAL/QUANTITY:AFFILIATE:FEE:DEX_AGG:DEX_ADDR:DEX_LIM
  0    1      2              3               4       5    6       7       8
```

`build` refuses to emit anything that would fail expensively:

| guard | why |
|---|---|
| **80-byte limit** | A swap *from* Bitcoin carries its memo in an `OP_RETURN`. An over-long memo isn't truncated — the tx doesn't relay, or it relays unreadable and the vault treats the funds as a donation. This is the most expensive failure in the flow, so it throws rather than warns. `:short-asset? true` abbreviates a token contract to its last 4 hex digits to fit. |
| **fee ceiling 1000 bps** | The docs say 0–1000 bps; THORNode itself only rejects a *total* above 10000 bps (100%). This library defaults to the documented 1000 and needs explicit `:allow-node-max? true` to exceed it, because the loose reading's failure mode is a wallet quietly charging 50%. |
| **shared-bps arithmetic** | `:affiliate ["a" "b" "c"] :affiliate-bps 300` is **900 bps total**, not 300. One value applies to *each* affiliate. Counted against the ceiling accordingly. |
| **affiliate without bps** | Rejected. A missing bps is a silent 0% fee, not a default. |
| **integer 1e8 amounts** | A decimal `:limit` means the caller confused units. The grammar accepts `1e6`, but this emits plain integers: a misread exponent silently changes slippage protection. |

## Never submit a memo you haven't read

`/thorchain/quote/swap` returns both the vault address to pay *and* the memo to
attach. Together those are **complete authority over the funds** — the memo says
where the output goes. Submitting them unread means trusting whatever answered
that HTTP call with the user's money, including a hijacked or compromised
endpoint.

```clojure
(require '[thorchain.quote :as q])

(def request {:from-asset "BTC.BTC" :to-asset "ETH.ETH" :amount "10000000"
              :destination "0xe6a3…" :affiliate "kb" :affiliate-bps 30})

(q/url my-own-thornode (q/swap-quote-request request))   ; base-url is required
;; …your HTTP client…
(def quote (q/parse-swap-quote body))

(q/verify-memo request (:memo quote))
;=> {:ok? true :parsed {…}}

;; a substituted destination fails locally, not on-chain:
;=> {:ok? false :problems [{:problem :destination-mismatch
;                           :requested "0xe6a3…" :returned "0xdeadbeef…"}]}
```

`verify-memo` checks the destination (case-insensitively — EVM addresses are
checksummed inconsistently across APIs), the asset, the affiliate list, and the
total basis points in **both** directions: a quote that silently drops your fee
fails too.

**The asset check has to understand the node's own dialect.** A live call was what
revealed this: THORNode does not echo `ETH.ETH`, it writes **`e`** — and for tokens
it drops the contract entirely (`ETH.USDC-0XA0B8…EB48` → `ETH.USDC`). Before that,
`verify-memo` rejected *every legitimate live memo*. `thorchain.asset/expand` now
resolves the abbreviations, from a table **measured against a live node** rather
than guessed:

| asset | abbreviation |
|---|---|
| `ETH.ETH` | `e` |
| `BTC.BTC` | `b` |
| `THOR.RUNE` | `r` |
| `AVAX.AVAX` | `a` |

Only measured entries are listed, and an unmeasured abbreviation **fails closed**
as its own problem (`:asset-abbreviation-unrecognized`) rather than passing —
because silently accepting an asset you cannot identify means possibly paying out
a different one. To extend the table, request a quote for that asset from a node
and read the abbreviation out of the returned memo.

## An affiliate must be REGISTERED, and shape cannot tell you

A live node rejects an unregistered THORName outright:

```
PARSE FAILURE(S): cannot parse 'kb' as an Address: kb is not recognizable
```

That fails the whole swap and refunds it minus fees — and an unregistered name is
shape-identical to a registered one, so no offline validation catches it. Check
before relying on a name:

```clojure
(q/thorname-request "kb")     ;=> {:method :get :path "/thorchain/thorname/kb"}
(q/registered? body)          ;=> false — the route answers 200 either way, so the
                              ;   discriminator is the presence of `owner`, not the
                              ;   status code
```

With a registered name the network quotes the fee back to you — a live
`BTC.BTC -> ETH.ETH` quote at 30 bps returned `fees.affiliate: 511881`, i.e. the
skim is real and computed by the network, not by us.

It deliberately does *not* compare against a locally rebuilt memo string — the
node legitimately emits its own limit field and abbreviated assets, so string
equality would fail on correct memos and train people to skip the check.

Also always re-read `inbound_addresses` before sending: **vault addresses rotate**
as the validator set churns, and a halted chain still publishes one.

```clojure
(def inbound (q/parse-inbound-addresses body))
(q/chain-sendable? inbound "BTC")   ;=> true / false (halts respected)
```

## No HTTP in here

Every request is `{:method :get :path … :query {…}}` and every parser takes an
already-decoded body. The caller supplies the transport. That keeps this pure
`.cljc` — the same code runs in a browser wallet, under nbb, and on the JVM — and
means the whole test suite runs without a network.

It also means the node URL is *yours to choose* — and as of 2026-07-26 it is
**yours to provide**, because there is no usable public default to offer.

Measured from a plain HTTP client on 2026-07-26:

| host | state |
|---|---|
| `rest.cosmos.directory/thorchain` | **open** — serves the custom `/thorchain/*` routes (`quote/swap`, `thorname`) and is the one measured host a plain client can use |
| `thornode.ninerealms.com` | **DNS does not resolve** (not even via `1.1.1.1`) |
| `midgard.ninerealms.com` | DNS does not resolve |
| `thornode.thorswap.net` | Cloudflare bot interstitial (`403`, *"Just a moment…"*) |
| `thornode.thorchain.liquify.com` | resolves, connection did not complete |

So `base-url` is a **required argument** and `url` throws without one. A default
pointing at a dead or bot-gated host is worse than no default: it fails at the
moment someone is moving funds, and it looks like a bug in this library. The same
measurements live in `thorchain.quote/known-endpoints` as data, with dates.

Run your own node, or use an endpoint you have an agreement with. This library
already said that was the right call — the measurements make it mandatory rather
than advisory. **Working around bot protection is not something this library will
do**, so it also does not pretend to have a keyless public path.

## API

| ns | what |
|---|---|
| `thorchain.memo` | `build` / `parse` / `total-affiliate-bps`, `max-memo-bytes`, `max-affiliate-bps` |
| `thorchain.quote` | `swap-quote-request` / `inbound-addresses-request` / `pools-request` / `url`, `parse-swap-quote` / `parse-inbound-addresses`, **`verify-memo`**, `chain-sendable?` |
| `thorchain.asset` | `parse` / `format-asset` / `valid?` / `short-form` / `evm-chain?` / `token?`, `gas-assets` |

There is no hard-coded list of tradeable assets — that goes stale silently as
pools churn. Ask `/thorchain/pools`.

## Verification

The builder reproduces **THORChain's own published memo examples verbatim** —
external vectors, not this library's output — and the parser round-trips them,
including the awkward ones: `s:` short prefix, `1e6` scientific limit, five
affiliates sharing one bps value, per-affiliate bps, and the interior empty limit
field in `=:ETH.ETH:0x…::t1/dx/ss:10/20/30`.

`verify-memo` is tested against the adversarial cases it exists for: substituted
destination, substituted asset, dropped affiliate fee, inflated affiliate fee,
non-swap memo.

```bash
kbb -M:test                             # JVM  — 43 tests, 116 assertions
kbb --backend sci --classpath src:test bin/run_tests.cljk  # cljs — same suite
kbb -M:lint
```

## Scope

This library builds and checks the **data**. It does not hold keys, sign, or
broadcast: a BTC-side swap is signed with `kotoba-lang/btc-crypto`, an ETH-side
one with `eth-crypto` + `erc20`, and `kotoba-lang/swap` orchestrates. Fees are
booked through `kotoba-lang/treasury`.

## License

Apache-2.0
