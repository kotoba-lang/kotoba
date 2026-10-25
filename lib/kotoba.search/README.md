# search

[![CI](https://github.com/kotoba-lang/search/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/search/actions/workflows/ci.yml)

Portable CLJC model for kotoba-lang/search.

`search.model` scores a small in-memory document map (O(corpus)).
`search.postings` is the :search serving plane: term → sorted doc-ids,
AND by intersection, rebuildable from documents or datoms. Query cost is
posting length, not corpus size.

Pages editor: https://kotoba-lang.github.io/search/

The Pages UI is local to kotoba-lang and does not redirect to external hosts.

## Test

```bash
kbb -M:test
```

## Kotoba bounded profile

Two capability-free kernels, compiled by `amu` and verified by RUNNING the
artifact on both backends (`js-browser` and `wasm32`), not by compiling it.

`src/search/bounded_index.kotoba` ports `search.model`'s index **structure**
— the name-keyed document registry (doc-id → `{:title :body}` record) and the
closed field-weight table — as the canonical bounded typed-map (`[:map :string
[:record …]]`, ≤31 entries) plus closed keyword membership.
See [migration/bounded-index-and-weights-v1.edn](migration/bounded-index-and-weights-v1.edn).

`src/search/bounded_search.kotoba` ports the **search machinery**: the
tokenizer (a-z0-9 plus the Japanese ranges `\u3040-\u30ff` and
`\u3400-\u9fff`, with each CJK run replaced by its overlapping bigrams),
`term-count`, and `score-doc` over the closed weight table. It is
parity-tested against the `.cljc` oracle
([test/search/bounded_search_kotoba_parity_test.cljk](test/search/bounded_search_kotoba_parity_test.cljk))
and has its own self-check, which returns **failures × 1000 + checks-run** —
a count, never a boolean, because a boolean cannot tell one regression apart
from a build that ran nothing. Both backends answer `52`.
See [migration/bounded-search-machinery-v1.edn](migration/bounded-search-machinery-v1.edn).

```bash
kbb -M:kotoba compile src/search/bounded_search.kotoba \
  --target js-browser --output target/bs.mjs  --fuel 8192
kbb -M:kotoba compile src/search/bounded_search.kotoba \
  --target wasm32     --output target/bs.wasm --fuel 8192
node scripts/verify-bounded-search.mjs target/bs.mjs target/bs.wasm \
  <amu-checkout>/runtime/browser-host.mjs
```

Two things this port measured, both of which were previously recorded as
blockers and are no longer:

* **`string-code-point-at` exists.** This README used to say the tokenizer
  "needs a per-code-point string primitive the compiler does not yet expose".
  That was an implementation state written without a date, and it went stale:
  the primitive is an admitted language builtin and lowers on both targets
  (amu `9092ee34`). It genuinely was rejected by the amu pin this repo
  carried (`f6ee539e`, "operation has no admitted lowering"), so `deps.edn`'s
  `:kotoba` pin was moved forward with that reason beside it.
* **What still cannot be written**, measured rather than assumed: this backend
  admits no readable collection of strings, so `tokenize` cannot return a
  vector of tokens and `search` cannot return a sorted document list. The
  kernel exposes the **indexed** face instead (`token-count`, and
  `token-start` / `token-end` / `token-text` for the nth token) — the shape
  `bounded-text`'s `segment-text` / `segment-count-text` already use for
  split. `search` stays the CLJC oracle.

`score-doc` returns `[:result :i64 :string]` and **refuses** on `U+0130` and
`U+212A`, the only two non-ASCII code points that lower-case into `[a-z0-9]`
(enumerated over all of Unicode on both hosts) and therefore the only inputs
where the kernel's ASCII-only fold can disagree with the oracle. A score of
`0` is a real answer; a refusal must never be readable as one.
