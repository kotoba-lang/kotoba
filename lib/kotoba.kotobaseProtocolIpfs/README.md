# kotobase-protocol-ipfs

**IPFS gateway surface for kotobase.** GET/HEAD `/ipfs/{cid}` with a content-type allowlist. GET/HEAD `/ipni/v1/ad/{cid}` and `/ipni/v1/head` are the IPNI publisher reads over the same block plane (ADR-2608160300). This repo does not require ipni.

Split out of [`kotobase-protocols`](https://github.com/kotoba-lang/kotobase-protocols)
by superproject ADR-2608051000 (`1 repo = 1 capability`), from that repo's
`main` tip.

The handler is a **pure cljc function** over an injected plain operation map —
`(handle ctx req) → resp`. No network I/O, no host JSON, no crypto dependency.
Authentication and transport belong to the deploy shell.

## Dependencies

[`kotobase-protocol-core`](https://github.com/kotoba-lang/kotobase-protocol-core)
and nothing else — alone among the six surface repos, this one really does stop
there. It is now declared in `deps.edn`, which said `:deps {}` until 2026-09-06
while this section claimed the dependency.

**This repo does not depend on the other surface repos, and they do not depend
on it** — that separation is the point of the split; the registry router in
core is what composes them when a deployment wants more than one.

## Test

```bash
kbb --backend sci --classpath "src:test:../kotobase-protocol-core/src:<kotobase>/src" bin/run_tests.cljk
```

`<kotobase>` is a checkout of `kotoba-lang/kotobase`. Nothing under `src/`
requires it — but it is not optional either, and calling it **test-only** (as
this file did until 2026-09-06) was wrong about the classpath: core's
`kotobase.protocols.blocks` requires `kotobase.store`, so anything that loads
this surface needs it present. It arrives through core's own `deps.edn`. The
`:test` alias names it a second time because the suite uses `kotobase.local`'s
LocalStore as its oracle directly.

## Namespaces are unchanged

They are still `kotobase.protocols.*`. Repo name and namespace need not match,
and renaming would break every consumer for no benefit.

**Do not put this repo and the `kotobase-protocols` facade on the same
classpath** — the namespaces collide. Use one or the other.
