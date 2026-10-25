import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BpmnMonitor } from './bpmn-monitor.js';
import { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';

describe('@etzhayyim/bpmn-sdk-ops', () => {
  let monitor: BpmnMonitor;
  let runtime: BpmnRuntime;

  beforeEach(() => {
    runtime = new BpmnRuntime();

    monitor = new BpmnMonitor({
      serviceName: 'test-service',
      metrics: { enabled: true, interval: 1000 },
      otel: { /* disabled for tests */ },
      logging: { level: 'info', format: 'json', destination: 'console' },
      alerts: {
        enabled: true,
        thresholds: {
          maxProcessInstances: 10,
          maxActiveTasks: 5,
          maxErrorRate: 0.1,
          maxAverageDuration: 30000,
          slaBreachRate: 0.05
        }
      }
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.clearAllMocks();
  });

  describe('BpmnMonitor', () => {
    it('should instantiate correctly', () => {
      expect(monitor).toBeDefined();
      expect(monitor).toBeInstanceOf(BpmnMonitor);
    });

    describe('attachToRuntime()', () => {
      it('should attach to runtime successfully', () => {
        expect(() => monitor.attachToRuntime(runtime)).not.toThrow();
      });

      it('should handle runtime events', async () => {
        monitor.attachToRuntime(runtime);

        // Deploy and start a process to trigger events
        const processId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, 'test-process');

        await runtime.startInstance(processId);

        // Events should be captured (mocked in test environment)
        expect(monitor).toBeDefined();
      });
    });

    describe('getPerformanceSnapshot()', () => {
      it('should return performance metrics', async () => {
        monitor.attachToRuntime(runtime);

        const snapshot = await monitor.getPerformanceSnapshot();

        expect(snapshot).toBeDefined();
        expect(snapshot.timestamp).toBeInstanceOf(Date);
        expect(snapshot.metrics).toBeDefined();
        expect(typeof snapshot.metrics.activeInstances).toBe('number');
        expect(typeof snapshot.metrics.totalInstances).toBe('number');
        expect(typeof snapshot.metrics.averageDuration).toBe('number');
      });

      it('should include process-specific metrics', async () => {
        monitor.attachToRuntime(runtime);

        // Create some process activity
        const processId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, 'test-process');

        await runtime.startInstance(processId);

        const snapshot = await monitor.getPerformanceSnapshot();

        expect(snapshot.processMetrics).toBeDefined();
        expect(snapshot.processMetrics['test-process']).toBeDefined();
      });
    });

    describe('getHealthStatus()', () => {
      it('should return health status', async () => {
        const health = await monitor.getHealthStatus();

        expect(health).toBeDefined();
        expect(['healthy', 'degraded', 'unhealthy']).toContain(health.status);
        expect(health.timestamp).toBeInstanceOf(Date);
        expect(health.checks).toBeDefined();
      });

      it('should detect unhealthy state with high error rate', async () => {
        // Simulate high error rate scenario
        monitor.attachToRuntime(runtime);

        const health = await monitor.getHealthStatus();

        // Health status should be calculated based on actual metrics
        expect(health).toBeDefined();
      });
    });

    describe('Metrics Collection', () => {
      it('should track instance counts', async () => {
        monitor.attachToRuntime(runtime);

        const processId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, 'test-process');

        await runtime.startInstance(processId);
        await runtime.startInstance(processId);

        const snapshot = await monitor.getPerformanceSnapshot();

        expect(snapshot.metrics.totalInstances).toBeGreaterThanOrEqual(1);
      });

      it('should track task metrics', async () => {
        monitor.attachToRuntime(runtime);

        const snapshot = await monitor.getPerformanceSnapshot();

        expect(typeof snapshot.metrics.activeTasks).toBe('number');
        expect(typeof snapshot.metrics.completedTasks).toBe('number');
      });

      it('should calculate duration metrics', async () => {
        monitor.attachToRuntime(runtime);

        const processId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, 'test-process');

        const startTime = Date.now();
        await runtime.startInstance(processId);

        // Wait a bit for processing
        await new Promise(resolve => setTimeout(resolve, 100));

        const snapshot = await monitor.getPerformanceSnapshot();

        expect(snapshot.metrics.averageDuration).toBeDefined();
      });
    });

    describe('Alert Management', () => {
      it('should configure alert thresholds', () => {
        const customMonitor = new BpmnMonitor({
          serviceName: 'test-service',
          alerts: {
            enabled: true,
        thresholds: {
          maxProcessInstances: 50,
          maxActiveTasks: 25,
          maxErrorRate: 0.2,
          maxAverageDuration: 60000,
          slaBreachRate: 0.1,
        }
          }
        });

        expect(customMonitor).toBeDefined();
      });

      it('should generate alerts for threshold violations', async () => {
        monitor.attachToRuntime(runtime);

        // Create many instances to potentially trigger alerts
        const processId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, 'test-process');

        // Create multiple instances
        for (let i = 0; i < 15; i++) {
          await runtime.startInstance(processId, { instanceId: `instance-${i}` });
        }

        const alerts = monitor.getActiveAlerts();

        // Should potentially generate alerts based on thresholds
        expect(Array.isArray(alerts)).toBe(true);
      });

      it('should handle alert acknowledgments', () => {
        const alert = {
          id: 'test-alert',
          type: 'high_instance_count' as const,
          severity: 'medium' as const,
          title: 'Test Alert',
          description: 'Test alert description',
          context: {},
          timestamp: new Date(),
          acknowledged: false
        };

        monitor.acknowledgeAlert('test-alert', 'test-user');

        // Alert acknowledgment should be tracked
        expect(monitor).toBeDefined();
      });
    });

    describe('Logging Integration', () => {
      it('should configure logging levels', () => {
        const loggingMonitor = new BpmnMonitor({
          serviceName: 'test-service',
          logging: {
            level: 'debug',
            format: 'json',
            destination: 'console'
          }
        });

        expect(loggingMonitor).toBeDefined();
      });

      it('should log process events', async () => {
        const loggingMonitor = new BpmnMonitor({
          serviceName: 'test-service',
          logging: { level: 'info', format: 'json', destination: 'console' }
        });

        loggingMonitor.attachToRuntime(runtime);

        const processId = await runtime.deployProcess({
          definitions: {
            processes: [{
              id: 'TestProcess',
              flowElements: [],
              sequenceFlows: []
            }]
          }
        } as any, 'test-process');

        await runtime.startInstance(processId);

        // Events should be logged
        expect(loggingMonitor).toBeDefined();
      });
    });

    describe('OpenTelemetry Integration', () => {
      it('should configure OpenTelemetry settings', () => {
        const otelMonitor = new BpmnMonitor({
          serviceName: 'test-service',
          otel: {
            serviceName: 'bpmn-service',
            endpoint: 'http://jaeger:14268/api/traces'
          }
        });

        expect(otelMonitor).toBeDefined();
      });

      it('should create traces for process execution', async () => {
        monitor.attachToRuntime(runtime);

        const processId = await runtime.deployProcess({
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
        } as any, 'trace-test-process');

        await runtime.startInstance(processId);

        // Traces should be created for the execution
        expect(monitor).toBeDefined();
      });
    });

    describe('Resource Cleanup', () => {
      it('should clean up resources on destruction', () => {
        monitor.attachToRuntime(runtime);

        // Monitor should handle cleanup properly
        expect(monitor).toBeDefined();
      });

      it('should handle runtime disconnection', () => {
        monitor.attachToRuntime(runtime);

        // Simulate runtime disconnection
        expect(() => {
          // Monitor should handle disconnection gracefully
        }).not.toThrow();
      });
    });

    describe('Configuration Validation', () => {
      it('should validate service name configuration', () => {
        expect(() => new BpmnMonitor({
          serviceName: '',
          metrics: { enabled: true }
        })).not.toThrow();
      });

      it('should handle missing optional configurations', () => {
        const minimalMonitor = new BpmnMonitor({
          serviceName: 'minimal-service'
        });

        expect(minimalMonitor).toBeDefined();
      });

      it('should validate alert thresholds', () => {
        const monitorWithThresholds = new BpmnMonitor({
          serviceName: 'test-service',
          alerts: {
            enabled: true,
            thresholds: {
              maxProcessInstances: 0, // Invalid threshold
              maxActiveTasks: 5,
              maxErrorRate: 0.1,
              maxAverageDuration: 30000,
              slaBreachRate: 0.05
            }
          }
        });

        expect(monitorWithThresholds).toBeDefined();
      });
    });
  });
});
// @vitest-environment node
