# ADR: Shared security adoption v3 and effect authorization

- Status: Accepted; implementation increment closed
- Date: 2026-07-20
- Decision owners: Kotoba security maintainers
- Machine-readable closure: `policy/shared-security-adoption-v3-closure.edn`

## Context

Dependency pinning and namespace imports proved library presence, but did not
prove that every platform branch was inventoried, that security-sensitive code
could not avoid the library, or that an allow decision governed the eventual
side effect. A declared entrypoint could also load a control and ignore its
result.

## Decision

Adoption v3 is the required next contract. The central verifier preserves
reader conditionals, scans CLJ and CLJS branches including tagged literals,
requires an exact source/runtime control-edge inventory, and discovers a
high-confidence set of sensitive operations that must be bound to protected
entrypoints.

Side effects use `kotoba.security.effect`. The evaluator runs once. Its exact
allow decision is stored in an opaque grant bound to action, resource, and
digest. Grant removal is atomic and one-shot; denial, claim mismatch, and replay
cannot invoke the effect callback. The implementation is CLJC.

## Closed scope and evidence

The central implementation is merged through security PRs #61–#65. Three real
effect paths are migrated:

- `kagitaba.import.sealed-archive/decrypt-admitted!` — PR #9, main `aef9765b3a5912c4e6618da54ecd7423dfc5f2db`;
- `kototama.fleet-store/b2-authorize!` — PR #47, main `44787aa400c0696b76b11230b2e607bb5afebe9d`;
- `kotobase.code-graph/revoke-pin!` — PR #17, main `2f77d4444ddbf6f9f13dd84eba34a20217412299`.

This increment is closed because its central mechanism and the first three
security-relevant effect classes—decryption, credential-bearing network access,
and audited revocation—are implemented. Closing the increment does not mark the
whole stack v3-complete.

## Deferred to the next increment

- `aiueos`: signature verification and broker authentication;
- `kagi`: secret-store, clipboard, device-secret, and identity-secret paths;
- `kotoba`: secret-reference validation;
- remaining consumers: v3 pin and sensitive-operation manifest rollout;
- organization rulesets that prevent removal of the verifier workflow itself.

These items may not be represented as passing controls or used for a score
promotion until their consumer PR, CI evidence, and resulting main commit are
recorded.

## Consequences

Security-sensitive names can now expose missing control integration instead of
silently passing because no security import exists. Effect migration is more
explicit and sometimes requires an operation-specific evaluator. This is
intentional: a manifest-only exception or a constant-allow evaluator does not
satisfy this ADR.

## Non-claims

- Source inventory is not proof of semantic correctness.
- An effect grant is not production authorization without a real evaluator.
- Three migrated paths do not mean all eight repositories are adoption v3.
- CI evidence is not HSM, PQC, recovery, or operational E4/E5 evidence.
