// microsoft.etzhayyim.com — Microsoft 365 write facade.
//
// Policy (per deps.toml [etzhayyim_agent.auth]):
//   - All-internal recipients  → direct Mail.Send.
//   - Any external recipient   → createDraft → human approval → sendDraft.
//
// Internal domain classification: INTERNAL_EMAIL_DOMAINS env var (comma-separated) +
// INTERNAL_EMAIL_SUFFIXES (comma-separated domain suffixes, e.g. .onmicrosoft.com
// for Teams channel email addresses).
//
// Host wiring: createHostSDK auto-constructs the m365 capability when M365_TENANT_ID
// / M365_CLIENT_ID / M365_CLIENT_SECRET are bound. No app-level setup needed.

import {
	asAgentTool,
	createWorkerExport,
	DecisionClass,
	hostClient,
	nsid,
	parseLexiconInput,
	requireApproval,
	type LexiconOutput,
} from "@etzhayyim/kotodama-host-sdk";

function parseList(s: string | undefined): string[] {
	return (s ?? "")
		.split(",")
		.map((x) => x.trim().toLowerCase())
		.filter((x) => x.length > 0);
}

function isInternal(email: string, domains: string[], suffixes: string[]): boolean {
	const lower = email.trim().toLowerCase();
	const at = lower.lastIndexOf("@");
	if (at < 0) return false;
	const domain = lower.slice(at + 1);
	if (domains.includes(domain)) return true;
	for (const suf of suffixes) {
		if (suf.length > 0 && domain.endsWith(suf)) return true;
	}
	return false;
}

function allInternal(
	recipients: string[],
	domains: string[],
	suffixes: string[],
): boolean {
	if (recipients.length === 0) return false;
	return recipients.every((r) => isInternal(r, domains, suffixes));
}

function resolveFromUpn(input: { fromUpn?: string }, env: Record<string, unknown>): string {
	const fromUpn = (input.fromUpn ?? "").trim() || String(env.DEFAULT_SENDER_UPN ?? "").trim();
	if (!fromUpn) throw new Error("SENDER_UPN_REQUIRED: provide fromUpn or set DEFAULT_SENDER_UPN");
	return fromUpn;
}

// ── MCP tool registration ────────────────────────────────────────────────
// Tools are registered once as `com.etzhayyim.tool.tool` records in `vertex_capability`
// (via `com.etzhayyim.kagami.sql` INSERT). See `60-apps/etzhayyim-project-microsoft/AGENTS.md`
// §"MCP tool registration" for the one-shot seed command. The PDS `com.etzhayyim.tool.register*`
// XRPC handlers are currently unusable (RisingWave rejects the `ON CONFLICT` Kysely
// emits); direct INSERT is the workaround.
//
// This Worker does NOT self-register on cold start — the per-row INSERT latency
// (~11s × 3) would blow the 25s XRPC handler timeout on every fresh isolate.

