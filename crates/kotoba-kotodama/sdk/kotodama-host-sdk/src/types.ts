// types.ts — Canonical type definitions for kotodama host SDK.
// Single Source of Truth — replaces duplicated types across Go/Rust/TS/Python guest SDKs.
// These types back the TS Native runtime and the legacy host-import compatibility surface.

// ── Write buffer / request cache (F-Plan task 4, inlined from @etzhayyim/kotodama-host-contract) ──
// These were previously in 00-contracts/kotodama-host-contract/ as a 12-line stub package.
// Inlined 2026-04-13 to eliminate the workspace dependency. The original package is archived.

export interface WriteBufferEntry {
  type: string;
  payload?: unknown;
}

export interface WriteBuffer {
  push(entry: WriteBufferEntry): void;
}

// Note: `RequestCache` class lives in ./request-cache.ts; this is the interface shape.
export interface RequestCacheShape {
  get(key: string): string | undefined;
}

// ── HTTP Handler types ──────────────────────────────────────────────────

export interface Request {
  method: string;
  url: string;
  headers: [string, string][];
  body: Uint8Array;
}

export interface Response {
  status: number;
  headers: [string, string][];
  body: Uint8Array;
}

// ── AT Protocol commit types ────────────────────────────────────────────
// Flattened AT Protocol subscribeRepos#commit operation.

export interface ComAtprotoSyncSubscribeReposCommit {
  seq: bigint;
  repo: string;
  collection: string;
  rkey: string;
  action: string;
  cid: string | null;
  rev: string | null;
  time: string;
}


// ── App Declaration types ───────────────────────────────────────────────

export interface AppDef {
  id: string;
  name: string;
  description?: string;
  agent?: AgentConfig;
}

export interface AgentConfig {
  systemPrompt: string;
  model: string;
}

export interface AppContext {
  orgId: string;
  userId: string;
  actorId: string;
  convoId: string;
  appId: string;
  now: string;
}

export interface RLSMeta {
  'orgId': string;
  'userId': string;
  'actorId': string;
  'createdAt': string;
  'updatedAt': string;
}

// ── Auth types ──────────────────────────────────────────────────────────

export interface IdentityClaims {
  'userId': string;
  'sessionId': string;
  orgId?: string;
  orgRole?: string;
  'orgPermissions': string[];
  'issuedAtMs': number;
  'expiresAtMs': number;
  issuer: string;
  'authorizedParties': string[];
  email?: string;
}

export interface AuthnContext {
  claims: IdentityClaims;
  targetOrgId?: string;
  requestId?: string;
}

// ── Governance types ────────────────────────────────────────────────────

export const enum RACIRole {
  Responsible = 0,
  Accountable = 1,
  Consulted = 2,
  Informed = 3,
}

export const enum AssigneeKind {
  OrgRole = 0,
  OrgPermission = 1,
  UserID = 2,
  ActorID = 3,
}

export interface RACIAssignee {
  role: RACIRole;
  kind: AssigneeKind;
  value: string;
}

export const enum DecisionClass {
  A = 0,
  B = 1,
  C = 2,
}

export interface AssigneeRef {
  kind: AssigneeKind;
  value: string;
}

export interface ApprovalRequirement {
  decisionClass: DecisionClass;
  minApprovers: number;
  approverPool: AssigneeRef[];
  riskTier: string;
  formId?: string;
}

export interface CommandPolicy {
  command: string;
  raci: RACIAssignee[];
  approval?: ApprovalRequirement;
  bpmnTaskId?: string;
  ocelEventType?: string;
}

export interface GovernanceManifest {
  appId: string;
  policies: CommandPolicy[];
}

export const enum PolicyVerdict {
  Allow = 0,
  PendingApproval = 1,
  Denied = 2,
}

// ── Capability types ────────────────────────────────────────────────────

export type CapabilityStatus = "planned" | "developing" | "operational" | "retired";

export interface ActorCapability {
  id: string;
  name: string;
  description: string;
  status: CapabilityStatus;
  phase: string;
  parentId?: string;
  tags: string[];
  activityIds: string[];
  measureNames: string[];
}

