# chain-observer

Transport-neutral, read-only chain observation contracts for Clojure and
ClojureScript.

The library preserves each network's own finality model:

- EVM: `latest`, `safe`, and `finalized`;
- Solana: `confirmed` and `finalized` commitments;
- Cosmos/CometBFT: latest committed block;
- Substrate: best and finalized heads;
- Lightning/LND: Bitcoin-chain sync and graph sync as separate facts.

Adapters produce finite allowlisted request plans. An injected request function
owns HTTP, WebSocket, TLS, credentials, retries, and provider selection. The
library owns response normalization, expected-network checks, capability
vocabulary, readiness, and reorganization evidence.

```clojure
(require '[chain.observer.evm :as evm]
         '[chain.observer.protocol :as observer])

(def backend
  (observer/observer
   (evm/adapter {:expected-chain-id 1
                 :expected-genesis-hash "0x..."})
   my-read-only-json-rpc-call))

(observer/snapshot backend)
```

No adapter constructs, signs, submits, or broadcasts a transaction. Lightning
transport must use a TLS-verified endpoint and a least-privilege read-only
macaroon. Remote RPC results have `:remote-rpc` trust and are observations, not
locally verified consensus.

## Verify

```bash
kbb -M:test
kbb -M:lint
kbb -M:coverage
```
