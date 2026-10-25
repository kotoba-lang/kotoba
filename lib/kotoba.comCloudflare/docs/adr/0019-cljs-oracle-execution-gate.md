# ADR-0019: the shipped oracles threw on ClojureScript, and every gate was JVM-only

Status: accepted (2026-08-12)

## Context

There are **two** distinct ways an oracle export can work on the JVM and throw on
ClojureScript. Both come from the same root — a guest `:i64` is a `long` on the
JVM and a `js/BigInt` on ClojureScript — but they break at different places, and
a gate that only covers one of them is not a gate.

| | mode 1 — substring offset | mode 2 — record field |
|---|---|---|
| where | `kir/utf8-substring!` | `kir/value/bounded-typed-value!` |
| trigger | `string-substring` whose index came from `:i64` arithmetic | an `:i64` field **inside a record** arriving as a host number |
| message | `string substring indexes are out of bounds` | `value is not a signed i64` |
| fix belongs to | the kir pin | the host seam (`oracle/record`) |
| status here | **was broken**, fixed by the pin | **already correct**, now under test |

Mode 2 does not fire for a *top-level* `:i64` argument, because `kir/execute`
coerces those. It fires only through a record — which is exactly the shape T5.2
pushed every multi-argument export into. `kotoba-lang/calendar` shipped a
delegated `overlaps?` that threw this way from the day it was delegated
(2026-08-11) and stayed invisible behind a green JVM suite.

All nine public namespaces in `src/` route their pure decisions through
`cloudflare.kotoba.oracle/call`, which executes the precompiled KIR in
`resources/cloudflare/oracle/*.kir.edn` and fails closed via `require-ready!`
(ADR 0012, ADR 0016). That is the intended shape.

**The shipped artifacts threw on ClojureScript.** Measured 2026-08-12 from the
repo root:

```
$ nbb  ;; ir/execute on resources/cloudflare/oracle/client_core.kir.edn
api-base -> "https://api.cloudflare.com/client/v4"
blank?   -> THREW: string substring indexes are out of bounds
```

### Mechanism (mode 1 — the live defect)

`kotoba.kir/utf8-substring!` guarded its offsets with `(integer? start)`. Under
ClojureScript an `:i64` is a `js/BigInt`, and `(integer? <BigInt>)` is **false**,
so the guard rejected every `string-substring` whose index came from `:i64`
arithmetic — `(string-substring s 1 n)` where `n` is `(string-byte-length s)`,
which is how each core walks a string. On the JVM an `:i64` is a `long` and
`integer?` is true, so the defect **cannot** fire there.

Both kir pins this repo used carried the old guard (`767f2f2f` in `deps.edn`,
`7ad08c4e` in `nbb.edn`). `kotoba-lang/kotoba-kir` `main` had already replaced
the guard with `bounded-host-byte-offset`, which converts a BigInt offset.

### Why nobody noticed

Every gate this repo had — the parity suites, `precompiled-kir-does-not-drift`,
even `kotoba_oracle_cljs_load_test.clj`, which exercises the *cljs load surface*
from the JVM — runs on the JVM. **A green `kbb -M:test` is not evidence
about ClojureScript**, and this repo's whole reason to exist is a runtime that is
JavaScript. 62 of 220 representative calls across 40+ exports threw, including
the entire deploy-validation path (`validate-account-id`, `validate-script-name`,
`validate-module-name`, `validate-asset-path`, `content-type-for-path`) and the
whole of `stream`'s number formatting and key redaction.

## Decision

**1. Migrate to the newer matched compiler/interpreter pair**, rather than
narrowing the exports:

| pin | was | now |
|---|---|---|
| `kotoba-kir` (deps.edn, nbb.edn) | `767f2f2f` / `7ad08c4e` | `6d08e3cf` |
| `compiler` (test-only) | `98b56bdb` | `b0095427` |

Advancing the interpreter alone is normally unsafe — emitter and interpreter are
a matched pair, and on `kotoba-lang/kura` the same move produced 1 failure / 32
errors, then an outright compile rejection (`expression type mismatch: expected
i64, got bool`) because `string=?` changed from returning `:i64` to `:bool`.

**That does not happen here, and it was measured before choosing.** All nine
cores compile clean under `b0095427`, and the emitted KIR is **byte-identical**
to what is already checked in — so no artifact was regenerated and no source
edit was needed. The cores are immune to the `string=?` type change because
every use is already consumed by an `if` (`(if (string=? c " ") 1 0)`), never
returned directly as an `:i64`. The host was already tolerant too:
`oracle/bool->host` has always accepted both booleans and 0/1 guest words.

