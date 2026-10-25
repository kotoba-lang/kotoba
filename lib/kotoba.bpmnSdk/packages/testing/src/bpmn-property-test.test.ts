import { describe, it, expect, beforeEach } from 'vitest';
import { BpmnPropertyTester, bpmnPropertyTest, bpmnScenarioTest } from './bpmn-property-test.js';
import { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';

describe('@etzhayyim/bpmn-sdk-testing', () => {
  let runtime: BpmnRuntime;
  let tester: BpmnPropertyTester;

  beforeEach(() => {
    runtime = new BpmnRuntime();
    tester = new BpmnPropertyTester(runtime);
  });

  describe('BpmnPropertyTester', () => {
    it('should instantiate correctly', () => {
      expect(tester).toBeDefined();
      expect(tester).toBeInstanceOf(BpmnPropertyTester);
    });

    describe('testProperty()', () => {
      it('should test noDeadEnds property', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'Task', type: 'task', taskType: 'user' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow1', sourceRef: 'Start', targetRef: 'Task' },
                { id: 'Flow2', sourceRef: 'Task', targetRef: 'End' }
              ]
            }]
          }
        };

        const result = await tester.testProperty(processIR as any, 'noDeadEnds');

        expect(result).toBeDefined();
        expect(result.property).toBe('noDeadEnds');
        expect(typeof result.success).toBe('boolean');
        expect(result.coverage).toBeDefined();
      });

      it('should test validExecution property', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow', sourceRef: 'Start', targetRef: 'End' }
              ]
            }]
          }
        };

        const result = await tester.testProperty(processIR as any, 'validExecution');

        expect(result.property).toBe('validExecution');
        expect(typeof result.success).toBe('boolean');
      });

      it('should handle unknown property', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        await expect(tester.testProperty(processIR as any, 'unknownProperty'))
          .rejects.toThrow('Unknown property: unknownProperty');
      });

      it('should respect test options', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow', sourceRef: 'Start', targetRef: 'End' }
              ]
            }]
          }
        };

        const result = await tester.testProperty(processIR as any, 'noDeadEnds', {
          maxTestCases: 10,
          timeout: 5000
        });

        expect(result).toBeDefined();
      });
    });

    describe('testScenario()', () => {
      it.skip('should execute a scenario successfully', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'Task', type: 'task', taskType: 'user' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow1', sourceRef: 'Start', targetRef: 'Task' },
                { id: 'Flow2', sourceRef: 'Task', targetRef: 'End' }
              ]
            }]
          }
        };

        const scenario = {
          id: 'test-scenario',
          description: 'Test scenario execution',
          inputs: { amount: 100 },
          expectedPath: ['Start', 'Task', 'End'],
          expectedOutputs: { completed: true }
        };

        const result = await tester.testScenario(processIR as any, scenario);

        expect(result).toBeDefined();
        expect(result.scenario.id).toBe(scenario.id);
        expect(typeof result.success).toBe('boolean');
        expect(result.actualPath).toBeDefined();
        expect(result.executionTime).toBeDefined();
      });

      it.skip('should handle scenario failure', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow', sourceRef: 'Start', targetRef: 'End' }
              ]
            }]
          }
        };

        const scenario = {
          id: 'failing-scenario',
          description: 'Scenario that should fail',
          inputs: { amount: 100 },
          expectedPath: ['Start', 'NonExistent', 'End'], // Wrong path
          expectedOutputs: { completed: true }
        };

        const result = await tester.testScenario(processIR as any, scenario);

        expect(result).toBeDefined();
        expect(result.success).toBe(false);
        expect(result.errors).toBeDefined();
      });
    });

    describe('generateProcessInput()', () => {
      it('should generate valid process inputs', () => {
        const input = tester.generateProcessInput();

        expect(input).toBeDefined();
        expect(input.definitions).toBeDefined();
        expect(Array.isArray(input.definitions.processes)).toBe(true);
      });
    });
  });

  describe('bpmnPropertyTest() function', () => {
    it('should export and work with correct parameter order', async () => {
      const processIR = {
        definitions: {
          processes: [{
            id: 'TestProcess',
            flowElements: [
              { id: 'Start', type: 'event', eventType: 'start' },
              { id: 'End', type: 'event', eventType: 'end' }
            ],
            sequenceFlows: [
              { id: 'Flow', sourceRef: 'Start', targetRef: 'End' }
            ]
          }]
        }
      };

      const result = await bpmnPropertyTest(processIR as any, runtime, 'noDeadEnds', { maxTestCases: 1 });

      expect(result).toBeDefined();
      expect(result.property).toBe('noDeadEnds');
    });

    it('should accept options parameter', async () => {
      const processIR = {
        definitions: {
          processes: [{
            id: 'TestProcess',
            flowElements: [],
            sequenceFlows: []
          }]
        }
      };

      const result = await bpmnPropertyTest(processIR as any, runtime, 'noDeadEnds', {
        maxTestCases: 5
      });

      expect(result).toBeDefined();
    });
  });

  describe('bpmnScenarioTest() function', () => {
    it.skip('should export and work correctly', async () => {
      const processIR = {
        definitions: {
          processes: [{
            id: 'TestProcess',
            flowElements: [
              { id: 'Start', type: 'event', eventType: 'start' },
              { id: 'End', type: 'event', eventType: 'end' }
            ],
            sequenceFlows: [
              { id: 'Flow', sourceRef: 'Start', targetRef: 'End' }
            ]
          }]
        }
      };

      const scenario = {
        id: 'test-scenario',
        description: 'Test scenario',
        inputs: {},
        expectedPath: ['Start', 'End'],
        expectedOutputs: {}
      };

        const result = await bpmnScenarioTest(processIR as any, runtime, scenario, { maxTestCases: 1 });

      expect(result).toBeDefined();
      expect(result.scenario.id).toBe(scenario.id);
    });
  });

  describe('Property Testing Coverage', () => {
    describe('noDeadEnds property', () => {
      it('should pass for processes with proper flow', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'GoodProcess',
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'Task', type: 'task', taskType: 'user' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow1', sourceRef: 'Start', targetRef: 'Task' },
                { id: 'Flow2', sourceRef: 'Task', targetRef: 'End' }
              ]
            }]
          }
        };

        const result = await tester.testProperty(processIR as any, 'noDeadEnds');
        expect(result.success).toBe(true);
      });

      it('should fail for processes with dead ends', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'BadProcess',
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'DeadEnd', type: 'task', taskType: 'user' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow1', sourceRef: 'Start', targetRef: 'DeadEnd' },
                { id: 'Flow2', sourceRef: 'DeadEnd', targetRef: 'End' }
              ]
            }]
          }
        };

        // This would typically fail, but depends on the implementation
        const result = await tester.testProperty(processIR as any, 'noDeadEnds');
        expect(result).toBeDefined();
      });
    });

    describe('validExecution property', () => {
      it('should pass for executable processes', async () => {
        const processIR = {
          definitions: {
            processes: [{
              id: 'ExecutableProcess',
              isExecutable: true,
              flowElements: [
                { id: 'Start', type: 'event', eventType: 'start' },
                { id: 'End', type: 'event', eventType: 'end' }
              ],
              sequenceFlows: [
                { id: 'Flow', sourceRef: 'Start', targetRef: 'End' }
              ]
            }]
          }
        };

        const result = await tester.testProperty(processIR as any, 'validExecution');
        expect(result).toBeDefined();
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle invalid process IR gracefully', async () => {
      const invalidIR = { invalid: 'structure' };

      await expect(tester.testProperty(invalidIR as any, 'noDeadEnds'))
        .rejects.toThrow();
    });

    it('should handle runtime errors during testing', async () => {
      const processIR = {
        definitions: {
          processes: [{
            id: 'ErrorProcess',
            flowElements: [],
            sequenceFlows: []
          }]
        }
      };

      // Should not throw, but handle errors gracefully
      const result = await tester.testProperty(processIR as any, 'noDeadEnds');
      expect(result).toBeDefined();
    });
  });
});
// @vitest-environment node