export interface CapabilityDiscoveryEntry {
  nanoid: string;
  capability: ActorCapability;
}

// ── Identity types ──────────────────────────────────────────────────────

export type AddressScheme = "email" | "actor" | "webhook";

export interface ActorAddress {
  address: string;
  scheme: AddressScheme;
  nanoid: string;
  displayName?: string;
}

export interface ToolDescriptor {
  name: string;
  description: string;
  inputSchemaJson: string;
}

export interface ProviderInfo {
  nanoid: string;
  endpoint: string;
  appDid?: string;
  tier?: number;
  tags: string[];
}

export interface ActorCard {
  nanoid: string;
  name: string;
  description: string;
  serviceUserId?: string;
  addresses: ActorAddress[];
  tools: ToolDescriptor[];
  protocols: string[];
  capabilitiesJson?: string;
}

// ── Conversation types ──────────────────────────────────────────────────

export interface ConversationSession {
  sessionId: string;
  topic: string;
  participants: string[];
  status: string;
  createdAt: string;
  createdBy?: string;
}

export interface ConversationMessage {
  messageId: string;
  sessionId: string;
  from: string;
  content: string;
  replyTo?: string;
  createdAt: string;
}

// ── Agent types ─────────────────────────────────────────────────────────

export const enum Role {
  System = 0,
  User = 1,
  Assistant = 2,
  Tool = 3,
}

export const enum ToolChoiceMode {
  Auto = 0,
  Required = 1,
  None = 2,
}

export interface AgentToolDef {
  name: string;
  description: string;
  inputSchemaJson: string;
}

export interface ChatResponse {
  content: string;
  toolCalls?: Uint8Array;
  usage?: { promptTokens: number; completionTokens: number; totalTokens: number; cachedTokens: number };
  model: string;
  finishReason: string;
}

// ── W Protocol Caller (serve interface) ─────────────────────────────────

export interface WProtoCaller {
  did: string;
  orgId: string;
  nanoid: string;
  roles: string[];
  trustLevel: string;
  contractRefs: string[];
}

// ── SMTP types ──────────────────────────────────────────────────────────

export interface SmtpConnectionInfo {
  provider: string;
  email: string;
  displayName: string;
  connected: boolean;
}

// ── Handler types ───────────────────────────────────────────────────────

export type CommandHandler = (ctx: AppContext, payload: Uint8Array) => Uint8Array | unknown | Promise<Uint8Array | unknown>;
export type ConversationHandler = (ctx: AppContext, msg: ConversationMessage) => void;
export type RemoteCallHandler = (params: Uint8Array, callerDid: string, callerOrgId: string) => Uint8Array;

// ── Host Import Interface ───────────────────────────────────────────────
// Host functions covering every WIT import from kotodama:runtime world.

export interface HostImports {
  // ── kotodama:core/config ──
  configGet(key: string): string | undefined;

  // ── kotodama:core/log ──
  logAppend(stream: string, subject: string, payload: Uint8Array): bigint;

  // ── kotodama:graph/vector-search ──
  vectorSearch(queryVector: number[], limit: number, labelFilter: string, propFilter: string): string;
  vectorWrite(verticesJson: string, embeddingKey: string, dim: number): number;
  vectorCreateIndex(): string;

  // ── kotodama:auth/clerk ──
  clerkVerifyToken(token: string): Uint8Array;
  clerkVerifyTokenWithAzp(token: string, azp: string): Uint8Array;
  clerkAuthorize(header: string, orgId: string, permission: string): Uint8Array;
  clerkGetUser(userId: string): Uint8Array;
  clerkGetOrganization(orgId: string): Uint8Array;
  clerkGetSession(sessionId: string): Uint8Array;
  clerkCheckPermission(userId: string, orgId: string, permission: string): boolean;
  clerkCheckRole(userId: string, orgId: string, role: string): boolean;

  // ── kotodama:auth/authn ──
  authnResolveContext(authHeader: string, orgHeader: string, requestId: string): AuthnContext | null;
  authnVerifyToken(token: string): Uint8Array;
  authnEnsureActiveSession(sessionId: string): void;

