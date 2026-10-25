# Contributing

`kotobase-commoncrawl-actor` accepts contributions to the OSS actor, policy
tests, seed-list tooling, and documentation.

## Development

```bash
kbb -M:dev:test
kbb -M:lint
kbb -M:dev:run   # offline demo (commoncrawl.sim)
```

Keep changes small and include tests for the Governor (seed-scope/exclude/
budget), the fetch/advise/commit path, and the store/loop durability
properties (lease, cursor, budget).

## Rules

- Do not commit real CACAO seeds/identities (`.commoncrawl/` is gitignored —
  keep it that way).
- Do not widen the effective fetch scope anywhere except
  `resources/seeds.edn` / `commoncrawl.seeds/embedded-seeds` — no
  keyword/industry-wide discovery, no bypassing `commoncrawl.policy`'s
  seed-scope check.
- Keep every network/gzip capability injected (`http-fn`/`warc-fetch-fn`/
  `complete-fn`/`embed-fn`) so the core stays testable offline — real IO only
  lives in `commoncrawl.live-http`.
- Do not raise the default per-tick fetch budget without discussing the
  operational impact on Common Crawl and net-kotobase.

## Pull Requests

PRs should describe:

- what behavior changed
- which Governor rule (if any) is affected
- how it was tested (offline fixtures vs. a real tick run)
- whether `docs/` needs updates
