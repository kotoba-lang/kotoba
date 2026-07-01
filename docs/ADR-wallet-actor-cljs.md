# ADR: CLJS wallet actor and Ethereum library surface

- **Status**: Proposed / R0.168 pure core landed
- **Date**: 2026-06-27
- **Deciders**: 河崎純真
- **Context tags**: clojurescript, wallet, ethereum, evm, actor, swap, did, pkh, datom, safe Kotoba
- **Related**: `ADR-kotoba-wasm.md`, `ADR-browser-cid-query-vs-p2p.md`, `ADR-safe-capability-language.md`, `ADR-sealed-cold-tier.md`, `docs/gftd-office/d-did-identity-layer.md`, `crates/kotoba-evm`, `crates/kotoba-custody`

## Context

kotoba already has the right lower substrate for an Ethereum-based wallet:

- `kotoba-evm` executes EVM calls over Datom-projected state and exposes receipts/logs.
- `kotoba-crypto` and `kotoba-custody` provide key material handling and threshold custody primitives.
- Browser CLJS already exists as a first-class surface for verified CID reads and trustless writes.
- DID/CACAO already models subjects, delegated capabilities, and graph-scoped authorization.

The missing layer is a **ClojureScript wallet actor/library**: a MetaMask-like surface that can hold accounts, switch EVM networks, track balances, sign/send transactions, and quote/execute swaps while keeping state in kotoba datoms and all dangerous effects behind explicit host capabilities.

## Decision

Create a wallet subsystem named **`kotoba.wallet`**. It is a `.cljc` domain library with a CLJS browser adapter and a Pregel-style actor. Rust remains substrate only. Wallet policy, state, swap planning, approval safety, portfolio views, and event reducers live in Clojure/ClojureScript.

```
CLJS UI / dapp bridge
  kotoba.wallet.provider      EIP-1193-compatible request/event facade
  kotoba.wallet.ui            optional app shell state, not a protocol dependency

.cljc domain library
  kotoba.wallet.actor         command/event actor and Pregel reducer
  kotoba.wallet.account       DID, did:pkh, derivation metadata, session policy
  kotoba.wallet.network       EVM network registry and RPC routing
  kotoba.wallet.asset         native/ERC-20/ERC-721/ERC-1155 metadata
  kotoba.wallet.tx            transaction intent, simulation, signing envelope
  kotoba.wallet.swap          route quote, approval plan, execution plan
  kotoba.wallet.risk          spender, allowance, chain-id, slippage, phishing checks
  kotoba.wallet.store         datom schema + queries

Host capabilities
  :evm-rpc-fn                 eth_call, eth_getBalance, eth_getLogs, sendRawTransaction
  :sign-fn                    secp256k1 sign / passkey-gated key unwrap / hardware signer
  :quote-fn                   aggregator quotes, optional and replaceable
  :price-fn                   market prices, optional and cacheable
  :clock-fn                   host timestamp for quote observation, tx submission, and signatures
  :notify-fn                  host notifications, optional

Rust substrate
  kotoba-evm                  local simulation / receipt/log semantics
  kotoba-crypto/custody       sealed keys and recovery
  kotoba-datomic/query        immutable wallet facts and audit log
```

The actor does not own ambient network, clock, or signing power. It receives those as values. This keeps safe Kotoba confinement intact and lets the same `.cljc` code run in browser CLJS, JVM tests, SCI, or WASM.

## Actor model

The wallet actor is event-sourced. Commands validate policy and produce intents; effects are performed by the host; resulting observations are committed as datoms.

### Commands

```clojure
[:wallet/connect {:origin "https://app.example" :requested [:eth_accounts]}]
[:wallet/select-account {:account/id "..."}]
[:wallet/select-network {:chain/id 1}]
[:wallet/add-network {:chain/id 8453 :rpc/url "..." :native/symbol "ETH"}]
[:wallet/watch-asset {:chain/id 1 :asset/address "0x..." :asset/kind :erc20}]
[:wallet/prepare-transfer {:to "0x..." :asset :native :amount "10000000000000000"}]
[:wallet/prepare-contract-call {:to "0x..." :data "0x..." :value "0x0"}]
[:wallet/prepare-swap {:from-token "0x..." :to-token "0x..." :amount-in "..." :slippage-bps 50}]
[:wallet/approve-intent {:intent/id "..."}]
[:wallet/reject-intent {:intent/id "..." :reason "..."}]
[:wallet/revoke-approval {:token "0x..." :spender "0x..."}]
[:wallet/sync {:chain/id 1 :account/address "0x..."}]
```

### Events

