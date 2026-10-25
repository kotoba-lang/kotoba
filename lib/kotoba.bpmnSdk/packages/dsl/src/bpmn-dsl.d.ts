import type { BpmnIR, ProcessIR, EventIR, TaskIR, GatewayIR, SubProcessIR, SequenceFlowIR, EventDefinitionIR } from '@etzhayyim/bpmn-sdk-core';
export interface MutableEventIR extends Omit<EventIR, 'eventDefinitions'> {
    eventDefinitions?: EventDefinitionIR[];
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
import { StartEventBuilder, EndEventBuilder, IntermediateCatchEventBuilder, BoundaryEventBuilder, ServiceTaskBuilder, UserTaskBuilder, ManualTaskBuilder, ScriptTaskBuilder, BusinessRuleTaskBuilder, SendTaskBuilder, ReceiveTaskBuilder, CallActivityBuilder, ExclusiveGatewayBuilder, InclusiveGatewayBuilder, ParallelGatewayBuilder, EventBasedGatewayBuilder, ComplexGatewayBuilder, EmbeddedSubprocessBuilder, SequenceFlowBuilder } from './builders/index.js';
import { LaneSetBuilder } from './builders/subprocess.js';
export declare class DslContext {
    private idCounter;
    private elements;
    private sequenceFlows;
    generateId(prefix?: string): string;
    addElement(id: string, element: any): void;
    getElement(id: string): any;
    addSequenceFlow(flow: SequenceFlowIR): void;
    getSequenceFlows(): SequenceFlowIR[];
    getElements(): any[];
}
export declare function flow(name: string, builder: (f: FlowBuilder) => void): BpmnIR;
export interface FlowBuilderResult {
    process: ProcessIR;
}
export declare class CollaborationBuilder {
    private context;
    private name;
    constructor(context: DslContext, name: string);
    build(): any;
}
export declare class FlowBuilder {
    private context;
    private processName;
    private elements;
    private laneSets;
    private _processBuilder?;
    constructor(context: DslContext, processName: string);
    process(idOrConfig?: string | {
        id?: string;
        isExecutable?: boolean;
    }, callback?: (builder: ProcessBuilder) => void): void;
    process(callback: (builder: ProcessBuilder) => void): void;
    collaboration(name: string): CollaborationBuilder;
    build(): FlowBuilderResult;
}
export declare class ProcessBuilder {
    private context;
    private processId;
    private processName;
    private isExecutable;
    private elements;
    private laneSets;
    constructor(context: DslContext, processId: string, processName: string, isExecutable: boolean);
    laneSet(name?: string): LaneSetBuilder;
    startEvent(name?: string): StartEventBuilder;
    endEvent(name?: string): EndEventBuilder;
    intermediateCatchEvent(name?: string): IntermediateCatchEventBuilder;
    boundaryEvent(attachedToRef: string, name?: string): BoundaryEventBuilder;
    serviceTask(name?: string): ServiceTaskBuilder;
    userTask(name?: string): UserTaskBuilder;
    manualTask(name?: string): ManualTaskBuilder;
    scriptTask(name?: string): ScriptTaskBuilder;
    businessRuleTask(name?: string): BusinessRuleTaskBuilder;
    sendTask(name?: string): SendTaskBuilder;
    receiveTask(name?: string): ReceiveTaskBuilder;
    callActivity(name?: string): CallActivityBuilder;
    exclusiveGateway(name?: string): ExclusiveGatewayBuilder;
    inclusiveGateway(name?: string): InclusiveGatewayBuilder;
    parallelGateway(name?: string): ParallelGatewayBuilder;
    eventBasedGateway(name?: string): EventBasedGatewayBuilder;
    complexGateway(name?: string): ComplexGatewayBuilder;
    embeddedSubprocess(name?: string): EmbeddedSubprocessBuilder;
    sequenceFlow(sourceRef: string, targetRef: string, name?: string): SequenceFlowBuilder;
    build(): FlowBuilderResult;
}
//# sourceMappingURL=bpmn-dsl.d.ts.map
