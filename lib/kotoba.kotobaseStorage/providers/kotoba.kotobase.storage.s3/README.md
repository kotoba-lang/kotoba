# kotobase-storage-s3

S3-compatible/R2 adapter for `kotobase-storage`. Immutable blocks are stored
under `blocks/<cid>` and refs under `refs/<name>`. Ref publication uses ETag
`If-Match`/`If-None-Match`.

Block creation is conditional and rejects a CID/bytes collision.
`signed-client` provides AWS Signature Version 4 HTTP requests; `r2-client`
accepts a Worker R2 binding.

## Ranged reads, and the one byte that decides a CAR frame

Both clients can now return `[start, end)` for an object, which is what a
packed block store needs: it has to hold the bytes to parse a CAR frame out
of them (superproject ADR-2608160100).

The contract is **half-open**. The two clients convert differently, and each
conversion is the kind that is right in the head and wrong in the file:

| client | wire form | conversion |
|---|---|---|
| R2 binding | `{offset, length}` | `length = end - start` |
| signed HTTP | `Range: bytes=a-b`, **inclusive** | `b = end - 1` |

One byte too many is the first byte of the *next* frame — a read that parses
and returns the wrong block rather than failing. So both are tested, and
tested by something that can disagree: the R2 conversion against miniflare's
R2 implementation (`test/object_r2.cljk`, with an off-by-one client as the
teeth), and the HTTP header against the request that would leave the process
(`test/object_run.cljk`).

### Measured against a real endpoint, once

miniflare implements the R2 API and the injected-fetch test checks the header
that would leave the process — neither is an endpoint. Two things about the
signed path had therefore never met a real server: whether SigV4 with `range`
among the signed headers is accepted at all rather than 403ing on
canonicalisation, and whether the endpoint returns exactly the bytes asked
for.

`test/b2_range_probe.cljk` answers both. It packs a real CARv2, PUTs it,
ranges one frame back out, checks the returned bytes **parse as that frame**
— a one-byte overshoot still parses, as the wrong block — and deletes the
object.

Measured 2026-08-16 against Backblaze B2 (`s3.us-west-004.backblazeb2.com`):
`Range: bytes=175-227` returned exactly 53 bytes, parsing as the requested
frame with byte-identical contents. **AWS S3 proper has not been probed**;
"S3-compatible" is not one behaviour, which is the same reason
`:conditional-put` defaults to `:unverified` here.

It is an operator-run probe, not a gate: it needs credentials (Keychain
service `b2:ai-gftd-datasets`, resolved by exact name — never enumerated)
and a network, and a fleet node has neither. Same shape as
`probe-conditional-put!`, and for the same reason.

```bash
kbb --backend sci --classpath "src:<io-ipld-car>/src:$(kbb -Spath -M:cljs-test)"     test/b2_range_probe.cljk
```

A `200` answer to a ranged GET means the endpoint **ignored** `Range` and is
returning the whole object. That is refused rather than sliced locally: it
would work quietly for small objects and hit the Worker memory limit on a
large one.

Capabilities follow the client. A binding that can range gets `:range-read`;
a signing client also gets `:range-grant`, because a URL it hands out honours
`Range` too — those are different claims and only the first has a protocol
behind it.

### `signed-client` takes an injected `:fetch`

Not for elegance. The HTTP path had never been executed by any suite — the
tests drive the R2 binding client and an in-repo mock — and the first test to
actually call it found `signed-request` throwing on **every** request: its
`:key` destructuring shadowed `clojure.core/key`, so the object key string
became the sort function for the canonical headers. Fixed, and the path is
now runnable offline, which is the reason it stayed broken.

## "S3-compatible" does not imply a conditional PUT

The ref CAS here is `-read-ref`, compare, conditional PUT. Whether that is a
compare-and-swap or a lost-update generator is a property of the **endpoint**,
not of this code:

| endpoint | conditional PUT | profile |
|---|---|---|
| Cloudflare R2 | `onlyIf.etagMatches`, evaluated by R2 | `:linearizable-ref` |
| AWS S3 | `If-None-Match: *` and `If-Match` on PutObject | `:linearizable-ref` once confirmed for the account in use |
| Backblaze B2 | **none**, on either the native or the S3-compatible API | `:single-writer-ref` |

B2 accepts the PUT and ignores the header. Nothing errors; the write
succeeds; the other writer's commit is simply gone.

So the profile is not a constant. Each client declares what its endpoint
enforces, and an unmarked client is `:unverified` — the only safe default,
because the failure of guessing wrong is silent.

