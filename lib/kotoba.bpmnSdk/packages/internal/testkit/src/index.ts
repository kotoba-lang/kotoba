// Merkle DAG: testkit_arbitraries
// Fast-check arbitraries for BPMN property-based testing

import fc from 'fast-check';
import type {
  BpmnIR,
  DefinitionsIR,
  ProcessIR,
  FlowElementIR,
  EventIR,
  TaskIR,
  GatewayIR,
  SequenceFlowIR,
} from '@etzhayyim/bpmn-sdk-core';
import type { Parameters } from 'fast-check';

// Custom arbitraries for BPMN elements
export const bpmnIdArb = fc.stringMatching(/^[a-zA-Z_][a-zA-Z0-9_]*$/).filter(id => id.length > 0 && id.length < 50);

export const bpmnNameArb = fc.string({ minLength: 1, maxLength: 100 });

export const eventTypeArb = fc.constantFrom('start' as const, 'end' as const, 'intermediate' as const, 'boundary' as const);

export const taskTypeArb = fc.constantFrom(
  'service' as const, 'user' as const, 'manual' as const, 'script' as const, 'businessRule' as const,
  'send' as const, 'receive' as const, 'callActivity' as const
);

export const gatewayTypeArb = fc.constantFrom('exclusive' as const, 'inclusive' as const, 'parallel' as const, 'eventBased' as const, 'complex' as const);

// Event IR arbitrary
export const eventIrArb: fc.Arbitrary<EventIR> = fc.record({
  type: fc.constant('event'),
  eventType: eventTypeArb,
  id: bpmnIdArb,
  name: fc.option(bpmnNameArb),
  eventDefinitions: fc.option(fc.array(fc.constant({ type: 'message' as const }))),
  attachedToRef: fc.option(bpmnIdArb),
  cancelActivity: fc.option(fc.boolean()),
});

// Task IR arbitrary
export const taskIrArb: fc.Arbitrary<TaskIR> = fc.record({
  type: fc.constant('task'),
  taskType: taskTypeArb,
  id: bpmnIdArb,
  name: fc.option(bpmnNameArb),
  implementation: fc.option(fc.string()),
  assignee: fc.option(fc.string()),
  candidateUsers: fc.option(fc.string()),
  candidateGroups: fc.option(fc.string()),
  formKey: fc.option(fc.string()),
  calledElement: fc.option(bpmnIdArb),
  script: fc.option(fc.string()),
  topic: fc.option(fc.string()),
  operationRef: fc.option(bpmnIdArb),
  class: fc.option(fc.string()),
  delegateExpression: fc.option(fc.string()),
  expression: fc.option(fc.string()),
  decisionRef: fc.option(bpmnIdArb),
  resultVariable: fc.option(fc.string()),
  messageRef: fc.option(bpmnIdArb),
  instantiate: fc.option(fc.boolean()),
});

// Gateway IR arbitrary
export const gatewayIrArb: fc.Arbitrary<GatewayIR> = fc.record({
  type: fc.constant('gateway'),
  gatewayType: gatewayTypeArb,
  id: bpmnIdArb,
  name: fc.option(bpmnNameArb),
  default: fc.option(bpmnIdArb),
  instantiate: fc.option(fc.boolean()),
  eventGatewayType: fc.option(fc.constantFrom('Exclusive', 'Parallel')),
  activationCondition: fc.option(fc.string()),
});

// Sequence Flow IR arbitrary
export const sequenceFlowIrArb: fc.Arbitrary<SequenceFlowIR> = fc.record({
  id: bpmnIdArb,
  name: fc.option(bpmnNameArb),
  sourceRef: bpmnIdArb,
  targetRef: bpmnIdArb,
  conditionExpression: fc.option(fc.string()),
  isImmediate: fc.option(fc.boolean()),
});

// Flow Element IR arbitrary
export const flowElementIrArb: fc.Arbitrary<FlowElementIR> = fc.oneof(
  eventIrArb,
  taskIrArb,
  gatewayIrArb
);

