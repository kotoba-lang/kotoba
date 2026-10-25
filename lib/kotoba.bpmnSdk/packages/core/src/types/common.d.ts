export type BpmnId = string & {
    readonly __brand: 'BpmnId';
};
export type BpmnName = string;
export type BpmnVersionTag = string;
export interface BaseElement {
    readonly id: BpmnId;
    readonly name?: BpmnName;
    readonly documentation?: string;
    readonly extensionElements?: ExtensionElements;
}
export interface ExtensionElements {
    readonly [key: string]: unknown;
}
export type VariableValue = string | number | boolean | null | VariableValue[];
export interface FlowElement extends BaseElement {
    readonly categoryValueRef?: BpmnId[];
    readonly auditing?: Auditing;
    readonly monitoring?: Monitoring;
}
export interface Auditing {
    readonly id: BpmnId;
    readonly extensionElements?: ExtensionElements;
}
export interface Monitoring {
    readonly id: BpmnId;
    readonly extensionElements?: ExtensionElements;
}
export interface SequenceFlowCondition {
    readonly expression: Expression;
    readonly language?: string;
}
export interface TimerDefinition {
    readonly timeDate?: Expression;
    readonly timeCycle?: Expression;
    readonly timeDuration?: Expression;
}
export interface MessageRef {
    readonly id: BpmnId;
    readonly name?: BpmnName;
}
export interface SignalRef {
    readonly id: BpmnId;
    readonly name?: BpmnName;
}
export interface ErrorRef {
    readonly id: BpmnId;
    readonly name?: BpmnName;
    readonly errorCode?: string;
}
export interface EscalationRef {
    readonly id: BpmnId;
    readonly name?: BpmnName;
    readonly escalationCode?: string;
}
export interface CancelEventDefinition {
    readonly extensionElements?: ExtensionElements;
}
export interface CompensationEventDefinition {
    readonly waitForCompletion?: boolean;
    readonly activityRef?: BpmnId;
}
export interface ConditionalEventDefinition {
    readonly condition: Expression;
}
export interface LinkEventDefinition {
    readonly name?: BpmnName;
    readonly source?: BpmnId;
    readonly target?: BpmnId;
}
export interface TerminateEventDefinition {
    readonly extensionElements?: ExtensionElements;
}
export interface CancelEventDefinition {
    readonly extensionElements?: ExtensionElements;
}
export interface CompensationEventDefinition {
    readonly waitForCompletion?: boolean;
    readonly activityRef?: BpmnId;
}
export interface MultipleEventDefinition {
    readonly extensionElements?: ExtensionElements;
}
export interface ParallelMultipleEventDefinition {
    readonly extensionElements?: ExtensionElements;
}
export interface MessageEventDefinition extends BaseElement {
    readonly messageRef?: MessageRef;
    readonly operationRef?: string;
}
export interface TimerEventDefinition extends BaseElement {
    readonly timerDefinition: TimerDefinition;
}
export interface SignalEventDefinition extends BaseElement {
    readonly signalRef?: SignalRef;
}
export interface ErrorEventDefinition extends BaseElement {
    readonly errorRef?: ErrorRef;
}
export interface EscalationEventDefinition extends BaseElement {
    readonly escalationRef?: EscalationRef;
}
export type EventDefinition = MessageEventDefinition | TimerEventDefinition | SignalEventDefinition | ErrorEventDefinition | EscalationEventDefinition | CancelEventDefinition | CompensationEventDefinition | ConditionalEventDefinition | LinkEventDefinition | TerminateEventDefinition | MultipleEventDefinition | ParallelMultipleEventDefinition;
export type Expression = string;
//# sourceMappingURL=common.d.ts.map