```clojure
[:wallet/event :account/connected]
[:wallet/event :network/selected]
[:wallet/event :asset/balance-observed]
[:wallet/event :tx/intent-created]
[:wallet/event :tx/simulated]
[:wallet/event :tx/signed]
[:wallet/event :tx/submitted]
[:wallet/event :tx/confirmed]
[:wallet/event :swap/quoted]
[:wallet/event :risk/flagged]
```

The actor state is a pure projection from events and observed chain facts. UI state can cache projections, but the authoritative audit trail is datom-backed.

## Datom schema

Wallet state uses ordinary kotoba EAV facts. Sensitive key material is never stored as plaintext datoms.

```clojure
;; account
[a :wallet.account/id "acct:main"]
[a :wallet.account/did "did:key:z..."]
[a :wallet.account/pkh "did:pkh:eip155:1:0xabc..."]
[a :wallet.account/address "0xabc..."]
[a :wallet.account/label "Main"]
[a :wallet.account/custody :custody/passkey]
[a :wallet.account/created-at 1782560000000]

;; network
[n :wallet.network/chain-id 1]
[n :wallet.network/name "Ethereum Mainnet"]
[n :wallet.network/namespace "eip155"]
[n :wallet.network/native-symbol "ETH"]
[n :wallet.network/rpc-ref "rpc:mainnet-1"]       ;; secret URL stored by host, not graph
[n :wallet.network/explorer "https://etherscan.io"]
[n :wallet.network/status :network.status/enabled]

;; asset
[t :wallet.asset/chain n]
[t :wallet.asset/kind :asset.kind/erc20]
[t :wallet.asset/address "0xa0b8..."]
[t :wallet.asset/symbol "USDC"]
[t :wallet.asset/decimals 6]
[t :wallet.asset/source :asset.source/token-list]

;; observed balance
[b :wallet.balance/account a]
[b :wallet.balance/asset t]
[b :wallet.balance/block-number 23000000]
[b :wallet.balance/raw "123450000"]
[b :wallet.balance/observed-at 1782560000000]

;; observed allowance
[al :wallet.allowance/account a]
[al :wallet.allowance/chain-id 1]
[al :wallet.allowance/token "0xa0b8..."]
[al :wallet.allowance/spender "0xrouter..."]
[al :wallet.allowance/amount "1000000"]
[al :wallet.allowance/block-number 23000000]
[al :wallet.allowance/observed-at 1782560000000]

;; transaction intent and execution
[i :wallet.intent/id "intent:..."]
[i :wallet.intent/account a]
[i :wallet.intent/chain n]
[i :wallet.intent/kind :intent.kind/swap]
[i :wallet.intent/to "0xrouter..."]
[i :wallet.intent/value "0"]
[i :wallet.intent/data "0x..."]
[i :wallet.intent/spender "0xspender..."]          ;; approvals only
[i :wallet.intent/status :intent.status/pending-user]
[i :wallet.intent/origin "https://app.example"]
[i :wallet.intent/risk :risk.level/medium]
[i :wallet.intent/quote-id "quote:..."]             ;; swap intents only

[tx :wallet.tx/hash "0x..."]
[tx :wallet.tx/intent i]
[tx :wallet.tx/status :tx.status/submitted]
[tx :wallet.tx/nonce 42]
[tx :wallet.tx/submitted-at 1782560010000]

;; message / typed-data signature
[sig :wallet.signature/id "sig:..."]
[sig :wallet.signature/intent i]
[sig :wallet.signature/account a]
[sig :wallet.signature/chain-id 1]
[sig :wallet.signature/origin "https://app.example"]
[sig :wallet.signature/kind :intent.kind/typed-data-sign]
[sig :wallet.signature/payload-hash "typed-data-v4:..."]
[sig :wallet.signature/signature "0x..."]
[sig :wallet.signature/signed-at 1782560010000]
```

## Provider facade

The CLJS adapter exposes an EIP-1193-compatible provider for dapps:

```clojure
(wallet/request! env {:method "eth_requestAccounts" :params []})
(wallet/request! env {:method "wallet_switchEthereumChain"
                      :params [{:chainId "0x1"}]})
(wallet/request! env {:method "eth_sendTransaction"
                      :params [{:from "0xabc..." :to "0x..." :value "0x0"}]})
```

Supported P0 methods:

