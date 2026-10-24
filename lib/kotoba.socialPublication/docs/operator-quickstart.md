# Operator quickstart

For the operator wiring this membrane into an actor. Every command below was run end to end
against `4fa1f48` on 2026-08-30; the transcripts are the real output, not illustrations. If a
step here stops working, the step is wrong — say so rather than working around it locally.

This library produces **drafts that are not posts**. It cannot publish, and it holds no key.
An operator's job is to supply identity and prose, read the refusals, and carry the draft to
whatever signs actor-side.

## 1. Get it

Two coordinates, depending on where you are.

Inside this workspace the repo is a west project at `orgs/kotoba-lang/social-publication`; a
sibling consumer uses `:local/root`. From outside, use the git coordinate — pin the SHA, not a
branch, so the four invariants you audited are the four you get:

```clojure
;; deps.edn
{:deps {io.github.kotoba-lang/social-publication
        {:git/url "https://github.com/kotoba-lang/social-publication"
         :git/sha "4fa1f486e0dbbd4b9013ccace12d8d23d17af203"}}}
```

Verify it resolves and is callable before writing any actor code:

```console
$ kbb -M -e '(require (quote [etzhayyim.social.publication :as pub]))
                 (println (get (pub/draft-observation-post
                                {:actor-id "a" :display-name "A"} "s" "b" ["x" "y"])
                               ":post/status"))'
:dry-run
```

## 2. Run the suite

Do this in the checkout before trusting it. The suite runs on **both** runtimes and prints its
marker only when both are green — the implementation is `.cljc`, so a suite that ran on one
would make portability a claim rather than an observation.

```console
$ kbb --backend sci run_tests.cljk
── JVM (kbb -M:test)
Testing etzhayyim.social.publication-test

Ran 11 tests containing 45 assertions.
0 failures, 0 errors.

── nbb (cljs.test)

Testing etzhayyim.social.publication-test

Ran 11 tests containing 45 assertions.
0 failures, 0 errors.

social-publication: both runtimes green (nbb + JVM)
```

The classpath comes from `nbb.edn`. If you see `Could not find namespace:
etzhayyim.social.publication-test`, that file is missing or you are not in the repo root —
the namespace is present, the classpath is not.

## 3. Draft an observation post

`draft-observation-post` is the direct form. Config is yours; the invariants are not.

```console
$ kbb --backend sci -e '(require (quote [etzhayyim.social.publication :as pub]))
          (println (get (pub/draft-observation-post
                         {:actor-id "fuchi" :display-name "扶持 — Maintainer Sustenance Allocator"}
                         "観測: 依存の維持者が無償である"
                         "3 つの配布物が 1 人の維持者に依存している。"
                         ["https://example.org/a" "https://example.org/b"])
                        ":post/body"))'
【観測ミラー / accountability map — NOT a verdict, NOT advice, 非断定】 扶持 — Maintainer Sustenance Allocator が既知の観測から編んだ事実の要約です。

3 つの配布物が 1 人の維持者に依存している。 出典 2 件。
```

Two things to notice, because both are load-bearing:

- The non-adjudication notice is in **the body a reader sees**, not only in the
  `:post/non-adjudicating-notice` flag. Shortening the prefix is a regression even with the
  flag still true.
- The citation count in the text is the count of *distinct, nonblank* sources, so it cannot
  disagree with `:post/sources`.

`:post/status` is `":dry-run"`, `:post/is-mirror` is `true`, and `:post/server-held-key` is
`false`. There is no argument that changes any of the three.

## 4. Drive the state machine

Actors call `transition-to-drafted`, which takes and returns wire-shaped state — keys are
strings, and so are values that arrived over a wire. It never throws for a policy violation;
it returns a refusal.

