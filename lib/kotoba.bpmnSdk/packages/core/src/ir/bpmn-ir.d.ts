import type { MessageFlow, Participant, Message, Signal, Error, Escalation, DataStore, Artifact } from '../types/index.js';
export interface BpmnIR {
    readonly definitions: DefinitionsIR;
}
export interface DefinitionsIR {
    readonly id: string;
    readonly name?: string;
    readonly targetNamespace: string;
    readonly processes: ProcessIR[];
    readonly collaborations?: CollaborationIR[];
    readonly messages?: Message[];
    readonly signals?: Signal[];
    readonly errors?: Error[];
    readonly escalations?: Escalation[];
    readonly dataStores?: DataStore[];
    readonly version?: string;
}
export interface ProcessIR {
    readonly id: string;
    readonly name?: string;
    readonly isExecutable: boolean;
    readonly flowElements: FlowElementIR[];
    readonly sequenceFlows: SequenceFlowIR[];
    readonly messageFlows?: MessageFlow[];
    readonly participants?: Participant[];
    readonly artifacts?: Artifact[];
    readonly laneSets?: LaneSetIR[];
}
export interface CollaborationIR {
    readonly id: string;
    readonly name?: string;
    readonly participants: Participant[];
    readonly messageFlows: MessageFlow[];
}
export type FlowElementIR = EventIR | TaskIR | GatewayIR | SubProcessIR | DataObjectIR;
export interface EventIR {
    readonly type: 'event';
    readonly eventType: 'start' | 'end' | 'intermediate' | 'boundary';
    readonly id: string;
    readonly name?: string;
    readonly eventDefinitions?: EventDefinitionIR[];
    readonly attachedToRef?: string;
    readonly cancelActivity?: boolean;
}
export interface TaskIR {
    readonly type: 'task';
    readonly taskType: 'service' | 'user' | 'manual' | 'script' | 'businessRule' | 'send' | 'receive' | 'callActivity';
    readonly id: string;
    readonly name?: string;
    readonly implementation?: string;
    readonly assignee?: string;
    readonly candidateUsers?: string;
    readonly candidateGroups?: string;
    readonly formKey?: string;
    readonly calledElement?: string;
    readonly script?: string;
    readonly topic?: string;
    readonly operationRef?: string;
    readonly class?: string;
    readonly delegateExpression?: string;
    readonly expression?: string;
    readonly decisionRef?: string;
    readonly resultVariable?: string;
    readonly messageRef?: string;
    readonly instantiate?: boolean;
}
export interface GatewayIR {
    readonly type: 'gateway';
    readonly gatewayType: 'exclusive' | 'inclusive' | 'parallel' | 'eventBased' | 'complex';
    readonly id: string;
    readonly name?: string;
    readonly default?: string;
    readonly instantiate?: boolean;
    readonly eventGatewayType?: 'Exclusive' | 'Parallel';
    readonly activationCondition?: string;
}
export interface SubProcessIR {
    readonly type: 'subprocess';
    readonly subProcessType: 'embedded' | 'event' | 'transaction' | 'adHoc';
    readonly id: string;
    readonly name?: string;
    readonly triggeredByEvent?: boolean;
    readonly flowElements: FlowElementIR[];
    readonly sequenceFlows: SequenceFlowIR[];
    readonly artifacts?: Artifact[];
    readonly completionCondition?: string;
    readonly ordering?: 'Parallel' | 'Sequential';
    readonly cancelRemainingInstances?: boolean;
    readonly method?: string;
}
export interface SequenceFlowIR {
    readonly id: string;
    readonly name?: string;
    readonly sourceRef: string;
    readonly targetRef: string;
    readonly conditionExpression?: string;
    readonly isImmediate?: boolean;
}
export interface DataObjectIR {
    readonly type: 'dataObject';
    readonly id: string;
    readonly name?: string;
    readonly isCollection?: boolean;
    readonly itemSubjectRef?: string;
}
export type EventDefinitionIR = MessageEventDefinitionIR | TimerEventDefinitionIR | SignalEventDefinitionIR | ErrorEventDefinitionIR | EscalationEventDefinitionIR | CancelEventDefinitionIR | CompensationEventDefinitionIR | ConditionalEventDefinitionIR | LinkEventDefinitionIR | TerminateEventDefinitionIR | MultipleEventDefinitionIR | ParallelMultipleEventDefinitionIR;
export interface MessageEventDefinitionIR {
    readonly type: 'message';
    readonly messageRef?: string;
    readonly operationRef?: string;
}
export interface TimerEventDefinitionIR {
    readonly type: 'timer';
    readonly timeDate?: string;
    readonly timeCycle?: string;
    readonly timeDuration?: string;
}
export interface SignalEventDefinitionIR {
    readonly type: 'signal';
    readonly signalRef?: string;
}
export interface ErrorEventDefinitionIR {
    readonly type: 'error';
    readonly errorRef?: string;
}
export interface EscalationEventDefinitionIR {
    readonly type: 'escalation';
    readonly escalationRef?: string;
}
export interface CancelEventDefinitionIR {
    readonly type: 'cancel';
}
export interface CompensationEventDefinitionIR {
    readonly type: 'compensation';
    readonly waitForCompletion?: boolean;
    readonly activityRef?: string;
}
export interface ConditionalEventDefinitionIR {
    readonly type: 'conditional';
    readonly condition: string;
}
export interface LinkEventDefinitionIR {
    readonly type: 'link';
    readonly name?: string;
    readonly source?: string;
    readonly target?: string;
}
export interface TerminateEventDefinitionIR {
    readonly type: 'terminate';
}
export interface MultipleEventDefinitionIR {
    readonly type: 'multiple';
}
export interface ParallelMultipleEventDefinitionIR {
    readonly type: 'parallelMultiple';
}
export interface LaneSetIR {
    readonly id: string;
    readonly name?: string;
    readonly lanes: LaneIR[];
}
export interface LaneIR {
    readonly id: string;
    readonly name?: string;
    readonly flowNodeRefs?: string[];
}
export declare class BpmnIRUtils {
    static generateId(prefix?: string): string;
    static validateIR(ir: BpmnIR): {
        valid: boolean;
        errors: string[];
    };
}
//# sourceMappingURL=bpmn-ir.d.ts.map
