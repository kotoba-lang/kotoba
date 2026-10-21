# kotoba-lang/fmt

[![CI](https://github.com/kotoba-lang/fmt/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/fmt/actions/workflows/ci.yml)

**Layer 4 (tooling) of the kotoba foundational stdlib** — a deterministic EDN
formatter. Reads EDN, re-emits it with canonical whitespace/indentation so the
same data always yields the same text — the rustfmt / dprint equivalent for
kotoba/EDN source. No third-party deps; every namespace is `.cljc` (JVM / SCI /
ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Current surface

`kotoba.lang.fmt`:

- `format` — EDN string → canonical EDN string (parse → re-emit)
- `format-str` — Clojure data → canonical EDN string (emit)
- `pprint` / `pprint-str` — same emit engine, aimed at human-facing value
  inspection rather than source-text canonicalization (see below)
- options: `:indent` (default 2), `:margin` (line width before force-break)

The emitter prints collections with one element per line when they exceed
`:margin`, otherwise inline. Map keys are kept in insertion order (EDN is
order-preserving on read), not sorted — canonicalization of key order is a
separate concern (see `dag-cbor` for content-addressed sorting).

## Install

```clojure
io.github.kotoba-lang/fmt {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.fmt :as fmt])

(fmt/format "{:a 1,    :b [2 3 4 5 6 7 8 9 10]}")
;;=> a multi-line, indented canonical form
(fmt/format-str {:a 1 :b [2 3]})
```

## `pprint` / `pprint-str`

`adr-2809061500-clojure-namespace-to-kotoba-stdlib` names `clojure.pprint`
(183 require sites workspace-wide — the lowest-usage of the eight namespaces
the ADR covers) as a gap, and asks: does the *spirit* of this namespace
(`format-str`'s job — take an in-memory value, emit an indented,
margin-wrapped string) match closely enough with the *letter* of it
(`clojure.pprint`'s actual name and call shape) to extend here, or is it a
different enough job that it needs its own repository?

It's the same job. `format-str` already takes arbitrary Clojure/EDN data —
not source text — and renders it through the recursive `emit` above with the
same `:indent`/`:margin` line-wrapping rules `format` uses for source
canonicalization. There is no second data model, no second traversal, no
second wrapping algorithm to keep in sync — `pprint-str` **is** `format-str`,
exposed under the name a caller reaches for when the job is "print this
value so a human can read it" (`clojure.pprint`'s job) instead of
"canonicalize this source text" (`format`'s job). `pprint` is `pprint-str`
followed by `println`.

```clojure
(fmt/pprint-str {:a 1 :b [2 3]})       ;=> "{:a 1, :b [2 3]}"
(fmt/pprint {:a 1 :b [2 3]})           ; prints "{:a 1, :b [2 3]}\n" to stdout

;; the (with-out-str (pprint x)) idiom real callers reach for becomes direct:
(fmt/pprint-str big-nested-map)        ; a string, no with-out-str needed
```

This is a *different* situation from `kotoba-lang/strfmt`, which explicitly
disclaims being confused with this repository (`fmt`) despite sharing three
letters — `strfmt` implements printf-style directive substitution (`%x`,
`%04d`, ...), a genuinely different algorithm over a genuinely different
input (a format string plus positional args, not a data structure). `pprint`
here is not a different algorithm wearing a similar name; it is this
repository's own existing engine wearing the name its new callers expect.

### What this covers of `clojure.pprint`

- pretty-printing of EDN values: maps, vectors, sets, seqs (Clojure `list`),
  and scalars (nil, booleans, numbers, strings, chars, keywords, symbols)
- deterministic indentation and margin-based line-wrapping (a collection
  prints inline if it fits under `:margin`, one child per line otherwise —
  the exact same rule `format`/`format-str` already use)
- both the print-to-stdout (`pprint`) and return-a-string (`pprint-str`)
  forms real `clojure.pprint` callers use (`pprint-str` is what
  `(with-out-str (pprint x))` is usually reached for)

### What this deliberately does not attempt

- **No column-alignment / miser-mode tricks.** Real `clojure.pprint` tracks a
  right margin and a separate "miser width" and can align nested forms in
  ways sensitive to exactly how much horizontal room is left at the point of
  printing. This emitter has exactly one decision per collection — "does its
  *inline* rendering fit under `:margin` at this depth" — and does not
  otherwise adjust layout based on sibling content.
- **No custom dispatch / `print-method` extension mechanism.** Real
  `clojure.pprint` has `*print-pprint-dispatch*`, `simple-dispatch`,
  `code-dispatch`, and lets callers register how their own types print. This
  emitter has one fixed `cond` over Clojure's built-in collection/scalar
  types; anything else (records, `deftype`, functions, atoms, refs,
  exceptions, ...) falls through to `(str x)`, which is *not* guaranteed to
  be valid, readable EDN. That fallback is inherited unchanged from
  `format-str` — it was never in scope for canonicalizing source text either.
- **No `cl-format`.** `clojure.pprint` also ships a whole Common Lisp
  `format`-style directive language (`~a`, `~d`, `~{...~}`, ...). Out of
  scope; `kotoba-lang/strfmt` is the (unrelated, printf-style) directive
  formatter this workspace already has.
- **No `*print-length*` / `*print-level*` truncation.** Deeply nested or long
  collections are rendered in full, one line per element once `:margin` is
  exceeded — there is no depth or element-count cap that elides output with
  `...`.
- **No table/columnar pretty-printing** (`print-table` has no equivalent
  here).
- **Map key order is insertion order, not alphabetical**, same as
  `format`/`format-str` — `clojure.pprint` does not sort map keys either, so
  this is not a divergence, just worth restating for `pprint` callers who
  might expect it.

Anything above "not attempted" that a caller actually needs is a reason to
extend this file's `emit`/`fits-margin?` — not to reach for a different
formatting function under the same name.

## Verify

```sh
kbb -M:test                              # JVM
kbb --backend sci --classpath src:test:../text/src run-tests.cljk      # nbb / ClojureScript
```

Both run the **same** `.cljc` suite: `14 tests, 42 assertions, 0 failures`.
