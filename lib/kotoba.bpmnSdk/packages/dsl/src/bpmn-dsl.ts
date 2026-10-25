// Merkle DAG: bpmn_dsl_builder
// BPMN 2.0 TypeScript DSL - 宣言的モデリング

import type {
  BpmnIR,
  DefinitionsIR,
  ProcessIR,
  EventIR,
  TaskIR,
  GatewayIR,
  SubProcessIR,
  SequenceFlowIR,
  EventDefinitionIR,
  LaneSetIR,
} from '@etzhayyim/bpmn-sdk-core';

// Mutable versions for building
export interface MutableEventIR extends Omit<EventIR, 'eventDefinitions' | 'name'> {
  eventDefinitions?: EventDefinitionIR[];
  name?: string;
}

export interface MutableTaskIR extends Omit<TaskIR, 'name'> {
  name?: string;
}

export interface MutableGatewayIR extends Omit<GatewayIR, 'name'> {
  name?: string;
}

export interface MutableSubProcessIR extends Omit<SubProcessIR, 'name'> {
  name?: string;
}

export interface MutableSequenceFlowIR extends Omit<SequenceFlowIR, 'name'> {
  name?: string;
}


// Import builders
import {
  StartEventBuilder,
  EndEventBuilder,
  IntermediateCatchEventBuilder,
  BoundaryEventBuilder,
  ServiceTaskBuilder,
  UserTaskBuilder,
  ManualTaskBuilder,
  ScriptTaskBuilder,
  BusinessRuleTaskBuilder,
  SendTaskBuilder,
  ReceiveTaskBuilder,
  CallActivityBuilder,
  ExclusiveGatewayBuilder,
  InclusiveGatewayBuilder,
  ParallelGatewayBuilder,
  EventBasedGatewayBuilder,
  ComplexGatewayBuilder,
  EmbeddedSubprocessBuilder,
  SequenceFlowBuilder,
} from './builders/index.js';
import { LaneSetBuilder } from './builders/subprocess.js';

// DSL Context - ビルド中の状態管理
export class DslContext {
  private idCounter = 0;
  private elements = new Map<string, any>();
  private sequenceFlows: SequenceFlowIR[] = [];

  generateId(prefix: string = 'id'): string {
    return `${prefix}_${++this.idCounter}`;
  }

  addElement(id: string, element: any): void {
    this.elements.set(id, element);
  }

  getElement(id: string): any {
    return this.elements.get(id);
  }

  addSequenceFlow(flow: SequenceFlowIR): void {
    this.sequenceFlows.push(flow);
  }

  getSequenceFlows(): SequenceFlowIR[] {
    return [...this.sequenceFlows];
  }

  getElements(): any[] {
    return Array.from(this.elements.values());
  }
}

// Flow Builder - メインエントリーポイント
export function flow(name: string, builder: (f: FlowBuilder) => void): BpmnIR {
  const context = new DslContext();
  const flowBuilder = new FlowBuilder(context, name);
  builder(flowBuilder);
  const result = flowBuilder.build();

  return {
    definitions: {
      id: context.generateId('Definitions'),
      name,
      targetNamespace: 'http://www.etzhayyim.com/bpmn',
      processes: [result.process],
      version: '1.0',
    },
  };
}

// Flow Builder Result
export interface FlowBuilderResult {
  process: ProcessIR;
}

// Collaboration Builder (simplified for now)
export class CollaborationBuilder {
  constructor(private context: DslContext, private name: string) {}

  // Placeholder implementation
  build(): any {
    return { type: 'collaboration', name: this.name };
  }
}


// Flow Builder - プロセス構築のメインクラス
export class FlowBuilder {
  private context: DslContext;
  private processName: string;
  private elements: any[] = [];
  private laneSets: LaneSetIR[] = [];
  private _processBuilder?: ProcessBuilder;

  constructor(context: DslContext, processName: string) {
    this.context = context;
    this.processName = processName;
  }