  // ── kotodama:auth/authz ──
  authzEnforce(orgId: string, role: string, permissions: string[], requiredPermissions: string[], requiredRoles: string[]): void;

  // ── kotodama:auth/crypto ──
  cryptoSha256(data: Uint8Array): Uint8Array;
  cryptoSha256Hex(data: string): string;

  // ── kotodama:identity/identity ──
  identityRegister(card: ActorCard): void;
  identityResolve(nanoid: string): string | null;
  identityResolveAddress(address: string): string | null;
  identityListActors(offset: number, limit: number): string;

  // ── kotodama:identity/capability ──
  capabilityDeclare(cap: ActorCapability): void;
  capabilityRevoke(id: string): void;
  capabilityListOwn(): string;
  capabilityAddDependency(depJson: string): void;
  capabilityRemoveDependency(fromId: string, toId: string): void;
  capabilityListDependencies(capabilityId: string): string;
  capabilityDiscover(tag: string | null, status: string | null, offset: number, limit: number): string;

  // ── kotodama:identity/dependency ──
  dependencyDeclare(dep: string): void;
  dependencyRemove(pkg: string, iface: string): void;
  dependencyListOwn(): string;
  dependencyCheckAll(): string;
  dependencyCheck(pkg: string, iface: string): string;
  dependencyListDependents(): string;

  // ── kotodama:governance/raci ──
  governanceRegisterManifest(manifestJson: string): void;
  governanceCheckPolicy(command: string, userId: string, orgId: string): PolicyVerdict;

  // ── kotodama:governance/rbac ──
  rbacDefineRole(roleJson: string): void;
  rbacRemoveRole(roleId: string): void;
  rbacListRoles(orgId: string): string;
  rbacAssignRole(assignmentJson: string): void;
  rbacRevokeRole(userId: string, roleId: string, orgId: string): void;
  rbacListUserRoles(userId: string, orgId: string): string;
  rbacCheckPermission(userId: string, orgId: string, permission: string): string;

  // ── kotodama:governance/governance ──
  governanceGetConfig(key: string): string;
  governanceSetConfig(key: string, value: string): void;

  // ── kotodama:governance/traceability ──
  traceabilityLink(sourceId: string, targetId: string, relationType: string): void;
  traceabilityGetChain(entityId: string): string;

  // ── kotodama:consent/consent ──
  consentCreate(grantJson: string): string;
  consentRevoke(consentId: string): void;
  consentCheck(subjectDid: string, purpose: string, scope: string): string;
  consentList(subjectDid: string): string;

  // ── kotodama:agent/agent ──
  agentRegisterTools(tools: AgentToolDef[]): void;
  agentChat(userMessage: string, llmContextJson: string): string;
  agentInvokeTool(toolName: string, inputJson: string): string;
  agentConverse(messages: unknown[], options: unknown): unknown;
  agentRoute(inputJson: string): string;
  agentReact(taskJson: string, optionsJson: string): string;

  // ── kotodama:agent/skill ──
  skillInstall(skillJson: string): void;
  skillUninstall(skillId: string): void;
  skillListOwn(): string;
  skillGet(skillId: string): string | null;
  skillDiscover(tag: string, offset: number, limit: number): string;
  skillInvokeTool(skillId: string, toolName: string, inputJson: string): string;

  // ── etzhayyim:invoke/invoke ──
  invoke(did: string, method: string, params: Uint8Array): Uint8Array;
  invokeStream(did: string, method: string, params: Uint8Array): unknown;

  // ── etzhayyim:wrpc/stream (messaging) ──
  createChannel(name: string, description: string, kind: string, inviteDids: string[]): string;
  createProjectConvo(peerDid: string, kind: string, payload: Uint8Array, contentType: string): string;
  sendProjectMessage(convoId: string, kind: string, payload: Uint8Array, contentType: string, replyTo: string | null, threadId: string | null): string;
  listEnvelopes(convoId: string, limit: number, beforeRkey: string | null): string;
  getThread(convoId: string, rootRkey: string): string;
  searchMessages(query: string, convoId: string | null, limit: number): string;
  getUnread(): string;
  markRead(convoId: string, lastRkey: string): void;
  updatePresence(status: string, statusText: string): void;