| Method | Behavior |
|---|---|
| `eth_accounts` / `eth_requestAccounts` | Return selected authorized accounts for origin. |
| `eth_chainId` | Return selected network. |
| `wallet_switchEthereumChain` | Select enabled chain after policy check. |
| `wallet_addEthereumChain` | Add a chain into the network registry, disabled until approved. |
| `wallet_watchAsset` | Add asset metadata after contract verification. |
| `eth_call` / `eth_estimateGas` | Route through `:evm-rpc-fn`; wallet facts are unchanged unless a later sync/observation command commits them. |
| `eth_sendTransaction` | Convert to intent, simulate, require user approval, sign, submit. |
| `wallet_revokeApproval` | Convert to bounded ERC-20 `approve(spender, 0)` intent, simulate, require user approval, sign, submit. |
| `personal_sign` / `eth_signTypedData_v4` | Sign typed payloads only after origin-bound approval. |

Raw private-key export is not a provider feature.

## Swap design

Swap is modeled as a two-phase plan:

1. **Quote**: call `:quote-fn` or local router logic and store `:swap.quote/*` facts.
2. **Execution plan**: produce one or more transaction intents: allowance change if needed, then router call.

```clojure
{:swap/from-token "0xa0b8..."
 :swap/to-token "0xc02a..."
 :swap/amount-in "1000000"
 :swap/slippage-bps 50
 :swap/routes [{:dex :uniswap-v3 :pool "0x..." :fee-bps 5}]
 :swap/min-amount-out "..."
 :swap/deadline-ms 1782560300000}
```

Safety requirements:

- Never create infinite approvals by default. Use exact approval or bounded approval unless the user explicitly changes policy.
- Simulate the final router calldata against the selected chain before presenting approval.
- Bind quote, chain id, token addresses, spender, amount, slippage, and deadline into the intent hash.
- Treat cross-chain bridge routes as P1, separate from same-chain swaps.
- Persist quote provenance: aggregator, router, block number, response hash, and expiry.

## Risk and policy

The actor must produce risk facts before any signature:

| Risk | Rule |
|---|---|
| Chain mismatch | `tx.chain-id` must equal selected chain and signer `did:pkh` namespace. |
| Unknown spender | ERC-20 approval spender must be in route provenance or user allowlist; revoke-to-zero intents are treated as exposure reduction. |
| Unlimited approval | Flag high unless per-origin policy permits it. |
| Blind signing | Flag high for opaque bytes; typed data must show domain, chain, verifying contract. |
| Slippage | Flag medium/high above policy threshold. |
| Contract call | Simulate and decode ABI when ABI is known; otherwise mark opaque. |
| Origin | Every dapp permission is scoped to `{origin account chain capabilities}`; provider effects are denied before execution when the target account or chain is outside policy. |

Policy is data:

```clojure
{:wallet.policy/origin "https://app.example"
 :wallet.policy/accounts ["acct:main"]
 :wallet.policy/chains [1 8453]
 :wallet.policy/caps #{:eth/accounts :eth/send-tx :eth/sign-typed-data}
 :wallet.policy/max-slippage-bps 100
 :wallet.policy/allow-unlimited-approval? false}
```

## Library API

Pure functions:

```clojure
(wallet.actor/step state command)         ;; => {:state ... :effects [...] :datoms [...]}
(wallet.tx/normalize-tx chain tx-map)     ;; => canonical tx intent
(wallet.tx/intent-hash intent)            ;; => content-addressed user approval target
(wallet.swap/plan state quote request)    ;; => approval + swap tx intents
(wallet.risk/assess state intent)         ;; => risk facts
(wallet.store/balances db account chain)  ;; => projection query
```

Effect runners:

```clojure
(wallet.runtime/run-effect! env effect)   ;; host boundary only
(wallet.provider/install! env js-window)  ;; CLJS dapp bridge
```

The pure layer is testable without RPC, signing, or browser APIs.

## Current implementation

R0 landed as pure `.cljc` wallet namespaces. The former
`crates/kotoba-wasm/web/cljs` browser package was retired during the Kotoba/CLJC
migration; browser ESM packaging is now host-adapter owned.

