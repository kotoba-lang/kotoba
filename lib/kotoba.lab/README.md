# kotoba-lab

Research notebook prototype rendered from `lab.kotoba`.

Published at:

https://kotoba-lang.github.io/lab/

## Implementation Rules

The lab contract is Kotoba/Clojure-first.

- Canonical verification contracts must live in `.kotoba` files; `.cljc` is
  retained only as the legacy semantic oracle during cutover.
- Do not add `.mjs`, `.sh`, shell-script, or ad-hoc script contracts.
- Browser automation may use a minimal `.js` runner only to drive Playwright.
- Product behavior, maturity rules, coverage requirements, and environment locks must be represented in `lab.kotoba` and canonical `.kotoba` modules.
- CI must treat JavaScript runners as wrappers, not as the source of truth.

Current contract files:

- `src/kotoba/lab/verification.kotoba`
- `test/kotoba/lab/verification_conformance.kotoba`

Legacy CLJC oracles remain at `src/kotoba/lab/verification.cljk` and
`src/kotoba/lab/verification_check.cljk`; consumers must not select them as
the active contract.

Current browser runner:

- `scripts/verify-lab.js`
