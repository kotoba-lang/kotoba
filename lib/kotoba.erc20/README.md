# erc20

[![CI](https://github.com/kotoba-lang/erc20/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/erc20/actions/workflows/ci.yml)

**ERC-20 calldata + EIP-2612 permit typed data, in pure `.cljc` with zero
dependencies — and it actually runs in a browser.**

Part of the kotoba-lang swap plane (ADR-2607261500): `eth-crypto` signs
transactions, `swap` routes them, `treasury` books the fee — this library is the
token layer in between. Nothing here hashes, signs, or sends: it turns intent
into calldata and calldata back into values.

```clojure
(require '[erc20.core :as erc20])

;; 1) exact decimal -> smallest unit, with string arithmetic (no float, ever)
(erc20/->units "1.5" 6)              ;=> "1500000"      (USDC has 6 decimals)
(erc20/->units "0.1" 18)             ;=> "100000000000000000"

;; 2) calldata
(erc20/transfer "0x3535…35" "1500000")
;=> "0xa9059cbb0000000000000000000000003535…"
(erc20/approve router (erc20/->units "1.5" 6))
(erc20/balance-of owner)             ; for eth_call

;; 3) decode what eth_call gave back
(erc20/decode-uint "0x…000f4240")    ;=> "1000000"   (decimal STRING, not a number)
(erc20/decode-string "0x…")          ;=> "USD Coin"
(erc20/->display "1500000" 6)        ;=> "1.5"
```

## Why the selectors are pinned rather than hashed

A 4-byte function selector is `keccak256(signature)[0..4]` — but the ERC-20
selectors are **constants**. So they are pinned in `erc20.core/selectors` and
**verified** against `keccak256` in the test suite instead of recomputed at
runtime. Static-type ABI encoding is likewise just 32-byte word padding.

Result: **zero runtime dependencies, and no hash implementation needed on either
platform** — yet nobody has to trust a hand-typed hex string, because
`test/erc20/selector_test.cljk` recomputes all 12 of them with `keccak256`. That
is the only kind of shortcut that's safe here: pin a constant *and* prove it. A
hand-typed selector that's wrong 1 time in 12 doesn't crash — it quietly calls a
different function on a real token.

When this library was written, `eth-crypto/keccak256` was also `:clj`-only, so
pinning was the *only* way to serve a browser. That port has since landed
(`eth-crypto` is now fully dual-platform), so pinning is now a choice — kept on
the merits above rather than out of necessity.

## Numbers are strings

`uint256` does not fit in a double, and **ClojureScript loses precision above
2^53 before this library ever sees the value**. So:

- pass amounts as decimal strings (`"1000000"`) or `0x`-hex, not as numbers;
- `decode-uint` returns a **decimal string**, never a number;
- `->units` / `->display` are **pure string arithmetic** — `0.1` at 18 decimals
  is exactly `100000000000000000`, not `99999999999999999`;
- `->units` **throws** if the amount carries more fractional digits than the
  token has decimals (`:truncate? true` opts into truncation). Quietly losing a
  user's dust is worse than failing loudly.

## API

### `erc20.core`

| fn | → |
|---|---|
| `transfer` / `transfer-from` / `approve` | 0x… calldata (state-changing) |
| `allowance` / `balance-of` / `total-supply` / `decimals` / `symbol-of` / `name-of` | 0x… calldata (`eth_call`) |
| `nonces` / `domain-separator-call` | EIP-2612 views |
| `permit` | `permit(owner,spender,value,deadline,v,r,s)` calldata |
| `decode-uint` | return data → decimal **string** |
| `decode-bool` / `decode-address` / `decode-string` | return data → value |
| `->units` / `->display` | exact decimal ↔ smallest unit |
| `max-uint256` | `2^256-1` as a decimal string |
| `selector` / `selectors` | pinned 4-byte selectors (throws on unpinned) |
| `uint-word` / `address-word` / `bytes32-word` / `calldata` | word-level primitives |

`decode-address` returns a **lowercase** address — EIP-55 checksumming needs
keccak256, so pipe it through `eth-crypto/eip55-checksum` on the JVM if you
need the mixed-case form.

### `erc20.permit` (EIP-2612)

Builds the EIP-712 *data* only, so it stays portable and the signing can happen
anywhere — `eth-crypto` on the JVM, a hardware wallet, a WebAuthn passkey, or a
browser provider's `eth_signTypedData_v4`.

```clojure
(require '[erc20.permit :as permit] '[eth-crypto.core :as eth])

(let [{:keys [domain types primary message]}
      (permit/typed-data {:name "USD Coin" :version "2" :chain-id 1 :token usdc
                          :owner owner :spender router
                          :value (erc20/->units "1.5" 6)
                          :nonce 0 :deadline 1750000000})]
  (eth/eip712-digest domain types primary message))   ; sign this
```

**`:version` is not guessable.** USDC uses `"2"`, most tokens `"1"`, and DAI's
permit is a different struct entirely. A wrong name/version/chainId produces a
signature the token rejects with no other symptom — cross-check your domain
against the token's own `DOMAIN_SEPARATOR()` (`erc20.core/domain-separator-call`)
before trusting it.

**Permit2 is deliberately not implemented.** Uniswap's `PermitSingle` /
`PermitDetails` / `TokenPermissions` structs aren't reproduced from memory:
a subtly wrong EIP-712 struct yields signatures that are silently invalid, or
valid for something other than what the UI showed. It needs the real spec plus a
cross-implementation digest check — the same bar the EIP-2612 path met.

## Verification

Vectors come from an **independent implementation** (viem 2.x
`encodeFunctionData` / `encodeAbiParameters` / `hashTypedData`), not from this
library's own output:

- every calldata builder, byte-for-byte;
- all **12 selectors** recomputed from their canonical signatures with
  `keccak256`;
- the **EIP-2612 permit digest** for a real USDC permit == viem's
  `hashTypedData`, plus a sign → `ecrecover` roundtrip that recovers the owner;
- return-value decoding against viem-encoded words, including a
  `2^256-1` balance that a double would corrupt;
- `->units` / `->display` roundtrips and the refuse-to-truncate path.

```bash
kbb -M:test                            # JVM  — 31 tests, 77 assertions
kbb --backend sci --classpath src:test bin/run_tests.cljk # cljs — 27 tests, 60 assertions
kbb -M:lint
```

Both suites are CI gates. The cljs one is not decorative: it is the claim that
this works in a browser.

### And it has run on a real chain

`bin/verify_onchain.cljk` signs and broadcasts real transactions to Sepolia
(12/12 on 2026-07-26). Not in CI — it spends testnet funds and depends on a
public RPC — but it is the end of the ladder that unit vectors start:

| tx | what it proves |
|---|---|
| [`0xa3e0d711…`](https://sepolia.etherscan.io/tx/0xa3e0d7115a5b91c9b124f93066b3467e00bf1ffdd508a8c11f237a2f14aeb6e4) | an EIP-1559 envelope carrying **both calldata and value** — `deposit()` on Sepolia WETH, mined `status 0x1` |
| [`0x9a48363f…`](https://sepolia.etherscan.io/tx/0x9a48363f1a5123fdbfb27faae2d61b3db4344c11f2a12e2d9e760f7b3b6c87f0) | **this library's `transfer` calldata executing on a real deployed token**, mined `status 0x1` |

Then read back through this library's own decoder: `balanceOf(us)` was exactly
`0.01` WETH after the wrap and exactly `0.006` after transferring `0.004`, and the
recipient's balance rose by exactly `0.004`. Two independent things are confirmed
there — the calldata was correct, and `->units`/`->display`/`decode-uint` agree
with what the chain actually did.

Two checks in that script are worth copying elsewhere:

- **Before broadcasting**, `ecrecover` on the digest must return our own address.
  A signature that does not recover locally must never reach a node.
- **After broadcasting**, the node's transaction hash is compared to
  `eth-crypto/raw-tx-hash` computed locally. Both matched byte-for-byte, which is
  the only way to verify that function against an independent authority.

## Usage

```clojure
;; deps.edn
io.github.kotoba-lang/erc20 {:git/sha "<sha>"}
```

No runtime dependencies. `eth-crypto` is a **test-only** dependency here (it
verifies the selectors and the permit digest).

## License

Apache-2.0
