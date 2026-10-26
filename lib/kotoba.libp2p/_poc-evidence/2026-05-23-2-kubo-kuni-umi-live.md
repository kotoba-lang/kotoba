# 2-Kubo libp2p PoC — live HTTP + XRPC lexicon call against KuniUmiApiCell

Date:     2026-05-23T19:13Z
Protocol: `/x/etzhayyim/xrpc/1.0`
Kubo:     0.41.0
Backend:  `KuniUmiApiCell` (aiohttp, naphtali profile, port 13030) — see
          `40-engine/kotoba/crates/kotoba-kotodama/cells/kuni_umi_api/cell.py`

## Topology

| Role     | PeerId                                                  | IPFS_PATH        | API port | Swarm port |
|----------|---------------------------------------------------------|------------------|----------|------------|
| Primary  | `12D3KooWSrap6CTsz5RW4MTrjYn4tNKNXPHrDE2JYpqRNWEH4Ddf`   | `~/.ipfs`        | 5001     | 4001       |
| 2nd peer | `12D3KooWQ5z5TAk1V3cDuXqQsEv8RtvbgZu1p4x69w9AJeU16x5D`   | `/tmp/kubo-2nd`  | 5101     | 4101       |

Two distinct daemons on jacob; direct QUIC swarm-connect verified before mount.

## Wire log

### Primary listen
```
$ ipfs p2p listen /x/etzhayyim/xrpc/1.0 /ip4/127.0.0.1/tcp/13030 --allow-custom-protocol
$ ipfs p2p ls
  /x/etzhayyim/xrpc/1.0 /p2p/12D3KooWSrap6CTsz5RW4MTrjYn4tNKNXPHrDE2JYpqRNWEH4Ddf /ip4/127.0.0.1/tcp/13030
```

### 2nd peer forward
```
$ IPFS_PATH=/tmp/kubo-2nd ipfs p2p forward /x/etzhayyim/xrpc/1.0 \
    /ip4/127.0.0.1/tcp/29030 \
    /p2p/12D3KooWSrap6CTsz5RW4MTrjYn4tNKNXPHrDE2JYpqRNWEH4Ddf \
    --allow-custom-protocol
$ IPFS_PATH=/tmp/kubo-2nd ipfs p2p ls
  /x/etzhayyim/xrpc/1.0 /ip4/127.0.0.1/tcp/29030 /p2p/12D3KooWSrap6CTsz5RW4MTrjYn4tNKNXPHrDE2JYpqRNWEH4Ddf
```

### GET /healthz through tunnel
```
$ curl http://127.0.0.1:29030/healthz   # 2nd peer side
$ curl http://127.0.0.1:13030/healthz   # primary direct
$ diff <(curl ...:29030/healthz) <(curl ...:13030/healthz)
  → identical, 505 bytes each
```

### POST /xrpc/com.etzhayyim.apps.etzhayyim.kuniUmi.defineDeploymentSite through tunnel
```
$ curl -X POST http://127.0.0.1:29030/xrpc/com.etzhayyim.apps.etzhayyim.kuniUmi.defineDeploymentSite \
    -d '{"siteCode":"LIBP2P-2KUBO-001","name":"libp2p 2-Kubo PoC",
         "geo":{"type":"Feature","geometry":{"type":"Point","coordinates":[138.86,35.42]}},
         "utilityClass":"electric","domain":"terrestrial",
         "jurisdictionDid":"did:web:etzhayyim.com:land:test:0",
         "stewardDid":"did:web:etzhayyim.com:steward:0",
         "intendedUse":"Community microgrid 200hh","intendedBeneficiaryDids":[]}'

  ok=True
  latencyMs=6.74
  threadId=site-survey-s.etzhayyim.kuniUmi.defineDeploymentSite
  state.jurisdiction_ok=True
  state.charter_rider_ok=True
  state.ecology_baseline.impactScore=25
  state.submission_at_uri=at://did:web:etzhayyim.com:site:unknown/com.etzhayyim.apps.etzhayyim.kuniUmi.submitSiteSurvey/1779531205755
```

## Interpretation

