# Incident Response

Status: proposed baseline
Date: 2026-07-01

## Purpose

Kotoba's architecture produces receipts, denials, CIDs, manifests, and package
locks. Incident response must preserve and use that evidence quickly without
overwriting the state needed for forensics.

## Severity Model

| Severity | Definition | Examples | Initial response |
|---|---|---|---|
| SEV-1 | active compromise or private data exposure | signing key leak, unauthorized key release, host escape | freeze releases, rotate/revoke keys, preserve evidence |
| SEV-2 | exploitable security boundary failure | safe-build bypass, ambient host import, registry signature bypass | disable affected path, publish advisory draft |
| SEV-3 | control degradation with workaround | missing SBOM, failed monitoring, stale signer | create tracked remediation |
| SEV-4 | documentation or evidence gap | outdated DoDAF view, missing review note | fix in normal cadence |

## Triage Inputs

- component manifest and wasm digest;
- package manifest, lockfile, repo RID, tree CID, component CID;
- policy file and effective grants;
- run receipt id and parent receipts;
- audit/access receipt CIDs;
- signer id and verification result;
- host/runtime version and surface;
- command or API request that triggered the event.

## Playbooks

### Safe-build bypass

1. Preserve source, policy, compiler version, generated Wasm, and run receipt.
2. Re-run safe-policy, safe-build, selfhost-inspect, and conformance fixtures.
3. Identify whether bypass is subset, type, effect, capability, package, or
   runtime host-call enforcement.
4. Disable affected host import or package path if exploit is practical.
5. Add negative fixture before fixing implementation.
6. Publish advisory if released artifacts are affected.

### Compromised package signer

1. Mark signer key status as `:compromised` in key register.
2. Reject future packages signed only by that key.
3. Find package manifests and lockfiles using the signer.
4. Rebuild affected component CIDs from trusted source or quarantine.
5. Publish replacement lock records and advisory.

### Unauthorized key release

1. Preserve grant, receipt log, custodian id, requester DID, purpose, and nonce.
2. Check whether receipt exists and matches the signed grant.
3. Rotate affected epoch keys for future writes.
4. Re-encrypt high-value content if plaintext exposure is plausible.
5. File warrant/slash evidence if custodian release was unreceipted.

### Host capability escape

1. Stop or isolate the affected surface.
2. Capture component manifest, effective capability set, import table, and host
   logs.
3. Confirm whether escape came from policy materialization or host adapter bug.
4. Remove affected capability provider until a regression test exists.

## Evidence Preservation

Incident evidence must be immutable or content-addressed:

- store source artifacts, policies, manifests, lockfiles, receipts, and logs by
  CID or immutable object digest;
- record hashes of external logs when CID storage is unavailable;
- do not rewrite audit logs during containment;
- store a timeline in [Evidence Index](../registers/evidence-index.edn).

## Closure Criteria

An incident closes only when:

- root cause is documented;
- affected assets and users are identified;
- fix or compensating control is merged;
- regression evidence exists;
- keys/signers/locks are rotated or revoked where needed;
- advisory and postmortem are linked in the evidence index.