**2. Add a ClojureScript execution gate**, which is the real fix — the pin was
only the bug of the day.

- `test/cloudflare/oracle_cases.edn` — 220 cases covering **all 117 exports of
  all 9 shipped artifacts**. Arguments are authored by hand (they must be inputs
  the guest genuinely accepts, so a raised exception always means a defect and
  never a legitimate guest trap); expectations are derived by executing them on
  the JVM and checked in.
- `test/cloudflare/oracle_cases.cljk` — the portable table reader, arg decoder
  and result normalizer (a guest `:i64` is a `long` here and a `BigInt` there,
  so both collapse to a number before comparison).
- `test/cloudflare/oracle_cljs_gate.cljk` — `kbb --backend sci test/cloudflare/oracle_cljs_gate.cljk`.
- `test/cloudflare/oracle_cases_test.cljk` — the same table on the JVM.

Because both runtimes execute the *same* table through `oracle/call` — the
production seam, loader and ABI projection included — a JVM/cljs divergence is
now a test failure rather than a production incident. Routing through
`oracle/call` rather than `ir/execute` is what puts mode 2 under test at all:
the conversion that mode 2 depends on lives in `oracle/record`, not in kir.

**Coverage is enforced, not sampled.** `missing-coverage` fails when any shipped
export has no case, so a new `(:export …)` cannot land unexercised. This matters
more than the case count: the defect was not that the old gates were weak, but
that they were pointed at the wrong runtime.

**3. Lock the two kir pins together.** `deps.edn` and `nbb.edn` each pin
`kotoba-kir`, and they had drifted (`767f2f2f` vs `7ad08c4e`); the cljs half was
executing an interpreter no JVM run ever touched.
`kir-pin-agrees-between-runtimes` fails when they differ.

`kotoba-lang/calendar`'s `scripts/cljs-boundary-check.cljs` instead resolves the
interpreter through `kbb -Spath`, so drift is impossible by construction.
That is the stronger property and worth taking if a third pin ever appears; it
was not taken here because it makes `nbb.edn` a decoy — it would still declare a
`kotoba-kir` dep that nothing uses, and consumers of this library run nbb with
their own deps, so the config should stay real and just be kept honest.

## Evidence

Mutation-tested; the gate was shown to fail before it was shown to pass.

| mutation | result |
|---|---|
| pins reverted to `767f2f2f`/`7ad08c4e` (mode 1) | cljs gate exit 1, **62 of 220 cases threw** `string substring indexes are out of bounds` |
| pins advanced (the fix) | cljs gate exit 0, 220/220 match the JVM |
| `oracle/record`'s `(= field-type :i64) (as-i64 v)` → `v` (mode 2) | cljs gate exit 1, **6 cases threw** `value is not a signed i64` — while `kbb -M:test` reported **98 tests, 564 assertions, 0 failures** |
| one shipped artifact hand-edited (`rtmps://live.twitch.tv/app` → `TAMPERED`) | cljs gate exit 1 `:mismatch`; JVM `precompiled-kir-does-not-drift` also fails |
| all cases for `:stream/redact-key` deleted | cljs gate exit 1, `uncovered: [:stream redact-key]` |

**The mode-2 row is the whole argument for this ADR in one line**: the same
mutation is a clean sweep on the JVM and six failures on ClojureScript. No
amount of strengthening the JVM suite would have found it, because on the JVM
`(long n)` and `n` are the same value.

Suites at the landed pins: `kbb -M:test` — 98 tests, 564 assertions, 0
failures, 0 errors (was 94/537). `kbb --backend sci test/cloudflare/oracle_cljs_gate.cljk` —
220 cases, 117 exports, exit 0.

`precompiled-kir-does-not-drift` (extended to all nine artifacts in `4975784`)
still holds, and still fails on a stale artifact, as the table shows.

## Consequences

- `nbb.edn` `:paths` gains `"test"` so the gate and the shared table resolve.
- Regenerating the case table (`kbb -M:oracle-cases-gen`) rewrites the
  expectations from the JVM. **Read that diff** — a changed expectation is a
  changed decision, not a refresh.
- The cljs gate is not yet wired into the murakumo fleet CI (`scripts/fleet-ci/
  gates.edn` lives in the superproject). Until it is, it is a local command; it
  is deterministic, needs no credentials and no network beyond the nbb dep
  fetch, so it is a straightforward `:nbb-script` gate to add.

## Related

- ADR 0014 (cljs oracle dual-source), ADR 0016 (T6.4 required mirror delete)
- `com-junkawasaki` ADR-2608120200 — the survey that lists this repo as one of
  four running Kotoba cores in production
