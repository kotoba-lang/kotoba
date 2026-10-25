# Migration TODO (post-verification gap patch)

**Status**: 🔄 Substrate-boundary violation detected after ALIGN migration.

This app was originally classified as ALIGN (or already migrated as TRANSFORM)
but post-migration verification scan detected substrate-boundary violations
that were not previously flagged.

## Detected violations (per re-scan 2026-05-21):

```
  - 60-apps/etzhayyim-project-cloudflare-browser-render/appview/etzhayyim-wasm-cloudflare-browser-render-cfbr0w53/src/app.ts
```

## Required remediation (per AGENTS.md substrate boundary):

- [ ] Replace `@atproto/api` / `viem` / IPFS / Signal direct imports with `@etzhayyim/sdk`.
- [ ] Strip RisingWave / Postgres / Kysely / Drizzle / Prisma → AT MST + IPFS + Base L2.
- [ ] Strip Stripe / PayPal / fiat → USDC + ERC-4337 + `etzhayyim-tithe-router`.
- [ ] Remove GA4 / Meta Pixel / 3rd-party ad-tracking.
- [ ] Audit against Charter Rider v2.0 §2(a)-(h).

## Reference

- ADR-2605192100 / 2605192115 / 2605192200
- `/AGENTS.md` § Substrate boundary
- This file added by Coverage Gap Patch task #15.

