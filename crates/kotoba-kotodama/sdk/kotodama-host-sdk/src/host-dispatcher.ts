// host-dispatcher.ts — NSID → host implementation router (BindingTransport pattern).
//
// F-Plan (Lexicon SSoT) Phase 2: routes every com.etzhayyim.host.* NSID to the legacy
// host-imports.ts methods. The generated host client (src/generated/host-client.ts)
// calls into this dispatcher, which in turn calls the existing HostImports methods.
//
// No behavior change for apps using sdk.hostImports.* directly. New code should
// import typed capability functions from the generated client instead.
//
// Phase 3 will archive the WIT world.wit files and flip CLAUDE.md / deps.toml
// "TS Native + WIT Contract" to "TS Native + Lexicon Contract".

import type { M365Capability } from "./capabilities/m365.js";
import type { HostDispatcher } from "./generated/host-client.js";
import { HOST_NSID } from "./generated/host-client.js";
import type { HostImports } from "./types.js";

export interface HostDispatcherExtras {
	/** Optional Microsoft 365 Graph capability. Required if any `com.etzhayyim.host.m365.*` NSID is invoked. */
	m365?: M365Capability;
}

function b64ToBytes(s: string): Uint8Array {
	if (typeof s !== "string" || s.length === 0) return new Uint8Array();
	const bin = atob(s);
	const out = new Uint8Array(bin.length);
	for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
	return out;
}

function bytesToB64(bytes: Uint8Array): string {
	let bin = "";
	for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
	return btoa(bin);
}

