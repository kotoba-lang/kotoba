import type { FlowElement, EventDefinition } from './common.js';
export type EventType = 'start' | 'intermediate' | 'end' | 'boundary';
export type EventDefinitionType = 'message' | 'timer' | 'signal' | 'error' | 'escalation' | 'cancel' | 'compensation' | 'conditional' | 'link' | 'terminate' | 'multiple' | 'parallelMultiple';
export interface BaseEvent extends FlowElement {
    readonly eventType: EventType;
    readonly eventDefinitions: EventDefinition[];
}
export interface StartEvent extends BaseEvent {
    readonly eventType: 'start';
    readonly isInterrupting?: boolean;
    readonly parallelMultiple?: boolean;
}
export interface IntermediateCatchEvent extends BaseEvent {
    readonly eventType: 'intermediate';
    readonly parallelMultiple?: boolean;
}
export interface IntermediateThrowEvent extends BaseEvent {
    readonly eventType: 'intermediate';
    readonly parallelMultiple?: boolean;
}
export interface EndEvent extends BaseEvent {
    readonly eventType: 'end';
}
export interface BoundaryEvent extends BaseEvent {
    readonly eventType: 'boundary';
    readonly attachedToRef: string;
    readonly cancelActivity: boolean;
}
export type Event = StartEvent | IntermediateCatchEvent | IntermediateThrowEvent | EndEvent | BoundaryEvent;
//# sourceMappingURL=events.d.ts.map