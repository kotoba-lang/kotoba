# Migration TODO

**Status**: ✅ ad-pixel codemod complete (2026-05-23) — see closure section below for details.

**Codemod required**: strip ad-pixel/GA4 + DID-bind auth

> **Resolved (ad-pixel layer)** — see closure section below. DID-bind-auth + affiliate-revenue-paths still pending if listed in the checklist.

## Substrate-boundary checks (per AGENTS.md)

This seed was copied verbatim from `etzhayyim-root/60-apps/etzhayyim-project-meeting-recorder`.
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

---

## ad-pixel codemod closure (2026-05-23)

<!-- ad-pixel-codemod-closure:2605231600 -->

**Status**: ✅ ad-pixel / GA4 / AdSense / Meta Pixel codemod **complete** — verified clean.

Re-scan on 2026-05-23 confirmed zero matches across this app's source
tree (excluding `node_modules/`, `dist/`, `.svelte-kit/`, build outputs)
for: `googletagmanager.com`, `google-analytics.com`, `gtag(`, `fbq(`,
`connect.facebook.net`, `adsbygoogle`, `google-adsense`, `amplitude`,
`mixpanel`, `segment.com/analytics`, `hotjar`, `GoogleAnalytics`.

Per ADR-2605192115 §1.2 (No Advertising hard rule) + ADR-2605192100 §1.6
(Mission Charter middleman elimination). DID-bind-auth check remains a
separate item — see `auth` checklist above.

_Closed by `70-tools/scripts/codemod/2605231600-ad-pixel-codemod-closure.mjs`._
