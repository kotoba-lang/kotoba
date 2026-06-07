// tools-auth.test.ts — Unit tests for the MCP facade `lxm` routing guard (ADR-0042).
//
// checkBearerLxm is intentionally NOT a signature verifier. It decodes the JWT
// payload without checking signature and ensures the `lxm` claim matches the
// invoked tool NSID. Signature verification happens downstream in the existing
// XRPC → PDS path (ADR-0022 SSoT).

import { describe, it, expect } from "vitest";
import { checkBearerLxm } from "../src/tools-auth.js";

function base64urlEncode(obj: unknown): string {
	const json = typeof obj === "string" ? obj : JSON.stringify(obj);
	return Buffer.from(json, "utf8")
		.toString("base64")
		.replace(/\+/g, "-")
		.replace(/\//g, "_")
		.replace(/=+$/, "");
}

function makeUnsignedJwt(payload: Record<string, unknown>): string {
	const header = base64urlEncode({ alg: "ES256", typ: "JWT" });
	const body = base64urlEncode(payload);
	// signature segment is cosmetic — checkBearerLxm does not verify it
	return `${header}.${body}.FAKE_SIGNATURE`;
}

const NSID = "com.etzhayyim.apps.lawfirm.createCase";

describe("checkBearerLxm", () => {
	it("returns null when no authorization header is present (public tool path)", () => {
		expect(checkBearerLxm(undefined, NSID)).toBeNull();
		expect(checkBearerLxm("", NSID)).toBeNull();
	});

	it("returns null when authorization header is not a Bearer token", () => {
		expect(checkBearerLxm("Basic abc123", NSID)).toBeNull();
	});

	it("returns null when bearer is not a well-formed JWT", () => {
		expect(checkBearerLxm("Bearer not-a-jwt", NSID)).toBeNull();
		expect(checkBearerLxm("Bearer only.two", NSID)).toBeNull();
	});

	it("returns null when the JWT payload is not base64url-JSON", () => {
		expect(checkBearerLxm("Bearer aaaa.not!base64.sig", NSID)).toBeNull();
	});

	it("returns null when payload has no `lxm` claim (trust downstream verifier)", () => {
		const jwt = makeUnsignedJwt({ iss: "did:etzhayyim:abc", aud: "did:etzhayyim:xyz" });
		expect(checkBearerLxm(`Bearer ${jwt}`, NSID)).toBeNull();
	});

	it("returns null when `lxm` matches the requested tool (passthrough)", () => {
		const jwt = makeUnsignedJwt({ lxm: NSID });
		expect(checkBearerLxm(`Bearer ${jwt}`, NSID)).toBeNull();
	});

	it("returns LxmScopeMismatch when `lxm` does not match the requested tool", () => {
		const jwt = makeUnsignedJwt({ lxm: "com.etzhayyim.apps.lawfirm.closeMatter" });
		const result = checkBearerLxm(`Bearer ${jwt}`, NSID);
		expect(result).not.toBeNull();
		expect(result!.error).toBe("LxmScopeMismatch");
		expect(result!.message).toContain("com.etzhayyim.apps.lawfirm.closeMatter");
		expect(result!.message).toContain(NSID);
	});

	it("ignores `lxm` when it is not a string (trust downstream to reject)", () => {
		const jwt = makeUnsignedJwt({ lxm: 42 });
		expect(checkBearerLxm(`Bearer ${jwt}`, NSID)).toBeNull();
	});

	it("handles Bearer with mixed case and surrounding whitespace", () => {
		const jwt = makeUnsignedJwt({ lxm: "com.etzhayyim.apps.lawfirm.closeMatter" });
		const result = checkBearerLxm(`  bearer   ${jwt}  `, NSID);
		expect(result).not.toBeNull();
		expect(result!.error).toBe("LxmScopeMismatch");
	});
});