  // ── etzhayyim:convo/convo (conversation merged) ──
  conversationCreateSession(topic: string, participantsJson: string): string;
  conversationSendMessage(sessionId: string, content: string): string;
  conversationGetHistory(sessionId: string): string;
  conversationGetSession(sessionId: string): string;
  conversationListSessions(): string;

  // ── etzhayyim:signal/signal (crypto primitives) ──
  signalGenerateIdentity(): Uint8Array;
  signalGenerateSignedPrekey(identityCbor: Uint8Array, keyId: number): Uint8Array;
  signalGenerateOneTimePrekey(keyId: number): Uint8Array;
  signalBuildPreKeyBundle(identityCbor: Uint8Array, spkJson: Uint8Array, opkJson: Uint8Array | null): Uint8Array;
  signalX3dhInitiate(senderIkCbor: Uint8Array, bundleJson: Uint8Array): Uint8Array;
  signalX3dhRespond(recipientIkCbor: Uint8Array, spkJson: Uint8Array, opkJson: Uint8Array | null, initMsgJson: Uint8Array): Uint8Array;
  signalRatchetInitSender(x3dhResultJson: Uint8Array, recipientRatchetPublic: Uint8Array): Uint8Array;
  signalRatchetInitReceiver(x3dhResultJson: Uint8Array, ourRatchetSecret: Uint8Array): Uint8Array;
  signalRatchetEncrypt(sessionCbor: Uint8Array, plaintext: Uint8Array): Uint8Array;
  signalRatchetDecrypt(sessionCbor: Uint8Array, msgJson: Uint8Array): Uint8Array;
  signalGroupInitSender(groupId: string, ourDid: string): Uint8Array;
  signalGroupProcessDistribution(sessionJson: Uint8Array, distJson: Uint8Array): Uint8Array;
  signalGroupEncrypt(sessionJson: Uint8Array, plaintext: Uint8Array): Uint8Array;
  signalGroupDecrypt(sessionJson: Uint8Array, msgJson: Uint8Array): Uint8Array;

  // ── etzhayyim:signal/session (managed sessions) ──
  signalSessionGroupGetOrCreate(groupId: string, memberDids: string[]): { session: Uint8Array; distribution: Uint8Array };
  signalSessionGroupEncrypt(groupId: string, plaintext: Uint8Array): Uint8Array;
  signalSessionGroupDecrypt(groupId: string, ciphertext: Uint8Array, senderDid: string): Uint8Array;
  signalSessionGroupAddMember(groupId: string, memberDid: string): Uint8Array;

  // ── etzhayyim:yata/yata ──
  queryG(label: string, matchJson: string, returnClause: string, limit: number): string;
  queryGExec(query: string, paramsJson: string): bigint;
  graphExec(query: string, paramsJson: string): string;

  // ── com-atproto:identity/identity (AT Protocol lexicon aligned) ──
  comAtprotoIdentityCreate(path: string, documentJson: string): string;
  comAtprotoIdentityResolve(did: string): string;
  comAtprotoIdentityUpdate(did: string, patchesJson: string): void;
  comAtprotoIdentityDeactivate(did: string): void;
  comAtprotoIdentityList(): string;
  comAtprotoIdentityRotateKey(did: string, keyId: string): string;
  comAtprotoIdentityCreateRecord(did: string, collection: string, recordJson: string): string;
  comAtprotoIdentityUpdateRecord(did: string, collection: string, rkey: string, recordJson: string): void;
  comAtprotoIdentityDeleteRecord(did: string, collection: string, rkey: string): void;

