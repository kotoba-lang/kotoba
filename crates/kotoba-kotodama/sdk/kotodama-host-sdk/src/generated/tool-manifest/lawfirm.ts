// tool-manifest/lawfirm.ts — Auto-generated. DO NOT EDIT.
// Regenerate with: node 70-tools/scripts/contract/gen-tool-manifest.mjs
//
// ADR-0042 — lexicon JSON is the SSoT; this file projects it into:
//   - Zod schemas + createRoute configs (for @hono/zod-openapi)
//   - MCP tools/list entries (raw JSON Schema per MCP spec)
//   - TOOL_MANIFEST (runtime dispatcher lookup)

import { z, createRoute } from "@hono/zod-openapi";
import type { ToolManifestEntry, McpTool } from "./_types";

export const APP_NAME = "lawfirm" as const;

// ── Zod schemas ──

export const InputAcceptExternalCounsel = z.object({ grantDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}:[0-9a-f]{24}$")), granteeSignalPubkey: z.string().describe("Signal X25519 identity pubkey for per-document key wrap").optional() }).openapi("LawfirmAcceptExternalCounselInput");

export const OutputAcceptExternalCounsel = z.object({ grantDid: z.string(), status: z.enum(["accepted"] as const), acceptedAt: z.string().datetime({ offset: true }), wrappedDocumentKeyCount: z.number().int().optional() }).openapi("LawfirmAcceptExternalCounselOutput");

export const InputCloseMatter = z.object({ matterDid: z.string(), outcome: z.enum(["wonPlaintiff", "wonDefendant", "settled", "dismissed", "withdrawn", "referredOut", "archivedInactive", "other"] as const), finalNote: z.string().optional(), archiveBlob: z.boolean().default(false).describe("Emit Iceberg archive projection of matter history").optional() }).openapi("LawfirmCloseMatterInput");

export const OutputCloseMatter = z.object({ matterDid: z.string(), closedAt: z.string().datetime({ offset: true }), grantsRevoked: z.number().int(), openBlockers: z.array(z.string()).describe("If present, close was blocked").optional() }).openapi("LawfirmCloseMatterOutput");

export const InputCreateCase = z.object({ domain: z.enum(["ni138", "land", "family", "consumer", "labour", "corporate", "tax", "criminal", "rera", "fema", "pil-rti", "visa"] as const), state: z.string().describe("ISO 3166-2:IN code (e.g. IN-MH, IN-TN, IN-UP)"), city: z.string().describe("Municipality slug (mumbai, chennai, lucknow, ...)").optional(), lang: z.string().describe("ISO 639-1/3 of client interaction (hi/bn/ta/te/mr/gu/kn/ml/pa/or/as/ur/sa/ne/sd/ks/kok/mai/mni/sat/doi/brx/en)"), courtDid: z.string().describe("did:web:lawfirm.etzhayyim.com:court:{level}:{code} when known").optional(), subjectSummary: z.string().describe("Plaintext summary in client lang. Server encrypts via signal:v1: before persist.").optional(), amountInDispute: z.number().optional(), currency: z.string().default("INR").optional(), urgency: z.enum(["routine", "urgent", "ex-parte"] as const).optional() }).openapi("LawfirmCreateCaseInput");

export const OutputCreateCase = z.object({ did: z.string(), uri: z.string(), cohortDid: z.string().describe("service cohort actor handling this matter"), caseNumber: z.string().optional() }).openapi("LawfirmCreateCaseOutput");

export const InputCreateMatter = z.object({ firmDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}$")).describe("Law firm root DID (depth 1). Must match caller session accountDid."), matterType: z.enum(["litigation", "arbitration", "transactional", "advisory", "compliance", "ip", "tax", "labor", "criminal-defense", "family", "administrative", "ipc-criminal", "cpc-civil", "ibc-insolvency", "tmr-ip", "gst-tax", "id-act-labor", "writ-petition"] as const), clientDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}(:[0-9a-f]{24}){0,5}$")), leadBengoshiDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}$")), coCounselDids: z.array(z.string()).optional(), counterpartyDids: z.array(z.string()).optional(), openedAt: z.string().datetime({ offset: true }), jurisdiction: z.string().describe("ISO 3166-1 alpha-3 (JPN, IND, USA, …)").optional(), procedureCode: z.string().describe("Statute/section reference (e.g. 'IPC § 498A', 'CPC O.VII R.1', 'IBC § 7')").optional(), subjectMatter: z.string().optional(), matterNumber: z.string().describe("Optional firm-local matter number (display only)").optional(), estimatedFee: z.number().optional(), currency: z.string().describe("ISO 4217").optional(), feeStructure: z.enum(["hourly", "fixed", "contingency", "retainer", "pro-bono"] as const).optional(), confidentiality: z.enum(["firm", "matter", "ethicalWall"] as const).default("matter").optional() }).openapi("LawfirmCreateMatterInput");

export const OutputCreateMatter = z.object({ matterDid: z.string().describe("did:etzhayyim:{firm}:{matterHash} (depth 2)"), matterRkey: z.string().describe("Last 24 hex of matterDid; used as AT record rkey (DID ↔ AT URI isomorphism)"), uri: z.string(), materialHashProof: z.string().describe("Hex-encoded material bytes used in H(firmDid || 0x1F || material) (ADR-0029 chain verification input)").optional() }).openapi("LawfirmCreateMatterOutput");

export const InputGetCaseStatus = z.object({ caseDid: z.string(), lang: z.string().describe("Translate output to this lang via did:web:lawfirm.etzhayyim.com:lang:{iso}").optional() }).openapi("LawfirmGetCaseStatusInput");

export const OutputGetCaseStatus = z.object({ caseDid: z.string(), status: z.string(), domain: z.string().optional(), courtDid: z.string().optional(), cohortDid: z.string().optional(), nextHearingAt: z.string().datetime({ offset: true }).optional(), events: z.array(z.object({ event: z.string().optional(), occurredAt: z.string().datetime({ offset: true }).optional() })) }).openapi("LawfirmGetCaseStatusOutput");

export const InputInviteExternalCounsel = z.object({ matterDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$")), granteeDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}$")), granteeHandle: z.string().optional(), role: z.enum(["coCounsel", "local", "advisory", "reviewer"] as const), capabilities: z.array(z.enum(["read", "comment", "uploadDocument", "propose", "sign", "scheduleHearing"] as const)), expiresAt: z.string().datetime({ offset: true }), message: z.string().describe("Optional message included in consent.request DM").optional() }).openapi("LawfirmInviteExternalCounselInput");

export const OutputInviteExternalCounsel = z.object({ grantDid: z.string().describe("did:etzhayyim:{firm}:{matter}:{grant}"), grantUri: z.string(), conflictCheckPassed: z.boolean().optional(), materialHashProof: z.string().optional() }).openapi("LawfirmInviteExternalCounselOutput");

