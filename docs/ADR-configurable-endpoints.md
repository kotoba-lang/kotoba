# ADR — No single host is mandatory: configurable endpoint lists (decentralization step 1)

- **Status**: Accepted · implemented
- **Date**: 2026-10-10
- **Related**: `ADR-001-five-axis-distributed-redesign.md`,
  `ADR-browser-cid-query-vs-p2p.md`, `ADR-kotoba-content-addressed-codebase-gap.md`

## Context

Every network path in the CLI already verifies what it receives — blocks
against their CID, catalogs against a caller-pinned CID, IPNS records against
the key the name encodes, redirects never followed, sizes capped. Yet four
places still named exactly one host as the only place to ask:

| Where | Hard-coded | Effect |
|---|---|---|
| `kotoba.codebase-routing` | router `delegated-ipfs.dev`; gateways `trustless-gateway.link`, `ipfs.io` | discovery stops if that router is down; `ipfs.io` now 301-redirects raw requests to `trustless-gateway.link` (observed 2026-10-10), so the fallback was effectively one operator |
| `kotoba.package-install` | catalog `https://kotoba-lang.org/.well-known/…` | a pinned catalog CID could only be fetched from one origin |
| `kotoba.codebase-ipns` / launcher | hosted origin `https://kotobase.net`; IPNS routers env only for `deploy` | hosted publication had no override short of `--endpoint` |
| `kotoba.principal-identity` | Passkey RP `auth.kotoba.cloud`, all others refused | an operator could not run their own identity RP |

Because the content is self-certifying, a host here is only ever *where to
ask*, never *what to believe*. A single mandatory host is therefore an
availability and censorship dependency with no integrity benefit.

## Decision

Every such endpoint becomes an **ordered list with a default**, resolved by one
rule shared through `kotoba.endpoint-config`:

    CLI flag(s)  >  environment variable (comma-separated)  >  built-in defaults

This is the mechanism the launcher already used (`KOTOBA_IPNS_ROUTERS`,
`KOTOBA_CONTROL_PLANE_PROFILES`); it is now the only one. A blank variable is
treated as unset so it can never disable a list by accident.

Every URL entry (routers, gateways, catalog URLs, IPNS routers) is validated
where it enters (`endpoint-config/resolve-endpoints`): it must be an absolute
`http`/`https` URL with a host and no userinfo, query or fragment; trailing
`/` is stripped (no more `//ipfs/…`). An invalid entry is dropped with a
warning on stderr; a list left empty by that is an error
(`:endpoint/no-valid-endpoints`), never a silent fall-back to defaults. At
fetch time a malformed candidate is additionally treated as a miss rather than
aborting the operation.

| Knob | Env | CLI | Default (in order) |
|---|---|---|---|
| Delegated routers | `KOTOBA_ROUTERS` | `--router` (repeatable) | `delegated-ipfs.dev`, `cid.contact` |
| Trustless gateways | `KOTOBA_GATEWAYS` | `--gateway` (repeatable) | `trustless-gateway.link` (others opt-in, see below) |
| Catalog mirrors | `KOTOBA_CATALOG_URLS` | `--catalog` (repeatable) | `kotoba-lang.org/.well-known/kotoba-package-registry.edn` |
| Catalog CID gateways | `KOTOBA_CATALOG_GATEWAYS` | `--catalog-gateway` (repeatable) | none (opt-in) |
| Hosted storage origin | `KOTOBA_HOSTED_ENDPOINT` (exactly one origin) | `--endpoint` | `kotobase.net` |
| IPNS routers | `KOTOBA_IPNS_ROUTERS` (now also for `codebase publish --ipns` / `follow-name`) | `--router` | `kad.routing`'s own default |
| Passkey RP allow-list | `KOTOBA_PASSKEY_RP_IDS` (extends only) | `--rp-id` (must be allow-listed) | `auth.kotoba.cloud` (always allowed, always the implicit default) |
| Availability-proof evidence router | *(none — env ignored)* | `--router` | `delegated-ipfs.dev` |

Historical defaults keep their position at the head of each list, so an
unconfigured CLI asks the same hosts first.

### Default gateways: why only one, and the rest opt-in

Every gateway the CLI asks learns **the CID being fetched and the client's
IP address**. CID verification makes an extra gateway harmless for integrity,
but not for privacy: a default list is a decision, made for every user, about
which third parties observe what they fetch. So:

- `ipfs.io` is dropped: it 301-redirects `?format=raw` to
  `trustless-gateway.link`, and redirects are refused, so it was a dead entry
  that only cost a round trip (and leaked the CID to one more operator).
- `ipfs.4everland.io` is dropped: 53 s observed for a 117 KB block.
- `ipfs.filebase.io` and `gateway.pinata.cloud` (both commercial) are **not**
  defaults. They are listed in `codebase-routing/opt-in-gateways` as known
  working (`?format=raw`, 200, no redirect, 2026-10-10) and enabled by e.g.
  `KOTOBA_GATEWAYS=https://trustless-gateway.link,https://ipfs.filebase.io,https://gateway.pinata.cloud`.

The default is therefore exactly the one gateway an unconfigured CLI
effectively used before this change: no new third party sees a user's
fetches without the operator choosing it. Gateway availability is still not
a single point of failure for the *mechanism* — routing is tried first (two
default routers), any gateway list can be configured, and a gateway is only
the fallback when routing names no HTTP provider.

