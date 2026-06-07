// capabilities/m365.ts — Microsoft 365 Graph API host capability.
//
// Backs `com.etzhayyim.host.m365.*` lexicons. Used by T1 `m365-ingest` actor pipelines
// (and any other actor that declares `host.m365.*` capability).
//
// - Client credentials flow (app-only): requires tenant-admin-granted
//   Application.Mail.Read (or Mail.ReadBasic) on Microsoft Graph.
// - Token cache: per-instance memoization for ~55 min (tokens valid 1h).
// - Retry/backoff on 429/503 via Retry-After honor.
// - No PII persisted in host; all raw message payloads passed through to caller
//   (caller writes Signal-enveloped record per ADR-0014 Tier 3).
//
// Env / secrets:
//   M365_TENANT_ID        — tenant GUID
//   M365_CLIENT_ID        — Azure AD app registration client id
//   M365_CLIENT_SECRET    — client secret (from CF Secrets Store or wrangler secret)

export interface M365Config {
	tenantId: string;
	clientId: string;
	/** Client secret. String (plain env var) or provider function (CF Secrets Store binding — resolved each token acquisition). */
	clientSecret: string | (() => Promise<string>);
	/** Graph scope, default "https://graph.microsoft.com/.default" */
	scope?: string;
	/** Override authority host (sovereign cloud etc.). Default login.microsoftonline.com */
	authority?: string;
	/** Override graph host. Default graph.microsoft.com */
	graphHost?: string;
}

export interface M365SendMailInput {
	token: string;
	fromUpn: string;
	to: string[];
	cc?: string[];
	bcc?: string[];
	subject: string;
	bodyHtml?: string;
	bodyText?: string;
	saveToSentItems?: boolean;
	importance?: "low" | "normal" | "high";
	replyTo?: string[];
}

export interface M365CreateDraftInput extends Omit<M365SendMailInput, "saveToSentItems"> {}

export interface M365DraftSummary {
	id?: string;
	subject?: string;
	toRecipients?: string[];
	createdDateTime?: string;
	lastModifiedDateTime?: string;
	webLink?: string;
}

export interface M365Capability {
	acquireAppToken(): Promise<{ access_token: string; expires_in: number; scope?: string }>;
	enumerateUsers(input: { token: string; upnDomainSuffix?: string; top?: number }): Promise<{
		users: Array<{
			id?: string;
			userPrincipalName?: string;
			mail?: string;
			displayName?: string;
			accountEnabled?: boolean;
		}>;
	}>;
	fetchMailFolders(input: { token: string; upn: string }): Promise<{
		folders: Array<{
			id?: string;
			displayName?: string;
			parentFolderId?: string;
			totalItemCount?: number;
		}>;
	}>;
	fetchMessagesPage(input: { token: string; upn: string; since?: string; top?: number; nextLink?: string; folder?: string }): Promise<{
		messages: unknown[];
		nextLink?: string;
	}>;
	sendMail(input: M365SendMailInput): Promise<{ ok: boolean }>;
	createDraft(input: M365CreateDraftInput): Promise<{ id: string; webLink?: string; conversationId?: string }>;
	sendDraft(input: { token: string; fromUpn: string; draftId: string }): Promise<{ ok: boolean }>;
	listDrafts(input: { token: string; fromUpn: string; top?: number }): Promise<{ drafts: M365DraftSummary[] }>;
	batchMoveMessages(input: { token: string; upn: string; messageIds: string[]; targetFolder: string }): Promise<{
		results: Array<{ id: string; ok: boolean; status: number; error?: string }>;
		succeeded: number;
		failed: number;
	}>;
}

const DEFAULT_SCOPE = "https://graph.microsoft.com/.default";
const DEFAULT_AUTHORITY = "login.microsoftonline.com";
const DEFAULT_GRAPH = "graph.microsoft.com";
const TOKEN_CACHE_SKEW_MS = 5 * 60 * 1000; // refresh 5min before expiry

interface CachedToken {
	accessToken: string;
	expiresAt: number;
	scope?: string;
}

