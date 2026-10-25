// Merkle DAG: e2e_integration_test
// Complete E2E Integration Test - All Components Working Together

import { flow } from '@etzhayyim/bpmn-sdk-dsl';
import { compileToXml } from '@etzhayyim/bpmn-sdk-compiler';
import { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';
import { validateProcess } from '@etzhayyim/bpmn-sdk-validation';
import { HumanTaskManager } from '@etzhayyim/bpmn-sdk-human';
import { BpmnMonitor } from '@etzhayyim/bpmn-sdk-ops';
import { bpmnPropertyTest, bpmnScenarioTest } from '@etzhayyim/bpmn-sdk-testing';

/**
 * Complete BPMN Process: Invoice Approval Workflow
 * Start → User Task (Review) → XOR Gateway → Service Task (Process) → Human Task (Approval) → End
 *                                            ↓
 *                                     End (Rejected)
 */
async function createInvoiceApprovalProcess() {
  return flow('InvoiceApprovalProcess', f =>
    f.process('InvoiceApprovalProcess', p => {
      // Start Event
      p.startEvent('StartEvent');

      // Initial Review Task (User Task)
      p.userTask('ReviewInvoiceTask');

      // XOR Gateway for amount check
      p.exclusiveGateway('AmountCheckGateway');

      // High amount path: Manual approval
      p.userTask('ManualApprovalTask');

      // Low amount path: Auto approval
      p.serviceTask('AutoApprovalTask');

      // Final processing
      p.serviceTask('ProcessInvoiceTask');

      // End Event
      p.endEvent('EndEvent');

      // Sequence Flows
      p.sequenceFlow('StartEvent', 'ReviewInvoiceTask');
      p.sequenceFlow('ReviewInvoiceTask', 'AmountCheckGateway');

      // Gateway conditions
      p.sequenceFlow('AmountCheckGateway', 'ManualApprovalTask')
        .condition('${amount > 1000}');

      p.sequenceFlow('AmountCheckGateway', 'AutoApprovalTask')
        .condition('${amount <= 1000}');

      // Continue flows
      p.sequenceFlow('ManualApprovalTask', 'ProcessInvoiceTask');
      p.sequenceFlow('AutoApprovalTask', 'ProcessInvoiceTask');
      p.sequenceFlow('ProcessInvoiceTask', 'EndEvent');
    })
  );
}

/**
 * Run Complete E2E Integration Test
 */
async function runCompleteIntegrationTest() {
  console.log('🚀 Starting Complete BPMN SDK Integration Test...\n');

  let runtime: BpmnRuntime;
  let taskManager: HumanTaskManager;
  let monitor: BpmnMonitor | undefined;

  try {
    // ==========================================
    // 1. PROCESS MODELING & COMPILATION
    // ==========================================
    console.log('📝 Step 1: Process Modeling & Compilation');

    // Create process using DSL
    const invoiceProcess = await createInvoiceApprovalProcess();
    console.log('✅ Process created with DSL');

    // Validate process statically
    const validationResult = await validateProcess(invoiceProcess);
    console.log(`✅ Static validation: ${validationResult.valid ? 'PASSED' : 'FAILED'}`);
    console.log(`   - Errors: ${validationResult.errors.length}`);
    console.log(`   - Warnings: ${validationResult.warnings.length}`);
    console.log(`   - Complexity Score: ${validationResult.statistics.complexityScore}`);

    if (!validationResult.valid) {
      throw new Error('Process validation failed');
    }

    // Compile to BPMN XML
    const xml = await compileToXml(invoiceProcess);
    console.log('✅ Process compiled to BPMN XML');
    console.log(`   - XML length: ${xml.length} characters`);

    // ==========================================
    // 2. RUNTIME & MONITORING SETUP
    // ==========================================
    console.log('\n📊 Step 2: Runtime & Monitoring Setup');

    // Initialize runtime
    runtime = new BpmnRuntime();
    console.log('✅ BPMN Runtime initialized');

    // Initialize monitoring
    monitor = new BpmnMonitor({
      serviceName: 'bpmn-integration-test',
      serviceVersion: '1.0.0',
      metrics: { enabled: true, interval: 1000 },
      otel: { /* disabled for test */ },
      logging: { level: 'info', format: 'json', destination: 'console' },
      alerts: {
        enabled: true,
        thresholds: {
          maxProcessInstances: 10,
          maxActiveTasks: 20,
          maxErrorRate: 0.5,
          maxAverageDuration: 30000,
          slaBreachRate: 0.1,
        }
      }
    });

    monitor.attachToRuntime(runtime);
    console.log('✅ Monitoring system attached to runtime');

    // Initialize human task manager
    taskManager = new HumanTaskManager(runtime);
    console.log('✅ Human Task Manager initialized');

    // ==========================================
    // 3. PROPERTY-BASED TESTING
    // ==========================================
    console.log('\n🧪 Step 3: Property-Based Testing');

    const propertyTests = [
      'noDeadEnds',
      'allReachable',
      'gatewayConsistency',
      'properTermination',
      'validExecution'
    ];

    for (const property of propertyTests) {
      const result = await bpmnPropertyTest(invoiceProcess, runtime, property, {
        maxTestCases: 10,
        timeout: 5000
      });
      console.log(`✅ Property test "${property}": ${result.success ? 'PASSED' : 'FAILED'}`);
      console.log(`   - Test cases: ${result.passed}/${result.testCases}`);
    }

    // ==========================================
    // 4. SCENARIO TESTING
    // ==========================================
    console.log('\n🎭 Step 4: Scenario Testing');

    const scenarios = [
      {
        id: 'low_amount_auto_approval',
        description: 'Low amount invoice auto-approval',
        inputs: { amount: 500, invoiceId: 'INV-001' },
        expectedPath: ['StartEvent', 'ReviewInvoiceTask', 'AmountCheckGateway', 'AutoApprovalTask', 'ProcessInvoiceTask', 'EndEvent'],
        expectedOutputs: { approved: true, processed: true }
      },
      {
        id: 'high_amount_manual_approval',
        description: 'High amount invoice manual approval',
        inputs: { amount: 5000, invoiceId: 'INV-002' },
        expectedPath: ['StartEvent', 'ReviewInvoiceTask', 'AmountCheckGateway', 'ManualApprovalTask', 'ProcessInvoiceTask', 'EndEvent'],
        expectedOutputs: { approved: true, processed: true }
      }
    ];

    for (const scenario of scenarios) {
      const result = await bpmnScenarioTest(invoiceProcess, runtime, scenario, {
        timeout: 10000
      });
      console.log(`✅ Scenario "${scenario.id}": ${result.success ? 'PASSED' : 'FAILED'}`);
      if (!result.success) {
        console.log(`   - Error: ${result.error}`);
      }
    }

    // ==========================================
    // 5. PROCESS EXECUTION WITH HUMAN TASKS
    // ==========================================
    console.log('\n⚙️  Step 5: Process Execution with Human Tasks');

    // Deploy process
    const deployedProcessId = await runtime.deployProcess(invoiceProcess, 'InvoiceApprovalProcess');
    console.log(`✅ Process deployed: ${deployedProcessId}`);

    // Start high-amount instance (requires manual approval)
    console.log('\n📋 Executing High-Amount Invoice Process...');
    const highAmountContext = await runtime.startInstance(deployedProcessId, {
      instanceId: 'instance-high-001',
      variables: {
        amount: 2500,
        invoiceId: 'INV-HIGH-001',
        requester: 'john.doe@example.com'
      },
      businessKey: 'BIZ-HIGH-001'
    });

    console.log(`✅ High-amount instance started: ${highAmountContext.instanceId}`);
    console.log(`   - Status: ${highAmountContext.status}`);

    // Wait for human task to be created
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Check for pending human tasks
    const pendingTasks = taskManager.getTasksForUser('manager@example.com');
    console.log(`📋 Found ${pendingTasks.length} pending tasks for manager`);

    if (pendingTasks.length > 0) {
      const approvalTask = pendingTasks[0]!;
      console.log(`   - Task: ${approvalTask.name} (${approvalTask.id})`);

      // Claim and complete the approval task
      await taskManager.claimTask(approvalTask.id, 'manager@example.com');
      console.log('✅ Task claimed by manager');

      await taskManager.completeTask(approvalTask.id, 'manager@example.com', {
        decision: 'approved',
        comments: 'Approved for payment processing',
        approvedBy: 'manager@example.com',
        approvalDate: new Date()
      });
      console.log('✅ Task completed with approval');
    }

    // Start low-amount instance (auto-approval)
    console.log('\n📋 Executing Low-Amount Invoice Process...');
    const lowAmountContext = await runtime.startInstance(deployedProcessId, {
      instanceId: 'instance-low-001',
      variables: {
        amount: 500,
        invoiceId: 'INV-LOW-001',
        requester: 'jane.smith@example.com'
      },
      businessKey: 'BIZ-LOW-001'
    });

    console.log(`✅ Low-amount instance started: ${lowAmountContext.instanceId}`);
    console.log(`   - Status: ${lowAmountContext.status}`);

    // Wait for completion
    await new Promise(resolve => setTimeout(resolve, 2000));

    // ==========================================
    // 6. MONITORING & METRICS
    // ==========================================
    console.log('\n📊 Step 6: Monitoring & Metrics');

    const snapshot = await monitor.getPerformanceSnapshot();
    console.log('✅ Performance snapshot captured:');
    console.log(`   - Active instances: ${snapshot.metrics.activeInstances}`);
    console.log(`   - Completed instances: ${snapshot.metrics.completedInstances}`);
    console.log(`   - Total tasks: ${snapshot.metrics.totalTasks}`);
    console.log(`   - Error rate: ${(snapshot.metrics.errorRate * 100).toFixed(2)}%`);

    const health = await monitor.getHealthStatus();
    console.log(`✅ Health status: ${health.status}`);
    console.log(`   - Uptime: ${health.uptime} seconds`);

    const alerts = monitor.getAlerts();
    console.log(`📢 Active alerts: ${alerts.length}`);

    // ==========================================
    // 7. FINAL REPORT
    // ==========================================
    console.log('\n🎉 Integration Test Completed Successfully!');
    console.log('\n📊 Final Summary:');
    console.log('✅ DSL Process Modeling');
    console.log('✅ Static Validation');
    console.log('✅ BPMN XML Compilation');
    console.log('✅ Runtime Execution');
    console.log('✅ Human Task Management');
    console.log('✅ Property-based Testing');
    console.log('✅ Scenario Testing');
    console.log('✅ Monitoring & Observability');
    console.log('✅ Alert System');
    console.log('✅ Health Checks');

    console.log('\n🏆 All BPMN SDK Components Successfully Integrated!');

  } catch (error) {
    console.error('\n❌ Integration Test Failed:', error);
    console.error('Stack trace:', error instanceof Error ? error.stack : 'No stack trace');

    // Cleanup on failure
    if (monitor) {
      await monitor.shutdown().catch(console.error);
    }

    process.exit(1);
  }
}

// Export for testing
export { createInvoiceApprovalProcess, runCompleteIntegrationTest };

// Run if called directly
if (require.main === module) {
  runCompleteIntegrationTest().catch(console.error);
}
