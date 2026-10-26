# x402-sdk

**x402 clients for AI agents: read the 402, pay, retry.** One wire contract,
one library per language, no key ever held here.

x402 is HTTP's own payment step: ask for a resource, get `402` with the terms,
pay, ask again with the proof. It is small enough that an SDK's job is not to
hide it but to get the four details right that are easy to get wrong.

| package | install | tests |
|---|---|---|
| [`packages/go`](packages/go) | `go get github.com/kotoba-lang/x402-sdk/packages/go` | `go test ./...` |
| [`packages/typescript`](packages/typescript) — [`@com-kotobalabs/x402`](https://www.npmjs.com/package/@com-kotobalabs/x402) | `npm i @com-kotobalabs/x402` | `npm test` |
| [`packages/python`](packages/python) — [`com-kotobalabs-x402`](https://pypi.org/project/com-kotobalabs-x402/) | `pip install com-kotobalabs-x402` | `python -m unittest discover -s tests` |
| [`packages/rust`](packages/rust) — [`com-kotobalabs-x402`](https://crates.io/crates/com-kotobalabs-x402) | `cargo add com-kotobalabs-x402` | `cargo test` |

**All four are published.** Measured against the registries 2026-09-09, not
read off this file: npm, PyPI and crates.io each answer for `0.1.0`, and the Go
proxy answers `v0.1.0` at tag `packages/go/v0.1.0`. Every one was uploaded
2026-09-01.

Published under the `com-kotobalabs` organisation. `x402-sdk`, `x402` and
`x402-client` were already taken across crates.io, npm and PyPI — checked
before publishing rather than after a rejected upload — and the reverse-DNS
form says whose it is, which is more useful than a generic name anyway. npm
carries it as a scope; PyPI and crates.io have none, so they carry it as a
prefix.

This paragraph used to say that npm and PyPI `need a token created through a
web login`, and marked two of the four rows `once published`. That was true
when it was written and stopped being true on 2026-09-01, when all four were
pushed. It stayed here for eight days, and for those eight days the honest
caution — *saying `npm i` works before anyone has pushed would be a claim about
a registry rather than about this code* — was making the opposite error: a
claim that the code was unavailable when it was not. **Check the registry, not
the README.** Both directions of that sentence need the same evidence.

The contract both implement is [`spec/wire.md`](spec/wire.md), transcribed from
the facilitator that actually runs rather than from a document it might have
drifted from.

## The safe first call

```python
from x402_sdk import challenge
c = challenge("https://x402.nexus/gateway/hanmoto/x402/counts")
```

```ts
import { challenge } from "@com-kotobalabs/x402";
const c = await challenge("https://x402.nexus/gateway/hanmoto/x402/counts");
```

No key, no payment, no side effect. `c.accepts` states every acceptable
payment completely — price, token, network, recipient, and the EIP-712 domain
to sign under.

```go
import x402 "github.com/kotoba-lang/x402-sdk/packages/go"
c, _ := (&x402.Client{}).Challenge("https://x402.nexus/gateway/hanmoto/x402/counts")
```

## Paying

```ts
const res = await fetchWithPayment(url, undefined, {
  policy: { networks: ["base-sepolia"],
            assets: ["0x036CbD53842c5426634e7929541eC2318f3dCF7e"],
            maxAmount: "5000" },
  signer,                       // yours. See below.
});
```

**You do not need ETH.** The `exact` scheme has the facilitator submit the
authorization and pay the gas, so a buyer holding only USDC can pay.

## Optional paid-output validation

The library signs a payment authorization, retries with `X-PAYMENT`, and returns
the seller's HTTP response. It does **not** observe or verify on-chain
settlement, guarantee paid delivery, or judge response validity beyond what you
check. An optional hook runs only on a **successful** paid application response
(HTTP 2xx after the retry). A terminal second `402`, any other non-success
response, a free initial success, and pre-payment refusal are returned or thrown
unchanged and never invoke the hook. Rejection throws without another request,
credential, signature, authorization, retry, or payment.

```ts
import { fetchWithPayment, PaidOutputRejectedError } from "@com-kotobalabs/x402";

try {
  const res = await fetchWithPayment(url, undefined, {
    policy: { networks: ["base-sepolia"],
              assets: ["0x036CbD53842c5426634e7929541eC2318f3dCF7e"],
              maxAmount: "5000" },
    signer,
    validatePaidOutput: (view) => {
      const data = view.json() as { sku?: string };
      if (data.sku !== "expected-sku") throw new Error("wrong sku");
    },
  });
  // res is the original Response object from the paid retry
} catch (err) {
  if (err instanceof PaidOutputRejectedError) {
    // err.response is the same original Response; err.attemptEvidence is frozen
  }
}
```

The validator receives a detached body copy and frozen payment-attempt evidence
(offer, authorization, signature, payment header). Mutation does not alter the
response or evidence attached to the error.

## Four things these libraries insist on

**The signer is injected** (and in Rust, the HTTP transport too). These packages hold no key, sign nothing, and have
no cryptography dependency. Your wallet stays wherever you put it — viem,
ethers, eth-account, a hardware device, a remote signer. A payment library
that wants your key is a place your key can leak from.

**A policy is required.** `selectOffer` with no policy refuses with
`no-policy` rather than paying. There is no default ceiling, because a default
ceiling is a limit nobody chose.

**The cheapest allowed offer wins, never the first.** Sellers list the same
resource on mainnet and on a testnet in their own order. Taking `accepts[0]`
is how a buyer pays real money to rehearse.

**The EIP-712 domain comes from the offer.** Base mainnet USDC calls itself
`USD Coin`; Base Sepolia USDC calls itself `USDC`. Signing under the wrong one
produces a signature that recovers a different address, and the payment is
rejected as a bad signature — which reads like your fault. These libraries
refuse an offer that carries no domain rather than guessing one, and they
refuse an unknown network rather than defaulting its chain id.

## Refusals are named

Every refusal says which check failed, and **all** of them, not just the
first: an offer on the wrong network usually names that network's token too,
and a caller told only `network-not-allowed` will fix the network and be
refused again.

    no-policy · scheme-not-allowed · network-not-allowed · asset-not-allowed
    over-budget · unparseable-amount · not-a-challenge · no-offers

## What they do not do

They do not settle, do not hold funds, and do not implement the `transaction`
scheme's transfer — an offer asking for it is refused by name. They are the
protocol, not the wallet.

## Measured against a live facilitator

    challenge: parsed | offers: 2
      testnet         -> base-sepolia 1000 units domain=USDC/2     chainId=84532
      mainnet-only    -> base         1000 units domain=USD Coin/2 chainId=8453
      1-unit ceiling  REFUSED asset-not-allowed+network-not-allowed+over-budget
    catalog: 25 SKUs

MIT.