export function createM365Capability(cfg: M365Config): M365Capability {
	if (!cfg.tenantId || !cfg.clientId || !cfg.clientSecret) {
		throw new Error("createM365Capability: tenantId/clientId/clientSecret required");
	}
	const resolveClientSecret = async (): Promise<string> => {
		if (typeof cfg.clientSecret === "function") return await cfg.clientSecret();
		return cfg.clientSecret;
	};
	const scope = cfg.scope ?? DEFAULT_SCOPE;
	const authority = cfg.authority ?? DEFAULT_AUTHORITY;
	const graphHost = cfg.graphHost ?? DEFAULT_GRAPH;
	let cached: CachedToken | null = null;

	async function graphGet(url: string, token: string, maxAttempts = 5): Promise<Response> {
		let backoff = 1000;
		for (let attempt = 0; attempt < maxAttempts; attempt++) {
			const res = await fetch(url, {
				headers: {
					Authorization: `Bearer ${token}`,
					Accept: "application/json",
					ConsistencyLevel: "eventual",
				},
			});
			if (res.ok) return res;
			if (res.status === 429 || res.status === 503) {
				const ra = Number(res.headers.get("Retry-After")) || backoff / 1000;
				await sleep(Math.max(ra * 1000, backoff));
				backoff *= 2;
				continue;
			}
			if (res.status === 401 && attempt === 0) {
				// invalidate cached token, let caller retry after re-acquisition
				cached = null;
				throw new GraphAuthError("401 Unauthorized — token invalidated");
			}
			const body = await res.text().catch(() => "");
			throw new GraphError(`Graph ${res.status}: ${body.slice(0, 280)}`);
		}
		throw new GraphError(`Graph retries exhausted: ${url}`);
	}

	async function graphPost(
		url: string,
		token: string,
		body: unknown,
		maxAttempts = 5,
	): Promise<Response> {
		let backoff = 1000;
		const payload = JSON.stringify(body);
		for (let attempt = 0; attempt < maxAttempts; attempt++) {
			const res = await fetch(url, {
				method: "POST",
				headers: {
					Authorization: `Bearer ${token}`,
					"Content-Type": "application/json",
					Accept: "application/json",
				},
				body: payload,
			});
			if (res.ok || res.status === 202) return res;
			if (res.status === 429 || res.status === 503) {
				const ra = Number(res.headers.get("Retry-After")) || backoff / 1000;
				await sleep(Math.max(ra * 1000, backoff));
				backoff *= 2;
				continue;
			}
			if (res.status === 401 && attempt === 0) {
				cached = null;
				throw new GraphAuthError("401 Unauthorized — token invalidated");
			}
			const text = await res.text().catch(() => "");
			throw new GraphError(`Graph ${res.status}: ${text.slice(0, 280)}`);
		}
		throw new GraphError(`Graph retries exhausted: ${url}`);
	}

	function buildMessageBody(input: {
		to: string[];
		cc?: string[];
		bcc?: string[];
		subject: string;
		bodyHtml?: string;
		bodyText?: string;
		importance?: "low" | "normal" | "high";
		replyTo?: string[];
	}): Record<string, unknown> {
		const addr = (e: string) => ({ emailAddress: { address: e } });
		const body =
			input.bodyHtml && input.bodyHtml.length > 0
				? { contentType: "HTML", content: input.bodyHtml }
				: { contentType: "Text", content: input.bodyText ?? "" };
		const msg: Record<string, unknown> = {
			subject: input.subject,
			body,
			toRecipients: (input.to ?? []).map(addr),
		};
		if (input.cc && input.cc.length > 0) msg.ccRecipients = input.cc.map(addr);
		if (input.bcc && input.bcc.length > 0) msg.bccRecipients = input.bcc.map(addr);
		if (input.importance) msg.importance = input.importance;
		if (input.replyTo && input.replyTo.length > 0) msg.replyTo = input.replyTo.map(addr);
		return msg;
	}

	return {
		async acquireAppToken() {
			const now = Date.now();
			if (cached && cached.expiresAt - TOKEN_CACHE_SKEW_MS > now) {
				return {
					access_token: cached.accessToken,
					expires_in: Math.max(1, Math.floor((cached.expiresAt - now) / 1000)),
					scope: cached.scope,
				};
			}
			const secretValue = await resolveClientSecret();
			if (!secretValue) {
				throw new GraphAuthError("clientSecret provider returned empty value (check Secrets Store binding)");
			}
			const body = new URLSearchParams({
				client_id: cfg.clientId,
				client_secret: secretValue,
				grant_type: "client_credentials",
				scope,
			});
			const res = await fetch(`https://${authority}/${cfg.tenantId}/oauth2/v2.0/token`, {
				method: "POST",
				headers: { "Content-Type": "application/x-www-form-urlencoded" },
				body,
			});
			if (!res.ok) {
				const detail = await res.text().catch(() => "");
				throw new GraphAuthError(`Token acquisition failed (${res.status}): ${detail.slice(0, 280)}`);
			}
			const j = (await res.json()) as { access_token?: string; expires_in?: number; scope?: string };
			if (!j.access_token || !j.expires_in) {
				throw new GraphAuthError("Token response missing access_token or expires_in");
			}
			cached = {
				accessToken: j.access_token,
				expiresAt: now + j.expires_in * 1000,
				scope: j.scope,
			};
			return { access_token: j.access_token, expires_in: j.expires_in, scope: j.scope };
		},

		async enumerateUsers(input) {
			const top = Math.min(Math.max(input.top ?? 999, 1), 999);
			const params = new URLSearchParams({
				$top: String(top),
				$select: "id,userPrincipalName,mail,displayName,accountEnabled",
			});
			if (input.upnDomainSuffix) {
				params.set("$filter", `endsWith(userPrincipalName,'${input.upnDomainSuffix}')`);
			}
			const out: M365Capability extends { enumerateUsers(...a: unknown[]): Promise<infer R> } ? R : never = {
				users: [],
			} as any;
			let url = `https://${graphHost}/v1.0/users?${params.toString()}`;
			while (url) {
				const res = await graphGet(url, input.token);
				const j = (await res.json()) as { value?: unknown[]; "@odata.nextLink"?: string };
				if (Array.isArray(j.value)) {
					for (const u of j.value) {
						const uu = u as {
							id?: string;
							userPrincipalName?: string;
							mail?: string;
							displayName?: string;
							accountEnabled?: boolean;
						};
						out.users.push({
							id: uu.id,
							userPrincipalName: uu.userPrincipalName,
							mail: uu.mail,
							displayName: uu.displayName,
							accountEnabled: uu.accountEnabled,
						});
					}
				}
				url = j["@odata.nextLink"] ?? "";
			}
			return out;
		},

		async fetchMailFolders(input) {
			const folders: Array<{
				id?: string;
				displayName?: string;
				parentFolderId?: string;
				totalItemCount?: number;
			}> = [];
			const upn = encodeURIComponent(input.upn);
			async function walk(folderId?: string): Promise<void> {
				const base = `https://${graphHost}/v1.0/users/${upn}/mailFolders`;
				let url = folderId
					? `${base}/${folderId}/childFolders?$top=100&$select=id,displayName,parentFolderId,totalItemCount,childFolderCount`
					: `${base}?$top=100&$select=id,displayName,parentFolderId,totalItemCount,childFolderCount`;
				while (url) {
					const res = await graphGet(url, input.token);
					const j = (await res.json()) as { value?: unknown[]; "@odata.nextLink"?: string };
					if (Array.isArray(j.value)) {
						for (const f of j.value) {
							const ff = f as {
								id?: string;
								displayName?: string;
								parentFolderId?: string;
								totalItemCount?: number;
								childFolderCount?: number;
							};
							folders.push({
								id: ff.id,
								displayName: ff.displayName,
								parentFolderId: ff.parentFolderId,
								totalItemCount: ff.totalItemCount,
							});
							if (ff.id && (ff.childFolderCount ?? 0) > 0) {
								await walk(ff.id);
							}
						}
					}
					url = j["@odata.nextLink"] ?? "";
				}
			}
			await walk();
			return { folders };
		},

		async fetchMessagesPage(input) {
			let url: string;
			if (input.nextLink) {
				url = input.nextLink;
			} else {
				const top = Math.min(Math.max(input.top ?? 999, 1), 999);
				const select = [
					"id",
					"internetMessageId",
					"conversationId",
					"parentFolderId",
					"subject",
					"from",
					"toRecipients",
					"ccRecipients",
					"bccRecipients",
					"sender",
					"replyTo",
					"importance",
					"isRead",
					"hasAttachments",
					"flag",
					"receivedDateTime",
					"sentDateTime",
					"bodyPreview",
					"webLink",
				].join(",");
				const params = new URLSearchParams({
					$top: String(top),
					$select: select,
					$orderby: "receivedDateTime desc",
				});
				if (input.since) {
					params.set("$filter", `receivedDateTime ge ${input.since}`);
				}
				const folderSegment = input.folder
					? `/mailFolders/${encodeURIComponent(input.folder)}`
					: "";
				url = `https://${graphHost}/v1.0/users/${encodeURIComponent(input.upn)}${folderSegment}/messages?${params.toString()}`;
			}
			const res = await graphGet(url, input.token);
			const j = (await res.json()) as { value?: unknown[]; "@odata.nextLink"?: string };
			return {
				messages: Array.isArray(j.value) ? j.value : [],
				nextLink: j["@odata.nextLink"],
			};
		},

		async sendMail(input) {
			if (!input.fromUpn) throw new GraphError("sendMail: fromUpn required");
			if (!input.to || input.to.length === 0) throw new GraphError("sendMail: to[] required");
			const url = `https://${graphHost}/v1.0/users/${encodeURIComponent(input.fromUpn)}/sendMail`;
			const message = buildMessageBody(input);
			await graphPost(url, input.token, {
				message,
				saveToSentItems: input.saveToSentItems ?? true,
			});
			return { ok: true };
		},

		async createDraft(input) {
			if (!input.fromUpn) throw new GraphError("createDraft: fromUpn required");
			if (!input.to || input.to.length === 0) throw new GraphError("createDraft: to[] required");
			const url = `https://${graphHost}/v1.0/users/${encodeURIComponent(input.fromUpn)}/messages`;
			const res = await graphPost(url, input.token, buildMessageBody(input));
			const j = (await res.json()) as { id?: string; webLink?: string; conversationId?: string };
			if (!j.id) throw new GraphError("createDraft: Graph response missing id");
			return { id: j.id, webLink: j.webLink, conversationId: j.conversationId };
		},

		async sendDraft(input) {
			if (!input.fromUpn) throw new GraphError("sendDraft: fromUpn required");
			if (!input.draftId) throw new GraphError("sendDraft: draftId required");
			const url = `https://${graphHost}/v1.0/users/${encodeURIComponent(input.fromUpn)}/messages/${encodeURIComponent(input.draftId)}/send`;
			await graphPost(url, input.token, {});
			return { ok: true };
		},

		async listDrafts(input) {
			if (!input.fromUpn) throw new GraphError("listDrafts: fromUpn required");
			const top = Math.min(Math.max(input.top ?? 25, 1), 100);
			const params = new URLSearchParams({
				$top: String(top),
				$select: "id,subject,toRecipients,createdDateTime,lastModifiedDateTime,webLink",
				$orderby: "lastModifiedDateTime desc",
			});
			const url = `https://${graphHost}/v1.0/users/${encodeURIComponent(input.fromUpn)}/mailFolders/drafts/messages?${params.toString()}`;
			const res = await graphGet(url, input.token);
			const j = (await res.json()) as { value?: unknown[] };
			const drafts: M365DraftSummary[] = Array.isArray(j.value)
				? j.value.map((m) => {
						const mm = m as {
							id?: string;
							subject?: string;
							toRecipients?: Array<{ emailAddress?: { address?: string } }>;
							createdDateTime?: string;
							lastModifiedDateTime?: string;
							webLink?: string;
						};
						return {
							id: mm.id,
							subject: mm.subject,
							toRecipients: (mm.toRecipients ?? [])
								.map((r) => r?.emailAddress?.address)
								.filter((s): s is string => typeof s === "string"),
							createdDateTime: mm.createdDateTime,
							lastModifiedDateTime: mm.lastModifiedDateTime,
							webLink: mm.webLink,
						};
					})
				: [];
			return { drafts };
		},

		async batchMoveMessages(input) {
			const ids = input.messageIds.slice(0, 20);
			const batchUrl = `https://${graphHost}/v1.0/$batch`;
			const batchBody = {
				requests: ids.map((id, i) => ({
					id: String(i),
					method: "POST",
					url: `/users/${encodeURIComponent(input.upn)}/messages/${encodeURIComponent(id)}/move`,
					headers: { "Content-Type": "application/json" },
					body: { destinationId: input.targetFolder },
				})),
			};
			const res = await fetch(batchUrl, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Authorization": `Bearer ${input.token}`,
				},
				body: JSON.stringify(batchBody),
			});
			const j = (await res.json()) as { responses?: Array<{ id: string; status: number; body?: unknown }> };
			const responses = j.responses ?? [];
			const results = ids.map((id, i) => {
				const r = responses.find((x) => x.id === String(i));
				const ok = r ? r.status >= 200 && r.status < 300 : false;
				return { id, ok, status: r?.status ?? 0, error: ok ? undefined : JSON.stringify(r?.body) };
			});
			return {
				results,
				succeeded: results.filter((r) => r.ok).length,
				failed: results.filter((r) => !r.ok).length,
			};
		},
	};
}

function sleep(ms: number): Promise<void> {
	return new Promise((r) => setTimeout(r, ms));
}

export class GraphError extends Error {
	constructor(message: string) {
		super(message);
		this.name = "GraphError";
	}
}

export class GraphAuthError extends GraphError {
	constructor(message: string) {
		super(message);
		this.name = "GraphAuthError";
	}
}
