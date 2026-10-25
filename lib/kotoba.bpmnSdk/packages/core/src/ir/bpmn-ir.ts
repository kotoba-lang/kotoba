// Merkle DAG: bpmn_internal_representation
// BPMN 2.0 内部表現 (IR) - DSL → XML 変換の中間層

import type {
  Definitions,
  Process,
  FlowElement,
  SequenceFlow,
  MessageFlow,
  Event,
  Task,
  Gateway,
  SubProcess,
  Participant,
  Message,
  Signal,
  Error,
  Escalation,
  DataObject,
  DataStore,
  Artifact,
} from '../types/index.js';

// BPMN IR - Internal Representation for BPMN 2.0
export interface BpmnIR {
  readonly definitions: DefinitionsIR;
}

// Definitions IR
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

// Process IR
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

// Collaboration IR
export interface CollaborationIR {
  readonly id: string;
  readonly name?: string;
  readonly participants: Participant[];
  readonly messageFlows: MessageFlow[];
}

// Flow Elements IR
export type FlowElementIR =
  | EventIR
  | TaskIR
  | GatewayIR
  | SubProcessIR
  | DataObjectIR;

// Event IR
export interface EventIR {
  readonly type: 'event';
  readonly eventType: 'start' | 'end' | 'intermediate' | 'boundary';
  readonly id: string;
  readonly name?: string;
  readonly eventDefinitions?: EventDefinitionIR[];
  readonly attachedToRef?: string; // For boundary events
  readonly cancelActivity?: boolean; // For boundary events
}

// Task IR
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
  readonly calledElement?: string; // For call activity
  readonly script?: string; // For script task
  readonly topic?: string; // For external service task
  readonly operationRef?: string;
  readonly class?: string;
  readonly delegateExpression?: string;
  readonly expression?: string;
  readonly decisionRef?: string; // For business rule task
  readonly resultVariable?: string;
  readonly messageRef?: string;
  readonly instantiate?: boolean;
}

// Gateway IR
export interface GatewayIR {
  readonly type: 'gateway';
  readonly gatewayType: 'exclusive' | 'inclusive' | 'parallel' | 'eventBased' | 'complex';
  readonly id: string;
  readonly name?: string;
  readonly default?: string;
  readonly instantiate?: boolean; // For event-based gateway
  readonly eventGatewayType?: 'Exclusive' | 'Parallel'; // For event-based gateway
  readonly activationCondition?: string; // For complex gateway
}

// SubProcess IR
export interface SubProcessIR {
  readonly type: 'subprocess';
  readonly subProcessType: 'embedded' | 'event' | 'transaction' | 'adHoc';
  readonly id: string;
  readonly name?: string;
  readonly triggeredByEvent?: boolean;
  readonly flowElements: FlowElementIR[];
  readonly sequenceFlows: SequenceFlowIR[];
  readonly artifacts?: Artifact[];
  readonly completionCondition?: string; // For ad-hoc
  readonly ordering?: 'Parallel' | 'Sequential'; // For ad-hoc
  readonly cancelRemainingInstances?: boolean; // For ad-hoc
  readonly method?: string; // For transaction
}

// Sequence Flow IR
export interface SequenceFlowIR {
  readonly id: string;
  readonly name?: string;
  readonly sourceRef: string;
  readonly targetRef: string;
  readonly conditionExpression?: string;
  readonly isImmediate?: boolean;
}

// Data Object IR
export interface DataObjectIR {
  readonly type: 'dataObject';
  readonly id: string;
  readonly name?: string;
  readonly isCollection?: boolean;
  readonly itemSubjectRef?: string;
}

// Event Definitions IR
export type EventDefinitionIR =
  | MessageEventDefinitionIR
  | TimerEventDefinitionIR
  | SignalEventDefinitionIR
  | ErrorEventDefinitionIR
  | EscalationEventDefinitionIR
  | CancelEventDefinitionIR
  | CompensationEventDefinitionIR
  | ConditionalEventDefinitionIR
  | LinkEventDefinitionIR
  | TerminateEventDefinitionIR
  | MultipleEventDefinitionIR
  | ParallelMultipleEventDefinitionIR;

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

// Lane Set IR
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

// Utility functions for IR manipulation
export class BpmnIRUtils {
  static generateId(prefix: string = 'id'): string {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  static validateIR(ir: BpmnIR): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Basic validation
    if (!ir.definitions.id) {
      errors.push('Definitions must have an id');
    }

    if (!ir.definitions.targetNamespace) {
      errors.push('Definitions must have a targetNamespace');
    }

    // Validate processes
    ir.definitions.processes.forEach((process, index) => {
      if (!process.id) {
        errors.push(`Process ${index} must have an id`);
      }
      if (process.flowElements.length === 0) {
        errors.push(`Process ${process.id} must have at least one flow element`);
      }
    });

    return {
      valid: errors.length === 0,
      errors,
    };
  }
}