// Process IR arbitrary
export const processIrArb: fc.Arbitrary<ProcessIR> = fc.record({
  id: bpmnIdArb,
  name: fc.option(bpmnNameArb),
  isExecutable: fc.boolean(),
  flowElements: fc.array(flowElementIrArb, { minLength: 1, maxLength: 20 }),
  sequenceFlows: fc.array(sequenceFlowIrArb, { minLength: 0, maxLength: 20 }),
  participants: fc.option(fc.array(fc.record({ id: bpmnIdArb, name: fc.option(bpmnNameArb) }))) as fc.Arbitrary<ProcessIR['participants']>,
  artifacts: fc.option(fc.array(fc.record({ id: bpmnIdArb, name: fc.option(bpmnNameArb) }))) as fc.Arbitrary<ProcessIR['artifacts']>,
  laneSets: fc.option(fc.array(fc.record({
    id: bpmnIdArb,
    name: fc.option(bpmnNameArb),
    lanes: fc.array(fc.record({
      id: bpmnIdArb,
      name: fc.option(bpmnNameArb),
      flowNodeRefs: fc.option(fc.array(bpmnIdArb))
    }))
  }))) as fc.Arbitrary<ProcessIR['laneSets']>,
});

// Definitions IR arbitrary
export const definitionsIrArb: fc.Arbitrary<DefinitionsIR> = fc.record({
  id: bpmnIdArb,
  name: fc.option(bpmnNameArb),
  targetNamespace: fc.constant('http://www.etzhayyim.com/bpmn'),
  processes: fc.array(processIrArb, { minLength: 1, maxLength: 5 }),
  collaborations: fc.option(fc.array(fc.record({
    id: bpmnIdArb,
    name: fc.option(bpmnNameArb),
    participants: fc.array(fc.record({ id: bpmnIdArb, name: fc.option(bpmnNameArb) })),
    messageFlows: fc.array(fc.record({
      id: bpmnIdArb,
      name: fc.option(bpmnNameArb),
      sourceRef: bpmnIdArb,
      targetRef: bpmnIdArb
    }))
  }))) as fc.Arbitrary<DefinitionsIR['collaborations']>,
  messages: fc.option(fc.array(fc.record({
    id: bpmnIdArb,
    name: fc.option(bpmnNameArb)
  }))) as fc.Arbitrary<DefinitionsIR['messages']>,
  signals: fc.option(fc.array(fc.record({
    id: bpmnIdArb,
    name: fc.option(bpmnNameArb)
  }))) as fc.Arbitrary<DefinitionsIR['signals']>,
  errors: fc.option(fc.array(fc.record({
    id: bpmnIdArb,
    name: fc.option(bpmnNameArb)
  }))) as fc.Arbitrary<DefinitionsIR['errors']>,
  escalations: fc.option(fc.array(fc.record({
    id: bpmnIdArb,
    name: fc.option(bpmnNameArb)
  }))) as fc.Arbitrary<DefinitionsIR['escalations']>,
  dataStores: fc.option(fc.array(fc.record({
    id: bpmnIdArb,
    name: fc.option(bpmnNameArb)
  }))) as fc.Arbitrary<DefinitionsIR['dataStores']>,
  version: fc.option(fc.string()),
});

// BPMN IR arbitrary (main entry point)
export const bpmnIrArb: fc.Arbitrary<BpmnIR> = fc.record({
  definitions: definitionsIrArb,
});

// Test utilities
export class BpmnPropertyTest {
  static createProperty<T>(
    arbitrary: fc.Arbitrary<T>,
    property: (value: T) => boolean | void
  ) {
    return fc.property(arbitrary, property);
  }

  static createAsyncProperty<T>(
    arbitrary: fc.Arbitrary<T>,
    property: (value: T) => Promise<boolean | void>
  ) {
    return fc.asyncProperty(arbitrary, property);
  }

  static assert<T>(
    property: fc.IProperty<T>,
    options: Parameters<T> = {}
  ): void {
    fc.assert(property, {
      numRuns: 100,
      ...options,
    });
  }

  static async assertAsync<T>(
    property: fc.IAsyncProperty<T>,
    options: Parameters<T> = {}
  ): Promise<void> {
    await fc.assert(property, {
      numRuns: 100,
      ...options,
    });
  }
}
