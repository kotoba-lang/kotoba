# kotoba browser read-plane — ClojureScript

ClojureScript glue for the in-browser kotoba node. Implements
**docs/ADR-browser-cid-query-vs-p2p.md**: a browser queries a *pinned* graph with
**zero peer connection**, because query is content-addressed.

```
resolve+verify signed head   →   sync covering index roots
   (kotoba.ipns, gateway-untrusted)       (datomic.sync)
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
        CID-verified block pull (block.get)  →  hydrateFromProlly  →  datomicQ
                       kotoba.node — all in-browser, no libp2p / WebRTC
```

## Namespaces

| ns             | what                                                                    |
|----------------|-------------------------------------------------------------------------|
| `kotoba.ipns`  | `resolve-head` / `verify-record` — member-signed IPNS head, verified in-wasm (`KotobaNode.verifyIpnsRecord`). Whoever serves the record is untrusted. |
| `kotoba.idb`   | IndexedDB persistence (DB `kotoba-node` v2): `snapshots` + `rawblocks` stores. |
| `kotoba.blocks`| CID-verified, IndexedDB-cached block sync: `block-get`, `hydrate-via-blocks`, `hydrate-from-idb-blocks`. |
| `kotoba.node`  | `hydrate-and-query!` (works today, head via `datomic.sync`), `hydrate-and-query-verified!` (fully trustless head), plus `hydrate!` / `query` / `sync-index-roots`. |
| `kotoba.write` | `publish!` — trustless write: `block.put` push + `ipns.publish` (member-signed head advance). Sovereign/DID-scoped graphs only; shared graphs use CACAO `datomic.transact`. |
| `kotoba.wallet.*` | MetaMask-like wallet actor/provider core: accounts, networks, assets, balances, tx intents, risk checks, same-chain quote/swap planning, EIP-1193 wrapper, and datom audit trail. |

Trust lives in the CID (`ingestBlock` re-derives `sha2-256(dag-cbor)` and rejects
mismatches) and, for the mutable head, in the Ed25519 signature — never in the
transport. That is why no P2P is needed for read.

## Build

```sh
npm install            # once — pulls shadow-cljs
npm run build          # release → ../cljs-out/kotoba-node.js (ESM)
npm run watch          # dev, hot-reload
npm run test:wallet:node # require Node 22+
npm run test:wallet    # pure .cljc wallet actor/provider/runtime tests
npm run test:wallet:edn # ADR status/artifact + shadow-cljs export consistency
npm run test:wallet:esm # Node smoke for wallet ESM exports/provider wrapper
npm run test:wallet:all # Node + pure + ADR/package-lock/CI/export + browser ESM smoke
```

Output is `../cljs-out/kotoba-node.js`, importable as ESM.

## Use from the Service Worker (kotoba-sw.js)

```js
import { hydrateAndQuery } from "./cljs-out/kotoba-node.js";

// answer a datomic.q POST entirely in-browser:
const resultJson = await hydrateAndQuery(
  node, GRAPH, req.query_edn, req.inputs_edn, { remote: REMOTE });
```

`hydrate-and-query-verified!` additionally verifies the signed head first, via
`GET /xrpc/com.etzhayyim.apps.kotoba.ipns.head?graph=<cid>` (now implemented —
`xrpc::ipns_head`, lexicon `ipns/head.json`).

## Status

- `npm run test:wallet` passes the pure wallet actor/provider/runtime test suite.
- `npm run test:wallet:all` runs the wallet maturity gate: pure tests,
  Node 22+ runtime alignment, ADR document/registry/note status sync, artifact
  consistency, package-lock metadata, CI wallet job shape, shadow export
  consistency, browser ESM compile, and generated ESM smoke.
- `.github/workflows/ci.yml` runs the same wallet maturity gate in CI.
- `npx shadow-cljs compile web` completes the browser ESM bundle with 0 warnings
  and includes the wallet ESM exports.
