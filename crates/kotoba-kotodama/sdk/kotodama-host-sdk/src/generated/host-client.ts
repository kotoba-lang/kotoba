// host-client.ts — Auto-generated typed host capability client.
// DO NOT EDIT. Regenerate with: node 70-tools/scripts/contract/gen-host-client-from-lexicon.mjs
//
// Lexicon JSON (00-contracts/lexicons/com/etzhayyim/host/) is the Single Source of Truth
// for host capability surface. F-Plan Phase 1: replaces WIT-defined host imports.
//
// Runtime contract: each function forwards to a HostDispatcher supplied at SDK init.
// The dispatcher routes NSIDs to host implementation functions (in-process, BindingTransport).

export interface HostDispatcher {
	dispatch<T>(nsid: string, input: unknown): Promise<T>;
}

let _dispatcher: HostDispatcher | null = null;

export function setHostDispatcher(dispatcher: HostDispatcher): void {
	_dispatcher = dispatcher;
}

function requireDispatcher(): HostDispatcher {
	if (!_dispatcher) {
		throw new Error('HostDispatcher not set. Call setHostDispatcher() during SDK init.');
	}
	return _dispatcher;
}

// ── NSID constants (frozen Single Source) ──

export const HOST_NSID = {
	accessLogRecord: 'com.etzhayyim.host.accessLog.record' as const,
	activityAwaitAll: 'com.etzhayyim.host.activity.awaitAll' as const,
	activitySpawnParallel: 'com.etzhayyim.host.activity.spawnParallel' as const,
	authnVerifyToken: 'com.etzhayyim.host.authn.verifyToken' as const,
	authzEnforce: 'com.etzhayyim.host.authz.enforce' as const,
	capabilityDiscover: 'com.etzhayyim.host.capability.discover' as const,
	capabilityListOwn: 'com.etzhayyim.host.capability.listOwn' as const,
	cdnPublicUrl: 'com.etzhayyim.host.cdn.publicUrl' as const,
	cdnUpload: 'com.etzhayyim.host.cdn.upload' as const,
	conversationCreateSession: 'com.etzhayyim.host.conversation.createSession' as const,
	conversationSendMessage: 'com.etzhayyim.host.conversation.sendMessage' as const,
	coreConfigGet: 'com.etzhayyim.host.core.configGet' as const,
	coreLogAppend: 'com.etzhayyim.host.core.logAppend' as const,
	governanceCheckPolicy: 'com.etzhayyim.host.governance.checkPolicy' as const,
	governanceRegisterManifest: 'com.etzhayyim.host.governance.registerManifest' as const,
	identityListActors: 'com.etzhayyim.host.identity.listActors' as const,
	identityResolve: 'com.etzhayyim.host.identity.resolve' as const,
	invokeCall: 'com.etzhayyim.host.invoke.call' as const,
	ipfsPublish: 'com.etzhayyim.host.ipfs.publish' as const,
	llmChat: 'com.etzhayyim.host.llm.chat' as const,
	llmConverse: 'com.etzhayyim.host.llm.converse' as const,
	llmReact: 'com.etzhayyim.host.llm.react' as const,
	llmRoute: 'com.etzhayyim.host.llm.route' as const,
	lockTryLock: 'com.etzhayyim.host.lock.tryLock' as const,
	lockUnlock: 'com.etzhayyim.host.lock.unlock' as const,
	m365AcquireAppToken: 'com.etzhayyim.host.m365.acquireAppToken' as const,
	m365BatchMoveMessages: 'com.etzhayyim.host.m365.batchMoveMessages' as const,
	m365CreateDraft: 'com.etzhayyim.host.m365.createDraft' as const,
	m365EnumerateUsers: 'com.etzhayyim.host.m365.enumerateUsers' as const,
	m365FetchMailFolders: 'com.etzhayyim.host.m365.fetchMailFolders' as const,
	m365FetchMessagesPage: 'com.etzhayyim.host.m365.fetchMessagesPage' as const,
	m365ListDrafts: 'com.etzhayyim.host.m365.listDrafts' as const,
	m365SendDraft: 'com.etzhayyim.host.m365.sendDraft' as const,
	m365SendMail: 'com.etzhayyim.host.m365.sendMail' as const,
	ocelEmitEvent: 'com.etzhayyim.host.ocel.emitEvent' as const,
	pubsubPublish: 'com.etzhayyim.host.pubsub.publish' as const,
	pubsubPull: 'com.etzhayyim.host.pubsub.pull' as const,
	secretsDelete: 'com.etzhayyim.host.secrets.delete' as const,
	secretsGet: 'com.etzhayyim.host.secrets.get' as const,
	secretsSet: 'com.etzhayyim.host.secrets.set' as const,
	storageGetObject: 'com.etzhayyim.host.storage.getObject' as const,
	storagePutObject: 'com.etzhayyim.host.storage.putObject' as const,
	telemetryEmitMetric: 'com.etzhayyim.host.telemetry.emitMetric' as const,
	telemetryLog: 'com.etzhayyim.host.telemetry.log' as const,
	virtualActorInvoke: 'com.etzhayyim.host.virtualActor.invoke' as const,
} as const;

