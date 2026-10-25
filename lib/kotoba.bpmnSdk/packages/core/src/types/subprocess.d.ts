import type { BaseElement, FlowElement } from './common.js';
export type SubProcessType = 'embedded' | 'event' | 'transaction' | 'adHoc';
export interface BaseSubProcess extends FlowElement {
    readonly subProcessType: SubProcessType;
    readonly triggeredByEvent?: boolean;
    readonly flowElements: FlowElement[];
    readonly artifacts?: Artifact[];
    readonly laneSets?: LaneSet[];
}
export interface EmbeddedSubProcess extends BaseSubProcess {
    readonly subProcessType: 'embedded';
}
export interface EventSubProcess extends BaseSubProcess {
    readonly subProcessType: 'event';
    readonly triggeredByEvent: true;
}
export interface TransactionSubProcess extends BaseSubProcess {
    readonly subProcessType: 'transaction';
    readonly method?: TransactionMethod;
}
export type TransactionMethod = '##compensate' | '##image' | '##store';
export interface AdHocSubProcess extends BaseSubProcess {
    readonly subProcessType: 'adHoc';
    readonly completionCondition?: string;
    readonly ordering?: AdHocOrdering;
    readonly cancelRemainingInstances?: boolean;
}
export type AdHocOrdering = 'Parallel' | 'Sequential';
export type SubProcess = EmbeddedSubProcess | EventSubProcess | TransactionSubProcess | AdHocSubProcess;
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
//# sourceMappingURL=subprocess.d.ts.map