# Side-channel threat model v1

Status: enforced production baseline  
Date: 2026-07-23

## Scope

This model covers secrets handled by aiueos host adapters, signing and audit
cryptography, and mutually distrustful Wasm components sharing a physical
host. It considers:

- timing differences caused by secret-dependent work;
- shared-cache observation, including SMT sibling leakage;
- Spectre-class speculative execution across component and host boundaries.

Power, electromagnetic, physical-probe, malicious-firmware and privileged-host
attackers remain outside the software-only profile. Deployments exposed to
those attackers must not claim this baseline as sufficient.

## Required decisions

Every `sensitive-local` or `regulated` boot supplies a version-1
`:side-channel-decision` whose digest binds the deployment-specific extension
of this model. The decision must enumerate exactly `:timing`, `:cache`, and
`:spectre`, select only known mitigations, name an approver and approval time,
and explicitly accept residual risk.

The enforced `sensitive-local` minimum is:

- single-tenant host operation;
- constant-time cryptographic implementations.

The enforced `regulated` minimum additionally is:

- SMT disabled;
- isolated cores;
- host/firmware speculation controls enabled.

Optional enforced vocabulary includes secret zeroization and prohibition of
secret-dependent branches. A control assertion is admission metadata, not
proof that firmware, kernel or hardware actually applied it. Attested boot,
host-configuration collection and independent validation remain required
release evidence.

## Residual risk

Even with these mitigations, microarchitectural leakage is not proven absent.
Hardware defects, incomplete speculation mitigations, shared uncore resources,
JIT/runtime behavior and future attack classes remain. Production admission
therefore requires an explicit, deployment-specific residual-risk acceptance;
`high-assurance` remains blocked.
