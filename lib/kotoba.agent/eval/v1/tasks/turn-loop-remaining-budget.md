# Task: remaining budget export

## Stage 1

In `src/agent/turn_loop.kotoba`, add and export
`run-budget-remaining(max-iterations, budget-max, events)`. It must return
`max(0, budget-max - budget-used-after-events)` while preserving all existing
turn-loop semantics. Add a `main()` self-check for the new export. Do not
change the event encoding, upstream behavior, or introduce forbidden Kotoba
forms.

## Stage 2 (resume the same agent session)

Review your implementation against the task and existing oracle. Run
`scripts/verify-turn-loop-parity.cljk`, which checks remaining budget against
all ten committed golden vectors, then fix any issue it finds. Do not edit the
verifier or oracle. Report the exact command and whether the compiler and
upstream oracle were available.

## Acceptance

- The `.kotoba` source exports `run-budget-remaining` with the stated behavior.
- The check includes all committed oracle vectors and the `main() = 42` checks
  on both `js-browser` and `wasm32-browser`.
- No pre-existing parity vector changes and no forbidden Kotoba form is added.