// ── Typed capability functions ──

// ── accessLog ──

/** Record an access log entry (auto-collected path). */
export async function accessLogRecord(input: { entryJson: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.accessLogRecord, input);
}


// ── activity ──

/** Join on a previously spawned parallel batch. Returns results array. */
export async function activityAwaitAll(input: { batchId: string; timeoutMs: number }): Promise<{ resultsJson: string }> {
	return requireDispatcher().dispatch<{ resultsJson: string }>(HOST_NSID.activityAwaitAll, input);
}

/** Fan out a batch of activities for parallel execution. Returns batch ID. */
export async function activitySpawnParallel(input: { activitiesJson: string }): Promise<{ batchId: string }> {
	return requireDispatcher().dispatch<{ batchId: string }>(HOST_NSID.activitySpawnParallel, input);
}


// ── authn ──

/** Verify a bearer token and return its claims (base64 bytes). */
export async function authnVerifyToken(input: { token: string }): Promise<{ claims: string }> {
	return requireDispatcher().dispatch<{ claims: string }>(HOST_NSID.authnVerifyToken, input);
}


// ── authz ──

/** In-process RBAC enforcement. Throws on deny, returns on allow. */
export async function authzEnforce(input: { orgId: string; role: string; permissions: string[]; requiredPermissions: string[]; requiredRoles: string[] }): Promise<{ allowed: boolean }> {
	return requireDispatcher().dispatch<{ allowed: boolean }>(HOST_NSID.authzEnforce, input);
}


// ── capability ──

/** Discover capabilities by tag/status (CV-1 discovery). */
export async function capabilityDiscover(input: { tag?: string; status?: string; offset: number; limit: number }): Promise<{ capabilitiesJson: string }> {
	return requireDispatcher().dispatch<{ capabilitiesJson: string }>(HOST_NSID.capabilityDiscover, input);
}

/** List capabilities owned by the current actor. */
export async function capabilityListOwn(input: Record<string, unknown>): Promise<{ capabilitiesJson: string }> {
	return requireDispatcher().dispatch<{ capabilitiesJson: string }>(HOST_NSID.capabilityListOwn, input);
}


// ── cdn ──

/** Resolve the public URL for a CDN object. */
export async function cdnPublicUrl(input: { subdomain: string; path: string }): Promise<{ url: string }> {
	return requireDispatcher().dispatch<{ url: string }>(HOST_NSID.cdnPublicUrl, input);
}

/** Upload bytes to the CDN under a subdomain/path. */
export async function cdnUpload(input: { subdomain: string; path: string; data: string; contentType: string }): Promise<{ url: string }> {
	return requireDispatcher().dispatch<{ url: string }>(HOST_NSID.cdnUpload, input);
}


// ── conversation ──

