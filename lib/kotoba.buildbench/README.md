# kotoba-lang/buildbench

**How long does a build take when the code stops being a toy — and does the
artifact still answer?**

Every published build-time comparison this repository could find shares one
shape: a tiny source, a stopwatch, a table. That shape has two holes in it,
and this harness exists because both of them turned out to be load-bearing.

The first hole is **size**. A twenty-line program measures process startup.
It says nothing about the thing a developer actually waits for, which is a
compiler working through a real file. The interesting number is not the
intercept — it is the slope.

The second hole is **whether the artifact is the program**. The fastest way
to emit a build artifact is to emit a broken one. A benchmark that times a
compiler without executing what it produced is measuring how quickly a tool
can be wrong.

This harness closes both. It generates the same program at several sizes in
four languages, builds it through every toolchain on the host, and then —
after the clock has stopped — runs the artifact and checks the answer.

On its first serious run it found three lanes that stopped working. One was a
real bug; the other two were declared bounds doing exactly what they say they
do. Telling those apart is the point. See
[What it found](#what-it-found-on-the-first-run).

## Running it

```sh
npm install -g nbb          # or: npx nbb
git clone https://github.com/kotoba-lang/perfgate ../perfgate
git clone https://github.com/kotoba-lang/machine  ../machine

kbb --backend sci --classpath "src:../perfgate/src:../machine/src" bin/buildbench.cljk \
  --scales 1,32,128,129,512,1023,1024 \
  --runs 7 \
  --budget-ms 300000 \
  --fuel 1048576 \
  --amu /path/to/kotoba-lang/amu \
  --output results/latest.json
```

Every lane whose tool is missing is reported `unavailable`. It is never
reported as zero, and never silently dropped — a toolchain that did not run
must not look like a toolchain that ran and was fast.

`--amu` is optional and points at a checkout of
[`kotoba-lang/amu`](https://github.com/kotoba-lang/amu), because the current
Kotoba compiler is a repository rather than a released binary. Without it the
two Amu lanes report `unavailable` and the rest still run.

### Exit codes are three-valued

| code | meaning |
|---:|---|
| `0` | every available lane built and its artifact answered correctly |
| `1` | a lane produced something that is not the program — details on stdout and in the JSON |
| `2` | the harness could not measure at all (no toolchain found) |

The third one matters. A run that could not answer must not exit like a run
that answered and found nothing wrong.

## The workload

At size `K` the generator emits `K` independent four-operation leaf
functions and one entry point that accumulates all `K` of them through a flat
sequence of bindings.

```clojure
(defn f7 [x :i64] :i64
  (let [a (+ x 7)
        b (- a 7)
        c (+ b 1)]
    (if (< c 0) (- 0 c) c)))
```

Three properties are deliberate:

- **Flat, not nested.** A deeply nested expression measures a parser's
  recursion limit, which is not what anyone means by build time.
- **Every leaf live.** The entry point calls all `K`, so no toolchain gets to
  skip codegen for dead code and post a faster number for less work.
- **Small integers everywhere.** Each leaf is `x + 1` by construction, so the
  values stay tiny and no language needs overflow semantics another language
  does not have. `main` returns exactly `K`, which is what each artifact is
  checked against.

Generated rather than hand-written, because hand-written "equivalent"
programs drift, and the drift lands in the timing as though it were a
property of the compiler.

## The lanes

| lane | language | target | how the artifact is checked |
|---|---|---|---|
| `kotoba-wasm-cli` | Kotoba | WebAssembly | instantiated, `main()` called, answer compared |
| `amu-wasm` | Kotoba | WebAssembly | instantiated, `main()` called, answer compared |
| `amu-native` | Kotoba | native `kexe` | **structural only** — sealed-container header and payload |
| `rustc-wasm` | Rust | WebAssembly | instantiated, `main()` called, answer compared |
| `rustc-native` | Rust | host dylib | Mach-O / ELF header |
| `clang-wasm` | C | WebAssembly | instantiated, `main()` called, answer compared |
| `clang-native` | C | host dylib | Mach-O / ELF header |
| `javac` | Java | JVM class | `CAFEBABE`, then `java Main` run and its exit status checked |

The native lanes get a weaker check than the Wasm lanes, and this table says
so rather than letting a reader assume otherwise. A structurally valid native
image that computes the wrong answer would pass `amu-native` and fail
`amu-wasm`; the two lanes are not equally strong evidence.

**The lanes are not equivalent.** Different targets, ABIs, optimisation
levels, and runtime contracts. `rustc-native` builds a dynamic library;
`javac` emits a class the JVM will later JIT; `amu-native` emits a sealed
container. Comparing their wall times is a legitimate question about
developer feedback latency. It is not a claim that they did the same work.

## Two qualifications, kept apart

Absolute milliseconds and the ordering between lanes are different claims
with different failure modes, so the report carries two separate verdicts.

**Absolute times** are gated on a quiet host (`load1 ≤ 1.0`). On a busy
machine the milliseconds are still true observations of that run, but they
are not portable to anyone else's hardware, and `absoluteTimes.qualified`
says which case you are reading.

**The ordering** is gated by
[`perfgate`](https://github.com/kotoba-lang/perfgate), which refuses a
ranking whose gap falls inside the arms' own spread — however large the ratio
looks. Because the lanes are interleaved on one host, a gap that survives
that test survives the host being busy: the load fell on both arms.

The policy is perfgate's own default, unrelaxed:

```clojure
{:policy/min-samples 5
 :policy/max-relative-stdev 0.10
 :policy/min-improvement 0.05
 :policy/require-provenance :measured
 :policy/require-baseline? true}
```

A threshold loosened to let this run's result through would be a benchmark
measuring its own thresholds. If a lane is too noisy to rank, the report says
`:too-noisy` and publishes the samples anyway.

`:require-provenance :measured` is why `src/buildbench/host.cljk` reads cache
line size, page size and core count off the machine with `sysctl` instead of
declaring a plausible Apple M4. A claim pinned to numbers nobody read is a
claim pinned to nothing, and perfgate refuses it.

## What it found on the first run

Two things, and they are not the same kind of thing. Telling them apart is
most of what this harness is for.

### A real bug: the released CLI stops emitting valid modules at 129 functions

```
K=128 → ok
K=129 → CompileError: function index #15872 is out of bounds
```

128 is where a LEB128 index stops fitting in one byte. The current compiler in
[`amu`](https://github.com/kotoba-lang/amu) does not have this; the released
`kotoba` 0.7.3 binary does.

This is the entire argument for validating inside a benchmark harness. Timed
without the check, that lane would have posted a *faster* number at every size
above 128 — less work, no valid module — and the fastest column in the table
would have been the broken one.

### Not a bug, twice: two declared bounds doing their job

Two more Kotoba lanes stopped, and publishing them next to the paragraph above
would have been wrong in both cases.

**The default fuel budget.**

The first run also showed Kotoba "failing" at exactly `K=512`, and it would
have been easy, and wrong, to publish that next to the paragraph above.

A Kotoba module carries a **declared call-fuel budget**, and the compiler
default is 512 calls. The workload's entry point calls `K` leaves, so at
`K=512` the module runs out of the fuel its author declared and traps. That is
not a compiler defect; it is the language refusing to run a module longer than
it was authorised to run. Raise the bound and it builds and answers correctly:

```sh
echo '{:budgets {:fuel 1048576}}' > fuel.edn
amu compile main.kotoba --target wasm32 --policy fuel.edn --output m.wasm
# main() = 512
```

So the harness declares the budget explicitly and records it in the report
(`method.declaredKotobaFuel`). C, Rust and Java have no equivalent bound to
raise, which is itself worth stating rather than quietly equalising away.

**The function-count admission limit.** Past `max-functions` (1,024) the
compiler refuses the module:

```
{:ok false, :error :subset,
 :diagnostic {:code :kotoba.error/subset-reject},
 :message "function count exceeds admission limit"}
```

It exits 65 and names what it refused. This is worth putting directly beside
the LEB128 bug, because the two are opposites and they arrive at the same
place in a naive table — a lane that stopped:

| | released CLI above 128 functions | Amu above 1,024 functions |
|---|---|---|
| exit status | success | 65 |
| what you get | a module that will not load | a diagnostic naming the limit |
| how you find out | when something tries to run it | immediately |

A loud ceiling and a silent one are very different results. Only a harness that
executes the artifact can tell them apart, which is the whole reason this one
does.

### Correction, 2026-09-07: the limit is not per module

An earlier version of this section said the limit was per module, so a bigger
program was a multi-module project the single-file harness deliberately did not
exercise, and `K=1023` was therefore this benchmark's ceiling rather than the
language's. That was measured against Amu `715138d0` and it is false:

```
$ amu check main.kotoba --source-path proj800     # 4 modules, 800 leaves
{:format :kotoba.check/v1, :definitions {...}}    # links and checks

$ amu check main.kotoba --source-path proj2048    # 4 modules, 2048 leaves
{:ok false, :error :project-link,
 :message "linked project exceeds function limit"}
```

`kotoba/compiler/project.cljc` carries `max-project-functions`, also 1,024,
checked against the **linked** program. There is no arrangement of modules that
compiles a 2,048-function Kotoba program today, so `K=1024` and `K=2048` are the
language's ceiling and not only this harness's. That does not make the bound a
defect — it is still declared, still loud, and still exits 65 — but the escape
route this README offered its readers does not exist, and a reader could have
acted on it.

The correction is recorded in Amu's `docs/build-scaling-coscientist.md`.

The general shape is worth naming, because it is easy to hit and it looks like
success: **a benchmark that trips a declared bound and reports it as a defect
is measuring the bound, not the compiler.** The difference between the three
failures above is one field in the report and an opposite conclusion.

## Testing the validator itself

```sh
kbb --backend sci --classpath "src:../perfgate/src:../machine/src" test/validator_test.cljk
```

A validator that has only ever been seen to pass is not evidence of anything,
and its bad failure mode is silent: one that accepts everything looks exactly
like a toolchain that never breaks. So the test asserts all three outcomes
against hand-assembled modules, including the case that is hardest to catch —
a structurally perfect module that computes the wrong answer, which
instantiating without calling would wave through.

It has been run in both directions. Removing the answer comparison makes
exactly the two answer-dependent checks fail and leaves the other three
passing, which is the failure matching what was broken rather than a red for
some unrelated reason.

## Layout

```
bin/buildbench.cljk        entry point
src/buildbench/workload.cljk   the generator, one program in four languages
src/buildbench/lanes.cljk      toolchains and what each artifact must prove
src/buildbench/measure.cljk    interleaving, budgets, validation-after-clock
src/buildbench/host.cljk       sysctl probe → a :measured machine descriptor
src/buildbench/report.cljk     the two qualifications, kept apart
test/validator_test.cljk       proof the artifact check refuses for its stated reason
results/                       published runs, one JSON per host
```

nbb (ClojureScript on Node) throughout, per this workspace's script-host rule.

## Reproducing, and disagreeing

`results/*.json` carries every sample, the machine descriptor and its
fingerprint, tool versions, the exact commands, and both qualification
verdicts. It is a record of one host on one day, not a portable ceiling.

Run it on your own machine. If your ordering differs from the published one,
that is a result — and the JSON contains enough to find out which of us was
measuring something else.

## Licence

MIT. See [LICENSE](LICENSE).
