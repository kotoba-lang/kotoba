// Merkle DAG: dsl_subprocess_builders
// DSL SubProcess Builders - Embedded/Event/Transaction/AdHoc

import type { SubProcessIR, LaneSetIR } from '@etzhayyim/bpmn-sdk-core';
import { ProcessBuilder } from '../bpmn-dsl.js';
import type { DslContext, MutableSubProcessIR } from '../bpmn-dsl.js';

// Base SubProcess Builder
export class BaseSubprocessBuilder {
  protected context: DslContext;
  protected subProcess: MutableSubProcessIR;

  constructor(context: DslContext, subProcess: MutableSubProcessIR) {
    this.context = context;
    this.subProcess = subProcess;
  }

  // Add flow elements to subprocess (similar to process builder)
  startEvent(name?: string): ProcessBuilder {
    // Create a nested process builder for subprocess content
    const nestedProcessId = this.context.generateId('NestedProcess');
    const nestedBuilder = new ProcessBuilder(
      this.context,
      nestedProcessId,
      name || 'SubProcess',
      false // Subprocesses are not executable by themselves
    );

    // The nested builder will add elements to the subprocess
    return nestedBuilder;
  }
}

// Embedded SubProcess Builder
export class EmbeddedSubprocessBuilder extends BaseSubprocessBuilder {
  // Embedded subprocesses can contain any flow elements
}

// Event SubProcess Builder
export class EventSubprocessBuilder extends BaseSubprocessBuilder {
  constructor(context: DslContext, subProcess: SubProcessIR) {
    super(context, subProcess);
    (this.subProcess as any).triggeredByEvent = true;
  }
}

// Transaction SubProcess Builder
export class TransactionSubprocessBuilder extends BaseSubprocessBuilder {
  compensate(): this {
    (this.subProcess as any).method = '##compensate';
    return this;
  }

  image(): this {
    (this.subProcess as any).method = '##image';
    return this;
  }

  store(): this {
    (this.subProcess as any).method = '##store';
    return this;
  }
}

// Ad-hoc SubProcess Builder
export class AdHocSubprocessBuilder extends BaseSubprocessBuilder {
  completionCondition(condition: string): this {
    (this.subProcess as any).completionCondition = condition;
    return this;
  }

  parallel(): this {
    (this.subProcess as any).ordering = 'Parallel';
    return this;
  }

  sequential(): this {
    (this.subProcess as any).ordering = 'Sequential';
    return this;
  }

  cancelRemainingInstances(cancel: boolean = true): this {
    (this.subProcess as any).cancelRemainingInstances = cancel;
    return this;
  }
}

// Lane Set Builder
export class LaneSetBuilder {
  private context: DslContext;
  private laneSet: LaneSetIR;

  constructor(context: DslContext, laneSet: LaneSetIR) {
    this.context = context;
    this.laneSet = laneSet;
  }

  lane(name?: string): LaneBuilder {
    const laneId = this.context.generateId('Lane');
    const lane = {
      id: laneId,
      name,
      flowNodeRefs: [],
    };
    this.laneSet.lanes.push(lane);
    return new LaneBuilder(this.context, lane);
  }
}

// Lane Builder
export class LaneBuilder {
  private context: DslContext;
  private lane: any;

  constructor(context: DslContext, lane: any) {
    this.context = context;
    this.lane = lane;
  }

  flowNodeRefs(...refs: string[]): this {
    this.lane.flowNodeRefs.push(...refs);
    return this;
  }
}

// Collaboration Builder (for multi-pool processes)
export class CollaborationBuilder {
  private context: DslContext;
  private collaborationName: string;
  private participants: any[] = [];
  private messageFlows: any[] = [];

  constructor(context: DslContext, name: string) {
    this.context = context;
    this.collaborationName = name;
  }

  participant(name: string): ParticipantBuilder {
    const participantId = this.context.generateId('Participant');
    const participant = {
      id: participantId,
      name,
    };
    this.participants.push(participant);
    return new ParticipantBuilder(this.context, participant);
  }

  messageFlow(sourceRef: string, targetRef: string, name?: string): MessageFlowBuilder {
    const flowId = this.context.generateId('MessageFlow');
    const flow = {
      id: flowId,
      name,
      sourceRef,
      targetRef,
    };
    this.messageFlows.push(flow);
    return new MessageFlowBuilder(this.context, flow);
  }
}

// Participant Builder
export class ParticipantBuilder {
  private context: DslContext;
  private participant: any;

  constructor(context: DslContext, participant: any) {
    this.context = context;
    this.participant = participant;
  }

  processRef(processId: string): this {
    this.participant.processRef = processId;
    return this;
  }
}

// Message Flow Builder
export class MessageFlowBuilder {
  private context: DslContext;
  private flow: any;

  constructor(context: DslContext, flow: any) {
    this.context = context;
    this.flow = flow;
  }

  messageRef(messageRef: string): this {
    this.flow.messageRef = messageRef;
    return this;
  }
}
