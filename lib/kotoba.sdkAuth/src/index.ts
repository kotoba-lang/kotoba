import { Etzhayyim, type EtzhayyimConfig } from "@etzhayyim/sdk";

export interface SessionEnv {
  ACTOR_DID: string;
  PDS_URL: string;
  L2_RPC_URL?: string;
  /** atproto access JWT (short-lived). */
  PDS_ACCESS_JWT?: string;
  /** atproto refresh JWT (long-lived) — stored as CF Workers Secret. */
  PDS_REFRESH_JWT?: string;
  /**
   * kotoba-datomic-projection: feed-discover projector DID (ADR-2605231500).
   * When set, feed read paths read the cross-DID projection emitted by
   * `50-infra/mst-projector/` instead of the single ACTOR_DID MST.
   * See `50-infra/mst-projector/projection/kotoba-datomic-projection.edn`.
   */
  PROJECTION_DISCOVER_DID?: string;
  /**
   * kotoba server base URL (e.g. `https://kotoba.etzhayyim.com`). When set,
   * `yoro-kotoba` feed/graph/actor reads resolve through the kotoba Datom log
   * (canonical state, ADR-2606013200) instead of the PDS/projection path.
   */
  KOTOBA_URL?: string;
  /** Multibase CID of the kotoba graph holding the yoro feed Datoms. */
  YORO_GRAPH_CID?: string;
}

export interface AuthedEtzhayyimOpts {
  env: SessionEnv;
  /** Optional override of the request-bound Authorization header (e.g. user-facing XRPC calls). */
  bearerToken?: string;
}

/**
 * Construct an Etzhayyim SDK instance with PDS session attached.
 *
 * Precedence:
 *   1. bearerToken (from incoming Authorization: Bearer <jwt> header)
 *   2. env.PDS_ACCESS_JWT (CF Workers var — actor-local service identity)
 *   3. anonymous (read-only; writes will fail at PDS)
 */
export function createAuthedEtzhayyim(opts: AuthedEtzhayyimOpts): Etzhayyim {
  const accessJwt = opts.bearerToken ?? opts.env.PDS_ACCESS_JWT;

  const config: EtzhayyimConfig = {
    did: opts.env.ACTOR_DID,
    pdsUrl: opts.env.PDS_URL,
    l2RpcUrl: opts.env.L2_RPC_URL ?? "https://mainnet.base.org",
    projectionDiscoverDid: opts.env.PROJECTION_DISCOVER_DID,
    kotobaUrl: opts.env.KOTOBA_URL,
    yoroGraphCid: opts.env.YORO_GRAPH_CID,
  };

  // Attach session if we have an access JWT.
  if (accessJwt && opts.env.PDS_REFRESH_JWT) {
    config.session = {
      did: opts.env.ACTOR_DID,
      handle: opts.env.ACTOR_DID.replace("did:", ""),
      accessJwt,
      refreshJwt: opts.env.PDS_REFRESH_JWT,
    };
  } else if (accessJwt) {
    // If only access JWT provided, create minimal session.
    config.session = {
      did: opts.env.ACTOR_DID,
      handle: opts.env.ACTOR_DID.replace("did:", ""),
      accessJwt,
      refreshJwt: "", // Will be populated on refresh
    };
  }

  return new Etzhayyim(config);
}

/**
 * Extract bearer token from `Authorization: Bearer <token>` header on a Request.
 * Returns undefined if header missing or malformed.
 */
export function extractBearerToken(req: Request): string | undefined {
  const auth =
    req.headers.get("authorization") ?? req.headers.get("Authorization");
  if (!auth) return undefined;
  const m = /^Bearer\s+(.+)$/i.exec(auth);
  return m ? m[1] : undefined;
}

/**
 * Refresh the PDS session using the refresh JWT.
 * Returns the new access JWT and refresh JWT, or null on failure.
 *
 * The actual atproto refresh endpoint is `com.atproto.server.refreshSession`.
 */
export async function refreshPdsSession(
  pdsUrl: string,
  refreshJwt: string,
): Promise<{ accessJwt: string; refreshJwt: string } | null> {
  try {
    const r = await fetch(`${pdsUrl}/xrpc/com.atproto.server.refreshSession`, {
      method: "POST",
      headers: { Authorization: `Bearer ${refreshJwt}` },
    });
    if (!r.ok) return null;
    const j = (await r.json()) as { accessJwt: string; refreshJwt: string };
    return { accessJwt: j.accessJwt, refreshJwt: j.refreshJwt };
  } catch {
    return null;
  }
}

export type { EtzhayyimConfig } from "@etzhayyim/sdk";
export { Etzhayyim } from "@etzhayyim/sdk";
