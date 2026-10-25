# kotoba-harness

**System One Coding on kotoba.** A policy model (TypeSafe Jev via the OpenRouter
Decisions API) chooses typed blocks one hole at a time; the harness assembles
the AST, emits **kotoba typed-subset source**, and accepts it only when kotoba
itself verifies it. The model never returns source text — only the id of a
legal candidate.

Modelled on [Mithril Code's System One Coding](https://code.mithril.fund/),
re-implemented natively for kotoba so that verification runs on the kotoba
toolchain rather than a Clojure host.

## How it works

1. A project (`projects/*.edn`) declares typed functions (`:i64`, `:bool`),
   literals, and **stages** with their admitted operations, admitted calls and
   dependencies; a function may carry its own `:goal`. The operation catalog is
   a whitelist of kotoba typed-subset heads (`+ - * min max < = if`).
2. Stages run in dependency order. Inside a stage, each decision fills the
   first open hole. The policy sees the goal, the stage goal, the partial
   assembly as kotoba source (`?` = this hole, `_` = later holes), the hole's
   **role** (e.g. "argument 1 of 2 in the call to budget-left: the parameter
   used :i64"), frozen functions from earlier stages, and previously rejected
   assemblies with their failure counts.
3. Each completed function is spliced into the baseline module (only the stub lines
   change; every other byte, e.g. `marker`, is preserved) and verified:
   `kotoba -M check` on the module → module + fixed checks compiled with
   `kotoba -M compile --target wasm32-browser --policy {:budgets {:fuel N}}` →
   run through amu's `instantiateKotoba`; `main` returns the number of failed
   cases and must be `0`. Verification is per function (with the functions
   already frozen), so a failure is never blamed on a sibling in the same
   stage; a verified function's AST is frozen.
4. **Backtracking reaches the outermost choice.** A verification failure
   rewinds to the most recent decision with an untried alternative. When the
   policy answers `stop` at a hole ("no candidate here can be right"), the
   search **escalates outward** to the next earlier decision with an untried
   alternative, up to the function's outermost operation. Purely chronological
   retry (escalation off) refuses at the first `stop`, so a wrong outermost
   operation could never be repaired.

Every run writes `runs/<project>-<method>-*/receipt.json`: decisions with
confidence and usage, rewinds/escalations, every verified attempt, the final
source, wasm SHA-256, tokens and the provider-reported API cost. Credentials are
never written.

## Projects

| Project | Subject | Functions | Exhaustive cases |
|---|---|---|--:|
| `kotoba` | kotoba-code durable outer-loop budget | `budget-left`, `may-call` | 256 |
| `itonami` | registered free trial (3 / account / day, 100 / service) | `account-left`, `admit` | 847 |
| `murakumo` | gateway output-token cap | `output-cap`, `can-generate` | 1521 |

`projects/*.edn` state stage goals outermost-first ("guided");
`projects/plain/*.edn` use the original bottom-up wording ("subtract …, then
clamp with maximum") under which the outermost operation was often chosen
wrong.

## Usage

Requirements: Node, [nbb](https://github.com/babashka/nbb), the `kotoba` CLI on
`PATH` (or `KOTOBA_BIN`), and a checkout of `kotoba-lang/amu` for
`runtime/browser-host.mjs` (default `../amu`, or `KOTOBA_BROWSER_HOST`).

```sh
npm test                                         # offline search/catalog tests
bin/kotoba-harness projects/kotoba.edn validate  # offline shape/catalog/splice check
bin/kotoba-harness projects/kotoba.edn known     # known-correct bodies (no model)
bin/kotoba-harness projects/kotoba.edn wrong     # negative control (must be rejected)
OPENROUTER_API_KEY=... bin/kotoba-harness projects/kotoba.edn jev
KOTOBA_HARNESS_ESCALATE=0 bin/kotoba-harness projects/plain/kotoba.edn jev   # ablation
bin/bench 5 && bin/summarize.py runs/bench
```

`jev` spends OpenRouter credit (fractions of a cent per run).

## Results

See [`evidence/`](evidence/) for the measured runs.

Measured 2026-10-07: 5 alternating rounds × 3 projects × {guided, plain} wording ×
{escalation on, off} = 60 live Jev runs, all verified by kotoba (check + wasm32-browser +
instantiateKotoba). Raw per-run evidence (choices, rewinds, escalations, every attempt,
final source, tokens, provider-reported cost): [`evidence/bench-2026-10-07.json`](evidence/bench-2026-10-07.json).

| Wording | Escalation | Project | Passed | Median s | Median API USD | Median in/out tokens | Escalations per run |
|---|---|---|---|--:|--:|--:|---|
| guided | on | kotoba | 5/5 | 13.3 | 0.000283 | 6739 / 589 | 0, 0, 0, 0, 0 |
| guided | on | itonami | 5/5 | 15.3 | 0.000432 | 10294 / 1025 | 0, 0, 2, 0, 0 |
| guided | on | murakumo | 5/5 | 15.2 | 0.000409 | 9740 / 962 | 0, 0, 0, 0, 0 |
| guided | off | kotoba | 5/5 | 13.6 | 0.000283 | 6739 / 589 | 0, 0, 0, 0, 0 |
| guided | off | itonami | 4/5 | 14.1 | 0.000432 | 10294 / 1025 | 0, 0, 0, 0, 0 |
| guided | off | murakumo | 5/5 | 15.0 | 0.000409 | 9740 / 962 | 0, 0, 0, 0, 0 |
| plain | on | kotoba | 5/5 | 30.3 | 0.000736 | 17524 / 1486 | 5, 13, 2, 13, 5 |
| plain | on | itonami | 5/5 | 22.0 | 0.000681 | 16224 / 1590 | 2, 10, 2, 11, 2 |
| plain | on | murakumo | 5/5 | 27.8 | 0.000685 | 16317 / 1567 | 8, 3, 3, 3, 3 |
| plain | off | kotoba | 0/5 | 6.9 | 0.000116 | 2761 / 246 | 0, 0, 0, 0, 0 |
| plain | off | itonami | 0/5 | 6.1 | 0.000123 | 2926 / 290 | 0, 0, 0, 0, 0 |
| plain | off | murakumo | 0/5 | 7.2 | 0.000197 | 4679 / 483 | 0, 0, 0, 0, 0 |

Total API cost of the 60 runs: **USD 0.025895856**.

- With the original bottom-up wording, Jev usually picks the wrong **outermost**
  operation (`subtract` instead of `maximum`), verification fails, and Jev answers
  `stop` at a leaf. Without escalation this ends the run: **0/15** (14 `policy-stopped`
  refusals, 1 transport failure). With outward escalation the search returns to the
  root and repairs it: **15/15**, e.g. `subtract → limit → used → verification-failed →
  stop → escalate → maximum → 0 → subtract → limit → used`.
- With outermost-first ("guided") wording, escalation is rarely needed (1 run used it) and both
  settings pass; the one guided/off failure was a transport error (`fetch failed`), not
  a policy outcome.
- Escalation costs time and tokens (plain/on median 22–30 s, ≈ USD 0.0007 per run) —
  measured on the real implementation, including kotoba verification (≈ 4.5–6.5 s each).
- Controls: known-correct bodies pass 3/3 (0 failures); wrong bodies are rejected 3/3
  (120 / 400 / 702 failing cases).

Earlier same-day runs of the predecessor workspace harness (Mithril generator, chronological
retry only, no hole roles) passed 14/15 with guided wording at about twice the tokens per run.

## Scope and limits

- Small typed functions with exhaustive integer grids — not SWE-bench and not
  general repository coding. No claim of general accuracy, speed or cost
  advantage.
- Wasm fuel defaults to 512 calls; exhaustive checks need a fuel policy.
- On the measured amu checkout, `kotoba -M test`, `--target js` and the native
  kexe compile path were unavailable, so verification uses wasm32-browser only.
- Wall time is dominated by kotoba verification (≈4.5–6.5 s per verify).
