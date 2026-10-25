// Merkle DAG: bpmn_event_types
// BPMN 2.0 Event 型定義 - 完全網羅

import type { BaseElement, FlowElement, EventDefinition } from './common.js';

// Event Types
export type EventType = 'start' | 'intermediate' | 'end' | 'boundary';
export type EventDefinitionType =
  | 'message'
  | 'timer'
  | 'signal'
  | 'error'
  | 'escalation'
  | 'cancel'
  | 'compensation'
  | 'conditional'
  | 'link'
  | 'terminate'
  | 'multiple'
  | 'parallelMultiple';

// Base Event interface
export interface BaseEvent extends FlowElement {
  readonly eventType: EventType;
  readonly eventDefinitions: EventDefinition[];
}

// Start Event
export interface StartEvent extends BaseEvent {
  readonly eventType: 'start';
  readonly isInterrupting?: boolean; // Always true for start events
  readonly parallelMultiple?: boolean;
}

// Intermediate Catch Event
export interface IntermediateCatchEvent extends BaseEvent {
  readonly eventType: 'intermediate';
  readonly parallelMultiple?: boolean;
}

// Intermediate Throw Event
export interface IntermediateThrowEvent extends BaseEvent {
  readonly eventType: 'intermediate';
  readonly parallelMultiple?: boolean;
}

// End Event
export interface EndEvent extends BaseEvent {
  readonly eventType: 'end';
}

// Boundary Event
export interface BoundaryEvent extends BaseEvent {
  readonly eventType: 'boundary';
  readonly attachedToRef: string; // Reference to the activity it's attached to
  readonly cancelActivity: boolean; // Whether it interrupts the activity
}

// Union type for all events
export type Event =
  | StartEvent
  | IntermediateCatchEvent
  | IntermediateThrowEvent
  | EndEvent
  | BoundaryEvent;

// Event definitions are imported from common.ts