  // Process configuration
  process(idOrConfig?: string | { id?: string; isExecutable?: boolean }, callback?: (builder: ProcessBuilder) => void): void;
  process(callback: (builder: ProcessBuilder) => void): void;
  process(idOrConfig?: string | { id?: string; isExecutable?: boolean } | ((builder: ProcessBuilder) => void), callback?: (builder: ProcessBuilder) => void): void {
    let config: { id?: string; isExecutable?: boolean } = {};
    let actualCallback: (builder: ProcessBuilder) => void;

    if (typeof idOrConfig === 'function') {
      // process(callback)
      actualCallback = idOrConfig;
    } else if (typeof idOrConfig === 'string') {
      // process(id, callback)
      config.id = idOrConfig;
      actualCallback = callback!;
    } else if (idOrConfig && typeof idOrConfig === 'object') {
      // process(config, callback)
      config = idOrConfig;
      actualCallback = callback!;
    } else {
      throw new Error('Invalid arguments for process method');
    }

    const processId = config.id || this.context.generateId('Process');
    const processBuilder = new ProcessBuilder(this.context, processId, this.processName, config.isExecutable ?? true);
    // Store reference to the process builder for building
    this._processBuilder = processBuilder;

    // Call the callback with the process builder if provided
    if (actualCallback) {
      actualCallback(processBuilder);
    }
  }

  // Collaboration (multi-pool)
  collaboration(name: string): CollaborationBuilder {
    return new CollaborationBuilder(this.context, name);
  }

  // Build the flow
  build(): FlowBuilderResult {
    if (this._processBuilder) {
      return this._processBuilder.build();
    }
    return {
      process: {
        id: this.processName,
        isExecutable: true,
        flowElements: this.context.getElements(),
        sequenceFlows: this.context.getSequenceFlows(),
        laneSets: this.laneSets.length > 0 ? this.laneSets : undefined,
      }
    };
  }
}

// Process Builder
export class ProcessBuilder {
  private context: DslContext;
  private processId: string;
  private processName: string;
  private isExecutable: boolean;
  private elements: any[] = [];
  private laneSets: LaneSetIR[] = [];

  constructor(context: DslContext, processId: string, processName: string, isExecutable: boolean) {
    this.context = context;
    this.processId = processId;
    this.processName = processName;
    this.isExecutable = isExecutable;
  }

  // Lane sets
  laneSet(name?: string): LaneSetBuilder {
    const laneSetId = this.context.generateId('LaneSet');
    const laneSet: LaneSetIR = {
      id: laneSetId,
      name,
      lanes: [],
    };
    this.laneSets.push(laneSet);
    return new LaneSetBuilder(this.context, laneSet);
  }

  // Events
  startEvent(id: string, name?: string): this {
    const event: MutableEventIR = {
      type: 'event',
      eventType: 'start',
      id,
      name,
    };
    this.elements.push(event as EventIR);
    this.context.addElement(id, event);
    return this;
  }

  endEvent(id: string, name?: string): this {
    const event: MutableEventIR = {
      type: 'event',
      eventType: 'end',
      id,
      name,
    };
    this.elements.push(event as EventIR);
    this.context.addElement(id, event);
    return this;
  }

  intermediateCatchEvent(id: string, name?: string): this {
    const event: MutableEventIR = {
      type: 'event',
      eventType: 'intermediate',
      id,
      name,
    };
    this.elements.push(event as EventIR);
    this.context.addElement(id, event);
    return this;
  }

  boundaryEvent(attachedToRef: string, id: string, name?: string): this {
    const event: MutableEventIR = {
      type: 'event',
      eventType: 'boundary',
      id,
      name,
      attachedToRef,
      cancelActivity: true, // Default to interrupting
    };
    this.elements.push(event as EventIR);
    this.context.addElement(id, event);
    return this;
  }

  // Tasks
  serviceTask(id: string, name?: string): this {
    const task: MutableTaskIR = {
      type: 'task',
      taskType: 'service',
      id,
      name,
    };
    this.elements.push(task as TaskIR);
    this.context.addElement(id, task);
    return this;
  }

  userTask(id: string, name?: string): this {
    const task: MutableTaskIR = {
      type: 'task',
      taskType: 'user',
      id,
      name,
    };
    this.elements.push(task as TaskIR);
    this.context.addElement(id, task);
    return this;
  }

