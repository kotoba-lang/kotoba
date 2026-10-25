// Merkle DAG: bpmn_importer
// BPMN XML → IR Importer (reverse compiler)

// Mock implementation for now - TODO: Implement full moddle integration
import { BpmnModdle } from 'bpmn-moddle';
import { fromXML } from 'moddle-xml';
import type {
  BpmnIR,
  DefinitionsIR,
  ProcessIR,
  FlowElementIR,
  EventIR,
  TaskIR,
  GatewayIR,
  SequenceFlowIR,
  EventDefinitionIR,
} from '@etzhayyim/bpmn-sdk-core';

// Use type assertions for building (similar to DSL approach)

// BPMN Importer - Converts BPMN 2.0 XML to IR
export class BpmnImporter {
  private moddle: InstanceType<typeof BpmnModdle>;

  constructor() {
    this.moddle = new BpmnModdle();
  }

  /**
   * Parse XML to BPMN definitions
   */
  async parseXml(xml: string): Promise<any> {
    const { rootElement } = await fromXML(xml, { moddle: this.moddle });
    return rootElement;
  }

  /**
   * Import BPMN XML to IR
   */
  async importFromXml(xml: string): Promise<BpmnIR> {
    const { rootElement } = await fromXML(xml, { moddle: this.moddle });
    return this.createIR(rootElement);
  }

  /**
   * Create IR from BPMN Definitions
   */
  private createIR(definitions: any): BpmnIR {
    const definitionsIR: DefinitionsIR = {
      id: definitions.id || 'Definitions',
      name: definitions.name,
      targetNamespace: definitions.targetNamespace || 'http://www.omg.org/spec/BPMN/20100524/MODEL',
      processes: [],
      version: definitions.exporterVersion || '1.0',
    };

    // Convert root elements
    if (definitions.rootElements) {
      for (const rootElement of definitions.rootElements) {
        if (rootElement.$type === 'bpmn:Process') {
          definitionsIR.processes.push(this.createProcessIR(rootElement));
        }
        // Add other root elements as needed (collaborations, messages, etc.)
      }
    }

    return {
      definitions: definitionsIR,
    };
  }

  /**
   * Create Process IR from BPMN Process
   */
  private createProcessIR(process: any): ProcessIR {
    const processIR: ProcessIR = {
      id: process.id,
      name: process.name,
      isExecutable: process.isExecutable !== false,
      flowElements: [],
      sequenceFlows: [],
    };

    // Convert flow elements
    if (process.flowElements) {
      for (const element of process.flowElements) {
        if (element.$type === 'bpmn:SequenceFlow') {
          processIR.sequenceFlows.push(this.createSequenceFlowIR(element));
        } else {
          const flowElementIR = this.createFlowElementIR(element);
          if (flowElementIR) {
            processIR.flowElements.push(flowElementIR);
          }
        }
      }
    }

    return processIR;
  }

  /**
   * Create Flow Element IR from BPMN element
   */
  private createFlowElementIR(element: any): FlowElementIR | null {
    switch (element.$type) {
      case 'bpmn:StartEvent':
        return this.createEventIR(element, 'start');
      case 'bpmn:EndEvent':
        return this.createEventIR(element, 'end');
      case 'bpmn:IntermediateCatchEvent':
        return this.createEventIR(element, 'intermediate');
      case 'bpmn:BoundaryEvent':
        return this.createEventIR(element, 'boundary');
      case 'bpmn:ServiceTask':
        return this.createTaskIR(element, 'service');
      case 'bpmn:UserTask':
        return this.createTaskIR(element, 'user');
      case 'bpmn:ManualTask':
        return this.createTaskIR(element, 'manual');
      case 'bpmn:ScriptTask':
        return this.createTaskIR(element, 'script');
      case 'bpmn:BusinessRuleTask':
        return this.createTaskIR(element, 'businessRule');
      case 'bpmn:SendTask':
        return this.createTaskIR(element, 'send');
      case 'bpmn:ReceiveTask':
        return this.createTaskIR(element, 'receive');
      case 'bpmn:CallActivity':
        return this.createTaskIR(element, 'callActivity');
      case 'bpmn:ExclusiveGateway':
        return this.createGatewayIR(element, 'exclusive');
      case 'bpmn:InclusiveGateway':
        return this.createGatewayIR(element, 'inclusive');
      case 'bpmn:ParallelGateway':
        return this.createGatewayIR(element, 'parallel');
      case 'bpmn:EventBasedGateway':
        return this.createGatewayIR(element, 'eventBased');
      case 'bpmn:ComplexGateway':
        return this.createGatewayIR(element, 'complex');
      default:
        // Unknown element type - skip for now
        console.warn(`Unknown BPMN element type: ${element.$type}`);
        return null;
    }
  }

  /**
   * Create Event IR
   */
  private createEventIR(element: any, eventType: 'start' | 'end' | 'intermediate' | 'boundary'): EventIR {
    const eventIR = {
      type: 'event',
      eventType,
      id: element.id,
      name: element.name,
    } as any;

    // Add event definitions
    if (element.eventDefinitions) {
      eventIR.eventDefinitions = element.eventDefinitions.map((def: any) =>
        this.createEventDefinitionIR(def)
      );
    }

    // Boundary event specific properties
    if (eventType === 'boundary') {
      eventIR.attachedToRef = element.attachedToRef?.id;
      eventIR.cancelActivity = element.cancelActivity !== false;
    }

    return eventIR as EventIR;
  }

