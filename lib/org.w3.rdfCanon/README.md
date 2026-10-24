# kotoba-lang/org-w3-rdf-canon

**[RDF Dataset Canonicalization (RDFC-1.0)](https://www.w3.org/TR/rdf-canon/), portable `.cljc`.**

Second layer of the `-rdfc-` cryptosuite stack. `org-w3-nquads` fixes the bytes for a
term; this fixes which **blank node labels** those bytes carry, so two parties holding
the same graph produce the same hash even though blank node labels are arbitrary.

## Complete, including N-degree hashing

All of §4.4.3 is implemented: first-degree hashing (§4.6), Hash Related Blank Node
(§4.7), and the Hash N-Degree Quads algorithm (§4.8) that resolves blank nodes
*sharing* a first-degree hash by exploring the graph around them.

N-degree hashing is where the cost lives. When two blank nodes cannot be told apart
by their own quads, RDFC-1.0 distinguishes them by the shortest "gossip path" through
their neighbours, and finds it by trying **every permutation** of the related nodes at
each step, recursing as it goes. That is factorial work.

## The work limit is a spec requirement, not a nicety

§4.4.3 says implementations **MUST** defend against denial of service "by raising
suitable exceptions and terminating early", and the Security Considerations suggest
exactly "a configurable limit on the number of iterations… particularly recursive
steps and permutations of long lists".

So every N-degree call and permutation examined draws down `:max-work`; exhausting it
throws `:rdf-canon/work-limit-exceeded`. The margin is **measured, not guessed**:

| | work units |
|---|---|
| heaviest legitimate vector in the suite (`test044`/`045`/`046`) | 3,348 |
| next heaviest of the other 61 | 54 |
| the 10-node clique (`test074`) | exceeds 2,000,000 |
| default `:max-work` | 100,000 |

The distribution is sharply bimodal, so the default sits ~30x above every real
document while still refusing the attack promptly. Raise it if you own the input;
do not raise it for input from strangers, which is the case it exists for.

## Hash algorithm

SHA-256 by default; `{:hash-algorithm :sha384}` selects the OPTIONAL variant the spec
names and the suite covers (`test075`). The digest is threaded through every layer
rather than hardcoded, because the first-degree and related-node hashes feed the final
one — mixing algorithms between layers would produce a hash nobody else computes.

## Correctness is measured, not asserted

`test/fixtures/rdfc10/` holds the **entire official W3C test suite**, committed so the
suite needs no network:

```
official RDFC-1.0 eval vectors: 64/64 byte-identical to W3C
official RDFC-1.0 map vectors:  21/21 identical to W3C
the poison clique (test074):    refused, as a negative test requires
```

The map tests are separate because a canonical form can be right while the
input-label → canonical-label map is wrong.

Both hosts are checked: `kbb -M:test` on the JVM and `npm run smoke` on nbb, with
the same canonical forms and hash strings pinned in both. This namespace has three
reader conditionals a hash depends on — byte encoding, hex formatting and the code
point walk — so a host that differed in any of them would compute a different
canonical hash for the same graph.

The assertion that matters is that **nothing produces a wrong canonical form** — a
mismatch would be worse than a refusal. A canonicalizer that only agreed with itself
would be worthless; the whole point is that two independent parties produce the same
bytes.

## Code point order, not UTF-16 order

§4.4.3 orders in **code point** order. A JVM string compare is UTF-16 **code unit**
order, and they differ for supplementary characters: a surrogate pair leads with
0xD800–0xDBFF, so it sorts *before* U+E000 under code units and *after* it under code
points.

This is the **opposite** requirement to RFC 8785 JCS, which explicitly wants UTF-16
code unit order for property names. Two specs, two orders — using one library's
comparator for the other's job is a silent interoperability bug, so
`compare-code-points` implements the specified order rather than the convenient one.

## A correction worth recording

The first version of the sibling `org-w3-nquads` escaped only four characters in a
literal and carried a test asserting that tab and form feed are *not* escaped. Every
test in that repo agreed with it, and it was wrong: canonical N-Triples requires seven
ECHARs plus UCHAR for several ranges, and an IRIREF admits UCHAR too.

W3C's own escaping vector — `test060`, run from here — is what disproved it. That is
the whole argument for validating against someone else's expected bytes: a
self-consistent implementation passes its own tests no matter how wrong it is.

## Test

```bash
kbb -M:dev:test     # JVM, the whole official suite
kbb -M:lint
npm install && npm run smoke   # the nbb host, same values pinned
```

## License

MIT. See `LICENSE`.
