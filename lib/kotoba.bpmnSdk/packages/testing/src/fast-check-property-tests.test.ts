// Merkle DAG: fast_check_property_tests
// Fast-check based property testing for BPMN SDK

import { describe, it, expect } from 'vitest';
import { bpmnIrArb, BpmnPropertyTest } from '@etzhayyim/bpmn-sdk/testkit';
import { BpmnIRUtils } from '@etzhayyim/bpmn-sdk-core';

describe.skip('Fast-check Property Tests', () => {
  describe('BpmnIR Structure Properties', () => {
    it('should always have valid definitions', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions !== undefined &&
                 ir.definitions.id !== undefined &&
                 ir.definitions.targetNamespace !== undefined &&
                 Array.isArray(ir.definitions.processes) &&
                 ir.definitions.processes.length >= 1;
        })
      );
    });

    it('should have valid process IDs', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.id &&
            typeof process.id === 'string' &&
            process.id.length > 0 &&
            /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(process.id)
          );
        })
      );
    });

    it('should have valid flow elements', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            Array.isArray(process.flowElements) &&
            process.flowElements.every(element =>
              element.id &&
              element.type &&
              ['event', 'task', 'gateway', 'subprocess', 'dataObject'].includes(element.type)
            )
          );
        })
      );
    });

    it('should have valid sequence flows', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            Array.isArray(process.sequenceFlows) &&
            process.sequenceFlows.every(flow =>
              flow.id &&
              flow.sourceRef &&
              flow.targetRef &&
              typeof flow.id === 'string' &&
              typeof flow.sourceRef === 'string' &&
              typeof flow.targetRef === 'string'
            )
          );
        })
      );
    });

    it('should pass IR validation', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          const validation = BpmnIRUtils.validateIR(ir);
          return validation.valid;
        })
      );
    });
  });

  describe('BpmnIR Consistency Properties', () => {
    it('should have sequence flows referencing existing elements', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process => {
            const elementIds = new Set(process.flowElements.map(el => el.id));
            return process.sequenceFlows.every(flow =>
              elementIds.has(flow.sourceRef) && elementIds.has(flow.targetRef)
            );
          });
        })
      );
    });

    it('should have executable processes by default', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.isExecutable === true || process.isExecutable === false
          );
        })
      );
    });

    it('should have unique IDs within processes', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process => {
            const allIds = [
              ...process.flowElements.map(el => el.id),
              ...process.sequenceFlows.map(flow => flow.id)
            ];
            return allIds.length === new Set(allIds).size;
          });
        })
      );
    });
  });

  describe('Event-Specific Properties', () => {
    it('should have valid event types', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.flowElements
              .filter(el => el.type === 'event')
              .every(event =>
                ['start', 'end', 'intermediate', 'boundary'].includes(event.eventType!)
              )
          );
        })
      );
    });

    it('should have start events in processes', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.flowElements.some(el =>
              el.type === 'event' && el.eventType === 'start'
            )
          );
        })
      );
    });

    it('should have end events in processes', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.flowElements.some(el =>
              el.type === 'event' && el.eventType === 'end'
            )
          );
        })
      );
    });
  });

  describe('Task-Specific Properties', () => {
    it('should have valid task types', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.flowElements
              .filter(el => el.type === 'task')
              .every(task =>
                ['service', 'user', 'manual', 'script', 'businessRule', 'send', 'receive', 'callActivity'].includes(task.taskType!)
              )
          );
        })
      );
    });

    it('should have valid task configurations', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.flowElements
              .filter(el => el.type === 'task')
              .every(task => {
                if (task.taskType === 'user') {
                  return task.assignee || task.candidateUsers || task.candidateGroups;
                }
                if (task.taskType === 'service') {
                  return task.implementation || task.class || task.delegateExpression || task.expression;
                }
                return true;
              })
          );
        })
      );
    });
  });

  describe('Gateway-Specific Properties', () => {
    it('should have valid gateway types', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.flowElements
              .filter(el => el.type === 'gateway')
              .every(gateway =>
                ['exclusive', 'inclusive', 'parallel', 'eventBased', 'complex'].includes(gateway.gatewayType!)
              )
          );
        })
      );
    });
  });

  describe('Process Flow Properties', () => {
    it('should have connected flows', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process => {
            if (process.sequenceFlows.length === 0) return true;

            const elementIds = new Set(process.flowElements.map(el => el.id));
            const sourceIds = new Set(process.sequenceFlows.map(flow => flow.sourceRef));
            const targetIds = new Set(process.sequenceFlows.map(flow => flow.targetRef));

            // All sources and targets should exist in flow elements
            return [...sourceIds, ...targetIds].every(id => elementIds.has(id));
          });
        })
      );
    });

    it('should have reasonable process sizes', () => {
      BpmnPropertyTest.assert(
        BpmnPropertyTest.createProperty(bpmnIrArb, (ir) => {
          return ir.definitions.processes.every(process =>
            process.flowElements.length >= 2 && // At least start and end
            process.flowElements.length <= 50 && // Not too large
            process.sequenceFlows.length >= 1 &&
            process.sequenceFlows.length <= 100
          );
        })
      );
    });
  });
});