export const InputIssueInvoice = z.object({ matterDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$")), period: z.object({ from: z.string().datetime({ offset: true }), to: z.string().datetime({ offset: true }) }), includeTimeEntryRefs: z.array(z.string()).describe("Optional explicit allowlist; omit to include all approved entries in period").optional(), flatFeeAmount: z.number().optional(), flatFeeNote: z.string().optional(), expenses: z.array(z.object({ description: z.string(), amount: z.number() })).optional(), taxRate: z.number().optional(), discountAmount: z.number().optional(), dueInDays: z.number().int().default(30).optional(), invoiceNumber: z.string().describe("Optional firm-local invoice number (display only)").optional() }).openapi("LawfirmIssueInvoiceInput");

export const OutputIssueInvoice = z.object({ invoiceDid: z.string(), uri: z.string(), subtotal: z.number().optional(), taxAmount: z.number().optional(), total: z.number(), currency: z.string(), timeEntriesBilled: z.number().int(), dueAt: z.string().datetime({ offset: true }).optional(), materialHashProof: z.string().optional() }).openapi("LawfirmIssueInvoiceOutput");

export const InputListCases = z.object({ cohortDid: z.string().optional(), state: z.string().describe("ISO 3166-2:IN").optional(), lang: z.string().optional(), domain: z.string().optional(), status: z.string().optional(), limit: z.number().int().max(200).default(50).optional(), cursor: z.string().optional() }).openapi("LawfirmListCasesInput");

export const OutputListCases = z.object({ cases: z.array(z.object({ did: z.string().optional(), domain: z.string().optional(), status: z.string().optional(), filedAt: z.string().datetime({ offset: true }).optional() })), limit: z.number().int(), cursor: z.string().optional() }).openapi("LawfirmListCasesOutput");

export const InputListConflictChecks = z.object({ matterDid: z.string(), scanScope: z.enum(["matterIntake", "externalCounselInvite", "periodicAudit"] as const).optional(), result: z.enum(["clear", "disclosureRequired", "waivable", "blocked"] as const).optional(), limit: z.number().int().min(1).max(200).default(50).optional(), offset: z.number().int().min(0).default(0).optional() }).openapi("LawfirmListConflictChecksInput");

export const OutputListConflictChecks = z.object({ items: z.array(z.object({}).passthrough()), offset: z.number().int(), limit: z.number().int(), total: z.number().int() }).openapi("LawfirmListConflictChecksOutput");

export const InputListGrants = z.object({ matterDid: z.string().describe("Optional matter DID filter (depth-2 did:etzhayyim)").optional(), includeRevoked: z.boolean().default(false).describe("When false, excludes grants where revoked_at OR parent_revoked_at is set").optional(), limit: z.number().int().min(1).max(200).default(50).optional(), offset: z.number().int().min(0).default(0).optional() }).openapi("LawfirmListGrantsInput");

export const OutputListGrants = z.object({ items: z.array(z.object({ grantDid: z.string().optional(), matterDid: z.string().optional(), inviterDid: z.string().optional(), status: z.string().optional(), materialHashProof: z.string().optional(), createdAt: z.string().datetime({ offset: true }).optional(), revokedAt: z.string().datetime({ offset: true }).optional(), parentRevokedAt: z.string().datetime({ offset: true }).describe("Parent matter revoked_at — if set, grant is effectively revoked by cascade").optional(), effectivelyActive: z.boolean().describe("false when self OR parent is revoked").optional() })), offset: z.number().int(), limit: z.number().int(), total: z.number().int() }).openapi("LawfirmListGrantsOutput");

export const InputListInvoices = z.object({ matterDid: z.string().optional(), firmDid: z.string().optional(), status: z.enum(["draft", "sent", "partiallyPaid", "paid", "overdue", "void"] as const).optional(), ageingBucket: z.enum(["current", "dueSoon", "overdue30", "overdue60", "overdue90"] as const).optional(), limit: z.number().int().min(1).max(200).default(50).optional(), offset: z.number().int().min(0).default(0).optional() }).openapi("LawfirmListInvoicesInput");

export const OutputListInvoices = z.object({ items: z.array(z.object({}).passthrough()), offset: z.number().int(), limit: z.number().int(), total: z.number().int() }).openapi("LawfirmListInvoicesOutput");

export const InputListMatters = z.object({ matterType: z.string().optional(), leadLawyerDid: z.string().optional(), clientDid: z.string().optional(), status: z.enum(["open", "active", "stayed", "closed", "withdrawn"] as const).optional(), jurisdiction: z.string().optional(), offset: z.number().int().min(0).default(0).optional(), limit: z.number().int().min(1).max(200).default(50).optional() }).openapi("LawfirmListMattersInput");

export const OutputListMatters = z.object({ matters: z.array(z.object({ did: z.string().optional(), matterType: z.string().optional(), matterNumber: z.string().optional(), leadLawyerDid: z.string().optional(), status: z.string().optional(), openedAt: z.string().datetime({ offset: true }).optional() })), total: z.number().int(), offset: z.number().int(), limit: z.number().int() }).openapi("LawfirmListMattersOutput");

export const InputRecordTimeEntry = z.object({ matterDid: z.string(), lawyerDid: z.string(), occurredOn: z.string(), minutes: z.number().int().min(1), activityCode: z.string().describe("UTBMS activity code").optional(), narrative: z.string().optional(), billable: z.boolean().default(true).optional(), rate: z.number().optional(), currency: z.string().optional() }).openapi("LawfirmRecordTimeEntryInput");

export const OutputRecordTimeEntry = z.object({ uri: z.string() }).openapi("LawfirmRecordTimeEntryOutput");

export const InputRegisterLawfirm = z.object({ name: z.string(), nameLocal: z.string().optional(), jurisdiction: z.string().describe("ISO 3166-1 alpha-3"), legalEntityDid: z.string().describe("underlying legal-entity DID").optional(), headquarters: z.string().optional(), officeCount: z.number().int().min(1).optional(), lawyerCount: z.number().int().min(1).optional(), specializations: z.array(z.string()).optional(), barAdmissions: z.array(z.string()).optional(), websiteUri: z.string().url().optional() }).openapi("LawfirmRegisterLawfirmInput");

export const OutputRegisterLawfirm = z.object({ did: z.string(), uri: z.string() }).openapi("LawfirmRegisterLawfirmOutput");

export const InputRequestConsult = z.object({ lang: z.string(), state: z.string().describe("ISO 3166-2:IN").optional(), city: z.string().optional(), summary: z.string().describe("Free-text complaint in client lang"), domainHint: z.string().optional(), channel: z.enum(["web", "voice", "whatsapp", "in-person"] as const).optional() }).openapi("LawfirmRequestConsultInput");

export const OutputRequestConsult = z.object({ consultDid: z.string(), uri: z.string(), triageCohortDid: z.string().optional(), suggestedDomain: z.string().optional() }).openapi("LawfirmRequestConsultOutput");

export const InputRespondConsult = z.object({ consultDid: z.string(), responseEncrypted: z.string().describe("signal:v1:{ciphertext}"), respondedAt: z.string().datetime({ offset: true }).optional(), responderDid: z.string().describe("did:web:bengoshi.etzhayyim.com:IND:{barId} or cohort agent").optional(), nextAction: z.enum(["createCase", "moreInfo", "referOut", "decline"] as const).optional() }).openapi("LawfirmRespondConsultInput");

export const OutputRespondConsult = z.object({ uri: z.string(), cid: z.string() }).openapi("LawfirmRespondConsultOutput");

export const InputRevokeExternalCounsel = z.object({ grantDid: z.string(), reason: z.enum(["completed", "conflict", "breach", "request", "expired", "other"] as const), noteToGrantee: z.string().optional() }).openapi("LawfirmRevokeExternalCounselInput");

export const OutputRevokeExternalCounsel = z.object({ grantDid: z.string(), revokedAt: z.string().datetime({ offset: true }), descendantsInvalidated: z.number().int().describe("Number of child DIDs (sessions, sub-capabilities) now failing to resolve").optional() }).openapi("LawfirmRevokeExternalCounselOutput");

export const InputRunConflictCheck = z.object({ matterDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$")), scanScope: z.enum(["matterIntake", "externalCounselInvite", "periodicAudit"] as const), counterpartyDids: z.array(z.string()).optional(), candidateDid: z.string().describe("Required when scanScope=externalCounselInvite").optional(), subjectMatter: z.string().optional() }).openapi("LawfirmRunConflictCheckInput");

export const OutputRunConflictCheck = z.object({ rkey: z.string(), uri: z.string(), result: z.enum(["clear", "disclosureRequired", "waivable", "blocked"] as const), conflicts: z.array(z.object({}).passthrough()).describe("Shape matches conflictCheck.conflicts[]").optional(), wallId: z.string().optional(), scannedAt: z.string().datetime({ offset: true }).optional() }).openapi("LawfirmRunConflictCheckOutput");

export const InputScheduleHearing = z.object({ matterDid: z.string(), courtId: z.string().optional(), judgeDid: z.string().optional(), hearingType: z.enum(["firstAppearance", "oral", "evidentiary", "conciliation", "mediation", "sentencing", "appellate", "procedural"] as const), scheduledAt: z.string().datetime({ offset: true }), durationMin: z.number().int().optional(), location: z.string().optional(), attendees: z.array(z.string()).optional(), agenda: z.string().optional() }).openapi("LawfirmScheduleHearingInput");

export const OutputScheduleHearing = z.object({ hearingDid: z.string(), uri: z.string(), saibanJikenRef: z.string(), materialHashProof: z.string().optional() }).openapi("LawfirmScheduleHearingOutput");

export const InputSubmitFiling = z.object({ caseDid: z.string(), filingType: z.enum(["plaint", "complaint", "vakalatnama", "written-statement", "rejoinder", "interim-application", "appeal", "review", "writ-petition", "evidence-affidavit", "exhibit"] as const), courtDid: z.string(), vaultItemId: z.string().describe("com.etzhayyim.vault.* item id holding ciphertext PDF/scan"), filedAt: z.string().datetime({ offset: true }).optional(), feeAmount: z.number().optional(), feeCurrency: z.string().default("INR").optional(), lang: z.string().describe("Filing language (court of record requires en/hi or state language)").optional() }).openapi("LawfirmSubmitFilingInput");

export const OutputSubmitFiling = z.object({ did: z.string(), uri: z.string(), filingNumber: z.string().optional(), ackAt: z.string().datetime({ offset: true }).optional() }).openapi("LawfirmSubmitFilingOutput");

export const InputTrackFiling = z.object({ filingDid: z.string() }).openapi("LawfirmTrackFilingInput");

export const OutputTrackFiling = z.object({ filingDid: z.string(), status: z.enum(["draft", "submitted", "accepted", "defective", "registered", "listed", "disposed"] as const), filingNumber: z.string().optional(), courtDid: z.string().optional(), nextDate: z.string().datetime({ offset: true }).optional(), defectReason: z.string().optional() }).openapi("LawfirmTrackFilingOutput");

export const InputTranslateFromLang = z.object({ text: z.string(), sourceLang: z.string(), targetLang: z.string().default("en").describe("en | hi").optional(), domain: z.string().optional() }).openapi("LawfirmTranslateFromLangInput");

export const OutputTranslateFromLang = z.object({ text: z.string(), targetLang: z.string(), sourceLang: z.string().optional(), modelId: z.string().optional() }).openapi("LawfirmTranslateFromLangOutput");

export const InputTranslateToLang = z.object({ text: z.string(), sourceLang: z.string().describe("Auto-detect when omitted").optional(), targetLang: z.string().describe("ISO of one of 22 Scheduled Languages + en"), domain: z.string().describe("Legal domain hint for terminology accuracy").optional(), register: z.enum(["plain", "court-of-record", "client-friendly"] as const).optional() }).openapi("LawfirmTranslateToLangInput");

export const OutputTranslateToLang = z.object({ text: z.string(), targetLang: z.string(), sourceLang: z.string().optional(), modelId: z.string().describe("resolveModelId() result").optional() }).openapi("LawfirmTranslateToLangOutput");

export const InputUpdateCase = z.object({ caseDid: z.string(), event: z.enum(["filed", "served", "hearing-scheduled", "hearing-held", "evidence-submitted", "judgment", "appeal", "settled", "withdrawn", "closed"] as const), occurredAt: z.string().datetime({ offset: true }).optional(), noteEncrypted: z.string().describe("signal:v1:{ciphertext} (attorney-client privilege)").optional(), nextHearingAt: z.string().datetime({ offset: true }).optional() }).openapi("LawfirmUpdateCaseInput");

export const OutputUpdateCase = z.object({ uri: z.string(), cid: z.string() }).openapi("LawfirmUpdateCaseOutput");

export const InputUpdateMatterStatus = z.object({ matterDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$")), newStatus: z.enum(["intake", "conflictCheck", "engaged", "filed", "hearing", "trial", "judgment", "appeal", "execution", "closed", "archived", "withdrawn"] as const), reason: z.string().optional(), conflictCheckRef: z.string().describe("Required when newStatus=engaged and previous status was conflictCheck").optional() }).openapi("LawfirmUpdateMatterStatusInput");

export const OutputUpdateMatterStatus = z.object({ matterDid: z.string(), previousStatus: z.string(), newStatus: z.string(), updatedAt: z.string().datetime({ offset: true }) }).openapi("LawfirmUpdateMatterStatusOutput");

export const InputUploadDocument = z.object({ matterDid: z.string().regex(new RegExp("^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$")), docType: z.enum(["pleading", "motion", "brief", "evidence", "contract", "memo", "letter", "opinion", "filing", "correspondence", "other"] as const), title: z.string(), cid: z.string().describe("SHA-256 hex of vault-encrypted ciphertext (pre-computed client-side)"), privileged: z.boolean(), authorDid: z.string().optional(), aiGenerated: z.boolean().default(false).describe("When true, record enters status=pendingReview until ISCO-2611 approval (RULE-003)").optional(), supersedesDocumentDid: z.string().optional() }).openapi("LawfirmUploadDocumentInput");

export const OutputUploadDocument = z.object({ documentDid: z.string(), uri: z.string(), status: z.enum(["draft", "pendingReview", "approved"] as const), materialHashProof: z.string().optional() }).openapi("LawfirmUploadDocumentOutput");

// ── OpenAPI routes (createRoute configs) ──

export const RouteAcceptExternalCounsel = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.acceptExternalCounsel",
	operationId: "ai_etzhayyim_apps_lawfirm_acceptExternalCounsel",
	tags: ["lawfirm"],
	summary: "External counsel accepts an externalCounselGrant. Caller must authenticate as granteeDid. Server flips grant status from 'invited' → 'accepted' and vault-wraps the matter document keys for the grantee (ECIES X25519+HKDF+AES-KW).",
	request: { body: { content: { "application/json": { schema: InputAcceptExternalCounsel } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputAcceptExternalCounsel } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteCloseMatter = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.closeMatter",
	operationId: "ai_etzhayyim_apps_lawfirm_closeMatter",
	tags: ["lawfirm"],
	summary: "Close a matter. Server (1) checks no open hearings / unpaid invoices / pending-review documents, (2) revokes all active externalCounselGrant under the matter (ADR-0029 cascade), (3) sets matter.status='closed' + closedAt, (4) optional final report derive.",
	request: { body: { content: { "application/json": { schema: InputCloseMatter } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputCloseMatter } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteCreateCase = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.createCase",
	operationId: "ai_etzhayyim_apps_lawfirm_createCase",
	tags: ["lawfirm"],
	summary: "Open a new client matter at lawfirm.etzhayyim.com. Routes to service cohort actor did:web:lawfirm.etzhayyim.com:geo:{state}[:{city}]:lang:{iso}:domain:{area} (ADR-0019 path topology, ADR-0026 cohort emergence). PII (client identity) → Preferences tier 3 (ADR-0018), AT Repo holds hashed cohort id only.",
	request: { body: { content: { "application/json": { schema: InputCreateCase } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputCreateCase } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteCreateMatter = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.createMatter",
	operationId: "ai_etzhayyim_apps_lawfirm_createMatter",
	tags: ["lawfirm"],
	summary: "Create a new legal matter. ADR-0029: server mints a recursive child DID (did:etzhayyim:{firm}:{matterHash}) via com.etzhayyim.auth.mintChildDid and writes the matter record at at://{firmDid}/com.etzhayyim.apps.lawfirm.matter/{matterHash}. 18 matterType values supported (civil / criminal / admin / IP / tax / labor / family / IN-specific).",
	request: { body: { content: { "application/json": { schema: InputCreateMatter } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputCreateMatter } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteGetCaseStatus = createRoute({
	method: "get",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.getCaseStatus",
	operationId: "ai_etzhayyim_apps_lawfirm_getCaseStatus",
	tags: ["lawfirm"],
	summary: "Fetch latest status + event timeline for a case. Reads from RisingWave streaming MV (graphar.vertex_lawfirmCase + edge_caseEvent).",
	request: { query: InputGetCaseStatus },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputGetCaseStatus } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteInviteExternalCounsel = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.inviteExternalCounsel",
	operationId: "ai_etzhayyim_apps_lawfirm_inviteExternalCounsel",
	tags: ["lawfirm"],
	summary: "Invite an external bengoshi (possibly from a different firm) to collaborate on a specific matter. Server: (1) runs conflict scan against matter counterparties, (2) mints a grant DID via com.etzhayyim.auth.mintChildDid under matterDid, (3) writes externalCounselGrant record in 'invited' status, (4) sends W Protocol DM with consent.request card. Ethical wall enforced at hash-prefix level (ADR-0029).",
	request: { body: { content: { "application/json": { schema: InputInviteExternalCounsel } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputInviteExternalCounsel } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteIssueInvoice = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.issueInvoice",
	operationId: "ai_etzhayyim_apps_lawfirm_issueInvoice",
	tags: ["lawfirm"],
	summary: "Generate an invoice from approved timeEntry records for a matter over a period. Server (1) selects timeEntry where status='approved' AND matter+period match, (2) mints invoiceDid via com.etzhayyim.auth.mintChildDid (materialKind='doc', docCid=invoicePdfCid), (3) writes invoice record status='draft', (4) flips selected timeEntry status='billed' with invoiceRef. PDF rendering is optional and asynchronous.",
	request: { body: { content: { "application/json": { schema: InputIssueInvoice } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputIssueInvoice } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteListCases = createRoute({
	method: "get",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.listCases",
	operationId: "ai_etzhayyim_apps_lawfirm_listCases",
	tags: ["lawfirm"],
	summary: "List cases scoped by cohort / geo / lang / domain. Default 50, max 200.",
	request: { query: InputListCases },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputListCases } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteListConflictChecks = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.listConflictChecks",
	operationId: "ai_etzhayyim_apps_lawfirm_listConflictChecks",
	tags: ["lawfirm"],
	summary: "List conflict-of-interest scan history for a matter. Reads view_lawfirm_conflict_findings. Ordered by scannedAt DESC so the first row is the most recent scan (used by the UI to surface the current header badge).",
	request: { body: { content: { "application/json": { schema: InputListConflictChecks } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputListConflictChecks } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteListGrants = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.listGrants",
	operationId: "ai_etzhayyim_apps_lawfirm_listGrants",
	tags: ["lawfirm"],
	summary: "List external counsel grants (optionally filtered by matterDid). Reads view_lawfirm_external_counsel_access — joins grant identity with parent matter revocation cascade (ADR-0029).",
	request: { body: { content: { "application/json": { schema: InputListGrants } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputListGrants } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteListInvoices = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.listInvoices",
	operationId: "ai_etzhayyim_apps_lawfirm_listInvoices",
	tags: ["lawfirm"],
	summary: "List invoices for a matter (or firm-wide). Reads view_lawfirm_invoice_ageing which surfaces subtotal/tax/total, dueAt, status, and a derived ageing bucket (current / dueSoon / overdue30 / overdue60 / overdue90).",
	request: { body: { content: { "application/json": { schema: InputListInvoices } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputListInvoices } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteListMatters = createRoute({
	method: "get",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.listMatters",
	operationId: "ai_etzhayyim_apps_lawfirm_listMatters",
	tags: ["lawfirm"],
	summary: "List law firm matters with offset/limit pagination, optional filters.",
	request: { query: InputListMatters },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputListMatters } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteRecordTimeEntry = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.recordTimeEntry",
	operationId: "ai_etzhayyim_apps_lawfirm_recordTimeEntry",
	tags: ["lawfirm"],
	summary: "Record a billable time entry against a matter (タイムシート).",
	request: { body: { content: { "application/json": { schema: InputRecordTimeEntry } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputRecordTimeEntry } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteRegisterLawfirm = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.registerLawfirm",
	operationId: "ai_etzhayyim_apps_lawfirm_registerLawfirm",
	tags: ["lawfirm"],
	summary: "Register a law firm. Path-based DID: did:web:lawfirm.etzhayyim.com:{iso3}:{slug}. ISCO-2611 HAR gate enforced.",
	request: { body: { content: { "application/json": { schema: InputRegisterLawfirm } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputRegisterLawfirm } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteRequestConsult = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.requestConsult",
	operationId: "ai_etzhayyim_apps_lawfirm_requestConsult",
	tags: ["lawfirm"],
	summary: "Initial intake. Routes through triage cohort → service cohort (ADR-0026). No PII in AT Repo; PII to Preferences tier 3.",
	request: { body: { content: { "application/json": { schema: InputRequestConsult } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputRequestConsult } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteRespondConsult = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.respondConsult",
	operationId: "ai_etzhayyim_apps_lawfirm_respondConsult",
	tags: ["lawfirm"],
	summary: "Lawyer / agent response to a consult. Field-level encrypted (signal:v1:) — attorney-client privilege.",
	request: { body: { content: { "application/json": { schema: InputRespondConsult } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputRespondConsult } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteRevokeExternalCounsel = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.revokeExternalCounsel",
	operationId: "ai_etzhayyim_apps_lawfirm_revokeExternalCounsel",
	tags: ["lawfirm"],
	summary: "Terminate an external counsel grant. Sets vertex_etzhayyim_identity.revoked_at on the grant DID — ADR-0029 ancestor cascade automatically invalidates all descendants (sessions, per-document capabilities). Vault document keys for the grantee become unwrap-impossible. Revocation is irreversible.",
	request: { body: { content: { "application/json": { schema: InputRevokeExternalCounsel } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputRevokeExternalCounsel } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteRunConflictCheck = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.runConflictCheck",
	operationId: "ai_etzhayyim_apps_lawfirm_runConflictCheck",
	tags: ["lawfirm"],
	summary: "Run a conflict-of-interest scan and write a conflictCheck record. Two modes:\n  - matterIntake: evaluate a prospective matter's counterparties against the firm's active matter portfolio + prior representation history.\n  - externalCounselInvite: verify a candidate grantee DID does not belong to a counterparty org (reverse scan).\nThe returned result may be {clear, disclosureRequired, waivable, blocked}. When blocked the caller MUST NOT advance matter.status past 'conflictCheck' or proceed with inviteExternalCounsel.",
	request: { body: { content: { "application/json": { schema: InputRunConflictCheck } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputRunConflictCheck } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteScheduleHearing = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.scheduleHearing",
	operationId: "ai_etzhayyim_apps_lawfirm_scheduleHearing",
	tags: ["lawfirm"],
	summary: "Schedule a court hearing for a matter. Server (1) invokes saiban.scheduleTrialEvent via service sync (Write-Only Derived Architecture per ADR-0004), (2) mints hearingDid = did:etzhayyim:{firm}:{matter}:{hearing} via com.etzhayyim.auth.mintChildDid, (3) writes hearing record mirror, (4) registers Path F scheduler cron for reminder + docket-pull. Changes to the saiban-side record are replayed to the mirror via subscribeRepos on saiban collections.",
	request: { body: { content: { "application/json": { schema: InputScheduleHearing } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputScheduleHearing } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteSubmitFiling = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.submitFiling",
	operationId: "ai_etzhayyim_apps_lawfirm_submitFiling",
	tags: ["lawfirm"],
	summary: "Submit a court filing (plaint, application, vakalatnama, written statement, etc.). Document blob → Vault (zero-knowledge, ADR vault.etzhayyim.com). AT Repo holds metadata + Vault item id only.",
	request: { body: { content: { "application/json": { schema: InputSubmitFiling } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputSubmitFiling } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteTrackFiling = createRoute({
	method: "get",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.trackFiling",
	operationId: "ai_etzhayyim_apps_lawfirm_trackFiling",
	tags: ["lawfirm"],
	summary: "Track court filing status (registry acceptance, defect notice, listing, hearing date).",
	request: { query: InputTrackFiling },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputTrackFiling } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteTranslateFromLang = createRoute({
	method: "get",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.translateFromLang",
	operationId: "ai_etzhayyim_apps_lawfirm_translateFromLang",
	tags: ["lawfirm"],
	summary: "Translate a regional-language text into en (court of record) or hi. Inverse of translateToLang.",
	request: { query: InputTranslateFromLang },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputTranslateFromLang } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteTranslateToLang = createRoute({
	method: "get",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.translateToLang",
	operationId: "ai_etzhayyim_apps_lawfirm_translateToLang",
	tags: ["lawfirm"],
	summary: "Translate a case-bound text fragment into a target Indian Scheduled Language. Pipethrough to did:web:lawfirm.etzhayyim.com:lang:{targetLang} actor (Murakumo MLX backend).",
	request: { query: InputTranslateToLang },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputTranslateToLang } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteUpdateCase = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.updateCase",
	operationId: "ai_etzhayyim_apps_lawfirm_updateCase",
	tags: ["lawfirm"],
	summary: "Append a status transition or note to an existing case. Write-only derived (260407): handler writes com.etzhayyim.apps.lawfirm.caseEvent record; downstream notification + projector derive from kotodama.jsonld rule.",
	request: { body: { content: { "application/json": { schema: InputUpdateCase } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputUpdateCase } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteUpdateMatterStatus = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.updateMatterStatus",
	operationId: "ai_etzhayyim_apps_lawfirm_updateMatterStatus",
	tags: ["lawfirm"],
	summary: "Transition a matter's lifecycle status. Enforces allowed transitions:\n  intake          → conflictCheck / engaged / withdrawn\n  conflictCheck   → engaged (requires conflictCheck.result IN {clear, disclosureRequired, waivable}) / withdrawn\n  engaged         → filed / closed (settled) / archived\n  filed           → hearing / judgment / withdrawn\n  hearing         → trial / judgment / conciliated\n  trial           → judgment\n  judgment        → appeal / execution / closed\n  appeal          → judgment / closed\n  execution       → closed\nReverse transitions are rejected. Use closeMatter for the terminal close flow (which performs open-blocker checks + grant cascade revoke).",
	request: { body: { content: { "application/json": { schema: InputUpdateMatterStatus } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputUpdateMatterStatus } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

export const RouteUploadDocument = createRoute({
	method: "post",
	path: "/xrpc/com.etzhayyim.apps.lawfirm.uploadDocument",
	operationId: "ai_etzhayyim_apps_lawfirm_uploadDocument",
	tags: ["lawfirm"],
	summary: "Upload a legal document to a matter. Body contains vault-encrypted ciphertext (per ADR root §Vault Zero-Knowledge Invariant; server never sees plaintext). Server (1) stores ciphertext as R2 blob keyed by SHA-256 cid, (2) mints documentDid = did:etzhayyim:{firm}:{matter}:{doc} via com.etzhayyim.auth.mintChildDid (materialKind='doc', docCid=cid), (3) writes legalDocument record. Privileged by default; AI-generated drafts enter status='pendingReview' awaiting approverBengoshiDid.",
	request: { body: { content: { "application/json": { schema: InputUploadDocument } }, required: true } },
	responses: {
		200: {
			description: "ok",
			content: { "application/json": { schema: OutputUploadDocument } },
		},
		default: {
			description: "error",
			content: { "application/json": { schema: z.object({ error: z.string(), message: z.string().optional() }).openapi("XrpcError") } },
		},
	},
});

// ── Bulk iteration helpers ──

export const ROUTES = [RouteAcceptExternalCounsel, RouteCloseMatter, RouteCreateCase, RouteCreateMatter, RouteGetCaseStatus, RouteInviteExternalCounsel, RouteIssueInvoice, RouteListCases, RouteListConflictChecks, RouteListGrants, RouteListInvoices, RouteListMatters, RouteRecordTimeEntry, RouteRegisterLawfirm, RouteRequestConsult, RouteRespondConsult, RouteRevokeExternalCounsel, RouteRunConflictCheck, RouteScheduleHearing, RouteSubmitFiling, RouteTrackFiling, RouteTranslateFromLang, RouteTranslateToLang, RouteUpdateCase, RouteUpdateMatterStatus, RouteUploadDocument] as const;

export const ROUTE_BY_NSID = {
	"com.etzhayyim.apps.lawfirm.acceptExternalCounsel": RouteAcceptExternalCounsel,
	"com.etzhayyim.apps.lawfirm.closeMatter": RouteCloseMatter,
	"com.etzhayyim.apps.lawfirm.createCase": RouteCreateCase,
	"com.etzhayyim.apps.lawfirm.createMatter": RouteCreateMatter,
	"com.etzhayyim.apps.lawfirm.getCaseStatus": RouteGetCaseStatus,
	"com.etzhayyim.apps.lawfirm.inviteExternalCounsel": RouteInviteExternalCounsel,
	"com.etzhayyim.apps.lawfirm.issueInvoice": RouteIssueInvoice,
	"com.etzhayyim.apps.lawfirm.listCases": RouteListCases,
	"com.etzhayyim.apps.lawfirm.listConflictChecks": RouteListConflictChecks,
	"com.etzhayyim.apps.lawfirm.listGrants": RouteListGrants,
	"com.etzhayyim.apps.lawfirm.listInvoices": RouteListInvoices,
	"com.etzhayyim.apps.lawfirm.listMatters": RouteListMatters,
	"com.etzhayyim.apps.lawfirm.recordTimeEntry": RouteRecordTimeEntry,
	"com.etzhayyim.apps.lawfirm.registerLawfirm": RouteRegisterLawfirm,
	"com.etzhayyim.apps.lawfirm.requestConsult": RouteRequestConsult,
	"com.etzhayyim.apps.lawfirm.respondConsult": RouteRespondConsult,
	"com.etzhayyim.apps.lawfirm.revokeExternalCounsel": RouteRevokeExternalCounsel,
	"com.etzhayyim.apps.lawfirm.runConflictCheck": RouteRunConflictCheck,
	"com.etzhayyim.apps.lawfirm.scheduleHearing": RouteScheduleHearing,
	"com.etzhayyim.apps.lawfirm.submitFiling": RouteSubmitFiling,
	"com.etzhayyim.apps.lawfirm.trackFiling": RouteTrackFiling,
	"com.etzhayyim.apps.lawfirm.translateFromLang": RouteTranslateFromLang,
	"com.etzhayyim.apps.lawfirm.translateToLang": RouteTranslateToLang,
	"com.etzhayyim.apps.lawfirm.updateCase": RouteUpdateCase,
	"com.etzhayyim.apps.lawfirm.updateMatterStatus": RouteUpdateMatterStatus,
	"com.etzhayyim.apps.lawfirm.uploadDocument": RouteUploadDocument,
} as const;

// ── MCP tools/list (raw JSON Schema, per MCP spec) ──

export const MCP_TOOLS: readonly McpTool[] = Object.freeze(
[
	{
		name: "com.etzhayyim.apps.lawfirm.acceptExternalCounsel",
		description: "External counsel accepts an externalCounselGrant. Caller must authenticate as granteeDid. Server flips grant status from 'invited' → 'accepted' and vault-wraps the matter document keys for the grantee (ECIES X25519+HKDF+AES-KW).",
		inputSchema: {
			type: "object",
			required: [
				"grantDid",
			],
			properties: {
				grantDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				granteeSignalPubkey: {
					type: "string",
					description: "Signal X25519 identity pubkey for per-document key wrap",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.closeMatter",
		description: "Close a matter. Server (1) checks no open hearings / unpaid invoices / pending-review documents, (2) revokes all active externalCounselGrant under the matter (ADR-0029 cascade), (3) sets matter.status='closed' + closedAt, (4) optional final report derive.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"outcome",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				outcome: {
					type: "string",
					enum: [
						"wonPlaintiff",
						"wonDefendant",
						"settled",
						"dismissed",
						"withdrawn",
						"referredOut",
						"archivedInactive",
						"other",
					],
				},
				finalNote: {
					type: "string",
				},
				archiveBlob: {
					type: "boolean",
					default: false,
					description: "Emit Iceberg archive projection of matter history",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.createCase",
		description: "Open a new client matter at lawfirm.etzhayyim.com. Routes to service cohort actor did:web:lawfirm.etzhayyim.com:geo:{state}[:{city}]:lang:{iso}:domain:{area} (ADR-0019 path topology, ADR-0026 cohort emergence). PII (client identity) → Preferences tier 3 (ADR-0018), AT Repo holds hashed cohort id only.",
		inputSchema: {
			type: "object",
			required: [
				"domain",
				"state",
				"lang",
			],
			properties: {
				domain: {
					type: "string",
					enum: [
						"ni138",
						"land",
						"family",
						"consumer",
						"labour",
						"corporate",
						"tax",
						"criminal",
						"rera",
						"fema",
						"pil-rti",
						"visa",
					],
				},
				state: {
					type: "string",
					description: "ISO 3166-2:IN code (e.g. IN-MH, IN-TN, IN-UP)",
				},
				city: {
					type: "string",
					description: "Municipality slug (mumbai, chennai, lucknow, ...)",
				},
				lang: {
					type: "string",
					description: "ISO 639-1/3 of client interaction (hi/bn/ta/te/mr/gu/kn/ml/pa/or/as/ur/sa/ne/sd/ks/kok/mai/mni/sat/doi/brx/en)",
				},
				courtDid: {
					type: "string",
					format: "did",
					description: "did:web:lawfirm.etzhayyim.com:court:{level}:{code} when known",
				},
				subjectSummary: {
					type: "string",
					description: "Plaintext summary in client lang. Server encrypts via signal:v1: before persist.",
				},
				amountInDispute: {
					type: "number",
				},
				currency: {
					type: "string",
					default: "INR",
				},
				urgency: {
					type: "string",
					enum: [
						"routine",
						"urgent",
						"ex-parte",
					],
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.createMatter",
		description: "Create a new legal matter. ADR-0029: server mints a recursive child DID (did:etzhayyim:{firm}:{matterHash}) via com.etzhayyim.auth.mintChildDid and writes the matter record at at://{firmDid}/com.etzhayyim.apps.lawfirm.matter/{matterHash}. 18 matterType values supported (civil / criminal / admin / IP / tax / labor / family / IN-specific).",
		inputSchema: {
			type: "object",
			required: [
				"firmDid",
				"matterType",
				"clientDid",
				"leadBengoshiDid",
				"openedAt",
			],
			properties: {
				firmDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}$",
					description: "Law firm root DID (depth 1). Must match caller session accountDid.",
				},
				matterType: {
					type: "string",
					enum: [
						"litigation",
						"arbitration",
						"transactional",
						"advisory",
						"compliance",
						"ip",
						"tax",
						"labor",
						"criminal-defense",
						"family",
						"administrative",
						"ipc-criminal",
						"cpc-civil",
						"ibc-insolvency",
						"tmr-ip",
						"gst-tax",
						"id-act-labor",
						"writ-petition",
					],
				},
				clientDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}(:[0-9a-f]{24}){0,5}$",
				},
				leadBengoshiDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}$",
				},
				coCounselDids: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				counterpartyDids: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				openedAt: {
					type: "string",
					format: "datetime",
				},
				jurisdiction: {
					type: "string",
					description: "ISO 3166-1 alpha-3 (JPN, IND, USA, …)",
				},
				procedureCode: {
					type: "string",
					description: "Statute/section reference (e.g. 'IPC § 498A', 'CPC O.VII R.1', 'IBC § 7')",
				},
				subjectMatter: {
					type: "string",
				},
				matterNumber: {
					type: "string",
					description: "Optional firm-local matter number (display only)",
				},
				estimatedFee: {
					type: "number",
				},
				currency: {
					type: "string",
					description: "ISO 4217",
				},
				feeStructure: {
					type: "string",
					enum: [
						"hourly",
						"fixed",
						"contingency",
						"retainer",
						"pro-bono",
					],
				},
				confidentiality: {
					type: "string",
					enum: [
						"firm",
						"matter",
						"ethicalWall",
					],
					default: "matter",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.getCaseStatus",
		description: "Fetch latest status + event timeline for a case. Reads from RisingWave streaming MV (graphar.vertex_lawfirmCase + edge_caseEvent).",
		inputSchema: {
			type: "object",
			properties: {
				caseDid: {
					type: "string",
					format: "did",
				},
				lang: {
					type: "string",
					description: "Translate output to this lang via did:web:lawfirm.etzhayyim.com:lang:{iso}",
				},
			},
			required: [
				"caseDid",
			],
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.inviteExternalCounsel",
		description: "Invite an external bengoshi (possibly from a different firm) to collaborate on a specific matter. Server: (1) runs conflict scan against matter counterparties, (2) mints a grant DID via com.etzhayyim.auth.mintChildDid under matterDid, (3) writes externalCounselGrant record in 'invited' status, (4) sends W Protocol DM with consent.request card. Ethical wall enforced at hash-prefix level (ADR-0029).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"granteeDid",
				"role",
				"capabilities",
				"expiresAt",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				granteeDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}$",
				},
				granteeHandle: {
					type: "string",
				},
				role: {
					type: "string",
					enum: [
						"coCounsel",
						"local",
						"advisory",
						"reviewer",
					],
				},
				capabilities: {
					type: "array",
					items: {
						type: "string",
						enum: [
							"read",
							"comment",
							"uploadDocument",
							"propose",
							"sign",
							"scheduleHearing",
						],
					},
				},
				expiresAt: {
					type: "string",
					format: "datetime",
				},
				message: {
					type: "string",
					description: "Optional message included in consent.request DM",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.issueInvoice",
		description: "Generate an invoice from approved timeEntry records for a matter over a period. Server (1) selects timeEntry where status='approved' AND matter+period match, (2) mints invoiceDid via com.etzhayyim.auth.mintChildDid (materialKind='doc', docCid=invoicePdfCid), (3) writes invoice record status='draft', (4) flips selected timeEntry status='billed' with invoiceRef. PDF rendering is optional and asynchronous.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"period",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				period: {
					type: "object",
					required: [
						"from",
						"to",
					],
					properties: {
						from: {
							type: "string",
							format: "datetime",
						},
						to: {
							type: "string",
							format: "datetime",
						},
					},
				},
				includeTimeEntryRefs: {
					type: "array",
					items: {
						type: "string",
						format: "at-uri",
					},
					description: "Optional explicit allowlist; omit to include all approved entries in period",
				},
				flatFeeAmount: {
					type: "number",
				},
				flatFeeNote: {
					type: "string",
				},
				expenses: {
					type: "array",
					items: {
						type: "object",
						required: [
							"description",
							"amount",
						],
						properties: {
							description: {
								type: "string",
							},
							amount: {
								type: "number",
							},
						},
					},
				},
				taxRate: {
					type: "number",
				},
				discountAmount: {
					type: "number",
				},
				dueInDays: {
					type: "integer",
					default: 30,
				},
				invoiceNumber: {
					type: "string",
					description: "Optional firm-local invoice number (display only)",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.listCases",
		description: "List cases scoped by cohort / geo / lang / domain. Default 50, max 200.",
		inputSchema: {
			type: "object",
			properties: {
				cohortDid: {
					type: "string",
					format: "did",
				},
				state: {
					type: "string",
					description: "ISO 3166-2:IN",
				},
				lang: {
					type: "string",
				},
				domain: {
					type: "string",
				},
				status: {
					type: "string",
				},
				limit: {
					type: "integer",
					default: 50,
					maximum: 200,
				},
				cursor: {
					type: "string",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.listConflictChecks",
		description: "List conflict-of-interest scan history for a matter. Reads view_lawfirm_conflict_findings. Ordered by scannedAt DESC so the first row is the most recent scan (used by the UI to surface the current header badge).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				scanScope: {
					type: "string",
					enum: [
						"matterIntake",
						"externalCounselInvite",
						"periodicAudit",
					],
				},
				result: {
					type: "string",
					enum: [
						"clear",
						"disclosureRequired",
						"waivable",
						"blocked",
					],
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.listGrants",
		description: "List external counsel grants (optionally filtered by matterDid). Reads view_lawfirm_external_counsel_access — joins grant identity with parent matter revocation cascade (ADR-0029).",
		inputSchema: {
			type: "object",
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					description: "Optional matter DID filter (depth-2 did:etzhayyim)",
				},
				includeRevoked: {
					type: "boolean",
					default: false,
					description: "When false, excludes grants where revoked_at OR parent_revoked_at is set",
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.listInvoices",
		description: "List invoices for a matter (or firm-wide). Reads view_lawfirm_invoice_ageing which surfaces subtotal/tax/total, dueAt, status, and a derived ageing bucket (current / dueSoon / overdue30 / overdue60 / overdue90).",
		inputSchema: {
			type: "object",
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				firmDid: {
					type: "string",
					format: "did",
				},
				status: {
					type: "string",
					enum: [
						"draft",
						"sent",
						"partiallyPaid",
						"paid",
						"overdue",
						"void",
					],
				},
				ageingBucket: {
					type: "string",
					enum: [
						"current",
						"dueSoon",
						"overdue30",
						"overdue60",
						"overdue90",
					],
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.listMatters",
		description: "List law firm matters with offset/limit pagination, optional filters.",
		inputSchema: {
			type: "object",
			properties: {
				matterType: {
					type: "string",
				},
				leadLawyerDid: {
					type: "string",
					format: "did",
				},
				clientDid: {
					type: "string",
					format: "did",
				},
				status: {
					type: "string",
					enum: [
						"open",
						"active",
						"stayed",
						"closed",
						"withdrawn",
					],
				},
				jurisdiction: {
					type: "string",
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.recordTimeEntry",
		description: "Record a billable time entry against a matter (タイムシート).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"lawyerDid",
				"occurredOn",
				"minutes",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				lawyerDid: {
					type: "string",
					format: "did",
				},
				occurredOn: {
					type: "string",
					format: "date",
				},
				minutes: {
					type: "integer",
					minimum: 1,
				},
				activityCode: {
					type: "string",
					description: "UTBMS activity code",
				},
				narrative: {
					type: "string",
				},
				billable: {
					type: "boolean",
					default: true,
				},
				rate: {
					type: "number",
				},
				currency: {
					type: "string",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.registerLawfirm",
		description: "Register a law firm. Path-based DID: did:web:lawfirm.etzhayyim.com:{iso3}:{slug}. ISCO-2611 HAR gate enforced.",
		inputSchema: {
			type: "object",
			required: [
				"name",
				"jurisdiction",
			],
			properties: {
				name: {
					type: "string",
				},
				nameLocal: {
					type: "string",
				},
				jurisdiction: {
					type: "string",
					description: "ISO 3166-1 alpha-3",
				},
				legalEntityDid: {
					type: "string",
					format: "did",
					description: "underlying legal-entity DID",
				},
				headquarters: {
					type: "string",
				},
				officeCount: {
					type: "integer",
					minimum: 1,
				},
				lawyerCount: {
					type: "integer",
					minimum: 1,
				},
				specializations: {
					type: "array",
					items: {
						type: "string",
					},
				},
				barAdmissions: {
					type: "array",
					items: {
						type: "string",
					},
				},
				websiteUri: {
					type: "string",
					format: "uri",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.requestConsult",
		description: "Initial intake. Routes through triage cohort → service cohort (ADR-0026). No PII in AT Repo; PII to Preferences tier 3.",
		inputSchema: {
			type: "object",
			required: [
				"lang",
				"summary",
			],
			properties: {
				lang: {
					type: "string",
				},
				state: {
					type: "string",
					description: "ISO 3166-2:IN",
				},
				city: {
					type: "string",
				},
				summary: {
					type: "string",
					description: "Free-text complaint in client lang",
				},
				domainHint: {
					type: "string",
				},
				channel: {
					type: "string",
					enum: [
						"web",
						"voice",
						"whatsapp",
						"in-person",
					],
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.respondConsult",
		description: "Lawyer / agent response to a consult. Field-level encrypted (signal:v1:) — attorney-client privilege.",
		inputSchema: {
			type: "object",
			required: [
				"consultDid",
				"responseEncrypted",
			],
			properties: {
				consultDid: {
					type: "string",
					format: "did",
				},
				responseEncrypted: {
					type: "string",
					description: "signal:v1:{ciphertext}",
				},
				respondedAt: {
					type: "string",
					format: "datetime",
				},
				responderDid: {
					type: "string",
					format: "did",
					description: "did:web:bengoshi.etzhayyim.com:IND:{barId} or cohort agent",
				},
				nextAction: {
					type: "string",
					enum: [
						"createCase",
						"moreInfo",
						"referOut",
						"decline",
					],
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.revokeExternalCounsel",
		description: "Terminate an external counsel grant. Sets vertex_etzhayyim_identity.revoked_at on the grant DID — ADR-0029 ancestor cascade automatically invalidates all descendants (sessions, per-document capabilities). Vault document keys for the grantee become unwrap-impossible. Revocation is irreversible.",
		inputSchema: {
			type: "object",
			required: [
				"grantDid",
				"reason",
			],
			properties: {
				grantDid: {
					type: "string",
					format: "did",
				},
				reason: {
					type: "string",
					enum: [
						"completed",
						"conflict",
						"breach",
						"request",
						"expired",
						"other",
					],
				},
				noteToGrantee: {
					type: "string",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.runConflictCheck",
		description: "Run a conflict-of-interest scan and write a conflictCheck record. Two modes:\n  - matterIntake: evaluate a prospective matter's counterparties against the firm's active matter portfolio + prior representation history.\n  - externalCounselInvite: verify a candidate grantee DID does not belong to a counterparty org (reverse scan).\nThe returned result may be {clear, disclosureRequired, waivable, blocked}. When blocked the caller MUST NOT advance matter.status past 'conflictCheck' or proceed with inviteExternalCounsel.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"scanScope",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				scanScope: {
					type: "string",
					enum: [
						"matterIntake",
						"externalCounselInvite",
						"periodicAudit",
					],
				},
				counterpartyDids: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				candidateDid: {
					type: "string",
					format: "did",
					description: "Required when scanScope=externalCounselInvite",
				},
				subjectMatter: {
					type: "string",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.scheduleHearing",
		description: "Schedule a court hearing for a matter. Server (1) invokes saiban.scheduleTrialEvent via service sync (Write-Only Derived Architecture per ADR-0004), (2) mints hearingDid = did:etzhayyim:{firm}:{matter}:{hearing} via com.etzhayyim.auth.mintChildDid, (3) writes hearing record mirror, (4) registers Path F scheduler cron for reminder + docket-pull. Changes to the saiban-side record are replayed to the mirror via subscribeRepos on saiban collections.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"hearingType",
				"scheduledAt",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				courtId: {
					type: "string",
				},
				judgeDid: {
					type: "string",
					format: "did",
				},
				hearingType: {
					type: "string",
					enum: [
						"firstAppearance",
						"oral",
						"evidentiary",
						"conciliation",
						"mediation",
						"sentencing",
						"appellate",
						"procedural",
					],
				},
				scheduledAt: {
					type: "string",
					format: "datetime",
				},
				durationMin: {
					type: "integer",
				},
				location: {
					type: "string",
				},
				attendees: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				agenda: {
					type: "string",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.submitFiling",
		description: "Submit a court filing (plaint, application, vakalatnama, written statement, etc.). Document blob → Vault (zero-knowledge, ADR vault.etzhayyim.com). AT Repo holds metadata + Vault item id only.",
		inputSchema: {
			type: "object",
			required: [
				"caseDid",
				"filingType",
				"courtDid",
				"vaultItemId",
			],
			properties: {
				caseDid: {
					type: "string",
					format: "did",
				},
				filingType: {
					type: "string",
					enum: [
						"plaint",
						"complaint",
						"vakalatnama",
						"written-statement",
						"rejoinder",
						"interim-application",
						"appeal",
						"review",
						"writ-petition",
						"evidence-affidavit",
						"exhibit",
					],
				},
				courtDid: {
					type: "string",
					format: "did",
				},
				vaultItemId: {
					type: "string",
					description: "com.etzhayyim.vault.* item id holding ciphertext PDF/scan",
				},
				filedAt: {
					type: "string",
					format: "datetime",
				},
				feeAmount: {
					type: "number",
				},
				feeCurrency: {
					type: "string",
					default: "INR",
				},
				lang: {
					type: "string",
					description: "Filing language (court of record requires en/hi or state language)",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.trackFiling",
		description: "Track court filing status (registry acceptance, defect notice, listing, hearing date).",
		inputSchema: {
			type: "object",
			properties: {
				filingDid: {
					type: "string",
					format: "did",
				},
			},
			required: [
				"filingDid",
			],
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.translateFromLang",
		description: "Translate a regional-language text into en (court of record) or hi. Inverse of translateToLang.",
		inputSchema: {
			type: "object",
			properties: {
				text: {
					type: "string",
				},
				sourceLang: {
					type: "string",
				},
				targetLang: {
					type: "string",
					default: "en",
					description: "en | hi",
				},
				domain: {
					type: "string",
				},
			},
			required: [
				"text",
				"sourceLang",
			],
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.translateToLang",
		description: "Translate a case-bound text fragment into a target Indian Scheduled Language. Pipethrough to did:web:lawfirm.etzhayyim.com:lang:{targetLang} actor (Murakumo MLX backend).",
		inputSchema: {
			type: "object",
			properties: {
				text: {
					type: "string",
				},
				sourceLang: {
					type: "string",
					description: "Auto-detect when omitted",
				},
				targetLang: {
					type: "string",
					description: "ISO of one of 22 Scheduled Languages + en",
				},
				domain: {
					type: "string",
					description: "Legal domain hint for terminology accuracy",
				},
				register: {
					type: "string",
					enum: [
						"plain",
						"court-of-record",
						"client-friendly",
					],
				},
			},
			required: [
				"text",
				"targetLang",
			],
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.updateCase",
		description: "Append a status transition or note to an existing case. Write-only derived (260407): handler writes com.etzhayyim.apps.lawfirm.caseEvent record; downstream notification + projector derive from kotodama.jsonld rule.",
		inputSchema: {
			type: "object",
			required: [
				"caseDid",
				"event",
			],
			properties: {
				caseDid: {
					type: "string",
					format: "did",
				},
				event: {
					type: "string",
					enum: [
						"filed",
						"served",
						"hearing-scheduled",
						"hearing-held",
						"evidence-submitted",
						"judgment",
						"appeal",
						"settled",
						"withdrawn",
						"closed",
					],
				},
				occurredAt: {
					type: "string",
					format: "datetime",
				},
				noteEncrypted: {
					type: "string",
					description: "signal:v1:{ciphertext} (attorney-client privilege)",
				},
				nextHearingAt: {
					type: "string",
					format: "datetime",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.updateMatterStatus",
		description: "Transition a matter's lifecycle status. Enforces allowed transitions:\n  intake          → conflictCheck / engaged / withdrawn\n  conflictCheck   → engaged (requires conflictCheck.result IN {clear, disclosureRequired, waivable}) / withdrawn\n  engaged         → filed / closed (settled) / archived\n  filed           → hearing / judgment / withdrawn\n  hearing         → trial / judgment / conciliated\n  trial           → judgment\n  judgment        → appeal / execution / closed\n  appeal          → judgment / closed\n  execution       → closed\nReverse transitions are rejected. Use closeMatter for the terminal close flow (which performs open-blocker checks + grant cascade revoke).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"newStatus",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				newStatus: {
					type: "string",
					enum: [
						"intake",
						"conflictCheck",
						"engaged",
						"filed",
						"hearing",
						"trial",
						"judgment",
						"appeal",
						"execution",
						"closed",
						"archived",
						"withdrawn",
					],
				},
				reason: {
					type: "string",
				},
				conflictCheckRef: {
					type: "string",
					format: "at-uri",
					description: "Required when newStatus=engaged and previous status was conflictCheck",
				},
			},
		},
	},
	{
		name: "com.etzhayyim.apps.lawfirm.uploadDocument",
		description: "Upload a legal document to a matter. Body contains vault-encrypted ciphertext (per ADR root §Vault Zero-Knowledge Invariant; server never sees plaintext). Server (1) stores ciphertext as R2 blob keyed by SHA-256 cid, (2) mints documentDid = did:etzhayyim:{firm}:{matter}:{doc} via com.etzhayyim.auth.mintChildDid (materialKind='doc', docCid=cid), (3) writes legalDocument record. Privileged by default; AI-generated drafts enter status='pendingReview' awaiting approverBengoshiDid.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"docType",
				"title",
				"cid",
				"privileged",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				docType: {
					type: "string",
					enum: [
						"pleading",
						"motion",
						"brief",
						"evidence",
						"contract",
						"memo",
						"letter",
						"opinion",
						"filing",
						"correspondence",
						"other",
					],
				},
				title: {
					type: "string",
				},
				cid: {
					type: "string",
					description: "SHA-256 hex of vault-encrypted ciphertext (pre-computed client-side)",
				},
				privileged: {
					type: "boolean",
				},
				authorDid: {
					type: "string",
					format: "did",
				},
				aiGenerated: {
					type: "boolean",
					default: false,
					description: "When true, record enters status=pendingReview until ISCO-2611 approval (RULE-003)",
				},
				supersedesDocumentDid: {
					type: "string",
					format: "did",
				},
			},
		},
	},
]
) as readonly McpTool[];

// ── Runtime manifest (dispatcher lookup) ──

export const TOOL_MANIFEST: readonly ToolManifestEntry[] = Object.freeze(
[
	{
		nsid: "com.etzhayyim.apps.lawfirm.acceptExternalCounsel",
		description: "External counsel accepts an externalCounselGrant. Caller must authenticate as granteeDid. Server flips grant status from 'invited' → 'accepted' and vault-wraps the matter document keys for the grantee (ECIES X25519+HKDF+AES-KW).",
		inputSchema: {
			type: "object",
			required: [
				"grantDid",
			],
			properties: {
				grantDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				granteeSignalPubkey: {
					type: "string",
					description: "Signal X25519 identity pubkey for per-document key wrap",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"grantDid",
				"status",
				"acceptedAt",
			],
			properties: {
				grantDid: {
					type: "string",
				},
				status: {
					type: "string",
					enum: [
						"accepted",
					],
				},
				acceptedAt: {
					type: "string",
					format: "datetime",
				},
				wrappedDocumentKeyCount: {
					type: "integer",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.closeMatter",
		description: "Close a matter. Server (1) checks no open hearings / unpaid invoices / pending-review documents, (2) revokes all active externalCounselGrant under the matter (ADR-0029 cascade), (3) sets matter.status='closed' + closedAt, (4) optional final report derive.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"outcome",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				outcome: {
					type: "string",
					enum: [
						"wonPlaintiff",
						"wonDefendant",
						"settled",
						"dismissed",
						"withdrawn",
						"referredOut",
						"archivedInactive",
						"other",
					],
				},
				finalNote: {
					type: "string",
				},
				archiveBlob: {
					type: "boolean",
					default: false,
					description: "Emit Iceberg archive projection of matter history",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"matterDid",
				"closedAt",
				"grantsRevoked",
			],
			properties: {
				matterDid: {
					type: "string",
				},
				closedAt: {
					type: "string",
					format: "datetime",
				},
				grantsRevoked: {
					type: "integer",
				},
				openBlockers: {
					type: "array",
					items: {
						type: "string",
					},
					description: "If present, close was blocked",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.createCase",
		description: "Open a new client matter at lawfirm.etzhayyim.com. Routes to service cohort actor did:web:lawfirm.etzhayyim.com:geo:{state}[:{city}]:lang:{iso}:domain:{area} (ADR-0019 path topology, ADR-0026 cohort emergence). PII (client identity) → Preferences tier 3 (ADR-0018), AT Repo holds hashed cohort id only.",
		inputSchema: {
			type: "object",
			required: [
				"domain",
				"state",
				"lang",
			],
			properties: {
				domain: {
					type: "string",
					enum: [
						"ni138",
						"land",
						"family",
						"consumer",
						"labour",
						"corporate",
						"tax",
						"criminal",
						"rera",
						"fema",
						"pil-rti",
						"visa",
					],
				},
				state: {
					type: "string",
					description: "ISO 3166-2:IN code (e.g. IN-MH, IN-TN, IN-UP)",
				},
				city: {
					type: "string",
					description: "Municipality slug (mumbai, chennai, lucknow, ...)",
				},
				lang: {
					type: "string",
					description: "ISO 639-1/3 of client interaction (hi/bn/ta/te/mr/gu/kn/ml/pa/or/as/ur/sa/ne/sd/ks/kok/mai/mni/sat/doi/brx/en)",
				},
				courtDid: {
					type: "string",
					format: "did",
					description: "did:web:lawfirm.etzhayyim.com:court:{level}:{code} when known",
				},
				subjectSummary: {
					type: "string",
					description: "Plaintext summary in client lang. Server encrypts via signal:v1: before persist.",
				},
				amountInDispute: {
					type: "number",
				},
				currency: {
					type: "string",
					default: "INR",
				},
				urgency: {
					type: "string",
					enum: [
						"routine",
						"urgent",
						"ex-parte",
					],
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"did",
				"uri",
				"cohortDid",
			],
			properties: {
				did: {
					type: "string",
					format: "did",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				cohortDid: {
					type: "string",
					format: "did",
					description: "service cohort actor handling this matter",
				},
				caseNumber: {
					type: "string",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.createMatter",
		description: "Create a new legal matter. ADR-0029: server mints a recursive child DID (did:etzhayyim:{firm}:{matterHash}) via com.etzhayyim.auth.mintChildDid and writes the matter record at at://{firmDid}/com.etzhayyim.apps.lawfirm.matter/{matterHash}. 18 matterType values supported (civil / criminal / admin / IP / tax / labor / family / IN-specific).",
		inputSchema: {
			type: "object",
			required: [
				"firmDid",
				"matterType",
				"clientDid",
				"leadBengoshiDid",
				"openedAt",
			],
			properties: {
				firmDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}$",
					description: "Law firm root DID (depth 1). Must match caller session accountDid.",
				},
				matterType: {
					type: "string",
					enum: [
						"litigation",
						"arbitration",
						"transactional",
						"advisory",
						"compliance",
						"ip",
						"tax",
						"labor",
						"criminal-defense",
						"family",
						"administrative",
						"ipc-criminal",
						"cpc-civil",
						"ibc-insolvency",
						"tmr-ip",
						"gst-tax",
						"id-act-labor",
						"writ-petition",
					],
				},
				clientDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}(:[0-9a-f]{24}){0,5}$",
				},
				leadBengoshiDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}$",
				},
				coCounselDids: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				counterpartyDids: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				openedAt: {
					type: "string",
					format: "datetime",
				},
				jurisdiction: {
					type: "string",
					description: "ISO 3166-1 alpha-3 (JPN, IND, USA, …)",
				},
				procedureCode: {
					type: "string",
					description: "Statute/section reference (e.g. 'IPC § 498A', 'CPC O.VII R.1', 'IBC § 7')",
				},
				subjectMatter: {
					type: "string",
				},
				matterNumber: {
					type: "string",
					description: "Optional firm-local matter number (display only)",
				},
				estimatedFee: {
					type: "number",
				},
				currency: {
					type: "string",
					description: "ISO 4217",
				},
				feeStructure: {
					type: "string",
					enum: [
						"hourly",
						"fixed",
						"contingency",
						"retainer",
						"pro-bono",
					],
				},
				confidentiality: {
					type: "string",
					enum: [
						"firm",
						"matter",
						"ethicalWall",
					],
					default: "matter",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"matterDid",
				"uri",
				"matterRkey",
			],
			properties: {
				matterDid: {
					type: "string",
					description: "did:etzhayyim:{firm}:{matterHash} (depth 2)",
				},
				matterRkey: {
					type: "string",
					description: "Last 24 hex of matterDid; used as AT record rkey (DID ↔ AT URI isomorphism)",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				materialHashProof: {
					type: "string",
					description: "Hex-encoded material bytes used in H(firmDid || 0x1F || material) (ADR-0029 chain verification input)",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.getCaseStatus",
		description: "Fetch latest status + event timeline for a case. Reads from RisingWave streaming MV (graphar.vertex_lawfirmCase + edge_caseEvent).",
		inputSchema: {
			type: "object",
			properties: {
				caseDid: {
					type: "string",
					format: "did",
				},
				lang: {
					type: "string",
					description: "Translate output to this lang via did:web:lawfirm.etzhayyim.com:lang:{iso}",
				},
			},
			required: [
				"caseDid",
			],
		},
		outputSchema: {
			type: "object",
			required: [
				"caseDid",
				"status",
				"events",
			],
			properties: {
				caseDid: {
					type: "string",
					format: "did",
				},
				status: {
					type: "string",
				},
				domain: {
					type: "string",
				},
				courtDid: {
					type: "string",
					format: "did",
				},
				cohortDid: {
					type: "string",
					format: "did",
				},
				nextHearingAt: {
					type: "string",
					format: "datetime",
				},
				events: {
					type: "array",
					items: {
						type: "object",
						properties: {
							event: {
								type: "string",
							},
							occurredAt: {
								type: "string",
								format: "datetime",
							},
						},
					},
				},
			},
		},
		method: "query",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.inviteExternalCounsel",
		description: "Invite an external bengoshi (possibly from a different firm) to collaborate on a specific matter. Server: (1) runs conflict scan against matter counterparties, (2) mints a grant DID via com.etzhayyim.auth.mintChildDid under matterDid, (3) writes externalCounselGrant record in 'invited' status, (4) sends W Protocol DM with consent.request card. Ethical wall enforced at hash-prefix level (ADR-0029).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"granteeDid",
				"role",
				"capabilities",
				"expiresAt",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				granteeDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}$",
				},
				granteeHandle: {
					type: "string",
				},
				role: {
					type: "string",
					enum: [
						"coCounsel",
						"local",
						"advisory",
						"reviewer",
					],
				},
				capabilities: {
					type: "array",
					items: {
						type: "string",
						enum: [
							"read",
							"comment",
							"uploadDocument",
							"propose",
							"sign",
							"scheduleHearing",
						],
					},
				},
				expiresAt: {
					type: "string",
					format: "datetime",
				},
				message: {
					type: "string",
					description: "Optional message included in consent.request DM",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"grantDid",
				"grantUri",
			],
			properties: {
				grantDid: {
					type: "string",
					description: "did:etzhayyim:{firm}:{matter}:{grant}",
				},
				grantUri: {
					type: "string",
					format: "at-uri",
				},
				conflictCheckPassed: {
					type: "boolean",
				},
				materialHashProof: {
					type: "string",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.issueInvoice",
		description: "Generate an invoice from approved timeEntry records for a matter over a period. Server (1) selects timeEntry where status='approved' AND matter+period match, (2) mints invoiceDid via com.etzhayyim.auth.mintChildDid (materialKind='doc', docCid=invoicePdfCid), (3) writes invoice record status='draft', (4) flips selected timeEntry status='billed' with invoiceRef. PDF rendering is optional and asynchronous.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"period",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				period: {
					type: "object",
					required: [
						"from",
						"to",
					],
					properties: {
						from: {
							type: "string",
							format: "datetime",
						},
						to: {
							type: "string",
							format: "datetime",
						},
					},
				},
				includeTimeEntryRefs: {
					type: "array",
					items: {
						type: "string",
						format: "at-uri",
					},
					description: "Optional explicit allowlist; omit to include all approved entries in period",
				},
				flatFeeAmount: {
					type: "number",
				},
				flatFeeNote: {
					type: "string",
				},
				expenses: {
					type: "array",
					items: {
						type: "object",
						required: [
							"description",
							"amount",
						],
						properties: {
							description: {
								type: "string",
							},
							amount: {
								type: "number",
							},
						},
					},
				},
				taxRate: {
					type: "number",
				},
				discountAmount: {
					type: "number",
				},
				dueInDays: {
					type: "integer",
					default: 30,
				},
				invoiceNumber: {
					type: "string",
					description: "Optional firm-local invoice number (display only)",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"invoiceDid",
				"uri",
				"total",
				"currency",
				"timeEntriesBilled",
			],
			properties: {
				invoiceDid: {
					type: "string",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				subtotal: {
					type: "number",
				},
				taxAmount: {
					type: "number",
				},
				total: {
					type: "number",
				},
				currency: {
					type: "string",
				},
				timeEntriesBilled: {
					type: "integer",
				},
				dueAt: {
					type: "string",
					format: "datetime",
				},
				materialHashProof: {
					type: "string",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.listCases",
		description: "List cases scoped by cohort / geo / lang / domain. Default 50, max 200.",
		inputSchema: {
			type: "object",
			properties: {
				cohortDid: {
					type: "string",
					format: "did",
				},
				state: {
					type: "string",
					description: "ISO 3166-2:IN",
				},
				lang: {
					type: "string",
				},
				domain: {
					type: "string",
				},
				status: {
					type: "string",
				},
				limit: {
					type: "integer",
					default: 50,
					maximum: 200,
				},
				cursor: {
					type: "string",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"cases",
				"limit",
			],
			properties: {
				cases: {
					type: "array",
					items: {
						type: "object",
						properties: {
							did: {
								type: "string",
								format: "did",
							},
							domain: {
								type: "string",
							},
							status: {
								type: "string",
							},
							filedAt: {
								type: "string",
								format: "datetime",
							},
						},
					},
				},
				limit: {
					type: "integer",
				},
				cursor: {
					type: "string",
				},
			},
		},
		method: "query",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.listConflictChecks",
		description: "List conflict-of-interest scan history for a matter. Reads view_lawfirm_conflict_findings. Ordered by scannedAt DESC so the first row is the most recent scan (used by the UI to surface the current header badge).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				scanScope: {
					type: "string",
					enum: [
						"matterIntake",
						"externalCounselInvite",
						"periodicAudit",
					],
				},
				result: {
					type: "string",
					enum: [
						"clear",
						"disclosureRequired",
						"waivable",
						"blocked",
					],
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"items",
				"offset",
				"limit",
				"total",
			],
			properties: {
				items: {
					type: "array",
					items: {
						type: "object",
					},
				},
				offset: {
					type: "integer",
				},
				limit: {
					type: "integer",
				},
				total: {
					type: "integer",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.listGrants",
		description: "List external counsel grants (optionally filtered by matterDid). Reads view_lawfirm_external_counsel_access — joins grant identity with parent matter revocation cascade (ADR-0029).",
		inputSchema: {
			type: "object",
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					description: "Optional matter DID filter (depth-2 did:etzhayyim)",
				},
				includeRevoked: {
					type: "boolean",
					default: false,
					description: "When false, excludes grants where revoked_at OR parent_revoked_at is set",
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"items",
				"offset",
				"limit",
				"total",
			],
			properties: {
				items: {
					type: "array",
					items: {
						type: "object",
						properties: {
							grantDid: {
								type: "string",
							},
							matterDid: {
								type: "string",
							},
							inviterDid: {
								type: "string",
							},
							status: {
								type: "string",
							},
							materialHashProof: {
								type: "string",
							},
							createdAt: {
								type: "string",
								format: "datetime",
							},
							revokedAt: {
								type: "string",
								format: "datetime",
							},
							parentRevokedAt: {
								type: "string",
								format: "datetime",
								description: "Parent matter revoked_at — if set, grant is effectively revoked by cascade",
							},
							effectivelyActive: {
								type: "boolean",
								description: "false when self OR parent is revoked",
							},
						},
					},
				},
				offset: {
					type: "integer",
				},
				limit: {
					type: "integer",
				},
				total: {
					type: "integer",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.listInvoices",
		description: "List invoices for a matter (or firm-wide). Reads view_lawfirm_invoice_ageing which surfaces subtotal/tax/total, dueAt, status, and a derived ageing bucket (current / dueSoon / overdue30 / overdue60 / overdue90).",
		inputSchema: {
			type: "object",
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				firmDid: {
					type: "string",
					format: "did",
				},
				status: {
					type: "string",
					enum: [
						"draft",
						"sent",
						"partiallyPaid",
						"paid",
						"overdue",
						"void",
					],
				},
				ageingBucket: {
					type: "string",
					enum: [
						"current",
						"dueSoon",
						"overdue30",
						"overdue60",
						"overdue90",
					],
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"items",
				"offset",
				"limit",
				"total",
			],
			properties: {
				items: {
					type: "array",
					items: {
						type: "object",
					},
				},
				offset: {
					type: "integer",
				},
				limit: {
					type: "integer",
				},
				total: {
					type: "integer",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.listMatters",
		description: "List law firm matters with offset/limit pagination, optional filters.",
		inputSchema: {
			type: "object",
			properties: {
				matterType: {
					type: "string",
				},
				leadLawyerDid: {
					type: "string",
					format: "did",
				},
				clientDid: {
					type: "string",
					format: "did",
				},
				status: {
					type: "string",
					enum: [
						"open",
						"active",
						"stayed",
						"closed",
						"withdrawn",
					],
				},
				jurisdiction: {
					type: "string",
				},
				offset: {
					type: "integer",
					minimum: 0,
					default: 0,
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200,
					default: 50,
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"matters",
				"total",
				"offset",
				"limit",
			],
			properties: {
				matters: {
					type: "array",
					items: {
						type: "object",
						properties: {
							did: {
								type: "string",
								format: "did",
							},
							matterType: {
								type: "string",
							},
							matterNumber: {
								type: "string",
							},
							leadLawyerDid: {
								type: "string",
								format: "did",
							},
							status: {
								type: "string",
							},
							openedAt: {
								type: "string",
								format: "datetime",
							},
						},
					},
				},
				total: {
					type: "integer",
				},
				offset: {
					type: "integer",
				},
				limit: {
					type: "integer",
				},
			},
		},
		method: "query",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.recordTimeEntry",
		description: "Record a billable time entry against a matter (タイムシート).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"lawyerDid",
				"occurredOn",
				"minutes",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				lawyerDid: {
					type: "string",
					format: "did",
				},
				occurredOn: {
					type: "string",
					format: "date",
				},
				minutes: {
					type: "integer",
					minimum: 1,
				},
				activityCode: {
					type: "string",
					description: "UTBMS activity code",
				},
				narrative: {
					type: "string",
				},
				billable: {
					type: "boolean",
					default: true,
				},
				rate: {
					type: "number",
				},
				currency: {
					type: "string",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"uri",
			],
			properties: {
				uri: {
					type: "string",
					format: "at-uri",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.registerLawfirm",
		description: "Register a law firm. Path-based DID: did:web:lawfirm.etzhayyim.com:{iso3}:{slug}. ISCO-2611 HAR gate enforced.",
		inputSchema: {
			type: "object",
			required: [
				"name",
				"jurisdiction",
			],
			properties: {
				name: {
					type: "string",
				},
				nameLocal: {
					type: "string",
				},
				jurisdiction: {
					type: "string",
					description: "ISO 3166-1 alpha-3",
				},
				legalEntityDid: {
					type: "string",
					format: "did",
					description: "underlying legal-entity DID",
				},
				headquarters: {
					type: "string",
				},
				officeCount: {
					type: "integer",
					minimum: 1,
				},
				lawyerCount: {
					type: "integer",
					minimum: 1,
				},
				specializations: {
					type: "array",
					items: {
						type: "string",
					},
				},
				barAdmissions: {
					type: "array",
					items: {
						type: "string",
					},
				},
				websiteUri: {
					type: "string",
					format: "uri",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"did",
				"uri",
			],
			properties: {
				did: {
					type: "string",
					format: "did",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.requestConsult",
		description: "Initial intake. Routes through triage cohort → service cohort (ADR-0026). No PII in AT Repo; PII to Preferences tier 3.",
		inputSchema: {
			type: "object",
			required: [
				"lang",
				"summary",
			],
			properties: {
				lang: {
					type: "string",
				},
				state: {
					type: "string",
					description: "ISO 3166-2:IN",
				},
				city: {
					type: "string",
				},
				summary: {
					type: "string",
					description: "Free-text complaint in client lang",
				},
				domainHint: {
					type: "string",
				},
				channel: {
					type: "string",
					enum: [
						"web",
						"voice",
						"whatsapp",
						"in-person",
					],
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"consultDid",
				"uri",
			],
			properties: {
				consultDid: {
					type: "string",
					format: "did",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				triageCohortDid: {
					type: "string",
					format: "did",
				},
				suggestedDomain: {
					type: "string",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.respondConsult",
		description: "Lawyer / agent response to a consult. Field-level encrypted (signal:v1:) — attorney-client privilege.",
		inputSchema: {
			type: "object",
			required: [
				"consultDid",
				"responseEncrypted",
			],
			properties: {
				consultDid: {
					type: "string",
					format: "did",
				},
				responseEncrypted: {
					type: "string",
					description: "signal:v1:{ciphertext}",
				},
				respondedAt: {
					type: "string",
					format: "datetime",
				},
				responderDid: {
					type: "string",
					format: "did",
					description: "did:web:bengoshi.etzhayyim.com:IND:{barId} or cohort agent",
				},
				nextAction: {
					type: "string",
					enum: [
						"createCase",
						"moreInfo",
						"referOut",
						"decline",
					],
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"uri",
				"cid",
			],
			properties: {
				uri: {
					type: "string",
					format: "at-uri",
				},
				cid: {
					type: "string",
					format: "cid",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.revokeExternalCounsel",
		description: "Terminate an external counsel grant. Sets vertex_etzhayyim_identity.revoked_at on the grant DID — ADR-0029 ancestor cascade automatically invalidates all descendants (sessions, per-document capabilities). Vault document keys for the grantee become unwrap-impossible. Revocation is irreversible.",
		inputSchema: {
			type: "object",
			required: [
				"grantDid",
				"reason",
			],
			properties: {
				grantDid: {
					type: "string",
					format: "did",
				},
				reason: {
					type: "string",
					enum: [
						"completed",
						"conflict",
						"breach",
						"request",
						"expired",
						"other",
					],
				},
				noteToGrantee: {
					type: "string",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"grantDid",
				"revokedAt",
			],
			properties: {
				grantDid: {
					type: "string",
				},
				revokedAt: {
					type: "string",
					format: "datetime",
				},
				descendantsInvalidated: {
					type: "integer",
					description: "Number of child DIDs (sessions, sub-capabilities) now failing to resolve",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.runConflictCheck",
		description: "Run a conflict-of-interest scan and write a conflictCheck record. Two modes:\n  - matterIntake: evaluate a prospective matter's counterparties against the firm's active matter portfolio + prior representation history.\n  - externalCounselInvite: verify a candidate grantee DID does not belong to a counterparty org (reverse scan).\nThe returned result may be {clear, disclosureRequired, waivable, blocked}. When blocked the caller MUST NOT advance matter.status past 'conflictCheck' or proceed with inviteExternalCounsel.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"scanScope",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				scanScope: {
					type: "string",
					enum: [
						"matterIntake",
						"externalCounselInvite",
						"periodicAudit",
					],
				},
				counterpartyDids: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				candidateDid: {
					type: "string",
					format: "did",
					description: "Required when scanScope=externalCounselInvite",
				},
				subjectMatter: {
					type: "string",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"rkey",
				"uri",
				"result",
			],
			properties: {
				rkey: {
					type: "string",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				result: {
					type: "string",
					enum: [
						"clear",
						"disclosureRequired",
						"waivable",
						"blocked",
					],
				},
				conflicts: {
					type: "array",
					items: {
						type: "object",
					},
					description: "Shape matches conflictCheck.conflicts[]",
				},
				wallId: {
					type: "string",
				},
				scannedAt: {
					type: "string",
					format: "datetime",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.scheduleHearing",
		description: "Schedule a court hearing for a matter. Server (1) invokes saiban.scheduleTrialEvent via service sync (Write-Only Derived Architecture per ADR-0004), (2) mints hearingDid = did:etzhayyim:{firm}:{matter}:{hearing} via com.etzhayyim.auth.mintChildDid, (3) writes hearing record mirror, (4) registers Path F scheduler cron for reminder + docket-pull. Changes to the saiban-side record are replayed to the mirror via subscribeRepos on saiban collections.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"hearingType",
				"scheduledAt",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
				},
				courtId: {
					type: "string",
				},
				judgeDid: {
					type: "string",
					format: "did",
				},
				hearingType: {
					type: "string",
					enum: [
						"firstAppearance",
						"oral",
						"evidentiary",
						"conciliation",
						"mediation",
						"sentencing",
						"appellate",
						"procedural",
					],
				},
				scheduledAt: {
					type: "string",
					format: "datetime",
				},
				durationMin: {
					type: "integer",
				},
				location: {
					type: "string",
				},
				attendees: {
					type: "array",
					items: {
						type: "string",
						format: "did",
					},
				},
				agenda: {
					type: "string",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"hearingDid",
				"uri",
				"saibanJikenRef",
			],
			properties: {
				hearingDid: {
					type: "string",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				saibanJikenRef: {
					type: "string",
					format: "at-uri",
				},
				materialHashProof: {
					type: "string",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.submitFiling",
		description: "Submit a court filing (plaint, application, vakalatnama, written statement, etc.). Document blob → Vault (zero-knowledge, ADR vault.etzhayyim.com). AT Repo holds metadata + Vault item id only.",
		inputSchema: {
			type: "object",
			required: [
				"caseDid",
				"filingType",
				"courtDid",
				"vaultItemId",
			],
			properties: {
				caseDid: {
					type: "string",
					format: "did",
				},
				filingType: {
					type: "string",
					enum: [
						"plaint",
						"complaint",
						"vakalatnama",
						"written-statement",
						"rejoinder",
						"interim-application",
						"appeal",
						"review",
						"writ-petition",
						"evidence-affidavit",
						"exhibit",
					],
				},
				courtDid: {
					type: "string",
					format: "did",
				},
				vaultItemId: {
					type: "string",
					description: "com.etzhayyim.vault.* item id holding ciphertext PDF/scan",
				},
				filedAt: {
					type: "string",
					format: "datetime",
				},
				feeAmount: {
					type: "number",
				},
				feeCurrency: {
					type: "string",
					default: "INR",
				},
				lang: {
					type: "string",
					description: "Filing language (court of record requires en/hi or state language)",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"did",
				"uri",
			],
			properties: {
				did: {
					type: "string",
					format: "did",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				filingNumber: {
					type: "string",
				},
				ackAt: {
					type: "string",
					format: "datetime",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.trackFiling",
		description: "Track court filing status (registry acceptance, defect notice, listing, hearing date).",
		inputSchema: {
			type: "object",
			properties: {
				filingDid: {
					type: "string",
					format: "did",
				},
			},
			required: [
				"filingDid",
			],
		},
		outputSchema: {
			type: "object",
			required: [
				"filingDid",
				"status",
			],
			properties: {
				filingDid: {
					type: "string",
					format: "did",
				},
				status: {
					type: "string",
					enum: [
						"draft",
						"submitted",
						"accepted",
						"defective",
						"registered",
						"listed",
						"disposed",
					],
				},
				filingNumber: {
					type: "string",
				},
				courtDid: {
					type: "string",
					format: "did",
				},
				nextDate: {
					type: "string",
					format: "datetime",
				},
				defectReason: {
					type: "string",
				},
			},
		},
		method: "query",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.translateFromLang",
		description: "Translate a regional-language text into en (court of record) or hi. Inverse of translateToLang.",
		inputSchema: {
			type: "object",
			properties: {
				text: {
					type: "string",
				},
				sourceLang: {
					type: "string",
				},
				targetLang: {
					type: "string",
					default: "en",
					description: "en | hi",
				},
				domain: {
					type: "string",
				},
			},
			required: [
				"text",
				"sourceLang",
			],
		},
		outputSchema: {
			type: "object",
			required: [
				"text",
				"targetLang",
			],
			properties: {
				text: {
					type: "string",
				},
				targetLang: {
					type: "string",
				},
				sourceLang: {
					type: "string",
				},
				modelId: {
					type: "string",
				},
			},
		},
		method: "query",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.translateToLang",
		description: "Translate a case-bound text fragment into a target Indian Scheduled Language. Pipethrough to did:web:lawfirm.etzhayyim.com:lang:{targetLang} actor (Murakumo MLX backend).",
		inputSchema: {
			type: "object",
			properties: {
				text: {
					type: "string",
				},
				sourceLang: {
					type: "string",
					description: "Auto-detect when omitted",
				},
				targetLang: {
					type: "string",
					description: "ISO of one of 22 Scheduled Languages + en",
				},
				domain: {
					type: "string",
					description: "Legal domain hint for terminology accuracy",
				},
				register: {
					type: "string",
					enum: [
						"plain",
						"court-of-record",
						"client-friendly",
					],
				},
			},
			required: [
				"text",
				"targetLang",
			],
		},
		outputSchema: {
			type: "object",
			required: [
				"text",
				"targetLang",
			],
			properties: {
				text: {
					type: "string",
				},
				targetLang: {
					type: "string",
				},
				sourceLang: {
					type: "string",
				},
				modelId: {
					type: "string",
					description: "resolveModelId() result",
				},
			},
		},
		method: "query",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.updateCase",
		description: "Append a status transition or note to an existing case. Write-only derived (260407): handler writes com.etzhayyim.apps.lawfirm.caseEvent record; downstream notification + projector derive from kotodama.jsonld rule.",
		inputSchema: {
			type: "object",
			required: [
				"caseDid",
				"event",
			],
			properties: {
				caseDid: {
					type: "string",
					format: "did",
				},
				event: {
					type: "string",
					enum: [
						"filed",
						"served",
						"hearing-scheduled",
						"hearing-held",
						"evidence-submitted",
						"judgment",
						"appeal",
						"settled",
						"withdrawn",
						"closed",
					],
				},
				occurredAt: {
					type: "string",
					format: "datetime",
				},
				noteEncrypted: {
					type: "string",
					description: "signal:v1:{ciphertext} (attorney-client privilege)",
				},
				nextHearingAt: {
					type: "string",
					format: "datetime",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"uri",
				"cid",
			],
			properties: {
				uri: {
					type: "string",
					format: "at-uri",
				},
				cid: {
					type: "string",
					format: "cid",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.updateMatterStatus",
		description: "Transition a matter's lifecycle status. Enforces allowed transitions:\n  intake          → conflictCheck / engaged / withdrawn\n  conflictCheck   → engaged (requires conflictCheck.result IN {clear, disclosureRequired, waivable}) / withdrawn\n  engaged         → filed / closed (settled) / archived\n  filed           → hearing / judgment / withdrawn\n  hearing         → trial / judgment / conciliated\n  trial           → judgment\n  judgment        → appeal / execution / closed\n  appeal          → judgment / closed\n  execution       → closed\nReverse transitions are rejected. Use closeMatter for the terminal close flow (which performs open-blocker checks + grant cascade revoke).",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"newStatus",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				newStatus: {
					type: "string",
					enum: [
						"intake",
						"conflictCheck",
						"engaged",
						"filed",
						"hearing",
						"trial",
						"judgment",
						"appeal",
						"execution",
						"closed",
						"archived",
						"withdrawn",
					],
				},
				reason: {
					type: "string",
				},
				conflictCheckRef: {
					type: "string",
					format: "at-uri",
					description: "Required when newStatus=engaged and previous status was conflictCheck",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"matterDid",
				"previousStatus",
				"newStatus",
				"updatedAt",
			],
			properties: {
				matterDid: {
					type: "string",
				},
				previousStatus: {
					type: "string",
				},
				newStatus: {
					type: "string",
				},
				updatedAt: {
					type: "string",
					format: "datetime",
				},
			},
		},
		method: "procedure",
	},
	{
		nsid: "com.etzhayyim.apps.lawfirm.uploadDocument",
		description: "Upload a legal document to a matter. Body contains vault-encrypted ciphertext (per ADR root §Vault Zero-Knowledge Invariant; server never sees plaintext). Server (1) stores ciphertext as R2 blob keyed by SHA-256 cid, (2) mints documentDid = did:etzhayyim:{firm}:{matter}:{doc} via com.etzhayyim.auth.mintChildDid (materialKind='doc', docCid=cid), (3) writes legalDocument record. Privileged by default; AI-generated drafts enter status='pendingReview' awaiting approverBengoshiDid.",
		inputSchema: {
			type: "object",
			required: [
				"matterDid",
				"docType",
				"title",
				"cid",
				"privileged",
			],
			properties: {
				matterDid: {
					type: "string",
					format: "did",
					pattern: "^did:etzhayyim:[0-9a-f]{24}:[0-9a-f]{24}$",
				},
				docType: {
					type: "string",
					enum: [
						"pleading",
						"motion",
						"brief",
						"evidence",
						"contract",
						"memo",
						"letter",
						"opinion",
						"filing",
						"correspondence",
						"other",
					],
				},
				title: {
					type: "string",
				},
				cid: {
					type: "string",
					description: "SHA-256 hex of vault-encrypted ciphertext (pre-computed client-side)",
				},
				privileged: {
					type: "boolean",
				},
				authorDid: {
					type: "string",
					format: "did",
				},
				aiGenerated: {
					type: "boolean",
					default: false,
					description: "When true, record enters status=pendingReview until ISCO-2611 approval (RULE-003)",
				},
				supersedesDocumentDid: {
					type: "string",
					format: "did",
				},
			},
		},
		outputSchema: {
			type: "object",
			required: [
				"documentDid",
				"uri",
				"status",
			],
			properties: {
				documentDid: {
					type: "string",
				},
				uri: {
					type: "string",
					format: "at-uri",
				},
				status: {
					type: "string",
					enum: [
						"draft",
						"pendingReview",
						"approved",
					],
				},
				materialHashProof: {
					type: "string",
				},
			},
		},
		method: "procedure",
	},
]
) as readonly ToolManifestEntry[];
