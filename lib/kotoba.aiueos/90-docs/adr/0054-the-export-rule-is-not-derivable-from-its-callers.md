# ADR-0054 — The export rule is not derivable from the sources that depend on it

Date: 2026-08-18

## Status

Accepted as a measurement, and as a set of negative results worth not
repeating. [amu#626](https://github.com/kotoba-lang/amu/issues/626) filed. The
ratchet still reads ten.

## Context

ADR-0053 filed the intrinsic gap (four of ten) and left the other three — the
`:per-object-export-symbol` class — deliberately unfiled, on the grounds that
whether the contracts or the target selection was wrong had not been decided.
This iteration tried to decide it, and could not.

## What was measured

The 57 objects the UEFI path links each carry their own symbol; `nm` on the
checked-in `.o` files shows `kotoba_aiueos_msr_read`,
`kotoba_aiueos_probe` for `kernel-probe`, and so on. The `value-*` objects all
compile to `kotoba_aiueos_probe`, which collides with `kernel-probe` and with
each other, so their contracts' `:native :export` check fails.

Trying to find the rule, **every minimal source produced the generic symbol and
the real file did not**:

| source | export |
|---|---|
| `(defn aiueos-foo [x] (+ x 1)) (defn main [] 0)` | `kotoba_aiueos_probe` |
| the same with typed parameters and return | `kotoba_aiueos_probe` |
| a helper `defn` before it | `kotoba_aiueos_probe` |
| calling a kernel intrinsic (`kernel-read-msr`) | `kotoba_aiueos_probe` |
| named `aiueos-value-runtime-syscall-plan` | `kotoba_aiueos_probe` |
| **the real `msr-read.kotoba`** | **`kotoba_aiueos_msr_read`** |
| the same file with every comment removed | `kotoba_aiueos_msr_read` |
| the real `value-runtime-syscall-plan.kotoba` | `kotoba_aiueos_probe` |
| the same with its `(ns … (:export […]))` stripped | `kotoba_aiueos_probe` |

So it is **not** the `ns`/`:export` form, not typed versus untyped signatures,
not calling an intrinsic, not the presence of `main`, and not comments. A real
working object and a source written to mirror it produce different symbols, and
this repository cannot say which difference matters.

**That is the finding.** Not "the compiler is wrong" — the rule may be perfectly
sensible — but that **the naming rule for the symbol 57 linked objects depend
on is not derivable from the sources that depend on it.** A convention nobody
can restate is a convention that will be broken again, and the value runtime is
the evidence that it already was.

## Decision

**File the question rather than guess the answer.** amu#626 carries the table
above, both readings of the ask (what is the rule / is `compile-source`
supposed to honour the `ns` export list), and an explicit statement that it is
not a duplicate of #625.

**Every failure class points at where the work is.** ADR-0053's floor was
per-*form*, and the export class carries no rejected form — the compiler did
not reject it, the contract did — so that floor would have let three failures
sit unreferenced. `:value-runtime/upstream-by-cause` closes it, and
`every-failure-class-points-at-where-the-work-is` fails when a class with
failures has no issue.

## Executable evidence

`aiueos.value-runtime-baseline-test`: **11 tests, 74 assertions, 0 failures**
(was 10/71). Full suite **625 tests, 9371 assertions, 19 failures** — the
baseline nineteen. **Both directions**: dropping the export class's issue fails
only `every-failure-class-points-at-where-the-work-is`, and prints the reason
the per-form floor was not enough.

## A process note worth keeping

This iteration edited the **shared west checkout** by accident — a `cd` into
the child repo left the working directory there, and the next command's
worktree creation failed while the edit and the regeneration ran anyway. Caught
by `git status`, restored with `git checkout --`, and redone in a proper
worktree. The change was inert at that commit, so nothing was lost; the lesson
is that the guard against editing the shared checkout is a habit, not a
mechanism, and a failed `worktree add` does not stop the commands after it.

## Remaining boundary

- **Ten still failing**, now split across two filed issues: #625 (seven, three
  forms) and #626 (three, the symbol).
- **Neither issue has an answer.** Filing is not fixing.
- **The intermittent twentieth suite failure is still unexplained** (ADR-0051)
  and has now gone unattempted for three iterations, which is a choice worth
  naming rather than letting it fall off.