/** Create a W Protocol WChannel conversation session. */
export async function conversationCreateSession(input: { topic: string; participantsJson: string }): Promise<{ sessionId: string }> {
	return requireDispatcher().dispatch<{ sessionId: string }>(HOST_NSID.conversationCreateSession, input);
}

/** Send a message into an existing conversation session. */
export async function conversationSendMessage(input: { sessionId: string; content: string }): Promise<{ envelopeJson: string }> {
	return requireDispatcher().dispatch<{ envelopeJson: string }>(HOST_NSID.conversationSendMessage, input);
}


// ── core ──

/** Resolve a configuration value (env var / SPIN_VARIABLE_*). */
export async function coreConfigGet(input: { key: string }): Promise<{ value?: string }> {
	return requireDispatcher().dispatch<{ value?: string }>(HOST_NSID.coreConfigGet, input);
}

/** Append a log record to a named stream. */
export async function coreLogAppend(input: { stream: string; subject: string; payload: string }): Promise<{ offset: number }> {
	return requireDispatcher().dispatch<{ offset: number }>(HOST_NSID.coreLogAppend, input);
}


// ── governance ──

/** Check whether a command is permitted for a user under current policy. */
export async function governanceCheckPolicy(input: { command: string; userId: string; orgId: string }): Promise<{ verdictJson: string }> {
	return requireDispatcher().dispatch<{ verdictJson: string }>(HOST_NSID.governanceCheckPolicy, input);
}

/** Register a governance manifest (RACI / approval policy) for the current actor. */
export async function governanceRegisterManifest(input: { manifestJson: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.governanceRegisterManifest, input);
}


// ── identity ──

/** Paginated list of registered actor DIDs. */
export async function identityListActors(input: { offset: number; limit: number }): Promise<{ actorsJson: string }> {
	return requireDispatcher().dispatch<{ actorsJson: string }>(HOST_NSID.identityListActors, input);
}

/** Resolve a nanoid to its DID. Returns null if not registered. */
export async function identityResolve(input: { nanoid: string }): Promise<{ did?: string }> {
	return requireDispatcher().dispatch<{ did?: string }>(HOST_NSID.identityResolve, input);
}


// ── invoke ──

/** DID-addressed RPC call. Governance-gated. Empty did = host auto-discovers provider. */
export async function invokeCall(input: { did: string; method: string; params: string }): Promise<{ result: string }> {
	return requireDispatcher().dispatch<{ result: string }>(HOST_NSID.invokeCall, input);
}


// ── ipfs ──

/** Publish bytes to IPFS (S3/R2-backed). Returns CIDv1. */
export async function ipfsPublish(input: { data: string; contentType: string }): Promise<{ cid: string }> {
	return requireDispatcher().dispatch<{ cid: string }>(HOST_NSID.ipfsPublish, input);
}


// ── llm ──

/** Single-turn LLM chat (legacy agentChat). Prefer llm.converse for structured I/O. */
export async function llmChat(input: { userMessage: string; llmContextJson: string }): Promise<{ response: string }> {
	return requireDispatcher().dispatch<{ response: string }>(HOST_NSID.llmChat, input);
}

/** Multi-turn structured LLM conversation. Routes to Murakumo or CF Workers AI per llm-model-registry. In-process capability (BindingTransport). */
export async function llmConverse(input: { messages: { role: string; content: string }[]; model?: string; useCase?: string }): Promise<{ response: string; model?: string }> {
	return requireDispatcher().dispatch<{ response: string; model?: string }>(HOST_NSID.llmConverse, input);
}

/** ReAct loop: LLM → tool → observe → repeat until stop condition or max iterations. */
export async function llmReact(input: { taskJson: string; optionsJson: string }): Promise<{ resultJson: string }> {
	return requireDispatcher().dispatch<{ resultJson: string }>(HOST_NSID.llmReact, input);
}

/** Intent classification via LLM tool_choice=required. Returns tool name, does not execute. */
export async function llmRoute(input: { inputJson: string }): Promise<{ toolName: string }> {
	return requireDispatcher().dispatch<{ toolName: string }>(HOST_NSID.llmRoute, input);
}


