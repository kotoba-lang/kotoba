import type {
  AppDef,
  ActorCard,
  ActorAddress,
  ToolDescriptor,
  ActorCapability,
  GovernanceManifest,
  CommandPolicy,
  RACIAssignee,
  AgentToolDef,
} from "./types.js";
import { RACIRole, AssigneeKind } from "./types.js";
import { humanizeIdentifier, inferCommandVerb, normalizeTag, dedupeStrings, firstNonEmpty } from "./helpers.js";
import type { CommandEntry } from "./app-options.js";

export function buildActorCardFromCommands(def: AppDef, commands: CommandEntry[], nanoid: string): ActorCard {
  const tools: ToolDescriptor[] = commands.map((cmd) => ({
    name: cmd.name,
    description: cmd.agentToolDesc || cmd.name,
    inputSchemaJson: '{"type":"object"}',
  }));

  const addresses: ActorAddress[] = [
    { address: `${nanoid}.etzhayyim.com`, scheme: "actor", nanoid, displayName: "" },
    { address: `${nanoid}@etzhayyim.com`, scheme: "email", nanoid, displayName: "" },
  ];

  return {
    nanoid,
    name: def.name,
    description: def.description ?? "",
    protocols: ["xrpc", "w-protocol"],
    tools,
    addresses,
  };
}

export function buildCapabilitiesFromCommands(def: AppDef, commands: CommandEntry[]): ActorCapability[] {
  return commands.map((cmd) => ({
    id: `${def.id}.${cmd.name}`,
    name: cmd.name,
    description: cmd.agentToolDesc || `Execute ${humanizeIdentifier(cmd.name)}`,
    status: "operational",
    phase: cmd.capabilityPhase || "current",
    tags: capabilityTags(def, cmd),
    activityIds: [],
    measureNames: capabilityMeasures(cmd),
  }));
}

export function buildGovernanceManifestFromCommands(def: AppDef, commands: CommandEntry[]): GovernanceManifest {
  const policies = commands.map((cmd) => {
    const policy: CommandPolicy = { command: cmd.name, raci: governanceRaci(cmd) };
    if (cmd.approval) policy.approval = cmd.approval;
    if (cmd.bpmnTaskId) policy.bpmnTaskId = cmd.bpmnTaskId;
    if (cmd.ocelEventType) policy.ocelEventType = cmd.ocelEventType;
    return policy;
  });
  return { appId: def.id, policies };
}

export function buildAgentToolsFromCommands(commands: CommandEntry[]): AgentToolDef[] {
  const tools: AgentToolDef[] = [];
  for (const cmd of commands) {
    if (!cmd.agentToolDesc) continue;
    tools.push({
      name: cmd.name,
      description: cmd.agentToolDesc,
      inputSchemaJson: '{"type":"object","properties":{}}',
    });
  }
  return tools;
}

export function buildDefaultAgentSystemPrompt(def: AppDef, commands: CommandEntry[]): string {
  const configured = def.agent?.systemPrompt?.trim();
  if (configured) return configured;
  const name = def.name || def.id;
  const parts = [`You are the built-in conversation agent for the App '${name}'.`];
  const desc = def.description?.trim();
  if (desc) parts.push(desc.endsWith(".") ? desc : `${desc}.`);
  parts.push("Reply concisely and use the app's registered tools when they help.");
  if (commands.length > 0) {
    parts.push(`Available commands: ${commands.map((c) => c.name).join(", ")}.`);
  }
  return parts.join(" ");
}

function capabilityTags(def: AppDef, cmd: CommandEntry): string[] {
  const tags = [...cmd.capabilityTags];
  const appTag = normalizeTag(firstNonEmpty(def.name, def.id));
  if (appTag) tags.push(appTag);
  const verbTag = normalizeTag(inferCommandVerb(cmd.name));
  if (verbTag) tags.push(verbTag);
  if (governanceRaci(cmd).length > 0) tags.push("governed");
  if (cmd.approval) tags.push("approval-required");
  if (cmd.bpmnTaskId) tags.push("bpmn");
  if (cmd.ocelEventType) tags.push("ocel");
  return dedupeStrings(tags);
}

function capabilityMeasures(cmd: CommandEntry): string[] {
  const m: string[] = [];
  if (cmd.approval) m.push("approvalLatency", "approvalRate");
  if (cmd.ocelEventType) m.push("eventThroughput");
  return m;
}

function governanceRaci(cmd: CommandEntry): RACIAssignee[] {
  if (cmd.raci.length > 0) return [...cmd.raci];
  return [
    { role: RACIRole.Responsible, kind: AssigneeKind.OrgRole, value: "operator" },
    { role: RACIRole.Accountable, kind: AssigneeKind.OrgRole, value: "owner" },
  ];
}
