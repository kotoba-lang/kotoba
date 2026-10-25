// Merkle DAG: dsl_gateway_builders
// DSL Gateway Builders - Exclusive/Inclusive/Parallel/EventBased/Complex

import type { GatewayIR, SequenceFlowIR } from '@etzhayyim/bpmn-sdk-core';
import type { DslContext, MutableGatewayIR, MutableSequenceFlowIR } from '../bpmn-dsl.js';

// Base Gateway Builder
export class BaseGatewayBuilder {
  protected context: DslContext;
  protected gateway: MutableGatewayIR;

  constructor(context: DslContext, gateway: MutableGatewayIR) {
    this.context = context;
    this.gateway = gateway;
  }

  // Set gateway name
  name(name: string): this {
    this.gateway.name = name;
    return this;
  }

  default(flowId: string): this {
    (this.gateway as any).default = flowId;
    return this;
  }
}

// Exclusive Gateway Builder (XOR)
export class ExclusiveGatewayBuilder extends BaseGatewayBuilder {
  // Exclusive gateways use default for default flow
}

// Inclusive Gateway Builder (OR)
export class InclusiveGatewayBuilder extends BaseGatewayBuilder {
  // Inclusive gateways use default for default flow
}

// Parallel Gateway Builder (AND)
export class ParallelGatewayBuilder extends BaseGatewayBuilder {
  // Parallel gateways don't have default flows
}

// Event-based Gateway Builder
export class EventBasedGatewayBuilder extends BaseGatewayBuilder {
  instantiate(instantiate: boolean = true): this {
    (this.gateway as any).instantiate = instantiate;
    return this;
  }

  exclusive(): this {
    (this.gateway as any).eventGatewayType = 'Exclusive';
    return this;
  }

  parallel(): this {
    (this.gateway as any).eventGatewayType = 'Parallel';
    return this;
  }
}

// Complex Gateway Builder
export class ComplexGatewayBuilder extends BaseGatewayBuilder {
  activationCondition(condition: string): this {
    (this.gateway as any).activationCondition = condition;
    return this;
  }
}

// Sequence Flow Builder for conditional flows
export class SequenceFlowBuilder {
  private context: DslContext;
  private flow: MutableSequenceFlowIR;

  constructor(context: DslContext, flow: MutableSequenceFlowIR) {
    this.context = context;
    this.flow = flow;
  }

  condition(expression: string): this {
    (this.flow as any).conditionExpression = expression;
    return this;
  }

  immediate(immediate: boolean = true): this {
    (this.flow as any).isImmediate = immediate;
    return this;
  }
}
