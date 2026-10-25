// Monitoring & Observability Integration Tests

import { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';
import { BpmnMonitor } from '@etzhayyim/bpmn-sdk-ops';
import { flow } from '@etzhayyim/bpmn-sdk-dsl';

describe.skip('Monitoring Integration', () => {
  let runtime: BpmnRuntime;
  let monitor: BpmnMonitor;
  let testProcess: any;

  beforeEach(async () => {
    runtime = new BpmnRuntime();

    monitor = new BpmnMonitor({
      serviceName: 'test-monitor',
      metrics: { enabled: true, interval: 100 },
      otel: { /* disabled for test */ },
      logging: { level: 'info', format: 'json', destination: 'console' },
      alerts: {
        enabled: true,
        thresholds: {
          maxProcessInstances: 5,
          maxErrorRate: 0.8,
          maxAverageDuration: 10000,
          slaBreachRate: 0.5,
        }
      }
    });

    monitor.attachToRuntime(runtime);

    testProcess = flow('TestProcess', f => {
      f.process('TestProcess', p => {
        p.startEvent('StartEvent');
        p.userTask('UserTask1');
        p.endEvent('EndEvent');
        p.sequenceFlow('StartEvent', 'UserTask1');
        p.sequenceFlow('UserTask1', 'EndEvent');
      });
    });
  });

  afterEach(async () => {
    await monitor.shutdown();
  });

  test('should collect process metrics', async () => {
    const processId = await runtime.deployProcess(testProcess);

    // Start multiple instances
    for (let i = 0; i < 3; i++) {
      await runtime.startInstance(processId, {
        instanceId: `test-instance-${i}`,
        variables: { testId: i }
      });
    }

    // Wait for metrics collection
    await new Promise(resolve => setTimeout(resolve, 200));

    const snapshot = await monitor.getPerformanceSnapshot();

    expect(snapshot.metrics.totalInstances).toBe(3);
    expect(snapshot.metrics.activeInstances).toBe(3);
    expect(snapshot.timestamp).toBeInstanceOf(Date);
  });

  test('should perform health checks', async () => {
    const health = await monitor.getHealthStatus();

    expect(health.status).toBe('healthy');
    expect(health.timestamp).toBeInstanceOf(Date);
    expect(health.uptime).toBeGreaterThan(0);
    expect(health.checks).toBeDefined();
    expect(health.checks.length).toBeGreaterThan(0);
  });

  test('should handle alerts', async () => {
    const processId = await runtime.deployProcess(testProcess);

    // Create many instances to trigger alert
    for (let i = 0; i < 7; i++) { // More than threshold of 5
      await runtime.startInstance(processId, {
        instanceId: `test-instance-${i}`,
        variables: { testId: i }
      });
    }

    // Wait for alert processing
    await new Promise(resolve => setTimeout(resolve, 500));

    const alerts = monitor.getAlerts();
    const highInstanceAlerts = alerts.filter(a => a.type === 'high_instance_count');

    expect(highInstanceAlerts.length).toBeGreaterThan(0);

    // Acknowledge alert
    if (highInstanceAlerts.length > 0) {
      monitor.acknowledgeAlert(highInstanceAlerts[0].id, 'test-user');

      const updatedAlerts = monitor.getAlerts({ acknowledged: false });
      expect(updatedAlerts.some(a => a.id === highInstanceAlerts[0].id)).toBe(false);
    }
  });

  test('should collect memory and performance metrics', async () => {
    const snapshot = await monitor.getPerformanceSnapshot();

    expect(snapshot.memoryUsage).toBeDefined();
    expect(snapshot.cpuUsage).toBeGreaterThanOrEqual(0);
    expect(snapshot.eventLoopDelay).toBeGreaterThanOrEqual(0);
    expect(snapshot.activeTraces).toBeGreaterThanOrEqual(0);
  });

  test('should filter alerts by criteria', async () => {
    // Create some alerts by triggering conditions
    const processId = await runtime.deployProcess(testProcess);

    for (let i = 0; i < 10; i++) {
      await runtime.startInstance(processId, {
        instanceId: `alert-test-${i}`,
        variables: { testId: i }
      });
    }

    await new Promise(resolve => setTimeout(resolve, 500));

    const allAlerts = monitor.getAlerts();
    const criticalAlerts = monitor.getAlerts({ severity: 'critical' });
    const acknowledgedAlerts = monitor.getAlerts({ acknowledged: true });

    expect(allAlerts.length).toBeGreaterThanOrEqual(criticalAlerts.length);
    expect(allAlerts.length).toBeGreaterThanOrEqual(acknowledgedAlerts.length);
  });
});
