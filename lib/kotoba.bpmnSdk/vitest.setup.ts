// Vitest setup file
import { expect, vi } from 'vitest';

// Extend expect with custom matchers for BPMN testing
expect.extend({
  toBeValidBpmnProcess(received) {
    const pass = received && typeof received === 'object' && 'definitions' in received;
    if (pass) {
      return {
        message: () => `expected ${received} not to be a valid BPMN process`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${received} to be a valid BPMN process`,
        pass: false,
      };
    }
  },

  toHaveValidTasks(received) {
    const pass = received &&
                 Array.isArray(received.flowElements) &&
                 received.flowElements.some(el => el.type === 'task');
    if (pass) {
      return {
        message: () => `expected process not to have valid tasks`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected process to have valid tasks`,
        pass: false,
      };
    }
  },

  toBeCompletedTask(received) {
    const pass = received &&
                 typeof received === 'object' &&
                 received.status === 'completed';
    if (pass) {
      return {
        message: () => `expected task not to be completed`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected task to be completed`,
        pass: false,
      };
    }
  },
});

// Mock external dependencies
vi.mock('bpmn-engine', () => ({
  Engine: vi.fn().mockImplementation(() => ({
    execute: vi.fn(),
    getState: vi.fn(),
    resume: vi.fn(),
    stop: vi.fn(),
  })),
}));

vi.mock('moddle-xml', () => ({
  toXML: vi.fn().mockImplementation((obj, options) => Promise.resolve({ xml: '<xml>test</xml>' })),
  fromXML: vi.fn().mockImplementation(async (xml, options) => ({
    root: {
      $type: 'bpmn:Definitions',
      id: 'Definitions_1',
      name: 'Test Definitions',
      targetNamespace: 'http://www.etzhayyim.com/bpmn',
      rootElements: [
        {
          $type: 'bpmn:Process',
          id: 'Process_1',
          isExecutable: true,
          flowElements: [],
        },
      ],
      version: '1.0',
    },
  })),
}));

// Global test utilities
global.testUtils = {
  createMockProcess: () => ({
    id: 'test-process',
    isExecutable: true,
    flowElements: [],
    sequenceFlows: [],
  }),

  createMockBpmnIR: () => ({
    definitions: {
      id: 'Definitions_1',
      name: 'Test Definitions',
      targetNamespace: 'http://www.etzhayyim.com/bpmn',
      processes: [{
        id: 'test-process',
        isExecutable: true,
        flowElements: [],
        sequenceFlows: [],
      }],
      version: '1.0',
    },
  }),

  createMockEngine: () => ({
    execute: vi.fn(),
    getState: vi.fn(),
    resume: vi.fn(),
    stop: vi.fn(),
  }),
};