```clojure
(s3/open {:client (s3/r2-client bucket)})           ; :linearizable-ref
(s3/open {:client (s3/signed-client cfg)})          ; :single-writer-ref
(s3/open {:client (assoc (s3/signed-client cfg)     ; :linearizable-ref, on your word
                         :conditional-put :verified)})

(s3/open {:client (s3/signed-client cfg)            ; throws
          :require-linearizable? true})
```

Set `:require-linearizable? true` wherever more than one writer touches a
ref. The alternative is learning the endpoint's behaviour from a missing
commit.

An earlier version of this adapter declared `:linearizable-ref`
unconditionally, for any endpoint. The older production code in
`kotobase-peer` already had this right — it fails closed behind
`MERKLE_S3_CONDITIONAL_HEAD`, noted "only for a backend with conditional
PutObject" — and this is that discipline, made executable rather than left
to a comment.

## Probe instead of asserting

```clojure
(s3/probe-conditional-put! {:client c :prefix "kotobase"})
;; => {:enforced? false
;;     :checks {:if-none-match-rejected? false   ; accepted a PUT on an object that exists
;;              :if-match-rejected? false        ; accepted a PUT with a wrong ETag
;;              :etag-returned? true}}
```

It writes one small object at `<prefix>probe/conditional-put`, then attempts
two preconditions that **must** fail against it. An endpoint accepting either
is ignoring the header. Reusing the same key keeps the probe idempotent.

This exists because the manual verification the old code required is a manual
step gating a silent failure, and those get skipped.

## Test

```sh
npm test    # test/run.cljk (mock) + test/r2.cljk (real R2 binding)
```

`test/run.cljk` runs the shared contract against a mock written here to the
shape `open` expects, plus the decisions made before any request is sent:
which profile each client shape yields, when `open` refuses, and the probe
against endpoints that do and do not enforce.

`test/r2.cljk` runs the same contract **through `r2-client`, against a real
R2Bucket binding** (miniflare). That path had no coverage at all — the mock
never calls `r2-client`, so the code translating a CAS into
`bucket.put(key, body, {onlyIf: {etagMatches}})` was untested while being
the client this adapter recommends. A mock cannot close that gap, because
the question is whether the R2 API behaves as the adapter assumes.

It found one. `probe-conditional-put!` sent a literal quoted sentinel as
its wrong ETag; R2's binding **rejects a quoted ETag outright** —
`Conditional ETag should not be wrapped in quotes` — so the probe threw
instead of answering, on the client it most needs to answer for. The mock
had accepted any string. `wrong-etag` now derives the value from the real
ETag by flipping its hex digits, which preserves whatever quoting and shape
the endpoint itself produced; when no hex digit exists to flip it reports
`:enforced? nil :inconclusive :cannot-derive-a-wrong-etag`, because "the
endpoint ignores preconditions" and "this probe could not ask" are
different answers.

Both suites carry an oracle that must be rejected, so a green race is
evidence rather than decoration: for R2 that is `r2-client` with the
precondition stripped out of the put — the shape a dropped or misspelled
`onlyIf` key would produce, which R2 ignores silently.

`test/engine_r2.cljk` goes one layer further: `transact` / `q` and a
**reopened connection** through `kotobase-engine`, over the same R2 binding.
Passing the storage contract does not by itself mean the Datalog surface
reaches the bucket — the D1 backend answers queries from a SQL projection,
and nothing in the storage contract says the engine can serve them from
blocks alone. It can:

```
ok  - q over blocks in R2 returned both entities: #{["kawaraban"] ["itonami"]}
ok  - a REOPENED connection reads it back -- the data is in the bucket, not in the process
```

That suite is compiled with shadow-cljs rather than run under nbb, and the
reason is worth stating: nbb's dynamic interop cannot dispatch `.then`
through kotobase-peer's internals and fails with a stack entirely inside
nbb, which is indistinguishable from "the engine does not work on R2"
unless you look. Note also that the four security controls must return
**Promises** on cljs — kotobase-peer's crypto seam is synchronous on the
JVM but Promise-returning here, so a plain `identity` throws from inside
`put-tx-block!`.

## Measured against production R2 — and it found a shipped bug

`probe-conditional-put!` and the contract were run against a real bucket
through `wrangler dev --remote`. Production R2 **does** enforce both
preconditions and **does** survive the race. The adapter did not:

