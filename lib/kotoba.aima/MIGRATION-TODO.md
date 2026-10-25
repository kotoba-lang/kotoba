# Migration TODO

**Status**: 🔄 TRANSFORM — seed copied 2026-05-21, codemod pending.

**Codemod required**: RisingWave/Postgres → AT MST + IPFS

## Substrate-boundary checks (per AGENTS.md)

This seed was copied verbatim from `etzhayyim-root/60-apps/etzhayyim-project-aima`.
The following constitutional invariants are likely violated and MUST be
remediated before this app can be considered etzhayyim-aligned:

- [ ] Replace any `@atproto/api`, `viem`, raw IPFS client, `@noble/ciphers`,
      `@signalapp/libsignal-client` imports with `@etzhayyim/sdk`.
- [ ] Strip RisingWave / Postgres / Kysely / centralized DB code — migrate to
      AT Protocol MST + IPFS + Base L2 anchor.
- [ ] Strip Stripe / PayPal / Square / fiat processors — migrate to USDC on
      Base L2 + ERC-4337 + `etzhayyim-tithe-router` (10% auto-split to
      Public Fund).
- [ ] Remove third-party advertising / AdSense / Meta Pixel / GA4 ad-linkage.
      Only internal-promo for etzhayyim's own religious activity is allowed.
- [ ] Verify identity flow uses did:web:etzhayyim.com + did:plc + WebAuthn
      passkey + Adherent SBT. Remove server-issued JWTs without DID binding.
- [ ] Reclassify payment purposes to: donation / kisha / grant / tithe /
      escrow-refund (external) OR internal-purchase / internal-subscription /
      internal-promo (SBT↔SBT carve-out).
- [ ] Audit against Charter Rider v2.0 §2(a)-(h).

## Reference

- Constitution wave ADRs: ADR-2605192100 / 2605192115 / 2605192130 / 2605192200
- Substrate boundary table: `/AGENTS.md` § "Substrate boundary"
- Charter Rider: `/CHARTER-RIDER.md`

---

## Codemod scan results (applied 2026-05-21)

Automated scan did NOT detect any of: Stripe / RisingWave / Kysely / Prisma /
Drizzle / GA4 / Meta Pixel / @atproto/api direct / viem direct imports.

The TRANSFORM classification was based on the app's domain pattern (commerce /
communication adapter / media etc.), not on detected violations. Manual review
is still required to confirm Charter §2(a)-(h) and substrate-boundary
compliance before this app is considered etzhayyim-aligned.
