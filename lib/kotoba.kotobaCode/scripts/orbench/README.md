# orbench — which model can port Clojure to `.kotoba`?

kotoba-code is model-neutral by design. This is how you find out which model to
point it at for one specific job: **extracting the decision core of a `.cljc`
namespace into `.kotoba`**.

The grade is not a judge model. It is the compiler, run for real, four times:

| gate | question |
|---|---|
| `kotoba -M inspect` | does it compile, and are the exports/arities/result types the ones asked for |
| `kotoba -M test` | does the battery pass on `:jvm-kir` **and** `:js` **and** `:wasm` |
| `kotoba -M compile --target aarch64-macos` | is it native-qualified |
| rounds | how many turns of real compiler diagnostics did it need |

## How it differs from `scripts/compare-openrouter-models.sh`

Two bake-offs in one repo have to say what separates them, or the next reader
picks whichever they find first.

|  | `compare-openrouter-models.sh` | `scripts/orbench` |
|---|---|---|
| task | write Clojure against failing tests | port `.cljc` → `.kotoba` |
| gate | `kbb -M:test` on a synthetic fixture | the Kotoba compiler, on held-out real ports |
| oracle | tests written for the fixture | landed cores in `kotoba-lang/murakumo`, kept out of the prompt |
| models | a paid shortlist | anything, including `:free` |

Use the shell one to ask *can this model write Clojure*. Use this one to ask
*can this model write Kotoba*.

## Running it

```bash
export ORBENCH_ROOT=/path/to/west/superproject   # required; no default
cd scripts/orbench
npx --no-install kbb --backend sci bench.cljk models           # cache the price catalogue
npx --no-install kbb --backend sci bench.cljk validate         # prove the gate can fail
npx --no-install kbb --backend sci bench.cljk agent 3 200 6 \
  poolside/laguna-s-2.1:free nvidia/nemotron-3-super-120b-a12b:free
npx --no-install kbb --backend sci bench.cljk report           # correctness, speed, cost
npx --no-install kbb --backend sci bench.cljk quality          # duplicated truth, fuel/call
npx --no-install kbb --backend sci bench.cljk mutate t2-prices work/....kotoba  # holes in the battery
```

The key is read from `$OPENROUTER_API_KEY`, else from the kagi item
`OPENROUTER_API_KEY` — one targeted lookup, never an enumeration.

| env | meaning |
|---|---|
| `ORBENCH_ROOT` | west superproject root. **Required** — the harness refuses rather than guessing |
| `KOTOBA_BIN` | kotoba CLI (default `$ORBENCH_ROOT/orgs/kotoba-lang/compiler/bin/kotoba`) |
| `ORBENCH_FIXTURES` | repo the `:reference` paths resolve against (default `kotoba-lang/murakumo`) |
| `ORBENCH_MAX_TOKENS` | per-reply ceiling (default 16000) — **see below** |
| `ORBENCH_DIR` | where `tasks.edn` / `results.edn` live (default cwd) |

## `mutate` — for ports that have no reference

`validate` needs a landed reference to mutate. Real work does not have one: you
are writing the port precisely because it does not exist yet. There the battery's
discriminating power has to be checked against the *candidate*, and doing that by
hand does not survive contact with a long session — in one day it was done three
times from memory, and once the hand-applied edit silently failed to match, so a
green run read as "the battery is blind" when nothing had been mutated at all.

```bash
npx --no-install kbb --backend sci bench.cljk mutate <task-id> path/to/port.kotoba
```

Each mutation is one token — a string literal off by a character, an integer off
by one, a comparison weakened, `and`/`or` swapped. Every one is checked to have
actually changed the file before it counts; a mutation that did not apply is
reported as `could not be applied`, never as a kill. Surviving mutants are
printed as `HOLE:` — those are the literals and operators your battery does not
constrain.

Run it on the file you are about to commit, not on the reference.

## Run `validate` before you believe a number

`validate` compiles the landed reference, runs the battery against it, then runs
it again against a one-token mutation. The reference must be green and the
mutant must be red. A battery that cannot fail is not measuring anything, and
`validate` is what proves this one can.

## What this harness got wrong, so you don't have to

Every one of these produced a result that looked exactly like a measured
failure. They are the reason the code is shaped the way it is
(ADR-2800004600 in `com-junkawasaki/root`).

- **`kotoba` CLI errors go to stderr.** Reading only stdout turned every
  rejected file into a silent `nil`, scored the same as a passing one.
- **`bin/kotoba` chdirs to its own repo root.** Relative paths become
  `input could not be read`. Absolute paths only.
- **Reasoning tokens count against `max_tokens`.** At 4,000 a model spent the
  whole budget thinking and returned empty content. Raised to 16,000 — and the
  same thing happened again to different models. `finish_reason: "length"` is
  now recorded as `:truncated`, a separate outcome from a wrong answer.
- **`:free` ids sit behind the upstream provider's shared pool**, which 429s on
  its own schedule (`limit_source: upstream_provider_shared_pool`) while the
  account's own 20rpm/1000rpd is barely touched. Retried with backoff and
  reported as `:rate-limited`, never as a capability result.
- **The battery cannot see a missing export.** It calls the function from
  inside the module, where defined and exported are indistinguishable. Only
  `inspect` can, so the interface check is part of the green condition — not a
  column printed afterwards.

## Self-hosted endpoints: `ORBENCH_ENDPOINT`

```bash
ORBENCH_ENDPOINT=https://infer.murakumo.cloud/v1/chat/completions \
  npx --no-install kbb --backend sci bench.cljk agent 4 30 1 murakumo-main
```

Any OpenAI-compatible endpoint. No bearer token is sent, and the model id is
passed through — resolve it via the `murakumo-main` alias rather than naming a
concrete model (ADR-2607173100).

**Requests to such an endpoint stream, and that is not a preference.**
`infer.murakumo.cloud` sits behind Cloudflare, whose proxy cuts a non-streaming
response at 100 seconds with a `524`. A reasoning model asked to port a
namespace takes longer than that. Measured 2026-08-13:

| | outcome |
|---|---|
| non-streaming | both benchmark tasks `HTTP 524`, **0 rounds** — the model's ability was never sampled |
| streaming | rounds of 210 s, 260 s, 260 s all completed, no 524 |

`sse->completion` folds the event stream back into the one non-streaming shape
the rest of the harness expects, and **drops `reasoning_content` deltas** — they
are not the answer, and keeping them lets `extract` pull a code block out of the
model's thinking.

## Why `quality` reports charges, not nanoseconds

A Kotoba js artifact carries `let fuel=512` per instantiation. A hot loop dies
with `fuel-exhausted` during warm-up, so wall-clock is not available — and
charges-per-call is the better number anyway: deterministic, independent of
machine load. Measured limitation: charges land on function calls, not
arithmetic, so it discriminates call structure rather than complexity.
