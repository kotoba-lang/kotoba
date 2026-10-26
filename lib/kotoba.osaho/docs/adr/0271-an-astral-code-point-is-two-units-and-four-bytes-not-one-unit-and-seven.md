# 0271 — an astral code point is two UTF-16 units and four UTF-8 bytes, not one unit and seven

Status: accepted
Date: 2026-09-09
Base: `origin/main` `a37577c92d5b60b683c98957f1a07cf3252b3e68`

## Context

`kotoba.kir.value/utf8-index-of!` converts the host's UTF-16 index — what
`.indexOf` answers on both the JVM and ClojureScript — into the UTF-8 byte
offset `string-index-of` is contracted to return (`kotoba-lang`
`lang/guest-grammar.edn`: *"first UTF-8 byte offset of needle in haystack, -1
when absent"*; `lang/surface-status.edn` `:string-index-of {:indexes
:utf8-byte-offsets :not-found -1}`).

It did that by walking the haystack one UTF-16 unit at a time and adding the
UTF-8 width of each. For a code point outside the BMP that is wrong twice over:
the pair is charged 4 bytes at the high surrogate, and then the walk steps onto
the LOW surrogate, which matches no earlier arm and falls through to `:else` —
another 3. Every astral code point before the match added **7**.

`utf8-substring!`, four lines above, has always had this right: its `cond`
yields `[units bytes]` and a high surrogate yields `[2 4]`, so the walk
advances past both units. `utf8-byte-count!` likewise does `(+ index 2)`.
`utf8-index-of!`'s own docstring claimed it walked *"exactly as
utf8-substring! does, so astral and multi-byte prefixes compose"* — which is
the one thing it did not do.

## Measurement

`(string-index-of "𝄞ab" "ab")` — U+1D11E is one code point, two UTF-16 units,
four UTF-8 bytes, so `"ab"` begins at byte 4.

| implementation | answer |
|---|---|
| `kotoba.kir` (this repository, before) | **7** |
| `kotoba-script` JS emitter, executed (`amu compile --target js`) | 4 |
| `kotoba-native` `lower-index-of`, executed through the KIR module | 4 |
| CPython `bytes.index` on the UTF-8 encoding | 4 |

The reference was the one that was wrong, and it was found from the outside:
kotoba-native's string-search suite compares each rewrite against this
interpreter and never writes an expected value down, so the disagreement
surfaced as `(not (= 7 4))` on the row `"𝄞ab" / "ab"` the moment a native
lowering for the operation existed to disagree with it.

## Why nothing caught it

Every multi-byte row this repository had used 2- or 3-byte code points — `"あ"`,
`"日本語"`, `"héllo wörld"` — and the loop handled all of those correctly,
because they are one UTF-16 unit each. The defect needed a surrogate pair, and
no test had one. `index-of-utf8-byte-offsets` even said *"A UTF-16 answer would
say 6"*, naming the wrong answer it was guarding against, and 7 is neither that
one nor the right one.

The blast radius is not only runtime: `lower` folds a pure `:i64` entry through
this evaluator, so a guest whose `main` is a constant `string-index-of` over an
astral literal had the wrong offset **baked into the artifact**.

## Decision

`utf8-index-of!` walks with the same `[units bytes]` pairs `utf8-substring!`
uses. `utf8-byte-count!` has already run over both strings by then, so an
unpaired surrogate on either side is refused before the walk starts and every
high surrogate reached is followed by its low one — which is also why the
host index can only land on a code-point boundary and the loop's `>=` can
never overshoot into the middle of a pair.

`kir_string_index_of_test.cljc` gains the rows that would have caught it: an
astral prefix, two astral prefixes (a fix that skips one unit too few or too
many fails here and not above), an astral code point *after* the match, an
astral needle, and mixed widths on the way to the match. Each is asserted
through `run` and the astral prefix also through `fold`, since the fold is
what reaches an artifact.

## Consequences

- `string-index-of` agrees across all three implementations that have one.
- The three plausible wrong answers for `"𝄞ab" / "ab"` — 7 (this defect), 2
  (a UTF-16 answer), 1 (a code-point answer) — are now separated by a row,
  which the previous rows could not do.
- No API, arity, trap or representation changed. `:cljs` still hands back a
  BigInt.
