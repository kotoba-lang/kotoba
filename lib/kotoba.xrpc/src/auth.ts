// auth.ts — XRPC service-auth header resolution for Worker-to-Worker calls.
// SessionAuth / PublicAuth / mintInternalAuthJWT were pruned 2026-04-23 —
// they had zero external consumers. Browser auth is @atproto/api (wproto facade).
// Canonical ES256 minter: `60-apps/etzhayyim-project-auth/worker/src-ts/service-auth.ts`.

/** Auth header resolver interface. All transports use this. */
export interface AuthResolver {
  resolve(nsid?: string): Promise<Record<string, string>>;
}

/** Service auth signer: signs JWT with NSID as LXM. */
export type ServiceAuthSigner = (lxm: string) => Promise<string>;

/** Worker host auth: service binding verified header + JWT signer + internal token. */
export class ServiceAuth implements AuthResolver {
  constructor(
    private opts: {
      signer?: ServiceAuthSigner;
      internalToken?: string;
      isServiceBinding?: boolean;
      orgId?: string;
    } = {},
  ) {}

  async resolve(nsid?: string): Promise<Record<string, string>> {
    const h: Record<string, string> = {
      "content-type": "application/json",
      "x-etzhayyim-org-id": this.opts.orgId ?? "service",
    };

    // ADR-0023 P4: prefer ES256 Service Auth JWT. When a signer is wired,
    // the JWT alone provides cryptographic proof of caller identity — the
    // spoofable `x-kotodama-verified` header is NOT emitted in that mode.
    if (this.opts.signer && nsid) {
      const jwt = await this.opts.signer(nsid);
      if (jwt) {
        h["authorization"] = `Bearer ${jwt}`;
        return h;
      }
      // signer returned empty — fall through to legacy paths below so the
      // request at least has some trust context (caller will be audited via
      // `[auth][deprecated]` log at PDS).
    }

    if (this.opts.internalToken) {
      // Legacy dispatch/HTTP mode: internal token is no longer a valid AT session JWT.
      // Send trusted internal headers instead of Authorization so PDS authenticates this
      // as an internal service call and avoids session/token-scope enforcement.
      h["x-kotodama-verified"] = "true";
      h["x-kotodama-internal-token"] = this.opts.internalToken;
    } else if (this.opts.isServiceBinding !== false) {
      h["x-kotodama-verified"] = "true";
    }
    return h;
  }

  /** Update service binding state. */
  setServiceBinding(isBinding: boolean): void {
    this.opts.isServiceBinding = isBinding;
  }

  /** Update internal token. */
  setInternalToken(token: string): void {
    this.opts.internalToken = token;
  }

  /** Set service auth JWT signer. */
  setSigner(signer: ServiceAuthSigner): void {
    this.opts.signer = signer;
  }
}