| Namespace | File | Landed surface |
|---|---|---|
| `kotoba.wallet.store` | `store.cljc` | wallet datom schema and account/network/asset/balance/allowance/quote/intent/signature/tx encoders, including approval spender facts |
| `kotoba.wallet.tx` | `tx.cljc` | canonical tx normalization and stable intent approval hash |
| `kotoba.wallet.risk` | `risk.cljc` | chain, `did:pkh`, origin policy, spender, unlimited approval, slippage, opaque-call checks |
| `kotoba.wallet.swap` | `swap.cljc` | same-chain swap plan with exact approval before router call |
| `kotoba.wallet.actor` | `actor.cljc` | pure command/event reducer, native/ERC20 transfer preparation, approval revoke/signature preparation, swap preparation, balance/allowance/tx/signature observation, and host-effect descriptions |
| `kotoba.wallet.provider` | `provider.cljc` | pure EIP-1193 request dispatcher with per-origin capability/chain authorization, provider and setState event derivation, and EIP-1193 error codes, `wallet_prepareTransfer`, `wallet_revokeApproval`, `personal_sign`, `eth_signTypedData_v4`, `wallet_quoteSwap`/`wallet_prepareSwap`, plus CLJS `request-js` and stateful `create-provider-js` ESM wrappers |
| `kotoba.wallet.runtime` | `runtime.cljc` | injected host-effect runner contract for quote/RPC/sign/sign-message/sync; sync materializes balances, allowances, and receipts into actor commands; plus CLJS ESM wrappers for run/apply |
| Historical browser bundle gate | retired | the removed shadow-cljs package exported `walletRequest`, `createWalletProvider`, `runWalletEffect`, and `applyWalletCommands`; equivalent JS packaging is now adapter-owned |
| Historical ESM smoke | retired | the removed Node/shadow smoke covered JS shape guards, provider events, host-effect conversion, chain/account normalization, sync, replay, and error data |
| `kotoba.wallet-test` | `wallet_test.clj` | bb-testable proof that the R0 invariants hold |

Historical verification for the retired browser package used a bb-loadable
`kotoba.wallet-test` runner. The path no longer exists in this repo; current
adapter repositories must provide their own JS/browser verification over the
pure wallet contract.

Covered R0 invariants:

