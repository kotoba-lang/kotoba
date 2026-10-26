# ADR-0012 — Binding `:aiueos/component` ids to authorized signers

- Status: accepted
- Date: 2026-07-13

## Context

ADR-0003 added Ed25519 signatures over the identity↔artifact binding
(`<component-id>\n<wasm-sha256>`), verified by `aiueos.signing/verify`
against a flat `:aiueos.policy/signers` registry (`{signer-id -> pubkey-hex}`).
A security audit (2026-07-13, landed alongside ADR-0011) found that this
proves *authenticity of the bytes under a claimed id*, not *that the specific
signer is the one authorized to claim that id*:

- `aiueos.broker/authenticate` resolves a valid signature to a `signer-id`
  and returns it — but that `signer-id` is discarded before reaching
  capability decisions. `aiueos.broker/verify-one` calls
  `aiueos.policy/verify-component m-eff graph policy`, which never receives
  `signer`.
- `aiueos.policy/granted-to` looks up `(:aiueos.policy/grants policy)` by
  `id` (`(:aiueos/component m)`) alone:

  ```clojure
  (defn granted-to [policy m]
    (let [... id (:aiueos/component m)
          extra (get (:aiueos.policy/grants policy) id #{})]
      (set/union base extra)))
  ```

- `:aiueos.policy/signers` is flat: any registered signer's key can produce
  a validly-signed manifest for **any** `:aiueos/component` id, including one
  `:aiueos.policy/grants` elevates with real privilege.

Net effect: under a `:aiueos.policy/require-signed` policy today, a
compromised or malicious *registered* signer — not necessarily the one an
operator intended to own a given component id — can sign a manifest claiming
a privileged id and receive that id's full grant. Signing proves "some
registered signer vouches for these exact bytes under this id," not "the
signer authorized to speak for this id vouches for it."

This is a real gap, but fixing it requires a policy-shape decision with
several reasonable answers and real tradeoffs — ADR-0011 deliberately left it
unfixed rather than guess. This ADR lays out the mechanism and the specific
decisions needed to close it.

## Mechanism

1. Add `:aiueos.policy/component-signers {component-id #{signer-id ...}}` to
   the policy shape (`aiueos.policy/default-policy`, default `{}`) — a set,
   not a single signer, so key rotation and multi-maintainer ids don't
   require a structural change later (add the new signer's id, drop the
   old one, no schema migration).
2. Thread `signer` from `aiueos.broker/authenticate`'s result into
   `aiueos.policy/verify-component`/`granted-to`. `verify-component`'s
   arity grows to `[m graph policy signer]`; `broker/verify-one` already
   computes `signer` via `authenticate`, so this is a threading change, not
   new computation. All existing 3-arg call sites (`policy/verify-system`,
   `test/aiueos/policy_test.cljc`) pass `nil` for `signer` unless they're
   specifically testing this feature, preserving today's behavior.
3. In `granted-to`, `id`'s `extra` grant is now gated as follows:
   - **`id` is a BOUND id** (has an entry in `component-signers`) — `extra`
     applies only when `signer` is a member of that entry's set. A bound id
     claimed by an unregistered/wrong signer, or presented unsigned, gets
     `base` only. This check is enforced **whenever a binding is declared,
     independent of `:aiueos.policy/require-signed`** — an operator who
     explicitly wrote a `component-signers` entry for an id means it, they
     shouldn't have to also flip a global flag for that specific
     declaration to take effect.
   - **`id` is UNBOUND** (no entry in `component-signers`) — see Decision
     below; this is the one case whose behavior depends on
     `require-signed`.
   Either way, a failed check is "no elevated grant," not a hard deny — same
   as an unrecognized id today, matching this codebase's existing "ungranted
   capability → the import simply fails to link" fail-closed pattern from
   ADR-0011 rather than inventing a new denial shape here.

## Decision

**Closed under `:aiueos.policy/require-signed`, no separate opt-in knob.**
Once a policy sets `require-signed true`, ANY id present in
`:aiueos.policy/grants` but *absent* from `:aiueos.policy/component-signers`
gets `base` only (kernel-caps ∩ surface), never the id-specific `extra`
grant, regardless of signature validity. `require-signed false` (permissive/
dev mode) is unaffected — see decision 2 below.

