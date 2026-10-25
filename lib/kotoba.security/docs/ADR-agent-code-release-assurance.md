# ADR — Security-by-Design assurance for autonomous-agent code

- Status: Accepted and partially implemented
- Date: 2026-08-15
- Scope: Kotoba package admission, signed modules, runtime containment, deployment and public claims

## Context

Kotoba is designed for programs authored and operated by autonomous agents. The
security boundary therefore cannot depend on a human noticing suspicious code.
Every grant, artifact and deployment transition must be machine-verifiable and
fail closed. NIST CSF 2.0 is used to organize cybersecurity outcomes, NIST SSDF
to organize secure-development evidence, and DoDAF to describe architecture and
evidence views. None of those references is a language certification.

Current implementation evidence supports a working Clojure-family profile,
Wasm execution and bounded native targets. It does not support claims of being
unhackable, universally safer or faster than Rust, or certified for regulated
and defence deployment.

## Decision

The release identity is one indivisible security object. A release is admitted
only when all of the following describe the same bytes and authority:

1. a verified package receipt contains the component CID;
2. supplied component bytes recompute to that CID;
3. a v2 module signature covers the complete module record, including exports,
   requested capabilities and module-graph digest;
4. a non-empty trust set contains the signer and the key register marks that
   signer active;
5. SBOM and provenance evidence are present; an unsigned exception cannot waive
   either requirement.

Legacy v1 signed-module envelopes fail closed. Compatibility must be provided by
explicit offline migration and re-signing, never by accepting an incompletely
bound envelope at the release boundary.

## Assurance ladder

| Level | Meaning | Required evidence |
|---|---|---|
| A0 | design | ADR and threat model only |
| A1 | executable | compiler/runtime path and deterministic tests |
| A2 | bounded pilot | negative security tests, complete release identity, resource ceilings |
| A3 | production | independent review, signed receipts and sustained soak |
| A4 | regulated profile | domain safety case, applicable certification and operational evidence |

Marketing and documentation must name the achieved level. Repository count,
architecture intent and green unit tests are not substitutes for A3 or A4.

## Implementation status

- Implemented here: receipt/component binding, complete module-metadata
  signature, non-empty trust, active signer and mandatory SBOM/provenance.
- Required for A2: persistent CACAO replay store; structural URL-scope checks;
  Wasm memory maximum and host limiter; HTTP timeout/streaming quota; deployment
  admission bound to immutable release evidence.
- Required for A3: independent adversarial review and multi-run production soak.
- Required for A4: a domain-specific safety case and external assessment.

## Claim policy

Until A3 evidence exists, public language must use “pilot-grade” and “bounded
native targets”. It may say that Kotoba is designed to reduce ambient authority
for AI-authored code. It must not say “unhackable”, “safer and faster than Rust”,
or “ready for medical, financial or military use”.

## Verification

`test/kotoba/security/release_evidence_test.cljk` is the executable negative
contract for the implemented decision. Removing any binding above must make at
least one test fail.
