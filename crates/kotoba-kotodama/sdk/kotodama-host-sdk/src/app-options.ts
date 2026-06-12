import type { CommandHandler, RACIAssignee, ApprovalRequirement, AssigneeRef } from "./types.js";
import { RACIRole, AssigneeKind, DecisionClass } from "./types.js";
import { withWLexicon as withWLexiconCore, type CommandOption as CoreCommandOption } from "@etzhayyim/xrpc/command-dsl";

export interface CommandEntry {
  name: string;
  handler: CommandHandler;
  lexiconSuffix: string;
  signalGroupField: string;
  agentToolDesc: string;
  capabilityTags: string[];
  capabilityPhase: string;
  raci: RACIAssignee[];
  approval: ApprovalRequirement | null;
  bpmnTaskId: string;
  ocelEventType: string;
}

export interface QueryEntry {
  name: string;
  handler: CommandHandler;
}

export type CommandOption = CoreCommandOption<CommandEntry>;

export function createCommandEntry(name: string, handler: CommandHandler): CommandEntry {
  return {
    name,
    handler,
    lexiconSuffix: "",
    signalGroupField: "",
    agentToolDesc: "",
    capabilityTags: [],
    capabilityPhase: "",
    raci: [],
    approval: null,
    bpmnTaskId: "",
    ocelEventType: "",
  };
}

export function asAgentTool(description: string): CommandOption {
  return (e) => { e.agentToolDesc = description; };
}

export function withCapabilityTags(...tags: string[]): CommandOption {
  return (e) => { e.capabilityTags.push(...tags); };
}

export function withWLexicon(suffix: string): CommandOption {
  return withWLexiconCore<CommandEntry>(suffix);
}

export function withSignalEncrypt(groupIdField: string): CommandOption {
  return (e) => { e.signalGroupField = groupIdField; };
}

export function withCapabilityPhase(phase: string): CommandOption {
  return (e) => { e.capabilityPhase = phase; };
}

export function responsible(kind: AssigneeKind, value: string): CommandOption {
  return (e) => { e.raci.push({ role: RACIRole.Responsible, kind, value }); };
}

export function accountable(kind: AssigneeKind, value: string): CommandOption {
  return (e) => { e.raci.push({ role: RACIRole.Accountable, kind, value }); };
}

export function consulted(kind: AssigneeKind, value: string): CommandOption {
  return (e) => { e.raci.push({ role: RACIRole.Consulted, kind, value }); };
}

export function informed(kind: AssigneeKind, value: string): CommandOption {
  return (e) => { e.raci.push({ role: RACIRole.Informed, kind, value }); };
}

export function requireApproval(
  cls: DecisionClass, minApprovers: number, riskTier: string, ...approvers: AssigneeRef[]
): CommandOption {
  return (e) => {
    e.approval = { decisionClass: cls, minApprovers, approverPool: approvers, riskTier };
  };
}

export function withBPMNTask(taskId: string): CommandOption {
  return (e) => { e.bpmnTaskId = taskId; };
}

export function withOCELEvent(eventType: string): CommandOption {
  return (e) => { e.ocelEventType = eventType; };
}