// ── lock ──

/** Attempt to acquire a distributed lock with a TTL lease. */
export async function lockTryLock(input: { key: string; ttlMs: number }): Promise<{ acquired: boolean }> {
	return requireDispatcher().dispatch<{ acquired: boolean }>(HOST_NSID.lockTryLock, input);
}

/** Release a previously acquired lock. */
export async function lockUnlock(input: { key: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.lockUnlock, input);
}


// ── m365 ──

/** Acquire a Microsoft Graph app-only access token via client credentials flow. Uses tenant secret from Cloudflare Secrets Store. */
export async function m365AcquireAppToken(input: Record<string, unknown>): Promise<{ access_token: string; expires_in: number; scope?: string }> {
	return requireDispatcher().dispatch<{ access_token: string; expires_in: number; scope?: string }>(HOST_NSID.m365AcquireAppToken, input);
}

/** Move up to 20 messages to a well-known folder via Graph $batch API. */
export async function m365BatchMoveMessages(input: { token: string; upn: string; messageIds: string[]; targetFolder: string }): Promise<{ results: { id?: string; ok?: boolean; status?: number; error?: string }[]; succeeded: number; failed: number }> {
	return requireDispatcher().dispatch<{ results: { id?: string; ok?: boolean; status?: number; error?: string }[]; succeeded: number; failed: number }>(HOST_NSID.m365BatchMoveMessages, input);
}

/** Create a draft email via Graph POST /users/{fromUpn}/messages. The message lands in the Drafts folder and is NOT sent. Returns the draft id + Outlook web link for human review/approval. Used for external-recipient policy (draft_only). */
export async function m365CreateDraft(input: { token: string; fromUpn: string; to: string[]; cc?: string[]; bcc?: string[]; subject: string; bodyHtml?: string; bodyText?: string; importance?: string; replyTo?: string[] }): Promise<{ id: string; webLink?: string; conversationId?: string }> {
	return requireDispatcher().dispatch<{ id: string; webLink?: string; conversationId?: string }>(HOST_NSID.m365CreateDraft, input);
}

/** Enumerate tenant users matching a UPN domain filter. Uses ConsistencyLevel=eventual for advanced filters. */
export async function m365EnumerateUsers(input: { token: string; upnDomainSuffix?: string; top?: number }): Promise<{ users: { id?: string; userPrincipalName?: string; mail?: string; displayName?: string; accountEnabled?: boolean }[] }> {
	return requireDispatcher().dispatch<{ users: { id?: string; userPrincipalName?: string; mail?: string; displayName?: string; accountEnabled?: boolean }[] }>(HOST_NSID.m365EnumerateUsers, input);
}

/** Fetch all mail folders (recursive childFolders) for a user. Returns flat id→displayName map. */
export async function m365FetchMailFolders(input: { token: string; upn: string }): Promise<{ folders: { id?: string; displayName?: string; parentFolderId?: string; totalItemCount?: number }[] }> {
	return requireDispatcher().dispatch<{ folders: { id?: string; displayName?: string; parentFolderId?: string; totalItemCount?: number }[] }>(HOST_NSID.m365FetchMailFolders, input);
}

/** Fetch one page of /users/{upn}/messages. Pagination via nextLink. Classification (folder → signal_class, sender_kind) is caller responsibility. */
export async function m365FetchMessagesPage(input: { token: string; upn: string; since?: string; top?: number; nextLink?: string }): Promise<{ messages: unknown[]; nextLink?: string }> {
	return requireDispatcher().dispatch<{ messages: unknown[]; nextLink?: string }>(HOST_NSID.m365FetchMessagesPage, input);
}

