# ADR 0268: a fuel budget is bounded by the counter that counts it

Status: accepted. Date: 2026-09-03.

## Context

`execute` asked of a declared budget only that it be a positive integer. There
was no upper bound, and for four years there did not need to be one, because
the number nobody could exceed lived in a different repository and was not a
decision at all.

`kotoba.native.elf64` writes a kernel object's per-call budget with

```
49 c7 41 08 <imm32>      mov qword [r9+8], imm32
```

The immediate is 32 bits and the CPU sign-extends it, so the largest budget any
object could carry was **2,147,483,647**. Nobody chose that. It is the width of
a field in an instruction.

It then became an argument twice:

- aiueos ADR-0142 sized the `sha256-region` object's window at 1 MiB and said
  so in as many words — *"the replenish immediate is 32 bits so 2,147,483,647
  is the largest tier ANY object can have, which at 14,894/block pays for
  8.80 MiB"*.
- aiueos ADR-0175 (QWEN-KERNELS-2) concluded that `evaluate_token` **cannot be
  one Kotoba object**, because the output projection alone is
  248,320 × 5,120 = 1,271,398,400 MACs ≈ 27,970,764,800 fuel — thirteen times
  that ceiling — and left the forward pass with C orchestrating it.

Neither conclusion was wrong about the number. Both were wrong about what the
number was. The context field is a **qword**: `kexe_context_v4`'s `fuel` is a
`uint64_t`, the charge is `cmp qword [r9+8],0` / `dec qword [r9+8]`, and the
image route has always written the budget as eight data bytes. On AArch64 there
is no immediate at all — no object route exists there, and the image shim writes
the same eight bytes.

Two other ceilings restated the same subject at different values, and neither
had been reconciled with the first:

| where | value | route it binds |
|---|---|---|
| `kotoba.native.elf64` replenish | 2,147,483,647 | object (`.o`) |
| `kotoba.verifier/max-native-fuel` | 1,048,576 | image, and every sealed artifact |
| `kotoba.compiler.nbb.cli/native-fuel!` | 1,048,576 | same, JVM-free route |
| here | none | the oracle |

The shipped aiueos objects run at 250,000,000 and 2,147,483,647 through a
verifier that admits at most 1,048,576, and nothing noticed, because the object
route does not read the sealed budget: `package-kernel-object` picks a tier by
symbol name and writes 512 into the artifact's own context. Two numbers that
mean the same thing, four hundred times apart, that never met.

## Decision

**The ceiling is decided here, because the counter is here, and it is
`2^53 - 1 = 9,007,199,254,740,991`.**

`charge!` is `(vswap! fuel dec)` on a plain host number — deliberately, since
fuel is interpreter bookkeeping and never a guest value. On the JVM that is a
`Long`, exact to 2^63−1. **On Node it is a double.** Measured 2026-09-03:

```
        9007199254740991 -> 9007199254740990   exact   (2^53-1)
        9007199254740992 -> 9007199254740991   exact   (2^53)
        9007199254740994 -> 9007199254740992   step 2
        9007199254740996 -> 9007199254740996   STUCK   (2^53+4)
       18014398509481984 -> 18014398509481984  STUCK   (2^54, and every value above)
     4611686018427388000 -> 4611686018427388000 STUCK  (the wasm ceiling)
```

A budget above 2^53−1 is one this interpreter would never see reach zero. It
would return `:ok` for a program that does not terminate — the single answer a
fuel bound exists to prevent. So the ceiling is set where the counters are
still exact, not where the wider of them stops.

`Number.MAX_SAFE_INTEGER` is not an arbitrary choice dressed up: it is the
bound `kotoba.compiler.nbb.cli/native-fuel!` was **already enforcing**, through
`js/Number.isSafeInteger`, beside a `max-native-fuel` test four hundred million
times tighter that hid it.

### Not the same number as `kotoba.wasm/max-fuel` (2^62−1), and that is not an oversight

A wasm module's counter is an i64 global throughout — `global.get`, `i64.eqz`,
`i64.sub` — with no double anywhere in the path, so its exact range is wider.
Two counters, two exact ranges, two ceilings, stated in both places rather than
averaged. Handing a 2^62 budget to *this* interpreter stalls it on the first
charge, as the table above shows.

The asymmetry has a second measurement behind it: `lang/surface-status.edn`,
which states both ceilings, **cannot state the wasm one as a number**. The cljs
EDN reader returns `4611686018427388000` for `4611686018427387903`. It is
recorded there as a string, and the reason is written next to it.

### What this changes for a caller

- `execute` refuses a budget outside `[1, max-fuel]` with
  `:reason :fuel-outside-admitted-range`, rather than clamping. A clamped
  budget is a different program's answer wearing this program's receipt.
- A `:fuel-exhausted` trap now names the budget that was actually exhausted.
  It reported `{:limit 512}` unconditionally — the historical default — for
  every run, including the aiueos objects at 250,000,000. One field, wrong
  every time the caller passed a budget.

### Restated in three other files, on purpose

`kotoba.native.elf64/max-object-fuel` (a packager that required this namespace
would put the whole evaluator on the JVM-free packaging path for one integer),
`kotoba.verifier`, and `kotoba.compiler.nbb.cli`. The latter two **read**
`max-fuel`; only the packager copies it.

The verifier reads it despite that file's standing rule about re-deriving its
own tables, and the distinction is deliberate: that rule exists so a producer
cannot ratify its own admitted-operator **set**, where rejecting by absence has
a safe direction. **A ceiling is not a set.** A verifier that admits less than
the interpreter can count refuses valid artifacts; one that admits more
ratifies a budget the oracle cannot decrement. There is one right answer and it
is a property of the counter.

No single classpath holds more than two of the four. amu holds all of them, so
`kotoba.compiler.fuel64-ceiling-test` is where they are compared.

## Consequences

- The binding constraint on a native per-call budget moves from an instruction
  encoding to a counter's exact range, and is written down.
- `evaluate_token`'s ≈2.8×10^10 is now four orders of magnitude inside the
  ceiling. That says the road is open; it does not say the object exists.
  ADR-0175's other reasons (the shape of the forward pass, what remains in C)
  are untouched.
- A fuel bound near this ceiling is a hang, not a bound, on an object the
  kernel calls with interrupts disabled. The ceiling is what the mechanism may
  carry, not a recommendation; the per-object tiers stay measured with a stated
  margin, and no shipped object is anywhere near it.

## Evidence

`test/kotoba/kir_fuel64_test.cljk`, run on both runtimes (JVM `kbb -M:test`
and nbb through `run-tests.cljk`, where the `:cljs` branch asserts the
`x - 1 === x` measurements directly).

The discriminator is the low word: the positive assertions use
4,294,967,396 = 2^32+100 and 4,294,968,796 = 2^32+1500, and the negative ones
run the **same program** at exactly 100 and 1,500 and show that it traps there.
Without that pair the positive assertions would pass on a program that was
never in danger. `the-loop-costs-what-this-file-says-it-costs` pins the cost at
1,002 from both sides, so the two numbers are not asserted against themselves.
