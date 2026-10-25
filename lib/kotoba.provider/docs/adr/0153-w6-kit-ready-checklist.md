# ADR 0153: W6 capability kit ready checklist (T8.1)

- Status: Accepted
- Date: 2026-07-28

## Context

Reliability WBS **T8.1** requires a shared kit ready checklist so “granted
capability” confidence matches a well-tested client library. T8.3 asks for
**signed** network/secret providers; that must not be faked by labeling
reference-impl dual-runtime as “signed”.

## Decision — checklist dimensions

A kit is scored per dimension (not a single boolean):

| id | dimension | ready means |
|---|---|---|
| `schema` | typed request/result in kit EDN + provider map | present and validatable |
| `dual-runtime` | JVM + cljs reference invoke path | tests green on both where applicable |
| `deny-fixtures` | not-allowed / out-of-policy cases | negative tests or pure validators |
| `quota` | byte/item/timeout bounds | documented in kit `:limits` |
| `audit` | host audit hook or explicit N/A | documented (ops kits often host-audit) |
| `host-parity` | 2-host / dual-runtime parity evidence | linked tests or smoke |
| `package` | capability-kit EDN registered in conformance | resource path lands |
| `signed-wasm` | content-addressed **signed** Wasm provider artifact | production claim only |

### Status vocabulary

- `:ready` — dimension satisfied with evidence
- `:partial` — code exists, evidence incomplete
- `:pending` — not claimed
- `:n/a` — dimension does not apply (document why)

### Production signed claim gate

A kit may advertise **production signed provider** only when:

1. All of `schema`, `dual-runtime`, `deny-fixtures`, `quota`, `package` are `:ready`
2. `signed-wasm` is `:ready` with a content-address + signature receipt

Until then, kits may say `:reference :implemented` and must keep
`:signed-content-addressed-package :pending` (ADR 0152).

## Machine status

`resources/kotoba/lang/kit-readiness-v1.edn` applies this checklist (T8.2 first
pass) for HTTP / secret / process / scoped-fs / git / entropy / object-related
kits.

Package content-address of kit EDN (unsigned fingerprint) is available via
`provider.kit-package` — fingerprint ≠ signed production provider.

## Related

- ADR 0152 ops kit packages + signing honesty
- Reliability WBS T8.1–T8.3