  // ── app-bsky:graph/graph ──
  followFollow(targetNanoid: string): string;
  followUnfollow(targetNanoid: string): void;
  followSetMuted(targetNanoid: string, muted: boolean): void;
  followListFollowing(offset: number, limit: number): string;
  followListFollowers(offset: number, limit: number): string;
  followCountFollowers(): bigint;
  followCountFollowing(): bigint;
  followReact(targetNanoid: string, targetCollection: string, targetRkey: string, kind: number): string;
  followUnreact(targetNanoid: string, targetCollection: string, targetRkey: string): void;
  followGetReactions(collection: string, rkey: string, offset: number, limit: number): string;
  followPullFeed(limit: number): string;
  followAckFeed(upToTs: string): void;
  followGetEngagement(): string;
  followLeaderboard(limit: number): string;
  followListFollowRequests(direction: string, status: string | null, offset: number, limit: number): string;
  followApproveFollowRequest(requestId: string): string;
  followRejectFollowRequest(requestId: string): void;
  followApproveAllFollowRequests(): bigint;

  // ── etzhayyim:governance/governance ──
  wGovernanceCheckAccess(did: string, lexicon: string, action: string): string;
  wGovernanceGetPolicy(did: string): string;
  wGovernanceRegisterPolicy(lexicon: string, policyJson: string): void;
  wGovernanceListPolicies(): string;
  wGovernanceRegisterMethodPolicy(method: string, policyJson: string): void;
  wGovernanceSetActorSensitivity(sensitivity: string): void;
  wGovernanceGetActorSensitivity(): string;
  wGovernanceResolveActorVisibility(targetDid: string): string;

  // ── com-atproto:label/label ──
  contentLabelCreate(labelJson: string): string;
  contentLabelQuery(filterJson: string): string;
  contentLabelSetPref(labelValue: string, visibility: number): void;
  contentLabelGetPrefs(): string;
  contentLabelDeclareLabeler(labelerJson: string): string;
  contentLabelGetLabeler(labelerDid: string): string;
  contentLabelSubscribe(labelerDid: string): void;
  contentLabelUnsubscribe(labelerDid: string): void;
  contentLabelListSubscribed(): string;

  // ── etzhayyim:smtp/smtp ──
  smtpConnect(provider: string, authCode: string, redirectUri: string, userId: string, orgId: string): SmtpConnectionInfo;
  smtpDisconnect(provider: string, userId: string, orgId: string): void;
  smtpStatus(provider: string, userId: string, orgId: string): Uint8Array;
  smtpSendTransactional(fromEmail: string, fromName: string, to: string[], subject: string, bodyText: string, bodyHtml: string): string;

  // ── kotodama:storage/ipfs ──
  ipfsPublish(data: Uint8Array, contentType: string): string;
  ipfsPublishUrl(data: Uint8Array, contentType: string): string;
  ipfsGatewayUrl(cid: string): string;

  // ── kotodama:storage/storage ──
  storagePutObject(bucket: string, key: string, data: Uint8Array, contentType: string): string;
  storageGetObject(bucket: string, key: string): Uint8Array;
  storageDeleteObject(bucket: string, key: string): void;

  // ── kotodama:storage/cdn ──
  cdnUpload(subdomain: string, path: string, data: Uint8Array, contentType: string): string;
  cdnFetchUpload(subdomain: string, sourceUrl: string, path: string, contentType: string): string;
  cdnDelete(subdomain: string, path: string): void;
  cdnPublicUrl(subdomain: string, path: string): string;
  cdnUploadImage(subdomain: string, path: string, data: Uint8Array, optionsJson: string): string;

  // ── kotodama:storage/static-site ──
  staticSitePut(path: string, data: Uint8Array, contentType: string): bigint;
  staticSiteDelete(path: string): void;
  staticSiteListFiles(prefix: string): string[];

  // ── kotodama:workflow/workflow ──
  workflowStart(name: string, inputJson: string, optionsJson: string): string;
  workflowSignal(workflowId: string, signalName: string, payload: string): void;
  workflowQuery(workflowId: string, queryName: string, payload: string): string;
  workflowGet(workflowId: string): string;
  workflowPause(workflowId: string): void;
  workflowResume(workflowId: string): void;
  workflowTerminate(workflowId: string): void;
  workflowPurge(workflowId: string): void;
  workflowRaiseEvent(workflowId: string, eventName: string, payload: string): void;
  workflowCreateTimer(workflowId: string, name: string, fireAtMs: bigint): void;

