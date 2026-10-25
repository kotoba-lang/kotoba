// Merkle DAG: dsl_event_builders
// DSL Event Builders - Start/End/Intermediate/Boundary Events

import type { EventIR, EventDefinitionIR } from '@etzhayyim/bpmn-sdk-core';
import type { DslContext, MutableEventIR } from '../bpmn-dsl.js';

// Base Event Builder
export class BaseEventBuilder {
  protected context: DslContext;
  protected event: MutableEventIR;

  constructor(context: DslContext, event: MutableEventIR) {
    this.context = context;
    this.event = event;
  }

  // Set event name
  name(name: string): this {
    this.event.name = name;
    return this;
  }

  // Common event configurations
  message(messageRef?: string): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'message',
      messageRef,
    });
    return this;
  }

  signal(signalRef?: string): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'signal',
      signalRef,
    });
    return this;
  }

  error(errorRef?: string): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'error',
      errorRef,
    });
    return this;
  }

  timer(config: { timeDate?: string; timeCycle?: string; timeDuration?: string }): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'timer',
      ...config,
    });
    return this;
  }

  compensation(activityRef?: string, waitForCompletion?: boolean): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'compensation',
      activityRef,
      waitForCompletion,
    });
    return this;
  }

  conditional(condition: string): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'conditional',
      condition,
    });
    return this;
  }

  link(name?: string): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'link',
      name,
    });
    return this;
  }

  terminate(): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'terminate',
    });
    return this;
  }

  cancel(): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'cancel',
    });
    return this;
  }

  escalation(escalationRef?: string): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'escalation',
      escalationRef,
    });
    return this;
  }

  multiple(): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'multiple',
    });
    return this;
  }

  parallelMultiple(): this {
    this.event.eventDefinitions = this.event.eventDefinitions || [];
    this.event.eventDefinitions.push({
      type: 'parallelMultiple',
    });
    return this;
  }
}

// Start Event Builder
export class StartEventBuilder extends BaseEventBuilder {
  // Start events are always interrupting and don't have boundary-specific configs
}

// End Event Builder
export class EndEventBuilder extends BaseEventBuilder {
  // End events don't have special configurations
}

// Intermediate Catch Event Builder
export class IntermediateCatchEventBuilder extends BaseEventBuilder {
  // Intermediate catch events support all event definitions
}

// Boundary Event Builder
export class BoundaryEventBuilder extends BaseEventBuilder {
  attachedToRef(activityId: string): this {
    (this.event as any).attachedToRef = activityId;
    return this;
  }

  nonInterrupting(): this {
    // Mutable cast for building
    (this.event as any).cancelActivity = false;
    return this;
  }

  interrupting(): this {
    // Mutable cast for building
    (this.event as any).cancelActivity = true;
    return this;
  }
}