This was chosen over the initially-proposed "(A) open by default + separate
`:aiueos.policy/require-signer-binding` opt-in knob" compromise, on capability-
security grounds:

- **No ambient authority.** An id with elevated grants but no explicit
  signer binding is exactly the ambient-authority pattern capability systems
  exist to avoid — authority must flow from an explicit declaration, never
  from a default. This codebase already applies deny-by-default elsewhere
  (kernel-caps, `:ai-generated`/`:untrusted` forbid-effects); this decision
  makes signer-binding consistent with that, rather than a carved-out
  exception.
- **`require-signed true` is already the operator's explicit "I want strong
  guarantees" signal.** Leaving the id-claiming gap open specifically inside
  that mode undermines what the flag is supposed to mean. A separate
  `require-signer-binding` knob would recreate the "security feature nobody
  enables because they don't know it exists" failure class (the same shape
  as historical TLS hostname-verification opt-outs) — coupling the strict
  behavior directly to `require-signed` avoids that trap.
- **The compatibility risk is low and fails safe.** No shipped example
  policy in this repo sets `require-signed true` today (only
  `examples/signed/policy.edn` registers signers, without requiring them),
  so there is effectively no current deployment to break. And if some
  external deployment *is* affected, the failure direction is "a component
  silently gets fewer grants" (loud — something stops working, gets
  investigated) rather than "a component silently gets grants it shouldn't
  have" (quiet — the actual vulnerability this ADR closes).

### Unsigned components under a non-`require-signed` (permissive/dev) policy

When a component is unsigned and the policy doesn't require signatures,
`signer` is `nil` and there is no identity to bind against — the existing
bare-id `granted-to` lookup continues to apply unchanged. Requiring signer
identity for an unsigned component would be incoherent (there is nothing to
check), so this path is unaffected by the decision above.

### Rejected alternative — namespaced component ids

Considered and NOT recommended: instead of a separate binding table, require
`:aiueos/component` ids to be structurally scoped by owner (e.g.
`<signer-id>/<local-name>`, mirroring npm scoped packages or reverse-DNS
Java package names) so the owning signer is unforgeable by construction —
no table to keep in sync, no way to "forget" a binding. Rejected for now
because it is far more invasive (every existing component id would need
renaming; every manifest-authoring workflow and doc referencing bare ids
would need updating) for a benefit an explicit binding table already
delivers at much lower migration cost. Worth revisiting only if the
binding-table approach proves operationally painful to maintain at scale
(e.g. many ids, frequent rotation) once it has real usage data behind it.

## Consequences

- `aiueos.policy/verify-component`/`granted-to` gain a `signer` parameter;
  `aiueos.broker/verify-one` (the only caller with the resolved signer
  already in hand) threads it through for free.
- New policy field `:aiueos.policy/component-signers` (default `{}`, i.e. no
  ids bound — under `require-signed false` this is a no-op; under
  `require-signed true` an unbound id with `:aiueos.policy/grants` now gets
  `base` only, per the Decision above).
- `src/aiueos/contract.cljc`'s `deployment-policy-optional-keys` and
  `validate-deployment-policy` (the `:aiueos/*` overlay's field-name
  validation) need the new field(s) added. NOT `resources/aiueos/
  policy_contract.edn`/`aiueos.contract`'s `validate-policy-contract` —
  that's a different contract (decision-level enumerations: kernel-cap
  values, forbid-effects, `:aiueos.policy/decision-shapes`, `:aiueos.policy/
  violation-kinds`, the grant record's own field names) that this ADR's
  mechanism doesn't touch, since it adds no new violation kind (a
  binding-mismatch is "no elevated grant," not a hard deny) and doesn't
  change the grant record shape.
- No change to `aiueos.execute`/ADR-0011's link-time enforcement — this ADR
  only affects which capabilities `verify-component` decides to grant in the
  first place, not how a granted set is subsequently enforced at the wasm
  host-import boundary.