```console
$ # (config {:actor-id "fuchi" :display-name "扶持"}, base state
$ #  {"subject" "s" "sources" ["a" "b"] "requested_status" "dry-run"})
two sources, dry-run      -> phase="drafted" payload-empty=false refusal=""
one nonblank source       -> phase="refused" payload-empty=true  refusal="source-provenance: a post needs ≥ 2 distinct citations"
same source twice         -> phase="refused" payload-empty=true  refusal="source-provenance: a post needs ≥ 2 distinct citations"
same source, spaced       -> phase="refused" payload-empty=true  refusal="source-provenance: a post needs ≥ 2 distinct citations"
server key (boolean)      -> phase="refused" payload-empty=true  refusal="no-server-key: server-held-key must be false"
server key (wire string)  -> phase="refused" payload-empty=true  refusal="no-server-key: server-held-key must be false"
requested_status=live     -> phase="refused" payload-empty=true  refusal="R0-gate: only dry-run posts"
status with leading colon -> phase="drafted" payload-empty=false refusal=""
```

Read those eight lines as four rules:

1. **A blank source is not a source.** `["a" "   "]` is one citation, and one is not enough.
2. **The same source twice is one source.** The ≥ 2 threshold exists to say a claim rests on
   more than one origin, so citing one origin twice adds no corroboration — it only makes the
   count look right. Whitespace is not provenance either: `["a" "  a  "]` is also one.
3. **A wire-shaped key is still a key.** `"true"` refuses exactly like `true`. Anything but
   nil/false is treated as a claim to hold a key.
4. **The status the library emits is a status it accepts back.** `":dry-run"` — the form it
   writes into `:post/status` — round-trips. Only a genuinely different status is refused.

Rules 1 and 2 are one function, `distinct-citations`, and both entry points call it — this
one that returns a refusal, and `draft-observation-post`, which throws. When the rule lived in
two places they agreed only by coincidence; a fix to one would have left the other quietly
stale. `the-two-provenance-paths-cannot-drift` in the suite is what keeps them the same.

## 5. A refusal carries no draft

`cell_state` is carried by *you*, not by the library, so a payload from an earlier success is
in the state you hand back. It is dropped on refusal, because a refusal means nothing was
made:

```console
after success   payload-empty= false
after refusal   payload-empty= true   phase= "refused"
```

That sequence — succeed, then resubmit the returned state with `server_held_key` set — is a
real defect that existed here on 2026-08-08: the refusal kept the previous draft, and a caller
that never read `phase` could publish it. If you are writing that caller, read `phase`
anyway. Do not treat a non-empty `payload` as permission.

## 6. Going live is not a flag

There is no live mode to enable. `build-live` exists to refuse, and to tell you what would be
required:

```console
$ kbb --backend sci -e '(require (quote [etzhayyim.social.publication :as pub]))
          (try (pub/build-live {:actor-id "fuchi" :display-name "扶持"})
               (catch :default e (println (pr-str (ex-data e))) (println (ex-message e))))'
{:actor-id "fuchi", :status :refused}
fuchi R0: live social posting is Council Lv6+ + operator + member/actor-signature gated. Only dry-run posts are producible offline; signing happens actor-side, never with a server key.
```

Signing happens actor-side. If your design has this library — or the server it runs on —
holding a key, the design is wrong at that point, not this library.

## 7. What you must supply

`:actor-id` and `:display-name`, both nonblank. The second is not decoration: an accountability
mirror that does not say whose observation it is has no accountability in it, so an
unattributed post is not producible.

```console
$ kbb --backend sci -e '(require (quote [etzhayyim.social.publication :as pub]))
          (try (pub/draft-observation-post {:actor-id "fuchi"} "s" "b" ["a" "b"])
               (catch :default e (println (ex-message e))))'
social publication config requires :display-name
```

Keep actor DIDs, product policy, deployment targets, datasets, and actor-specific prose out of
this repo — they are yours, and this membrane stays actor-neutral so that every actor gets the
same four invariants.

## 8. When you change behaviour here

The invariants are guarded by mutation testing in the superproject's
`scripts/maturity-loop/mutations.edn`, which checks that the tests can still go **red** — a
test that quietly stopped biting stays green forever. Change behaviour and an anchor there will
move; update it rather than deleting it.

```console
$ kbb --backend sci scripts/maturity-loop/run.cljk --only social-publication   # from the superproject root
```
