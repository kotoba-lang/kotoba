# kotoba-lang/org-ietf-ers

**[RFC 4998](https://www.rfc-editor.org/rfc/rfc4998.html) Evidence Record
Syntax** — the reduced hash tree and the renewals that keep it meaningful after
its own cryptography ages. Portable `.cljc` on `org-ietf-rfc3161`.

```clojure
(require '[ers.core :as ers] '[cms.jvm :as jvm])

(def tree (ers/build-tree jvm/digest :sha256 leaf-digests))
;; timestamp (:root tree) with a TSA, then keep only one document's path:
(ers/reduced-path tree 7)

(ers/verify record leaf-digest {:digest-fn jvm/digest :verify-fn jvm/verify})
;=> {:verified true :trusted :unknown :oldest "2026-07-30T13:57:58Z" …}
```

## The problem it solves, which is not the one signatures solve

A signature proves who agreed; a timestamp proves when. Neither survives time —
the TSA's certificate expires, its algorithm weakens, and today's SHA-256 is
tomorrow's SHA-1. A Japanese retention obligation runs seven to ten years and
the evidence has to still mean something at the end of it.

## Two renewals, and they are not the same operation

| | covers | needs the original data | cost |
|---|---|---|---|
| **timestamp renewal** (§5.2) | the previous **token** | no | one token per archive |
| **hash renewal** (§5.3) | `digest_new(data) ‖ digest_new(previous chain)` | **yes** | re-hash everything |

**A hash renewal that does not re-hash the original data is not a hash
renewal.** It carries the new algorithm's name over the old algorithm's digests
and claims a strength it does not have. `hash-renewal-digest` refuses without
the data, and `verify` reports `:hash-renewal-needs-data` rather than skipping
the chain.

A timestamp renewal appends to the current chain; a hash renewal starts a **new
chain**, because from that point the digests are computed differently.

## Sorted concatenation

§4.2: a node's hash is over its children's hashes **sorted, then concatenated**.
Sorted, so a verifier does not need to know which sibling was on the left —
which is what lets one document's path travel without the other 999,999.

Skip the sort and verification depends on reconstructing an order the record
does not carry: it passes for records you built and fails for everyone else's,
in a way self-consistent tests never catch. So the suite checks the root against
a **nine-line Python script** applying the rule independently.

An odd node is **promoted, not duplicated** — pairing it with a copy of itself
would make two archives differing only in their last document produce the same
root.

## `:oldest` is the claim

An evidence record proves the data existed before the **earliest** verified
timestamp. Later ones exist to keep the older ones checkable, not to move the
date forward.

`:trusted` stays `:unknown` unless every TSA was vouched for — `rfc3161.core`
keeps `:verified` and `:trusted` apart and this does not undo it.

## The tree is the storage index

In a content-addressed store each node is named by its own digest, so the path
is not overhead. That is the one place decentralised storage genuinely helps an
evidence record — availability and tamper-evidence of the hash tree, which is a
different claim from legal validity and should not be confused with it.

## Test

```bash
kbb -M:test    # tree root vs an independent implementation; real openssl ts tokens
kbb -M:lint
```

Apache-2.0.
