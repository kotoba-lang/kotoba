---
name: kotoba-coding
description: Write and review exact Kotoba source in agent projects, preserve the no-ambient-authority subset, and verify the selected compiler targets.
---

# Kotoba coding

Use this skill when editing `.kotoba` files or reasoning about Kotoba source.

## Source and authority

- Treat `.kotoba` as the source language. Do not silently replace it with
  Clojure, ClojureScript, JavaScript, or a host-language implementation.
- Read the repository's `AGENTS.md` and the current
  `lang/surface-status.edn` before making claims about syntax or capability
  support. Use the repository's EDN reader for that file.
- Preserve the guest grammar's no-ambient-authority rules. Never introduce
  forbidden forms such as `eval`, `load-string`, `atom`, or `swap!` to make a
  task easier.
- Select targets from the current capability-kit qualification predicates;
  do not infer target support from a successful parser check.
- Distinguish parser acceptance, compiler success, target qualification, and
  runtime behavior in reports.

## Editing loop

1. Find the smallest existing `.kotoba` entry point and its tests or golden
   vectors. Preserve neighboring semantics and public names.
2. Make the narrow source change. Add a deterministic self-check or golden
   vector for each new behavior.
3. Compile and run the repository's declared target gates. A `check` command
   alone is not proof that generated JavaScript, Wasm, or another target works.
4. Run the existing upstream parity oracle when the source transcribes an
   upstream agent. If the oracle or compiler is unavailable, report the gate
   as unavailable instead of claiming parity.
5. Review the final diff for unsupported forms, accidental host authority,
   stale generated projections, and unrelated changes.

## Agent evaluation

For a versioned coding benchmark, keep the task set, evaluator, model/agent
version, tool permissions, target set, and execution environment fixed across
comparisons. Record only aggregate metrics and gate outcomes. Never save
conversation transcripts, prompts, source dumps, or raw session identifiers in
the result artifact.

Use `eval/v1/README.md` and `scripts/score-kotoba-eval.mjs` for this
repository's initial benchmark. Missing token or session telemetry means the
combined reward is unavailable; do not estimate or substitute zero.
