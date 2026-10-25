# ADR 0012: W6 product-shell oracle authority (cloudflare dual-source)

- Status: Accepted
- Date: 2026-07-28

## Context

W6 landed `kotoba/*_core.kotoba` pure-request oracles with KIR parity tests.
Product `cloudflare.*` cljc still reimplemented the same pure helpers. Murakumo
already cut over dual-source authority (#86–#113). Cloudflare product surfaces
need the same thin host wiring so kotoba is SSoT.

## Decision

Ship precompiled KIR under `resources/cloudflare/oracle/`, register them in
`cloudflare.kotoba.oracle`, and wire high-traffic pure helpers on the JVM:

| catalog | host | pure delegates |
|---|---|---|
| `:client` | `cloudflare.client` | api-base, graphql, secret ids, rest-url, query-pair, bearer-auth, transport-ok?, prefer-explicit-token?, secret-name-matches? |
| `:workers-path` | `cloudflare.workers` / `pages` | zone-routes, custom-domains, scripts, pages-projects paths |
| `:zones-path` | `cloudflare.zones` | list-zones path+query, dns-records path, hostname-matches? |
| `:logpush-path` | `cloudflare.logpush` | datasets/jobs/job paths |

Catalog also ships (artifact only; host wiring incremental):

- `:stream`, `:deploy`, `:pages-bulk`, `:analytics`, `:analytics-parse`

### Still host

- `jvm-http-fn` / `rest!` / `graphql!` transport
- JSON encode/decode, `System.getenv`
- deploy validators / multipart / stream validate (next slices)
- cljs resource load

### Regeneration

```bash
kbb -M:test -m cloudflare.kotoba-oracle-gen
```

## Evidence

- `src/cloudflare/kotoba/oracle.cljk`
- `resources/cloudflare/oracle/*.kir.edn`
- `test/cloudflare/kotoba_oracle_authority_test.cljk`
- existing client/path parity tests

## Related

- murakumo product-shell dual-source trail (#86–#113)
- ADR 0010 client kotoba oracle (parity)
- ADRs 0004–0009 path/plan oracles
