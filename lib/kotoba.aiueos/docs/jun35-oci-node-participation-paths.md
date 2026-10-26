# JUN-35: OCI node participation paths — Murakumo / Itonami / Yataverse

Scope: document each service's supported protocol, endpoint, node identity /
registration, policy, and required capabilities **separately**, so the OCI
AIUEOS node (JUN-24 / JUN-34) can be wired one service at a time and read back
one service at a time. Readiness must be proven per service with a bounded
smoke task; configuration alone is not participation.

Evidence provenance (local checkouts, read 2026-10-23 JST):

| repo | HEAD |
|---|---|
| `network-awai/cloud-murakumo-api` | `5e5b497a08e2ee653488c65fb052708d9af52c48` |
| `kotoba-lang/yataverse` | `c875a39db9a2ddd79c9666284673696ae02fd9b9` |
| `kotoba-lang/kura-node` | `c6c48d3bd7c6d021e90f32cb82c3ef8960709c10` |
| `kotoba-lang/kura` | `d3d77920a04e2bdad4de6e080727334ab237df12` |
| `cloud-itonami/itonami-registry` | `422e10b3fe6f1261e2daf9a58ada4f2b2b489a2b` |

No credentials, signing keys, or customer data are recorded here.

## 1. Murakumo (distributed inference)

Source: `network-awai/cloud-murakumo-api/README.md`, `src/local_murakumo/readiness.cljk`.

- **Protocol / endpoint**: HTTPS JSON against the inference API gateway
  deployed at `api.murakumo.cloud` (ClojureScript Cloudflare Worker). The node
  surface is the fleet HTTP API:
  `GET /nodes`, `GET|PUT /nodes/<id>`, `POST /events`,
  `GET /events?since=<seq>`, `GET /health`,
  `GET|PUT /infer/models/<id>`, `GET|PUT /infer/plans/<id>`,
  `POST /infer/runs`, `GET /infer/runs?since=<seq>`.
  Client inference surfaces: `POST /v1/messages` (Anthropic Messages shape),
  `POST /v1/embeddings` (OpenAI shape), and the clean-room AWAI Grok Bots
  boundary `POST /v1/grok-bots/responses` (capability descriptor at
  `GET /v1/grok-bots`, compatibility limits in
  `docs/grok-bots-clean-room.md`).
- **Node identity / registration**: a node is a row written through
  `PUT /nodes/<id>`; ongoing participation is `POST /events` plus periodic
  **hwmetrics observations**. Fleet state is stored in kotobase.net (the kotoba
  PDS) and served from the Worker.
- **Policy / readiness gate** (`readiness.cljk`): "a stored descriptor is
  inventory; only a recent hwmetrics observation may call a node online."
  `live-node?` requires `:reachable true` **and** observation age ≤ 60 s
  (`default-stale-ms`); model-generation freshness is 15 min. Stored `online`
  claims are never copied. Expected fleet size is 11 (`expected-fleet-size`).
  ⇒ the OCI node readback for "online" must be a fresh hwmetrics observation,
  not the descriptor it uploaded.
- **Auth / capabilities**: actor-authored writes (`POST /infer/runs`,
  `/infer/spend`, `/v1/slow/*` server side) accept the CAIP-122 credential
  emitted by `cacao.core/auth-header` (`Authorization: CACAO …`); the verified
  CACAO `iss` must equal the claimed `who`/`did`. `POST /infer/transfer` is
  stricter: its signed SIWE resources must contain the exact capability
  `murakumo:transfer?to=<recipient>&credits=<amount>`. Credits, fleet registry,
  passkey/Biscuit auth, model routing are owned by this Worker.
- **Planned OCI smoke task** (bounded): register node → emit one hwmetrics
  event → `POST /infer/runs` with a fixed tiny prompt → read back
  `GET /infer/runs?since=` and `GET /health`. Readiness = the run is listed
  and the node is `live-node?` at readback time.

## 2. Itonami (node management / registry)

Source: `cloud-itonami/itonami-registry/README.md`, itonami world manifest
conventions (manifest/worlds.edn, manifest/agent-registry.edn).

- **Protocol / endpoint**: static-site + JSON API on GitHub Pages
  (`api/v1/index.json`, `categories.json`, `models.json`, `registries.json`,
  `entries/<registry>/<type>/<id>.json`) built by `scripts/build_site.py`;
  profiles are installed via `scripts/add_profile.py`.
