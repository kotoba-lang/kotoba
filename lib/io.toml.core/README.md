# kotoba-lang/org-toml

**[TOML v1.0.0](https://toml.io/en/v1.0.0) as a reader, in portable `.cljc`,
with no dependencies.**

A hand-written recursive-descent scanner. TOML is small enough that a parser
combinator library would be more code than the grammar, and this stays a leaf.

```clojure
(require '[toml.reader :as toml])

(toml/read! "[owner]\nname = \"Tom\"\ndob = 1979-05-27T07:32:00Z")
;=> {"owner" {"name" "Tom"
;             "dob" {:toml/offset-date-time "1979-05-27T07:32:00Z"}}}
```

`read` returns `{:status :ok :value m}` or `{:status :error :reason kw :line n
:column n}`; `read!` throws. The reason keywords are contract.

## What a document becomes

| TOML | Clojure |
|---|---|
| table | map, **string** keys |
| array | vector |
| string | string |
| integer | integer |
| float | double, with `:inf` `:-inf` `:nan` for the named values |
| boolean | `true` / `false` |
| offset date-time | `{:toml/offset-date-time "1979-05-27T07:32:00Z"}` |
| local date-time | `{:toml/local-date-time "…"}` |
| local date | `{:toml/local-date "…"}` |
| local time | `{:toml/local-time "…"}` |

**Keys stay strings.** TOML keys may contain anything — `"a.b"` and `""` are
both legal — and keywordising them would lose exactly those.

**The four date-time types are tagged, not parsed into an instant.** TOML's
*local* types carry no offset, so there is no instant to produce, and a
reader that invented one would be choosing a timezone on the caller's behalf.
`kotoba-lang/time` is where that belongs.

**`1.0` is indistinguishable from `1` under ClojureScript.** One numeric type;
the reader takes the float path on both runtimes but the result is an integer
there. That is the host, not this reader. Do not build a wire format on the
difference.

## Writing

Not here. A writer has to decide table layout, key quoting and float
formatting, and every one of those is a policy question that a reader does
not have to answer. Adding one to this repository would double it and make
the round-trip tests look like validation when they would only be checking
the reader against its own writer.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

The document in the suite is **toml.io's own example** verbatim, plus every
form in the grammar and the refusals: duplicate keys, a redefined table,
`[[a]]` after `[a]`, a newline inside an inline table, a lone surrogate in a
`\u` escape, a control character in a string.

Run both. Three things are per-runtime here: `\u`-escape decoding
(`Character/toChars` vs `String.fromCodePoint`), the code-point read in
`control-char?`, and radix parsing (`Long/parseLong` vs `js/parseInt`).

## Two bugs this had, both from the same divergence

**`(nth "abc" 0)` is a `Character` on the JVM and a one-character string
under ClojureScript.** The scanner compares against string literals like
`" "`, so on the JVM *every* comparison was false and the whole reader
failed. Character access now goes through `char-at`, which returns a string
on both. It is the same divergence
`scripts/verify-char-int-coercion.cljs` reports elsewhere in this workspace,
arriving through `nth` rather than `int`.

**`map?` cannot tell an error from the scanner state.** Most readers here
return `[state value]` on success, so a map did mean an error — until one
returned bare state, at which point `read` reported every valid document as
a failure with a nil `:reason`. There is now an explicit `error?`.

Neither survived the first run of the suite, which is the argument for having
written the suite from the specification rather than from the implementation.
