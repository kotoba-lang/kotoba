# Key Lifecycle

Status: proposed baseline
Date: 2026-07-01
Updated: 2026-07-17 (promote / revoke pure helpers + CLI)

## Purpose

Kotoba uses keys for package/component signing, DID/CACAO verification,
encrypted object wrapping, custody grants, audit commits, and transport. These
uses must be separated, inventoried, rotated, and revocable.

## Key Classes

| Class | Use | Default status |
|---|---|---|
| package-signing | package manifests, component releases | required before safe execution |
| identity-delegation | DID/CACAO verification relationships | required for delegated access |
| object-wrapping | envelope encryption recipient keys | required for private data |
| custody-share | t-of-N key share wrapping/release | required for sealed cold tier |
| audit-signing | commit/receipt signing | required for non-repudiation |
| transport | session security | deployment-specific |

## Lifecycle States

```text
pre-active -> active -> suspended -> retired -> destroyed
                         -> compromised
                         -> revoked
                         -> expired
```

State rules:

- `pre-active`: generated but not trusted for verification of **new** artifacts.
- `active`: may sign, wrap, or verify according to class policy.
- `suspended`: verify only while incident review is pending; not trusted for new artifacts.
- `retired`: verify historical artifacts only; cannot sign or wrap new data.
- `destroyed`: private material destroyed; public verification metadata retained.
- `compromised`: reject new artifacts and assess historical impact.
- `revoked`: explicit operator revocation; reject new artifacts.
- `expired`: crypto period ended; reject new artifacts.

Executable evaluation lives in `src/kotoba/security/key_status.cljk`:

- **blocked for new artifacts**: `:revoked` `:expired` `:compromised` `:retired` `:pre-active`
- **active for new artifacts**: `:active` only

## Pure transitions (`key_status.cljc`)

| Function | Effect | Secret material |
|---|---|---|
| `status-transition-ok?` | predicate over allowed edges | none |
| `promote-to-active` | set `:key/status :active`, `:key/active-from`, optional `:key/active-until` | **never invents** private keys; notes that material must be provisioned out-of-band |
| `revoke-key` | set `:key/status :revoked`, optional reason + `:key/revoked-at` | does not destroy secrets (operator step) |

Allowed edges (summary):

- `pre-active` → `active` | `revoked` | `destroyed`
- `active` → `retired` | `revoked` | `expired` | `suspended` | `compromised`
- `suspended` → `active` | `revoked` | `compromised` | `retired`
- `retired` / `expired` / `compromised` → `destroyed` | `revoked`
- `revoked` → `destroyed`
- `destroyed` → ∅ (terminal)

Illegal transitions return the key map unchanged with
`:key/transition-error {:problem :illegal-status-transition ...}`.

## CLI semantics

### Inspect the register

```sh
kbb --backend sci --classpath src scripts/check-key-register.cljk
kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active
```

- Default: print `active` / `blocked` / `problems`; exit 0 even when only
  template (`:pre-active`) keys exist (research posture).
- `--require-active`: exit 1 if no `:active` key or the register has problems.
  Use this for **regulated** release packaging.

### Promote / revoke (operator workflow)

These are pure library functions today — operators edit
`registers/key-register.edn` (or an out-of-band register) after calling them
from a REPL / small nbb one-liner. Example:

```clojure
(require '[kotoba.security.key-status :as ks])

;; After provisioning the real private key out-of-band (HSM / kagi / OS keychain):
(ks/promote-to-active pre-active-key "2026-07-17" "2026-10-17")

;; Incident or rotation:
(ks/revoke-key active-key "compromised signing host" "2026-07-17")
```

**Never** commit private key material to this repository. Template keys remain
`:pre-active` with `:key/storage :placeholder` until a real secret exists
outside git.

### Safe-release gate integration

```sh
# research / default — deployment-profile is recommended, not hard-required
kbb --backend sci --classpath src scripts/check-safe-release.cljk --release --profile research

# regulated — hard-require :deployment-profile claim + active key-register
kbb --backend sci --classpath src scripts/check-safe-release.cljk --release --profile regulated
```

See [deployment-profiles.md](deployment-profiles.md).

## Crypto Periods

Initial target crypto periods:

| Key class | Signing/wrapping period | Verification/retention |
|---|---|---|
| package-signing | 90 days for release keys | life of release plus 7 years |
| identity-delegation | 90 days for delegated grants | grant lifetime plus audit retention |
| object-wrapping | per data epoch, rotate on access-policy change | protected object retention |
| custody-share | per deal/epoch | protected object retention |
| audit-signing | 180 days | audit retention period |
| transport | short-lived sessions | not used for long-term proof |

## Separation Rules

- A package signing key must not wrap object encryption keys.
- An audit signing key must not authorize runtime capabilities.
- Transport keys must not be used for artifact provenance.
- Custody share keys must be scoped to custodian identity and epoch.
- PQ/hybrid keys must carry algorithm metadata and policy status.

## Revocation

Revocation requires:

- key id and class;
- revocation reason;
- effective time;
- affected artifacts or object epochs;
- replacement key id if any;
- evidence index entry.

Runtime and package verifiers must treat revoked package-signing keys as invalid
for new artifacts. Historical artifacts require incident-specific assessment.

Downstream: `kotoba-lang/kotoba` package admission folds non-`:active`
key-register entries into trust `:revoked-signers` via `--key-register`
(see that repo's `docs/deployment-profiles.md`).

## FIPS Boundary

If a deployment claims FIPS compliance, key generation, signing, encryption, and
randomness must occur inside the validated cryptographic module boundary for the
claimed control. The default repository design does not claim this.
