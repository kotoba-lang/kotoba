# Shared social publication library rules

- `library.edn` is the canonical repository metadata.
- This repository must remain actor-neutral: no actor DID, product policy, deployment target,
  dataset, or actor-specific prose in implementation code.
- Never weaken the four structural invariants: non-adjudicating output, at least two nonblank
  sources, no server-held key, and dry-run-only publication.
- Consumers supply `:actor-id` and `:display-name` as configuration.
- A refusal must not carry a draft. `transition-to-drafted` receives the caller's `cell_state`,
  so a `payload` left by an earlier success would otherwise survive the refusal and be
  publishable by a caller that never reads `phase`.
- `kbb --backend sci run_tests.cljk` must pass from a standalone checkout. It runs the same suite on **both**
  runtimes — nbb first (the workspace's first-class runtime), then `kbb -M:test` — and only
  prints its green marker when both are green. The implementation is `.cljc`; a suite that runs
  on one runtime makes portability a claim rather than an observation.
- `nbb.edn` is what makes the documented `kbb --backend sci run_tests.cljk` resolve: it carries `:paths
  ["src" "test"]`. It is not stray config — delete it and the command in the README exits 1
  with `Could not find namespace`, while the mutation harness keeps passing its own
  `--classpath src:test` and stays green. That is the shape this repo's own loop exists to
  catch, so it is worth not reintroducing.
- Do not reintroduce `run_tests.sh`. Shell scripts and `bb` as a script host are both retired
  workspace-wide, and the loop that guards this repo shells the nbb runner directly.
- The invariants are guarded by mutation testing, not just by green tests: see the
  `social-publication` suite in the superproject's `scripts/maturity-loop/mutations.edn`. When
  you change behaviour here, expect an anchor there to move — update it rather than deleting it.
