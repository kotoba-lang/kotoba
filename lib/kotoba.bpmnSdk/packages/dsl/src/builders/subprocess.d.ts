import type { SubProcessIR, LaneSetIR } from '@etzhayyim/bpmn-sdk-core';
import { ProcessBuilder } from '../bpmn-dsl.js';
import type { DslContext, MutableSubProcessIR } from '../bpmn-dsl.js';
export declare class BaseSubprocessBuilder {
    protected context: DslContext;
    protected subProcess: MutableSubProcessIR;
    constructor(context: DslContext, subProcess: MutableSubProcessIR);
    startEvent(name?: string): ProcessBuilder;
}
export declare class EmbeddedSubprocessBuilder extends BaseSubprocessBuilder {
}
export declare class EventSubprocessBuilder extends BaseSubprocessBuilder {
    constructor(context: DslContext, subProcess: SubProcessIR);
}
export declare class TransactionSubprocessBuilder extends BaseSubprocessBuilder {
    compensate(): this;
    image(): this;
    store(): this;
}
export declare class AdHocSubprocessBuilder extends BaseSubprocessBuilder {
    completionCondition(condition: string): this;
    parallel(): this;
    sequential(): this;
    cancelRemainingInstances(cancel?: boolean): this;
}
export declare class LaneSetBuilder {
    private context;
    private laneSet;
    constructor(context: DslContext, laneSet: LaneSetIR);
    lane(name?: string): LaneBuilder;
}
export declare class LaneBuilder {
    private context;
    private lane;
    constructor(context: DslContext, lane: any);
    flowNodeRefs(...refs: string[]): this;
}
export declare class CollaborationBuilder {
    private context;
    private collaborationName;
    private participants;
    private messageFlows;
    constructor(context: DslContext, name: string);
    participant(name: string): ParticipantBuilder;
    messageFlow(sourceRef: string, targetRef: string, name?: string): MessageFlowBuilder;
}
export declare class ParticipantBuilder {
    private context;
    private participant;
    constructor(context: DslContext, participant: any);
    processRef(processId: string): this;
}
export declare class MessageFlowBuilder {
    private context;
    private flow;
    constructor(context: DslContext, flow: any);
    messageRef(messageRef: string): this;
}
//# sourceMappingURL=subprocess.d.ts.map