# dns kotoba

Phase E Option B reference implementation of dns (domain transfer workflow) on the etzhayyim substrate.

Per [ADR-2605203000](../../../90-docs/adr/2605203000-kotoba-write-target-options.md), dns migrates from vendor's `createKyselyDb` pattern to **Option B** — PDS XRPC writes via `@etzhayyim/sdk e.write()`.

Coverage: **6 of 6 (100%) canonical** dns commands ported (covering all 7 vendor lexicons).

| Tier | Commands | Slice |
|---|---|---|
| Transfer | createTransferRequest, getTransferRequest, transferFromSquarespace, putTransferStep, listTransferSteps, putTransferOutcome | **1** |

## Workflow

```
transferFromSquarespace (3-signer ClassA approvals required)
  ↓
TransferRequest (status: requested → approved)
  ↓
putTransferStep × 5 (disableAutoRenew → unlock → authCode → dnsExport → cfTransfer)
  ↓                  ↑ authCode MUST be signal:v1: encrypted
TransferOutcome (success → zoneDid auto-derived from domain
                 failure → status=failed
                 aborted → status=rolled-back)
```

## Authority-chain DIDs

```
did:web:dns.etzhayyim.com:transfer:{transferId-slug}   — TransferRequest
did:web:dns.etzhayyim.com:zone:{domain-slug}           — Zone (post-success)
```

## Security invariants

1. **3-signer ClassA approvals required** — `transferFromSquarespace` rejects with `needsApprovals` if fewer than 3 approvals supplied.
2. **authCode encryption** — `putTransferStep` with step=`authCode` MUST have `authCodeEncrypted` starting with `signal:v1:` (vault zero-knowledge invariant per root AGENTS.md).
3. **Idempotent step rkey** — each step is keyed by `(transferId, step)` so retries don't duplicate.
4. **Outcome auto-derives zoneDid** — only on `result: "success"` does the Outcome record include `did:web:dns.etzhayyim.com:zone:{domain-slug}`.

## Sibling reference impls (16 actors)

| Actor | Coverage | Status |
|---|---|---|
| (previously) | 15 actors canonical complete | — |
| **dns** | **6/6 (100%)** | **complete** |
