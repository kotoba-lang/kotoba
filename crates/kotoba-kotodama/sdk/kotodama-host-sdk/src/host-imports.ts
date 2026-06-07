// host-imports.ts — host capability implementations backing the Lexicon dispatcher.
//
// This module is still shaped like the older host-import surface so existing app code
// can keep calling `sdk.hostImports.*`, but the canonical contract is now
// `00-contracts/lexicons/com/etzhayyim/host/*.json` plus generated/host-client.ts.
// The RequestCache dependency is a no-op compatibility stub.
// Writes call XrpcClient.dispatch() — failures tracked in failedWrites[] for outbox archive.

import type {
  HostImports,
  ActorCard,
  ActorCapability,
  AgentToolDef,
  AuthnContext,
  PolicyVerdict,
  SmtpConnectionInfo,
} from "./types.js";
import type { XrpcClient } from "./xrpc-client.js";
import { RequestCache } from "./request-cache.js";

const EMPTY_BYTES = new Uint8Array();
const EMPTY_JSON = "{}";
const EMPTY_ARRAY = "[]";

// pds is a direct PDS dispatch client.
export function createHostImports(
  env: Record<string, unknown>,
  pds: XrpcClient,
  appId?: string,
): HostImports & { _requestCache: RequestCache } {
  const requestCache = new RequestCache();
  return {
    _requestCache: requestCache,
    // ══════════════════════════════════════════════════════════════════
    // kotodama:core
    // ══════════════════════════════════════════════════════════════════

    configGet(key: string): string | undefined {
      const val = env[key];
      if (typeof val === "string") return val;
      return undefined;
    },

    logAppend(stream: string, subject: string, payload: Uint8Array): bigint {
      pds.dispatch({ type: "log-append", payload: { stream, subject, payload: Array.from(payload) } });
      return 0n;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:graph/vector-search
    // ══════════════════════════════════════════════════════════════════

    vectorSearch(_queryVector: number[], _limit: number, _labelFilter: string, _propFilter: string): string {
      return EMPTY_ARRAY;
    },

    vectorWrite(verticesJson: string, embeddingKey: string, dim: number): number {
      pds.dispatch({ type: "sql-exec", payload: { op: "vector-write", verticesJson, embeddingKey, dim } });
      return 0;
    },

    vectorCreateIndex(): string {
      pds.dispatch({ type: "sql-exec", payload: { op: "vector-create-index" } });
      return EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:auth/clerk
    // ══════════════════════════════════════════════════════════════════

    clerkVerifyToken(_token: string): Uint8Array {
      return EMPTY_BYTES;
    },

    clerkVerifyTokenWithAzp(_token: string, _azp: string): Uint8Array {
      return EMPTY_BYTES;
    },

    clerkAuthorize(_header: string, _orgId: string, _permission: string): Uint8Array {
      return EMPTY_BYTES;
    },

    clerkGetUser(_userId: string): Uint8Array {
      const cached = requestCache.get(`clerk:user:${_userId}`);
      return cached ? new TextEncoder().encode(cached) : EMPTY_BYTES;
    },

    clerkGetOrganization(_orgId: string): Uint8Array {
      const cached = requestCache.get(`clerk:org:${_orgId}`);
      return cached ? new TextEncoder().encode(cached) : EMPTY_BYTES;
    },

    clerkGetSession(_sessionId: string): Uint8Array {
      return EMPTY_BYTES;
    },

    clerkCheckPermission(_userId: string, _orgId: string, _permission: string): boolean {
      return false;
    },

    clerkCheckRole(_userId: string, _orgId: string, _role: string): boolean {
      return false;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:auth/authn
    // ══════════════════════════════════════════════════════════════════

    authnResolveContext(_authHeader: string, _orgHeader: string, _requestId: string): AuthnContext | null {
      return null;
    },

    authnVerifyToken(_token: string): Uint8Array {
      return EMPTY_BYTES;
    },

    authnEnsureActiveSession(_sessionId: string): void {},

    // ══════════════════════════════════════════════════════════════════
    // kotodama:auth/authz
    // ══════════════════════════════════════════════════════════════════

    authzEnforce(_orgId: string, _role: string, _permissions: string[], _requiredPermissions: string[], _requiredRoles: string[]): void {},

    // ══════════════════════════════════════════════════════════════════
    // kotodama:auth/crypto
    // ══════════════════════════════════════════════════════════════════

    cryptoSha256(data: Uint8Array): Uint8Array {
      // Use Web Crypto API synchronously via pre-computed cache, or return empty
      const cached = requestCache.getBinary(`sha256:${data.length}`);
      return cached ?? EMPTY_BYTES;
    },

    cryptoSha256Hex(_data: string): string {
      return "";
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:identity
    // ══════════════════════════════════════════════════════════════════

    identityRegister(card: ActorCard): void {
      pds.dispatch({ type: "identity-register", payload: card });
    },

    identityResolve(nanoid: string): string | null {
      return requestCache.get(`identity:${nanoid}`);
    },

    identityResolveAddress(address: string): string | null {
      return requestCache.get(`identity:addr:${address}`);
    },

    identityListActors(offset: number, limit: number): string {
      return requestCache.get(`identity:list:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:identity/capability
    // ══════════════════════════════════════════════════════════════════

    capabilityDeclare(cap: ActorCapability): void {
      pds.dispatch({ type: "capability-declare", payload: cap });
    },

    capabilityRevoke(id: string): void {
      pds.dispatch({ type: "capability-revoke", payload: { id } });
    },

    capabilityListOwn(): string {
      return requestCache.get("capability:own") ?? EMPTY_ARRAY;
    },

    capabilityAddDependency(depJson: string): void {
      pds.dispatch({ type: "dependency-declare", payload: depJson });
    },

    capabilityRemoveDependency(fromId: string, toId: string): void {
      pds.dispatch({ type: "dependency-remove", payload: { fromId, toId } });
    },

    capabilityListDependencies(capabilityId: string): string {
      return requestCache.get(`capability:deps:${capabilityId}`) ?? EMPTY_ARRAY;
    },

    capabilityDiscover(tag: string | null, status: string | null, offset: number, limit: number): string {
      return requestCache.get(`capability:discover:${tag}:${status}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:identity/dependency
    // ══════════════════════════════════════════════════════════════════

    dependencyDeclare(dep: string): void {
      pds.dispatch({ type: "dependency-declare", payload: dep });
    },

    dependencyRemove(pkg: string, iface: string): void {
      pds.dispatch({ type: "dependency-remove", payload: { pkg, iface } });
    },

    dependencyListOwn(): string {
      return requestCache.get("dependency:own") ?? EMPTY_ARRAY;
    },

    dependencyCheckAll(): string {
      return requestCache.get("dependency:check-all") ?? EMPTY_ARRAY;
    },

    dependencyCheck(pkg: string, iface: string): string {
      return requestCache.get(`dependency:check:${pkg}:${iface}`) ?? EMPTY_JSON;
    },

    dependencyListDependents(): string {
      return requestCache.get("dependency:dependents") ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:governance
    // ══════════════════════════════════════════════════════════════════

    governanceRegisterManifest(manifestJson: string): void {
      pds.dispatch({ type: "governance-manifest", payload: manifestJson });
    },

    governanceCheckPolicy(_command: string, _userId: string, _orgId: string): PolicyVerdict {
      return 0; // Allow
    },

    rbacDefineRole(roleJson: string): void {
      pds.dispatch({ type: "rbac-define-role", payload: roleJson });
    },

    rbacRemoveRole(roleId: string): void {
      pds.dispatch({ type: "rbac-remove-role", payload: { roleId } });
    },

    rbacListRoles(orgId: string): string {
      return requestCache.get(`rbac:roles:${orgId}`) ?? EMPTY_ARRAY;
    },

    rbacAssignRole(assignmentJson: string): void {
      pds.dispatch({ type: "rbac-assign-role", payload: assignmentJson });
    },

    rbacRevokeRole(userId: string, roleId: string, orgId: string): void {
      pds.dispatch({ type: "rbac-revoke-role", payload: { userId, roleId, orgId } });
    },

    rbacListUserRoles(userId: string, orgId: string): string {
      return requestCache.get(`rbac:user-roles:${userId}:${orgId}`) ?? EMPTY_ARRAY;
    },

    rbacCheckPermission(userId: string, orgId: string, permission: string): string {
      return requestCache.get(`rbac:check:${userId}:${orgId}:${permission}`) ?? EMPTY_JSON;
    },

    governanceGetConfig(key: string): string {
      return requestCache.get(`governance:config:${key}`) ?? "";
    },

    governanceSetConfig(key: string, value: string): void {
      pds.dispatch({ type: "governance-manifest", payload: { op: "set-config", key, value } });
    },

    traceabilityLink(sourceId: string, targetId: string, relationType: string): void {
      pds.dispatch({ type: "traceability-link", payload: { sourceId, targetId, relationType } });
    },

    traceabilityGetChain(entityId: string): string {
      return requestCache.get(`traceability:${entityId}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:consent
    // ══════════════════════════════════════════════════════════════════

    consentCreate(grantJson: string): string {
      pds.dispatch({ type: "consent-create", payload: grantJson });
      return EMPTY_JSON;
    },

    consentRevoke(consentId: string): void {
      pds.dispatch({ type: "consent-revoke", payload: { consentId } });
    },

    consentCheck(subjectDid: string, purpose: string, scope: string): string {
      return requestCache.get(`consent:check:${subjectDid}:${purpose}:${scope}`) ?? EMPTY_JSON;
    },

    consentList(subjectDid: string): string {
      return requestCache.get(`consent:list:${subjectDid}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:agent
    // ══════════════════════════════════════════════════════════════════

    agentRegisterTools(tools: AgentToolDef[]): void {
      pds.dispatch({ type: "agent-register-tools", payload: tools });
    },

    agentChat(userMessage: string, llmContextJson: string): string {
      // Push to write buffer for async murakumo call during flush.
      // Sync return is empty; result stored as com.etzhayyim.agent.chatResult record.
      pds.dispatch({ type: "agent-chat", payload: { userMessage, llmContextJson } });
      return EMPTY_JSON;
    },

    agentInvokeTool(_toolName: string, _inputJson: string): string {
      return EMPTY_JSON;
    },

    agentConverse(_messages: unknown[], _options: unknown): unknown {
      return { content: "", model: "", finishReason: "error" };
    },

    agentRoute(_inputJson: string): string {
      return EMPTY_ARRAY;
    },

    agentReact(_taskJson: string, _optionsJson: string): string {
      return EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:agent/skill
    // ══════════════════════════════════════════════════════════════════

    skillInstall(skillJson: string): void {
      pds.dispatch({ type: "skill-install", payload: skillJson });
    },

    skillUninstall(skillId: string): void {
      pds.dispatch({ type: "skill-uninstall", payload: { skillId } });
    },

    skillListOwn(): string {
      return requestCache.get("skill:own") ?? EMPTY_ARRAY;
    },

    skillGet(skillId: string): string | null {
      return requestCache.get(`skill:${skillId}`);
    },

    skillDiscover(_tag: string, _offset: number, _limit: number): string {
      return EMPTY_ARRAY;
    },

    skillInvokeTool(_skillId: string, _toolName: string, _inputJson: string): string {
      return EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:invoke/invoke
    // ══════════════════════════════════════════════════════════════════

    invoke(did: string, method: string, params: Uint8Array): Uint8Array {
      pds.dispatch({ type: "invoke", payload: { did, method, params: Array.from(params) } });
      return EMPTY_BYTES;
    },

    invokeStream(_did: string, _method: string, _params: Uint8Array): unknown {
      return null;
    },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:wrpc/stream (messaging)
    // ══════════════════════════════════════════════════════════════════

    createChannel(name: string, description: string, kind: string, inviteDids: string[]): string {
      pds.dispatch({ type: "create-channel", payload: { name, description, kind, inviteDids } });
      return EMPTY_JSON;
    },

    createProjectConvo(peerDid: string, kind: string, payload: Uint8Array, contentType: string): string {
      pds.dispatch({ type: "create-dm", payload: { peerDid, kind, payload: Array.from(payload), contentType } });
      return EMPTY_JSON;
    },

    sendProjectMessage(convoId: string, kind: string, payload: Uint8Array, contentType: string, replyTo: string | null, threadId: string | null): string {
      pds.dispatch({ type: "send-message", payload: { convoId, kind, payload: Array.from(payload), contentType, replyTo, threadId } });
      return EMPTY_JSON;
    },

    listEnvelopes(convoId: string, limit: number, beforeRkey: string | null): string {
      return requestCache.get(`messaging:envelopes:${convoId}:${limit}:${beforeRkey}`) ?? EMPTY_ARRAY;
    },

    getThread(convoId: string, rootRkey: string): string {
      return requestCache.get(`messaging:thread:${convoId}:${rootRkey}`) ?? EMPTY_ARRAY;
    },

    searchMessages(query: string, convoId: string | null, limit: number): string {
      return requestCache.get(`messaging:search:${query}:${convoId}:${limit}`) ?? EMPTY_ARRAY;
    },

    getUnread(): string {
      return requestCache.get("messaging:unread") ?? EMPTY_JSON;
    },

    markRead(convoId: string, lastRkey: string): void {
      pds.dispatch({ type: "mark-read", payload: { convoId, lastRkey } });
    },

    updatePresence(status: string, statusText: string): void {
      pds.dispatch({ type: "update-presence", payload: { status, statusText } });
    },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:convo/convo (conversation merged)
    // ══════════════════════════════════════════════════════════════════

    conversationCreateSession(topic: string, participantsJson: string): string {
      pds.dispatch({ type: "convo-create-session", payload: { topic, participantsJson } });
      return EMPTY_JSON;
    },

    conversationSendMessage(sessionId: string, content: string): string {
      pds.dispatch({ type: "convo-send-message", payload: { sessionId, content } });
      return EMPTY_JSON;
    },

    conversationGetHistory(sessionId: string): string {
      return requestCache.get(`conversation:history:${sessionId}`) ?? EMPTY_ARRAY;
    },

    conversationGetSession(sessionId: string): string {
      return requestCache.get(`conversation:session:${sessionId}`) ?? EMPTY_JSON;
    },

    conversationListSessions(): string {
      return requestCache.get("conversation:sessions") ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:signal/signal (crypto primitives)
    // ══════════════════════════════════════════════════════════════════

    signalGenerateIdentity(): Uint8Array { return EMPTY_BYTES; },
    signalGenerateSignedPrekey(_identityCbor: Uint8Array, _keyId: number): Uint8Array { return EMPTY_BYTES; },
    signalGenerateOneTimePrekey(_keyId: number): Uint8Array { return EMPTY_BYTES; },
    signalBuildPreKeyBundle(_identityCbor: Uint8Array, _spkJson: Uint8Array, _opkJson: Uint8Array | null): Uint8Array { return EMPTY_BYTES; },
    signalX3dhInitiate(_senderIkCbor: Uint8Array, _bundleJson: Uint8Array): Uint8Array { return EMPTY_BYTES; },
    signalX3dhRespond(_recipientIkCbor: Uint8Array, _spkJson: Uint8Array, _opkJson: Uint8Array | null, _initMsgJson: Uint8Array): Uint8Array { return EMPTY_BYTES; },
    signalRatchetInitSender(_x3dhResultJson: Uint8Array, _recipientRatchetPublic: Uint8Array): Uint8Array { return EMPTY_BYTES; },
    signalRatchetInitReceiver(_x3dhResultJson: Uint8Array, _ourRatchetSecret: Uint8Array): Uint8Array { return EMPTY_BYTES; },
    signalRatchetEncrypt(_sessionCbor: Uint8Array, plaintext: Uint8Array): Uint8Array { return plaintext; },
    signalRatchetDecrypt(_sessionCbor: Uint8Array, msgJson: Uint8Array): Uint8Array { return msgJson; },
    signalGroupInitSender(_groupId: string, _ourDid: string): Uint8Array { return EMPTY_BYTES; },
    signalGroupProcessDistribution(_sessionJson: Uint8Array, _distJson: Uint8Array): Uint8Array { return EMPTY_BYTES; },
    signalGroupEncrypt(_sessionJson: Uint8Array, plaintext: Uint8Array): Uint8Array { return plaintext; },
    signalGroupDecrypt(_sessionJson: Uint8Array, msgJson: Uint8Array): Uint8Array { return msgJson; },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:signal/session (managed sessions)
    // ══════════════════════════════════════════════════════════════════

    signalSessionGroupGetOrCreate(_groupId: string, _memberDids: string[]): { session: Uint8Array; distribution: Uint8Array } {
      return { session: EMPTY_BYTES, distribution: EMPTY_BYTES };
    },

    signalSessionGroupEncrypt(_groupId: string, plaintext: Uint8Array): Uint8Array { return plaintext; },
    signalSessionGroupDecrypt(_groupId: string, ciphertext: Uint8Array, _senderDid: string): Uint8Array { return ciphertext; },
    signalSessionGroupAddMember(_groupId: string, _memberDid: string): Uint8Array { return EMPTY_BYTES; },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:yata/yata
    // ══════════════════════════════════════════════════════════════════

    queryG(label: string, matchJson: string, returnClause: string, limit: number): string {
      const cached = requestCache.get(RequestCache.graphKey(label, matchJson, returnClause, limit));
      return cached ?? EMPTY_ARRAY;
    },

    queryGExec(query: string, paramsJson: string): bigint {
      pds.dispatch({ type: "query-graph-exec", payload: { query, paramsJson } });
      return 0n;
    },

    graphExec(query: string, paramsJson: string): string {
      const cached = requestCache.get(RequestCache.sqlKey(query, paramsJson));
      return cached ?? '{"columns":[],"rows":[]}';
    },

    // ══════════════════════════════════════════════════════════════════
    // com-atproto:identity/identity (AT Protocol lexicon aligned)
    // ══════════════════════════════════════════════════════════════════

    comAtprotoIdentityCreate(path: string, documentJson: string): string {
      pds.dispatch({ type: "com.atproto.identity.create", payload: { path, documentJson } });
      const nanoid = appId || (env["PERFORMER_ID"] as string) || (env["APP_NANOID"] as string) || "";
      if (nanoid && path) {
        return `did:web:${nanoid}.etzhayyim.com:${path}`;
      }
      return "";
    },

    comAtprotoIdentityResolve(did: string): string {
      return requestCache.get(`did:resolve:${did}`) ?? EMPTY_JSON;
    },

    comAtprotoIdentityUpdate(did: string, patchesJson: string): void {
      pds.dispatch({ type: "com.atproto.identity.update", payload: { did, patchesJson } });
    },

    comAtprotoIdentityDeactivate(did: string): void {
      pds.dispatch({ type: "com.atproto.identity.deactivate", payload: { did } });
    },

    comAtprotoIdentityList(): string {
      return requestCache.get("did:list") ?? EMPTY_ARRAY;
    },

    comAtprotoIdentityRotateKey(did: string, keyId: string): string {
      pds.dispatch({ type: "com.atproto.identity.rotateKey", payload: { did, keyId } });
      return "";
    },

    comAtprotoIdentityCreateRecord(did: string, collection: string, recordJson: string): string {
      pds.dispatch({ type: "com.atproto.identity.createRecord", payload: { did, collection, recordJson } });
      return "";
    },

    comAtprotoIdentityUpdateRecord(did: string, collection: string, rkey: string, recordJson: string): void {
      pds.dispatch({ type: "com.atproto.identity.updateRecord", payload: { did, collection, rkey, recordJson } });
    },

    comAtprotoIdentityDeleteRecord(did: string, collection: string, rkey: string): void {
      pds.dispatch({ type: "com.atproto.identity.deleteRecord", payload: { did, collection, rkey } });
    },

    // ══════════════════════════════════════════════════════════════════
    // app-bsky:graph/graph
    // ══════════════════════════════════════════════════════════════════

    followFollow(targetNanoid: string): string {
      pds.dispatch({ type: "social-graph-follow", payload: { targetNanoid } });
      return "";
    },

    followUnfollow(targetNanoid: string): void {
      pds.dispatch({ type: "social-graph-unfollow", payload: { targetNanoid } });
    },

    followSetMuted(targetNanoid: string, muted: boolean): void {
      pds.dispatch({ type: "social-graph-mute-actor", payload: { targetNanoid, muted } });
    },

    followListFollowing(offset: number, limit: number): string {
      return requestCache.get(`follow:following:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    followListFollowers(offset: number, limit: number): string {
      return requestCache.get(`follow:followers:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    followCountFollowers(): bigint {
      const cached = requestCache.get("follow:count-followers");
      return cached ? BigInt(cached) : 0n;
    },

    followCountFollowing(): bigint {
      const cached = requestCache.get("follow:count-following");
      return cached ? BigInt(cached) : 0n;
    },

    followReact(targetNanoid: string, targetCollection: string, targetRkey: string, kind: number): string {
      pds.dispatch({ type: "social-graph-react", payload: { targetNanoid, targetCollection, targetRkey, kind } });
      return "";
    },

    followUnreact(targetNanoid: string, targetCollection: string, targetRkey: string): void {
      pds.dispatch({ type: "social-graph-unreact", payload: { targetNanoid, targetCollection, targetRkey } });
    },

    followGetReactions(collection: string, rkey: string, offset: number, limit: number): string {
      return requestCache.get(`follow:reactions:${collection}:${rkey}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    followPullFeed(limit: number): string {
      return requestCache.get(`follow:pull-feed:${limit}`) ?? EMPTY_ARRAY;
    },

    followAckFeed(upToTs: string): void {
      pds.dispatch({ type: "social-graph-ack-feed", payload: { upToTs } });
    },

    followGetEngagement(): string {
      return requestCache.get("follow:engagement") ?? '{"likes":0,"loves":0,"score":0,"delta":0}';
    },

    followLeaderboard(limit: number): string {
      return requestCache.get(`follow:leaderboard:${limit}`) ?? EMPTY_ARRAY;
    },

    followListFollowRequests(direction: string, status: string | null, offset: number, limit: number): string {
      return requestCache.get(`follow:requests:${direction}:${status}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    followApproveFollowRequest(requestId: string): string {
      pds.dispatch({ type: "social-graph-approve-request", payload: { requestId } });
      return "";
    },

    followRejectFollowRequest(requestId: string): void {
      pds.dispatch({ type: "social-graph-reject-request", payload: { requestId } });
    },

    followApproveAllFollowRequests(): bigint {
      pds.dispatch({ type: "social-graph-approve-all-requests", payload: {} });
      return 0n;
    },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:governance/governance
    // ══════════════════════════════════════════════════════════════════

    wGovernanceCheckAccess(did: string, lexicon: string, action: string): string {
      return requestCache.get(`w-governance:check:${did}:${lexicon}:${action}`) ?? '{"allowed":true}';
    },

    wGovernanceGetPolicy(did: string): string {
      return requestCache.get(`w-governance:policy:${did}`) ?? EMPTY_JSON;
    },

    wGovernanceRegisterPolicy(lexicon: string, policyJson: string): void {
      pds.dispatch({ type: "governance-register-policy", payload: { lexicon, policyJson } });
    },

    wGovernanceListPolicies(): string {
      return requestCache.get("w-governance:policies") ?? EMPTY_ARRAY;
    },

    wGovernanceRegisterMethodPolicy(method: string, policyJson: string): void {
      pds.dispatch({ type: "governance-register-method-policy", payload: { method, policyJson } });
    },

    wGovernanceSetActorSensitivity(sensitivity: string): void {
      pds.dispatch({ type: "governance-set-actor-sensitivity", payload: { sensitivity } });
    },

    wGovernanceGetActorSensitivity(): string {
      return requestCache.get("w-governance:sensitivity") ?? '"public"';
    },

    wGovernanceResolveActorVisibility(targetDid: string): string {
      return requestCache.get(`w-governance:visibility:${targetDid}`) ?? EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // com-atproto:label/label
    // ══════════════════════════════════════════════════════════════════

    contentLabelCreate(labelJson: string): string {
      pds.dispatch({ type: "content-label-create", payload: labelJson });
      return "";
    },

    contentLabelQuery(filterJson: string): string {
      return requestCache.get(`content-label:query:${filterJson}`) ?? EMPTY_ARRAY;
    },

    contentLabelSetPref(labelValue: string, visibility: number): void {
      pds.dispatch({ type: "content-label-set-pref", payload: { labelValue, visibility } });
    },

    contentLabelGetPrefs(): string {
      return requestCache.get("content-label:prefs") ?? EMPTY_JSON;
    },

    contentLabelDeclareLabeler(labelerJson: string): string {
      pds.dispatch({ type: "content-label-declare-labeler", payload: labelerJson });
      return "";
    },

    contentLabelGetLabeler(labelerDid: string): string {
      return requestCache.get(`content-label:labeler:${labelerDid}`) ?? EMPTY_JSON;
    },

    contentLabelSubscribe(labelerDid: string): void {
      pds.dispatch({ type: "content-label-subscribe", payload: { labelerDid } });
    },

    contentLabelUnsubscribe(labelerDid: string): void {
      pds.dispatch({ type: "content-label-unsubscribe", payload: { labelerDid } });
    },

    contentLabelListSubscribed(): string {
      return requestCache.get("content-label:subscribed") ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // etzhayyim:smtp/smtp
    // ══════════════════════════════════════════════════════════════════

    smtpConnect(provider: string, authCode: string, redirectUri: string, userId: string, orgId: string): SmtpConnectionInfo {
      pds.dispatch({ type: "smtp-connect", payload: { provider, authCode, redirectUri, userId, orgId } });
      return { provider, email: "", displayName: "", connected: false };
    },

    smtpDisconnect(provider: string, userId: string, orgId: string): void {
      pds.dispatch({ type: "smtp-disconnect", payload: { provider, userId, orgId } });
    },

    smtpStatus(_provider: string, _userId: string, _orgId: string): Uint8Array {
      return EMPTY_BYTES;
    },

    smtpSendTransactional(fromEmail: string, fromName: string, to: string[], subject: string, bodyText: string, bodyHtml: string): string {
      pds.dispatch({ type: "smtp-send", payload: { fromEmail, fromName, to, subject, bodyText, bodyHtml } });
      return "";
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:storage
    // ══════════════════════════════════════════════════════════════════

    ipfsPublish(data: Uint8Array, contentType: string): string {
      pds.dispatch({ type: "ipfs-publish", payload: { data: Array.from(data), contentType } });
      return "";
    },

    ipfsPublishUrl(data: Uint8Array, contentType: string): string {
      pds.dispatch({ type: "ipfs-publish", payload: { data: Array.from(data), contentType, returnUrl: true } });
      return "";
    },

    ipfsGatewayUrl(cid: string): string {
      return `https://ipfs.etzhayyim.com/ipfs/${cid}`;
    },

    storagePutObject(bucket: string, key: string, data: Uint8Array, contentType: string): string {
      pds.dispatch({ type: "storage-put", payload: { bucket, key, data: Array.from(data), contentType } });
      return "";
    },

    storageGetObject(bucket: string, key: string): Uint8Array {
      return requestCache.getBinary(`storage:${bucket}:${key}`) ?? EMPTY_BYTES;
    },

    storageDeleteObject(bucket: string, key: string): void {
      pds.dispatch({ type: "storage-delete", payload: { bucket, key } });
    },

    cdnUpload(subdomain: string, path: string, data: Uint8Array, contentType: string): string {
      pds.dispatch({ type: "cdn-upload", payload: { subdomain, path, data: Array.from(data), contentType } });
      return "";
    },

    cdnFetchUpload(subdomain: string, sourceUrl: string, path: string, contentType: string): string {
      pds.dispatch({ type: "cdn-fetch-upload", payload: { subdomain, sourceUrl, path, contentType } });
      return "";
    },

    cdnDelete(subdomain: string, path: string): void {
      pds.dispatch({ type: "cdn-delete", payload: { subdomain, path } });
    },

    cdnPublicUrl(subdomain: string, path: string): string {
      return `https://cdn.etzhayyim.com/${subdomain}/${path}`;
    },

    cdnUploadImage(subdomain: string, path: string, data: Uint8Array, optionsJson: string): string {
      pds.dispatch({ type: "cdn-upload-image", payload: { subdomain, path, data: Array.from(data), optionsJson } });
      return "";
    },

    staticSitePut(path: string, data: Uint8Array, contentType: string): bigint {
      pds.dispatch({ type: "static-site-put", payload: { path, data: Array.from(data), contentType } });
      return BigInt(data.length);
    },

    staticSiteDelete(path: string): void {
      pds.dispatch({ type: "static-site-delete", payload: { path } });
    },

    staticSiteListFiles(prefix: string): string[] {
      const cached = requestCache.get(`static-site:files:${prefix}`);
      return cached ? JSON.parse(cached) : [];
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:workflow
    // ══════════════════════════════════════════════════════════════════

    workflowStart(name: string, inputJson: string, optionsJson: string): string {
      pds.dispatch({ type: "workflow-start", payload: { name, inputJson, optionsJson } });
      return EMPTY_JSON;
    },

    workflowSignal(workflowId: string, signalName: string, payload: string): void {
      pds.dispatch({ type: "workflow-signal", payload: { workflowId, signalName, payload } });
    },

    workflowQuery(workflowId: string, queryName: string, payload: string): string {
      return requestCache.get(`workflow:query:${workflowId}:${queryName}`) ?? EMPTY_JSON;
    },

    workflowGet(workflowId: string): string {
      return requestCache.get(`workflow:${workflowId}`) ?? EMPTY_JSON;
    },

    workflowPause(workflowId: string): void {
      pds.dispatch({ type: "workflow-pause", payload: { workflowId } });
    },

    workflowResume(workflowId: string): void {
      pds.dispatch({ type: "workflow-resume", payload: { workflowId } });
    },

    workflowTerminate(workflowId: string): void {
      pds.dispatch({ type: "workflow-terminate", payload: { workflowId } });
    },

    workflowPurge(workflowId: string): void {
      pds.dispatch({ type: "workflow-purge", payload: { workflowId } });
    },

    workflowRaiseEvent(workflowId: string, eventName: string, payload: string): void {
      pds.dispatch({ type: "workflow-raise-event", payload: { workflowId, eventName, payload } });
    },

    workflowCreateTimer(workflowId: string, name: string, fireAtMs: bigint): void {
      pds.dispatch({ type: "workflow-create-timer", payload: { workflowId, name, fireAtMs: Number(fireAtMs) } });
    },

    activitySchedule(name: string, inputJson: string, optionsJson: string): string {
      pds.dispatch({ type: "activity-schedule", payload: { name, inputJson, optionsJson } });
      return EMPTY_JSON;
    },

    activityHeartbeat(activityId: string, details: string): void {
      pds.dispatch({ type: "activity-heartbeat", payload: { activityId, details } });
    },

    activitySpawnParallel(activitiesJson: string): string {
      pds.dispatch({ type: "activity-spawn-parallel", payload: activitiesJson });
      return EMPTY_JSON;
    },

    activityAwaitAll(batchId: string, _timeoutMs: bigint): string {
      return requestCache.get(`activity:batch:${batchId}`) ?? EMPTY_ARRAY;
    },

    dagSubmit(dagJson: string): string {
      pds.dispatch({ type: "dag-submit", payload: dagJson });
      return EMPTY_JSON;
    },

    dagStatus(dagId: string): string {
      return requestCache.get(`dag:${dagId}`) ?? EMPTY_JSON;
    },

    dagCancel(dagId: string): void {
      pds.dispatch({ type: "dag-cancel", payload: { dagId } });
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:actor
    // ══════════════════════════════════════════════════════════════════

    timerSet(name: string, delayMs: bigint, callbackData: string): void {
      pds.dispatch({ type: "timer-set", payload: { name, delayMs: Number(delayMs), callbackData } });
    },

    timerCancel(name: string): void {
      pds.dispatch({ type: "timer-cancel", payload: { name } });
    },

    timerList(): string {
      return requestCache.get("timer:list") ?? EMPTY_ARRAY;
    },

    reminderSet(name: string, dueMs: bigint, period: bigint, data: string): void {
      pds.dispatch({ type: "reminder-set", payload: { name, dueMs: Number(dueMs), period: Number(period), data } });
    },

    reminderGet(name: string): string | null {
      return requestCache.get(`reminder:${name}`);
    },

    reminderDelete(name: string): void {
      pds.dispatch({ type: "reminder-delete", payload: { name } });
    },

    reminderList(): string {
      return requestCache.get("reminder:list") ?? EMPTY_ARRAY;
    },

    actorStateGet(key: string): string | null {
      return requestCache.get(`actor-state:${key}`);
    },

    actorStateSet(key: string, value: string): void {
      pds.dispatch({ type: "actor-state-set", payload: { key, value } });
    },

    actorStateDelete(key: string): void {
      pds.dispatch({ type: "actor-state-delete", payload: { key } });
    },

    actorStateList(prefix: string): string {
      return requestCache.get(`actor-state:list:${prefix}`) ?? EMPTY_ARRAY;
    },

    lockTryLock(key: string, ttlMs: bigint): boolean {
      pds.dispatch({ type: "lock-try", payload: { key, ttlMs: Number(ttlMs) } });
      return true; // optimistic
    },

    lockUnlock(key: string): void {
      pds.dispatch({ type: "lock-unlock", payload: { key } });
    },

    lockRenew(key: string, ttlMs: bigint): boolean {
      pds.dispatch({ type: "lock-renew", payload: { key, ttlMs: Number(ttlMs) } });
      return true;
    },

    virtualActorRegister(actorType: string, optionsJson: string): void {
      pds.dispatch({ type: "virtual-actor-register", payload: { actorType, optionsJson } });
    },

    virtualActorInvoke(actorType: string, actorId: string, method: string, paramsJson: string): string {
      return requestCache.get(`virtual-actor:${actorType}:${actorId}:${method}`) ?? EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:telemetry
    // ══════════════════════════════════════════════════════════════════

    telemetryEmitMetric(name: string, value: number, tagsJson: string): void {
      pds.dispatch({ type: "telemetry-metric", payload: { name, value, tagsJson } });
    },

    telemetryStartSpan(name: string, attributesJson: string): string {
      pds.dispatch({ type: "telemetry-start-span", payload: { name, attributesJson } });
      return "";
    },

    telemetryEndSpan(spanId: string, statusJson: string): void {
      pds.dispatch({ type: "telemetry-end-span", payload: { spanId, statusJson } });
    },

    telemetryLog(level: string, message: string, attributesJson: string): void {
      pds.dispatch({ type: "telemetry-log", payload: { level, message, attributesJson } });
    },

    accessLogRecord(entryJson: string): void {
      pds.dispatch({ type: "access-log-record", payload: entryJson });
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:audit
    // ══════════════════════════════════════════════════════════════════

    auditEmit(category: string, action: string, resourceId: string, outcome: string, detailsJson: string): bigint {
      pds.dispatch({
        type: "anomaly-emit-event",
        payload: { category, action, resourceId, outcome, detailsJson },
      });
      return 0n;
    },

    auditQuery(category: string, actorDid: string, sinceUnixMs: bigint, offset: number, limit: number): string {
      return requestCache.get(`audit:${category}:${actorDid}:${sinceUnixMs}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    auditCount(category: string, actorDid: string, sinceUnixMs: bigint): bigint {
      const cached = requestCache.get(`audit:count:${category}:${actorDid}:${sinceUnixMs}`);
      return cached ? BigInt(cached) : 0n;
    },

    ocelEmitEvent(eventJson: string): void {
      let payload: unknown = { raw: eventJson };
      try { payload = JSON.parse(eventJson); } catch { /* keep raw string envelope */ }
      pds.dispatch({ type: "anomaly-emit-event", payload });
    },

    ocelQuery(filterJson: string): string {
      return requestCache.get(`ocel:${filterJson}`) ?? EMPTY_ARRAY;
    },

    anomalyDetect(_metricJson: string): string {
      return EMPTY_JSON;
    },

    anomalyReport(anomalyJson: string): void {
      pds.dispatch({ type: "anomaly-report", payload: anomalyJson });
    },

    incidentCreate(incidentJson: string): string {
      pds.dispatch({ type: "incident-create", payload: incidentJson });
      return EMPTY_JSON;
    },

    incidentUpdate(incidentId: string, updateJson: string): void {
      pds.dispatch({ type: "incident-update", payload: { incidentId, updateJson } });
    },

    incidentResolve(incidentId: string, resolutionJson: string): void {
      pds.dispatch({ type: "incident-resolve", payload: { incidentId, resolutionJson } });
    },

    incidentGet(incidentId: string): string {
      return requestCache.get(`incident:${incidentId}`) ?? EMPTY_JSON;
    },

    incidentList(filterJson: string): string {
      return requestCache.get(`incident:list:${filterJson}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:pubsub
    // ══════════════════════════════════════════════════════════════════

    pubsubPublish(topic: string, payload: Uint8Array): void {
      pds.dispatch({ type: "pubsub-publish", payload: { topic, payload: Array.from(payload) } });
    },

    pubsubPull(topic: string, maxMessages: number): string {
      return requestCache.get(`pubsub:${topic}:${maxMessages}`) ?? EMPTY_ARRAY;
    },

    pubsubAck(topic: string, messageIds: string[]): void {
      pds.dispatch({ type: "pubsub-ack", payload: { topic, messageIds } });
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:secrets
    // ══════════════════════════════════════════════════════════════════

    secretsGet(key: string): string | null {
      return requestCache.get(`secrets:${key}`);
    },

    secretsSet(key: string, value: string): void {
      pds.dispatch({ type: "secrets-set", payload: { key, value } });
    },

    secretsDelete(key: string): void {
      pds.dispatch({ type: "secrets-delete", payload: { key } });
    },

    vaultGet(path: string): string | null {
      return requestCache.get(`vault:${path}`);
    },

    vaultPut(path: string, value: string): void {
      pds.dispatch({ type: "vault-put", payload: { path, value } });
    },

    vaultDelete(path: string): void {
      pds.dispatch({ type: "vault-delete", payload: { path } });
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:forms
    // ══════════════════════════════════════════════════════════════════

    formsCreate(schemaJson: string): string {
      pds.dispatch({ type: "forms-create", payload: schemaJson });
      return EMPTY_JSON;
    },

    formsValidate(formId: string, dataJson: string): string {
      return requestCache.get(`forms:validate:${formId}`) ?? '{"valid":true}';
    },

    formsGet(formId: string): string {
      return requestCache.get(`forms:${formId}`) ?? EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:bpmn
    // ══════════════════════════════════════════════════════════════════

    bpmnDeploy(bpmnXml: string): string {
      pds.dispatch({ type: "bpmn-deploy", payload: bpmnXml });
      return EMPTY_JSON;
    },

    bpmnStartProcess(processId: string, variablesJson: string): string {
      pds.dispatch({ type: "bpmn-start-process", payload: { processId, variablesJson } });
      return EMPTY_JSON;
    },

    bpmnCompleteTask(taskId: string, variablesJson: string): void {
      pds.dispatch({ type: "bpmn-complete-task", payload: { taskId, variablesJson } });
    },

    bpmnGetProcess(instanceId: string): string {
      return requestCache.get(`bpmn:process:${instanceId}`) ?? EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:dmn
    // ══════════════════════════════════════════════════════════════════

    dmnEvaluate(decisionId: string, contextJson: string): string {
      return requestCache.get(`dmn:evaluate:${decisionId}`) ?? EMPTY_JSON;
    },

    dmnDeploy(dmnXml: string): string {
      pds.dispatch({ type: "dmn-deploy", payload: dmnXml });
      return EMPTY_JSON;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:dm2
    // ══════════════════════════════════════════════════════════════════

    dm2RegisterPerformer(performerJson: string): void {
      pds.dispatch({ type: "dm2-register-performer", payload: performerJson });
    },

    dm2ResolvePerformer(id: string): string | null {
      return requestCache.get(`dm2:performer:${id}`);
    },

    dm2ListPerformers(kind: string, offset: number, limit: number): string {
      return requestCache.get(`dm2:performers:${kind}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    dm2GetParent(id: string): string | null {
      return requestCache.get(`dm2:parent:${id}`);
    },

    dm2ListChildren(id: string, offset: number, limit: number): string {
      return requestCache.get(`dm2:children:${id}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    dm2ListSiblings(id: string, offset: number, limit: number): string {
      return requestCache.get(`dm2:siblings:${id}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    dm2ListRelationships(id: string, relation: string, offset: number, limit: number): string {
      return requestCache.get(`dm2:relationships:${id}:${relation}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    dm2ListDependencies(id: string, dependencyKind: string, offset: number, limit: number): string {
      return requestCache.get(`dm2:dependencies:${id}:${dependencyKind}:${offset}:${limit}`) ?? EMPTY_ARRAY;
    },

    dm2ResolveLineage(id: string): string {
      return requestCache.get(`dm2:lineage:${id}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:contract
    // ══════════════════════════════════════════════════════════════════

    contractCreateAgreement(agreementJson: string): string {
      pds.dispatch({ type: "contract-create-agreement", payload: agreementJson });
      return EMPTY_JSON;
    },

    contractGetAgreement(agreementId: string): string {
      return requestCache.get(`contract:agreement:${agreementId}`) ?? EMPTY_JSON;
    },

    contractListAgreements(filterJson: string): string {
      return requestCache.get(`contract:agreements:${filterJson}`) ?? EMPTY_ARRAY;
    },

    contractRegister(registrationJson: string): void {
      pds.dispatch({ type: "contract-register", payload: registrationJson });
    },

    contractLookup(query: string): string {
      return requestCache.get(`contract:lookup:${query}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:browser
    // ══════════════════════════════════════════════════════════════════

    scraperFetchHtml(_url: string): string { return ""; },
    scraperExtractText(_html: string, _cssSelector: string): string[] { return []; },
    scraperExtractTable(_html: string, _cssSelector: string): string[][] { return []; },
    scraperExtractLinks(_html: string, _cssSelector: string): [string, string][] { return []; },
    scraperExtractAttr(_html: string, _cssSelector: string, _attrName: string): string[] { return []; },
    analyzerExtractStructured(_html: string, _schemaJson: string): string { return EMPTY_JSON; },
    analyzerAnalyze(_prompt: string, _context: string): string { return EMPTY_JSON; },

    automationOpenSession(): string {
      pds.dispatch({ type: "automation-open-session", payload: {} });
      return "";
    },

    automationCloseSession(sessionId: string): void {
      pds.dispatch({ type: "automation-close-session", payload: { sessionId } });
    },

    automationNavigate(sessionId: string, url: string): void {
      pds.dispatch({ type: "automation-navigate", payload: { sessionId, url } });
    },

    automationClick(sessionId: string, cssSelector: string): void {
      pds.dispatch({ type: "automation-click", payload: { sessionId, cssSelector } });
    },

    automationTypeText(sessionId: string, cssSelector: string, text: string): void {
      pds.dispatch({ type: "automation-type-text", payload: { sessionId, cssSelector, text } });
    },

    automationSelectOption(sessionId: string, cssSelector: string, value: string): void {
      pds.dispatch({ type: "automation-select-option", payload: { sessionId, cssSelector, value } });
    },

    automationWaitForSelector(_sessionId: string, _cssSelector: string, _waitMs: number): void {},
    automationWaitForNavigation(_sessionId: string, _waitMs: number): void {},
    automationCurrentUrl(_sessionId: string): string { return ""; },
    automationPageHtml(_sessionId: string): string { return ""; },
    automationScreenshot(_sessionId: string): string { return ""; },
    automationQueryText(_sessionId: string, _cssSelector: string): string[] { return []; },
    automationIsVisible(_sessionId: string, _cssSelector: string): boolean { return false; },
    automationEvalJs(_sessionId: string, _expression: string): string { return ""; },

    pipelineScrapeAndAnalyze(_url: string, _schemaJson: string): string { return EMPTY_JSON; },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:cloudflare/kv
    // ══════════════════════════════════════════════════════════════════

    kvGet(key: string): string | null {
      return requestCache.get(`kv:${key}`);
    },

    kvPut(key: string, value: string, ttlSeconds: number): void {
      pds.dispatch({ type: "kv-put", payload: { key, value, ttlSeconds } });
    },

    kvDelete(key: string): void {
      pds.dispatch({ type: "kv-delete", payload: { key } });
    },

    kvList(prefix: string, limit: number): string {
      return requestCache.get(`kv:list:${prefix}:${limit}`) ?? EMPTY_ARRAY;
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:cloudflare/r2
    // ══════════════════════════════════════════════════════════════════

    r2Get(key: string): Uint8Array | null {
      return requestCache.getBinary(`r2:${key}`);
    },

    r2Put(key: string, data: Uint8Array, contentType: string): void {
      pds.dispatch({ type: "r2-put", payload: { key, data: Array.from(data), contentType } });
    },

    r2Delete(key: string): void {
      pds.dispatch({ type: "r2-delete", payload: { key } });
    },

    r2List(prefix: string, limit: number): string {
      return requestCache.get(`r2:list:${prefix}:${limit}`) ?? EMPTY_ARRAY;
    },

    r2Head(key: string): string | null {
      return requestCache.get(`r2:head:${key}`);
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:cloudflare/queue
    // ══════════════════════════════════════════════════════════════════

    queueSend(queueName: string, message: Uint8Array): void {
      pds.dispatch({ type: "queue-send", payload: { queueName, message: Array.from(message) } });
    },

    queueSendBatch(queueName: string, messages: Uint8Array[]): void {
      pds.dispatch({ type: "queue-send-batch", payload: { queueName, messages: messages.map(m => Array.from(m)) } });
    },

    // ══════════════════════════════════════════════════════════════════
    // kotodama:web3/wallet
    // ══════════════════════════════════════════════════════════════════

    walletSign(_data: Uint8Array): Uint8Array { return EMPTY_BYTES; },
    walletVerify(_data: Uint8Array, _signature: Uint8Array, _publicKey: Uint8Array): boolean { return false; },
    walletGetAddress(): string { return ""; },

  };
}
