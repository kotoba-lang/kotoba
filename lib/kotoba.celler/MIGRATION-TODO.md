# Migration TODO

**Status**: 🔄 TRANSFORM — seed copied 2026-05-21, codemod pending.

**Codemod required**: seller / cellar storage — commerce carve-out

## Substrate-boundary checks (per AGENTS.md)

This seed was copied verbatim from `etzhayyim-root/60-apps/etzhayyim-project-celler`.
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

Automated annotation pass added `// CHARTER-VIOLATION` comments above each
detected violation line. The imports themselves were NOT removed (would break
the build). Remediation must replace these imports with the substrate-aligned
equivalents listed at the top of this file.

Detected violations:

```
  GA4/gtag: Binary file /Users/junkawasaki/github/etzhayyim-root/60-apps/etzhayyim-project-celler/appview/etzhayyim-wasm-celler-oilt0wta/etzhayyim-wasm-celler-oilt0wta matches:
```

---

## Post-verification gap patch (2026-05-21)

Additional violations detected in re-scan:

```
  - 60-apps/etzhayyim-project-celler/appview/etzhayyim-wasm-celler-oilt0wta/etzhayyim-wasm-celler-oilt0wta
```

Lines annotated with `CHARTER-VIOLATION §substrate` comments.
