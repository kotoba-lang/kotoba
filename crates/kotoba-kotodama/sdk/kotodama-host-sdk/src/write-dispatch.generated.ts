// Auto-generated dispatch table — DO NOT EDIT.
// Maps WriteBufferEntry `type` field → XRPC NSID.
// Originally WIT-generated; retained as hand-maintained after F-Plan F2 (2026-04-13).
// PdsInternalFn parameter archived 2026-04-13 (all dispatch is XRPC-only).
// Source of truth for new write types: add the case directly to dispatchWriteEntry() below
// and register the corresponding lexicon JSON under 00-contracts/lexicons/com/etzhayyim/apps/.

import type { WriteBufferEntry } from "./types.js";

type XrpcFn = (nsid: string, payload: unknown) => Promise<void>;

/**
 * Auto-generated dispatch for 777 write buffer entry types.
 * Each case maps a WIT @kind write func to its XRPC NSID.
 */
export async function dispatchWriteEntry(
  entry: WriteBufferEntry,
  xrpc: XrpcFn,
): Promise<void> {
  switch (entry.type) {

    // ── kotodama:telemetry/access-log@1.0.0 ──
    // kotodama:telemetry/access-log@1.0.0#counter-add
    case "access-log-counter-add":
      return xrpc("com.etzhayyim.telemetry.counterAdd", entry.payload);
    // kotodama:telemetry/access-log@1.0.0#gauge-set
    case "access-log-gauge-set":
      return xrpc("com.etzhayyim.telemetry.gaugeSet", entry.payload);
    // kotodama:telemetry/access-log@1.0.0#histogram-record
    case "access-log-histogram-record":
      return xrpc("com.etzhayyim.telemetry.histogramRecord", entry.payload);
    // kotodama:telemetry/access-log@1.0.0#page-views
    case "access-log-page-views":
      return xrpc("com.etzhayyim.telemetry.pageViews", entry.payload);
    // kotodama:telemetry/access-log@1.0.0#total-requests
    case "access-log-total-requests":
      return xrpc("com.etzhayyim.telemetry.totalRequests", entry.payload);

    // ── kotodama:workflow/activity@1.0.0 ──
    // kotodama:workflow/activity@1.0.0#await-all
    case "activity-await-all":
      return xrpc("com.etzhayyim.workflow.awaitAll", entry.payload);
    // kotodama:workflow/activity@1.0.0#create-timer
    case "activity-create-timer":
      return xrpc("com.etzhayyim.workflow.createTimer", entry.payload);
    // kotodama:workflow/activity@1.0.0#get
    case "activity-get":
      return xrpc("com.etzhayyim.workflow.get", entry.payload);
    // kotodama:workflow/activity@1.0.0#heartbeat
    case "activity-heartbeat":
      return xrpc("com.etzhayyim.workflow.heartbeat", entry.payload);
    // kotodama:workflow/activity@1.0.0#pause
    case "activity-pause":
      return xrpc("com.etzhayyim.workflow.pause", entry.payload);
    // kotodama:workflow/activity@1.0.0#purge
    case "activity-purge":
      return xrpc("com.etzhayyim.workflow.purge", entry.payload);
    // kotodama:workflow/activity@1.0.0#query
    case "activity-query":
      return xrpc("com.etzhayyim.workflow.query", entry.payload);
    // kotodama:workflow/activity@1.0.0#raise-event
    case "activity-raise-event":
      return xrpc("com.etzhayyim.workflow.raiseEvent", entry.payload);
    // kotodama:workflow/activity@1.0.0#resume
    case "activity-resume":
      return xrpc("com.etzhayyim.workflow.resume", entry.payload);
    // kotodama:workflow/activity@1.0.0#schedule
    case "activity-schedule":
      return xrpc("com.etzhayyim.workflow.schedule", entry.payload);
    // kotodama:workflow/activity@1.0.0#signal
    case "activity-signal":
      return xrpc("com.etzhayyim.workflow.signal", entry.payload);
    // kotodama:workflow/activity@1.0.0#start
    case "activity-start":
      return xrpc("com.etzhayyim.workflow.start", entry.payload);
    // kotodama:workflow/activity@1.0.0#submit-dag
    case "activity-submit-dag":
      return xrpc("com.etzhayyim.workflow.submitDag", entry.payload);
    // kotodama:workflow/activity@1.0.0#terminate
    case "activity-terminate":
      return xrpc("com.etzhayyim.workflow.terminate", entry.payload);

    // ── chat-bsky:actor/actor@1.0.0 ──
    // chat-bsky:actor/actor@1.0.0#delete-account
    case "actor-delete-account":
      return xrpc("com.etzhayyim.apps.actor.deleteAccount", entry.payload);
    // chat-bsky:actor/actor@1.0.0#export-account-data
    case "actor-export-account-data":
      return xrpc("com.etzhayyim.apps.actor.exportAccountData", entry.payload);
    // app-bsky:actor/actor@1.0.0#put-preferences
    case "actor-put-preferences":
      return xrpc("com.etzhayyim.apps.actor.putPreferences", entry.payload);
    // kotodama:actor/actor-state@1.0.0#cancel-schedule
    case "actor-state-cancel-schedule":
      return xrpc("com.etzhayyim.actor.cancelSchedule", entry.payload);
    // kotodama:actor/actor-state@1.0.0#deactivate
    case "actor-state-deactivate":
      return xrpc("com.etzhayyim.actor.deactivate", entry.payload);
    // kotodama:actor/actor-state@1.0.0#delete
    case "actor-state-delete":
      return xrpc("com.etzhayyim.actor.delete", entry.payload);
    // kotodama:actor/actor-state@1.0.0#get
    case "actor-state-get":
      return xrpc("com.etzhayyim.actor.get", entry.payload);
    // kotodama:actor/actor-state@1.0.0#invoke
    case "actor-state-invoke":
      return xrpc("com.etzhayyim.actor.invoke", entry.payload);
    // kotodama:actor/actor-state@1.0.0#put
    case "actor-state-put":
      return xrpc("com.etzhayyim.actor.put", entry.payload);
    // kotodama:actor/actor-state@1.0.0#register
    case "actor-state-register":
      return xrpc("com.etzhayyim.actor.register", entry.payload);
    // kotodama:actor/actor-state@1.0.0#renew
    case "actor-state-renew":
      return xrpc("com.etzhayyim.actor.renew", entry.payload);
    // kotodama:actor/actor-state@1.0.0#schedule-method
    case "actor-state-schedule-method":
      return xrpc("com.etzhayyim.actor.scheduleMethod", entry.payload);
    // kotodama:actor/actor-state@1.0.0#try-lock
    case "actor-state-try-lock":
      return xrpc("com.etzhayyim.actor.tryLock", entry.payload);
    // kotodama:actor/actor-state@1.0.0#unlock
    case "actor-state-unlock":
      return xrpc("com.etzhayyim.actor.unlock", entry.payload);
    // kotodama:actor/actor-state@1.0.0#unregister
    case "actor-state-unregister":
      return xrpc("com.etzhayyim.actor.unregister", entry.payload);

    // ── com-atproto:admin/admin@1.0.0 ──
    // com-atproto:admin/admin@1.0.0#delete-account
    case "admin-delete-account":
      return xrpc("com.etzhayyim.apps.admin.deleteAccount", entry.payload);
    // com-atproto:admin/admin@1.0.0#disable-account-invites
    case "admin-disable-account-invites":
      return xrpc("com.etzhayyim.apps.admin.disableAccountInvites", entry.payload);
    // com-atproto:admin/admin@1.0.0#disable-invite-codes
    case "admin-disable-invite-codes":
      return xrpc("com.etzhayyim.apps.admin.disableInviteCodes", entry.payload);
    // com-atproto:admin/admin@1.0.0#enable-account-invites
    case "admin-enable-account-invites":
      return xrpc("com.etzhayyim.apps.admin.enableAccountInvites", entry.payload);
    // com-atproto:admin/admin@1.0.0#send-email
    case "admin-send-email":
      return xrpc("com.etzhayyim.apps.admin.sendEmail", entry.payload);
    // com-atproto:admin/admin@1.0.0#update-account-email
    case "admin-update-account-email":
      return xrpc("com.etzhayyim.apps.admin.updateAccountEmail", entry.payload);
    // com-atproto:admin/admin@1.0.0#update-account-handle
    case "admin-update-account-handle":
      return xrpc("com.etzhayyim.apps.admin.updateAccountHandle", entry.payload);
    // com-atproto:admin/admin@1.0.0#update-account-password
    case "admin-update-account-password":
      return xrpc("com.etzhayyim.apps.admin.updateAccountPassword", entry.payload);
    // com-atproto:admin/admin@1.0.0#update-account-signing-key
    case "admin-update-account-signing-key":
      return xrpc("com.etzhayyim.apps.admin.updateAccountSigningKey", entry.payload);
    // com-atproto:admin/admin@1.0.0#update-subject-status
    case "admin-update-subject-status":
      return xrpc("com.etzhayyim.apps.admin.updateSubjectStatus", entry.payload);

    // ── app-bsky:ageassurance/ageassurance@1.0.0 ──
    // app-bsky:ageassurance/ageassurance@1.0.0#begin
    case "ageassurance-begin":
      return xrpc("com.etzhayyim.apps.ageassurance.begin", entry.payload);

    // ── kotodama:agent/agent@1.0.0 ──
    // kotodama:agent/agent@1.0.0#chat
    case "agent-chat":
      return xrpc("com.etzhayyim.agent.chat", entry.payload);
    // kotodama:agent/agent@1.0.0#converse
    case "agent-converse":
      return xrpc("com.etzhayyim.agent.converse", entry.payload);
    // kotodama:agent/agent@1.0.0#get
    case "agent-get":
      return xrpc("com.etzhayyim.agent.get", entry.payload);
    // kotodama:agent/agent@1.0.0#install
    case "agent-install":
      return xrpc("com.etzhayyim.agent.install", entry.payload);
    // kotodama:agent/agent@1.0.0#invoke-tool
    case "agent-invoke-tool":
      return xrpc("com.etzhayyim.agent.invokeTool", entry.payload);
    // kotodama:agent/agent@1.0.0#react
    case "agent-react":
      return xrpc("com.etzhayyim.agent.react", entry.payload);
    // kotodama:agent/agent@1.0.0#register-manifest
    case "agent-register-manifest":
      return xrpc("com.etzhayyim.agent.registerManifest", entry.payload);
    // kotodama:agent/agent@1.0.0#register-tools
    case "agent-register-tools":
      return xrpc("com.etzhayyim.agent.registerTools", entry.payload);
    // kotodama:agent/agent@1.0.0#route
    case "agent-route":
      return xrpc("com.etzhayyim.agent.route", entry.payload);
    // kotodama:agent/agent@1.0.0#uninstall
    case "agent-uninstall":
      return xrpc("com.etzhayyim.agent.uninstall", entry.payload);

    // ── kotodama:contract/agreement@1.0.0 ──
    // kotodama:contract/agreement@1.0.0#bind-performer
    case "agreement-bind-performer":
      return xrpc("com.etzhayyim.contract.bindPerformer", entry.payload);
    // kotodama:contract/agreement@1.0.0#register-contract
    case "agreement-register-contract":
      return xrpc("com.etzhayyim.contract.registerContract", entry.payload);
    // kotodama:contract/agreement@1.0.0#register-dependency
    case "agreement-register-dependency":
      return xrpc("com.etzhayyim.contract.registerDependency", entry.payload);
    // kotodama:contract/agreement@1.0.0#resolve-graph
    case "agreement-resolve-graph":
      return xrpc("com.etzhayyim.contract.resolveGraph", entry.payload);

    // ── kotodama:browser/analyzer@1.0.0 ──
    // kotodama:browser/analyzer@1.0.0#analyze
    case "analyzer-analyze":
      return xrpc("com.etzhayyim.browser.analyze", entry.payload);
    // kotodama:browser/analyzer@1.0.0#batch-fetch
    case "analyzer-batch-fetch":
      return xrpc("com.etzhayyim.browser.batchFetch", entry.payload);
    // kotodama:browser/analyzer@1.0.0#click
    case "analyzer-click":
      return xrpc("com.etzhayyim.browser.click", entry.payload);
    // kotodama:browser/analyzer@1.0.0#close-session
    case "analyzer-close-session":
      return xrpc("com.etzhayyim.browser.closeSession", entry.payload);
    // kotodama:browser/analyzer@1.0.0#current-url
    case "analyzer-current-url":
      return xrpc("com.etzhayyim.browser.currentUrl", entry.payload);
    // kotodama:browser/analyzer@1.0.0#eval-js
    case "analyzer-eval-js":
      return xrpc("com.etzhayyim.browser.evalJs", entry.payload);
    // kotodama:browser/analyzer@1.0.0#extract-attr
    case "analyzer-extract-attr":
      return xrpc("com.etzhayyim.browser.extractAttr", entry.payload);
    // kotodama:browser/analyzer@1.0.0#extract-links
    case "analyzer-extract-links":
      return xrpc("com.etzhayyim.browser.extractLinks", entry.payload);
    // kotodama:browser/analyzer@1.0.0#extract-structured
    case "analyzer-extract-structured":
      return xrpc("com.etzhayyim.browser.extractStructured", entry.payload);
    // kotodama:browser/analyzer@1.0.0#extract-table
    case "analyzer-extract-table":
      return xrpc("com.etzhayyim.browser.extractTable", entry.payload);
    // kotodama:browser/analyzer@1.0.0#extract-text
    case "analyzer-extract-text":
      return xrpc("com.etzhayyim.browser.extractText", entry.payload);
    // kotodama:browser/analyzer@1.0.0#fetch-html
    case "analyzer-fetch-html":
      return xrpc("com.etzhayyim.browser.fetchHtml", entry.payload);
    // kotodama:browser/analyzer@1.0.0#is-visible
    case "analyzer-is-visible":
      return xrpc("com.etzhayyim.browser.isVisible", entry.payload);
    // kotodama:browser/analyzer@1.0.0#navigate
    case "analyzer-navigate":
      return xrpc("com.etzhayyim.browser.navigate", entry.payload);
    // kotodama:browser/analyzer@1.0.0#open-session
    case "analyzer-open-session":
      return xrpc("com.etzhayyim.browser.openSession", entry.payload);
    // kotodama:browser/analyzer@1.0.0#page-html
    case "analyzer-page-html":
      return xrpc("com.etzhayyim.browser.pageHtml", entry.payload);
    // kotodama:browser/analyzer@1.0.0#press-key
    case "analyzer-press-key":
      return xrpc("com.etzhayyim.browser.pressKey", entry.payload);
    // kotodama:browser/analyzer@1.0.0#scrape-and-store
    case "analyzer-scrape-and-store":
      return xrpc("com.etzhayyim.browser.scrapeAndStore", entry.payload);
    // kotodama:browser/analyzer@1.0.0#screenshot
    case "analyzer-screenshot":
      return xrpc("com.etzhayyim.browser.screenshot", entry.payload);
    // kotodama:browser/analyzer@1.0.0#scroll
    case "analyzer-scroll":
      return xrpc("com.etzhayyim.browser.scroll", entry.payload);
    // kotodama:browser/analyzer@1.0.0#select-option
    case "analyzer-select-option":
      return xrpc("com.etzhayyim.browser.selectOption", entry.payload);
    // kotodama:browser/analyzer@1.0.0#set-cookies
    case "analyzer-set-cookies":
      return xrpc("com.etzhayyim.browser.setCookies", entry.payload);
    // kotodama:browser/analyzer@1.0.0#type-text
    case "analyzer-type-text":
      return xrpc("com.etzhayyim.browser.typeText", entry.payload);
    // kotodama:browser/analyzer@1.0.0#wait-for-navigation
    case "analyzer-wait-for-navigation":
      return xrpc("com.etzhayyim.browser.waitForNavigation", entry.payload);
    // kotodama:browser/analyzer@1.0.0#wait-for-selector
    case "analyzer-wait-for-selector":
      return xrpc("com.etzhayyim.browser.waitForSelector", entry.payload);

    // ── kotodama:audit/anomaly@1.0.0 ──
    // kotodama:audit/anomaly@1.0.0#ack-alert
    case "anomaly-ack-alert":
      return xrpc("com.etzhayyim.audit.ackAlert", entry.payload);
    // kotodama:audit/anomaly@1.0.0#add-object-edge
    case "anomaly-add-object-edge":
      return xrpc("com.etzhayyim.audit.addObjectEdge", entry.payload);
    // kotodama:audit/anomaly@1.0.0#declare-incident
    case "anomaly-declare-incident":
      return xrpc("com.etzhayyim.audit.declareIncident", entry.payload);
    // kotodama:audit/anomaly@1.0.0#emit-event
    case "anomaly-emit-event":
      // Legacy endpoint removed on PDS side; keep best-effort and avoid noisy 404 spam.
      return;
    // kotodama:audit/anomaly@1.0.0#export-json
    case "anomaly-export-json":
      return xrpc("com.etzhayyim.audit.exportJson", entry.payload);
    // kotodama:audit/anomaly@1.0.0#register-rule
    case "anomaly-register-rule":
      return xrpc("com.etzhayyim.audit.registerRule", entry.payload);
    // kotodama:audit/anomaly@1.0.0#remove-rule
    case "anomaly-remove-rule":
      return xrpc("com.etzhayyim.audit.removeRule", entry.payload);
    // kotodama:audit/anomaly@1.0.0#set-sla
    case "anomaly-set-sla":
      return xrpc("com.etzhayyim.audit.setSla", entry.payload);
    // kotodama:audit/anomaly@1.0.0#update-incident
    case "anomaly-update-incident":
      return xrpc("com.etzhayyim.audit.updateIncident", entry.payload);
    // kotodama:audit/anomaly@1.0.0#upsert-object
    case "anomaly-upsert-object":
      return xrpc("com.etzhayyim.audit.upsertObject", entry.payload);

    // ── kotodama:auth/authn@1.0.0 ──
    // kotodama:auth/authn@1.0.0#authorize
    case "authn-authorize":
      return xrpc("com.etzhayyim.auth.authorize", entry.payload);
    // kotodama:auth/authn@1.0.0#ensure-active-session
    case "authn-ensure-active-session":
      return xrpc("com.etzhayyim.auth.ensureActiveSession", entry.payload);
    // kotodama:auth/authn@1.0.0#resolve-context
    case "authn-resolve-context":
      return xrpc("com.etzhayyim.auth.resolveContext", entry.payload);
    // kotodama:auth/authn@1.0.0#sha256
    case "authn-sha256":
      return xrpc("com.etzhayyim.auth.sha256", entry.payload);
    // kotodama:auth/authn@1.0.0#sha256-hex
    case "authn-sha256-hex":
      return xrpc("com.etzhayyim.auth.sha256Hex", entry.payload);
    // kotodama:auth/authn@1.0.0#verify-token
    case "authn-verify-token":
      return xrpc("com.etzhayyim.auth.verifyToken", entry.payload);
    // kotodama:auth/authn@1.0.0#verify-token-with-azp
    case "authn-verify-token-with-azp":
      return xrpc("com.etzhayyim.auth.verifyTokenWithAzp", entry.payload);

    // ── app-bsky:bookmark/bookmark@1.0.0 ──
    // app-bsky:bookmark/bookmark@1.0.0#create-bookmark
    case "bookmark-create-bookmark":
      return xrpc("com.etzhayyim.apps.bookmark.createBookmark", entry.payload);
    // app-bsky:bookmark/bookmark@1.0.0#delete-bookmark
    case "bookmark-delete-bookmark":
      return xrpc("com.etzhayyim.apps.bookmark.deleteBookmark", entry.payload);

    // ── kotodama:bpmn/bpmn@1.0.0 ──
    // kotodama:bpmn/bpmn@1.0.0#broadcast-signal
    case "bpmn-broadcast-signal":
      return xrpc("com.etzhayyim.bpmn.broadcastSignal", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#cancel
    case "bpmn-cancel":
      return xrpc("com.etzhayyim.bpmn.cancel", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#cancel-timer
    case "bpmn-cancel-timer":
      return xrpc("com.etzhayyim.bpmn.cancelTimer", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#claim-task
    case "bpmn-claim-task":
      return xrpc("com.etzhayyim.bpmn.claimTask", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#correlate-message
    case "bpmn-correlate-message":
      return xrpc("com.etzhayyim.bpmn.correlateMessage", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#create-timer
    case "bpmn-create-timer":
      return xrpc("com.etzhayyim.bpmn.createTimer", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#delegate-task
    case "bpmn-delegate-task":
      return xrpc("com.etzhayyim.bpmn.delegateTask", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#delete-definition
    case "bpmn-delete-definition":
      return xrpc("com.etzhayyim.bpmn.deleteDefinition", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#delete-variable
    case "bpmn-delete-variable":
      return xrpc("com.etzhayyim.bpmn.deleteVariable", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#export-xml
    case "bpmn-export-xml":
      return xrpc("com.etzhayyim.bpmn.exportXml", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#migrate
    case "bpmn-migrate":
      return xrpc("com.etzhayyim.bpmn.migrate", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#modify
    case "bpmn-modify":
      return xrpc("com.etzhayyim.bpmn.modify", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#publish-message
    case "bpmn-publish-message":
      return xrpc("com.etzhayyim.bpmn.publishMessage", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#resolve-incident
    case "bpmn-resolve-incident":
      return xrpc("com.etzhayyim.bpmn.resolveIncident", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#resume
    case "bpmn-resume":
      return xrpc("com.etzhayyim.bpmn.resume", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#set-element-variables
    case "bpmn-set-element-variables":
      return xrpc("com.etzhayyim.bpmn.setElementVariables", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#set-task-due-date
    case "bpmn-set-task-due-date":
      return xrpc("com.etzhayyim.bpmn.setTaskDueDate", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#set-task-priority
    case "bpmn-set-task-priority":
      return xrpc("com.etzhayyim.bpmn.setTaskPriority", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#set-variables
    case "bpmn-set-variables":
      return xrpc("com.etzhayyim.bpmn.setVariables", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#signal-instance
    case "bpmn-signal-instance":
      return xrpc("com.etzhayyim.bpmn.signalInstance", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#suspend
    case "bpmn-suspend":
      return xrpc("com.etzhayyim.bpmn.suspend", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#terminate
    case "bpmn-terminate":
      return xrpc("com.etzhayyim.bpmn.terminate", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#trigger-compensation
    case "bpmn-trigger-compensation":
      return xrpc("com.etzhayyim.bpmn.triggerCompensation", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#trigger-error
    case "bpmn-trigger-error":
      return xrpc("com.etzhayyim.bpmn.triggerError", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#trigger-escalation
    case "bpmn-trigger-escalation":
      return xrpc("com.etzhayyim.bpmn.triggerEscalation", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#unclaim-task
    case "bpmn-unclaim-task":
      return xrpc("com.etzhayyim.bpmn.unclaimTask", entry.payload);
    // kotodama:bpmn/bpmn@1.0.0#update-retries
    case "bpmn-update-retries":
      return xrpc("com.etzhayyim.bpmn.updateRetries", entry.payload);

    // ── kotodama:identity/capability@1.0.0 ──
    // kotodama:identity/capability@1.0.0#add-dependency
    case "capability-add-dependency":
      return xrpc("com.etzhayyim.identity.addDependency", entry.payload);
    // kotodama:identity/capability@1.0.0#check
    case "capability-check":
      return xrpc("com.etzhayyim.identity.check", entry.payload);
    // kotodama:identity/capability@1.0.0#declare
    case "capability-declare":
      return xrpc("com.etzhayyim.identity.declare", entry.payload);
    // kotodama:identity/capability@1.0.0#register
    case "capability-register":
      return xrpc("com.etzhayyim.identity.register", entry.payload);
    // kotodama:identity/capability@1.0.0#remove
    case "capability-remove":
      return xrpc("com.etzhayyim.identity.remove", entry.payload);
    // kotodama:identity/capability@1.0.0#remove-dependency
    case "capability-remove-dependency":
      return xrpc("com.etzhayyim.identity.removeDependency", entry.payload);
    // kotodama:identity/capability@1.0.0#resolve
    case "capability-resolve":
      return xrpc("com.etzhayyim.identity.resolve", entry.payload);
    // kotodama:identity/capability@1.0.0#resolve-address
    case "capability-resolve-address":
      return xrpc("com.etzhayyim.identity.resolveAddress", entry.payload);
    // kotodama:identity/capability@1.0.0#revoke
    case "capability-revoke":
      return xrpc("com.etzhayyim.identity.revoke", entry.payload);

    // ── kotodama:storage/cdn@1.0.0 ──
    // kotodama:storage/cdn@1.0.0#delete
    case "cdn-delete":
      return xrpc("com.etzhayyim.storage.delete", entry.payload);
    // kotodama:storage/cdn@1.0.0#delete-object
    case "cdn-delete-object":
      return xrpc("com.etzhayyim.storage.deleteObject", entry.payload);
    // kotodama:storage/cdn@1.0.0#fetch-upload
    case "cdn-fetch-upload":
      return xrpc("com.etzhayyim.storage.fetchUpload", entry.payload);
    // kotodama:storage/cdn@1.0.0#gateway-url
    case "cdn-gateway-url":
      return xrpc("com.etzhayyim.storage.gatewayUrl", entry.payload);
    // kotodama:storage/cdn@1.0.0#public-url
    case "cdn-public-url":
      return xrpc("com.etzhayyim.storage.publicUrl", entry.payload);
    // kotodama:storage/cdn@1.0.0#publish
    case "cdn-publish":
      return xrpc("com.etzhayyim.storage.publish", entry.payload);
    // kotodama:storage/cdn@1.0.0#publish-url
    case "cdn-publish-url":
      return xrpc("com.etzhayyim.storage.publishUrl", entry.payload);
    // kotodama:storage/cdn@1.0.0#put
    case "cdn-put":
      return xrpc("com.etzhayyim.storage.put", entry.payload);
    // kotodama:storage/cdn@1.0.0#put-object
    case "cdn-put-object":
      return xrpc("com.etzhayyim.storage.putObject", entry.payload);
    // kotodama:storage/cdn@1.0.0#upload
    case "cdn-upload":
      return xrpc("com.etzhayyim.storage.upload", entry.payload);
    // kotodama:storage/cdn@1.0.0#upload-image
    case "cdn-upload-image":
      return xrpc("com.etzhayyim.storage.uploadImage", entry.payload);

    // ── tools-ozone:communication/communication@1.0.0 ──
    // tools-ozone:communication/communication@1.0.0#ozone-create-template
    case "communication-ozone-create-template":
      return xrpc("com.etzhayyim.apps.communication.ozoneCreateTemplate", entry.payload);
    // tools-ozone:communication/communication@1.0.0#ozone-delete-template
    case "communication-ozone-delete-template":
      return xrpc("com.etzhayyim.apps.communication.ozoneDeleteTemplate", entry.payload);
    // tools-ozone:communication/communication@1.0.0#ozone-list-templates
    case "communication-ozone-list-templates":
      return xrpc("com.etzhayyim.apps.communication.ozoneListTemplates", entry.payload);
    // tools-ozone:communication/communication@1.0.0#ozone-update-template
    case "communication-ozone-update-template":
      return xrpc("com.etzhayyim.apps.communication.ozoneUpdateTemplate", entry.payload);

    // ── kotodama:core/config@1.0.0 ──
    // kotodama:core/config@1.0.0#append
    case "config-append":
      return xrpc("com.etzhayyim.core.append", entry.payload);
    // kotodama:core/config@1.0.0#get
    case "config-get":
      return xrpc("com.etzhayyim.core.get", entry.payload);
    // kotodama:core/config@1.0.0#handle
    case "config-handle":
      return xrpc("com.etzhayyim.core.handle", entry.payload);
    // kotodama:core/config@1.0.0#send
    case "config-send":
      return xrpc("com.etzhayyim.core.send", entry.payload);

    // ── kotodama:consent/consent@1.0.0 ──
    // kotodama:consent/consent@1.0.0#assign-clearance
    case "consent-assign-clearance":
      return xrpc("com.etzhayyim.consent.assignClearance", entry.payload);
    // etzhayyim:consent/consent@1.0.0#request-consent
    case "consent-request-consent":
      return xrpc("com.etzhayyim.apps.consent.requestConsent", entry.payload);
    // etzhayyim:consent/consent@1.0.0#resolve-consent
    case "consent-resolve-consent":
      return xrpc("com.etzhayyim.apps.consent.resolveConsent", entry.payload);
    // kotodama:consent/consent@1.0.0#revoke-clearance
    case "consent-revoke-clearance":
      return xrpc("com.etzhayyim.consent.revokeClearance", entry.payload);
    // etzhayyim:consent/consent@1.0.0#revoke-consent
    case "consent-revoke-consent":
      return xrpc("com.etzhayyim.apps.consent.revokeConsent", entry.payload);

    // ── app-bsky:contact/contact@1.0.0 ──
    // app-bsky:contact/contact@1.0.0#dismiss-match
    case "contact-dismiss-match":
      return xrpc("com.etzhayyim.apps.contact.dismissMatch", entry.payload);
    // app-bsky:contact/contact@1.0.0#import-contacts
    case "contact-import-contacts":
      return xrpc("com.etzhayyim.apps.contact.importContacts", entry.payload);
    // app-bsky:contact/contact@1.0.0#remove-data
    case "contact-remove-data":
      return xrpc("com.etzhayyim.apps.contact.removeData", entry.payload);
    // app-bsky:contact/contact@1.0.0#send-notification
    case "contact-send-notification":
      return xrpc("com.etzhayyim.apps.contact.sendNotification", entry.payload);
    // app-bsky:contact/contact@1.0.0#start-phone-verification
    case "contact-start-phone-verification":
      return xrpc("com.etzhayyim.apps.contact.startPhoneVerification", entry.payload);
    // app-bsky:contact/contact@1.0.0#verify-phone
    case "contact-verify-phone":
      return xrpc("com.etzhayyim.apps.contact.verifyPhone", entry.payload);

    // ── chat-bsky:convo/convo@1.0.0 ──
    // chat-bsky:convo/convo@1.0.0#accept-convo
    case "convo-accept-convo":
      return xrpc("com.etzhayyim.apps.convo.acceptConvo", entry.payload);
    // chat-bsky:convo/convo@1.0.0#add-reaction
    case "convo-add-reaction":
      return xrpc("com.etzhayyim.apps.convo.addReaction", entry.payload);
    // etzhayyim:convo/convo@1.0.0#archive-convo
    case "convo-archive-convo":
      return xrpc("com.etzhayyim.apps.convo.archiveConvo", entry.payload);
    // etzhayyim:convo/convo@1.0.0#create-channel
    case "convo-create-channel":
      return xrpc("com.etzhayyim.apps.convo.createChannel", entry.payload);
    // etzhayyim:convo/convo@1.0.0#create-convo
    case "convo-create-convo":
      return xrpc("com.etzhayyim.apps.convo.createConvo", entry.payload);
    // etzhayyim:convo/convo@1.0.0#create-dm
    case "convo-create-dm":
      return xrpc("com.etzhayyim.apps.convo.createDm", entry.payload);
    // etzhayyim:convo/convo@1.0.0#create-session
    case "convo-create-session":
      return xrpc("com.etzhayyim.apps.convo.createSession", entry.payload);
    // chat-bsky:convo/convo@1.0.0#delete-message-for-self
    case "convo-delete-message-for-self":
      return xrpc("com.etzhayyim.apps.convo.deleteMessageForSelf", entry.payload);
    // etzhayyim:convo/convo@1.0.0#diff
    case "convo-diff":
      return xrpc("com.etzhayyim.apps.convo.diff", entry.payload);
    // etzhayyim:convo/convo@1.0.0#edit-message
    case "convo-edit-message":
      return xrpc("com.etzhayyim.apps.convo.editMessage", entry.payload);
    // etzhayyim:convo/convo@1.0.0#fetch-blocks
    case "convo-fetch-blocks":
      return xrpc("com.etzhayyim.apps.convo.fetchBlocks", entry.payload);
    // etzhayyim:convo/convo@1.0.0#invite-convo-member
    case "convo-invite-convo-member":
      return xrpc("com.etzhayyim.apps.convo.inviteConvoMember", entry.payload);
    // etzhayyim:convo/convo@1.0.0#join-convo
    case "convo-join-convo":
      return xrpc("com.etzhayyim.apps.convo.joinConvo", entry.payload);
    // etzhayyim:convo/convo@1.0.0#leave-convo
    case "convo-leave-convo":
      return xrpc("com.etzhayyim.apps.convo.leaveConvo", entry.payload);
    // etzhayyim:convo/convo@1.0.0#mark-read
    case "convo-mark-read":
      return xrpc("com.etzhayyim.apps.convo.markRead", entry.payload);
    // chat-bsky:convo/convo@1.0.0#mute-convo
    case "convo-mute-convo":
      return xrpc("com.etzhayyim.apps.convo.muteConvo", entry.payload);
    // etzhayyim:projector/projector@1.0.0#add-convo-member
    case "projector-add-convo-member":
      return xrpc("com.etzhayyim.projector.addConvoMember", entry.payload);
    // etzhayyim:projector/projector@1.0.0#add-convo-task
    case "projector-add-convo-task":
      return xrpc("com.etzhayyim.projector.addConvoTask", entry.payload);
    // etzhayyim:projector/projector@1.0.0#archive-project-convo
    case "projector-archive-project-convo":
      return xrpc("com.etzhayyim.projector.archiveProjectConvo", entry.payload);
    // etzhayyim:projector/projector@1.0.0#complete-convo-task
    case "projector-complete-convo-task":
      return xrpc("com.etzhayyim.projector.completeConvoTask", entry.payload);
    // etzhayyim:projector/projector@1.0.0#new-project-convo
    case "projector-new-project-convo":
      return xrpc("com.etzhayyim.projector.newProjectConvo", entry.payload);
    // etzhayyim:projector/projector@1.0.0#send-project-message
    case "projector-send-project-message":
      return xrpc("com.etzhayyim.projector.sendProjectMessage", entry.payload);
    // etzhayyim:projector/projector@1.0.0#update-project-convo
    case "projector-update-project-convo":
      return xrpc("com.etzhayyim.projector.updateProjectConvo", entry.payload);
    // etzhayyim:convo/convo@1.0.0#react
    case "convo-react":
      return xrpc("com.etzhayyim.apps.convo.react", entry.payload);
    // etzhayyim:convo/convo@1.0.0#redact-message
    case "convo-redact-message":
      return xrpc("com.etzhayyim.apps.convo.redactMessage", entry.payload);
    // chat-bsky:convo/convo@1.0.0#remove-reaction
    case "convo-remove-reaction":
      return xrpc("com.etzhayyim.apps.convo.removeReaction", entry.payload);
    // etzhayyim:convo/convo@1.0.0#search
    case "convo-search":
      return xrpc("com.etzhayyim.apps.convo.search", entry.payload);
    // etzhayyim:convo/convo@1.0.0#send
    case "convo-send":
      return xrpc("com.etzhayyim.apps.convo.send", entry.payload);
    // etzhayyim:convo/convo@1.0.0#send-message
    case "convo-send-message":
      return xrpc("com.etzhayyim.apps.convo.sendMessage", entry.payload);
    // chat-bsky:convo/convo@1.0.0#send-message-batch
    case "convo-send-message-batch":
      return xrpc("com.etzhayyim.apps.convo.sendMessageBatch", entry.payload);
    // etzhayyim:convo/convo@1.0.0#send-session-message
    case "convo-send-session-message":
      return xrpc("com.etzhayyim.apps.convo.sendSessionMessage", entry.payload);
    // etzhayyim:convo/convo@1.0.0#send-typing
    case "convo-send-typing":
      return xrpc("com.etzhayyim.apps.convo.sendTyping", entry.payload);
    // etzhayyim:convo/convo@1.0.0#set-convo-encryption
    case "convo-set-convo-encryption":
      return xrpc("com.etzhayyim.apps.convo.setConvoEncryption", entry.payload);
    // etzhayyim:convo/convo@1.0.0#set-profile
    case "convo-set-profile":
      return xrpc("com.etzhayyim.apps.convo.setProfile", entry.payload);
    // chat-bsky:convo/convo@1.0.0#unmute-convo
    case "convo-unmute-convo":
      return xrpc("com.etzhayyim.apps.convo.unmuteConvo", entry.payload);
    // etzhayyim:convo/convo@1.0.0#unreact
    case "convo-unreact":
      return xrpc("com.etzhayyim.apps.convo.unreact", entry.payload);
    // chat-bsky:convo/convo@1.0.0#update-all-read
    case "convo-update-all-read":
      return xrpc("com.etzhayyim.apps.convo.updateAllRead", entry.payload);
    // etzhayyim:convo/convo@1.0.0#update-convo
    case "convo-update-convo":
      return xrpc("com.etzhayyim.apps.convo.updateConvo", entry.payload);
    // etzhayyim:convo/convo@1.0.0#update-convo-member-role
    case "convo-update-convo-member-role":
      return xrpc("com.etzhayyim.apps.convo.updateConvoMemberRole", entry.payload);
    // etzhayyim:convo/convo@1.0.0#update-presence
    case "convo-update-presence":
      return xrpc("com.etzhayyim.apps.convo.updatePresence", entry.payload);
    // chat-bsky:convo/convo@1.0.0#update-read
    case "convo-update-read":
      return xrpc("com.etzhayyim.apps.convo.updateRead", entry.payload);

    // ── kotodama:graph/sql@1.0.0 ──
    // kotodama:graph/sql@1.0.0#batch-exec
    case "sql-batch-exec":
      return xrpc("com.etzhayyim.kagami.sql", entry.payload);
    // kotodama:graph/sql@1.0.0#create-index
    case "sql-create-index":
      return xrpc("com.etzhayyim.kagami.sql", entry.payload);
    // kotodama:graph/sql@1.0.0#query
    case "sql-query":
      return xrpc("com.etzhayyim.kagami.sql", entry.payload);
    // kotodama:graph/sql@1.0.0#search
    case "sql-search":
      return xrpc("com.etzhayyim.kagami.sql", entry.payload);
    // kotodama:graph/sql@1.0.0#write
    case "sql-write":
      return xrpc("com.etzhayyim.kagami.sql", entry.payload);

    // ── kotodama:cloudflare/d1@1.0.0 ──
    // kotodama:cloudflare/d1@1.0.0#accept-websocket
    case "d1-accept-websocket":
      return xrpc("com.etzhayyim.cloudflare.acceptWebsocket", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#block-concurrency-while
    case "d1-block-concurrency-while":
      return xrpc("com.etzhayyim.cloudflare.blockConcurrencyWhile", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#close
    case "d1-close":
      return xrpc("com.etzhayyim.cloudflare.close", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#connect
    case "d1-connect":
      return xrpc("com.etzhayyim.cloudflare.connect", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#database-size
    case "d1-database-size":
      return xrpc("com.etzhayyim.cloudflare.databaseSize", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#delete
    case "d1-delete":
      return xrpc("com.etzhayyim.cloudflare.delete", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#delete-alarm
    case "d1-delete-alarm":
      return xrpc("com.etzhayyim.cloudflare.deleteAlarm", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#delete-all
    case "d1-delete-all":
      return xrpc("com.etzhayyim.cloudflare.deleteAll", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#delete-multiple
    case "d1-delete-multiple":
      return xrpc("com.etzhayyim.cloudflare.deleteMultiple", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#dump
    case "d1-dump":
      return xrpc("com.etzhayyim.cloudflare.dump", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#exec
    case "d1-exec":
      return xrpc("com.etzhayyim.cloudflare.exec", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#fetch
    case "d1-fetch":
      return xrpc("com.etzhayyim.cloudflare.fetch", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#get
    case "d1-get":
      return xrpc("com.etzhayyim.cloudflare.get", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#id-from-name
    case "d1-id-from-name":
      return xrpc("com.etzhayyim.cloudflare.idFromName", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#new-unique-id
    case "d1-new-unique-id":
      return xrpc("com.etzhayyim.cloudflare.newUniqueId", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#put
    case "d1-put":
      return xrpc("com.etzhayyim.cloudflare.put", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#put-multiple
    case "d1-put-multiple":
      return xrpc("com.etzhayyim.cloudflare.putMultiple", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#send-binary
    case "d1-send-binary":
      return xrpc("com.etzhayyim.cloudflare.sendBinary", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#send-text
    case "d1-send-text":
      return xrpc("com.etzhayyim.cloudflare.sendText", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#set-alarm
    case "d1-set-alarm":
      return xrpc("com.etzhayyim.cloudflare.setAlarm", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#set-auto-response
    case "d1-set-auto-response":
      return xrpc("com.etzhayyim.cloudflare.setAutoResponse", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#sync
    case "d1-sync":
      return xrpc("com.etzhayyim.cloudflare.sync", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#transaction
    case "d1-transaction":
      return xrpc("com.etzhayyim.cloudflare.transaction", entry.payload);
    // kotodama:cloudflare/d1@1.0.0#wait-until
    case "d1-wait-until":
      return xrpc("com.etzhayyim.cloudflare.waitUntil", entry.payload);

    // ── kotodama:identity/dependency@1.0.0 ──
    // kotodama:identity/dependency@1.0.0#check
    case "dependency-check":
      return xrpc("com.etzhayyim.identity.check", entry.payload);
    // kotodama:identity/dependency@1.0.0#remove
    case "dependency-remove":
      return xrpc("com.etzhayyim.identity.remove", entry.payload);

    // ── kotodama:dmn/dmn@1.0.0 ──
    // kotodama:dmn/dmn@1.0.0#delete-model
    case "dmn-delete-model":
      return xrpc("com.etzhayyim.dmn.deleteModel", entry.payload);
    // kotodama:dmn/dmn@1.0.0#evaluate-feel
    case "dmn-evaluate-feel":
      return xrpc("com.etzhayyim.dmn.evaluateFeel", entry.payload);
    // kotodama:dmn/dmn@1.0.0#export-xml
    case "dmn-export-xml":
      return xrpc("com.etzhayyim.dmn.exportXml", entry.payload);
    // kotodama:dmn/dmn@1.0.0#test-unary
    case "dmn-test-unary":
      return xrpc("com.etzhayyim.dmn.testUnary", entry.payload);
    // kotodama:dmn/dmn@1.0.0#validate-feel
    case "dmn-validate-feel":
      return xrpc("com.etzhayyim.dmn.validateFeel", entry.payload);

    // ── kotodama:div/documents@1.0.0 ──
    // kotodama:div/documents@1.0.0#delete
    case "documents-delete":
      return xrpc("com.etzhayyim.div.delete", entry.payload);
    // kotodama:div/documents@1.0.0#query
    case "documents-query":
      return xrpc("com.etzhayyim.div.query", entry.payload);
    // kotodama:div/documents@1.0.0#store
    case "documents-store":
      return xrpc("com.etzhayyim.div.store", entry.payload);
    // kotodama:div/documents@1.0.0#store-batch
    case "documents-store-batch":
      return xrpc("com.etzhayyim.div.storeBatch", entry.payload);

    // ── app-bsky:draft/draft@1.0.0 ──
    // app-bsky:draft/draft@1.0.0#create-draft
    case "draft-create-draft":
      return xrpc("com.etzhayyim.apps.draft.createDraft", entry.payload);
    // app-bsky:draft/draft@1.0.0#delete-draft
    case "draft-delete-draft":
      return xrpc("com.etzhayyim.apps.draft.deleteDraft", entry.payload);
    // app-bsky:draft/draft@1.0.0#update-draft
    case "draft-update-draft":
      return xrpc("com.etzhayyim.apps.draft.updateDraft", entry.payload);

    // ── app-bsky:feed/feed@1.0.0 ──
    // app-bsky:feed/feed@1.0.0#remove-threadgate
    case "feed-remove-threadgate":
      return xrpc("com.etzhayyim.apps.feed.removeThreadgate", entry.payload);
    // app-bsky:feed/feed@1.0.0#send-interactions
    case "feed-send-interactions":
      return xrpc("com.etzhayyim.apps.feed.sendInteractions", entry.payload);
    // app-bsky:feed/feed@1.0.0#set-threadgate
    case "feed-set-threadgate":
      return xrpc("com.etzhayyim.apps.feed.setThreadgate", entry.payload);
    // app-bsky:feed/feed@1.0.0#unlike-post
    case "feed-unlike-post":
      return xrpc("com.etzhayyim.apps.feed.unlikePost", entry.payload);
    // app-bsky:feed/feed@1.0.0#unrepost
    case "feed-unrepost":
      return xrpc("com.etzhayyim.apps.feed.unrepost", entry.payload);

    // ── kotodama:forms/forms@1.0.0 ──
    // kotodama:forms/forms@1.0.0#create-form
    case "forms-create-form":
      return xrpc("com.etzhayyim.forms.createForm", entry.payload);
    // kotodama:forms/forms@1.0.0#delete-form
    case "forms-delete-form":
      return xrpc("com.etzhayyim.forms.deleteForm", entry.payload);
    // kotodama:forms/forms@1.0.0#evaluate-expression
    case "forms-evaluate-expression":
      return xrpc("com.etzhayyim.forms.evaluateExpression", entry.payload);
    // kotodama:forms/forms@1.0.0#submit-form
    case "forms-submit-form":
      return xrpc("com.etzhayyim.forms.submitForm", entry.payload);
    // kotodama:forms/forms@1.0.0#update-form
    case "forms-update-form":
      return xrpc("com.etzhayyim.forms.updateForm", entry.payload);
    // kotodama:forms/forms@1.0.0#validate-form
    case "forms-validate-form":
      return xrpc("com.etzhayyim.forms.validateForm", entry.payload);

    // ── kotodama:governance/governance@1.0.0 ──
    // kotodama:governance/governance@1.0.0#activities-for-function
    case "governance-activities-for-function":
      return xrpc("com.etzhayyim.governance.activitiesForFunction", entry.payload);
    // kotodama:governance/governance@1.0.0#assign-role
    case "governance-assign-role":
      return xrpc("com.etzhayyim.governance.assignRole", entry.payload);
    // kotodama:governance/governance@1.0.0#classify-data
    case "governance-classify-data":
      return xrpc("com.etzhayyim.governance.classifyData", entry.payload);
    // kotodama:governance/governance@1.0.0#declare-entity
    case "governance-declare-entity":
      return xrpc("com.etzhayyim.governance.declareEntity", entry.payload);
    // kotodama:governance/governance@1.0.0#declare-field
    case "governance-declare-field":
      return xrpc("com.etzhayyim.governance.declareField", entry.payload);
    // kotodama:governance/governance@1.0.0#declare-risk
    case "governance-declare-risk":
      return xrpc("com.etzhayyim.governance.declareRisk", entry.payload);
    // kotodama:governance/governance@1.0.0#declare-standard
    case "governance-declare-standard":
      return xrpc("com.etzhayyim.governance.declareStandard", entry.payload);
    // kotodama:governance/governance@1.0.0#declare-vendor
    case "governance-declare-vendor":
      return xrpc("com.etzhayyim.governance.declareVendor", entry.payload);
    // kotodama:governance/governance@1.0.0#define-role
    case "governance-define-role":
      return xrpc("com.etzhayyim.governance.defineRole", entry.payload);
    // kotodama:governance/governance@1.0.0#functions-for-activity
    case "governance-functions-for-activity":
      return xrpc("com.etzhayyim.governance.functionsForActivity", entry.payload);
    // kotodama:governance/governance@1.0.0#register
    case "governance-register":
      return xrpc("com.etzhayyim.governance.register", entry.payload);
    // kotodama:governance/governance@1.0.0#register-manifest
    case "governance-register-manifest":
      return xrpc("com.etzhayyim.governance.registerManifest", entry.payload);
    // etzhayyim:governance/governance@1.0.0#register-method-policy
    case "governance-register-method-policy":
      return xrpc("com.etzhayyim.apps.governance.registerMethodPolicy", entry.payload);
    // etzhayyim:governance/governance@1.0.0#register-policy
    case "governance-register-policy":
      return xrpc("com.etzhayyim.apps.governance.registerPolicy", entry.payload);
    // kotodama:governance/governance@1.0.0#remove
    case "governance-remove":
      return xrpc("com.etzhayyim.governance.remove", entry.payload);
    // kotodama:governance/governance@1.0.0#remove-risk
    case "governance-remove-risk":
      return xrpc("com.etzhayyim.governance.removeRisk", entry.payload);
    // kotodama:governance/governance@1.0.0#remove-role
    case "governance-remove-role":
      return xrpc("com.etzhayyim.governance.removeRole", entry.payload);
    // kotodama:governance/governance@1.0.0#remove-vendor
    case "governance-remove-vendor":
      return xrpc("com.etzhayyim.governance.removeVendor", entry.payload);
    // etzhayyim:governance/governance@1.0.0#resolve-actor-visibility
    case "governance-resolve-actor-visibility":
      return xrpc("com.etzhayyim.apps.governance.resolveActorVisibility", entry.payload);
    // kotodama:governance/governance@1.0.0#revoke-role
    case "governance-revoke-role":
      return xrpc("com.etzhayyim.governance.revokeRole", entry.payload);
    // etzhayyim:governance/governance@1.0.0#set-actor-sensitivity
    case "governance-set-actor-sensitivity":
      return xrpc("com.etzhayyim.apps.governance.setActorSensitivity", entry.payload);

    // ── app-bsky:graph/graph@1.0.0 ──
    // app-bsky:graph/graph@1.0.0#ack-feed
    case "graph-ack-feed":
      return xrpc("com.etzhayyim.apps.graph.ackFeed", entry.payload);
    // app-bsky:graph/graph@1.0.0#approve-all-follow-requests
    case "graph-approve-all-follow-requests":
      return xrpc("com.etzhayyim.apps.graph.approveAllFollowRequests", entry.payload);
    // app-bsky:graph/graph@1.0.0#approve-follow-request
    case "graph-approve-follow-request":
      return xrpc("com.etzhayyim.apps.graph.approveFollowRequest", entry.payload);
    // app-bsky:graph/graph@1.0.0#block-actor
    case "graph-block-actor":
      return xrpc("com.etzhayyim.apps.graph.blockActor", entry.payload);
    // app-bsky:graph/graph@1.0.0#follow
    case "graph-follow":
      return xrpc("com.etzhayyim.apps.graph.follow", entry.payload);
    // app-bsky:graph/graph@1.0.0#leaderboard
    case "graph-leaderboard":
      return xrpc("com.etzhayyim.apps.graph.leaderboard", entry.payload);
    // app-bsky:graph/graph@1.0.0#mute-actor
    case "graph-mute-actor":
      return xrpc("com.etzhayyim.apps.graph.muteActor", entry.payload);
    // app-bsky:graph/graph@1.0.0#mute-actor-list
    case "graph-mute-actor-list":
      return xrpc("com.etzhayyim.apps.graph.muteActorList", entry.payload);
    // app-bsky:graph/graph@1.0.0#mute-thread
    case "graph-mute-thread":
      return xrpc("com.etzhayyim.apps.graph.muteThread", entry.payload);
    // app-bsky:graph/graph@1.0.0#pull-feed
    case "graph-pull-feed":
      return xrpc("com.etzhayyim.apps.graph.pullFeed", entry.payload);
    // app-bsky:graph/graph@1.0.0#reject-follow-request
    case "graph-reject-follow-request":
      return xrpc("com.etzhayyim.apps.graph.rejectFollowRequest", entry.payload);
    // app-bsky:graph/graph@1.0.0#unblock-actor
    case "graph-unblock-actor":
      return xrpc("com.etzhayyim.apps.graph.unblockActor", entry.payload);
    // app-bsky:graph/graph@1.0.0#unfollow
    case "graph-unfollow":
      return xrpc("com.etzhayyim.apps.graph.unfollow", entry.payload);
    // app-bsky:graph/graph@1.0.0#unfollow-user
    case "graph-unfollow-user":
      return xrpc("com.etzhayyim.apps.graph.unfollowUser", entry.payload);
    // app-bsky:graph/graph@1.0.0#unmute-actor
    case "graph-unmute-actor":
      return xrpc("com.etzhayyim.apps.graph.unmuteActor", entry.payload);
    // app-bsky:graph/graph@1.0.0#unmute-actor-list
    case "graph-unmute-actor-list":
      return xrpc("com.etzhayyim.apps.graph.unmuteActorList", entry.payload);
    // app-bsky:graph/graph@1.0.0#unmute-thread
    case "graph-unmute-thread":
      return xrpc("com.etzhayyim.apps.graph.unmuteThread", entry.payload);

    // ── tools-ozone:hosting/hosting@1.0.0 ──
    // tools-ozone:hosting/hosting@1.0.0#ozone-get-account-history
    case "hosting-ozone-get-account-history":
      return xrpc("com.etzhayyim.apps.hosting.ozoneGetAccountHistory", entry.payload);

    // ── com-atproto:identity/identity@1.0.0 ──
    // com-atproto:identity/identity@1.0.0#create
    case "identity-create":
      return xrpc("com.etzhayyim.apps.identity.create", entry.payload);
    // com-atproto:identity/identity@1.0.0#create-record
    case "identity-create-record":
      return xrpc("com.etzhayyim.apps.identity.createRecord", entry.payload);
    // com-atproto:identity/identity@1.0.0#deactivate
    case "identity-deactivate":
      return xrpc("com.etzhayyim.apps.identity.deactivate", entry.payload);
    // com-atproto:identity/identity@1.0.0#delete-record
    case "identity-delete-record":
      return xrpc("com.etzhayyim.apps.identity.deleteRecord", entry.payload);
    // com-atproto:identity/identity@1.0.0#refresh-identity
    case "identity-refresh-identity":
      return xrpc("com.etzhayyim.apps.identity.refreshIdentity", entry.payload);
    // kotodama:identity/identity@1.0.0#register
    case "identity-register":
      return xrpc("com.etzhayyim.identity.register", entry.payload);
    // com-atproto:identity/identity@1.0.0#request-plc-operation-signature
    case "identity-request-plc-operation-signature":
      return xrpc("com.etzhayyim.apps.identity.requestPlcOperationSignature", entry.payload);
    // kotodama:identity/identity@1.0.0#resolve
    case "identity-resolve":
      return xrpc("com.etzhayyim.identity.resolve", entry.payload);
    // kotodama:identity/identity@1.0.0#resolve-address
    case "identity-resolve-address":
      return xrpc("com.etzhayyim.identity.resolveAddress", entry.payload);
    // com-atproto:identity/identity@1.0.0#resolve-did
    case "identity-resolve-did":
      return xrpc("com.etzhayyim.apps.identity.resolveDid", entry.payload);
    // com-atproto:identity/identity@1.0.0#resolve-handle
    case "identity-resolve-handle":
      return xrpc("com.etzhayyim.apps.identity.resolveHandle", entry.payload);
    // com-atproto:identity/identity@1.0.0#resolve-identity
    case "identity-resolve-identity":
      return xrpc("com.etzhayyim.apps.identity.resolveIdentity", entry.payload);
    // com-atproto:identity/identity@1.0.0#rotate-key
    case "identity-rotate-key":
      return xrpc("com.etzhayyim.apps.identity.rotateKey", entry.payload);
    // com-atproto:identity/identity@1.0.0#sign-plc-operation
    case "identity-sign-plc-operation":
      return xrpc("com.etzhayyim.apps.identity.signPlcOperation", entry.payload);
    // com-atproto:identity/identity@1.0.0#submit-plc-operation
    case "identity-submit-plc-operation":
      return xrpc("com.etzhayyim.apps.identity.submitPlcOperation", entry.payload);
    // com-atproto:identity/identity@1.0.0#update
    case "identity-update":
      return xrpc("com.etzhayyim.apps.identity.update", entry.payload);
    // com-atproto:identity/identity@1.0.0#update-handle
    case "identity-update-handle":
      return xrpc("com.etzhayyim.apps.identity.updateHandle", entry.payload);
    // com-atproto:identity/identity@1.0.0#update-record
    case "identity-update-record":
      return xrpc("com.etzhayyim.apps.identity.updateRecord", entry.payload);

    // ── etzhayyim:invoke/invoke@1.0.0 ──
    // etzhayyim:invoke/invoke@1.0.0#invoke
    case "invoke-invoke":
      return xrpc("com.etzhayyim.apps.invoke.invoke", entry.payload);
    // etzhayyim:invoke/invoke@1.0.0#invoke-stream
    case "invoke-invoke-stream":
      return xrpc("com.etzhayyim.apps.invoke.invokeStream", entry.payload);

    // ── etzhayyim:ipfs/ipfs-gateway@1.0.0 ──
    // etzhayyim:ipfs/ipfs-gateway@1.0.0#resolve
    case "ipfs-gateway-resolve":
      return xrpc("com.etzhayyim.apps.ipfs.resolve", entry.payload);

    // ── com-atproto:label/label@1.0.0 ──
    // com-atproto:label/label@1.0.0#create-label
    case "label-create-label":
      return xrpc("com.etzhayyim.apps.label.createLabel", entry.payload);
    // com-atproto:label/label@1.0.0#declare-labeler
    case "label-declare-labeler":
      return xrpc("com.etzhayyim.apps.label.declareLabeler", entry.payload);
    // com-atproto:label/label@1.0.0#set-content-pref
    case "label-set-content-pref":
      return xrpc("com.etzhayyim.apps.label.setContentPref", entry.payload);
    // com-atproto:label/label@1.0.0#subscribe-labels
    case "label-subscribe-labels":
      return xrpc("com.etzhayyim.apps.label.subscribeLabels", entry.payload);
    // com-atproto:label/label@1.0.0#unsubscribe-labeler
    case "label-unsubscribe-labeler":
      return xrpc("com.etzhayyim.apps.label.unsubscribeLabeler", entry.payload);

    // ── com-atproto:lexicon/lexicon@1.0.0 ──
    // com-atproto:lexicon/lexicon@1.0.0#resolve-lexicon
    case "lexicon-resolve-lexicon":
      return xrpc("com.etzhayyim.apps.lexicon.resolveLexicon", entry.payload);

    // ── tools-ozone:moderation/moderation@1.0.0 ──
    // tools-ozone:moderation/moderation@1.0.0#ozone-cancel-scheduled-actions
    case "moderation-ozone-cancel-scheduled-actions":
      return xrpc("com.etzhayyim.apps.moderation.ozoneCancelScheduledActions", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-emit-event
    case "moderation-ozone-emit-event":
      return xrpc("com.etzhayyim.apps.moderation.ozoneEmitEvent", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-account-timeline
    case "moderation-ozone-get-account-timeline":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetAccountTimeline", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-event
    case "moderation-ozone-get-event":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetEvent", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-record
    case "moderation-ozone-get-record":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetRecord", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-records
    case "moderation-ozone-get-records":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetRecords", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-repo
    case "moderation-ozone-get-repo":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetRepo", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-reporter-stats
    case "moderation-ozone-get-reporter-stats":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetReporterStats", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-repos
    case "moderation-ozone-get-repos":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetRepos", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-get-subjects
    case "moderation-ozone-get-subjects":
      return xrpc("com.etzhayyim.apps.moderation.ozoneGetSubjects", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-list-scheduled-actions
    case "moderation-ozone-list-scheduled-actions":
      return xrpc("com.etzhayyim.apps.moderation.ozoneListScheduledActions", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-query-events
    case "moderation-ozone-query-events":
      return xrpc("com.etzhayyim.apps.moderation.ozoneQueryEvents", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-query-statuses
    case "moderation-ozone-query-statuses":
      return xrpc("com.etzhayyim.apps.moderation.ozoneQueryStatuses", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-schedule-action
    case "moderation-ozone-schedule-action":
      return xrpc("com.etzhayyim.apps.moderation.ozoneScheduleAction", entry.payload);
    // tools-ozone:moderation/moderation@1.0.0#ozone-search-repos
    case "moderation-ozone-search-repos":
      return xrpc("com.etzhayyim.apps.moderation.ozoneSearchRepos", entry.payload);
    // com-atproto:moderation/moderation@1.0.0#report-content
    case "moderation-report-content":
      return xrpc("com.etzhayyim.apps.moderation.reportContent", entry.payload);
    // chat-bsky:moderation/moderation@1.0.0#update-chat-actor-access
    case "moderation-update-chat-actor-access":
      return xrpc("com.etzhayyim.apps.moderation.updateChatActorAccess", entry.payload);

    // ── app-bsky:notification/notification@1.0.0 ──
    // app-bsky:notification/notification@1.0.0#put-activity-subscription
    case "notification-put-activity-subscription":
      return xrpc("com.etzhayyim.apps.notification.putActivitySubscription", entry.payload);
    // app-bsky:notification/notification@1.0.0#put-notification-preferences
    case "notification-put-notification-preferences":
      return xrpc("com.etzhayyim.apps.notification.putNotificationPreferences", entry.payload);
    // app-bsky:notification/notification@1.0.0#put-notification-preferences-v2
    case "notification-put-notification-preferences-v2":
      return xrpc("com.etzhayyim.apps.notification.putNotificationPreferencesV2", entry.payload);
    // app-bsky:notification/notification@1.0.0#register-push
    case "notification-register-push":
      return xrpc("com.etzhayyim.apps.notification.registerPush", entry.payload);
    // app-bsky:notification/notification@1.0.0#unregister-push
    case "notification-unregister-push":
      return xrpc("com.etzhayyim.apps.notification.unregisterPush", entry.payload);
    // app-bsky:notification/notification@1.0.0#update-seen
    case "notification-update-seen":
      return xrpc("com.etzhayyim.apps.notification.updateSeen", entry.payload);

    // ── etzhayyim:states/organization-directory@0.1.0 ──
    // etzhayyim:states/organization-directory@0.1.0#receive-inter-org-message
    case "organization-directory-receive-inter-org-message":
      return xrpc("com.etzhayyim.apps.states.receiveInterOrgMessage", entry.payload);
    // etzhayyim:states/organization-directory@0.1.0#send-inter-org-message
    case "organization-directory-send-inter-org-message":
      return xrpc("com.etzhayyim.apps.states.sendInterOrgMessage", entry.payload);
    // kotodama:dm2/organization@1.0.0#register
    case "organization-register":
      return xrpc("com.etzhayyim.dm2.register", entry.payload);
    // kotodama:dm2/organization@1.0.0#resolve
    case "organization-resolve":
      return xrpc("com.etzhayyim.dm2.resolve", entry.payload);
    // kotodama:dm2/organization@1.0.0#resolve-lineage
    case "organization-resolve-lineage":
      return xrpc("com.etzhayyim.dm2.resolveLineage", entry.payload);
    // kotodama:dm2/organization@1.0.0#upsert
    case "organization-upsert":
      return xrpc("com.etzhayyim.dm2.upsert", entry.payload);

    // ── kotodama:pubsub/pubsub@1.0.0 ──
    // kotodama:pubsub/pubsub@1.0.0#ack
    case "pubsub-ack":
      return xrpc("com.etzhayyim.pubsub.ack", entry.payload);
    // kotodama:pubsub/pubsub@1.0.0#cursor
    case "pubsub-cursor":
      return xrpc("com.etzhayyim.pubsub.cursor", entry.payload);
    // kotodama:pubsub/pubsub@1.0.0#publish
    case "pubsub-publish":
      return xrpc("com.etzhayyim.pubsub.publish", entry.payload);
    // kotodama:pubsub/pubsub@1.0.0#pull
    case "pubsub-pull":
      return xrpc("com.etzhayyim.pubsub.pull", entry.payload);

    // ── kotodama:coverage/query@1.0.0 ──
    // kotodama:coverage/query@1.0.0#report-dimension
    case "query-report-dimension":
      return xrpc("com.etzhayyim.coverage.reportDimension", entry.payload);
    // kotodama:coverage/query@1.0.0#report-gap
    case "query-report-gap":
      return xrpc("com.etzhayyim.coverage.reportGap", entry.payload);
    // kotodama:coverage/query@1.0.0#scan
    case "query-scan":
      return xrpc("com.etzhayyim.coverage.scan", entry.payload);

    // ── com-atproto:repo/repo@1.0.0 ──
    // com-atproto:repo/repo@1.0.0#apply-writes
    case "repo-apply-writes":
      return xrpc("com.etzhayyim.apps.repo.applyWrites", entry.payload);
    // com-atproto:repo/repo@1.0.0#create-follow
    case "repo-create-follow":
      return xrpc("com.etzhayyim.apps.repo.createFollow", entry.payload);
    // com-atproto:repo/repo@1.0.0#create-like
    case "repo-create-like":
      return xrpc("com.etzhayyim.apps.repo.createLike", entry.payload);
    // com-atproto:repo/repo@1.0.0#create-post
    case "repo-create-post":
      return xrpc("com.etzhayyim.apps.repo.createPost", entry.payload);
    // com-atproto:repo/repo@1.0.0#create-record
    case "repo-create-record":
      return xrpc("com.etzhayyim.apps.repo.createRecord", entry.payload);
    // com-atproto:repo/repo@1.0.0#create-repost
    case "repo-create-repost":
      return xrpc("com.etzhayyim.apps.repo.createRepost", entry.payload);
    // com-atproto:repo/repo@1.0.0#delete-record
    case "repo-delete-record":
      return xrpc("com.etzhayyim.apps.repo.deleteRecord", entry.payload);
    // com-atproto:repo/repo@1.0.0#import-repo
    case "repo-import-repo":
      return xrpc("com.etzhayyim.apps.repo.importRepo", entry.payload);
    // com-atproto:repo/repo@1.0.0#put-profile
    case "repo-put-profile":
      return xrpc("com.etzhayyim.apps.repo.putProfile", entry.payload);
    // com-atproto:repo/repo@1.0.0#put-record
    case "repo-put-record":
      return xrpc("com.etzhayyim.apps.repo.putRecord", entry.payload);
    // com-atproto:repo/repo@1.0.0#upload-blob
    case "repo-upload-blob":
      return xrpc("com.etzhayyim.apps.repo.uploadBlob", entry.payload);

    // ── kotodama:rpc/resilience@1.0.0 ──
    // kotodama:rpc/resilience@1.0.0#record-failure
    case "resilience-record-failure":
      return xrpc("com.etzhayyim.rpc.recordFailure", entry.payload);
    // kotodama:rpc/resilience@1.0.0#record-success
    case "resilience-record-success":
      return xrpc("com.etzhayyim.rpc.recordSuccess", entry.payload);
    // kotodama:rpc/resilience@1.0.0#register-breaker
    case "resilience-register-breaker":
      return xrpc("com.etzhayyim.rpc.registerBreaker", entry.payload);
    // kotodama:rpc/resilience@1.0.0#register-health-check
    case "resilience-register-health-check":
      return xrpc("com.etzhayyim.rpc.registerHealthCheck", entry.payload);
    // kotodama:rpc/resilience@1.0.0#report-health
    case "resilience-report-health":
      return xrpc("com.etzhayyim.rpc.reportHealth", entry.payload);

    // ── etzhayyim:rtc/rtc@1.0.0 ──
    // etzhayyim:rtc/rtc@1.0.0#hangup-call
    case "rtc-hangup-call":
      return xrpc("com.etzhayyim.apps.rtc.hangupCall", entry.payload);
    // etzhayyim:rtc/rtc@1.0.0#send-call-answer
    case "rtc-send-call-answer":
      return xrpc("com.etzhayyim.apps.rtc.sendCallAnswer", entry.payload);
    // etzhayyim:rtc/rtc@1.0.0#send-call-ice
    case "rtc-send-call-ice":
      return xrpc("com.etzhayyim.apps.rtc.sendCallIce", entry.payload);
    // etzhayyim:rtc/rtc@1.0.0#send-call-offer
    case "rtc-send-call-offer":
      return xrpc("com.etzhayyim.apps.rtc.sendCallOffer", entry.payload);
    // etzhayyim:rtc/rtc@1.0.0#subscribe-push
    case "rtc-subscribe-push":
      return xrpc("com.etzhayyim.apps.rtc.subscribePush", entry.payload);
    // etzhayyim:rtc/rtc@1.0.0#unsubscribe-push
    case "rtc-unsubscribe-push":
      return xrpc("com.etzhayyim.apps.rtc.unsubscribePush", entry.payload);

    // ── tools-ozone:safelink/safelink@1.0.0 ──
    // tools-ozone:safelink/safelink@1.0.0#ozone-safelink-add-rule
    case "safelink-ozone-safelink-add-rule":
      return xrpc("com.etzhayyim.apps.safelink.ozoneSafelinkAddRule", entry.payload);
    // tools-ozone:safelink/safelink@1.0.0#ozone-safelink-query-events
    case "safelink-ozone-safelink-query-events":
      return xrpc("com.etzhayyim.apps.safelink.ozoneSafelinkQueryEvents", entry.payload);
    // tools-ozone:safelink/safelink@1.0.0#ozone-safelink-query-rules
    case "safelink-ozone-safelink-query-rules":
      return xrpc("com.etzhayyim.apps.safelink.ozoneSafelinkQueryRules", entry.payload);
    // tools-ozone:safelink/safelink@1.0.0#ozone-safelink-remove-rule
    case "safelink-ozone-safelink-remove-rule":
      return xrpc("com.etzhayyim.apps.safelink.ozoneSafelinkRemoveRule", entry.payload);
    // tools-ozone:safelink/safelink@1.0.0#ozone-safelink-update-rule
    case "safelink-ozone-safelink-update-rule":
      return xrpc("com.etzhayyim.apps.safelink.ozoneSafelinkUpdateRule", entry.payload);

    // ── kotodama:secrets/secrets@1.0.0 ──
    // kotodama:secrets/secrets@1.0.0#create-vault
    case "secrets-create-vault":
      return xrpc("com.etzhayyim.secrets.createVault", entry.payload);
    // kotodama:secrets/secrets@1.0.0#delete
    case "secrets-delete":
      return xrpc("com.etzhayyim.secrets.delete", entry.payload);
    // kotodama:secrets/secrets@1.0.0#delete-item
    case "secrets-delete-item":
      return xrpc("com.etzhayyim.secrets.deleteItem", entry.payload);
    // kotodama:secrets/secrets@1.0.0#fetch-delegated
    case "secrets-fetch-delegated":
      return xrpc("com.etzhayyim.secrets.fetchDelegated", entry.payload);
    // kotodama:secrets/secrets@1.0.0#get
    case "secrets-get":
      return xrpc("com.etzhayyim.secrets.get", entry.payload);
    // kotodama:secrets/secrets@1.0.0#put-item
    case "secrets-put-item":
      return xrpc("com.etzhayyim.secrets.putItem", entry.payload);
    // kotodama:secrets/secrets@1.0.0#remove-member
    case "secrets-remove-member":
      return xrpc("com.etzhayyim.secrets.removeMember", entry.payload);
    // kotodama:secrets/secrets@1.0.0#revoke-delegation
    case "secrets-revoke-delegation":
      return xrpc("com.etzhayyim.secrets.revokeDelegation", entry.payload);
    // kotodama:secrets/secrets@1.0.0#set
    case "secrets-set":
      return xrpc("com.etzhayyim.secrets.set", entry.payload);

    // ── etzhayyim:serve/serve@1.0.0 ──
    // etzhayyim:serve/serve@1.0.0#handle
    case "serve-handle":
      return xrpc("com.etzhayyim.apps.serve.handle", entry.payload);
    // etzhayyim:serve/serve@1.0.0#handle-stream
    case "serve-handle-stream":
      return xrpc("com.etzhayyim.apps.serve.handleStream", entry.payload);

    // ── com-atproto:server/server@1.0.0 ──
    // com-atproto:server/server@1.0.0#activate-account
    case "server-activate-account":
      return xrpc("com.etzhayyim.apps.server.activateAccount", entry.payload);
    // com-atproto:server/server@1.0.0#confirm-email
    case "server-confirm-email":
      return xrpc("com.etzhayyim.apps.server.confirmEmail", entry.payload);
    // com-atproto:server/server@1.0.0#create-account
    case "server-create-account":
      return xrpc("com.etzhayyim.apps.server.createAccount", entry.payload);
    // com-atproto:server/server@1.0.0#create-app-password
    case "server-create-app-password":
      return xrpc("com.etzhayyim.apps.server.createAppPassword", entry.payload);
    // com-atproto:server/server@1.0.0#create-invite-code
    case "server-create-invite-code":
      return xrpc("com.etzhayyim.apps.server.createInviteCode", entry.payload);
    // com-atproto:server/server@1.0.0#create-invite-codes
    case "server-create-invite-codes":
      return xrpc("com.etzhayyim.apps.server.createInviteCodes", entry.payload);
    // com-atproto:server/server@1.0.0#create-session
    case "server-create-session":
      return xrpc("com.etzhayyim.apps.server.createSession", entry.payload);
    // com-atproto:server/server@1.0.0#deactivate-account
    case "server-deactivate-account":
      return xrpc("com.etzhayyim.apps.server.deactivateAccount", entry.payload);
    // com-atproto:server/server@1.0.0#delete-account
    case "server-delete-account":
      return xrpc("com.etzhayyim.apps.server.deleteAccount", entry.payload);
    // com-atproto:server/server@1.0.0#delete-session
    case "server-delete-session":
      return xrpc("com.etzhayyim.apps.server.deleteSession", entry.payload);
    // tools-ozone:server/server@1.0.0#ozone-get-config
    case "server-ozone-get-config":
      return xrpc("com.etzhayyim.apps.server.ozoneGetConfig", entry.payload);
    // com-atproto:server/server@1.0.0#refresh-session
    case "server-refresh-session":
      return xrpc("com.etzhayyim.apps.server.refreshSession", entry.payload);
    // com-atproto:server/server@1.0.0#request-account-delete
    case "server-request-account-delete":
      return xrpc("com.etzhayyim.apps.server.requestAccountDelete", entry.payload);
    // com-atproto:server/server@1.0.0#request-email-confirmation
    case "server-request-email-confirmation":
      return xrpc("com.etzhayyim.apps.server.requestEmailConfirmation", entry.payload);
    // com-atproto:server/server@1.0.0#request-email-update
    case "server-request-email-update":
      return xrpc("com.etzhayyim.apps.server.requestEmailUpdate", entry.payload);
    // com-atproto:server/server@1.0.0#request-password-reset
    case "server-request-password-reset":
      return xrpc("com.etzhayyim.apps.server.requestPasswordReset", entry.payload);
    // com-atproto:server/server@1.0.0#reserve-signing-key
    case "server-reserve-signing-key":
      return xrpc("com.etzhayyim.apps.server.reserveSigningKey", entry.payload);
    // com-atproto:server/server@1.0.0#reset-password
    case "server-reset-password":
      return xrpc("com.etzhayyim.apps.server.resetPassword", entry.payload);
    // com-atproto:server/server@1.0.0#revoke-app-password
    case "server-revoke-app-password":
      return xrpc("com.etzhayyim.apps.server.revokeAppPassword", entry.payload);
    // com-atproto:server/server@1.0.0#update-email
    case "server-update-email":
      return xrpc("com.etzhayyim.apps.server.updateEmail", entry.payload);

    // ── tools-ozone:set/set@1.0.0 ──
    // tools-ozone:set/set@1.0.0#ozone-set-add-values
    case "set-ozone-set-add-values":
      return xrpc("com.etzhayyim.apps.set.ozoneSetAddValues", entry.payload);
    // tools-ozone:set/set@1.0.0#ozone-set-delete-set
    case "set-ozone-set-delete-set":
      return xrpc("com.etzhayyim.apps.set.ozoneSetDeleteSet", entry.payload);
    // tools-ozone:set/set@1.0.0#ozone-set-delete-values
    case "set-ozone-set-delete-values":
      return xrpc("com.etzhayyim.apps.set.ozoneSetDeleteValues", entry.payload);
    // tools-ozone:set/set@1.0.0#ozone-set-get-values
    case "set-ozone-set-get-values":
      return xrpc("com.etzhayyim.apps.set.ozoneSetGetValues", entry.payload);
    // tools-ozone:set/set@1.0.0#ozone-set-query-sets
    case "set-ozone-set-query-sets":
      return xrpc("com.etzhayyim.apps.set.ozoneSetQuerySets", entry.payload);
    // tools-ozone:set/set@1.0.0#ozone-set-upsert-set
    case "set-ozone-set-upsert-set":
      return xrpc("com.etzhayyim.apps.set.ozoneSetUpsertSet", entry.payload);

    // ── tools-ozone:setting/setting@1.0.0 ──
    // tools-ozone:setting/setting@1.0.0#ozone-setting-list-options
    case "setting-ozone-setting-list-options":
      return xrpc("com.etzhayyim.apps.setting.ozoneSettingListOptions", entry.payload);
    // tools-ozone:setting/setting@1.0.0#ozone-setting-remove-options
    case "setting-ozone-setting-remove-options":
      return xrpc("com.etzhayyim.apps.setting.ozoneSettingRemoveOptions", entry.payload);
    // tools-ozone:setting/setting@1.0.0#ozone-setting-upsert-option
    case "setting-ozone-setting-upsert-option":
      return xrpc("com.etzhayyim.apps.setting.ozoneSettingUpsertOption", entry.payload);

    // ── etzhayyim:kotodama/shinka@1.0.0 ──
    // etzhayyim:kotodama/shinka@1.0.0#on-follow-request
    case "shinka-on-follow-request":
      return xrpc("com.etzhayyim.apps.kotodama.onFollowRequest", entry.payload);
    // etzhayyim:kotodama/shinka@1.0.0#on-heartbeat
    case "shinka-on-heartbeat":
      return xrpc("com.etzhayyim.apps.kotodama.onHeartbeat", entry.payload);
    // etzhayyim:kotodama/shinka@1.0.0#on-new-follower
    case "shinka-on-new-follower":
      return xrpc("com.etzhayyim.apps.kotodama.onNewFollower", entry.payload);
    // etzhayyim:kotodama/shinka@1.0.0#on-reaction
    case "shinka-on-reaction":
      return xrpc("com.etzhayyim.apps.kotodama.onReaction", entry.payload);

    // ── etzhayyim:signal/signal@1.0.0 ──
    // etzhayyim:signal/signal@1.0.0#build-pre-key-bundle
    case "signal-build-pre-key-bundle":
      return xrpc("com.etzhayyim.apps.signal.buildPreKeyBundle", entry.payload);
    // etzhayyim:signal/signal@1.0.0#generate-identity
    case "signal-generate-identity":
      return xrpc("com.etzhayyim.apps.signal.generateIdentity", entry.payload);
    // etzhayyim:signal/signal@1.0.0#generate-one-time-prekey
    case "signal-generate-one-time-prekey":
      return xrpc("com.etzhayyim.apps.signal.generateOneTimePrekey", entry.payload);
    // etzhayyim:signal/signal@1.0.0#generate-signed-prekey
    case "signal-generate-signed-prekey":
      return xrpc("com.etzhayyim.apps.signal.generateSignedPrekey", entry.payload);
    // etzhayyim:signal/signal@1.0.0#group-decrypt
    case "signal-group-decrypt":
      return xrpc("com.etzhayyim.apps.signal.groupDecrypt", entry.payload);
    // etzhayyim:signal/signal@1.0.0#group-encrypt
    case "signal-group-encrypt":
      return xrpc("com.etzhayyim.apps.signal.groupEncrypt", entry.payload);
    // etzhayyim:signal/signal@1.0.0#group-init-sender
    case "signal-group-init-sender":
      return xrpc("com.etzhayyim.apps.signal.groupInitSender", entry.payload);
    // etzhayyim:signal/signal@1.0.0#group-process-distribution
    case "signal-group-process-distribution":
      return xrpc("com.etzhayyim.apps.signal.groupProcessDistribution", entry.payload);
    // etzhayyim:signal/signal@1.0.0#ratchet-decrypt
    case "signal-ratchet-decrypt":
      return xrpc("com.etzhayyim.apps.signal.ratchetDecrypt", entry.payload);
    // etzhayyim:signal/signal@1.0.0#ratchet-encrypt
    case "signal-ratchet-encrypt":
      return xrpc("com.etzhayyim.apps.signal.ratchetEncrypt", entry.payload);
    // etzhayyim:signal/signal@1.0.0#ratchet-init-receiver
    case "signal-ratchet-init-receiver":
      return xrpc("com.etzhayyim.apps.signal.ratchetInitReceiver", entry.payload);
    // etzhayyim:signal/signal@1.0.0#ratchet-init-sender
    case "signal-ratchet-init-sender":
      return xrpc("com.etzhayyim.apps.signal.ratchetInitSender", entry.payload);
    // etzhayyim:signal/signal@1.0.0#x3dh-initiate
    case "signal-x3dh-initiate":
      return xrpc("com.etzhayyim.apps.signal.x3dhInitiate", entry.payload);
    // etzhayyim:signal/signal@1.0.0#x3dh-respond
    case "signal-x3dh-respond":
      return xrpc("com.etzhayyim.apps.signal.x3dhRespond", entry.payload);

    // ── tools-ozone:signature/signature@1.0.0 ──
    // tools-ozone:signature/signature@1.0.0#ozone-signature-find-correlation
    case "signature-ozone-signature-find-correlation":
      return xrpc("com.etzhayyim.apps.signature.ozoneSignatureFindCorrelation", entry.payload);
    // tools-ozone:signature/signature@1.0.0#ozone-signature-find-related-accounts
    case "signature-ozone-signature-find-related-accounts":
      return xrpc("com.etzhayyim.apps.signature.ozoneSignatureFindRelatedAccounts", entry.payload);
    // tools-ozone:signature/signature@1.0.0#ozone-signature-search-accounts
    case "signature-ozone-signature-search-accounts":
      return xrpc("com.etzhayyim.apps.signature.ozoneSignatureSearchAccounts", entry.payload);

    // ── kotodama:identity/source@1.0.0 ──
    // kotodama:identity/source@1.0.0#deactivate
    case "source-deactivate":
      return xrpc("com.etzhayyim.identity.deactivate", entry.payload);
    // kotodama:identity/source@1.0.0#get
    case "source-get":
      return xrpc("com.etzhayyim.identity.get", entry.payload);
    // kotodama:identity/source@1.0.0#list
    case "source-list":
      return xrpc("com.etzhayyim.identity.list", entry.payload);
    // kotodama:identity/source@1.0.0#register
    case "source-register":
      return xrpc("com.etzhayyim.identity.register", entry.payload);
    // kotodama:identity/source@1.0.0#update
    case "source-update":
      return xrpc("com.etzhayyim.identity.update", entry.payload);

    // ── etzhayyim:wrpc/stream@1.0.0 ──
    // etzhayyim:wrpc/stream@1.0.0#close
    case "stream-close":
      return xrpc("com.etzhayyim.apps.wrpc.close", entry.payload);

    // ── com-atproto:sync/subscribe-repos@1.0.0 ──
    // com-atproto:sync/subscribe-repos@1.0.0#handle-commit
    case "subscribe-repos-handle-commit":
      return xrpc("com.etzhayyim.apps.sync.handleCommit", entry.payload);

    // ── tools-ozone:team/team@1.0.0 ──
    // tools-ozone:team/team@1.0.0#ozone-team-add-member
    case "team-ozone-team-add-member":
      return xrpc("com.etzhayyim.apps.team.ozoneTeamAddMember", entry.payload);
    // tools-ozone:team/team@1.0.0#ozone-team-delete-member
    case "team-ozone-team-delete-member":
      return xrpc("com.etzhayyim.apps.team.ozoneTeamDeleteMember", entry.payload);
    // tools-ozone:team/team@1.0.0#ozone-team-list-members
    case "team-ozone-team-list-members":
      return xrpc("com.etzhayyim.apps.team.ozoneTeamListMembers", entry.payload);
    // tools-ozone:team/team@1.0.0#ozone-team-update-member
    case "team-ozone-team-update-member":
      return xrpc("com.etzhayyim.apps.team.ozoneTeamUpdateMember", entry.payload);

    // ── kotodama:trust/trust-policy@1.0.0 ──
    // kotodama:trust/trust-policy@1.0.0#batch-score
    case "trust-policy-batch-score":
      return xrpc("com.etzhayyim.trust.batchScore", entry.payload);
    // kotodama:trust/trust-policy@1.0.0#declare-requirements
    case "trust-policy-declare-requirements":
      return xrpc("com.etzhayyim.trust.declareRequirements", entry.payload);
    // kotodama:trust/trust-policy@1.0.0#detail
    case "trust-policy-detail":
      return xrpc("com.etzhayyim.trust.detail", entry.payload);
    // kotodama:trust/trust-policy@1.0.0#history
    case "trust-policy-history":
      return xrpc("com.etzhayyim.trust.history", entry.payload);
    // kotodama:trust/trust-policy@1.0.0#leaderboard
    case "trust-policy-leaderboard":
      return xrpc("com.etzhayyim.trust.leaderboard", entry.payload);
    // kotodama:trust/trust-policy@1.0.0#score
    case "trust-policy-score":
      return xrpc("com.etzhayyim.trust.score", entry.payload);

    // ── tools-ozone:verification/verification@1.0.0 ──
    // tools-ozone:verification/verification@1.0.0#ozone-grant-verifications
    case "verification-ozone-grant-verifications":
      return xrpc("com.etzhayyim.apps.verification.ozoneGrantVerifications", entry.payload);
    // tools-ozone:verification/verification@1.0.0#ozone-list-verifications
    case "verification-ozone-list-verifications":
      return xrpc("com.etzhayyim.apps.verification.ozoneListVerifications", entry.payload);
    // tools-ozone:verification/verification@1.0.0#ozone-revoke-verifications
    case "verification-ozone-revoke-verifications":
      return xrpc("com.etzhayyim.apps.verification.ozoneRevokeVerifications", entry.payload);

    // ── app-bsky:video/video@1.0.0 ──
    // app-bsky:video/video@1.0.0#upload-video
    case "video-upload-video":
      return xrpc("com.etzhayyim.apps.video.uploadVideo", entry.payload);

    // ── kotodama:web3/wallet@1.0.0 ──
    // kotodama:web3/wallet@1.0.0#estimate-gas
    case "wallet-estimate-gas":
      return xrpc("com.etzhayyim.web3.estimateGas", entry.payload);
    // kotodama:web3/wallet@1.0.0#send-eth
    case "wallet-send-eth":
      return xrpc("com.etzhayyim.web3.sendEth", entry.payload);
    // kotodama:web3/wallet@1.0.0#send-transaction
    case "wallet-send-transaction":
      return xrpc("com.etzhayyim.web3.sendTransaction", entry.payload);
    // kotodama:web3/wallet@1.0.0#sign-message
    case "wallet-sign-message":
      return xrpc("com.etzhayyim.web3.signMessage", entry.payload);
    // kotodama:web3/wallet@1.0.0#sign-typed-data
    case "wallet-sign-typed-data":
      return xrpc("com.etzhayyim.web3.signTypedData", entry.payload);
    // kotodama:web3/wallet@1.0.0#transfer-gcc
    case "wallet-transfer-gcc":
      return xrpc("com.etzhayyim.web3.transferGcc", entry.payload);
    // kotodama:web3/wallet@1.0.0#transfer-token
    case "wallet-transfer-token":
      return xrpc("com.etzhayyim.web3.transferToken", entry.payload);
    // kotodama:web3/wallet@1.0.0#verify-message
    case "wallet-verify-message":
      return xrpc("com.etzhayyim.web3.verifyMessage", entry.payload);

    // ── etzhayyim:wrpc-stream/wrpc-stream@1.0.0 ──
    // etzhayyim:wrpc-stream/wrpc-stream@1.0.0#close
    case "wrpc-stream-close":
      return xrpc("com.etzhayyim.apps.wrpc-stream.close", entry.payload);
    // etzhayyim:wrpc-stream/wrpc-stream@1.0.0#has-next
    case "wrpc-stream-has-next":
      return xrpc("com.etzhayyim.apps.wrpc-stream.hasNext", entry.payload);
    // etzhayyim:wrpc-stream/wrpc-stream@1.0.0#read
    case "wrpc-stream-read":
      return xrpc("com.etzhayyim.apps.wrpc-stream.read", entry.payload);

    // ── etzhayyim:yata/yata@1.0.0 ──
    // etzhayyim:yata/yata@1.0.0#graph-exec
    case "yata-graph-exec":
      return xrpc("com.etzhayyim.apps.yata.graphExec", entry.payload);

    default:
      console.warn(`[wrpc-binding] unknown write buffer entry type: ${entry.type}`);
  }
}