/** List drafts in /users/{fromUpn}/mailFolders/drafts/messages (newest first). Used for approval UIs / audit trails. */
export async function m365ListDrafts(input: { token: string; fromUpn: string; top?: number }): Promise<{ drafts: { id?: string; subject?: string; toRecipients?: string[]; createdDateTime?: string; lastModifiedDateTime?: string; webLink?: string }[] }> {
	return requireDispatcher().dispatch<{ drafts: { id?: string; subject?: string; toRecipients?: string[]; createdDateTime?: string; lastModifiedDateTime?: string; webLink?: string }[] }>(HOST_NSID.m365ListDrafts, input);
}

/** Send a previously created draft via Graph POST /users/{fromUpn}/messages/{id}/send. Post-approval transition from createDraft → sent. The draft is consumed (removed from Drafts, copy in Sent Items). */
export async function m365SendDraft(input: { token: string; fromUpn: string; draftId: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.m365SendDraft, input);
}

/** Send an email via Graph POST /users/{fromUpn}/sendMail. Requires Azure app-only Mail.Send. This host capability is unconditional — policy routing (internal direct / external draft_only) is enforced by the caller (e.g. com.etzhayyim.apps.microsoft.sendMail). For Teams channel posting, pass the channel email address as a recipient (channel_email_via_mail_send pattern). */
export async function m365SendMail(input: { token: string; fromUpn: string; to: string[]; cc?: string[]; bcc?: string[]; subject: string; bodyHtml?: string; bodyText?: string; saveToSentItems?: boolean; importance?: string; replyTo?: string[] }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.m365SendMail, input);
}


// ── ocel ──

/** Emit an OCEL event (object-centric event log). */
export async function ocelEmitEvent(input: { eventJson: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.ocelEmitEvent, input);
}


// ── pubsub ──

/** Publish a message to a pubsub topic (at-least-once). */
export async function pubsubPublish(input: { topic: string; payload: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.pubsubPublish, input);
}

/** Pull up to N messages from a topic. */
export async function pubsubPull(input: { topic: string; maxMessages: number }): Promise<{ envelopesJson: string }> {
	return requireDispatcher().dispatch<{ envelopesJson: string }>(HOST_NSID.pubsubPull, input);
}


// ── secrets ──

/** Delete a secret value by key. */
export async function secretsDelete(input: { key: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.secretsDelete, input);
}

/** Retrieve a secret value by key from the host secret store. In-process capability (BindingTransport). */
export async function secretsGet(input: { key: string }): Promise<{ value?: string; found: boolean }> {
	return requireDispatcher().dispatch<{ value?: string; found: boolean }>(HOST_NSID.secretsGet, input);
}

/** Store a secret value under a key. */
export async function secretsSet(input: { key: string; value: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.secretsSet, input);
}


// ── storage ──

/** Get an object from the storage satellite. */
export async function storageGetObject(input: { bucket: string; key: string }): Promise<{ data: string }> {
	return requireDispatcher().dispatch<{ data: string }>(HOST_NSID.storageGetObject, input);
}

/** Put an object to the storage satellite (bucket/key addressed). */
export async function storagePutObject(input: { bucket: string; key: string; data: string; contentType: string }): Promise<{ etag: string }> {
	return requireDispatcher().dispatch<{ etag: string }>(HOST_NSID.storagePutObject, input);
}


// ── telemetry ──

/** Emit an OTEL metric sample. */
export async function telemetryEmitMetric(input: { name: string; value: number; tagsJson: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.telemetryEmitMetric, input);
}

/** Emit a structured log line (OTEL logs). */
export async function telemetryLog(input: { level: string; message: string; attributesJson: string }): Promise<{ ok: boolean }> {
	return requireDispatcher().dispatch<{ ok: boolean }>(HOST_NSID.telemetryLog, input);
}


// ── virtualActor ──

/** Invoke a method on a virtual actor (lifecycle-managed, reentrant). */
export async function virtualActorInvoke(input: { actorType: string; actorId: string; method: string; paramsJson: string }): Promise<{ resultJson: string }> {
	return requireDispatcher().dispatch<{ resultJson: string }>(HOST_NSID.virtualActorInvoke, input);
}