  // ── kotodama:workflow/activity ──
  activitySchedule(name: string, inputJson: string, optionsJson: string): string;
  activityHeartbeat(activityId: string, details: string): void;

  // ── kotodama:workflow/activity-parallel ──
  activitySpawnParallel(activitiesJson: string): string;
  activityAwaitAll(batchId: string, timeoutMs: bigint): string;

  // ── kotodama:workflow/dag ──
  dagSubmit(dagJson: string): string;
  dagStatus(dagId: string): string;
  dagCancel(dagId: string): void;

  // ── kotodama:actor/timer ──
  timerSet(name: string, delayMs: bigint, callbackData: string): void;
  timerCancel(name: string): void;
  timerList(): string;

  // ── kotodama:actor/reminder ──
  reminderSet(name: string, dueMs: bigint, period: bigint, data: string): void;
  reminderGet(name: string): string | null;
  reminderDelete(name: string): void;
  reminderList(): string;

  // ── kotodama:actor/actor-state ──
  actorStateGet(key: string): string | null;
  actorStateSet(key: string, value: string): void;
  actorStateDelete(key: string): void;
  actorStateList(prefix: string): string;

  // ── kotodama:actor/lock ──
  lockTryLock(key: string, ttlMs: bigint): boolean;
  lockUnlock(key: string): void;
  lockRenew(key: string, ttlMs: bigint): boolean;

  // ── kotodama:actor/virtual-actor ──
  virtualActorRegister(actorType: string, optionsJson: string): void;
  virtualActorInvoke(actorType: string, actorId: string, method: string, paramsJson: string): string;

  // ── kotodama:telemetry/telemetry ──
  telemetryEmitMetric(name: string, value: number, tagsJson: string): void;
  telemetryStartSpan(name: string, attributesJson: string): string;
  telemetryEndSpan(spanId: string, statusJson: string): void;
  telemetryLog(level: string, message: string, attributesJson: string): void;

  // ── kotodama:telemetry/access-log ──
  accessLogRecord(entryJson: string): void;

  // ── kotodama:audit/audit-trail ──
  auditEmit(category: string, action: string, resourceId: string, outcome: string, detailsJson: string): bigint;
  auditQuery(category: string, actorDid: string, sinceUnixMs: bigint, offset: number, limit: number): string;
  auditCount(category: string, actorDid: string, sinceUnixMs: bigint): bigint;

  // ── kotodama:audit/ocel ──
  ocelEmitEvent(eventJson: string): void;
  ocelQuery(filterJson: string): string;

  // ── kotodama:audit/anomaly ──
  anomalyDetect(metricJson: string): string;
  anomalyReport(anomalyJson: string): void;

  // ── kotodama:audit/incident ──
  incidentCreate(incidentJson: string): string;
  incidentUpdate(incidentId: string, updateJson: string): void;
  incidentResolve(incidentId: string, resolutionJson: string): void;
  incidentGet(incidentId: string): string;
  incidentList(filterJson: string): string;

  // ── kotodama:pubsub/pubsub ──
  pubsubPublish(topic: string, payload: Uint8Array): void;
  pubsubPull(topic: string, maxMessages: number): string;
  pubsubAck(topic: string, messageIds: string[]): void;

  // ── kotodama:secrets/secrets ──
  secretsGet(key: string): string | null;
  secretsSet(key: string, value: string): void;
  secretsDelete(key: string): void;

  // ── kotodama:secrets/vault ──
  vaultGet(path: string): string | null;
  vaultPut(path: string, value: string): void;
  vaultDelete(path: string): void;

  // ── kotodama:forms/forms ──
  formsCreate(schemaJson: string): string;
  formsValidate(formId: string, dataJson: string): string;
  formsGet(formId: string): string;

  // ── kotodama:bpmn/bpmn ──
  bpmnDeploy(bpmnXml: string): string;
  bpmnStartProcess(processId: string, variablesJson: string): string;
  bpmnCompleteTask(taskId: string, variablesJson: string): void;
  bpmnGetProcess(instanceId: string): string;

