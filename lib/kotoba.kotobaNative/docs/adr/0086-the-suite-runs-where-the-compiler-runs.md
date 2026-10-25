# 0086 — the suite runs where the compiler runs

Status: accepted
Date: 2026-09-18
Base: `origin/main` `b8cd0f6`

## Context

Owner, 2026-09-18: 「kotoba-native も jvm 依存しない様にして」. The emitter
already ran without a JVM — amu compiles through it on the kbb engine, and
ADR 0085 was verified that way — but the SUITE did not: 22 of 37 test files
were JVM-only (`Throwable`, `clojure.lang.ExceptionInfo`, `Long/…`,
`Float/…`, `clojure.java.io`, `MessageDigest`, `format`, `bigint`), and
since the `.cljk` rename (2026-09-11) nothing could run them at all —
`kbb -M:test` substitutes cljs.test and died on the first `Throwable`,
`clojure -M:test` sees no `.cljk` and reports `Ran 0 tests`. Measured
2026-09-18. The last fleet receipt that says `Ran 379 tests` is from
2026-09-05/06.

Three things had rotted in the dark since:

- `elf64_test.cljk` had one `)` too many since de8e837 (2026-09-15) — the
  namespace could not load on any host.
- `source_control_bytes_test.cljk` filtered sources with `\.cljc?$`, which
  matched nothing after the rename; its evidence floor was the only
  assertion left.
- Six tests asserted a context-slot CALL for `vector-count` / `vector-at` /
  `vector-assoc!`, which ADR 0084 (2026-09-16) made inline.

## Decision

**Every test runs on the kbb engine. `run-tests.cljk` is the suite.**

- `nbb.edn` declares the six coordinates the tests reach (osaho,
  kotoba-gmir, kotoba-mir, kotoba-codegen, kotoba-object, artifact), same
  shas as `deps.edn`.
- `test/kotoba/native/test_support.cljk` replaces what came from the JVM:
  file/resource reads (`fs`), SHA-256 (`crypto`), `format`
  (`goog.string.format`), `Float/floatToRawIntBits` twins (`DataView`),
  UTF-8 bytes (`TextEncoder`), and the 32-bit-word bit operations. That
  last one is the substantive port: the tests read instruction words with
  `bit-and`/`bit-or`/`bit-shift-*` and compared them with positive
  literals, which JVM longs allowed and JS int32 ops do not (a word with
  bit 31 set came back negative — 173 failures on the first run, most of
  them this). The suite's bit operations are now the unsigned-32-bit-word
  versions, taken by `(:refer-clojure :exclude …)` + `:refer` in each
  namespace; a test that reasons about a genuine i64 uses
  `kotoba.kir.cljs-i64` (BigInt) — the same representation the emitter
  computes in — and never these.
- 64-bit test arithmetic is BigInt: the signed-division-magic oracle, the
  unsigned-borrow fuel simulation, `i64/max-i64`/`min-i64` in place of
  `Long/…`, f64 bit patterns as `(js/BigInt "…")` built with `list`, not
  inside a quoted form.
- The three rotted items above are fixed; the six ADR-0084-stale tests now
  assert the inline emission (zero slot calls, the inline check counted)
  and route the call-encoder tests through `vector-alloc`, which is still
  a call.

**The 18 x86-64 aiueos kernel-image tests are `known-red`, by name, with
one reason.** They read what only the JVM twin `elf64.clj.cljk` lays —
GDT/TSS/rsp0 stack, the value-runtime syscall shim, the interrupt entry
region, the context slot block (ADR 0036) — and the portable twin refuses
with `:isr-image-needs-the-jvm-packager` or has no entry region. They RUN,
their failures print, and the runner counts them apart:

    SCANNED   37 test files on disk against 37 listed
    known-red tests   18 of 18 listed
    kotoba-native suite: OK (known-red counted apart)

A failure outside the list fails the run; a listed test that passes fails
the run (stale list); a test file the list does not name fails the run.
Measured: removing one entry → `UNEXPECTED-RED … suite: FAIL`.

## What this does NOT do

It does not make the JVM twin's kernel image available without a JVM. amu
has compiled through the PORTABLE twin since its JVM route was removed
(2026-09-11), so the x86-64 aiueos kernels amu packages today carry no
GDT/TSS/value-runtime shim — the 18 tests name exactly what production
lost. The next step is the port of those features into `elf64.cljc.cljk`
(superseding ADR 0036's "does not merge live-boot into .cljc"), shortening
`known-red` to zero and deleting the JVM twin. Until then the twin-parity
test keeps the two allowlists equal.

## Consequences

- 432 tests, 5,620 assertions on kbb, 26 s on the M1.
- The fleet gate for this repository moves from `:jvm-test` to
  `:nbb-test` (root `scripts/fleet-ci/gates.edn`), classpath
  `src:resources:test`.
- `deps.edn`'s `:test` alias (cognitect test-runner) stays as a record of
  the shas, but nothing runs it.