- **Node identity / registration**: today's registry publishes **profile and
  role entries only** — "Registry publication grants no execution authority,
  changes no running profile and activates no scheduler." The node ledger /
  registration / LCM layer (`tsukasa`, decided 2026-10-21) is **named but not
  implemented** (no repository yet), and is architecturally separate from
  murakumo (observation/placement) and sahai (lease).
- **Policy**: `manifest/agent-registry.edn` is an index, not authority;
  authority is `yakuwari.edn`. Nodes are `resident` organisms — things that
  happen by themselves; bots proceed without waiting for human approval inside
  AWAI, but nothing here registers a compute node today.
- **Status for the OCI node: unsupported / 未実装.** There is no
  machine-facing node-registration endpoint to call. Recorded as an
  independent gap per JUN-35 acceptance ("record failures and unsupported
  paths independently"). When `tsukasa` lands, the OCI node's registration
  goes through it; until then, "Itonami participation" cannot be claimed.

## 3. Yataverse (bytes plane) and Kura (storage shards)

Source: `kotoba-lang/yataverse/README.md`, `kotoba-lang/kura-node/README.md`,
`kotoba-lang/kura/README.md`.

- **Protocol / endpoint (bytes plane)**: content-addressed blocks, CIDv1
  raw/sha2-256 (reads also accept legacy CIDv0 dag-pb). Read:
  `GET <readUrl>/ipfs/<cid>` (default `https://ipfs.yataverse.com`, gateway 301
  to per-CID subdomain, followed ≤3 hops **inside the read host's parent
  domain only**, `Accept: application/vnd.ipld.raw`, `?format=raw`). Write:
  `PUT <url><prefix><cid>` (default `https://kotobase.net/ipfs/`,
  `application/vnd.ipld.raw`); a write **never follows a redirect** (the
  `Authorization` header must not travel to another host), is limited to
  CIDv1/raw blocks, and **every write is read back and its CID recomputed**.
- **Node identity / capabilities**: `yataverse config init --tenant-id t_…`
  with a service-account token supplied on stdin (never on argv); tokens for
  other tools come from `yataverse token`. `yataverse status` reports local
  configuration by name only. A `yataverse mcp` stdio server exposes the same
  surface to MCP clients. Training-asset provenance: `asset-manifest` →
  canonical JSON → `put` → verified CID; `asset-did <cid>` derives the
  Murakumo `did:web` identifier.
- **Policy**: bytes are verified against the CID on **every read and after
  every write**; a response whose bytes do not match the multihash is refused.
  No unverified byte is accepted as a result.
- **Kura (shard layer)**: `kura-node` holds shards, moves bytes, answers
  audits, counts what is owed; `kura` decides placement/repair and
  `kura-bugyo` runs the coordinator loop. A backend **must** declare
  `:failure-domain` and `:independence` (`:independent` / `:shared-provider` /
  `:shared-substrate`, no default) — `store/audit` reports effective domains
  and `:survivable?`. Placement is two-level (hash → placement group → node
  set). Physical/Kura storage coordination is JUN-23.
- **Planned OCI smoke task** (bounded): `put` of a fixed small blob →
  `verify` by CID (readback evidence = recomputed CID match) → one
  `store/audit` readback from the node descriptor with its independence
  declaration recorded. Storage verification is reported **separately** from
  inference readiness.

## Readback matrix (to be filled after the node boots)

| service | smoke task | readiness evidence | result |
|---|---|---|---|
| Murakumo | register → hwmetrics → `POST /infer/runs` → readback | run listed + `live-node?` at readback | pending (OCI instance) |
| Itonami | none possible | — | unsupported: `tsukasa` not implemented |
| Yataverse | `put` → `verify` by CID | recomputed CID == CID | pending (OCI instance) |
| Kura | descriptor + `store/audit` | `:survivable?` + independence declared | pending (JUN-23 coordination) |

Blocking gate unchanged: OCI API/CLI auth is FAIL/FAIL (session token expired
2026-10-17 19:32 JST; durable API key never provisioned). Owner one-time
browser login (`kbb --backend sci scripts/oci-auth.cljk login`) unblocks
upload/import/instance; until then no OCI resource exists to read back from.
