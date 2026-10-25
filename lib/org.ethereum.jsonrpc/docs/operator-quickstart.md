# Operator quickstart

Five steps from an empty directory to a verified read-only Ethereum JSON-RPC
client. Each step prints something you can check, and each one below was run
from fresh clones on 2026-09-26.

Requirements: `git`, `kbb` (the `kotoba-lang/org-babashka-nbb` engine), and
outbound HTTPS for step 4 only.

## 1. Clone the repo and its three source dependencies side by side

```bash
mkdir eth && cd eth
for r in org-ethereum-jsonrpc kotobase kotobase-protocols text; do
  git clone https://github.com/kotoba-lang/$r.git
done
```

## 2. Check the dependencies out at the SHAs `deps.edn` pins

```bash
git -C kotobase           checkout bbf57df9dde5c1869182012860129a598382e088
git -C kotobase-protocols checkout 3f65e67896e7d54c2bba1a7514ceeb0f614b9f54
git -C text               checkout 73bdb13ae7a3d004b44bca08be03a3191157a38f
cd org-ethereum-jsonrpc
CP="src:test:../kotobase/src:../kotobase-protocols/src:../text/src"
```

The SHAs come from `deps.edn`. When `deps.edn` changes, copy them again from
there rather than from this page.

`../text` is required: `kotobase.ethereum.rpc` requires `kotoba.lang.text`.
Without it, every command below stops with
`Could not find namespace: kotoba.lang.text`.

## 3. Run the deterministic suite (no network)

```bash
kbb --backend sci --classpath "$CP" bin/run_tests.cljk
```

Expected ending, exit 0:

```
Ran 34 tests containing 139 assertions.
0 failures, 0 errors.
```

A failing assertion sets exit 1 (`bin/run_tests.cljk` sets
`process.exitCode` on an unsuccessful run).

## 4. Round-trip against a real public node

```bash
kbb --backend sci --classpath "$CP" test/kotobase/ethereum/live_smoke_demo.cljk
```

This calls `https://ethereum-sepolia-rpc.publicnode.com`, a free Sepolia
testnet endpoint that needs no API key. Expected output, exit 0 (block
numbers, hashes, and balances will differ on each run):

```
PASS - eth_chainId -> 11155111
PASS - eth_blockNumber -> <n>
PASS - eth_getBlockByNumber(latest) -> #<n> hash=0x… miner=0x…
PASS - eth_getBlockByHash round-trips to the same block #<n>
PASS - eth_getBalance(miner) -> <wei> wei
RESULT: all live calls round-tripped
```

CI does not run this step because it depends on the network.

## 5. Confirm the read-only boundary refuses a write method

```bash
kbb --backend sci --classpath "$CP" -e '
  (require (quote [kotobase.ethereum.rpc :as rpc]))
  (prn (rpc/build-request "eth_chainId" [] 1))
  (prn (try (rpc/build-request "eth_sendTransaction" [{}] 1)
            (catch :default e [:refused (:type (ex-data e))])))'
```

Expected:

```
{"jsonrpc" "2.0", "method" "eth_chainId", "params" [], "id" 1}
[:refused :kotobase.ethereum.rpc/disallowed-method]
```

The whitelisted method builds a request, and the write method is refused
with a named reason. The whitelist is permanent, not a phase limit. See the
README section "Permanent safety boundary".

## Pointing it at your own node

`kotobase.ethereum.client/create-client` takes `:endpoint` from the caller
(see README "Usage"). No endpoint and no credential is hardcoded. Supply
your own provider URL in the deploy environment, and do not commit a URL
that contains an API key.
