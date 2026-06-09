# Mishmar social-capital economy — Murakumo fleet deployment

Runbook for wiring the social-capital economic loop (ADR-2606082100) to live
infrastructure and running it on a **Murakumo Mac mini fleet node**. The node is
the right host because it can reach (a) the geth-private tunnel and (b) the
KaizenObserver feed; the loop is **read+verify only** (no inbound listener, no
on-chain signing — settlement credits the internal mKOTO `Econ` wallet).

```
[geth-private 260425]──eth_getLogs──▶ Pinned/Slashed ──▶ PinIndex/OriginIndex
[KaizenObserver]──feed (R0 schema)──▶ wellbecoming-Δ        did↔cid bridge attributes
            └────────────────────┬──────────────────────────────┘
   social_economy_tick:  SocialEconomyDriver.tick ─▶ mint ─▶ SocialCapitalView
            ─▶ SC_root ─▶ retainer(§6) ─▶ settle ─▶ Econ wallet (persisted mKOTO)
```

## Status of the live endpoints (probe before deploying)

```sh
# geth-private RPC — expect {"result":"0x3f949"} (chainId 260425).
curl -s -X POST https://geth.etzhayyim.com -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
```

As of 2026-06-09 this returned **HTTP 502** (CF Worker up, in-cluster geth /
tunnel down). Bring geth-private back up (see
`50-infra/vultr/geth-private/`) before the live tick can observe logs.

## 1. Deploy `MishmarBondEscrow` to geth-private

The contract is at `…/geth-private/contracts/src/MishmarBondEscrow.sol`
(17 Foundry tests green). Constructor args:

| arg | value (geth-private) |
|---|---|
| `bondToken` (GCC) | `0x8e9A5162b2800E0D19acC1708A531A3954900E21` |
| `sbt` (Adherent SBT) | see `50-infra/etzhayyim-membership-contract/` deploy |
| `charters` (compliance registry) | see `50-infra/etzhayyim-charters-compliance/` |
| `retainerPool` | commons retainer Safe (Public Fund sub-account) |
| `publicFund` | Public Fund Safe (`50-infra/etzhayyim-public-fund/`) |
| `owner` | Council Safe |

```sh
cd 50-infra/vultr/geth-private/contracts
SEALER=$(security find-generic-password -s "etzhayyim.private-chain" -a "SEALER_PRIV" -w)
forge create src/MishmarBondEscrow.sol:MishmarBondEscrow \
  --rpc-url https://geth.etzhayyim.com --private-key "$SEALER" \
  --constructor-args \
    0x8e9A5162b2800E0D19acC1708A531A3954900E21 \
    <SBT_ADDR> <CHARTERS_ADDR> <RETAINER_POOL> <PUBLIC_FUND> <OWNER_SAFE>
```

Then register the witness set (`setWitness`, owner-only) — the Murakumo cell
signer keys — and add `"storage-slash"` handling per the ADR. Record the
deployed address in `…/geth-private/contracts/ADDRESSES.md`.

> **Operator action.** This step uses the sealer key and writes on-chain — run it
> yourself (it is intentionally not automated). The agent only prepared the
> contract + tests + this runbook.

## 2. Build the tick binary on the fleet node

```sh
cd <kotoba checkout>
cargo build --release --example social_economy_tick -p kotoba-server
install -m755 target/release/examples/social_economy_tick /Users/Shared/kotoba/bin/
```

## 3. Configure

```sh
mkdir -p /Users/Shared/kotoba/social-economy
cp deploy/social-economy/social-economy.env.example /Users/Shared/kotoba/deploy/social-economy/social-economy.env
# edit: KOTOBA_MISHMAR_ESCROW_ADDR (step 1), KOTOBA_SOCIAL_GRAPH_CID,
#       KOTOBA_KAIZEN_FEED_URL, KOTOBA_TICK_BIN=/Users/Shared/kotoba/bin/social_economy_tick
```

Smoke-test one tick by hand (uses the env; falls back to a FAKE demo if unset):

```sh
KOTOBA_TICK_BIN=/Users/Shared/kotoba/bin/social_economy_tick \
  sh deploy/social-economy/run-tick.sh
```

## 4. Install the launchd agent (one tick / epoch-day)

```sh
cp deploy/social-economy/run-tick.sh /Users/Shared/kotoba/deploy/social-economy/
cp deploy/social-economy/com.etzhayyim.kotoba.social-economy.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.etzhayyim.kotoba.social-economy.plist
# logs: /Users/Shared/kotoba/social-economy/tick.{log,err.log}
```

## 5. Verify

- `tick.log` shows `LIVE: minted N social Datoms; … total … mKOTO`.
- Read a DID's capital over XRPC (any kotoba node serving the graph):
  `GET /xrpc/com.etzhayyim.apps.kotoba.social.capital?graph=<cid>&did=<cid>&epoch=<n>`.

## Remaining R0 caveats

- **KaizenObserver feed schema** (`KOTOBA_KAIZEN_FEED_URL`) is provisional —
  reconcile `parse_kaizen_wellbecoming` against the live feed (ADR-2605240200).
- **Disclosure/falsification observation** (ClaimStakeEscrow terminal events) is
  not yet decoded — only pin observation + wellbecoming are wired; the tick passes
  empty disclosures/falsifications until that decoder lands.
- **Minted Datoms must be transacted** to the canonical Datom log (`datomic.transact`)
  for the view to survive restart — the tick prints them; wire the transact next.
- **eth_getLogs block range** is a full scan (`0x0..latest`); add a persisted
  cursor for incremental observation at scale.
