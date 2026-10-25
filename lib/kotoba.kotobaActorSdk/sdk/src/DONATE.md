# @etzhayyim/sdk/donate — USDC Donation Flow (v0.2)

Per **ADR-2605192115**, external fiat payment (Stripe/PayPal) is prohibited. The v0.2 donation surface routes all payment through USDC on Base L2.

## API Surface

```typescript
import { donate } from "@etzhayyim/sdk/donate";

const result = await donate(
  {
    to: "0x...",            // recipient address
    amountUsdc: "50.00",    // human-readable or bigint base units
    purpose: "donation",    // "donation" | "kisha" | "grant" | "tithe" | ...
    memo: "...",            // optional (≤280 chars)
    forUri: "at://...",     // optional AT URI being funded
  },
  {
    rpcUrl: "https://...",  // Base L2 RPC (optional)
    privateKey: "0x...",    // EOA private key (v0.1 path)
    sponsored: {...},       // SmartAccount bundle (v0.2 path, stub)
    pds: {...},             // AT PDS agent for payment.sent record
  }
);

// result = { txHash: "0x...", paymentReceipt: {...} }
```

## Purpose Enum

Allowed purposes (Charter Rider §2 & ADR-2605192115 §3):

| Purpose | Use case |
|---|---|
| `donation` | Unrestricted gift to etzhayyim |
| `kisha` | Structured charitable contribution (Japan religious org) |
| `grant` | Time-bound project funding |
| `tithe` | 10% → Public Fund atomic auto-split |
| `escrow-refund` | Reversible hold pending arbiter decision |
| `internal-purchase` | SBT↔SBT in-app transaction |
| `internal-subscription` | SBT↔SBT recurring access |
| `internal-promo` | SBT↔SBT promotional/gift mint |

## Implementation Notes

### v0.1 Path (EOA)
When `cfg.privateKey` is provided, routes through `PayClient.pay()`:
1. EOA signs USDC.transfer on Base L2
2. Receipt includes on-chain tx hash + block number
3. Optionally emits `payment.sent` AT record to PDS

### v0.2 Path (ERC-4337, stub)
When `cfg.sponsored` is provided:
1. **TODO**: Route through `sponsoredWriteContract()` with SmartAccount + bundler
2. **TODO**: Paymaster covers gas via allowlist validation
3. **TODO**: UserOperation finalized, tx hash returned

Currently falls back to v0.1 with a warn log.

### Tithe Router (v0.2)
When `purpose === "tithe"`, recipient should be the **TitheRouter.sol** contract:
- Transfers USDC to the router
- Router atomically splits: 90% → recipient, 10% → Public Fund
- Enforced at contract level; no SDK branching needed

## Validation

`isAllowedDonationPurpose(str)` validates a string against the enum.

```typescript
if (!isAllowedDonationPurpose(userInput.purpose)) {
  throw new Error("Prohibited purpose per Charter Rider §2");
}
```

## Error Handling

| Condition | Behavior |
|---|---|
| Both `privateKey` and `sponsored` missing | throw Error |
| Invalid USDC amount (parse failure) | throw Error from `parseUsdc()` |
| On-chain USDC.transfer reverts | throw "USDC.transfer reverted" |
| Invalid recipient address | throw from viem |

## Future Work (v0.3+)

- [ ] DID address resolution (did:web, did:plc → Base address lookup)
- [ ] TitheRouter integration witness + split verification
- [ ] ChartersComplianceRegistry attestation check before emit
- [ ] Superfluid payStream for recurring donations (v0.3)
- [ ] Escrow 2-of-3 Safe release flow (v0.3)
