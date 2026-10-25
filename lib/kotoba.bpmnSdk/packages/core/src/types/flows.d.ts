import type { BaseElement, FlowElement, Expression, ExtensionElements } from './common.js';
export interface SequenceFlow extends BaseElement {
    readonly sourceRef: string;
    readonly targetRef: string;
    readonly conditionExpression?: Expression;
    readonly isImmediate?: boolean;
    readonly extensionElements?: ExtensionElements;
}
export interface MessageFlow extends BaseElement {
    readonly sourceRef: string;
    readonly targetRef: string;
    readonly messageRef?: string;
    readonly name?: string;
    readonly extensionElements?: ExtensionElements;
}
export interface DataAssociation extends BaseElement {
    readonly sourceRef?: string[];
    readonly targetRef?: string;
    readonly transformation?: Expression;
    readonly assignment?: Assignment[];
}
export interface Assignment {
    readonly from?: Expression;
    readonly to?: Expression;
}
export interface DataObject extends FlowElement {
    readonly isCollection?: boolean;
    readonly itemSubjectRef?: string;
}
export interface DataStore extends BaseElement {
    readonly name?: string;
    readonly capacity?: number;
    readonly isUnlimited?: boolean;
    readonly itemSubjectRef?: string;
}
export interface ConversationNode extends BaseElement {
    readonly name?: string;
    readonly participantRefs?: string[];
    readonly messageFlowRefs?: string[];
    readonly correlationKeys?: CorrelationKey[];
}
export interface Conversation extends ConversationNode {
    readonly conversationNodes?: ConversationNode[];
}
export interface ConversationLink extends BaseElement {
    readonly sourceRef: string;
    readonly targetRef: string;
    readonly name?: string;
}
export interface CorrelationKey extends BaseElement {
    readonly name?: string;
    readonly correlationPropertyRef?: string[];
}
export interface CorrelationProperty extends BaseElement {
    readonly name?: string;
    readonly type?: string;
    readonly correlationPropertyRetrievalExpression?: CorrelationPropertyRetrievalExpression[];
}
export interface CorrelationPropertyRetrievalExpression {
    readonly messageRef: string;
    readonly messagePath: Expression;
}
export interface Participant extends BaseElement {
    readonly name?: string;
    readonly processRef?: string;
    readonly participantMultiplicity?: ParticipantMultiplicity;
    readonly interfaceRef?: string[];
    readonly endpointRef?: string[];
    readonly participantMultiplicityRef?: string;
}
export interface ParticipantMultiplicity {
    readonly minimum?: number;
    readonly maximum?: number;
}
//# sourceMappingURL=flows.d.ts.map