export function createHostDispatcher(
	hostImports: HostImports,
	extras: HostDispatcherExtras = {},
): HostDispatcher {
	return {
		async dispatch<T>(nsid: string, input: unknown): Promise<T> {
			const i = (input ?? {}) as Record<string, any>;
			let result: unknown;
			switch (nsid) {
				// ── core ──
				case HOST_NSID.coreConfigGet: {
					const value = hostImports.configGet(i.key);
					result = value !== undefined ? { value } : {};
					break;
				}
				case HOST_NSID.coreLogAppend: {
					const offset = hostImports.logAppend(i.stream, i.subject, b64ToBytes(i.payload));
					result = { offset: Number(offset) };
					break;
				}

				// ── authn / authz ──
				case HOST_NSID.authnVerifyToken: {
					const claims = hostImports.authnVerifyToken(i.token);
					result = { claims: bytesToB64(claims) };
					break;
				}
				case HOST_NSID.authzEnforce: {
					hostImports.authzEnforce(
						i.orgId,
						i.role,
						i.permissions ?? [],
						i.requiredPermissions ?? [],
						i.requiredRoles ?? [],
					);
					result = { allowed: true };
					break;
				}

				// ── storage family ──
				case HOST_NSID.ipfsPublish: {
					const url = hostImports.ipfsPublish(b64ToBytes(i.data), i.contentType);
					result = { cid: url };
					break;
				}
				case HOST_NSID.storagePutObject: {
					const etag = hostImports.storagePutObject(
						i.bucket,
						i.key,
						b64ToBytes(i.data),
						i.contentType,
					);
					result = { etag };
					break;
				}
				case HOST_NSID.storageGetObject: {
					const bytes = hostImports.storageGetObject(i.bucket, i.key);
					result = { data: bytesToB64(bytes) };
					break;
				}
				case HOST_NSID.cdnUpload: {
					const url = hostImports.cdnUpload(
						i.subdomain,
						i.path,
						b64ToBytes(i.data),
						i.contentType,
					);
					result = { url };
					break;
				}
				case HOST_NSID.cdnPublicUrl: {
					const url = hostImports.cdnPublicUrl(i.subdomain, i.path);
					result = { url };
					break;
				}

				// ── telemetry / observability ──
				case HOST_NSID.telemetryEmitMetric: {
					hostImports.telemetryEmitMetric(i.name, i.value, i.tagsJson ?? "{}");
					result = { ok: true };
					break;
				}
				case HOST_NSID.telemetryLog: {
					hostImports.telemetryLog(i.level, i.message, i.attributesJson ?? "{}");
					result = { ok: true };
					break;
				}
				case HOST_NSID.accessLogRecord: {
					hostImports.accessLogRecord(i.entryJson);
					result = { ok: true };
					break;
				}
				case HOST_NSID.ocelEmitEvent: {
					hostImports.ocelEmitEvent(i.eventJson);
					result = { ok: true };
					break;
				}

				// ── pubsub ──
				case HOST_NSID.pubsubPublish: {
					hostImports.pubsubPublish(i.topic, b64ToBytes(i.payload));
					result = { ok: true };
					break;
				}
				case HOST_NSID.pubsubPull: {
					const envelopesJson = hostImports.pubsubPull(i.topic, i.maxMessages);
					result = { envelopesJson };
					break;
				}

				// ── secrets ──
				case HOST_NSID.secretsGet: {
					const value = hostImports.secretsGet(i.key);
					result = value !== null ? { found: true, value } : { found: false };
					break;
				}
				case HOST_NSID.secretsSet: {
					hostImports.secretsSet(i.key, i.value);
					result = { ok: true };
					break;
				}
				case HOST_NSID.secretsDelete: {
					hostImports.secretsDelete(i.key);
					result = { ok: true };
					break;
				}

				// ── lock ──
				case HOST_NSID.lockTryLock: {
					const acquired = hostImports.lockTryLock(i.key, BigInt(i.ttlMs));
					result = { acquired };
					break;
				}
				case HOST_NSID.lockUnlock: {
					hostImports.lockUnlock(i.key);
					result = { ok: true };
					break;
				}

				// ── virtual actor ──
				case HOST_NSID.virtualActorInvoke: {
					const resultJson = hostImports.virtualActorInvoke(
						i.actorType,
						i.actorId,
						i.method,
						i.paramsJson,
					);
					result = { resultJson };
					break;
				}

				// ── llm / agent ──
				case HOST_NSID.llmChat: {
					const response = hostImports.agentChat(i.userMessage, i.llmContextJson);
					result = { response };
					break;
				}
				case HOST_NSID.llmConverse: {
					const response = hostImports.agentConverse(i.messages, {
						model: i.model,
						useCase: i.useCase,
					});
					result = typeof response === "string"
						? { response }
						: (response as Record<string, unknown>) ?? { response: "" };
					break;
				}
				case HOST_NSID.llmRoute: {
					const toolName = hostImports.agentRoute(i.inputJson);
					result = { toolName };
					break;
				}
				case HOST_NSID.llmReact: {
					const resultJson = hostImports.agentReact(i.taskJson, i.optionsJson);
					result = { resultJson };
					break;
				}

				// ── parallel activity ──
				case HOST_NSID.activitySpawnParallel: {
					const batchId = hostImports.activitySpawnParallel(i.activitiesJson);
					result = { batchId };
					break;
				}
				case HOST_NSID.activityAwaitAll: {
					const resultsJson = hostImports.activityAwaitAll(i.batchId, BigInt(i.timeoutMs));
					result = { resultsJson };
					break;
				}

				// ── identity / capability ──
				case HOST_NSID.identityResolve: {
					const did = hostImports.identityResolve(i.nanoid);
					result = did !== null ? { did } : {};
					break;
				}
				case HOST_NSID.identityListActors: {
					const actorsJson = hostImports.identityListActors(i.offset, i.limit);
					result = { actorsJson };
					break;
				}
				case HOST_NSID.capabilityListOwn: {
					const capabilitiesJson = hostImports.capabilityListOwn();
					result = { capabilitiesJson };
					break;
				}
				case HOST_NSID.capabilityDiscover: {
					const capabilitiesJson = hostImports.capabilityDiscover(
						i.tag ?? null,
						i.status ?? null,
						i.offset,
						i.limit,
					);
					result = { capabilitiesJson };
					break;
				}

				// ── conversation ──
				case HOST_NSID.conversationCreateSession: {
					const sessionId = hostImports.conversationCreateSession(i.topic, i.participantsJson);
					result = { sessionId };
					break;
				}
				case HOST_NSID.conversationSendMessage: {
					const envelopeJson = hostImports.conversationSendMessage(i.sessionId, i.content);
					result = { envelopeJson };
					break;
				}

				// ── governance ──
				case HOST_NSID.governanceRegisterManifest: {
					hostImports.governanceRegisterManifest(i.manifestJson);
					result = { ok: true };
					break;
				}
				case HOST_NSID.governanceCheckPolicy: {
					const verdict = hostImports.governanceCheckPolicy(i.command, i.userId, i.orgId);
					result = { verdictJson: JSON.stringify(verdict) };
					break;
				}

				// ── invoke ──
				case HOST_NSID.invokeCall: {
					const bytes = hostImports.invoke(i.did, i.method, b64ToBytes(i.params));
					result = { result: bytesToB64(bytes) };
					break;
				}

				// ── m365 (Microsoft Graph) ──
				case HOST_NSID.m365AcquireAppToken: {
					result = await requireM365(extras).acquireAppToken();
					break;
				}
				case HOST_NSID.m365EnumerateUsers: {
					result = await requireM365(extras).enumerateUsers({
						token: i.token,
						upnDomainSuffix: i.upnDomainSuffix,
						top: i.top,
					});
					break;
				}
				case HOST_NSID.m365FetchMailFolders: {
					result = await requireM365(extras).fetchMailFolders({
						token: i.token,
						upn: i.upn,
					});
					break;
				}
				case HOST_NSID.m365FetchMessagesPage: {
					result = await requireM365(extras).fetchMessagesPage({
						token: i.token,
						upn: i.upn,
						since: i.since,
						top: i.top,
						nextLink: i.nextLink,
					});
					break;
				}
				case HOST_NSID.m365SendMail: {
					result = await requireM365(extras).sendMail({
						token: i.token,
						fromUpn: i.fromUpn,
						to: i.to ?? [],
						cc: i.cc,
						bcc: i.bcc,
						subject: i.subject,
						bodyHtml: i.bodyHtml,
						bodyText: i.bodyText,
						saveToSentItems: i.saveToSentItems,
						importance: i.importance,
						replyTo: i.replyTo,
					});
					break;
				}
				case HOST_NSID.m365CreateDraft: {
					result = await requireM365(extras).createDraft({
						token: i.token,
						fromUpn: i.fromUpn,
						to: i.to ?? [],
						cc: i.cc,
						bcc: i.bcc,
						subject: i.subject,
						bodyHtml: i.bodyHtml,
						bodyText: i.bodyText,
						importance: i.importance,
						replyTo: i.replyTo,
					});
					break;
				}
				case HOST_NSID.m365SendDraft: {
					result = await requireM365(extras).sendDraft({
						token: i.token,
						fromUpn: i.fromUpn,
						draftId: i.draftId,
					});
					break;
				}
				case HOST_NSID.m365ListDrafts: {
					result = await requireM365(extras).listDrafts({
						token: i.token,
						fromUpn: i.fromUpn,
						top: i.top,
					});
					break;
				}

				case HOST_NSID.m365BatchMoveMessages: {
					result = await requireM365(extras).batchMoveMessages({
						token: i.token,
						upn: i.upn,
						messageIds: i.messageIds,
						targetFolder: i.targetFolder,
					});
					break;
				}

				default:
					throw new Error(`host-dispatcher: unknown NSID '${nsid}'`);
			}
			return result as T;
		},
	};
}

function requireM365(extras: HostDispatcherExtras): M365Capability {
	if (!extras.m365) {
		throw new Error(
			"host-dispatcher: m365 capability not provided. Pass { m365: createM365Capability({...}) } to createHostDispatcher.",
		);
	}
	return extras.m365;
}