| build | probe | contract |
|---|---|---|
| `:optimizations :simple` | `enforced? true` | 14 checks, race verified |
| `:optimizations :advanced` | `etag-returned? false` | **4 of 4 concurrent writers all published** |

Same source, same bucket. Closure renamed `(.-etag object)` — externs
inference cannot type the bucket, which arrives as an untyped parameter —
so `:etag` came back nil, every ref carried a nil version, and
`-compare-and-set-ref!` added neither `:if-match` (no version) nor
`:if-none-match` (the ref exists) and sent an **unconditional PUT**.
Advanced is what a Workers build ships, and every suite here ran
unoptimised, so nothing could have caught it.

Two fixes, because the renaming is the trigger and not the defect:

- Property reads go through `goog.object/get` and an `invoke` helper, which
  survive renaming. `kotobase-storage-d1` already had the same helper.
- **`-compare-and-set-ref!` now refuses** when an existing ref carries no
  version, instead of falling through to an unconditional write. A backend
  claiming `:linearizable-ref` must never write without a precondition,
  whatever the reason it lacks one. A refusal is an outage; a silent
  last-writer-wins is corruption.

`test/advanced_r2.cljk` compiles at `:advanced` and pins that the ETag
survives. Verified in both directions: it fails (exit 1) with the property
access restored.

**Still not every production surface.** What this establishes is that
`r2-client` speaks the R2 API correctly and that its claimed profile
survives contention against an implementation of that API. Whether the
production service matches its own API implementation is what
`probe-conditional-put!` is for, and it has not been run against the real
endpoint yet.

## Qualifying a provider

The adapter's `-compare-and-set-ref!` reads the ref, compares, then issues a
conditional PUT. Sequentially the read-and-compare answers correctly whether or
not the provider enforces the precondition — so the shared storage contract
passes even for a backend that ignores preconditions entirely. **A sequential
suite cannot qualify a provider for compare-and-set**, because CAS is a
concurrency property.

Three checks, and they are not substitutes for one another:

```sh
# 1. the adapter's logic (sequential) — the shared contract
kbb --backend sci --classpath "src:test:../kotobase-storage/src" -e "(require '[run])"

# 2. two writers, one ref — deterministic, no threads, no credentials
kbb --backend sci --classpath "src:test:../kotobase-storage/src" -e "(require '[race]) (race/main)"

# 3. the provider itself — does it actually honour If-Match / If-None-Match
S3_ENDPOINT=... S3_BUCKET=... S3_REGION=... \
S3_ACCESS_KEY_ID=... S3_SECRET_ACCESS_KEY=... \
kbb --backend sci --classpath "src:bin:../kotobase-storage/src" -e "(require '[live-contract]) (live-contract/main)"
```

Measured (2026-07-31): with a provider that ignores `If-Match`, two writers
starting from the same observed ref are **both** told they won, and the head
diverges. The shared contract passes in that case, which is why check 2 and
check 3 exist.

`test/teeth.cljk` pins that conclusion: it runs the contract against
conforming and non-conforming providers and asserts the contract cannot tell
them apart. If that test ever starts failing because the contract got stricter,
delete it and say so.

## Live R2 latency and CAS benchmark

The live benchmark writes only unique keys below
`bench/kotobase-storage-s3/<uuid>/`, runs bounded PUT/HEAD/GET samples and an
eight-writer ETag race, then deletes every exact key before responding. It is
disabled unless the remote preview explicitly receives
`BENCH_LIVE_ENABLED=1`; do not deploy the benchmark configuration.

Both halves are ClojureScript: the worker is compiled by shadow-cljs, the
driver runs under nbb. Build the worker before starting wrangler -- the
config points at the compiled output, not at a hand-written module.

```sh
amu compile --target wasm32-browser r2-live-worker
wrangler dev --remote --config wrangler.r2-bench.jsonc --port 8799 \
  --var BENCH_LIVE_ENABLED:1
npm run bench:r2-live
```

The benchmark itself needs a real bucket, so `npm test` does not run it. What
`npm test` does run is the part that can be checked without one:
`test:bench-worker` exercises the three refusals that never touch R2 (kill
switch, method, bounds), and `test:bench-driver` checks that the driver tells
"the race did not run" apart from "the race had the wrong number of winners" --
a driver that treated a missing `conditional_race` block as success would
report a pass for a worker that never ran the race.

`R2_BENCH_SAMPLES`, `R2_BENCH_TRIALS`, `R2_BENCH_SIZES`, and `R2_BENCH_URL`
override the bounded defaults. The driver fails unless each concurrent race
has exactly one winner.
