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

| Knob | Env | CLI | Default (in order) |
|---|---|---|---|
| Delegated routers | `KOTOBA_ROUTERS` | `--router` (repeatable) | `delegated-ipfs.dev`, `cid.contact` |
| Trustless gateways | `KOTOBA_GATEWAYS` | `--gateway` (repeatable) | `trustless-gateway.link`, `ipfs.io`, `ipfs.filebase.io`, `gateway.pinata.cloud`, `ipfs.4everland.io` |
| Catalog mirrors | `KOTOBA_CATALOG_URLS` | `--catalog` (repeatable) | `kotoba-lang.org/.well-known/kotoba-package-registry.edn` |
| Catalog CID gateways | `KOTOBA_CATALOG_GATEWAYS` | `--catalog-gateway` (repeatable) | the gateway list above |
| Hosted storage origin | `KOTOBA_HOSTED_ENDPOINT` | `--endpoint` | `kotobase.net` |
| IPNS routers | `KOTOBA_IPNS_ROUTERS` (now also for `codebase publish --ipns` / `follow-name`) | `--router` | `kad.routing`'s own default |
| Passkey RP allow-list | `KOTOBA_PASSKEY_RP_IDS` | `--rp-id` (must be allow-listed) | `auth.kotoba.cloud` |

Historical defaults keep their position at the head of each list, so an
unconfigured CLI asks the same hosts first. New defaults are appended and
were chosen because they are run by different operators and were observed
serving `?format=raw` with a 200 and no redirect.

### Semantics per surface

- **Routing.** Routers are asked in order; the first that names an
  HTTP-reachable provider answers (one round trip in the common case). A
  router that errors or names nobody is skipped. An explicit `:router` /
  single `--router` still means exactly that router. An explicit `:gateways`
  (even empty) is never widened — `package add` keeps its provider set exact.
  Availability proofs still record one router: the first configured.
- **Catalog.** Sources are the URLs in order, then — only when
  `--catalog-cid` is pinned — the gateways asked for that CID. A source whose
  bytes hash to anything other than the pin is skipped exactly like an
  unreachable one. If none matches: any mismatch reports
  `:package/catalog-cid-mismatch`; a single source rethrows its own error
  (the old one-URL behaviour, unchanged); several failures report
  `:package/catalog-unavailable` with every attempt. `install!` still refuses
  to run without a pin. The 1 MiB cap binds the gateway path too.
- **Hosted origin.** Only the default is configurable; `--provider` already
  replaces the single origin with several independent ones.
- **Passkey RP.** The allow-list *replaces* the default when set; its first
  entry is what `kotoba id new` asks for. Entries must be bare lowercase DNS
  hostnames; invalid entries are never allowed, and a list with no valid
  entry falls back to `[auth.kotoba.cloud]`. The device flow is always
  spoken to `https://<rp-id>` — RP and origin cannot be configured apart — and
  `device-authorize!` itself refuses an RP outside the list, so the refusal
  happens before any browser opens or any request is sent, as before. The
  enrolled RP is recorded in `principal.edn`.

## What did not change

Verification is byte-for-byte the same: CID check per block, `?format=raw` +
`application/vnd.ipld.raw`, redirects not followed, 4 MiB block cap, 1 MiB
catalog cap, HTTPS-only catalog URLs (localhost excepted), IPNS validation
against the name's key, two-origin + PQC admission for packages. Adding a
host widens where the CLI asks, never what it accepts.

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
