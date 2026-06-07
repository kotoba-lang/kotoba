import { describe, it, expect } from "vitest";
import {
  parseSegmentHash,
  apqcL1DidFromSegment,
  deriveCohortEventType,
} from "../src/cohort.js";

describe("parseSegmentHash", () => {
  it("parses minimum required fields", () => {
    const s = parseSegmentHash(
      "sha256:pcfL1=3-market-sell;role=salesRep;locale=jp",
    );
    expect(s).toEqual({
      pcfL1: "3-market-sell",
      role: "salesRep",
      industry: null,
      locale: "jp",
    });
  });

  it("parses industry overlay", () => {
    const s = parseSegmentHash(
      "sha256:pcfL1=9-financial-resources;role=accountant;industry=banking;locale=jp",
    );
    expect(s?.industry).toBe("banking");
  });

  it("parses seniority overlay", () => {
    const s = parseSegmentHash(
      "sha256:pcfL1=8-info-technology;role=sreEngineer;seniority=senior;locale=jp",
    );
    expect(s?.seniority).toBe("senior");
    expect(s?.industry).toBeNull();
  });

  it("rejects missing prefix", () => {
    expect(parseSegmentHash("pcfL1=1;role=x;locale=jp")).toBeNull();
  });

  it("rejects missing required keys", () => {
    expect(parseSegmentHash("sha256:pcfL1=1-vision-strategy")).toBeNull();
    expect(parseSegmentHash("sha256:role=x;locale=jp")).toBeNull();
  });
});

describe("apqcL1DidFromSegment", () => {
  it("builds canonical path-based DID", () => {
    const s = parseSegmentHash(
      "sha256:pcfL1=7-human-capital;role=hrGeneralist;locale=jp",
    )!;
    expect(apqcL1DidFromSegment(s)).toBe(
      "did:web:kyber-projector.etzhayyim.com:apqc:7-human-capital",
    );
  });

  it("supports alternate projector host", () => {
    const s = parseSegmentHash(
      "sha256:pcfL1=1-vision-strategy;role=strategist;locale=en",
    )!;
    expect(apqcL1DidFromSegment(s, "staging-projector.etzhayyim.com")).toBe(
      "did:web:staging-projector.etzhayyim.com:apqc:1-vision-strategy",
    );
  });
});

describe("deriveCohortEventType", () => {
  const base = {
    evidenceCountBefore: 5,
    posterior: 0.5,
    judgeAgreement: false,
    kProxy: 100,
    fissionEnabled: false,
    didFission: false,
  };

  it("returns cohort.fission when didFission true", () => {
    expect(deriveCohortEventType({ ...base, didFission: true })).toBe(
      "cohort.fission",
    );
  });

  it("returns cohort.kReevaluated when k_proxy < 50", () => {
    expect(deriveCohortEventType({ ...base, kProxy: 49 })).toBe(
      "cohort.kReevaluated",
    );
  });

  it("returns cohort.evidence.fissionReady when gated conditions pass", () => {
    expect(
      deriveCohortEventType({
        ...base,
        posterior: 0.96,
        judgeAgreement: true,
        fissionEnabled: true,
      }),
    ).toBe("cohort.evidence.fissionReady");
  });

  it("does NOT return fissionReady when fission_enabled is false", () => {
    expect(
      deriveCohortEventType({
        ...base,
        posterior: 0.96,
        judgeAgreement: true,
        fissionEnabled: false,
      }),
    ).toBe("cohort.evidence.accrued");
  });

  it("returns cohort.genesis on first evidence", () => {
    expect(
      deriveCohortEventType({ ...base, evidenceCountBefore: 0 }),
    ).toBe("cohort.genesis");
  });

  it("defaults to cohort.evidence.accrued", () => {
    expect(deriveCohortEventType(base)).toBe("cohort.evidence.accrued");
  });

  it("k drift takes precedence over fission ready", () => {
    expect(
      deriveCohortEventType({
        ...base,
        posterior: 0.99,
        judgeAgreement: true,
        fissionEnabled: true,
        kProxy: 10,
      }),
    ).toBe("cohort.kReevaluated");
  });
});
