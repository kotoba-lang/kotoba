# ADR 0239: CR4 and XCR0 are firmware state, so the oracle refuses them

## Status

Accepted.

## Decision

Add `kernel-read-cr4`, `kernel-write-cr4` and `kernel-xsetbv` to the two sets
that govern privileged operations, named once as
`kernel-extended-state-operations`:

- `eval-expr`'s refusal set — the interpreter traps with
  `{:trap :kernel-privileged-unavailable :operation <op>}`;
- `lower`'s `kernel-operations` — a module that names one of them is
  kernel-native, so the constant oracle is never started on it.

This is the treatment `kernel-read-cr0` / `kernel-write-cr0` already get, and
ADR 0232 gave `kernel-xgetbv`.

## Why not model them as cells

"CR4 and XCR0 are just registers; hold them in the heap and answer reads from
what was written" is the obvious alternative, and it is wrong in a way that
would be hard to see afterwards.

Both registers **already hold a value when the first Kotoba instruction runs**.
UEFI firmware sets CR4 bits before it hands control over — OSFXSR is set on
every x86-64 machine that has run any SSE code, and on some firmware OSXSAVE is
set too. XCR0 likewise holds whatever the firmware left. An interpreter that
started at zero and tracked writes would answer with total confidence, and every
answer would be a value from a machine that does not exist.

The damage is not the wrong number. It is what the caller does with it. The
working spelling of the enable is

```clojure
(kernel-xsetbv 0 (bit-or (kernel-xgetbv 0) 6))
```

— a read-modify-write. An invented `0` for the read makes that expression
**clear** every bit the firmware set, while looking like the code that preserves
them. Refusing is the only answer this interpreter has.

## The refusal it does not add

`xsetbv` raises `#GP` when the value sets a bit XCR0 does not define, when bit 0
(x87 state) is clear, or when bit 2 (YMM) is set without bit 1 (SSE). A literal
operand could be checked here, and this ADR deliberately does not check it.

The reason is which call sites the check would reach. The expression above —
the one a kernel actually writes — passes `(bit-or (kernel-xgetbv 0) 6)`, which
is not a literal and never will be, because its value is a property of the
machine. A literal-only reserved-bit check would fire on toy calls and be silent
on every real one, which is worse than nothing: it reads as protection. The
constraint is stated in kotoba-gmir ADR 0012 and in kotoba-native
`docs/avx2-guard-sequence.md`, where the rest of the sequence lives.

## Why the membership in `lower` is the sharper half

`kernel-read-cr4` is **zero-arity**, and `(kernel-xsetbv 0 7)` is an operation
over two literals. There is nothing in either shape to suggest an effect, so a
constant folder has every structural reason to evaluate them — more reason than
it has for `kernel-cpuid-*`, whose operands at least look like a query. Without
the membership the interpreter's trap fires *inside `lower`*, and a valid kernel
fails to compile.

## Evidence

`kotoba.kir-kernel-privileged-test`, 3 tests / 34 assertions on the JVM:

- `machine-state-is-not-invented` — 10 refusals (`SCANNED refusals`), each
  asserted to trap with `:kernel-privileged-unavailable` **and to name itself**
  in `:operation`;
- `the-extended-state-enable-marks-a-module-kernel-native` — the three new
  operations and the read-modify-write spelling all yield `:oracle-value nil`
  and no folded block, with `(bit-or 262144 6)` folding to 262150 as the control.

Shown to discriminate in **both** directions, each with its own failure:

| break | failure |
|---|---|
| remove the operations from `eval-expr`'s refusal set | `(not (= :kernel-privileged-unavailable :unknown-function))` — the interpreter reaches the unknown-function arm |
| remove them from `lower`'s `kernel-operations` | `lower` itself throws `kernel-privileged-unavailable {:operation kernel-read-cr4}` out of `lower` |

Restored, 0 failures. Nothing here executes an instruction; the encodings live
in kotoba-native.
