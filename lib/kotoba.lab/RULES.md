# Rules

## Language Boundary

- Use `lab.kotoba` and canonical `.kotoba` modules for notebook schema,
  verification contracts, maturity coverage, and replay rules.
- Do not add `.mjs` files.
- Do not add `.sh` files or shell-script based workflows.
- Do not move product logic, verification policy, or maturity rules into JavaScript runners.
- Keep JavaScript limited to the static UI and the minimal Playwright browser runner.

## Verification

- Contract source of truth: `src/kotoba/lab/verification.kotoba`.
- Contract conformance source of truth: `test/kotoba/lab/verification_conformance.kotoba`.
- The `.cljc` counterparts are retained semantic oracles, not consumer entrypoints.
- Browser runner: `scripts/verify-lab.js`.
- CI must verify the canonical `.kotoba` contract is referenced by `lab.kotoba`.

## Changes

- When adding coverage, add the requirement to canonical `.kotoba` first and
  preserve the CLJC oracle until cross-backend parity is re-qualified.
- Then expose it in `lab.kotoba`.
- Then render it in the UI.
- Then verify it through the browser runner.
