# kotoba-lang/text

[![CI](https://github.com/kotoba-lang/text/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/text/actions/workflows/ci.yml)

**String / regex / unicode helpers** — the foundational-stdlib gap every other
lib re-rolls (`json`, `lint`, `time` hand-roll string ops). Zero third-party
deps; every namespace is `.cljk` (formerly `.cljc`; JVM / SCI / ClojureScript / GraalVM /
kotoba-WASM). `kotoba.lang.bounded-regex` is a bounded, backtracking-free regex engine a
`.kotoba` guest can call; the `.cljk` wrappers below still use the host's
`#"..."` as the general oracle. Pure string ops are portable. See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Three names, one library

`kotoba.lang.text` is the implementation. **`kotoba.text` and `kotoba.string`
are aliases of it** — every var in them IS the var in `kotoba.lang.text`, not a
copy (owner decision, 2026-09-08).

Three names existed because two places already pointed at two of them and
neither pointed at the third:

| name | what pointed at it before this |
|---|---|
| `kotoba.lang.text` | the implementation, and the only one that resolved |
| `kotoba.text` | root ADR-2609040930's replacement-router table routes `clojure.string` here — **it did not exist** |
| `kotoba.string` | the guest `.kotoba` plane in `kotoba-lang/kotoba-lang`, where the owner named it canonical |

Retiring two of the three would have meant rewriting call sites that are not
wrong. So they alias, and the router's row is now true rather than aspirational.

An alias list written by hand goes stale silently — someone adds a function to
the canonical namespace, nobody adds it to the aliases, and the aliases become
a subset that still passes every test anyone runs. So it is checked, not
trusted: `kotoba.lang.text-alias-test` asserts on the JVM that the public
surface of each alias is EXACTLY the canonical surface and that each var is
`identical?` to its canonical var. Deleting one `def` makes it say
`kotoba.text is missing (truncate)`; re-implementing one instead of aliasing it
makes it say `kotoba.string/upper is a COPY`. Both were measured, not assumed.
ClojureScript has no runtime var reflection, so the portable half calls each
name through all three namespaces and requires the three answers to agree.

The aliases carry no docstrings or arglists: `def` copies the value, not the
metadata. The documentation lives at `kotoba.lang.text`.

## Current surface

`kotoba.lang.text`:

- `split` / `split-lines` / `join` — tokenize / assemble
- `trim` / `triml` / `trimr` — whitespace trimming
- `upper` / `lower` / `capitalize` — case
- `starts-with?` / `ends-with?` / `includes?` — predicates
- `replace` / `replace-first` — regex substitution
- `re-find` / `re-matches` / `re-seq` — host regex (thin, portable wrappers)
- `format` — printf-style (`%s %d`) via a pure impl (no `String/format` — WASM-safe)
- `codepoints` / `from-codepoints` — unicode codepoint seqs (portable)
- `pad-left` / `pad-right` — padding
- `truncate` — truncate with optional ellipsis
- `blank?` / `index-of` / `last-index-of` / `reverse` / `trim-newline` — the
  last clojure.string primitives callers had to reach for `clojure.string` for
- kernel oracles — `trim-text` / `triml-text` / `trimr-text` / `blank-text?` /
  `reverse-text` / `repeat-text` / `index-of-text` / `last-index-of-text` /
  `pad-left-text` / `pad-right-text`: the CLJC oracle for the same operations
  as the `.kotoba` kernel, with the divergences the kernel names (UTF-8 byte
  offsets, ASCII whitespace class, code-point-safe reversal)
- tranche-2 oracles — `replace-first-text` (literal match, not regex) /
  `trim-newline-text` / `segment-text` / `segment-count-text` (the
  slice-and-count face of a separator; no collection return needed) /
  `pad-center-text`

## Regex, in the guest

`kotoba.lang.bounded-regex` (`src/kotoba/lang/bounded_regex.kotoba`) is a
regex engine a `.kotoba` guest can actually call. Until it existed, every
regex operation in this repo went through the host's `#"..."`, so a guest had
none at all.

Its absence was never a security decision. Root ADR-2608650000 classifies
regex as `:not-yet-implemented`: it is in neither `:forbidden-heads` nor
`lang/surface-status.edn`, and the one place `:regex` does appear --
`lang/value-codec.edn`'s `:rejected-closed` -- says a compiled pattern cannot
be transferred as a *value*, which is an encoding decision. A pattern here is
a `:string` argument, so nothing new has to become encodable.

What *is* a real constraint is backtracking, and it is met structurally rather
than by a budget: the subset is group-free, so a branch is a linear chain of
pieces, the state set is a bitmask in one `i64`, and one input code point
advances all of it in a single forward walk. There is no backtracking stack to
add. `O(n * m)` with `m <= 60` pieces per branch.

| export | answer |
|---|---|
| `regex-valid?` | is this pattern inside the subset |
| `regex-contains` | 1 / 0, one pass, `O(n * m)` -- the question grep asks |
| `regex-match` | 1 / 0 for the whole input |
| `regex-find-index` | leftmost match start in BYTES, or -1 |
| `regex-match-end` | just past the longest match anchored at an offset, or -1 |
| `regex-count` | non-overlapping matches |

Supported: literals, `.`, `[...]` with ranges and negation, `\d \D \w \W
\s \S \n \t \r` and escaped literals, `* + ?`, `^` and `$`, and top-level
`|`. Refused -- as the error arm of `[:result :i64 :string]`, never as a `0`
that would read like "no match": groups, backreferences, `{n,m}`, lookaround,
non-greedy. Named divergences: `[]]` matches `]` (POSIX, grep and Python
agree; JavaScript is the outlier), alternation is leftmost-longest, and the
character classes are ASCII.

Verify it by running the compiled artifact against the host's own RegExp:

```bash
node <amu>/bin/amu compile src/kotoba/lang/bounded_regex.kotoba \
  --target web --policy scripts/bounded-regex-policy.edn --output /tmp/re.mjs
kbb --backend sci scripts/verify-bounded-regex.cljk /tmp/re.mjs
```

Exit 0 clean, 1 findings, 2 refused. The kernel's own `main` answers
`failures * 1000 + checks-run`, so a build that ran nothing answers 0 rather
than looking like a pass. Measured 2026-09-08 at amu `9092ee34`: compiles on
both `web` and `wasm32`, self-check 47, 3901 comparisons clean. See
`migration/bounded-regex-v1.edn` for the evidence, the divergences, and the
measured backend cost that is *not* in this module.

`kotoba.lang.bounded-text` is the sovereign `.kotoba` kernel for the bounded
portable subset used during CLJC migration: contains, starts/ends-with,
replace-all, case-fold, (2026-09-04) trim/triml/trimr, blank?,
reverse, repeat, index-of/last-index-of, both pads, replace-first,
trim-newline, segment-text/segment-count-text, and pad-center — each composed
from the language's string builtins (`string-code-point-at`,
`string-substring`, `string-concat`, …), no new compiler operation.
join-text is deferred with a measured reason (no readable string collection
on wasm32; see the migration record). The CLJC namespace remains the general
oracle for regex, collection-returning split, Unicode construction,
formatting, upper/capitalize, and general-case trimming until those surfaces
have bounded compiler contracts — upper/capitalize landed as the
`string-upper` LANGUAGE operation the same day. See
`migration/bounded-text-v1.edn`.

## Install

```clojure
io.github.kotoba-lang/text {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.text :as text])

(text/split "a,b,c" #",")            ;=> ["a" "b" "c"]
(text/trim "  hi  ")                 ;=> "hi"
(text/capitalize "hello")            ;=> "Hello"
(text/format "%s = %d" ["x" 42])     ;=> "x = 42"
(text/codepoints "ab")               ;=> [97 98]
(text/truncate "hello world" 8 "..."));=> "hello..."
```

## Verify

```sh
kbb -M:test
```
