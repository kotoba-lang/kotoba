# en

**EN — the native currency unit riding on `kotoba-lang/engi`'s L1** —
implements
[ADR-2607993000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607993000-engi-l1-byzantine-consensus-en-currency.md)
(`com-junkawasaki/root`): ENGI (縁起) is the L1 — `engi.consensus`'s
chained-HotStuff BFT consensus, giving a globally-ordered, 3-chain-committed
sequence of transfers. EN (縁) is the currency unit that rides on top of
that order — this repo.

## What this is (and deliberately is not)

This is the simplest possible "smart contract": engi/L1 supplies global
BFT-finalized order; `en.core` supplies the deterministic state-transition
semantics over that order. There is no VM, no opcodes, no gas metering,
because ENGI/EN's entire domain is one operation (move a mutual-credit
balance between two `did:key` agents) and one invariant (net-zero, never
below a declared credit limit) — `en.core/replay-balances` **reuses**
`engi.core/fold-balance` unchanged, per agent, rather than duplicating its
invariant-checking logic. See `src/en/core.cljk`'s namespace docstring for
the exact reuse boundary.

`en.core/replay-balances` takes an **already-finalized**, globally-ordered
vector of transfers — i.e. the output of resolving `engi.consensus`'s
3-chain-committed blocks' proposal CIDs to their actual `TransferBody`
content. That resolution (reading kotobase.net, verifying witness Quorum
Certificates) is **not implemented in this repo yet** — see "Deliberately
NOT implemented" below.

## Usage

```clojure
(require '[en.core :as en])

(def replay
  (en/replay-balances
   [{:spender "did:key:zAlice" :receiver "did:key:zBob" :amount 15 :transfer-id "t0" :ts 0}]
   {"did:key:zAlice" -1000}))   ; credit-limits, same sign convention as ADR-2607101100

(en/balance-of replay "did:key:zAlice")  ; => -15
(en/balance-of replay "did:key:zBob")    ; => 15
(en/net-zero? replay)                    ; => true
```

## Deliberately NOT implemented (v1 scope)

- **Resolving `engi.consensus` blocks/proposal CIDs into the `transfers`
  vector `replay-balances` expects.** This repo starts one layer above
  that: it assumes the finalized transfer list already exists. Wiring this
  up to real `kotoba-lang/engi` L1 output (reading finalized blocks from
  kotobase.net, verifying each block's Quorum Certificate) is explicit
  follow-up — the same "pure core first, I/O layered on top later" order
  `kotoba-lang/engi` itself followed (`engi.core` landed before
  `engi.crypto`/`engi.store`/`engi.protocol`).
- **cljs / npm / shadow-cljs.** `en.core` is a plain `.cljc` with zero
  platform-specific dependencies (unlike `engi.crypto`, it needs no
  `@noble/curves`), so there is nothing cljs-specific to build yet. Add a
  cljs test target once an I/O layer needs it (mirroring
  `kotoba-lang/engi`'s `gen-shadow-cljs-edn.bb` pattern).
- **Minting / non-net-zero operations.** There are none, by design — every
  finalized transfer's delta always nets to zero (`net-zero?` is checkable
  after any prefix of the log, not just the full one).

## Layout

```
src/en/core.cljk      pure currency-unit logic — NO I/O, NO crypto, NO wall
                       clock. Depends only on engi.core (also pure), reused
                       unchanged for per-agent invariant-checked replay.
test/en/core_test.cljk unit tests: two-agent and multi-agent transfers net
                        to zero, credit-limit breach reported as data (never
                        throws), malformed (non-positive amount) transfer
                        throws, empty log is net-zero.
```

## Testing

```bash
kbb -M:test   # en.core-test (pure, JVM, no npm needed)
kbb -M:lint   # clj-kondo, src+test
```

## Finalized prefix adapter

`en.finality/project` verifies a complete bounded Inga prefix, resolves every
committed transfer, checks both parties' content and chain/genesis signatures,
and replays the native mutual-credit invariant. Missing proposals, nonce
collisions, rollback, forks or exceeded credit floors refuse the entire view.
A trusted host supplies content IDs, signature verification and credit grants.
Real-signature/QC fixtures qualify this adapter; they are not production funding
or proof that the live node's record envelopes are wired into this resolver.
