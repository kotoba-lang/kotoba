// lexicon-validator.test.ts — F-Plan step 6: runtime validator regression guard.

import { describe, it, expect } from "vitest";
import {
	parseLexiconInput,
	tryParseLexiconInput,
	LexiconValidationError,
	validateAgainstSchema,
} from "../src/lexicon-validator.js";
import { LEXICON_INPUT_SCHEMA } from "../src/generated/lexicon-nsid-types.js";
import { encodeJson } from "../src/helpers.js";

describe("F-Plan step 6: parseLexiconInput runtime validator (2026-04-13)", () => {
	describe("LEXICON_INPUT_SCHEMA registry", () => {
		it("contains host capability schemas (secrets, invoke, llm)", () => {
			expect(LEXICON_INPUT_SCHEMA["com.etzhayyim.host.secrets.get"]).toBeDefined();
			expect(LEXICON_INPUT_SCHEMA["com.etzhayyim.host.invoke.call"]).toBeDefined();
			expect(LEXICON_INPUT_SCHEMA["com.etzhayyim.host.llm.converse"]).toBeDefined();
		});

		it("captures required keys from lexicon", () => {
			const schema = LEXICON_INPUT_SCHEMA["com.etzhayyim.host.secrets.get"];
			expect(schema.required).toContain("key");
			expect(schema.properties.key).toBe("string");
		});
	});

	describe("validateAgainstSchema (unit)", () => {
		const schema = {
			properties: { name: "string", count: "integer", active: "boolean" } as Record<string, any>,
			required: ["name"] as ReadonlyArray<string>,
		};

		it("returns [] for valid object", () => {
			expect(validateAgainstSchema({ name: "foo", count: 42, active: true }, schema)).toEqual([]);
		});

		it("reports missing required field", () => {
			const issues = validateAgainstSchema({ count: 1 }, schema);
			expect(issues).toContain("missing required property 'name'");
		});

		it("reports type mismatch", () => {
			const issues = validateAgainstSchema({ name: "foo", count: "not-a-number" }, schema);
			expect(issues).toContain("property 'count': expected integer, got string");
		});

		it("accepts integer where number is expected", () => {
			const numSchema = { properties: { x: "number" } as Record<string, any>, required: [] as string[] };
			expect(validateAgainstSchema({ x: 5 }, numSchema)).toEqual([]);
			expect(validateAgainstSchema({ x: 5.5 }, numSchema)).toEqual([]);
		});

		it("rejects non-object input", () => {
			expect(validateAgainstSchema(null, schema).length).toBeGreaterThan(0);
			expect(validateAgainstSchema([1, 2], schema).length).toBeGreaterThan(0);
			expect(validateAgainstSchema("string", schema).length).toBeGreaterThan(0);
		});
	});

	describe("parseLexiconInput end-to-end", () => {
		it("parses and validates a valid secrets.get body", () => {
			const body = encodeJson({ key: "API_KEY" });
			const input = parseLexiconInput("com.etzhayyim.host.secrets.get", body);
			expect(input).toEqual({ key: "API_KEY" });
		});

		it("throws LexiconValidationError on missing required field", () => {
			const body = encodeJson({});
			expect(() => parseLexiconInput("com.etzhayyim.host.secrets.get", body)).toThrow(
				LexiconValidationError,
			);
		});

		it("LexiconValidationError carries nsid + issues", () => {
			const body = encodeJson({});
			try {
				parseLexiconInput("com.etzhayyim.host.secrets.get", body);
				expect.fail("expected throw");
			} catch (err) {
				expect(err).toBeInstanceOf(LexiconValidationError);
				const e = err as LexiconValidationError;
				expect(e.nsid).toBe("com.etzhayyim.host.secrets.get");
				expect(e.issues.length).toBeGreaterThan(0);
				expect(e.issues[0]).toMatch(/key/);
			}
		});

		it("throws on wrong type", () => {
			const body = encodeJson({ key: 42 }); // key should be string
			expect(() => parseLexiconInput("com.etzhayyim.host.secrets.get", body)).toThrow(
				/expected string, got integer/,
			);
		});
	});

	describe("tryParseLexiconInput non-throwing variant", () => {
		it("returns ok:true with typed input on success", () => {
			const body = encodeJson({ key: "foo" });
			const result = tryParseLexiconInput("com.etzhayyim.host.secrets.get", body);
			expect(result.ok).toBe(true);
			if (result.ok) {
				expect(result.input).toEqual({ key: "foo" });
			}
		});

		it("returns ok:false with issues on failure", () => {
			const body = encodeJson({});
			const result = tryParseLexiconInput("com.etzhayyim.host.secrets.get", body);
			expect(result.ok).toBe(false);
			if (!result.ok) {
				expect(result.issues.length).toBeGreaterThan(0);
			}
		});
	});
});