  manualTask(id: string, name?: string): this {
    const task: TaskIR = {
      type: 'task',
      taskType: 'manual',
      id,
      name,
    };
    this.elements.push(task);
    this.context.addElement(id, task);
    return this;
  }

  scriptTask(id: string, name?: string): this {
    const task: TaskIR = {
      type: 'task',
      taskType: 'script',
      id,
      name,
    };
    this.elements.push(task);
    this.context.addElement(id, task);
    return this;
  }

  businessRuleTask(id: string, name?: string): this {
    const task: TaskIR = {
      type: 'task',
      taskType: 'businessRule',
      id,
      name,
    };
    this.elements.push(task);
    this.context.addElement(id, task);
    return this;
  }

  sendTask(id: string, name?: string): this {
    const task: TaskIR = {
      type: 'task',
      taskType: 'send',
      id,
      name,
    };
    this.elements.push(task);
    this.context.addElement(id, task);
    return this;
  }

  receiveTask(id: string, name?: string): this {
    const task: TaskIR = {
      type: 'task',
      taskType: 'receive',
      id,
      name,
    };
    this.elements.push(task);
    this.context.addElement(id, task);
    return this;
  }

  callActivity(id: string, name?: string): this {
    const task: TaskIR = {
      type: 'task',
      taskType: 'callActivity',
      id,
      name,
    };
    this.elements.push(task);
    this.context.addElement(id, task);
    return this;
  }

  // Gateways
  exclusiveGateway(id: string, name?: string): this {
    const gateway: GatewayIR = {
      type: 'gateway',
      gatewayType: 'exclusive',
      id,
      name,
    };
    this.elements.push(gateway);
    this.context.addElement(id, gateway);
    return this;
  }

  inclusiveGateway(id: string, name?: string): this {
    const gateway: GatewayIR = {
      type: 'gateway',
      gatewayType: 'inclusive',
      id,
      name,
    };
    this.elements.push(gateway);
    this.context.addElement(id, gateway);
    return this;
  }

  parallelGateway(id: string, name?: string): this {
    const gateway: GatewayIR = {
      type: 'gateway',
      gatewayType: 'parallel',
      id,
      name,
    };
    this.elements.push(gateway);
    this.context.addElement(id, gateway);
    return this;
  }

  eventBasedGateway(id: string, name?: string): this {
    const gateway: GatewayIR = {
      type: 'gateway',
      gatewayType: 'eventBased',
      id,
      name,
      instantiate: false,
      eventGatewayType: 'Exclusive',
    };
    this.elements.push(gateway);
    this.context.addElement(id, gateway);
    return this;
  }

  complexGateway(id: string, name?: string): this {
    const gateway: GatewayIR = {
      type: 'gateway',
      gatewayType: 'complex',
      id,
      name,
    };
    this.elements.push(gateway);
    this.context.addElement(id, gateway);
    return this;
  }

  // Subprocesses
  embeddedSubprocess(id: string, name?: string): this {
    const subProcess: SubProcessIR = {
      type: 'subprocess',
      subProcessType: 'embedded',
      id,
      name,
      flowElements: [],
      sequenceFlows: [],
    };
    this.elements.push(subProcess);
    this.context.addElement(id, subProcess);
    return this;
  }

  // Sequence flows
  sequenceFlow(sourceRef: string, targetRef: string, id?: string, name?: string): SequenceFlowBuilder {
    const flowId = id || this.context.generateId('SequenceFlow');
    const flow: SequenceFlowIR = {
      id: flowId,
      name,
      sourceRef,
      targetRef,
    };
    this.context.addSequenceFlow(flow);
    return new SequenceFlowBuilder(this.context, flow);
  }

  // Build process
  build(): FlowBuilderResult {
    const process: ProcessIR = {
      id: this.processId,
      name: this.processName,
      isExecutable: this.isExecutable,
      flowElements: this.elements,
      sequenceFlows: this.context.getSequenceFlows(),
      laneSets: this.laneSets.length > 0 ? this.laneSets : undefined,
    };

    return { process };
  }
}
