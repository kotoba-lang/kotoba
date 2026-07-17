# ADR — Security kaizen 2026-07-17: fail-closed host, HTTP allowlist, cap consume

Status: **Accepted · implemented**
Date: 2026-07-17
Scope: `kotoba-lang/kotoba` (runtime/host/compiler gates),
`kotoba-lang/kototama` (tender HTTP allowlist),
`kotoba-lang/aiueos` (`net-url-allowed?` enforcement primitive)

## Context

Architecture review AR-2026-07-01 and the 2026-07-17 language security
assessment identified residual holes. Some resource scoping had already
landed on main (`*concrete-cap*` / `resource-permitted?`); this kaizen
closes the remaining fail-open defaults and least-privilege gaps.

## Decision

### 1. Fail-closed kgraph host

`kgraph-host-functions` 1-arg form is guarded with empty policy `{}`
(deny all effects). Explicit unguarded (tests/migration only):

```clojure
(kgraph-host-functions store {:kotoba.wasm/unguarded true})
```

### 2. URL prefix allowlists

- `resource-permitted?` accepts URL/file **prefix** matches for
  `http://` / `https://` / `file:` grant entries.
- `:kotoba.policy/http-require-allowlist true` makes missing network
  resources fail closed.
- Compiler `check` rejects literal URLs outside allowlist
  (`:resource-not-allowed`).

### 3. Runtime cap consume-on-use

`kotoba.cap-table/consume-use!` drops a handle after successful use.
`host-call-with` uses it (S2 defense-in-depth).

### 4. kototama / aiueos

See sibling PRs: `:http-url-allowlist` on tender; `net-url-allowed?` on
aiueos policy.

## Tests

- `test/kotoba/security_kaizen_test.clj`
- `test/kotoba/cap_table_test.clj` (`consume-use-drops-handle-after-one-success`)

## Non-claims

Side channels, formal verification, FIPS, PQC production, and complete
signer lifecycle remain non-claims.