export default createWorkerExport((sdk) => {
	sdk.app.command(
		nsid("com.etzhayyim.apps.microsoft.sendMail"),
		async (_ctx, body) => {
			const env = sdk.env;
			const internalDomains = parseList(String(env.INTERNAL_EMAIL_DOMAINS ?? "etzhayyim.com,etzhayyim.com,etzhayyim.works,etzhayyim.com"));
			const internalSuffixes = parseList(String(env.INTERNAL_EMAIL_SUFFIXES ?? ".onmicrosoft.com"));
			const input = parseLexiconInput("com.etzhayyim.apps.microsoft.sendMail", body);
			const fromUpn = resolveFromUpn(input, env);
			const to = input.to ?? [];
			const cc = input.cc ?? [];
			const bcc = input.bcc ?? [];
			const allRecipients = [...to, ...cc, ...bcc];

			const { access_token } = await hostClient.m365AcquireAppToken({});

			if (allInternal(allRecipients, internalDomains, internalSuffixes)) {
				await hostClient.m365SendMail({
					token: access_token,
					fromUpn,
					to,
					cc,
					bcc,
					subject: input.subject ?? "",
					bodyHtml: input.bodyHtml,
					bodyText: input.bodyText,
					saveToSentItems: true,
					importance: input.importance,
					replyTo: input.replyTo,
				});
				const output: LexiconOutput<"com.etzhayyim.apps.microsoft.sendMail"> = {
					status: "sent",
					fromUpn,
					recipientCount: allRecipients.length,
				};
				return JSON.stringify(output);
			}

			const draft = await hostClient.m365CreateDraft({
				token: access_token,
				fromUpn,
				to,
				cc,
				bcc,
				subject: input.subject ?? "",
				bodyHtml: input.bodyHtml,
				bodyText: input.bodyText,
				importance: input.importance,
				replyTo: input.replyTo,
			});

			// Register human-approval task in kaisya portal (non-fatal)
			{
				const keyRaw = env.KAISYA_SERVICE_KEY;
				const serviceKey = keyRaw
					? (typeof keyRaw === "object" && "get" in (keyRaw as object)
						? await (keyRaw as { get(): Promise<string> }).get().catch(() => "")
						: String(keyRaw))
					: "";
				if (serviceKey) {
					const kaisyaUrl = String(env.KAISYA_CREATE_TASK_URL ?? "https://kaisya.etzhayyim.com");
					const externalList = allRecipients.slice(0, 3).join(", ") + (allRecipients.length > 3 ? ` 他${allRecipients.length - 3}名` : "");
					await fetch(`${kaisyaUrl}/xrpc/com.etzhayyim.apps.kaisya.createTask`, {
						method: "POST",
						headers: { "content-type": "application/json", authorization: `Bearer ${serviceKey}` },
						body: JSON.stringify({
							agentId: "did:web:microsoft.etzhayyim.com",
							humanDid: "did:web:auth.etzhayyim.com:admin:bootstrap",
							title: `メール下書き要確認: ${input.subject ?? "(件名なし)"} → ${externalList}`,
							contextJson: JSON.stringify({ draftId: draft.id, webLink: draft.webLink, subject: input.subject, to, cc, ...(bcc.length > 0 ? { bcc } : {}) }),
							priority: 2,
						}),
					}).catch((e: unknown) => console.error("createTask non-fatal:", e));
				}
			}

			const output: LexiconOutput<"com.etzhayyim.apps.microsoft.sendMail"> = {
				status: "drafted",
				reason: "external recipient(s) detected — human approval required",
				fromUpn,
				recipientCount: allRecipients.length,
				draftId: draft.id,
				webLink: draft.webLink,
			};
			return JSON.stringify(output);
		},
		asAgentTool(
			"Send email via Microsoft 365. All-internal recipients (@etzhayyim.com / @etzhayyim.com / @etzhayyim.works / @etzhayyim.com and Teams channel email addresses) send directly. Any external recipient creates a draft in Outlook and returns draftId + webLink for human approval (caller then invokes sendDraft).",
		),
	);

	sdk.app.command(
		nsid("com.etzhayyim.apps.microsoft.sendDraft"),
		async (_ctx, body) => {
			const env = sdk.env;
			const input = parseLexiconInput("com.etzhayyim.apps.microsoft.sendDraft", body);
			const fromUpn = resolveFromUpn(input, env);
			if (!input.draftId) throw new Error("draftId required");
			const { access_token } = await hostClient.m365AcquireAppToken({});
			await hostClient.m365SendDraft({
				token: access_token,
				fromUpn,
				draftId: input.draftId,
			});
			const output: LexiconOutput<"com.etzhayyim.apps.microsoft.sendDraft"> = {
				status: "sent",
				fromUpn,
				draftId: input.draftId,
			};
			return JSON.stringify(output);
		},
		asAgentTool(
			"Send a previously created draft by id (post human approval). Use after com.etzhayyim.apps.microsoft.sendMail returns status=drafted, once a human has reviewed the draft at webLink.",
		),
		// Governance gate: external-recipient mail requires human approval.
		// deps.toml [etzhayyim_agent.auth].email_send_external = "draft_only" → sendDraft
		// cannot fire autonomously; PDS governance manifest blocks until one human (class C
		// decision, low risk tier) approves the specific invocation.
		requireApproval(DecisionClass.C, 1, "low"),
	);

	sdk.app.query(nsid("com.etzhayyim.apps.microsoft.listInbox"), async (_ctx, body) => {
		const env = sdk.env;
		const decoded: Record<string, unknown> = (() => {
			try {
				const text = new TextDecoder().decode(body as unknown as Uint8Array);
				return text ? (JSON.parse(text) as Record<string, unknown>) : {};
			} catch { return {}; }
		})();
		if (typeof decoded.top === "string" && decoded.top !== "") {
			const n = Number(decoded.top);
			if (Number.isFinite(n)) decoded.top = Math.round(n);
		}
		const coerced = new TextEncoder().encode(JSON.stringify(decoded));
		const input = parseLexiconInput("com.etzhayyim.apps.microsoft.listInbox", coerced);
		const fromUpn = resolveFromUpn(input, env);
		const { access_token } = await hostClient.m365AcquireAppToken({});
		const { messages, nextLink } = await hostClient.m365FetchMessagesPage({
			token: access_token,
			upn: fromUpn,
			top: input.top ?? 50,
			since: input.since,
			nextLink: input.nextLink,
			folder: input.folder,
		});
		// Normalise raw Graph message objects → lexicon shape
		type RawMsg = {
			id?: string; conversationId?: string; subject?: string;
			from?: { emailAddress?: { address?: string; name?: string } };
			toRecipients?: Array<{ emailAddress?: { address?: string } }>;
			receivedDateTime?: string; bodyPreview?: string;
			isRead?: boolean; importance?: string; hasAttachments?: boolean;
		};
		const normalized = (messages as RawMsg[]).map((m) => ({
			id:             m.id ?? "",
			conversationId: m.conversationId ?? "",
			subject:        m.subject ?? "",
			fromAddress:    m.from?.emailAddress?.address ?? "",
			fromName:       m.from?.emailAddress?.name ?? "",
			toAddresses:    (m.toRecipients ?? [])
				.map((r) => r.emailAddress?.address ?? "").filter(Boolean).join(","),
			receivedAt:     m.receivedDateTime ?? "",
			bodyPreview:    (m.bodyPreview ?? "").slice(0, 500),
			isRead:         m.isRead ?? false,
			importance:     m.importance ?? "normal",
			hasAttachments: m.hasAttachments ?? false,
		}));
		const output: LexiconOutput<"com.etzhayyim.apps.microsoft.listInbox"> = {
			fromUpn,
			messages: normalized,
			nextLink: nextLink ?? "",
		};
		return JSON.stringify(output);
	});

	sdk.app.command(nsid("com.etzhayyim.apps.microsoft.batchMoveMessages"), async (_ctx, body) => {
		const input = parseLexiconInput("com.etzhayyim.apps.microsoft.batchMoveMessages", body);
		const { access_token } = await hostClient.m365AcquireAppToken({});
		const { results, succeeded, failed } = await hostClient.m365BatchMoveMessages({
			token: access_token,
			upn: input.upn,
			messageIds: input.messageIds as string[],
			targetFolder: input.targetFolder,
		});
		const output: LexiconOutput<"com.etzhayyim.apps.microsoft.batchMoveMessages"> = {
			results: results as LexiconOutput<"com.etzhayyim.apps.microsoft.batchMoveMessages">["results"],
			succeeded,
			failed,
		};
		return JSON.stringify(output);
	});

	sdk.app.query(nsid("com.etzhayyim.apps.microsoft.listDrafts"), async (_ctx, body) => {
		const env = sdk.env;
		// XRPC query params arrive as JSON bytes with string values (e.g. {"top":"3"}).
		// Decode, coerce numeric fields, then re-encode before Lexicon validation.
		const decoded: Record<string, unknown> = (() => {
			try {
				const text = new TextDecoder().decode(body as unknown as Uint8Array);
				return text ? (JSON.parse(text) as Record<string, unknown>) : {};
			} catch {
				return {};
			}
		})();
		if (typeof decoded.top === "string" && decoded.top !== "") {
			const n = Number(decoded.top);
			if (Number.isFinite(n)) decoded.top = Math.round(n);
		}
		const coerced = new TextEncoder().encode(JSON.stringify(decoded));
		const input = parseLexiconInput("com.etzhayyim.apps.microsoft.listDrafts", coerced);
		const fromUpn = resolveFromUpn(input, env);
		const { access_token } = await hostClient.m365AcquireAppToken({});
		const { drafts } = await hostClient.m365ListDrafts({
			token: access_token,
			fromUpn,
			top: input.top,
		});
		const output: LexiconOutput<"com.etzhayyim.apps.microsoft.listDrafts"> = {
			fromUpn,
			drafts,
		};
		return JSON.stringify(output);
	});
});