- account/balance datoms do not contain seed/private-key/RPC URL material;
- balance and allowance observations require account/chain provenance, positive block and observed timestamps, decimal uint256 values, update projected state, and emit `:wallet.balance/*` / `:wallet.allowance/*` datoms;
- intent hash is stable and excludes the generated `:hash` field itself;
- native/ERC20 transfer preparation creates auditable intents with recipient/token/amount facts;
- ERC-20 approval revoke creates an auditable `approve(spender, 0)` intent with token/spender/amount facts and a simulation effect;
- chain mismatch, `did:pkh` mismatch, unknown spender, unlimited approval, and slippage policy become explicit risk facts;
- same-chain swap planning emits bounded ERC-20 approval before router execution;
- swap allowance comparison is CLJ/CLJS portable for uint256 decimal strings and does not depend on JVM-only bigint vars;
- actor/provider `prepare-swap` turns a quote into approval + router intents and simulation effects;
- provider event derivation is pure CLJC: `eth_requestAccounts` emits `accountsChanged`, command replay for unchanged authorized accounts is silent, and changed account authorization emits `accountsChanged`;
- setState replacement event derivation is pure CLJC: unchanged replacements are silent, selected-chain changes emit `chainChanged`, and authorized-account changes emit `accountsChanged`;
- provider and setState event derivation reject malformed selected-chain transitions with structured `-32602` invalid-selected-chain errors;
- provider/runtime `quote-swap` delegates quote lookup to injected `:quote-fn` without hard-coding an aggregator, preserving host-returned quote mismatch provenance for later risk checks;
- quote results are persisted as `:wallet.quote/*` datoms with provider, request hash, block number, router, spender, min amount out, and observation time;
- quote observations and prepare-swap plans reject quotes missing required provenance (`provider`, `router`, `spender`, `calldata`, `min-amount-out`, `deadline-ms`, `block-number`, plus observed request context) before intent or quote datoms are emitted;
- swap approval/router intents carry `:wallet.intent/quote-id`, so the approval hash and datom log link back to the quote provenance;
- swap router intents bind deadline, min amount out, slippage, and explicit host-supplied prepare time into the intent hash/datoms; expired quotes become high-risk `:risk/quote-expired` before signing, and fatal approval rejection leaves the pending intent with deadline/now, hash, and datom evidence.
- swap router intents also bind quote/request mismatch fields into the intent hash/datoms; mismatched quote chain/token/amount fields become high-risk `:risk/quote-request-mismatch`, and fatal approval rejection leaves the pending intent with mismatch fields, hash, and datom evidence.
- actor `:wallet/prepare-contract-call` creates a pending intent, simulation effect, and intent datoms without performing ambient I/O, and honors provider-materialized explicit `from` account and `chainId` fields instead of silently falling back to selected account/chain.
- intent ids are immutable audit identities; prepare commands cannot overwrite an existing intent id.
- provider `eth_accounts`/`eth_chainId` return immediate results from projected state;
- provider `wallet_addEthereumChain` validates chain id, chain name, native currency symbol, and non-empty HTTP(S) RPC URLs before network state mutation, provider `wallet_watchAsset` validates supported asset type, contract address, and ERC20 metadata before asset state mutation, and provider `wallet_addEthereumChain`/`wallet_switchEthereumChain`/`wallet_watchAsset` update projected state through actor events, and actor replay validates connect/add-network/select-network/watch-asset, prepare-contract-call/prepare-transfer/revoke-approval/prepare-signature, and approve/reject, and sync command payloads before datom or effect emission;
- provider `eth_call`/`eth_estimateGas` return host RPC effects, not ambient network calls;
- runtime `:evm-rpc/call` and `:evm-rpc/estimate-gas` effects invoke injected `:evm-rpc-fn` with method, chain, and params and return host results without committing wallet facts.
- provider `eth_call`/`eth_estimateGas` validate the first tx object, reject invalid RPC params with `-32602`, and enforce tx-object `chainId` and `from` against origin policy before host RPC effects are emitted.
- provider `eth_sendTransaction` creates a pending intent and simulation effect, not a raw submission.
- provider authorization, unsupported method, unknown-chain, and invalid-params failures carry codes `4100`, `4200`, `4902`, and `-32602`.
- provider validates request parameter shape and required fields before actor intent creation, so malformed dapp requests cannot produce nil-filled network, intent, or quote datoms.
- provider signature requests require an explicit, unambiguous address before actor intent creation: `personal_sign` must contain exactly one address-like param and `eth_signTypedData_v4` must use an address-like first param.
- provider switch/RPC/tx/transfer/revoke/swap effects are denied with EIP-1193 `4100` when the target chain is outside the origin policy.
- provider switch/RPC/tx/transfer/revoke/quote/swap/signing effects are denied with EIP-1193 `4902` when the target chain is allowed by policy but not registered in wallet networks.
- provider RPC/tx/transfer/revoke/quote/swap/signing effects are denied before host effects or intent creation when the target account id/address is not registered or when an explicit account id does not match the supplied address.
- provider tx/transfer/revoke/swap/signing effects are denied with EIP-1193 `4100` when the target account/address is outside the origin policy.
- provider quote/swap preparation resolves nested swap `request` chain/account fields before policy checks, so multi-network and multi-account swap requests cannot bypass origin policy.
- approving an intent emits a `:wallet/sign-and-submit` effect that composes injected `:sign-fn` and `:submit-raw-tx-fn`;
- runtime rejects host signer results that echo a different transaction intent hash or message payload hash than the approved intent.
- runtime rejects submitter results that echo a different signed raw transaction than the signer produced.
- runtime submit results and host tx observations must include a tx hash before tx facts are emitted.
- runtime sign-message results and host signature observations must include signature bytes before signature facts are emitted.
- approval/rejection is accepted only for existing `:intent.status/pending-user` intents; missing or terminal intents cannot emit signing effects.
- high-risk intents require explicit `:risk-acknowledged? true` before approval emits signing effects; rejection remains available without risk acknowledgement.
- fatal swap risks such as expired quotes and quote/request mismatches cannot be approved even with high-risk acknowledgement.
- approval/rejection decisions emit `:wallet.intent/status` datoms; high-risk acknowledgement and rejection reason are retained as intent facts for audit replay.
- approval/rejection decision metadata is retained in projected actor state as well as datoms.
- `personal_sign` and `eth_signTypedData_v4` create origin-bound approval intents; approval emits `:wallet/sign-message`, and host signatures become `:wallet.signature/*` datoms while audit hash/datoms retain payload hashes and redacted previews rather than full payload bodies; canonical intent hashes bind payload hashes/previews and exclude raw payload bodies;
- signed/submitted/confirmed tx observations become `:wallet.tx/*` datoms and update intent status.
- signature and tx host observations emit matching `:wallet.intent/status` datoms for signed/submitted/confirmed transitions, so audit replay can reconstruct intent lifecycle without relying only on projected state.
- host tx/signature observations must reference an existing intent in the expected lifecycle state: approved for signed/submitted/signature observations, submitted for confirmation observations.
- runtime `:wallet/sync` maps host-returned balances, allowances, and receipts into `:wallet/observe-balance`, `:wallet/observe-allowance`, and `:wallet/tx-confirmed` commands while preserving explicit host commands before materialized observations.
- runtime command replay rejects invalid batches, malformed JS command tuple shapes, and malformed JS command batches with structured actor errors before returning partial replay state to callers;
- JS-facing runtime wrapper errors expose structured `data` for missing host capabilities, host result mismatches, missing required host fields, unsupported wallet effects, and invalid command replay.
- Historical shadow-cljs and Node wallet gates verified browser/ESM packaging for
  the retired prototype. Current verification in this repo covers the pure
  wallet actor contracts; browser bundle and EIP-1193 JS wrapper gates belong to
  the host adapter that packages them.
