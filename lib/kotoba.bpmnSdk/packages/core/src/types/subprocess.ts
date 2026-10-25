// Merkle DAG: bpmn_subprocess_types
// BPMN 2.0 SubProcess 型定義 - 完全網羅

import type { BaseElement, FlowElement } from './common.js';

// SubProcess Types
export type SubProcessType = 'embedded' | 'event' | 'transaction' | 'adHoc';

// Base SubProcess interface
export interface BaseSubProcess extends FlowElement {
  readonly subProcessType: SubProcessType;
  readonly triggeredByEvent?: boolean;
  readonly flowElements: FlowElement[];
  readonly artifacts?: Artifact[];
  readonly laneSets?: LaneSet[];
}

// Embedded SubProcess - Inline subprocess
export interface EmbeddedSubProcess extends BaseSubProcess {
  readonly subProcessType: 'embedded';
}

// Event SubProcess - Event-triggered subprocess
export interface EventSubProcess extends BaseSubProcess {
  readonly subProcessType: 'event';
  readonly triggeredByEvent: true;
}

// Transaction SubProcess - ACID transaction
export interface TransactionSubProcess extends BaseSubProcess {
  readonly subProcessType: 'transaction';
  readonly method?: TransactionMethod;
}

export type TransactionMethod = '##compensate' | '##image' | '##store';

// Ad-hoc SubProcess - Unstructured activities
export interface AdHocSubProcess extends BaseSubProcess {
  readonly subProcessType: 'adHoc';
  readonly completionCondition?: string;
  readonly ordering?: AdHocOrdering;
  readonly cancelRemainingInstances?: boolean;
}

export type AdHocOrdering = 'Parallel' | 'Sequential';

// Union type for all subprocesses
export type SubProcess =
  | EmbeddedSubProcess
  | EventSubProcess
  | TransactionSubProcess
  | AdHocSubProcess;

// Artifacts
export type Artifact = Association | Group | TextAnnotation;

export interface Association extends BaseElement {
  readonly associationDirection?: AssociationDirection;
  readonly sourceRef: string;
  readonly targetRef: string;
}

export type AssociationDirection = 'None' | 'One' | 'Both';

export interface Group extends BaseElement {
  readonly categoryValueRef?: string;
}

export interface TextAnnotation extends BaseElement {
  readonly text?: string;
  readonly textFormat?: string;
}

// Lane Sets for swimlanes
export interface LaneSet {
  readonly id: string;
  readonly name?: string;
  readonly lanes: Lane[];
}

export interface Lane {
  readonly id: string;
  readonly name?: string;
  readonly flowNodeRefs?: string[];
  readonly childLaneSet?: LaneSet;
}