  // ── kotodama:dmn/dmn ──
  dmnEvaluate(decisionId: string, contextJson: string): string;
  dmnDeploy(dmnXml: string): string;

  // ── kotodama:dm2/performer ──
  dm2RegisterPerformer(performerJson: string): void;
  dm2ResolvePerformer(id: string): string | null;
  dm2ListPerformers(kind: string, offset: number, limit: number): string;
  dm2GetParent(id: string): string | null;
  dm2ListChildren(id: string, offset: number, limit: number): string;
  dm2ListSiblings(id: string, offset: number, limit: number): string;
  dm2ListRelationships(id: string, relation: string, offset: number, limit: number): string;
  dm2ListDependencies(id: string, dependencyKind: string, offset: number, limit: number): string;
  dm2ResolveLineage(id: string): string;

  // ── kotodama:contract/agreement ──
  contractCreateAgreement(agreementJson: string): string;
  contractGetAgreement(agreementId: string): string;
  contractListAgreements(filterJson: string): string;

  // ── kotodama:contract/registry ──
  contractRegister(registrationJson: string): void;
  contractLookup(query: string): string;

  // ── kotodama:browser/scraper ──
  scraperFetchHtml(url: string): string;
  scraperExtractText(html: string, cssSelector: string): string[];
  scraperExtractTable(html: string, cssSelector: string): string[][];
  scraperExtractLinks(html: string, cssSelector: string): [string, string][];
  scraperExtractAttr(html: string, cssSelector: string, attrName: string): string[];

  // ── kotodama:browser/analyzer ──
  analyzerExtractStructured(html: string, schemaJson: string): string;
  analyzerAnalyze(prompt: string, context: string): string;

  // ── kotodama:browser/automation ──
  automationOpenSession(): string;
  automationCloseSession(sessionId: string): void;
  automationNavigate(sessionId: string, url: string): void;
  automationClick(sessionId: string, cssSelector: string): void;
  automationTypeText(sessionId: string, cssSelector: string, text: string): void;
  automationSelectOption(sessionId: string, cssSelector: string, value: string): void;
  automationWaitForSelector(sessionId: string, cssSelector: string, waitMs: number): void;
  automationWaitForNavigation(sessionId: string, waitMs: number): void;
  automationCurrentUrl(sessionId: string): string;
  automationPageHtml(sessionId: string): string;
  automationScreenshot(sessionId: string): string;
  automationQueryText(sessionId: string, cssSelector: string): string[];
  automationIsVisible(sessionId: string, cssSelector: string): boolean;
  automationEvalJs(sessionId: string, expression: string): string;

  // ── kotodama:browser/pipeline ──
  pipelineScrapeAndAnalyze(url: string, schemaJson: string): string;

  // ── kotodama:cloudflare/kv ──
  kvGet(key: string): string | null;
  kvPut(key: string, value: string, ttlSeconds: number): void;
  kvDelete(key: string): void;
  kvList(prefix: string, limit: number): string;

  // ── kotodama:cloudflare/r2 ──
  r2Get(key: string): Uint8Array | null;
  r2Put(key: string, data: Uint8Array, contentType: string): void;
  r2Delete(key: string): void;
  r2List(prefix: string, limit: number): string;
  r2Head(key: string): string | null;

  // ── kotodama:cloudflare/queue ──
  queueSend(queueName: string, message: Uint8Array): void;
  queueSendBatch(queueName: string, messages: Uint8Array[]): void;

  // ── kotodama:web3/wallet ──
  walletSign(data: Uint8Array): Uint8Array;
  walletVerify(data: Uint8Array, signature: Uint8Array, publicKey: Uint8Array): boolean;
  walletGetAddress(): string;

}

// ── Graph Op (structured graph operation for JS host) ───────────────────

export interface GraphOp {
  op: string;
  label: string;
  props?: Record<string, unknown>;
  match?: Record<string, unknown>;
  set?: Record<string, unknown>;
  where?: WhereClause[];
  return?: string[];
  orderBy?: string;
  orderDesc?: boolean;
  skip?: number;
  limit?: number;
}

export interface WhereClause {
  prop: string;
  op: string;
  val: unknown;
}
