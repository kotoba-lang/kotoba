# kotoba-lang/org-w3-nquads

**[RDF 1.1 N-Quads](https://www.w3.org/TR/n-quads/), portable `.cljc`.** Terms and
datasets as data, plus the serialization RDF Dataset Canonicalization hashes over.

First layer of the `-rdfc-` cryptosuite stack: RDFC-1.0 canonicalizes an abstract
dataset and hashes its N-Quads form, so getting these bytes exactly right is a
prerequisite for a canonical hash anybody else agrees with.

## N-Quads has no canonical form; RDFC-1.0 supplies one

The REC defines *serialization, not normalization* — several byte sequences are legal
for the same term. RDFC-1.0 fixes one, and `serialize-*` implements **that** rather
than merely something the grammar accepts:

> in a literal, escape **only** backslash, `"`, newline, carriage return

Tab, form feed and every non-ASCII character are emitted literally as UTF-8. The
grammar would also permit `\t`, `\f`, `\b`, `\'` and `\uXXXX` for those — and that
latitude is exactly why a serializer using them hashes the same graph differently.

Backslash is replaced **first**, or the backslashes introduced by the later
replacements would themselves be escaped.

## Two details that read as trivia and are not

**A blank node label is stored without its `_:` prefix.** The prefix is
serialization; the label is identity. RDFC-1.0 relabels blank nodes, and it relabels
*labels* — not strings that happen to begin with two characters.

**`serialize-dataset` does not sort.** RDFC-1.0 sorts the canonical N-Quads as one of
its own numbered steps, and sorting here would hide whether that step ran.

## Parsing reads what we do not write

RDFC-1.0 has to read documents it did not produce, so the parser handles the full
ECHAR set and both UCHAR forms including surrogate pairs. An unparseable line
**throws** rather than being skipped — silently dropping one loses a triple from the
graph being hashed. Blank lines and `#` comments are skipped.

## Test

```bash
kbb -M:test
kbb -M:lint
kbb --backend sci --classpath src test/nbb_smoke.cljk
```

The `:cljs` branch needs its own run: the reader conditionals decode UCHAR escapes
(`Character/toChars` vs `String.fromCodePoint`), and a host that read a surrogate
pair differently would parse a different graph from the same document — then hash it
differently, which is the failure this layer exists to prevent.

## License

MIT. See `LICENSE`.
