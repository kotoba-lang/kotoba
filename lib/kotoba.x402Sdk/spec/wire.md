# The wire, once

Both packages implement this and nothing else. It is transcribed from
`kotoba-lang/pay`'s `pay.x402`, which is what x402.nexus actually runs — not
from a specification document that the server might have drifted from.

## 1. Ask without paying

    GET /gateway/<seller>/<path>

No `X-PAYMENT` header. The answer is `402` with:

    {"x402Version": 1,
     "accepts": [ {...}, ... ],
     "error": "X-PAYMENT header is required"}

Each element of `accepts` states one acceptable payment **completely**:

| field | meaning |
|---|---|
| `scheme` | `exact` (EIP-3009, buyer needs no gas) or `transaction` (a settled transfer) |
| `network` | `base`, `base-sepolia`, or the CAIP-2 form |
| `asset` | the token contract on THAT network |
| `payTo` | the recipient |
| `maxAmountRequired` | amount in the token's smallest unit, as a string |
| `maxTimeoutSeconds` | how long the offer stands |
| `extra` | `{name, version}` — the EIP-712 domain of `asset` |

**Read every one of these from the response, every time.** They are not
constants. `extra.name` is `USD Coin` for Base mainnet USDC and `USDC` for
Base Sepolia USDC: signing under the wrong one produces a signature that
recovers a different address, and the payment is rejected as a bad signature —
which reads like the buyer's fault.

## 2. Pay

`scheme: "exact"` — sign an EIP-3009 `TransferWithAuthorization` under the
EIP-712 domain `{name: extra.name, version: extra.version, chainId, verifyingContract: asset}`:

    TransferWithAuthorization(address from,address to,uint256 value,
                              uint256 validAfter,uint256 validBefore,bytes32 nonce)

The buyer needs **no ETH**. The facilitator submits the authorization and pays
the gas.

`scheme: "transaction"` — make the transfer yourself and carry the hash.

## 3. Retry

    X-PAYMENT: base64(JSON.stringify(payload))

    exact:       {"x402Version":1,"scheme":"exact","network":…,
                  "payload":{"signature":"0x…",
                             "authorization":{"from","to","value",
                                              "validAfter","validBefore","nonce"}}}
    transaction: {"x402Version":1,"scheme":"transaction","network":…,
                  "payload":{"txHash":"0x…","from":"0x…"}}

Same method, same URL, same body. The gateway verifies on-chain and proxies
the real resource.

## What these SDKs do not do

They hold no key and sign nothing. A `signer` is injected, so the wallet stays
wherever its owner put it and this library never becomes a place a key could
leak from. That is the same seam every other injection point in this
workspace uses, and it is why these packages have no cryptography dependency.
