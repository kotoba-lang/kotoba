import type { BaseElement, FlowElement, Expression, CancelEventDefinition, CompensationEventDefinition, EventDefinition } from './common.js';
import type { MessageFlow, DataStore } from './flows.js';
import type { Artifact } from './subprocess.js';
export interface Definitions extends BaseElement {
    readonly targetNamespace: string;
    readonly expressionLanguage?: string;
    readonly typeLanguage?: string;
    readonly imports?: Import[];
    readonly extensions?: Extension[];
    readonly rootElements: RootElement[];
    readonly diagrams?: BPMNDiagram[];
    readonly exporter?: string;
    readonly exporterVersion?: string;
}
export type RootElement = Process | Category | Collaboration | GlobalTask | Interface | ItemDefinition | Message | Resource | Signal | Error | Escalation | CancelEventDefinition | CompensationEventDefinition | DataStore | EventDefinition;
export interface Process extends BaseElement {
    readonly processType?: ProcessType;
    readonly isExecutable?: boolean;
    readonly isClosed?: boolean;
    readonly auditing?: Auditing;
    readonly monitoring?: Monitoring;
    readonly properties?: Property[];
    readonly laneSets?: LaneSet[];
    readonly flowElements: FlowElement[];
    readonly artifacts?: Artifact[];
    readonly resources?: ResourceRole[];
    readonly correlationSubscriptions?: CorrelationSubscription[];
    readonly supports?: string[];
    readonly definitionalCollaborationRef?: string;
    readonly ioSpecification?: InputOutputSpecification;
    readonly ioBinding?: InputOutputBinding[];
}
export type ProcessType = 'None' | 'Public' | 'Private';
export interface Collaboration extends BaseElement {
    readonly isClosed?: boolean;
    readonly participants?: Participant[];
    readonly messageFlows?: MessageFlow[];
    readonly artifacts?: Artifact[];
    readonly conversations?: Conversation[];
    readonly conversationAssociations?: ConversationAssociation[];
    readonly participantAssociations?: ParticipantAssociation[];
    readonly messageFlowAssociations?: MessageFlowAssociation[];
    readonly correlationKeys?: CorrelationKey[];
    readonly choreographyRef?: string[];
    readonly conversationLinks?: ConversationLink[];
}
export interface Category extends BaseElement {
    readonly categoryValue?: CategoryValue[];
}
export interface CategoryValue extends BaseElement {
    readonly value?: string;
    readonly categorizedFlowElements?: FlowElement[];
}
export interface Interface extends BaseElement {
    readonly name?: string;
    readonly operations?: Operation[];
    readonly implementationRef?: string;
}
export interface Operation extends BaseElement {
    readonly name?: string;
    readonly inMessageRef: string;
    readonly outMessageRef?: string;
    readonly errorRefs?: string[];
    readonly implementationRef?: string;
}
export interface Message extends BaseElement {
    readonly name?: string;
    readonly itemRef?: string;
}
export interface Signal extends BaseElement {
    readonly name?: string;
    readonly structureRef?: string;
}
export interface Error extends BaseElement {
    readonly name?: string;
    readonly errorCode?: string;
    readonly structureRef?: string;
}
export interface Escalation extends BaseElement {
    readonly name?: string;
    readonly escalationCode?: string;
    readonly structureRef?: string;
}
export interface Resource extends BaseElement {
    readonly name?: string;
    readonly resourceParameters?: ResourceParameter[];
}
export interface ResourceParameter extends BaseElement {
    readonly name?: string;
    readonly isRequired?: boolean;
    readonly type?: ItemDefinition;
}
export interface ResourceRole extends BaseElement {
    readonly name?: string;
    readonly resourceRef?: string;
    readonly resourceParameterBindings?: ResourceParameterBinding[];
    readonly resourceAssignmentExpression?: ResourceAssignmentExpression;
}
export interface ResourceParameterBinding {
    readonly parameterRef: string;
    readonly expression: Expression;
}
export interface ResourceAssignmentExpression {
    readonly expression: Expression;
}
export interface ItemDefinition extends BaseElement {
    readonly structureRef?: string;
    readonly isCollection?: boolean;
    readonly import?: Import;
    readonly itemKind?: ItemKind;
}
export type ItemKind = 'Information' | 'Physical';
export interface CorrelationSubscription extends BaseElement {
    readonly correlationKeyRef?: string;
    readonly correlationPropertyBinding?: CorrelationPropertyBinding[];
}
export interface CorrelationPropertyBinding {
    readonly correlationPropertyRef: string;
    readonly dataPath: Expression;
}
export interface Import {
    readonly namespace: string;
    readonly location: string;
    readonly importType: string;
}
export interface Extension {
    readonly mustUnderstand?: boolean;
    readonly definition?: ExtensionDefinition;
}
export interface ExtensionDefinition {
    readonly name?: string;
    readonly extensionAttributeDefinitions?: ExtensionAttributeDefinition[];
}
export interface ExtensionAttributeDefinition {
    readonly name?: string;
    readonly type?: string;
    readonly isReference?: boolean;
}
export interface BPMNDiagram {
    readonly id: string;
    readonly name?: string;
    readonly documentation?: string;
    readonly resolution?: number;
    readonly plane: BPMNPlane;
}
export interface BPMNPlane {
    readonly bpmnElement?: string;
    readonly shapes?: BPMNShape[];
    readonly edges?: BPMNEdge[];
}
export interface BPMNShape {
    readonly id: string;
    readonly bpmnElement?: string;
    readonly bounds: Bounds;
    readonly isHorizontal?: boolean;
    readonly isExpanded?: boolean;
    readonly isMarkerVisible?: boolean;
    readonly isMessageVisible?: boolean;
    readonly participantBandKind?: string;
    readonly choreographyActivityShape?: string;
    readonly isInitiating?: boolean;
}
export interface BPMNEdge {
    readonly id: string;
    readonly bpmnElement?: string;
    readonly sourceElement?: string;
    readonly targetElement?: string;
    readonly waypoint: Point[];
    readonly label?: BPMNLabel;
}
export interface Bounds {
    readonly x: number;
    readonly y: number;
    readonly width: number;
    readonly height: number;
}
export interface Point {
    readonly x: number;
    readonly y: number;
}
export interface BPMNLabel {
    readonly bounds: Bounds;
}
export interface GlobalTask extends BaseElement {
    readonly resources?: ResourceRole[];
}
export interface Auditing {
    readonly id: string;
}
export interface Monitoring {
    readonly id: string;
}
export interface Property extends BaseElement {
    readonly name?: string;
}
export interface LaneSet {
    readonly id: string;
    readonly name?: string;
    readonly lanes?: Lane[];
}
export interface Lane {
    readonly id: string;
    readonly name?: string;
}
export interface InputOutputSpecification {
    readonly id: string;
}
export interface InputOutputBinding {
    readonly inputDataRef: string;
    readonly outputDataRef: string;
    readonly operationRef?: string;
}
export interface CorrelationKey {
    readonly id: string;
    readonly name?: string;
}
export interface Participant {
    readonly id: string;
}
export interface Conversation {
    readonly id: string;
}
export interface ConversationAssociation {
    readonly innerConversationNodeRef: string;
    readonly outerConversationNodeRef: string;
}
export interface ParticipantAssociation {
    readonly innerParticipantRef: string;
    readonly outerParticipantRef: string;
}
export interface MessageFlowAssociation {
    readonly innerMessageFlowRef: string;
    readonly outerMessageFlowRef: string;
}
export interface ConversationLink {
    readonly id: string;
}
//# sourceMappingURL=definitions.d.ts.map