- `npm run test:wallet:esm` imports the generated ESM bundle and verifies the
  wallet JS exports, JS object state normalization, provider request path,
  provider events, add-chain validation, host-effect result fallback, provider
  error conversion, direct walletRequest error conversion, host-effect error conversion, host-effect cause data preservation, null host state/command rejection, JS state object guard, runtime JS state object guard, runtime JS effect object guard, runtime JS env object guard, runtime capability function guard, provider constructor env guard, provider handleEffects function guard, provider origin string guard, provider listener function guard, provider event string guard, provider removeListener event guard, provider request object guard, provider request method guard, provider request params guard, direct walletRequest shape guard, provider missing origin guard, provider blank origin guard, direct walletRequest origin guard, provider blank event guard, provider removeListener listener guard, provider setState method boundary, JS policy origin guard, JS accounts object guard, JS networks object guard, JS policies object guard, JS record map object guard, JS composite map object guard, runtime JS accounts object guard, runtime JS networks object guard, runtime JS policies object guard, runtime JS record map object guard, runtime JS composite map object guard, runtime host result object guard, runtime optional capability function guard, kebab chain-id request normalization, runtime chain-id payload normalization, address accountId request normalization, explicit from/address account and chainId intent materialization, nested swap request account/chain materialization, signature address account materialization, async runtime host effects, async runtime host success coverage, async provider host success coverage, async provider result-only success coverage, provider host command replay, provider host command replay events, provider host command replay listener isolation, provider host command replay event dedupe, pure provider event derivation coverage, pure setState event derivation coverage, pure malformed event selected-chain coverage, pure command replay partial non-commit coverage, runtime sync explicit command ordering coverage, runtime quote mismatch provenance coverage, fatal quote mismatch state evidence coverage, fatal expired quote state evidence coverage, signature payload privacy coverage, intent hash payload digest binding coverage, signature observation payload-hash replay coverage, tx-signed signed-raw replay coverage, tx-confirmed block-number replay coverage, tx-confirmed block-number validation coverage, tx-confirmed gas-used validation coverage, tx-submitted submitted-at validation coverage, tx hex-prefix replay coverage, signature hex-prefix replay coverage, runtime host hex-prefix validation coverage, runtime host timestamp validation coverage, runtime quote timestamp validation coverage, balance/allowance observation validation coverage, tx-confirmed confirmed-at validation coverage, actor network/asset command validation coverage, actor connect command validation coverage, actor intent preparation command validation coverage, actor signature preparation command validation coverage, actor state transition command validation coverage, actor sync command validation coverage, JS command tuple validation coverage, JS command batch validation coverage, provider host-error-data coverage, provider null host result guard coverage, JS state object guard coverage, runtime JS state object guard coverage, runtime JS effect object guard coverage, runtime JS env object guard coverage, runtime capability function guard coverage, provider constructor env guard coverage, provider handleEffects function guard coverage, provider origin string guard coverage, provider listener function guard coverage, provider event string guard coverage, provider removeListener event guard coverage, provider request object guard coverage, provider request method guard coverage, provider request params guard coverage, direct walletRequest shape guard coverage, provider missing origin guard coverage, provider blank origin guard coverage, direct walletRequest origin guard coverage, provider blank event guard coverage, provider removeListener listener guard coverage, provider setState method boundary coverage, JS policy origin guard coverage, JS accounts object guard coverage, JS networks object guard coverage, JS policies object guard coverage, JS record map object guard coverage, JS composite map object guard coverage, runtime JS accounts object guard coverage, runtime JS networks object guard coverage, runtime JS policies object guard coverage, runtime JS record map object guard coverage, runtime JS composite map object guard coverage, runtime host result object guard coverage, runtime optional capability function guard coverage, malformed provider host command replay non-commit, malformed selected-chain state/fallback conversion, malformed selected-account fallback conversion, malformed host state non-commit, rejecting host-effect non-commit, throwing host-effect non-commit, host-effect tx error provenance, host-effect tx JS error message, host-effect tx structured code, async malformed host state non-commit, malformed setState non-commit, add-asset validation,
  effect-free provider request handling, setState provider events, runtime
  effect error conversion, command replay error conversion, method-name cap normalization, hex chain id state normalization including policy chains, selected/account policy address normalization, and composite-key
  state round-trip wrappers.
- Read plane (`hydrate-and-query!`) is exercisable today against any
  `kotoba-server` that serves `datomic.sync` + `block.get` (Public graphs).
- `hydrate-and-query-verified!` is now fully trustless: signed `ipns.head`
  (`xrpc::ipns_head`) → `commitIndexRoots` derives the EAVT root from the verified
  head → CID-verified block sync. No `datomic.sync` trust on that path.
- `kotoba.write/publish!` completes the symmetric, signature-authorized write path
  (`block.put` + `ipns.publish`) for sovereign graphs.
