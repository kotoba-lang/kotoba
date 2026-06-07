// lexicon-validator.ts — Runtime validation of decoded command/query body against
// the lexicon input schema. F-Plan step 6 (2026-04-13).
//
// The generated `LEXICON_INPUT_SCHEMA` in src/generated/lexicon-nsid-types.ts holds a
// compact per-NSID schema (property name → primitive type + required list) derived from
// 00-contracts/lexicons/com/etzhayyim/**. This module turns that data into a typed runtime
// validator so app handlers can replace manual `decodeJson(body, { foo: "", bar: 0 })`
// shape declarations with a single typed call:
//
//   const input = parseLexiconInput<"com.etzhayyim.apps.foo.bar">(nsid("com.etzhayyim.apps.foo.bar"), body);
//
// The returned object is statically typed as LexiconInput<N> and runtime-checked to
// have all required properties with the correct primitive types. Unknown NSIDs throw
// a descriptive error pointing to the codegen pipeline.

import {
	LEXICON_INPUT_SCHEMA,
	type LexiconInput,
	type LexiconNsid,
	type LexiconRuntimeSchema,
	type LexiconPrimitiveType,
} from "./generated/lexicon-nsid-types.js";
import { decodeJson } from "./helpers.js";

export class LexiconValidationError extends Error {
	readonly nsid: string;
	readonly issues: ReadonlyArray<string>;
	constructor(nsid: string, issues: string[]) {
		super(`lexicon validation failed for ${nsid}: ${issues.join("; ")}`);
		this.name = "LexiconValidationError";
		this.nsid = nsid;
		this.issues = issues;
	}
}

function typeOfValue(v: unknown): LexiconPrimitiveType {
	if (v === null || v === undefined) return "unknown";
	if (typeof v === "string") return "string";
	if (typeof v === "boolean") return "boolean";
	if (typeof v === "number") return Number.isInteger(v) ? "integer" : "number";
	if (Array.isArray(v)) return "array";
	if (typeof v === "object") return "object";
	return "unknown";
}

function matchesExpected(actual: LexiconPrimitiveType, expected: LexiconPrimitiveType): boolean {
	if (expected === "unknown") return true;
	// integer is a valid number; number accepts integer too
	if (expected === "number" && actual === "integer") return true;
	if (expected === "integer" && actual === "integer") return true;
	return actual === expected;
}

/**
 * Validate a decoded object against a compact lexicon input schema.
 * Returns a list of issue strings (empty array = valid).
 */
export function validateAgainstSchema(
	value: unknown,
	schema: LexiconRuntimeSchema,
): string[] {
	const issues: string[] = [];
	if (value === null || value === undefined || typeof value !== "object" || Array.isArray(value)) {
		issues.push(`input is not an object (got ${typeOfValue(value)})`);
		return issues;
	}
	const obj = value as Record<string, unknown>;

	for (const key of schema.required) {
		if (!(key in obj) || obj[key] === undefined || obj[key] === null) {
			issues.push(`missing required property '${key}'`);
		}
	}

	for (const [key, expected] of Object.entries(schema.properties)) {
		if (!(key in obj)) continue;
		const actual = typeOfValue(obj[key]);
		if (actual === "unknown" && obj[key] === undefined) continue;
		if (!matchesExpected(actual, expected)) {
			issues.push(`property '${key}': expected ${expected}, got ${actual}`);
		}
	}

	return issues;
}

/**
 * Parse and validate a command/query body against the lexicon input schema.
 *
 * - Decodes JSON from Uint8Array.
 * - Looks up the schema from LEXICON_INPUT_SCHEMA by NSID.
 * - Validates required properties and primitive types.
 * - Throws LexiconValidationError on failure.
 * - Returns a typed LexiconInput<N> (the narrow TS type generated from the lexicon).
 *
 * NSIDs without an input schema (void input) return an empty object.
 * NSIDs that don't appear in LEXICON_INPUT_SCHEMA throw a "regenerate codegen" error.
 */
export function parseLexiconInput<N extends LexiconNsid>(
	nsid: N,
	body: Uint8Array,
): LexiconInput<N> {
	const schema = LEXICON_INPUT_SCHEMA[nsid];
	if (!schema) {
		// No schema = void input (lexicon declares no parameters/input). Return empty object.
		// If the NSID is genuinely unknown, the LexiconNsid type check at call site would
		// have already caught it — we're defensive here only for runtime-constructed NSIDs.
		if (!(nsid in LEXICON_INPUT_SCHEMA)) {
			return decodeJson(body, {} as LexiconInput<N>);
		}
		return {} as LexiconInput<N>;
	}

	const decoded = decodeJson<unknown>(body, {});
	const issues = validateAgainstSchema(decoded, schema);
	if (issues.length > 0) {
		throw new LexiconValidationError(nsid, issues);
	}
	return decoded as LexiconInput<N>;
}

/**
 * Same as parseLexiconInput but returns the issues array instead of throwing.
 * Useful for apps that want to emit structured error responses.
 */
export function tryParseLexiconInput<N extends LexiconNsid>(
	nsid: N,
	body: Uint8Array,
):
	| { ok: true; input: LexiconInput<N> }
	| { ok: false; issues: ReadonlyArray<string> } {
	const schema = LEXICON_INPUT_SCHEMA[nsid];
	if (!schema) {
		return { ok: true, input: decodeJson(body, {} as LexiconInput<N>) };
	}
	const decoded = decodeJson<unknown>(body, {});
	const issues = validateAgainstSchema(decoded, schema);
	if (issues.length > 0) {
		return { ok: false, issues };
	}
	return { ok: true, input: decoded as LexiconInput<N> };
}
