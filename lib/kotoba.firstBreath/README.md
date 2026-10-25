# first-breath — proof-of-life cell for the etzhayyim substrate

The smallest LangGraph cell that demonstrates the etzhayyim artificial-organism substrate end-to-end:

```
heartbeat tick
   ↓
mutate cell state (counter++ + timestamp)
   ↓
serialize state → "MST root" (sha256 of the state CBOR/JSON)
   ↓
anchor to EtzhayyimAnchor on local anvil
   ↓
verify via EtzhayyimAnchor.anchors(rootHash) read
   ↓
next heartbeat
```

This is the **respiration** of an organism: a periodic, self-anchoring state evolution that any third party can verify against on-chain proof.

## Status

v0.0.0 scaffold. Local-only (anvil). Runs once per invocation (cron- or systemd-driven loop in production).

## Layout

```
first-breath/
├── README.md
├── bb.edn                  # babashka deps: eth-crypto-clj (the cljc signer)
├── breath.cljk             # the cell — babashka port (DEPLOYED impl; no web3/eth_account)
├── pyproject.toml          # uv / pip deps: web3, eth-account (python reference impl)
├── breath.py               # the cell — original Python module (kept for reference)
└── state.edn              # persistent cell state (counter + last_anchor)
```

## Quick run (against local anvil)

Prereqs:
1. `anvil --chain-id 260425 --port 8545` running locally
2. EtzhayyimAnchor deployed at the address in `deps.toml [platform.l2.anchor_contract].address_local_anvil` (= `0x5fbdb2315678afecb367f032d93f642f64180aa3` as of 2026-05-17)

**babashka (cljc) — the deployed impl** (`deploy.sh` / `monitor.sh` use this; tx is
built + signed by the pure-Clojure `eth-crypto-clj`, no web3 / no eth_account):

```bash
cd orgs/etzhayyim/com-etzhayyim-first-breath
kbb breath.cljk            # single breath
kbb breath.cljk --dry-run  # build + SIGN locally, do NOT broadcast (no-server-key)
kbb breath.cljk selftest   # offline EIP-155 sign-path self-check
# or repeated:
while true; do kbb breath.cljk; sleep 60; done
```

**python (original reference impl)** — `breath.py` is retained alongside the cljc
(its `pyproject.toml` still declares the web3 / eth_account project); not used by
deploy/monitor:

```bash
uv sync                   # or: pip install web3 eth-account
uv run breath.py          # single breath
```

## What you see

```
[first-breath] tick #1 — cell state: counter=1, ts=2026-05-17T22:30:00
[first-breath] root: 0xab12...
[first-breath] anchored: tx 0x4e1f..., block 9
[first-breath] verified: Anchor.rootCount() = 2  ← +1 each breath
```

Run repeatedly → `Anchor.rootCount()` grows monotonically → the cell is **demonstrably alive on-chain**.

## How this maps to the full substrate vision

| Demo (first-breath) | Production cell |
|---|---|
| local sha256 of state JSON | proper AT Protocol MST root CID |
| state.edn on disk | AT records on PDS via `@etzhayyim/sdk.write()` |
| Direct viem anchor call | SDK → `mst-projector` → `ipfs-pinner` → `anchor-cron` → Anchor |
| anvil at localhost:8545 | geth.etzhayyim.com (private chain) + Base L2 anchor |
| Hardcoded anvil acct[0] | DID-bound Smart Account + Paymaster sponsorship |
| Counter increment toy | LangGraph Pregel iteration (perception → reasoning → action) |
| Single process | Fleet of cells, each on a different mini |

The skeleton stays the same shape; production swaps each component for its full substrate counterpart.

## See also

- ADR-2605171800 — pipeline
- ADR-2605172000 — kotoba substrate
- ADR-2605172300 — bi-asset substrate (AdherentRegistry + KishaStream layer)
- `../etzhayyim-sdk/` — the future home of this anchor call (currently direct viem)