- `walletRequest` and `createWalletProvider` accept natural JS object state with camelCase selected-account fields, string-keyed account/network/policy maps, EIP-1193 method-name caps, decimal or hex string chain ids, kebab `chain-id` request payloads, origin policy chain lists, address-form selected accounts, address-form policy accounts, and address-form request accountId fields, explicit from/address account fields, and request chainId fields, normalizing it into actor state before dispatch; malformed selected-chain state, selected-chain fallback use, and selected-account fallback use are rejected with structured provider error codes/data; direct `walletRequest` failures expose structured provider error codes/data; provider state input also round-trips JS-visible balance/allowance composite keys before swap planning; JS-visible provider effects preserve namespaced effect strings such as `evm-rpc/call`.
- `runWalletEffect` accepts JS effect objects with string effect names and camelCase fields, adapts injected host functions, preserves namespaced wallet command strings in JS output, and `applyWalletCommands` normalizes JS state/commands, including decimal or hex string chain ids in effect payloads, commands, host results, policy chain lists, address-form selected accounts, and address-form policy accounts, before actor replay while preserving structured replay errors and balance/allowance composite-key state round trips.
- ESM smoke covers RPC, message signing, transaction sign+submit, quote-swap, wallet sync, invalid params, provider namespaced effect strings, direct walletRequest structured provider errors, host-effect full-result echo normalization, host-effect throw/reject structured error conversion, host-effect cause data preservation and null host state/command rejection and JS state object guard and runtime JS state object guard and runtime JS effect object guard and runtime JS env object guard and runtime capability function guard and provider constructor env guard and provider handleEffects function guard and provider origin string guard and provider listener function guard and provider event string guard and provider removeListener event guard and provider request object guard and provider request method guard and provider request params guard and direct walletRequest shape guard and provider missing origin guard and provider blank origin guard and direct walletRequest origin guard and provider blank event guard and provider removeListener listener guard and provider setState method boundary and JS policy origin guard and JS accounts object guard and JS networks object guard and JS policies object guard and JS record map object guard and JS composite map object guard and runtime JS accounts object guard and runtime JS networks object guard and runtime JS policies object guard and runtime JS record map object guard and runtime JS composite map object guard and runtime host result object guard and runtime optional capability function guard with throwing/rejecting tx non-commit, method/origin provenance, JS error message preservation, and structured code, kebab chain-id request normalization, runtime chain-id payload normalization, address accountId request normalization, explicit from/address account and chainId intent materialization, nested swap request account/chain materialization, signature address account materialization, async runtime host effects, async runtime host success coverage, async provider host success coverage, async provider result-only success coverage, provider host command replay, provider host command replay events, provider host command replay listener isolation, provider host command replay event dedupe, pure provider event derivation coverage, pure setState event derivation coverage, pure malformed event selected-chain coverage, pure command replay partial non-commit coverage, runtime sync explicit command ordering coverage, runtime quote mismatch provenance coverage, fatal quote mismatch state evidence coverage, fatal expired quote state evidence coverage, signature payload privacy coverage, intent hash payload digest binding coverage, signature observation payload-hash replay coverage, tx-signed signed-raw replay coverage, tx-confirmed block-number replay coverage, tx-confirmed block-number validation coverage, tx-confirmed gas-used validation coverage, tx-submitted submitted-at validation coverage, tx hex-prefix replay coverage, signature hex-prefix replay coverage, runtime host hex-prefix validation coverage, runtime host timestamp validation coverage, runtime quote timestamp validation coverage, balance/allowance observation validation coverage, tx-confirmed confirmed-at validation coverage, actor network/asset command validation coverage, actor connect command validation coverage, actor intent preparation command validation coverage, actor signature preparation command validation coverage, actor state transition command validation coverage, actor sync command validation coverage, JS command tuple validation coverage, JS command batch validation coverage, provider host-error-data coverage, provider null host result guard coverage, JS state object guard coverage, runtime JS state object guard coverage, runtime JS effect object guard coverage, runtime JS env object guard coverage, runtime capability function guard coverage, provider constructor env guard coverage, provider handleEffects function guard coverage, provider origin string guard coverage, provider listener function guard coverage, provider event string guard coverage, provider removeListener event guard coverage, provider request object guard coverage, provider request method guard coverage, provider request params guard coverage, direct walletRequest shape guard coverage, provider missing origin guard coverage, provider blank origin guard coverage, direct walletRequest origin guard coverage, provider blank event guard coverage, provider removeListener listener guard coverage, provider setState method boundary coverage, JS policy origin guard coverage, JS accounts object guard coverage, JS networks object guard coverage, JS policies object guard coverage, JS record map object guard coverage, JS composite map object guard coverage, runtime JS accounts object guard coverage, runtime JS networks object guard coverage, runtime JS policies object guard coverage, runtime JS record map object guard coverage, runtime JS composite map object guard coverage, runtime host result object guard coverage, runtime optional capability function guard coverage, malformed provider host command replay non-commit, rejecting host-effect non-commit, throwing host-effect non-commit, host-effect tx error provenance, host-effect tx JS error message, host-effect tx structured code, async malformed host state non-commit, malformed selected-chain state/fallback conversion, malformed selected-account fallback conversion, malformed host-returned provider state rejection before local state commit including Promise-returned malformed state, malformed setState replacement rejection before local state commit, method-name cap normalization, hex chain id, policy-chain, address selected-account, and address policy-account state normalization through walletRequest/provider/setState/runtime replay, runtime async host result/rejection handling plus async sign/submit, quote, and sync success, provider async host full-result success, provider async host result-only success, runtime missing-capability, host-mismatch, and command replay structured error conversion, balance/allowance composite-key state round trips through `applyWalletCommands` and provider swap planning, effect-free provider requests skipping host effect handlers while retaining provider events, setState chainChanged/accountsChanged replacement events with listener exception isolation, provider accountsChanged/chainChanged/removeListener behavior including repeated/unknown listener removal, listener exception isolation, add-chain and watch-asset payload validation with state non-mutation on rejection, host-effect result-only responses, including Promise-returning result-only responses, without provider state corruption, registered-chain/account provider errors, and command replay across the JS host boundary.
- `createWalletProvider` creates a stateful EIP-1193-shaped object with `request`, `on`, `removeListener`, `getState`, and `setState`; it keeps wallet state local, derives provider events before committing provider/host state changes, emits `chainChanged`/`accountsChanged` for provider requests and host state replacement, converts malformed `setState` replacement failures to structured JS provider errors before committing state, honors `removeListener` as an idempotent cleanup path, isolates listener exceptions from provider requests and state replacement, delegates non-empty effect execution to injected host code, skips host effect handlers for effect-free provider results, re-normalizes host-returned full result maps, converts host effect throw/reject failures to structured JS provider errors, and preserves local actor state when host effect handlers return only a result override.

