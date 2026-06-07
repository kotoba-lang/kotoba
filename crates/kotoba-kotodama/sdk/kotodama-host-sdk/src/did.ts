// did.ts — Method-agnostic DID parsing helpers.
//
// Phase D + I per 90-docs/260427-lexicon-did-pattern-method-agnostic.md.
// Strict regex pattern was stripped from 15 lawfirm/auth lexicons; depth +
// shape invariants must now run handler-side via these helpers.
//
// Accepted methods (ADR-0074 + ADR-0049 D5 + ADR-0029):
//   did:erc725 — platform primary identity
//   did:web    — AT Protocol facade / external entity catalogue
//   did:plc    — legacy AT primary
//   did:pkh    — wallet alias (CAIP-10 chain:network:address)
//   did:etzhayyim   — legacy / migration window
//
// did:etzhayyim-specific helpers (depth, parent, root) re-export from
// @etzhayyim/did-etzhayyim to keep the canonical impl single-sourced (ADR-0029).

import { isValidDidetzhayyim, didDepth as didDepthetzhayyim, didParent as didParentetzhayyim, didRoot as didRootetzhayyim } from "@etzhayyim/did-etzhayyim";

export type DidMethod = "erc725" | "web" | "plc" | "pkh" | "etzhayyim";

export interface ParsedDid {
  did: string;
  method: DidMethod;
  identifier: string;
}

export class DidParseError extends Error {
  constructor(public did: string, msg: string) {
    super(`invalid DID '${did}': ${msg}`);
    this.name = "DidParseError";
  }
}

const KNOWN_METHODS: ReadonlySet<DidMethod> = new Set(["erc725", "web", "plc", "pkh", "etzhayyim"]);

/**
 * Parse a DID into method + identifier. Throws DidParseError on malformed
 * input. Use tryParseDid() for non-throwing variant.
 *
 * Validation depth (per method):
 *   - erc725: did:erc725:{namespace}:{epoch}:0x{hex} — 4 colon-separated parts
 *   - web:    did:web:{host}[:{path}...] — at least 1 part after method
 *   - plc:    did:plc:{base32-cid} — exactly 1 part
 *   - pkh:    did:pkh:{namespace}:{reference}:{address} — CAIP-10 shape
 *   - etzhayyim:   delegates to @etzhayyim/did-etzhayyim isValidDidetzhayyim (depth ≤ 6)
 */
export function parseDid(did: string): ParsedDid {
  if (typeof did !== "string" || did.length === 0) {
    throw new DidParseError(String(did), "empty or non-string");
  }
  if (!did.startsWith("did:")) {
    throw new DidParseError(did, "missing 'did:' prefix");
  }
  const afterPrefix = did.slice(4);
  const colonIdx = afterPrefix.indexOf(":");
  if (colonIdx <= 0) {
    throw new DidParseError(did, "missing method-specific identifier");
  }
  const method = afterPrefix.slice(0, colonIdx) as DidMethod;
  const identifier = afterPrefix.slice(colonIdx + 1);
  if (!KNOWN_METHODS.has(method)) {
    throw new DidParseError(did, `unsupported method '${method}' (accepted: ${[...KNOWN_METHODS].join(", ")})`);
  }
  if (identifier.length === 0) {
    throw new DidParseError(did, "empty identifier");
  }

  switch (method) {
    case "erc725": {
      // did:erc725:etzhayyim:260425:0xAbC...
      const parts = identifier.split(":");
      if (parts.length !== 3) throw new DidParseError(did, "expected 'did:erc725:{ns}:{epoch}:0x{hex}'");
      const [, , addr] = parts;
      if (!/^0x[0-9a-fA-F]{40}$/.test(addr)) throw new DidParseError(did, "invalid contract address (expect 0x + 40 hex)");
      break;
    }
    case "web": {
      // did:web:host (URL-decoded host with optional :path...)
      const head = identifier.split(":")[0];
      if (!/^[A-Za-z0-9.-]+$/.test(head)) throw new DidParseError(did, "invalid web host segment");
      break;
    }
    case "plc": {
      // did:plc:{base32-cid}; spec: 24+ char alphanumeric body
      if (!/^[a-z0-9]{24,}$/.test(identifier)) throw new DidParseError(did, "invalid did:plc body (expect ≥24 lowercase alphanumeric)");
      break;
    }
    case "pkh": {
      // did:pkh:{namespace}:{reference}:{account_address} (CAIP-10)
      const parts = identifier.split(":");
      if (parts.length !== 3) throw new DidParseError(did, "expected CAIP-10 'namespace:reference:address'");
      break;
    }
    case "etzhayyim": {
      if (!isValidDidetzhayyim(did)) throw new DidParseError(did, "fails @etzhayyim/did-etzhayyim isValidDidetzhayyim");
      break;
    }
  }

  return { did, method, identifier };
}

/** Non-throwing variant. Returns null on parse failure. */
export function tryParseDid(did: string): ParsedDid | null {
  try {
    return parseDid(did);
  } catch {
    return null;
  }
}

/** Extract the DID method without full validation. Returns null if no method. */
export function extractDidMethod(did: string): DidMethod | null {
  if (typeof did !== "string" || !did.startsWith("did:")) return null;
  const afterPrefix = did.slice(4);
  const colonIdx = afterPrefix.indexOf(":");
  if (colonIdx <= 0) return null;
  const method = afterPrefix.slice(0, colonIdx);
  return KNOWN_METHODS.has(method as DidMethod) ? (method as DidMethod) : null;
}

export function isDid(did: string): boolean {
  return tryParseDid(did) !== null;
}

export function isDidErc725(did: string): boolean {
  return extractDidMethod(did) === "erc725" && isDid(did);
}
export function isDidWeb(did: string): boolean {
  return extractDidMethod(did) === "web" && isDid(did);
}
export function isDidPlc(did: string): boolean {
  return extractDidMethod(did) === "plc" && isDid(did);
}
export function isDidPkh(did: string): boolean {
  return extractDidMethod(did) === "pkh" && isDid(did);
}
export function isDidetzhayyim(did: string): boolean {
  return isValidDidetzhayyim(did);
}

// did:etzhayyim depth helpers — re-export so handlers don't need to import from
// two packages. Throws if input is not did:etzhayyim.
export const didetzhayyimDepth = didDepthetzhayyim;
export const didetzhayyimParent = didParentetzhayyim;
export const didetzhayyimRoot = didRootetzhayyim;

/**
 * Assert a did:etzhayyim has exactly the expected depth. Used in handlers like
 * lawfirm.createMatter where firmDid must be depth 1, matterDid depth 2.
 *
 * @throws DidParseError if not did:etzhayyim or depth mismatch.
 */
export function assertDidetzhayyimDepth(did: string, expected: number): void {
  if (!isValidDidetzhayyim(did)) throw new DidParseError(did, "expected did:etzhayyim");
  const actual = didDepthetzhayyim(did);
  if (actual !== expected) {
    throw new DidParseError(did, `expected depth ${expected}, got ${actual}`);
  }
}

/**
 * Assert one of: did:erc725, did:web, did:plc, did:pkh, or
 * did:etzhayyim-with-expected-depth. Used in lexicon-validated handlers where
 * depth invariants only apply when caller chose the legacy did:etzhayyim method.
 */
export function assertDidPrincipalOretzhayyimDepth(did: string, etzhayyimDepth: number): ParsedDid {
  const parsed = parseDid(did);
  if (parsed.method === "etzhayyim") {
    assertDidetzhayyimDepth(did, etzhayyimDepth);
  }
  return parsed;
}