### Semantics per surface

- **Routing.** Routers are asked in order; the first that names an
  HTTP-reachable provider answers (one round trip in the common case). A
  router that errors or names nobody is skipped. An explicit `:router` /
  single `--router` still means exactly that router. An explicit `:gateways`
  (even empty) is never widened by the configured gateway list — but providers
  named by the routers are still tried, **before** the explicit gateways
  (candidates are: providers that already answered, then router-named
  providers, then `:gateways`). So `package add` asks its catalog's providers
  plus whatever the routers name for that CID; every byte is verified either
  way.
- **Per-candidate verification.** `block-source` verifies each candidate's
  bytes against the CID (raw or dag-cbor by the CID's codec, using
  `kotoba.codebase.fetch/verify-raw-bytes` / `verify-bytes`) and moves to the
  next candidate on a mismatch, so one junk gateway early in the list cannot
  end a pull. Only when no candidate served the right bytes and some served
  wrong ones is `:codebase/fetched-cid-mismatch` raised. `hydrate!` verifies
  again (defense in depth).
- **Deadlines.** `:timeout-ms` bounds the whole gateway fetch including the
  body: `read-bounded` enforces an overall deadline even while a read is
  blocked, so a gateway cannot trickle a body forever.
- **Announcement.** `announced?` keeps router outages (exception or non-200)
  under `:errors`; if every router failed it throws
  `:codebase/announce-failed` instead of reporting "not announced".
- **Availability proofs** record one router as evidence. It comes only from an
  explicit `--router` or the built-in `default-router`; `KOTOBA_ROUTERS` is
  ignored for it (`library-release/availability-router`), because a silently
  swappable witness would weaken the proof.
- **Catalog.** Sources are the URLs in order, then — only when
  `--catalog-cid` is pinned **and** catalog gateways were configured — the
  gateways asked for that CID. Catalog gateways are **opt-in** (default none,
  and `KOTOBA_GATEWAYS` is not inherited): a gateway fallback sends the pinned
  CID and client IP to third parties and adds a full timeout per dead gateway
  before an install can fail. A source whose bytes hash to anything other than
  the pin is skipped exactly like an unreachable one. If none matches: any
  mismatch reports `:package/catalog-cid-mismatch`; a single source rethrows
  its own error (the old one-URL behaviour — the default configuration again);
  several failures report `:package/catalog-unavailable` with every attempt's
  `:problem`, `:status` and `:message`. `install!` still refuses to run without
  a pin. The 1 MiB cap binds the gateway path too, and is enforced *during* the
  read (`fetch-block-from` `:max-bytes`), so a gateway read stops at 1 MiB
  rather than at the 4 MiB block cap.
- **Hosted origin.** Only the default is configurable; `--provider` already
  replaces the single origin with several independent ones. The value (env or
  `--endpoint`) must be exactly one origin, HTTPS — plain HTTP only for
  `localhost` / `127.0.0.1` / `::1` — else `:codebase/hosted-endpoint-invalid`.
- **Passkey RP.** `KOTOBA_PASSKEY_RP_IDS` only *extends* the allow-list:
  `auth.kotoba.cloud` is always allowed and is always what `kotoba id new`
  asks for when `--rp-id` is absent. A non-canonical RP is used only when named
  explicitly with `--rp-id`; its enrollment prints a stderr warning (the
  identity projection it returns is shape-checked only) and is flagged
  `:non-canonical-rp? true` in the result and
  `:kotoba.principal/non-canonical-rp? true` in `principal.edn`. Rationale:
  whatever controls a shell's environment must not be able to silently
  redirect identity enrollment. Entries must be bare lowercase DNS hostnames;
  invalid entries are never allowed and are reported on stderr. The device flow is always
  spoken to `https://<rp-id>` — RP and origin cannot be configured apart — and
  `device-authorize!` itself refuses an RP outside the list, so the refusal
  happens before any browser opens or any request is sent, as before. The
  enrolled RP is recorded in `principal.edn`.

## What did not change

Verification is the same or stricter: CID check per block (now also per
candidate inside `block-source`), `?format=raw` + `application/vnd.ipld.raw`,
redirects not followed, 4 MiB block cap, 1 MiB catalog cap, IPNS validation
against the name's key, two-origin + PQC admission for packages. The
HTTPS-only rule applies to the catalog **URL** path (localhost excepted);
gateway entries may be `http` (bytes are verified against the pinned CID).
Adding a host widens where the CLI asks, never what it accepts.

### Privacy note

Every router and gateway asked sees the CID requested and the client IP. The
defaults keep that set to the hosts the CLI already contacted before this
change (plus `cid.contact` as a second router); widening it is the operator's
explicit choice.

## Not done in this step

- `deploy_adapter`'s pinned control-plane topology (which also names
  `auth.kotoba.cloud` and `kotobase.net`) is a separate authority check and is
  untouched.
- `kad.routing`'s default IPNS router list lives in
  `io-libp2p-specs-kad-dht`; no second public `/routing/v1` endpoint accepting
  IPNS `PUT` was identified, so none was added.
- No byte-identical catalog mirror exists yet (`kotoba.cloud` serves a
  different catalog), and the catalog is not yet published to IPFS; the
  mechanisms exist, the second copy is an operational follow-up.
- `follow-name` still needs `--endpoint` for blocks; resolving it through the
  gateway list is a follow-up.
