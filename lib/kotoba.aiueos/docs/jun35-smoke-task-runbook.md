# JUN-35: per-service smoke task runbook (bounded, readback-first)

Companion to `docs/jun35-oci-node-participation-paths.md` (merged #454). That
document states *what* participation is per service; this runbook fixes *how*
each readiness claim is proven with a bounded smoke task, so the OCI node's
readback rows can be filled mechanically once the node boots.

Machine entry point: `kbb --backend sci scripts/jun35-smoke.cljk`
(`plan` / `probe` / `run --service <s>`).

## 0. What is NOT readiness

Recorded so no row below can be satisfied by any of these:

- a configuration file, descriptor upload, or registry entry existing
- a UI window, a process start, a listener bind
- a local QEMU boot (JUN-31/JUN-34 local proofs are boot evidence, not
  service participation)
- an OCI resource being created (instance/volume existence proves nothing)
- `online: true` copied from a stored descriptor (Murakumo's readiness gate
  explicitly never trusts stored `online` claims)

## 1. Bounds (apply to every smoke task)

- **One attempt per step.** No retry loops. A failed step is recorded as a
  failure and the task stops for that service.
- **30 s timeout per HTTP call**; total task budget ≤ 5 minutes per service.
- **Fixed tiny prompt** (inference): the 4-byte literal `ping` — never a
  customer payload, never an unbounded generation.
- **Fixed small blob** (storage): exactly 1024 bytes of `0x00`. Its CID is
  recomputed from the bytes on every verification; a blob that cannot be
  re-hashed to the same CID fails the task.
- **No credentials, tokens, signing material, or payloads in receipts.**
  Receipts carry: ISO timestamp, service, step name, endpoint host + path,
  HTTP status, and the readback value named below.
- Receipt file: one JSON per attempt under the run's evidence directory
  (`receipts/<service>-<timestamp>.json`), written by `scripts/jun35-smoke.cljk`
  `run` mode or by hand with the same field names.

## 2. Murakumo (distributed inference) — bounded smoke task

Source of truth: `network-awai/cloud-murakumo-api`
(`GET /nodes`, `POST /events`, `POST /infer/runs`, `GET /infer/runs?since=`,
`GET /health`; readiness gate in `src/local_murakumo/readiness.cljk`).

Steps (in order, node identity `oci-<instance-id>`):

1. `PUT /nodes/oci-<id>` — descriptor row (inventory only; **not** readiness).
2. `POST /events` — one hwmetrics observation (`:reachable true`, cpu/mem/disk
   numbers as observed by the node itself).
3. `POST /infer/runs` — one run with the fixed prompt `ping`.
4. `GET /infer/runs?since=<seq-before-step-3>` — readback the run.
5. `GET /nodes` — readback the node's row **and its `age-ms`**.

Readiness evidence (all must hold at step 5 readback time):

- the run from step 3 is listed by step 4;
- the node row has `reachable: true` **and** `age-ms ≤ 60000` (the
  `default-stale-ms` of the readiness gate) — i.e. the node satisfies
  `live-node?` **from a fresh observation**, not from its descriptor;
- `GET /health` reports `ok: true` for `local-murakumo` at task start
  (precondition, recorded as step 0).

Writes (`POST /events`, `POST /infer/runs`) require the CAIP-122 credential
(`Authorization: CACAO *** issuer check against the claimed `who`/`did`). The
credential is supplied by the node's own identity material at run time and is
never recorded.

## 3. Itonami (node management / registry) — no smoke task possible

Unchanged from #454: the registry publishes profile/role entries only and
grants no execution authority; the node registration/LCM layer (`tsukasa`,
named 2026-10-21) has no repository or endpoint yet. There is nothing to call,
so the matrix row stays `unsupported` and is **not** marked pending. When
`tsukasa` lands, a registration smoke task replaces this section.

## 4. Yataverse (bytes plane) — bounded smoke task

Source of truth: `kotoba-lang/yataverse` (read `GET <readUrl>/ipfs/<cid>`
with `Accept: application/vnd.ipld.raw` + `?format=raw`; write
`PUT <url><prefix><cid>`, redirect-following forbidden, every write read back
and re-hashed).

Steps:

1. `put` the fixed 1 KiB zero blob; capture the returned CID.
2. `verify`: read the CID back and recompute the multihash from the bytes.
3. (separate row) `store/audit` readback from the node descriptor including
   its `:failure-domain` / `:independence` declaration.

Readiness evidence: recomputed CID == stored CID (bytes match the multihash);
storage results are reported separately from inference readiness. Redirects
are never followed on write; a write that redirects fails the task.

**Current measured gap (2026-10-23, independent of OCI):** the default
endpoints do not resolve in public DNS — `ipfs.yataverse.com`, `kotobase.net`
and `yataverse.com` all return NOERROR/NODATA (no A record) via both the
system resolver and 8.8.8.8 / Cloudflare DoH. Until an address is published
(or the node is given an in-network resolver for these names), steps 1–2
cannot execute and the row stays blocked at the endpoint, before any node
work. See §6 for the probe evidence.

## 5. Kura (storage shards) — bounded smoke task

Steps: node descriptor declaring `:failure-domain` and `:independence`
(no default value exists; a descriptor without both is invalid) → one
`store/audit` readback reporting effective domains and `:survivable?`.
Physical Kura storage coordination is JUN-23; the audit row is not claimed
until that coordination lands.

## 6. Host-side procedure validation (2026-10-23, measured)

Run from a macOS host, read-only, no OCI resources. This validates the
**procedure**, not participation — the OCI node is not involved.

| probe | measured result (2026-10-23 ~11:00 JST) |
|---|---|
| `GET https://api.murakumo.cloud/health` | **200**, `{"ok":true,"service":"local-murakumo","storage":{"backend":"merkle-lsm","ok":true}}` |
| `GET https://api.murakumo.cloud/nodes` | **200**, 11 rows (== `expected-fleet-size`), each with `source:"hwmetrics"`, `observed-at`, `age-ms` 5–9 s at readback; `reachable:true` on gad/issachar/joseph/naphtali/zebulun (5 live at readback instant) |
| `GET https://ipfs.yataverse.com/` | **DNS NODATA** (no A record; system resolver and 8.8.8.8 / DoH agree) |
| `GET https://kotobase.net/` | **DNS NODATA** (same) |

Conclusion: the Murakumo readback path (steps 4–5, `age-ms`-based `live-node?`)
works against the live fleet API exactly as §2 specifies. The Yataverse task
is blocked earlier than the node — at DNS for its endpoints — and that gap is
recorded independently of the OCI auth gate.

Re-run any time with `kbb --backend sci scripts/jun35-smoke.cljk probe`.

## 7. Blocking gates (unchanged, as of 2026-10-23)

1. **OCI auth** FAIL/FAIL (session token expired 2026-10-17 19:32 JST; durable
   API key never provisioned). Owner one-time
   `kbb --backend sci scripts/oci-auth.cljk login`; then preflight → upload →
   import → net → UEFI_64 boot + blank block volume (format-at-boot route,
   #453). No OCI resource has been created.
2. **Yataverse endpoint DNS** (§4/§6) — blocks the storage smoke task before
   any node-side work.
3. **Itonami `tsukasa`** not implemented (§3) — no registration path exists.
