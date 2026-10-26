# etzhayyim-libp2p

Peer-resolvable transport substrate for the religious-corp ecosystem.
Per **ADR-2605241800**.

This package is the **L2 transport layer** of the 5-layer architecture
defined in that ADR:

```
L5  ERC-725 root + ERC-8004 registry + AdherentRegistry + AAT     ← settled (chain)
L4  did:pkh + did:web + did:key + agentURI (IPFS-pinned)          ← settled (spec)
L3  agent.json service[]   ← libp2p Multiaddr injected by THIS package
L2  libp2p (Kubo's go-libp2p)   ← THIS package (Phase B)
L1  AT Protocol XRPC + Lexicons   ← unchanged
```

The package is **shell-thin** — it wraps the existing Kubo
`ipfs p2p listen` / `forward` commands. Every Murakumo Mac mini
already runs Kubo (per ADR-2605241500 datasets and ADR-2605171800
MST CAR pinning), so no new daemon is introduced.

## Why libp2p

libp2p (4.53/5 weighted score in the ADR-2605241800 comparison) wins
over iroh (4.36), pkarr (4.29), and Holochain DPKI (4.06) for the
combined axes of ERC-8004 fit, discovery, transport, Mac-fleet fit,
operational maturity, and doctrinal alignment. Crucially, the PeerId
(Ed25519) is bit-identical to the `did:key` form of the same key, so
the transport identity == the AT Protocol caller identity — one less
seam.

## One-time enable

```sh
ipfs config --json Experimental.Libp2pStreamMounting true
launchctl kickstart -k gui/$UID/com.etzhayyim.kubo   # restart Kubo
```

## Actor side (`expose-xrpc.sh`)

Tell Kubo to accept libp2p streams on `/x/etzhayyim/xrpc/1.0` and
deliver them to a local XRPC handler:

```sh
./scripts/expose-xrpc.sh 18080            # local XRPC listening on tcp:18080
# → /x/etzhayyim/xrpc/1.0  /p2p/<this-node-peer-id>  /ip4/127.0.0.1/tcp/18080
```

## Consumer side (`dial-xrpc.sh`)

Open a local TCP socket that tunnels to a remote peer's XRPC over libp2p:

```sh
./scripts/dial-xrpc.sh 12D3KooW...AiEc 29080
# → /x/etzhayyim/xrpc/1.0  /ip4/127.0.0.1/tcp/29080  /p2p/12D3KooW...AiEc
curl http://127.0.0.1:29080/xrpc/...   # bytes tunneled
```

## Publishing the libp2p endpoint in agentURI

```sh
./scripts/agent-json-libp2p-service.sh > my-service-entry.json
# Then splice into your IPFS-pinned agent.json `service[]` array.
```

The emitted JSON fragment looks like:

```json
{
  "id": "#xrpc-libp2p-primary",
  "type": "AtprotoXrpc",
  "serviceEndpoint": "/p2p/12D3KooW...AiEc",
  "x-libp2p-protocol": "/x/etzhayyim/xrpc/1.0"
}
```

For cold-bootstrap-friendly publication, also include the
dnsaddr-wrapped form (see `print-multiaddr.sh`):

```json
{
  "id": "#xrpc-libp2p-bootstrap",
  "type": "AtprotoXrpc",
  "serviceEndpoint": "/dnsaddr/etzhayyim.com/p2p/12D3KooW...AiEc",
  "x-libp2p-protocol": "/x/etzhayyim/xrpc/1.0"
}
```

## PoC evidence

`_poc-evidence/2026-05-24-2-peer-loopback.md` captures the
two-peer-Kubo loopback test that confirmed:

- Host peer `12D3KooW...AiEc` listens on `/x/etzhayyim/xrpc/1.0`.
- Consumer peer `12D3KooW...1bdX` (separate `/tmp/kubo-consumer`) forwards.
- HTTP backend on `:18080` receives the tunneled GET (server log confirms).
- `diff` between direct and tunneled response bytes: identical.

## Migration phase (per ADR-2605241800)

This package ships Phase B. Phase C (HTTPS retirement) and Phase D
(kotoba-datomic witness quorum) are downstream follow-ons.

## License

Apache-2.0 + etzhayyim Charter Compliance Rider v2.0 (see repo-root
`CHARTER-RIDER.md`).
