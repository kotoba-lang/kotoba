import { describe, it, expect } from 'vitest';
import * as Core from './index.js';

// Test core exports
describe('@etzhayyim/bpmn-sdk-core', () => {
  it('should export core utilities', () => {
    expect(Core.BpmnIRUtils).toBeDefined();
    expect(typeof Core.BpmnIRUtils.generateId).toBe('function');
    expect(typeof Core.BpmnIRUtils.validateIR).toBe('function');
  });

  it('should create valid IR structure', () => {
    const ir: Core.BpmnIR = {
      definitions: {
        id: 'test-definitions',
        name: 'Test Definitions',
        targetNamespace: 'http://example.com',
        processes: [{
          id: 'test-process',
          isExecutable: true,
          flowElements: [],
          sequenceFlows: []
        }],
        version: '1.0.0'
      }
    };

    expect(ir.definitions.id).toBe('test-definitions');
    expect(ir.definitions.processes).toHaveLength(1);
    expect(ir.definitions.processes[0].id).toBe('test-process');
  });

  describe('BpmnIRUtils', () => {
    describe('generateId()', () => {
      it('should generate an ID with default prefix', () => {
        const id = Core.BpmnIRUtils.generateId();
        expect(typeof id).toBe('string');
        expect(id).toMatch(/^id_\d+_[a-z0-9]+$/);
      });

      it('should generate an ID with custom prefix', () => {
        const id = Core.BpmnIRUtils.generateId('test');
        expect(typeof id).toBe('string');
        expect(id).toMatch(/^test_\d+_[a-z0-9]+$/);
      });

      it('should generate unique IDs', () => {
        const id1 = Core.BpmnIRUtils.generateId();
        const id2 = Core.BpmnIRUtils.generateId();
        expect(id1).not.toBe(id2);
      });
    });

    describe('validateIR()', () => {
      it('should validate a valid IR', () => {
        const validIR: Core.BpmnIR = {
          definitions: {
            id: 'test-definitions',
            targetNamespace: 'http://example.com',
            processes: [{
              id: 'test-process',
              isExecutable: true,
              flowElements: [{
                type: 'event',
                eventType: 'start',
                id: 'start-event',
                name: 'Start'
              }],
              sequenceFlows: []
            }]
          }
        };

        const result = Core.BpmnIRUtils.validateIR(validIR);
        expect(result.valid).toBe(true);
        expect(result.errors).toHaveLength(0);
      });

      it('should reject IR without definitions id', () => {
        const invalidIR: any = {
          definitions: {
            targetNamespace: 'http://example.com',
            processes: [{
              id: 'test-process',
              isExecutable: true,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        const result = Core.BpmnIRUtils.validateIR(invalidIR);
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Definitions must have an id');
      });

      it('should reject IR without targetNamespace', () => {
        const invalidIR: any = {
          definitions: {
            id: 'test-definitions',
            processes: [{
              id: 'test-process',
              isExecutable: true,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        const result = Core.BpmnIRUtils.validateIR(invalidIR);
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Definitions must have a targetNamespace');
      });

      it('should reject process without id', () => {
        const invalidIR: any = {
          definitions: {
            id: 'test-definitions',
            targetNamespace: 'http://example.com',
            processes: [{
              isExecutable: true,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        const result = Core.BpmnIRUtils.validateIR(invalidIR);
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Process 0 must have an id');
      });

      it('should reject process without flow elements', () => {
        const invalidIR: any = {
          definitions: {
            id: 'test-definitions',
            targetNamespace: 'http://example.com',
            processes: [{
              id: 'test-process',
              isExecutable: true,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        const result = Core.BpmnIRUtils.validateIR(invalidIR);
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Process test-process must have at least one flow element');
      });

      it('should handle multiple validation errors', () => {
        const invalidIR: any = {
          definitions: {
            processes: [{
              flowElements: []
            }]
          }
        };

        const result = Core.BpmnIRUtils.validateIR(invalidIR);
        expect(result.valid).toBe(false);
        expect(result.errors.length).toBeGreaterThan(1);
      });
    });
  });
});

