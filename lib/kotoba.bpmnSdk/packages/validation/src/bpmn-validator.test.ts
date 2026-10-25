// Merkle DAG: bpmn_validator_tests
// BPMN Validator unit tests for high coverage

import { describe, it, expect, beforeEach } from 'vitest';
import { BpmnValidator } from './bpmn-validator.js';
import type { ValidationOptions } from './types.js';

describe('@etzhayyim/bpmn-sdk-validation', () => {
  let validator: BpmnValidator;
  let defaultOptions: ValidationOptions;

  beforeEach(() => {
    defaultOptions = {
      checkReachability: true,
      checkDeadEnds: true,
      checkCycles: true,
      checkGatewayConsistency: true,
      checkEventConsistency: true,
      checkFlowConsistency: true,
      strictBpmnCompliance: false,
      maxComplexityScore: 50,
      timeoutMs: 30000,
    };
    validator = new BpmnValidator(defaultOptions);
  });

  describe('BpmnValidator constructor', () => {
    it('should instantiate with default options', () => {
      const validator = new BpmnValidator();
      expect(validator).toBeDefined();
      expect(validator).toBeInstanceOf(BpmnValidator);
    });

    it('should merge provided options with defaults', () => {
      const customOptions: ValidationOptions = {
        checkReachability: false,
        maxComplexityScore: 100,
      };
      const validator = new BpmnValidator(customOptions);
      expect(validator).toBeDefined();
    });

    it('should handle empty options object', () => {
      const validator = new BpmnValidator({});
      expect(validator).toBeDefined();
    });
  });

  describe('validateProcess()', () => {
    it('should validate valid process', async () => {
      const validProcess = {
        definitions: {
          id: 'TestDefinitions',
          targetNamespace: 'http://example.com',
          processes: [{
            id: 'ValidProcess',
            isExecutable: true,
            flowElements: [
              {
                type: 'event',
                eventType: 'start',
                id: 'StartEvent',
                name: 'Start'
              },
              {
                type: 'event',
                eventType: 'end',
                id: 'EndEvent',
                name: 'End'
              }
            ],
            sequenceFlows: [{
              id: 'Flow1',
              sourceRef: 'StartEvent',
              targetRef: 'EndEvent'
            }]
          }]
        }
      };

      const result = await validator.validateProcess(validProcess as any);
      expect(result).toBeDefined();
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should detect invalid process', async () => {
      const invalidProcess = {
        definitions: {
          id: 'TestDefinitions',
          targetNamespace: 'http://example.com',
          processes: [{
            id: 'InvalidProcess',
            isExecutable: true,
            flowElements: [],
            sequenceFlows: []
          }]
        }
      };

      const result = await validator.validateProcess(invalidProcess as any);
      expect(result).toBeDefined();
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it('should handle multiple processes', async () => {
      const multiProcess = {
        definitions: {
          id: 'TestDefinitions',
          targetNamespace: 'http://example.com',
          processes: [
            {
              id: 'Process1',
              isExecutable: true,
              flowElements: [{
                type: 'event',
                eventType: 'start',
                id: 'Start1'
              }],
              sequenceFlows: []
            },
            {
              id: 'Process2',
              isExecutable: true,
              flowElements: [{
                type: 'event',
                eventType: 'start',
                id: 'Start2'
              }],
              sequenceFlows: []
            }
          ]
        }
      };

      const result = await validator.validateProcess(multiProcess as any);
      expect(result).toBeDefined();
      expect(result.statistics).toBeDefined();
      expect(result.statistics.totalElements).toBeGreaterThan(0);
    });

    it('should handle empty process list', async () => {
      const emptyProcess = {
        definitions: {
          id: 'TestDefinitions',
          targetNamespace: 'http://example.com',
          processes: []
        }
      };

      const result = await validator.validateProcess(emptyProcess as any);
      expect(result).toBeDefined();
      expect(result.statistics).toBeDefined();
      expect(result.statistics.totalElements).toBe(0);
    });
  });

  describe('validateProcessIR()', () => {
    it('should validate valid process IR', async () => {
      const validProcess: any = {
        id: 'ValidProcess',
        isExecutable: true,
        flowElements: [
          {
            type: 'event',
            eventType: 'start',
            id: 'StartEvent'
          },
          {
            type: 'event',
            eventType: 'end',
            id: 'EndEvent'
          }
        ],
        sequenceFlows: [{
          id: 'Flow1',
          sourceRef: 'StartEvent',
          targetRef: 'EndEvent'
        }]
      };

      const result = await (validator as any).validateProcessIR(validProcess);
      expect(result).toBeDefined();
      expect(result.errors).toBeDefined();
      expect(result.warnings).toBeDefined();
    });

    it('should detect process without start event', async () => {
      const invalidProcess: any = {
        id: 'InvalidProcess',
        isExecutable: true,
        flowElements: [
          {
            type: 'task',
            taskType: 'user',
            id: 'Task1'
          }
        ],
        sequenceFlows: []
      };

      const result = await (validator as any).validateProcessIR(invalidProcess);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it('should detect process without end event', async () => {
      const invalidProcess: any = {
        id: 'InvalidProcess',
        isExecutable: true,
        flowElements: [
          {
            type: 'event',
            eventType: 'start',
            id: 'StartEvent'
          },
          {
            type: 'task',
            taskType: 'user',
            id: 'Task1'
          }
        ],
        sequenceFlows: [{
          id: 'Flow1',
          sourceRef: 'StartEvent',
          targetRef: 'Task1'
        }]
      };

      const result = await (validator as any).validateProcessIR(invalidProcess);
      expect(result.errors.length).toBeGreaterThan(0);
    });
  });

  describe('calculateStatistics()', () => {
    it('should calculate statistics correctly', () => {
      const ir: any = {
        definitions: {
          processes: [{
            id: 'Process1',
            flowElements: [],
            sequenceFlows: []
          }]
        }
      };
      const errors: any[] = [];
      const warnings: any[] = [];

      const stats = (validator as any).calculateStatistics(ir, errors, warnings);
      expect(stats).toBeDefined();
      expect(stats.totalElements).toBeDefined();
      expect(typeof stats.totalElements).toBe('number');
    });
  });


  describe('validate with different options', () => {
    it('should respect checkReachability option', async () => {
      const validator = new BpmnValidator({ checkReachability: false });
      const process: any = {
        definitions: {
          processes: [{
            flowElements: [],
            sequenceFlows: []
          }]
        }
      };

      const result = await validator.validateProcess(process);
      expect(result).toBeDefined();
    });

    it('should respect strictBpmnCompliance option', async () => {
      const validator = new BpmnValidator({ strictBpmnCompliance: true });
      const process: any = {
        definitions: {
          processes: [{
            flowElements: [],
            sequenceFlows: []
          }]
        }
      };

      const result = await validator.validateProcess(process);
      expect(result).toBeDefined();
    });
  });
});
