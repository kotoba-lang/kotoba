/**
 * @etzhayyim/auth — trust-scoring tests (coverage loop iteration 19).
 *
 * trust.ts computes the shell-wide trust score + label + access gating that
 * every *.etzhayyim.com app reads to decide what a user can reach. Pure
 * function of (user, org); zero tests. A scoring or gate bug silently
 * over- or under-grants access. Isolated island → root pnpm-lock untouched.
 */
import { describe, it, expect } from "vitest";
import {
  buildTrustSummary,
  trustVariantFromScore,
  normalizeExternalAccount,
} from "../src/lib/trust.ts";
import type { ClerkUserInfo, Organization } from "../src/lib/types.ts";

function user(over: Partial<ClerkUserInfo> = {}): ClerkUserInfo {
  return {
    id: "u1", firstName: null, lastName: null, fullName: null, username: null,
    emailAddress: null, phoneNumber: null, hasVerifiedEmail: false, hasVerifiedPhone: false,
    imageUrl: null, publicMetadata: {}, ...over,
  };
}
function org(metadata: Record<string, unknown> = {}, over: Partial<Organization> = {}): Organization {
  return { id: "o1", name: "Org", slug: "org", category: "c", role: "member", metadata, ...over };
}

// ── trustVariantFromScore ────────────────────────────────────────────────────

describe("trustVariantFromScore", () => {
  it("maps score bands to UI variants", () => {
    expect(trustVariantFromScore(0)).toBe("default");
    expect(trustVariantFromScore(24)).toBe("default");
    expect(trustVariantFromScore(25)).toBe("warning");
    expect(trustVariantFromScore(50)).toBe("accent");
    expect(trustVariantFromScore(75)).toBe("success");
  });
});

// ── guest (no user) ──────────────────────────────────────────────────────────

describe("buildTrustSummary — guest", () => {
  it("returns the guest summary with onboarding steps and first threshold target", () => {
    const s = buildTrustSummary(null, null);
    expect(s.score).toBe(0);
    expect(s.label).toBe("guest");
    expect(s.nextScoreTarget).toBe(25);
    expect(s.methods).toEqual([]);
    expect(s.accessReady).toBe(true);
  });

  it("surfaces org gates as access reasons for a guest", () => {
    const s = buildTrustSummary(null, org({ minimumTrustScore: 50, minimumAge: 18 }));
    expect(s.accessReady).toBe(false);
    expect(s.accessReasons).toContain("Trust score 50+ required");
    expect(s.accessReasons).toContain("Age 18+ required");
  });
});

// ── score accumulation ───────────────────────────────────────────────────────

describe("buildTrustSummary — score model", () => {
  it("base account scores 5 → starter", () => {
    const s = buildTrustSummary(user(), null);
    expect(s.score).toBe(5);
    expect(s.label).toBe("starter");
    expect(s.methods).toContain("clerk");
  });

  it("accumulates per-method points and detects methods", () => {
    // base 5 + username 15 + email 10 + phone 20 + wallet 20 + social 10 = 80
    const s = buildTrustSummary(user({
      username: "alice", hasVerifiedEmail: true, hasVerifiedPhone: true,
      web3Wallets: [{ id: "w", web3Wallet: "0x1" }],
      externalAccounts: [{ id: "e", provider: "google", label: "Google", verified: true }],
    }), null);
    expect(s.score).toBe(80);
    expect(s.label).toBe("high-trust");
    expect(new Set(s.methods)).toEqual(new Set(["clerk", "username", "email", "phone", "metamask", "social"]));
  });

  it("clamps to 100 and age verification adds 20", () => {
    const s = buildTrustSummary(user({
      username: "a", hasVerifiedEmail: true, hasVerifiedPhone: true,
      web3Wallets: [{ id: "w", web3Wallet: "0x1" }],
      externalAccounts: [{ id: "e", provider: "x", label: "X", verified: true }],
      publicMetadata: { ageVerified: true },
    }), null);
    // 80 + 20 (age) = 100 (no clamp needed here, but verify ceiling holds)
    expect(s.score).toBe(100);
    expect(s.ageVerified).toBe(true);
  });

  it("an explicit trustScore in metadata overrides the additive model", () => {
    const s = buildTrustSummary(user({ username: "a", publicMetadata: { trustScore: 42 } }), null);
    expect(s.score).toBe(42);
    expect(s.label).toBe("verified");      // 25..49
    expect(s.nextScoreTarget).toBe(50);
  });

  it("label thresholds: starter/verified/trusted/high-trust", () => {
    const at = (n: number) => buildTrustSummary(user({ publicMetadata: { trustScore: n } }), null).label;
    expect(at(0)).toBe("guest");           // score 0 → guest
    expect(at(1)).toBe("starter");
    expect(at(25)).toBe("verified");
    expect(at(50)).toBe("trusted");
    expect(at(75)).toBe("high-trust");
  });
});

// ── access gating ────────────────────────────────────────────────────────────

describe("buildTrustSummary — access gating", () => {
  it("blocks when score is below the org's required trust score", () => {
    const u = user({ username: "a" }); // score 20
    const s = buildTrustSummary(u, org({ minimumTrustScore: 50 }));
    expect(s.accessReady).toBe(false);
    expect(s.accessReasons).toContain("Needs trust score 50+");
  });

  it("blocks on age: missing vs under minimum; ready when of age", () => {
    const base = user({ publicMetadata: { trustScore: 80 } });
    const noAge = buildTrustSummary(base, org({ minimumAge: 18 }));
    expect(noAge.accessReasons).toContain("Needs age 18+");

    const young = buildTrustSummary(
      user({ publicMetadata: { trustScore: 80, ageYears: 15 } }), org({ minimumAge: 18 }));
    expect(young.accessReasons).toContain("Available for age 18+");

    const okAge = buildTrustSummary(
      user({ publicMetadata: { trustScore: 80, ageYears: 21 } }), org({ minimumAge: 18 }));
    expect(okAge.accessReady).toBe(true);
  });

  it("reads org-level requiredTrustScore/minimumAge fallback fields", () => {
    const s = buildTrustSummary(user({ username: "a" }), org({}, { requiredTrustScore: 50 }));
    expect(s.requiredTrustScore).toBe(50);
    expect(s.accessReady).toBe(false);
  });
});

// ── normalizeExternalAccount ─────────────────────────────────────────────────

describe("normalizeExternalAccount", () => {
  it("requires an id; humanizes the provider label", () => {
    expect(normalizeExternalAccount({ provider: "google" })).toBeNull(); // no id
    const a = normalizeExternalAccount({ id: "e1", provider: "google_oauth" })!;
    expect(a.label).toBe("Google Oauth");
    expect(a.provider).toBe("google_oauth");
    expect(a.verified).toBe(false);
  });

  it("derives verified from verificationStatus/status or nested verification", () => {
    expect(normalizeExternalAccount({ id: "1", verificationStatus: "verified" })!.verified).toBe(true);
    expect(normalizeExternalAccount({ id: "2", status: "verified" })!.verified).toBe(true);
    expect(normalizeExternalAccount({ id: "3", verification: { status: "verified" } })!.verified).toBe(true);
    expect(normalizeExternalAccount({ id: "4", verification: { status: "pending" } })!.verified).toBe(false);
  });
});
