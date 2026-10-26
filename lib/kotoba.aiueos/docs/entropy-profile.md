# Security entropy profile v1

Status: enforced production baseline  
Date: 2026-07-23

The only guest API intended for keys, nonces and tokens is the typed
`:random/bytes` / `random_bytes(ptr,len)` capability.

`aiueos.entropy` selects `SecureRandom.getInstanceStrong()`, records its
algorithm, provider, provider version and JVM strong-algorithm policy, and
limits every request to 1–4096 bytes before allocation.

Every sample is withheld from guest memory until it passes:

- continuous duplicate-block detection;
- repetition-count detection;
- adaptive-proportion detection on sufficiently large samples.

These online checks detect gross provider failure; they do not prove entropy
quality. Production evidence must capture the runtime provider identity and
health-test set. A FIPS claim additionally requires a named validated module,
boundary evidence, and an explicit assertion that the entropy provider is
inside that validated boundary.

Deterministic PRNGs used by simulations and test fixtures are not security
entropy and must never be exposed through `:random/bytes`.