## Implementation phases

### P0: Read-only wallet and provider

- Account/network/asset/balance datom schema: **R0.1 landed**.
- Balance sync projection: **R0.11 landed for host sync materialization into observed facts**; RPC polling implementation remains host-owned.
- Pure provider dispatcher for `eth_accounts`, `eth_chainId`, `wallet_switchEthereumChain`, `wallet_addEthereumChain`, `wallet_watchAsset`, `eth_call`, `eth_estimateGas`, `eth_sendTransaction`: **R0.1 landed**.
- `:evm-rpc-fn` host injection: represented as `:evm-rpc/*` effects; runtime runner **R0.20 landed** for `eth_call` and `eth_estimateGas`.
- bb tests for pure actor projections: **R0 landed**.
- Browser/CLJS ESM export wrappers and export map: **R0.3 landed historically**;
  current browser packaging is host-adapter owned.
- Stateful EIP-1193 provider object wrapper and browser ESM gates landed in the
  retired prototype. Adapter-owned browser packaging must re-establish those JS
  gates against the current pure wallet actor contracts.
- EIP-1193 provider error codes: **R0.9 landed** for unauthorized, unsupported method, and unknown chain failures.
- Provider invalid params boundary: **R0.32 landed** with `-32602` errors for malformed or missing dapp request params before intent creation; strict signature address params **R0.43 landed**; add-chain payload validation **R0.54 landed** for chain id, chain name, native currency symbol, and HTTP(S) RPC URLs before network state mutation.
- Per-origin provider chain authorization: **R0.12 landed** for switch, RPC, tx, transfer, revoke, quote, and swap preparation paths; nested swap request chain guards **R0.19 landed**; RPC tx-object `chainId` guard **R0.44 landed**; registered-chain guard **R0.45 landed**.
- Per-origin provider account authorization: **R0.14 landed** for tx, transfer, revoke, swap, message-sign, and typed-data-sign preparation paths; nested swap request account guards **R0.19 landed**; RPC tx-object `from` guard **R0.44 landed**; registered-account and account-id/address consistency guard **R0.46 landed**.
- `personal_sign` / `eth_signTypedData_v4`: **R0.13 landed** as origin-bound signature intents plus injected `:sign-message-fn` runtime contract.

### P1: Transaction intents