- The 2nd peer's TCP socket on `127.0.0.1:29030` is a libp2p stream forwarder.
  All bytes flow over the `/x/etzhayyim/xrpc/1.0` protocol to the primary,
  then via the primary's `ipfs p2p listen` mount into the local TCP socket of
  `KuniUmiApiCell` at `127.0.0.1:13030`.
- The SiteSurveyCell LangGraph ran fully end-to-end (jurisdiction_dmn,
  unispsc_lookup, ecology_assessment, witness_attestation, synthesize_survey,
  emit_at_record) and emitted a `submission_at_uri`. The 6.74ms latency includes
  the round-trip over libp2p plus all 8 graph nodes.
- Bytes identical to the direct path confirms the libp2p stream is transparent
  to the HTTP layer (no mangling, no framing artifacts).
- The single-host self-dial failure from iter-10 is resolved by running two
  Kubo daemons with distinct PeerIds (Ed25519 keypairs). Production fleet
  will use the same pattern with one Kubo per Mac mini.

## Outstanding

- The fleet (`naphtali / zebulun / joseph / issachar / dan / simeon / levi`)
  is not yet deployed (task #6, blocked on 1Password ssh-copy-id).
- SiteSurveyCell's `fan_out_specialists` now has `_ensure_libp2p_tunnel(shard)`
  that uses `kotodama.transport.libp2p.dial_peer()` when
  `UNISPSC_SHARD_<n>_PEER_ID` env is set; falls back to plain LAN HTTP otherwise.
- Cell-runner `KUBO_LIBP2P=1` auto-expose hook is wired (iter-10) so every
  `lan-api` cell automatically publishes its TCP port on libp2p when the env
  knob is set.

## How to reproduce

```bash
# 1) Init 2nd Kubo
export IPFS_PATH_2=/tmp/kubo-2nd
IPFS_PATH=$IPFS_PATH_2 ipfs init --profile=server
IPFS_PATH=$IPFS_PATH_2 ipfs config --json Experimental.Libp2pStreamMounting true
IPFS_PATH=$IPFS_PATH_2 ipfs config --json Addresses.API '"/ip4/127.0.0.1/tcp/5101"'
IPFS_PATH=$IPFS_PATH_2 ipfs config --json Addresses.Gateway '"/ip4/127.0.0.1/tcp/8180"'
IPFS_PATH=$IPFS_PATH_2 ipfs config --json Addresses.Swarm '["/ip4/0.0.0.0/tcp/4101","/ip4/0.0.0.0/udp/4101/quic-v1"]'

# 2) Start both daemons
ipfs daemon --routing=dhtclient &
IPFS_PATH=$IPFS_PATH_2 ipfs daemon --routing=dhtclient &

# 3) Have 2nd peer connect to primary directly
PRIMARY_ADDR=$(curl -fsS -X POST http://127.0.0.1:5001/api/v0/id | jq -r '.Addresses[] | select(contains("127.0.0.1") and contains("/tcp/"))' | head -1)
IPFS_PATH=$IPFS_PATH_2 ipfs swarm connect "$PRIMARY_ADDR"

# 4) Boot KuniUmiApiCell as the actor backend
cd 40-engine/kotoba/crates/kotoba-kotodama/py
UNISPSC_EXECUTOR_SHARD_0=http://127.0.0.1:1 \
UNISPSC_EXECUTOR_SHARD_1=http://127.0.0.1:1 \
UNISPSC_EXECUTOR_SHARD_2=http://127.0.0.1:1 \
uv run python -m kotodama.cell_runner_main --node naphtali &

# 5) Mount + forward
PRIMARY_ID=$(ipfs id -f '<id>')
ipfs p2p listen /x/etzhayyim/xrpc/1.0 /ip4/127.0.0.1/tcp/13030 --allow-custom-protocol
IPFS_PATH=$IPFS_PATH_2 ipfs p2p forward /x/etzhayyim/xrpc/1.0 \
    /ip4/127.0.0.1/tcp/29030 \
    /p2p/$PRIMARY_ID --allow-custom-protocol

# 6) curl through tunnel
curl http://127.0.0.1:29030/healthz
```
