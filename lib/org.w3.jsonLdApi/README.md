# kotoba-lang/org-w3-json-ld-api

**[JSON-LD 1.1](https://www.w3.org/TR/json-ld11-api/) expansion and RDF conversion, portable `.cljc`.**

Third layer of the `-rdfc-` cryptosuite stack. `org-w3-rdf-canon` canonicalizes an RDF
dataset; a Verifiable Credential is a JSON-LD document, and expansion is what turns its
context-dependent shorthand into the explicit form RDF conversion needs. Without it,
`eddsa-rdfc-2022` has nothing to canonicalize.

Complements `kotoba-lang/json-ld`, which provides EDN-first constructors and says in its
own README that the processor layer belongs elsewhere. This is that layer.

## Contexts are never fetched, and that is a security property

`expand` does no network I/O. A remote `@context` must be supplied in `:contexts`; an
unsupplied one throws `context-not-provided`.

A `@context` decides what every term in a document *means*. A verifier that fetches one
at verification time hands the context's host the power to change what a signature
covers — **after signing, with no key and no detectable tampering**. The document would
still verify, against a different graph. Pinning is the only way the meaning of a signed
document stays fixed, so this library cannot be configured to fetch.

```clojure
(require '[json-ld-api.core :as jld])

(jld/expand credential {:contexts {"https://www.w3.org/ns/credentials/v2" v2-context}})
```

## `expand` is NOT a validator

**30 of the suite's 103 malformed documents are still accepted rather than refused.** A
successful `expand` does not mean the input was valid JSON-LD. Validate separately.

## What refuses rather than guessing

Refused with `unsupported`: `@nest`, `@json` coercion, `@import`, `@propagate`,
`@included`, `@direction`, and the `@container` variants `@index`/`@id`/`@type`.

A processor that quietly ignored `@nest` would return an expansion **missing triples**,
and the caller's next step is to *sign* it — so the failure would surface as a signature
over a graph nobody intended, not as an error.

**Refusals fire at use, not at definition.** A large shared context defines terms a
document never touches; credentials/v2 declares `@json` on `_sd`, `cnf/jwk` and
`jsonSchema`. Refusing when those are merely *defined* made the whole context unusable.

## Measured, and the pass rate is not the useful number

```
official JSON-LD 1.1 expand suite (376 of 385 entries; 9 are 1.0-only)
  positive: 126/273 exact match   (95 refused as unsupported, 13 threw, 39 mismatch, 0 crash)
  negative: 51/103 exact error code (25 accepted that should have been refused)
```

The negative cases assert the spec's own error **code**, not merely that something was
raised. Counts are pinned as a floor, so they can only improve — but a baseline is not
approval, and the gaps print on every run.

What told me this library would refuse **every real Verifiable Credential** was expanding
one, not the pass rate: credentials/v2 puts `@container: @graph` on `proof`, and my
refusals sat at context-processing time. `a-real-verifiable-credential-expands` is the
test that matters, and it checks the datatypes a signature is actually taken over —
`cryptosuiteString`, `multibase`, `xsd:dateTime`, and `proofPurpose` as an IRI.

## The tower, end to end

`json-ld-api.to-rdf` (§7) turns expanded JSON-LD into statements in `nquads.core`
shape — the form `rdf-canon` consumes directly, with no serialization in between, so
no spelling difference can creep in between the layers.

```clojure
(-> credential
    (jld/expand {:contexts {"https://www.w3.org/ns/credentials/v2" v2}})
    (tordf/to-rdf)
    (c14n/canonical-hash))          ;=> the 64 hex chars eddsa-rdfc-2022 signs
```

A real credential now reaches a stable canonical hash, and the test prints the exact
bytes:

```
<did:web:example.com:alice> <https://schema.org/name> "Alice" .
<urn:uuid:0c07c1ce> <…22-rdf-syntax-ns#type> <…credentials#VerifiableCredential> .
<urn:uuid:0c07c1ce> <…credentials#credentialSubject> <did:web:example.com:alice> .
<urn:uuid:0c07c1ce> <…credentials#issuer> <did:web:hooks.itonami.cloud:orgs:acme> .
<urn:uuid:0c07c1ce> <…credentials#validFrom> "2026-07-31T00:00:00Z"^^<…XMLSchema#dateTime> .
```

The hash is stable across JSON key order and changes when a value changes — the
property that makes signing canonical RDF meaningful at all.

### Numbers are where §7 bites

A JSON number has no datatype; RDF demands one. An integral value becomes
`xsd:integer`; anything else becomes `xsd:double` in **XSD canonical form** — `1.0E0`,
not `1.0` or `1e+0`. The form is mandatory, not cosmetic: the string is what gets
hashed, so `1.0` and `1.0E0` are different signatures over the same number. The two
hosts disagree natively (JVM `1.0E0`, JavaScript `1e+0`), so it is assembled by hand.

### What §7 drops, and what that costs

A relative IRI in any position, and a blank node as predicate (unless
`:produce-generalized-rdf?`). Dropping is the spec's instruction, but it means **the
RDF is not always a faithful image of the JSON-LD** — a document can lose statements
here and still sign cleanly. A signature over canonical RDF attests to the *dataset*,
not to the JSON that produced it.

```
official JSON-LD 1.1 toRdf suite (456 of 467 entries; 11 are 1.0-only)
  positive: 158/340 same graph   (97 refused as unsupported, 20 threw, 65 mismatch, 0 crash)
  negative:  51/100 exact error code (22 accepted that should have been refused)
  syntax:    16/16 converted
```

These run expansion *and* conversion, so they are a joint measure. Comparison is on
the **canonical form of both sides** — raw N-Quads text would differ on blank node
labels and statement order, neither of which carries meaning.

## Both hosts, because a number's spelling gets signed

`to-rdf` turns a JSON number into an RDF literal, and the two hosts disagree
natively: the JVM writes `1.0E0` where JavaScript writes `1e+0`. XSD canonical form
is the former, and the string is what gets hashed — so a divergence would mean a
credential signed on one host does not verify on the other, with nothing to notice.

`test/nbb_smoke.cljk` pins the same lexical forms the JVM suite measures (`1.5E0`,
`1.0E-1`, `3.14159265358979E0`, `1.0E21`, and the 1e21 integer/double boundary) and
runs in CI. They agree — but before that file existed, nothing here was verified on
`:cljs` at all.

## Test

```bash
kbb -M:test     # includes the whole official suite, no network
kbb -M:lint
npm run smoke       # the nbb host, same values pinned
```

Measured 2026-09-25 (126 / 158 after the §5.3.2 string-only coercion fix), and this is a known gap in the runner rather than in the
library: since the `.cljk` rename, the JVM runner finds **0 test namespaces** (it
exits 0 having run nothing), and `kbb -M:test` stops at `clojure.java.io`, which the
suites use to read fixtures. The counts above were taken by running both suites
unchanged except for host shims (fixture reads through `fs`, `catch :default`, a
`%d`/`%s` format) on the kbb engine. A green `kbb -M:test` or JVM run is therefore
not evidence until the fixture reads are host-neutral.

## License

MIT. See `LICENSE`.
