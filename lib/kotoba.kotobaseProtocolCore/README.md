# kotobase-protocol-core

**The shared bottom of the kotobase protocol stack for kotobase.** HTTP request/response data, JSON, ETag fingerprints, CIDs, the content-addressed block space, a memory store, and a registry-only router.

Split out of [`kotobase-protocols`](https://github.com/kotoba-lang/kotobase-protocols)
by superproject ADR-2608051000 (`1 repo = 1 capability`), from that repo's
`main` tip.

| namespace | what it owns |
|---|---|
| `kotobase.protocols.http` | ring-shaped request/response as plain data |
| `kotobase.protocols.json` | dependency-free JSON encode/parse |
| `kotobase.protocols.hash` | FNV fingerprint for ETags — **not** cryptographic, **not** a CID |
| `kotobase.protocols.cid` | CID handling |
| `kotobase.protocols.blocks` | shared content-addressed block space |
| `kotobase.protocols.store` | source-local deterministic memory host |
| `kotobase.protocols.router` | host-label dispatch, registry-only |

## The router has no built-in surface table

Upstream `kotobase-protocols` kept a `surfaces` def that `:require`d
s3/ipfs/atproto/git/ipfs-pinning/issue directly. **That table is what
prevented the surfaces from living in separate repositories** — it made the
router a compile-time consumer of all six.

Here the table is empty and `ctx :surfaces` is the whole registry. The
contract is otherwise unchanged and deliberately so — labels are strings,
`:path-surfaces` is `{prefix label}`, injected mounts are checked before the
built-in prefixes and are *not* stripped — so a deploy shell moves between
the facade and this repo by changing a dependency, not a call.

A surface absent from `:surfaces` is not served, **including its `/health`**,
so a shell never advertises readiness for a capability it does not carry.

A shell that owns exactly one host does not need this namespace at all; it
can call its one handler directly.

## Test

```bash
kbb --backend sci --classpath "src:test:<kotobase>/src" bin/run_tests.cljk
```

`<kotobase>` is a checkout of `kotoba-lang/kotobase`. It supplies both the
LocalStore test oracle and the runtime `kotobase.store` protocol used by the
legacy document-store fallback and audit path. The pinned runtime dependency
is declared in `deps.edn`; this source placement does not remove it.

## Namespaces are unchanged

They are still `kotobase.protocols.*`. Repo name and namespace need not match,
and renaming would break every consumer for no benefit.

**Do not put this repo and the `kotobase-protocols` facade on the same
classpath** — the namespaces collide. Use one or the other.

## Opt-in protocol source projects

IPQ, query composition and LFS now live as independent projects under
`surfaces/kotoba.kotobase.protocol.*`, retaining their public Lisp namespaces,
licenses, dependencies and release boundaries. The root router does not depend
on or auto-register them. Source IDs and the exact old repository/coordinate
aliases resolve with:

```sh
node scripts/protocol-sources.mjs list
node scripts/protocol-sources.mjs resolve kotoba.kotobase.protocol.ipq
node scripts/protocol-sources.mjs classpath kotoba-lang/kotobase-lfs
```

These commands return source paths with `admission: not-granted`. They do not
expand the standard library catalog, grant effects, change authentication or
publish a route. LFS's paths do not include the unrelated protocol-core root.
See [ADR-0001](docs/adr/0001-protocol-source-monorepo.md) for the reviewed LFS
storage compiler floor, typed dependency checks, independent host suites,
complete history/WIP recovery and pending main/retirement gates.
