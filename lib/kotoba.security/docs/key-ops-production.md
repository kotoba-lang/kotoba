# Production Key Operations Runbook

Status: operational baseline (demo keys ≠ production HSM)
Date: 2026-07-17

## Purpose

End-to-end operator procedure for package-signing (and related) keys:

1. Provision private material **out-of-band** (never in git).
2. Register **public** material only in `registers/key-register.edn`.
3. Promote, retire, revoke, and rotate via pure helpers in
   `src/kotoba/security/key_status.cljk`.
4. Gate releases with `check-key-register` / regulated safe-release.
5. Consumers fold the register into package admission with
   `kotoba package verify --key-register`.

This document is the production path. Residual: demo keys in this repo use
out-of-band demo storage, **not** a production HSM/kagi compartment. Do not
treat demo public keys as production trust roots.

## Non-negotiables

| Rule | Detail |
|---|---|
| No private keys in git | Never commit PEM, seed, kagi export, or HSM unwrap blobs |
| Public material only | `:key/public-key` (+ encoding) is registerable |
| Pure lifecycle | `promote-to-active` / `retire-key` / `revoke-key` edit EDN maps only |
| Fail closed for new artifacts | Non-`:active` statuses are blocked (`blocked-for-new-artifacts`) |
| Historical verify window | Retired keys may set `:key/verify-until` for old receipts |

## 1. Provision out-of-band (kagi / HSM / OS keychain)

### Preferred: kagi (OS Keychain-backed compartment)

When kagi is available on the operator host:

```sh
# Example names only — adapt to your fleet/kagi policy.
# Private key never leaves the keychain compartment.
kagi key generate --name fleet-package-signing-YYYYQN --alg ed25519
kagi key public  --name fleet-package-signing-YYYYQN --format raw-base64
```

Record the **public** base64 (32-byte Ed25519) for the register. Signing
operations use `--kagi <name>` (or equivalent) at the signing boundary;
this repository does not hold the secret.

### Alternative: HSM / PKCS#11 / cloud KMS

1. Generate Ed25519 (or hybrid) key inside the HSM/KMS.
2. Export **public** key only.
3. Set `:key/storage :hsm` (or `:kms`) and document the slot/key id in
   `:key/notes` (no secret material).
4. If claiming FIPS, generation/sign must stay inside the validated module
   boundary (`docs/fips-validation.md`). Default design makes **no** FIPS claim.

### Demo / research only

`openssl genpkey -algorithm Ed25519` locally is acceptable for research-demo
keys. Private material stays on the operator machine; only the public key
lands in git. Mark `:key/storage :out-of-band-demo` and notes as non-production.

## 2. Register public material only

Append (or edit) an entry in `registers/key-register.edn`:

```edn
{:key/id "package-signing-2026q4"
 :key/class :package-signing
 :key/algorithm :ed25519
 :key/status :pre-active
 :key/owner :package-owner
 :key/created-at "2026-07-17"
 :key/active-from nil
 :key/active-until nil
 :key/verify-until nil
 :key/public-key "<base64-raw-32>"
 :key/public-key-encoding :base64-raw-32
 :key/storage :kagi   ; or :hsm / :out-of-band-demo
 :key/fips-boundary nil
 :key/pq-status :classical-only
 :key/notes "Public material only. Private key out-of-band; never in-repo."}
```

Optional `:key/signer` may carry the DID used in lockfiles
(e.g. `did:key:z6Mk…`) when it differs from `:key/id`.

Validate structure:

```sh
kbb --backend sci --classpath src scripts/check-key-register.cljk
```

## 3. Promote to active

After the private key is live out-of-band and dual-control/change record
exists:

```clojure
(require '[kotoba.security.key-status :as ks])
(def promoted
  (ks/promote-to-active pre-active-key "2026-07-17" "2026-10-15"))
;; write `promoted` back into registers/key-register.edn (public fields only)
```

Then:

```sh
kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active
```

## 4. Rotate (new active + old retired with verify-until)

Planned rotation (not compromise):

```clojure
(require '[kotoba.security.key-status :as ks])
;; new-key starts as :pre-active with public material already registered
(def result
  (ks/rotate-signing-key old-active-key new-pre-active-key
                         "2026-07-17"   ; now
                         "2033-07-17")) ; verify-until for historical receipts
;; result: {:ok? true :new <active> :old <retired> :problems []}
```

Equivalent steps:

1. `promote-to-active` on the new key.
2. `retire-key` on the old key with `verify-until` (retention window).
3. Persist both maps; leave private material of the old key under HSM/kagi
   until destroy policy says otherwise.
4. Re-run `check-key-register --require-active`.
5. Consumers re-pull the register; new locks must be signed by the new key.

## 5. Revoke (incident / compromise)

See also `docs/incident-response.md` playbook **Compromised package signer**.

```clojure
(ks/revoke-key active-key "compromised signing host" "2026-07-17")
```

Effects:

- Status `:revoked` → blocked for **new** artifacts.
- Publish evidence-index entry + advisory.
- Assess historical artifacts signed by that key.
- Promote a replacement key (steps 1–3).

Do **not** leave production registers with zero active package-signing keys
if you still need regulated releases.

## 6. Gate: check-key-register --require-active

```sh
# Research / CI default — may pass with only template pre-active keys
kbb --backend sci --classpath src scripts/check-key-register.cljk

# Regulated packaging — requires >=1 :active key and no register problems
kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active

# Full safe-release under regulated profile
kbb --backend sci --classpath src scripts/check-safe-release.cljk --release --profile regulated
```

## 7. Consumer: package verify --key-register

Downstream (`kotoba-lang/kotoba`):

```sh
bin/kotoba-clj package verify \
  --lock kotoba.lock.edn \
  --trust trust.edn \
  --key-register path/to/key-register.edn \
  --receipt target/package-receipt.edn \
  --json
```

Admission folds every non-`:active` register entry into trust
`:revoked-signers`. Locks signed only by revoked/pre-active/retired/etc.
keys fail with `:package/signer-not-trusted`.

## Rotation sequence (quick checklist)

| Step | Action | Proof |
|---|---|---|
| 1 | Generate secret out-of-band (kagi/HSM) | Operator ticket; no git artifact |
| 2 | Register public key as `:pre-active` | key-register PR (public only) |
| 3 | Promote new key | `promote-to-active` + `--require-active` |
| 4 | Retire old key with verify-until | `retire-key` / `rotate-signing-key` |
| 5 | Sign new releases with new key | package receipt |
| 6 | Consumers verify with register | `package verify --key-register` |
| 7 | Later destroy private material | HSM/kagi destroy procedure; status → `:destroyed` |

## Residual risks (honest)

- Demo keys in this repository are **not** production HSM custody.
- Side-channel / formal verification remain non-claims (see R-008 / EV-0008).
- FIPS is not claimed without a named validated module boundary (R-003).
- Continuous monitoring of live deployments is still incomplete (R-005).

## Related

- [Key Lifecycle](key-lifecycle.md) — states, periods, separation
- [Incident Response](incident-response.md) — compromised signer playbook
- [Deployment Profiles](deployment-profiles.md) — research vs regulated
- `src/kotoba/security/key_status.cljk` — pure helpers
- `scripts/check-key-register.cljk` — register gate
- `scripts/check-key-lifecycle-drill.cljk` — synthetic revoke drill
- Evidence: EV-0009 (demo activation), EV-0010 (technical revoke drill),
  EV-0011 (tabletop), EV-0012 (technical IR drill alias)
