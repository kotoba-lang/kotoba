import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { BpmnRuntime, ExecutionContext } from './bpmn-runtime.js';

describe('@etzhayyim/bpmn-sdk-runtime', () => {
  let runtime: BpmnRuntime;
  let mockEngine: any;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create runtime instance
    runtime = new BpmnRuntime();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('BpmnRuntime', () => {
    it('should instantiate correctly', () => {
      expect(runtime).toBeDefined();
      expect(runtime).toBeInstanceOf(BpmnRuntime);
    });

    describe('deployProcess()', () => {
      it('should deploy a process and return process ID', async () => {
        const ir = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        const processId = await runtime.deployProcess(ir as any, 'custom-id');

        expect(processId).toBe('custom-id');
      });

      it('should generate process ID if not provided', async () => {
        const ir = {
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        const processId = await runtime.deployProcess(ir as any);

        expect(processId).toBe('TestProcess');
      });

      it('should throw error if no process ID found', async () => {
        const ir = {
          definitions: {
            processes: []
          }
        };

        await expect(runtime.deployProcess(ir as any)).rejects.toThrow('No process ID found in BPMN IR');
      });

      it('should throw error if process has no ID', async () => {
        const ir = {
          definitions: {
            processes: [{
              flowElements: [],
              sequenceFlows: []
            }]
          }
        };

        await expect(runtime.deployProcess(ir as any)).rejects.toThrow('No process ID found in BPMN IR');
      });

      it('should handle multiple processes', async () => {
        const ir = {
          definitions: {
            processes: [
              { id: 'Process1', flowElements: [], sequenceFlows: [] },
              { id: 'Process2', flowElements: [], sequenceFlows: [] }
            ]
          }
        };

        const processId1 = await runtime.deployProcess(ir as any, 'process-1');
        const processId2 = await runtime.deployProcess(ir as any, 'process-2');

        expect(processId1).toBe('process-1');
        expect(processId2).toBe('process-2');
      });
    });

    describe('startInstance()', () => {
      it('should start a process instance', async () => {
        const processId = 'test-process';
        const variables = { amount: 100, userId: 'user-1' };

        // Deploy process first
        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        const context = await runtime.startInstance(deployedId, { variables });

        expect(context).toBeDefined();
        expect(context.processId).toBe(deployedId);
        expect(context.variables).toEqual(variables);
        expect(context.status).toBe('completed');
        expect(context.startTime).toBeInstanceOf(Date);
      });

      it('should generate instance ID if not provided', async () => {
        const processId = 'test-process';

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        const context = await runtime.startInstance(deployedId);

        expect(context.instanceId).toBeDefined();
        expect(typeof context.instanceId).toBe('string');
      });

      it('should use provided instance ID', async () => {
        const processId = 'test-process';
        const instanceId = 'custom-instance-id';

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        const context = await runtime.startInstance(deployedId, { instanceId });

        expect(context.instanceId).toBe(instanceId);
      });

      it('should throw error for non-existent process', async () => {
        await expect(runtime.startInstance('non-existent-process'))
          .rejects.toThrow('Process non-existent-process not found');
      });
    });

    describe('signal()', () => {
      it('should send signal to process instance', async () => {
        const processId = 'test-process';
        const instanceId = 'test-instance';
        const signalId = 'test-signal';
        const payload = { data: 'test' };

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        await runtime.startInstance(deployedId, { instanceId });

        // Signal should not throw
        await expect(runtime.signal(deployedId, instanceId, signalId, payload))
          .resolves.not.toThrow();
      });

      it('should handle signal without payload', async () => {
        const processId = 'test-process';
        const instanceId = 'test-instance';
        const signalId = 'test-signal';

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        await runtime.startInstance(deployedId, { instanceId });

        await expect(runtime.signal(deployedId, instanceId, signalId))
          .resolves.not.toThrow();
      });
    });

    describe('sendMessage()', () => {
      it('should send message to process instance', async () => {
        const processId = 'test-process';
        const instanceId = 'test-instance';
        const messageId = 'test-message';
        const payload = { data: 'test' };

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        await runtime.startInstance(deployedId, { instanceId });

        await expect(runtime.sendMessage(deployedId, instanceId, messageId, payload))
          .resolves.not.toThrow();
      });
    });

    describe('getExecutionContext()', () => {
      it('should return execution context for running instance', async () => {
        const processId = 'test-process';
        const instanceId = 'test-instance';

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        await runtime.startInstance(deployedId, { instanceId });

        const context = await runtime.getExecutionContext(deployedId, instanceId);

        expect(context).toBeDefined();
        expect(context?.processId).toBe(deployedId);
        expect(context?.instanceId).toBe(instanceId);
      });

      it('should return null for non-existent instance', async () => {
        const context = await runtime.getExecutionContext('non-existent', 'instance');

        expect(context).toBeNull();
      });
    });

    describe('Event Handling', () => {
      it('should register event listeners', () => {
        const listener = vi.fn();

        runtime.onEvent(listener);

        expect(runtime).toBeDefined(); // Listener registration doesn't throw
      });

      it('should remove event listeners', () => {
        const listener = vi.fn();

        runtime.onEvent(listener);
        runtime.offEvent(listener);

        expect(runtime).toBeDefined(); // Listener removal doesn't throw
      });

      it('should handle multiple event listeners', () => {
        const listener1 = vi.fn();
        const listener2 = vi.fn();

        runtime.onEvent(listener1);
        runtime.onEvent(listener2);

        expect(runtime).toBeDefined();
      });
    });

    describe('Process State Management', () => {
      it('should handle process lifecycle correctly', async () => {
        const processId = 'test-process';
        const instanceId = 'test-instance';

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        // Start instance
        const context = await runtime.startInstance(deployedId, { instanceId });
        expect(context.status).toBe('completed');

        // Get context
        const retrievedContext = await runtime.getExecutionContext(deployedId, instanceId);
        expect(retrievedContext?.status).toBe('completed');
      });

      it('should handle concurrent instances', async () => {
        const processId = 'test-process';

        const deployedId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: processId,
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, processId);

        const instance1 = await runtime.startInstance(deployedId, { instanceId: 'instance-1' });
        const instance2 = await runtime.startInstance(deployedId, { instanceId: 'instance-2' });

        expect(instance1.instanceId).toBe('instance-1');
        expect(instance2.instanceId).toBe('instance-2');
        expect(instance1.processId).toBe(deployedId);
        expect(instance2.processId).toBe(deployedId);
      });
    });

    describe('Error Handling', () => {
      it('should handle deployment errors gracefully', async () => {
        const invalidIr = { invalid: 'structure' };

        await expect(runtime.deployProcess(invalidIr as any))
          .rejects.toThrow();
      });

      it('should handle signal errors gracefully', async () => {
        await expect(runtime.signal('non-existent', 'instance', 'signal'))
          .rejects.toThrow('Process non-existent not found');
      });
    });
  });
});
// @vitest-environment node

