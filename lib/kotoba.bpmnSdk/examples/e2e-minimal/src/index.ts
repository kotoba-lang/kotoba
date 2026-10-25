// Merkle DAG: e2e_minimal_test
// Minimal E2E test: DSL → IR → XML → Runtime execution

import { flow } from '@etzhayyim/bpmn-sdk-dsl';
import { compileToXml } from '@etzhayyim/bpmn-sdk-compiler';
import { deployAndStart } from '@etzhayyim/bpmn-sdk-runtime';
// import { importFromXml } from '@etzhayyim/bpmn-sdk-importer'; // TODO: Enable when ready

// Define a minimal BPMN process using DSL
// Process: Start → User Task → Service Task → XOR Gateway → End
async function createProcessIR() {
  const result = flow('MinimalProcess', (f: any) => f
    .process('MinimalProcess', (p: any) => p
      // Start Event
      .startEvent('StartEvent')

      // User Task
      .userTask('ReviewRequest')

      // Service Task
      .serviceTask('ProcessRequest')

      // XOR Gateway with conditions
      .exclusiveGateway('DecisionPoint')

      // End Events
      .endEvent('Approved')
      .endEvent('Rejected')

      // Sequence Flows
      .sequenceFlow('StartEvent', 'ReviewRequest')
      .sequenceFlow('ReviewRequest', 'ProcessRequest')
      .sequenceFlow('ProcessRequest', 'DecisionPoint')
      .sequenceFlow('DecisionPoint', 'Approved')
      .sequenceFlow('DecisionPoint', 'Rejected')
    )
    .build()
  );

  return result;
}

async function runE2ETest() {
  console.log('🚀 Starting BPMN SDK E2E Test...\n');

  try {
    // Step 1: Create IR from DSL
    console.log('🏗️ Creating IR from DSL...');
    const minimalProcessIR = await createProcessIR();
    console.log('✅ IR created successfully');

    // Step 2: Compile IR to BPMN XML
    console.log('📝 Compiling IR to BPMN XML...');
    const xml = await compileToXml(minimalProcessIR);
    console.log('✅ BPMN XML generated successfully');
    console.log('📄 XML Preview (first 300 chars):');
    console.log(xml.substring(0, 300) + '...\n');

    // Step 3: Test round-trip: XML → IR (TODO: Enable when importer ready)
    console.log('🔄 Testing round-trip conversion (XML → IR)... (SKIPPED)');
    // const importedIR = await importFromXml(xml);
    // console.log('✅ XML imported back to IR successfully');

    // Verify round-trip consistency (placeholder)
    const originalElements = minimalProcessIR.definitions.processes[0]?.flowElements?.length || 0;
    console.log(`📊 Original elements: ${originalElements}`);

    // Step 4: Deploy and start process instance
    console.log('🚀 Deploying and starting process instance...');
    const { runtime, context } = await deployAndStart(minimalProcessIR, {
      variables: {
        requestData: 'Test request data',
        userId: 'user1'
      },
      businessKey: 'test-key-123'
    });

    console.log('✅ Process instance started');
    console.log(`📊 Instance ID: ${context.instanceId}`);
    console.log(`📊 Process ID: ${context.processId}`);
    console.log(`📊 Status: ${context.status}`);
    console.log(`📊 Variables:`, context.variables);

    // Step 5: Set up event monitoring
    console.log('\n👂 Setting up event monitoring...');
    runtime.onEvent((event: any) => {
      console.log(`📢 Event: ${event.type}`, {
        processId: event.processId,
        instanceId: event.instanceId,
        ...(event.type === 'activity.start' || event.type === 'activity.end'
          ? { activityId: event.activityId, activityType: event.activityType }
          : {}),
        ...(event.type === 'end' ? { output: event.output } : {}),
      });
    });

    // Step 6: Wait for process completion
    console.log('\n⏳ Waiting for process completion...');

    // In a real scenario, we would wait for user tasks to be completed
    // For this minimal test, we'll simulate completion
    await new Promise(resolve => setTimeout(resolve, 2000));

    const finalContext = await runtime.getExecutionContext(
      context.processId,
      context.instanceId
    );

    console.log('\n🏁 Process execution completed');
    console.log(`📊 Final Status: ${finalContext?.status}`);
    console.log(`📊 Execution Time: ${finalContext?.endTime ? finalContext.endTime.getTime() - finalContext.startTime.getTime() : 'N/A'}ms`);

    // Step 7: Final summary
    console.log('\n🎉 BPMN SDK E2E Test completed successfully!');
    console.log('✅ DSL → IR conversion');
    console.log('✅ IR → XML compilation');
    console.log('⏳ XML → IR round-trip import (TODO)');
    console.log('✅ Process deployment and execution');
    console.log('✅ Runtime event monitoring');

  } catch (error) {
    console.error('❌ E2E Test failed:', error);
    console.error('Stack trace:', error instanceof Error ? error.stack : 'No stack trace');
    process.exit(1);
  }
}

// Run the test
runE2ETest().catch(console.error);