  /**
   * Create Task IR
   */
  private createTaskIR(element: any, taskType: TaskIR['taskType']): TaskIR {
    const taskIR = {
      type: 'task',
      taskType,
      id: element.id,
      name: element.name,
    } as any;

    // Add task-specific properties
    if (element.implementation) taskIR.implementation = element.implementation;
    if (element.topic) taskIR.topic = element.topic;
    if (element.operationRef) taskIR.operationRef = element.operationRef.id;
    if (element.class) taskIR.class = element.class;
    if (element.delegateExpression) taskIR.delegateExpression = element.delegateExpression;
    if (element.expression) taskIR.expression = element.expression;
    if (element.resultVariable) taskIR.resultVariable = element.resultVariable;
    if (element.assignee) taskIR.assignee = element.assignee;
    if (element.candidateUsers) taskIR.candidateUsers = element.candidateUsers;
    if (element.candidateGroups) taskIR.candidateGroups = element.candidateGroups;
    if (element.formKey) taskIR.formKey = element.formKey;
    if (element.script) taskIR.script = element.script;
    if (element.decisionRef) taskIR.decisionRef = element.decisionRef;
    if (element.messageRef) taskIR.messageRef = element.messageRef.id;
    if (element.calledElement) taskIR.calledElement = element.calledElement;
    if (element.instantiate !== undefined) taskIR.instantiate = element.instantiate;

    return taskIR as TaskIR;
  }

  /**
   * Create Gateway IR
   */
  private createGatewayIR(element: any, gatewayType: GatewayIR['gatewayType']): GatewayIR {
    const gatewayIR = {
      type: 'gateway',
      gatewayType,
      id: element.id,
      name: element.name,
    } as any;

    if (element.default) gatewayIR.default = element.default.id;
    if (element.instantiate !== undefined) gatewayIR.instantiate = element.instantiate;
    if (element.eventGatewayType) gatewayIR.eventGatewayType = element.eventGatewayType;
    if (element.activationCondition) {
      gatewayIR.activationCondition = element.activationCondition.body;
    }

    return gatewayIR as GatewayIR;
  }

  /**
   * Create Sequence Flow IR
   */
  private createSequenceFlowIR(element: any): SequenceFlowIR {
    const flowIR = {
      id: element.id,
      name: element.name,
      sourceRef: element.sourceRef?.id || '',
      targetRef: element.targetRef?.id || '',
    } as any;

    if (element.conditionExpression) {
      flowIR.conditionExpression = element.conditionExpression.body;
    }

    if (element.isImmediate !== undefined) {
      flowIR.isImmediate = element.isImmediate;
    }

    return flowIR as SequenceFlowIR;
  }

  /**
   * Create Event Definition IR
   */
  private createEventDefinitionIR(element: any): EventDefinitionIR {
    switch (element.$type) {
      case 'bpmn:MessageEventDefinition':
        return {
          type: 'message',
          messageRef: element.messageRef?.id,
          operationRef: element.operationRef?.id,
        };
      case 'bpmn:TimerEventDefinition':
        return {
          type: 'timer',
          timeDate: element.timeDate,
          timeCycle: element.timeCycle,
          timeDuration: element.timeDuration,
        };
      case 'bpmn:SignalEventDefinition':
        return {
          type: 'signal',
          signalRef: element.signalRef?.id,
        };
      case 'bpmn:ErrorEventDefinition':
        return {
          type: 'error',
          errorRef: element.errorRef?.id,
        };
      case 'bpmn:EscalationEventDefinition':
        return {
          type: 'escalation',
          escalationRef: element.escalationRef?.id,
        };
      case 'bpmn:CompensationEventDefinition':
        return {
          type: 'compensation',
          activityRef: element.activityRef?.id,
          waitForCompletion: element.waitForCompletion,
        };
      case 'bpmn:ConditionalEventDefinition':
        return {
          type: 'conditional',
          condition: element.condition?.body || '',
        };
      case 'bpmn:LinkEventDefinition':
        return {
          type: 'link',
          name: element.name,
        };
      case 'bpmn:TerminateEventDefinition':
        return {
          type: 'terminate',
        };
      case 'bpmn:CancelEventDefinition':
        return {
          type: 'cancel',
        };
      case 'bpmn:MultipleEventDefinition':
        return {
          type: 'multiple',
        };
      case 'bpmn:ParallelMultipleEventDefinition':
        return {
          type: 'parallelMultiple',
        };
      default:
        // Fallback for unknown event definition types
        console.warn(`Unknown event definition type: ${element.$type}`);
        return { type: 'multiple' as any };
    }
  }
}

// Convenience function
export async function importFromXml(xml: string): Promise<BpmnIR> {
  const importer = new BpmnImporter();
  return importer.importFromXml(xml);
}

export async function parseXml(xml: string): Promise<BpmnIR> {
  return importFromXml(xml);
}
