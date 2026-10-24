# Kotoba agent coding evaluation v1

This is a small, deterministic pilot for exact Kotoba coding in agent
development. It is designed to compare editor/agent integrations, not model
intelligence in general.

## Fixed task

`turn-loop-remaining-budget` asks an agent to add the remaining-budget scalar
export to `src/agent/turn_loop.kotoba`, then resume the same session to review
the implementation. The pre-registered verifier in
`scripts/verify-turn-loop-parity.cljk` compares the new export against all ten
oracle vectors. Its acceptance gate compiles both
`js-browser` and `wasm32-browser` and checks the fixed vectors.

The task uses two prompt stages so session continuity is measurable. Keep the
task text in `tasks/turn-loop-remaining-budget.md` unchanged when comparing
agents. The suite pins the pre-task `baseline_revision` in `manifest.json`.
Each run requires a fresh clean Git worktree at exactly that commit; the runner
copies the skill, task, verifier, schema, and result-free evaluation README into
it, then launches the agent there. This keeps later runs reproducible after the
task implementation has reached `main`.

The `.agents/skills/kotoba-coding/SKILL.md` project skill is available to
Codex in this repository. Hermes discovers the same `.agents/skills` directory
for a project after that repository is trusted with `hermes skills trust`;
then verify it appears in `hermes skills list`. Do not edit or replace an
existing user-level Hermes skill as part of this benchmark.

## Metrics and reward

The result record is `kotoba.eval.result.v1`; the exact shape and required
fields are in `result.schema.json`. `scripts/score-kotoba-eval.mjs result.json`
validates it and prints a score.

Create a fresh worktree for each run, then invoke the runner from the agent
repository root:

```sh
git worktree add --detach /path/to/fresh-eval-worktree 03094b7ebd6e00f4bd8a0b8a1b4acba7e880bcd6
KOTOBA_EVAL_WORKDIR=/path/to/fresh-eval-worktree \
  node scripts/run-codex-kotoba-eval.mjs eval/v1/codex-metrics.json
```

The runner rejects a dirty worktree, the wrong revision, or a baseline that
already has the requested export. Its result records the baseline, task, skill,
verifier, and result-free README digests. Run the acceptance verifier in the
evaluation worktree and combine its results with that metrics record; never
infer correctness from the agent's final message.

The two-stage Codex runner pins
the default model to `gpt-6.1-sol` (override with
`KOTOBA_EVAL_CODEX_MODEL`), resumes the first session for stage 2, consumes
JSONL telemetry in memory, and writes only aggregate metrics. Codex CLI keeps
its normal local session history so that the second stage can resume it; the
benchmark result file contains no transcript or raw session ID. Run the
acceptance verifier yourself afterward and combine its results with that
metrics record; never infer correctness from the agent's final message.

The Hermes runner uses the same fresh worktree through `KOTOBA_EVAL_WORKDIR`:

```sh
KOTOBA_EVAL_WORKDIR=/path/to/fresh-eval-worktree \
  node scripts/run-hermes-kotoba-eval.mjs eval/v1/hermes-metrics.json
```

Before each fresh worktree, trust its project path with `hermes skills trust`
and verify `kotoba-coding` appears in `hermes skills list`. It pins the current default route to OpenRouter
and `xiaomi/mimo-v2.6-pro` (override with `KOTOBA_EVAL_HERMES_PROVIDER` and
`KOTOBA_EVAL_HERMES_MODEL`), explicitly preloads `kotoba-coding`, and limits
tools to `terminal,skills`. It skips unrelated user memory/rules, streams
progress as JSONL, resumes stage 2 from the first session, and reads the
aggregate `--usage-file` report. Session IDs and response text are held only in
memory for resume and are not written to the metrics record; the temporary
usage files are removed after parsing. Hermes keeps its normal local session
history for the resume operation.

Both runners record retries, infrastructure failures, preflight failures,
tool counts and provider-reported usage separately from the score. Incomplete
or infrastructure-failed runs are retained as unscored outcomes; they are not
treated as incorrect code or zero-token runs.

The score is available only when all verification gates and telemetry are
present. Correctness is a hard gate:

`G = syntax_pass AND compile_pass AND all_acceptance_cases_passed AND no_forbidden_forms`

If `G = 0`, reward is `0`. Otherwise:

`reward = 60 + 20*S + 10*T + 10*C`

where:

- `S = max(0, 1 - elapsed_ms / 300000)`; the fixed time budget is five minutes.
- `T = max(0, 1 - (input_tokens + output_tokens) / 24000)`; the fixed token
  budget is 24,000 provider-reported tokens.
- `C = 1` only if the two stages complete in one successfully resumed session;
  otherwise `0`.

The correctness gate carries 60 points before efficiency rewards. This prevents
a fast or cheap incorrect solution from outranking an exact one. Tokens must be
reported by the agent/provider telemetry; missing or estimated usage makes the
combined reward unavailable. The scorer never treats missing metrics as zero.

`acceptance_total` and `acceptance_passed` must come from the named verifier,
not the agent's own summary. Record the verifier name and tested target set.
The JSON output is aggregate-only: it must not contain session IDs, prompt or
response text, patches, source files, or credentials.

## Pilot results (2026-10-22)

| Agent | Outcome | Elapsed | Provider tokens | Session | Verifier | Reward |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Codex CLI 0.163.0 / `gpt-6.1-sol` | completed | 214,928 ms | 1,817,800 input + 10,963 output | 1 session, resumed | 10/10 | 75.67/100 |
| Hermes Agent CLI 0.22.4 / OpenRouter `xiaomi/mimo-v2.6-pro` | infrastructure failure at stage 1 | 954 ms to failure | unavailable | no session observed | not run | unscored |

These are single-run pilot observations on the same task, skill, source and
compiler revisions, not a stable model ranking. The Hermes elapsed time is
time-to-failure and is excluded from speed scoring. Its failure diagnostics
were intentionally not retained, so the cause and whether a provider request
was reached are unknown. No retry was made.

- [Codex aggregate result](results/codex-cli-0.163.0-gpt-6.1-sol-2026-10-22.json)
- [Hermes aggregate result](results/hermes-cli-0.22.4-xiaomi-mimo-v2.6-pro-2026-10-22.json)

## Reading results

Report raw elapsed time, input/output tokens, session count, resume result,
gate outcomes, and the combined reward together. A single run is only a pilot;
comparisons need repeated runs with the same model, task set, tool access,
compiler build, host class, and clean starting revision. Distinguish failed
tasks from infrastructure failures; an unavailable compiler or agent launch
does not count as a coding failure or a zero-token run.
