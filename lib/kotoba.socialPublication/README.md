# com-etzhayyim-social-publication

Actor-neutral Clojure/CLJC membrane for dry-run social observations.

Canonical repository metadata is in `library.edn`. Actors provide identity and display text as
configuration while the library owns source provenance, non-adjudication, no-server-key, and
dry-run-only invariants.

```clojure
(require '[etzhayyim.social.publication :as publication])

(publication/draft-observation-post
 {:actor-id "fuchi" :display-name "扶持 — Maintainer Sustenance Allocator"}
 "subject"
 "observed body"
 ["source-a" "source-b"])
```

## Operator quickstart

`docs/operator-quickstart.md` walks the whole membrane end to end — resolving the dependency,
running the suite, drafting a post, and reading each of the four refusals — with the real
transcripts from a checkout.

## Tests

```bash
kbb --backend sci run_tests.cljk
```

The classpath comes from `nbb.edn`; without it the namespace does not resolve.

Runs the same suite on both runtimes — nbb (first-class in this workspace) and
`kbb -M:test` — and reports green only when both are. The implementation is `.cljc`, so a
suite that runs on one runtime would let a JVM-only regression through unseen.

Beyond the happy path the suite pins: the non-adjudication notice reaches the reader's text and
not just the `:post/non-adjudicating-notice` flag; blank citations count toward neither the
two-source threshold nor the recorded provenance; the same source cited twice is one source,
so a post cannot claim two-source corroboration it does not have; a wire-shaped (string)
`server_held_key` is still a server key; the `":dry-run"` status the library emits is one it
accepts back; a refusal carries no draft, including one left behind by an earlier success; and
an actor with no display name cannot produce an unattributed mirror post.

It also pins that the two provenance entry points agree. The rule is one function,
`distinct-citations`; `draft-observation-post` throws on a violation and `transition-to-drafted`
returns a refusal, but they must decide the same way. When the rule lived in both places it
held only by coincidence — and if only the state machine had stayed stale, an input it let
through would have thrown out of a function whose contract is to return a refusal.

Each of those is backed by a mutation in the superproject's
`scripts/maturity-loop/mutations.edn`, so the assertions are re-checked for whether they can
still go red.
