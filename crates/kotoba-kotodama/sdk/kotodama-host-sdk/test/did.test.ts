import { describe, it, expect } from "vitest";
import {
  parseDid,
  tryParseDid,
  extractDidMethod,
  isDid,
  isDidErc725,
  isDidWeb,
  isDidPlc,
  isDidPkh,
  isDidetzhayyim,
  assertDidetzhayyimDepth,
  assertDidPrincipalOretzhayyimDepth,
  DidParseError,
} from "../src/did";

// Sample DIDs aligned with ADR-0074 + ADR-0049 D5 + ADR-0029.
const ERC725 = "did:erc725:etzhayyim:260425:0xabcdef0123456789abcdef0123456789abcdef01";
const WEB_FLAT = "did:web:lawfirm.etzhayyim.com";
const WEB_PATH = "did:web:judge.etzhayyim.com:JPN:tanaka-001";
const PLC = "did:plc:abcdefghijklmnopqrstuvwx";
const PKH = "did:pkh:eip155:1:0xab5801a7d398351b8be11c439e05c5b3259aec9b";
const etzhayyim_ROOT = "did:etzhayyim:lf1rm8k0";
const etzhayyim_DEPTH2 = "did:etzhayyim:lf1rm8k0:abcdef0123456789abcdef01";

describe("extractDidMethod", () => {
  it("extracts known methods", () => {
    expect(extractDidMethod(ERC725)).toBe("erc725");
    expect(extractDidMethod(WEB_FLAT)).toBe("web");
    expect(extractDidMethod(PLC)).toBe("plc");
    expect(extractDidMethod(PKH)).toBe("pkh");
    expect(extractDidMethod(etzhayyim_ROOT)).toBe("etzhayyim");
  });
  it("returns null for unknown", () => {
    expect(extractDidMethod("did:unknown:foo")).toBeNull();
    expect(extractDidMethod("did:")).toBeNull();
    expect(extractDidMethod("not-a-did")).toBeNull();
    expect(extractDidMethod("")).toBeNull();
  });
});

describe("parseDid happy paths", () => {
  it("parses did:erc725", () => {
    const p = parseDid(ERC725);
    expect(p.method).toBe("erc725");
    expect(p.identifier).toMatch(/^etzhayyim:260425:0x[0-9a-f]{40}$/);
  });
  it("parses did:web flat and path", () => {
    expect(parseDid(WEB_FLAT).method).toBe("web");
    expect(parseDid(WEB_PATH).method).toBe("web");
  });
  it("parses did:plc", () => {
    expect(parseDid(PLC).method).toBe("plc");
  });
  it("parses did:pkh CAIP-10", () => {
    expect(parseDid(PKH).method).toBe("pkh");
  });
  it("parses did:etzhayyim root and depth 2", () => {
    expect(parseDid(etzhayyim_ROOT).method).toBe("etzhayyim");
    expect(parseDid(etzhayyim_DEPTH2).method).toBe("etzhayyim");
  });
});

describe("parseDid validation", () => {
  it("rejects missing prefix", () => {
    expect(() => parseDid("foo:bar")).toThrow(DidParseError);
  });
  it("rejects missing method-specific identifier", () => {
    expect(() => parseDid("did:web")).toThrow(DidParseError);
    expect(() => parseDid("did:web:")).toThrow(DidParseError);
  });
  it("rejects unsupported method", () => {
    expect(() => parseDid("did:key:z6Mk...")).toThrow(/unsupported method 'key'/);
  });
  it("rejects malformed did:erc725", () => {
    expect(() => parseDid("did:erc725:etzhayyim:260425")).toThrow(DidParseError);
    expect(() => parseDid("did:erc725:etzhayyim:260425:0xshort")).toThrow(DidParseError);
  });
  it("rejects malformed did:plc", () => {
    expect(() => parseDid("did:plc:tooSHORT")).toThrow(DidParseError);
  });
  it("rejects malformed did:pkh", () => {
    expect(() => parseDid("did:pkh:eip155:1")).toThrow(DidParseError);
  });
});

describe("tryParseDid", () => {
  it("returns null on bad input", () => {
    expect(tryParseDid("not-a-did")).toBeNull();
    expect(tryParseDid("")).toBeNull();
  });
  it("returns parsed on good input", () => {
    expect(tryParseDid(WEB_FLAT)?.method).toBe("web");
  });
});

describe("method predicates", () => {
  it("isDid", () => {
    expect(isDid(ERC725)).toBe(true);
    expect(isDid("garbage")).toBe(false);
  });
  it("isDidErc725 / Web / Plc / Pkh / etzhayyim", () => {
    expect(isDidErc725(ERC725)).toBe(true);
    expect(isDidErc725(WEB_FLAT)).toBe(false);
    expect(isDidWeb(WEB_FLAT)).toBe(true);
    expect(isDidWeb(WEB_PATH)).toBe(true);
    expect(isDidPlc(PLC)).toBe(true);
    expect(isDidPkh(PKH)).toBe(true);
    expect(isDidetzhayyim(etzhayyim_ROOT)).toBe(true);
    expect(isDidetzhayyim(etzhayyim_DEPTH2)).toBe(true);
    expect(isDidetzhayyim(WEB_FLAT)).toBe(false);
  });
});

describe("assertDidetzhayyimDepth", () => {
  it("passes on matching depth", () => {
    expect(() => assertDidetzhayyimDepth(etzhayyim_ROOT, 0)).not.toThrow();
    expect(() => assertDidetzhayyimDepth(etzhayyim_DEPTH2, 1)).not.toThrow();
  });
  it("throws on depth mismatch", () => {
    expect(() => assertDidetzhayyimDepth(etzhayyim_ROOT, 1)).toThrow(/expected depth 1/);
  });
  it("throws on non-etzhayyim input", () => {
    expect(() => assertDidetzhayyimDepth(WEB_FLAT, 0)).toThrow(/expected did:etzhayyim/);
  });
});

describe("assertDidPrincipalOretzhayyimDepth (handler-side gate)", () => {
  it("accepts erc725 / web / plc / pkh without depth check", () => {
    expect(() => assertDidPrincipalOretzhayyimDepth(ERC725, 0)).not.toThrow();
    expect(() => assertDidPrincipalOretzhayyimDepth(WEB_FLAT, 0)).not.toThrow();
    expect(() => assertDidPrincipalOretzhayyimDepth(PLC, 99)).not.toThrow();
    expect(() => assertDidPrincipalOretzhayyimDepth(PKH, 99)).not.toThrow();
  });
  it("enforces depth on did:etzhayyim", () => {
    expect(() => assertDidPrincipalOretzhayyimDepth(etzhayyim_ROOT, 0)).not.toThrow();
    expect(() => assertDidPrincipalOretzhayyimDepth(etzhayyim_DEPTH2, 1)).not.toThrow();
    expect(() => assertDidPrincipalOretzhayyimDepth(etzhayyim_ROOT, 1)).toThrow(/expected depth 1/);
  });
});