- `eth_sendTransaction` to intent conversion: **R0.1 landed for canonical tx maps and provider request**.
- Gas estimate, simulation, risk facts, user approval lifecycle: risk facts + simulation effect **R0 landed**; RPC host effect contract **R0.1 landed**.
- Approval lifecycle guard: **R0.15 landed** so only existing pending-user intents can be approved/rejected; high-risk approval acknowledgement guard **R0.22 landed**; approval/rejection decision datoms **R0.23 landed**; decision metadata projection **R0.31 landed**.
- Intent identity guard: **R0.16 landed** so prepare paths cannot overwrite existing intent ids, including multi-intent swap plans.
- Host observation lifecycle guard: **R0.17 landed** so tx/signature observations cannot create or advance missing/wrong-state intents; observation-driven intent status datoms **R0.24 landed**; tx hash required guard **R0.27 landed**; signature bytes required guard **R0.28 landed**.
- Swap quote deadline guard: **R0.18 landed** so router intents bind deadline/min-out/slippage/prepare-time into the audit hash/datoms and expired quotes are high risk before signing.
- Fatal swap approval guard: **R0.30 landed** so expired quotes and quote/request mismatches remain reject-only and cannot be signed through high-risk acknowledgement.
- Native/ERC20 transfer preparation: **R0.8 landed** as `:wallet/prepare-transfer` and provider `wallet_prepareTransfer`.
- ERC-20 approval revoke: **R0.10 landed** as `:wallet/revoke-approval` and provider `wallet_revokeApproval`.
- `:sign-fn` host injection and `eth_sendRawTransaction` submission: **R0.2 landed as injected `:sign-fn` + `:submit-raw-tx-fn` runtime contract**; signer intent-hash echo guard **R0.25 landed**; submit signed-raw echo guard **R0.26 landed**; submit tx-hash required guard **R0.27 landed**.
- `:sign-message-fn` host injection and signature datoms: **R0.13 landed** for message and typed-data signatures; payload-hash echo guard **R0.25 landed**; signature bytes required guard **R0.28 landed**.
- Receipt/log sync into datoms: tx submitted/confirmed projection **R0.2 landed**; host-returned receipt materialization via `:wallet/sync` **R0.11 landed**; JS ESM sync materialization smoke **R0.37 landed**; full log polling remains host-owned.

### P2: Same-chain swaps

- Quote host capability: **R0.6 landed** as provider `wallet_quoteSwap` + runtime `:quote-fn`; actor accepts host-provided quote in `:wallet/prepare-swap`.
- Quote request chain/account propagation: **R0.19 landed** so `wallet_quoteSwap` effects carry explicit target chain/account provenance instead of silently using only selected chain.
- Quote provenance datoms: **R0.7 landed** as `:wallet.quote/*` facts emitted by `:wallet/quote-observed`; quote required provenance guard **R0.29 landed** for runtime quote results, direct quote observations, and prepare-swap plans.
- Quote-to-intent audit link: **R0.9 landed** as `:wallet.intent/quote-id` carried into swap intent hashes and datoms.
- Quote/request mismatch guard: **R0.21 landed** so router intents bind mismatched quote fields into hash/datoms and flag high risk before signing.
- ERC-20 allowance observation: **R0.11 landed** as projected state, datoms, and host sync materialization; RPC polling implementation remains host-owned.
- Bounded approval + router execution plan: **R0.5 landed through actor/provider prepare-swap**; CLJ/CLJS portable uint256 allowance comparison **R0.33 landed**.
- Swap provenance and slippage/deadline enforcement: quote provenance link **R0.9 landed**; pure deadline risk guard **R0.18 landed** using explicit host-supplied prepare time. On-chain router deadline execution remains host/router-owned.

### P3: Advanced custody and recovery

- Threshold recovery using `kotoba-custody`.
- Hardware signer/passkey adapters.
- Per-origin session keys with CACAO attenuation.

### P4: Multi-device and bridge routes

- Encrypted wallet graph replication.
- Cross-chain bridge intents as a separate actor (`kotoba.bridge`) so same-chain swap safety stays simple.

## Non-goals

- No centralized order book.
- No raw seed phrase export in the provider API.
- No bridge execution in the same actor as same-chain swap.
- No Rust rewrite of wallet policy logic.
- No dependency on one quote aggregator; `:quote-fn` is replaceable.

## Consequences

- MetaMask-like behavior becomes a small CLJS facade over a durable kotoba actor, not browser-local mutable state.
- Wallet activity becomes queryable and auditable with the rest of the kotoba graph.
- The dangerous surfaces are explicit: RPC, signing, quote services, prices, and clock.
- Existing `kotoba-evm` remains useful for local simulation and log semantics without forcing the wallet library into Rust.
