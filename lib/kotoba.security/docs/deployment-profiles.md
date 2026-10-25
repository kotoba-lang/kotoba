# Deployment profiles

Security claims for kotoba-lang runtimes are **profile-specific**. Naming a
profile in a release evidence packet is recommended for research packets and
**hard-required** for regulated releases (`:deployment-profile` claim in the
safe-release gate when `--profile regulated`).

| Profile | Intended use | Claims allowed | Non-claims |
|---------|--------------|----------------|------------|
| `research` | demos, local experiments | capability confinement, fuel/memory limits, audit receipts | no FIPS, no side-channel, no multi-tenant isolation, no formal verification |
| `sensitive-local` | single-tenant local systems | research + host hardening expectations, encrypted audit/data preferred | no FIPS, no side-channel, no co-tenant secrets |
| `regulated` | orgs needing evidence packs | sensitive-local + SBOM/SLSA, key lifecycle, monitoring, provider policy | FIPS only inside named module boundaries with evidence; PQC only when hybrid path is deployed |
| `high-assurance` | blocked until evidence exists | none by default | formal verification + side-channel controls required before use |

## Gate behavior by profile

| Profile | `:deployment-profile` claim | key-register |
|---------|-----------------------------|--------------|
| `research` (default) | recommended (`:kotoba.release/recommended-missing`) | optional; if supplied, must evaluate cleanly |
| `regulated` | **required** for that evaluation | **required**; must have ≥1 `:active` key |

```sh
kbb --backend sci --classpath src scripts/check-safe-release.cljk --release --profile research
kbb --backend sci --classpath src scripts/check-safe-release.cljk --release --profile regulated
kbb --backend sci --classpath src scripts/check-key-register.cljk --require-active
```

## Operator checklist

1. Pick a profile and put it in the release evidence claims.
2. For any network capability, set a non-empty origin/URL allowlist
   (`:kotoba.policy/capability-resources` / `:aiueos/net-allow`).
   Language runtime default: `:kotoba.policy/http-require-allowlist` is **on**
   (see `kotoba-lang/kotoba` `docs/deployment-profiles.md`).
3. Pass a key-register into package admission (`--key-register`) so revoked /
   pre-active / compromised signers cannot authorize new locks.
4. For regulated releases, run the safe-release gate with `--profile regulated`
   and ensure at least one key is `:active` **after** out-of-band secret
   provisioning (never commit private keys here).
5. Do not claim FIPS, PQC, side-channel resistance, or multi-tenant isolation
   unless the profile row above allows it **and** evidence exists.
