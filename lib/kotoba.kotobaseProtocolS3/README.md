# kotobase-protocol-s3

**S3-compatible object surface for kotobase.** PUT/GET/HEAD/DELETE object plus ListObjectsV2 (XML).

Split out of [`kotobase-protocols`](https://github.com/kotoba-lang/kotobase-protocols)
by superproject ADR-2608051000 (`1 repo = 1 capability`), from that repo's
`main` tip.

The handler is a **pure cljc function** over an injected plain operation map —
`(handle ctx req) → resp`. No network I/O, no host JSON, no crypto dependency.
Authentication and transport belong to the deploy shell.

## Dependencies

[`kotobase-protocol-core`](https://github.com/kotoba-lang/kotobase-protocol-core)
for the hash helper and the HTTP shapes, and
[`kotobase`](https://github.com/kotoba-lang/kotobase) for `kotobase.store` —
the `IStore` protocol `src/` calls directly. Both are declared in `deps.edn`;
until 2026-09-06 neither was, and this section said "and nothing else".

**This repo does not depend on the other surface repos, and they do not depend
on it** — that separation is the point of the split; the registry router in
core is what composes them when a deployment wants more than one.

## Test

```bash
kbb --backend sci --classpath "src:test:../kotobase-protocol-core/src:<kotobase>/src" bin/run_tests.cljk
```

`<kotobase>` is a checkout of `kotoba-lang/kotobase`. It is **not** test-only,
whatever this file said until 2026-09-06 — `src/` requires `kotobase.store`,
and has done since the 11:46 JST re-split on 2026-08-05 (`45a1e2a`). The suite
additionally uses `kotobase.local`'s LocalStore as its oracle, which is why the
checkout is needed either way.

## Namespaces are unchanged

They are still `kotobase.protocols.*`. Repo name and namespace need not match,
and renaming would break every consumer for no benefit.

**Do not put this repo and the `kotobase-protocols` facade on the same
classpath** — the namespaces collide. Use one or the other.
