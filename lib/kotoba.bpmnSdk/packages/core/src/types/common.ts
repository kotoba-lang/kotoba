// Merkle DAG: bpmn_common_types
// BPMN 2.0 共通型定義 - 全ての要素の基盤

export type BpmnId = string & { readonly __brand: 'BpmnId' };
export type BpmnName = string;
export type BpmnVersionTag = string;

// BPMN 2.0 Base Element
export interface BaseElement {
  readonly id: BpmnId;
  readonly name?: BpmnName;
  readonly documentation?: string;
  readonly extensionElements?: ExtensionElements;
}

// Extension Elements for custom properties
export interface ExtensionElements {
  readonly [key: string]: unknown;
}

// Expression types are defined at the end of this file

// Data types
export type VariableValue = string | number | boolean | null | VariableValue[];

// Flow elements common interface
export interface FlowElement extends BaseElement {
  readonly categoryValueRef?: BpmnId[];
  readonly auditing?: Auditing;
  readonly monitoring?: Monitoring;
}

// Auditing information
export interface Auditing {
  readonly id: BpmnId;
  readonly extensionElements?: ExtensionElements;
}

// Monitoring information
export interface Monitoring {
  readonly id: BpmnId;
  readonly extensionElements?: ExtensionElements;
}

// Sequence flow condition
export interface SequenceFlowCondition {
  readonly expression: Expression;
  readonly language?: string;
}

// Timer definitions
export interface TimerDefinition {
  readonly timeDate?: Expression;
  readonly timeCycle?: Expression;
  readonly timeDuration?: Expression;
}

// Message reference
export interface MessageRef {
  readonly id: BpmnId;
  readonly name?: BpmnName;
}

// Signal reference
export interface SignalRef {
  readonly id: BpmnId;
  readonly name?: BpmnName;
}

// Error reference
export interface ErrorRef {
  readonly id: BpmnId;
  readonly name?: BpmnName;
  readonly errorCode?: string;
}

// Escalation reference
export interface EscalationRef {
  readonly id: BpmnId;
  readonly name?: BpmnName;
  readonly escalationCode?: string;
}

// Cancel event definition
export interface CancelEventDefinition {
  readonly extensionElements?: ExtensionElements;
}

// Compensation event definition
export interface CompensationEventDefinition {
  readonly waitForCompletion?: boolean;
  readonly activityRef?: BpmnId;
}

// Conditional event definition
export interface ConditionalEventDefinition {
  readonly condition: Expression;
}

// Link event definition
export interface LinkEventDefinition {
  readonly name?: BpmnName;
  readonly source?: BpmnId;
  readonly target?: BpmnId;
}

// Terminate event definition
export interface TerminateEventDefinition {
  readonly extensionElements?: ExtensionElements;
}

// Cancel event definition
export interface CancelEventDefinition {
  readonly extensionElements?: ExtensionElements;
}

// Compensation event definition
export interface CompensationEventDefinition {
  readonly waitForCompletion?: boolean;
  readonly activityRef?: BpmnId;
}

// Multiple event definition (combines multiple triggers)
export interface MultipleEventDefinition {
  readonly extensionElements?: ExtensionElements;
}

// Parallel multiple event definition
export interface ParallelMultipleEventDefinition {
  readonly extensionElements?: ExtensionElements;
}

// Message event definition
export interface MessageEventDefinition extends BaseElement {
  readonly messageRef?: MessageRef;
  readonly operationRef?: string;
}

// Timer event definition
export interface TimerEventDefinition extends BaseElement {
  readonly timerDefinition: TimerDefinition;
}

// Signal event definition
export interface SignalEventDefinition extends BaseElement {
  readonly signalRef?: SignalRef;
}

// Error event definition
export interface ErrorEventDefinition extends BaseElement {
  readonly errorRef?: ErrorRef;
}

// Escalation event definition
export interface EscalationEventDefinition extends BaseElement {
  readonly escalationRef?: EscalationRef;
}

// Event Definition union type
export type EventDefinition =
  | MessageEventDefinition
  | TimerEventDefinition
  | SignalEventDefinition
  | ErrorEventDefinition
  | EscalationEventDefinition
  | CancelEventDefinition
  | CompensationEventDefinition
  | ConditionalEventDefinition
  | LinkEventDefinition
  | TerminateEventDefinition
  | MultipleEventDefinition
  | ParallelMultipleEventDefinition;

// BPMN Expression type (moved from duplicate definition)
export type Expression = string;
