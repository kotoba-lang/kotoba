// tools-auth.ts — Bearer `lxm` pre-check for /mcp facade (ADR-0042).
//
// This is a ROUTING GUARD, not a trust boundary. It extracts the `lxm` claim
// from the JWT payload (unverified base64url decode) and fails fast if the
// caller invoked tool X while presenting a bearer minted for tool Y. The
// cryptographic signature check happens downstream in app.handleXRPC →
// PDS `verifyServiceAuthJWT` (ADR-0022 SSoT).
//
// Rationale: repeating signature verification at the facade would (a) require
// shipping P-256 public key resolution into host-sdk, (b) duplicate the ADR-0022
// auth SSoT (ADR-0005 violation). The existing XRPC path already enforces full
// verification; the facade only guards against obvious misrouting before the
// bearer reaches that path.
//
// If no bearer is present, this returns null — public tools (queries without
// auth) continue to work, matching /xrpc/:nsid behavior.

export interface LxmMismatchError {
	error: "LxmScopeMismatch";
	message: string;
}

/**
 * Pre-check that a bearer's `lxm` claim matches the requested tool NSID.
 * Returns a JSON error body on mismatch, or null if check passes (or is N/A).
 *
 * Callers: receive the error body, return it with HTTP 403. The bearer's
 * signature is verified downstream; this is purely defensive routing.
 */
export function checkBearerLxm(
	authHeader: string | undefined,
	expectedNsid: string,
): LxmMismatchError | null {
	const bearer = extractBearer(authHeader);
	if (!bearer) return null;
	const payload = parseJwtPayloadUnsafe(bearer);
	if (!payload) return null;
	const lxm = payload.lxm;
	if (typeof lxm !== "string") return null;
	if (lxm === expectedNsid) return null;
	return {
		error: "LxmScopeMismatch",
		message: `bearer lxm=${lxm} does not match requested tool ${expectedNsid}`,
	};
}

function extractBearer(h: string | undefined): string | null {
	if (!h) return null;
	const m = h.match(/^\s*Bearer\s+(.+?)\s*$/i);
	return m ? m[1] : null;
}

/**
 * Decode a JWT payload without signature verification.
 * SAFE USE ONLY: routing/logging pre-checks where a real verifier runs later.
 * Returns null on any parse failure.
 */
function parseJwtPayloadUnsafe(jwt: string): Record<string, unknown> | null {
	const parts = jwt.split(".");
	if (parts.length !== 3) return null;
	try {
		let s = parts[1].replace(/-/g, "+").replace(/_/g, "/");
		while (s.length % 4) s += "=";
		const json = atob(s);
		const obj = JSON.parse(json);
		return typeof obj === "object" && obj !== null ? (obj as Record<string, unknown>) : null;
	} catch {
		return null;
	}
}
