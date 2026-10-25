# ADR 0028: The grammar copy is compared to the frontend that owns it

## Status

Accepted (2026-09-03). Applies kotoba-lang
`docs/adr/ADR-the-authority-names-every-head-the-frontend-admits.md`.

## The measurement

`kotoba.compiler.frontend` is the only thing in this workspace that decides
whether a head is admitted. Measured 2026-09-03 at sema `1afff23`:

| table | heads |
|---|---|
| `kernel-memory-operations` | 53 |
| `slice-value-operations` | 8 |
| `kernel-privileged-operations` | 53 |
| | **114** |

kotoba-lang `lang/guest-grammar.edn` `:admitted-builtins` — the file that
claims to be the authority on which heads are admitted, and of which this
repository ships a byte copy at `resources/kotoba/lang/guest-grammar.edn` —
named **three**: `kernel-load-u8`, `kernel-store-u8`, `kernel-boot-info`.

The gap is older than the tables' current size. MEMWIDTH measured it at
46-against-3 and recorded that seven were already missing before that wave.
Every widening since — the 64 KiB tier, u16 and u64, six general atomics, the
f32 dot product, three fused dequantize-and-dot kernels, port reads, MSRs,
`cpuid`, `xgetbv`/`xsetbv`, CR4, fences, `rdtsc`, the UEFI thunks — landed in
this repository and reached the authority in none of them.

## Why nothing noticed

Nothing in this repository, in amu or in kotoba-lang reads `:admitted-builtins`
at all, and nothing anywhere reads it to decide what the COMPILER admits — the
three frontend tables above do that, and they never consult the file. Its one
reader anywhere is `kotoba.grammar/admitted-heads`, in kotoba-lang/kotoba's
vendored grammar loader (`vendor/grammar/src/kotoba/grammar.clj`), where a head
missing from the set is reported as `:unknown-form`.

So the understatement's consequence was one repository calling 111 heads the
compiler admits unknown, with nothing failing. A description that nothing
compares to the thing it describes will be wrong eventually, and nothing will
fail when it becomes wrong. That is the whole finding; the 111 missing heads
are the symptom.

> **Corrected 2026-09-03, after this ADR first landed.** The paragraph above
> originally said `:admitted-builtins` "decides nothing", from a grep across
> the four repositories that covered `src test scripts` and not `vendor/` —
> which is where the one reader lives. Measuring a subset and reporting it as
> the whole is the defect this ADR is about, so the correction is recorded
> rather than made quietly.

## The decision

`test/kotoba/compiler/guest_grammar_vendor_test.cljk` asserts two things this
repository is uniquely able to assert:

1. **`:admitted-builtins` names exactly the kernel heads the frontend
   admits.** Both directions — `missing` and `extra` — with the differing
   heads named in the failure message rather than "the files differ". The
   frontend lives here, so this comparison can be made nowhere else.
2. The vendored copy's sha256 equals the authority digest of the 2026-09-03
   wave, `67561e57…`. The same literal is pinned in kotoba-lang, amu and
   kotoba, which makes the next authority edit a four-repository wave by
   construction.

It also prints `COMPARED <n>` and refuses `n = 0`. The count here is **1**:
this repository's classpath carries one copy of the resource, because none of
`artifact`, `kotoba-hir` or `kotoba-kir` ships one. The cross-repository half
is done by the pinned digest, not by a comparison, and the file says so rather
than implying a comparison it cannot make. amu sees two copies and kotoba sees
three, and each compares them across its own pin.

## Why not extend kotoba-lang's existing check instead

`local-and-sibling-vendors-match-authority` already compares kotoba-lang's
authority against `../amu`, `../kotoba`, `../kotoba-sema` and `../grammar`.
Those are west monorepo paths; each is guarded with `(when (.isFile ...))`,
and `authority-vendor-drift` reports an absent path as `:missing`, which the
test tolerates. In a single-repository clone it compares one file — the
authority's own copy of itself — and reports green.

Measured 2026-09-03 on the four mains, before the resync: amu's copy was one
change behind (580 lines against 601) and kotoba's two copies were at 401.
**Three of four had drifted, on main, and the check written to find drift
reported nothing.** So the replacement is placed where the copy is on a
CLASSPATH, where it cannot be absent.

## Verification

```
kbb -M:test -n kotoba.compiler.guest-grammar-vendor-test
  COMPARED 1   SCANNED 114 kernel heads (114 declared)
  2 tests, 8 assertions, 0 failures, exit 0
```

Deliberately broken by deleting `"kernel-dot-f32"` from the vendored copy:

```
  2 failures, exit 1
  the frontend admits heads the authority does not name: ("kernel-dot-f32")
  vendored grammar drifted from the authority
    expected 67561e57…  actual 0af2cc09…
```

Both failures name the head. A run that could not open the resource fails on
the `COMPARED` floor instead, with a different message.