- `kotoba.wallet.*` R0.168 is Node 22+-guarded, pure-test, ADR/package-lock/CI/export-consistency, README-checked, browser-bundle, ESM-smoke, and CI-gated: provider methods produce actor
  events/effects, tx lifecycle and same-chain quote/swap provenance become datoms,
  swap intents link back to quotes through `:wallet.intent/quote-id`, router
  intents bind deadline/min-out/slippage/prepare-time into hash/datoms and mark
  expired quotes high risk before signing, quote observations and prepare-swap
  plans reject missing quote provenance before emitting quote/intent datoms,
  quote/request mismatches are bound
  into router intent hash/datoms and flagged high risk, provider
  errors carry EIP-1193/JSON-RPC codes including invalid params `-32602`,
  malformed dapp params, invalid add-chain payloads, invalid watch-asset payloads, invalid RPC tx params, and ambiguous signature address params are rejected before actor intent creation, network/asset state mutation, or host RPC effects, per-origin chain/account policy is enforced
  before provider effects including registered-chain, registered-account, account-id/address consistency, and nested swap request chain/account fields,
  JS-facing wallet exports accept natural object state and normalize string-keyed
  account/network/policy maps before dispatch, direct walletRequest failures expose structured provider errors,
  runtime ESM wrappers normalize string effect names, camelCase fields, host
  function results, structured runtime errors, composite-key state round trips, and command replay state/errors, ESM smoke covers RPC, message signing,
  tx sign+submit, quote-swap, wallet sync, invalid params, namespaced provider
  effect strings, host-effect full-result re-normalization,
  host-effect throw/reject structured error conversion, host-effect cause data preservation and null host state/command rejection and JS state object guard and runtime JS state object guard and runtime JS effect object guard and runtime JS env object guard and runtime capability function guard and provider constructor env guard and provider handleEffects function guard and provider origin string guard and provider listener function guard and provider event string guard and provider removeListener event guard and provider request object guard and provider request method guard and provider request params guard and direct walletRequest shape guard and provider missing origin guard and provider blank origin guard and direct walletRequest origin guard and provider blank event guard and provider removeListener listener guard and provider setState method boundary and JS policy origin guard and JS accounts object guard and JS networks object guard and JS policies object guard and JS record map object guard and JS composite map object guard and runtime JS accounts object guard and runtime JS networks object guard and runtime JS policies object guard and runtime JS record map object guard and runtime JS composite map object guard and runtime host result object guard and runtime optional capability function guard with throwing/rejecting tx non-commit, method/origin provenance, JS error message preservation, and structured code,
  kebab chain-id request normalization, runtime chain-id payload normalization, malformed selected-chain state/fallback conversion, malformed selected-account fallback conversion, malformed host-returned provider state rejection before local state commit including Promise-returned malformed state,
  EIP-1193 method-name caps normalize to provider capability keywords, hex string chain ids in JS provider/runtime state normalization including origin policy chains, address-form selected account, policy accounts, and request accountId fields normalized to account ids, and explicit from/address account plus chainId fields materialized into actor intents including nested swap requests, malformed setState replacement rejects with structured provider errors before local state commit,
  effect-free provider requests skipping host effect handlers,
  setState chainChanged/accountsChanged replacement events,
  accountsChanged/chainChanged/removeListener provider events with idempotent
  listener cleanup, listener exception isolation, add-chain and watch-asset validation with state non-mutation on rejection,
  host-effect result-only responses, including Promise-returning result-only responses, without provider state corruption,
  registered-chain/account provider errors, and command replay,
  runtime async host result/rejection handling plus async sign/submit, quote, and sync success, provider async host full-result success, provider async host result-only success, runtime missing-capability, host-mismatch, and command replay errors expose structured JS data,
  JS balance/allowance composite keys round-trip through `applyWalletCommands`
  and provider swap planning,
  swap allowance checks use CLJ/CLJS-portable uint256 decimal comparison,
  native/ERC20 transfers and ERC20 approval revokes
  become auditable intents, intent ids cannot be overwritten, only pending-user
  intents can be approved/rejected, high-risk intents require explicit risk
  acknowledgement before approval emits signing effects, fatal swap risks such as
  expired quotes and quote/request mismatches cannot be approved, approval/rejection
  decisions emit status/ack/reason datoms and retain the same metadata in projected
  state, host tx/signature observations must match
  valid lifecycle states, include tx hashes, and emit intent status datoms for lifecycle replay,
  signer results are checked against approved intent/message hashes, submitter
  raw echoes are checked against signer output, signature observations require
  signature bytes,
  `personal_sign`/typed-data signatures become auditable
  signature facts, host sync materializes balances/allowances/receipts into
  datoms, runtime RPC effects call injected `:evm-rpc-fn` for `eth_call` and
  `eth_estimateGas`, and host capabilities remain injected (`:evm-rpc-fn`, `:quote-fn`,
  `:sign-fn`, `:sign-message-fn`, `:submit-raw-tx-fn`, `:sync-fn`).
- The original `kotoba-blocks.js` / `kotoba-idb.js` are superseded by
  `kotoba.blocks` / `kotoba.idb` (the JS files remain until `kotoba-sw.js`, itself
  still JS, is migrated to import the cljs `cljs-out/kotoba-node.js`).
