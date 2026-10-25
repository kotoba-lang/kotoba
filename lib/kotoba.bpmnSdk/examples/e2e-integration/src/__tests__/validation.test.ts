// Static Validation Integration Tests

import { validateProcess } from '@etzhayyim/bpmn-sdk-validation';
import { flow } from '@etzhayyim/bpmn-sdk-dsl';

describe.skip('Static Validation Integration', () => {
  test('should validate correct process', async () => {
    const validProcess = flow('ValidProcess', f => f
      .process('ValidProcess', p => p
        .startEvent('StartEvent')
        .userTask('UserTask1')
        .endEvent('EndEvent')
        .sequenceFlow('StartEvent', 'UserTask1')
        .sequenceFlow('UserTask1', 'EndEvent')
      )
    ).process

    const result = await validateProcess(validProcess);

    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
    expect(result.warnings).toHaveLength(0);
    expect(result.statistics.totalElements).toBeGreaterThan(0);
  });

  test('should detect unreachable elements', async () => {
    const processWithUnreachable = flow('ProcessWithUnreachable', f => f
      .process('ProcessWithUnreachable', p => p
        .startEvent('StartEvent')
        .userTask('ReachableTask')
        .userTask('UnreachableTask') // Not connected
        .endEvent('EndEvent')
        .sequenceFlow('StartEvent', 'ReachableTask')
        .sequenceFlow('ReachableTask', 'EndEvent')
        // UnreachableTask is not connected
      )
    ).process

    const result = await validateProcess(processWithUnreachable);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.type === 'unreachable_element')).toBe(true);
    expect(result.statistics.unreachableElements).toBeGreaterThan(0);
  });

  test('should detect dead ends', async () => {
    const processWithDeadEnd = flow('ProcessWithDeadEnd', f => f
      .process('ProcessWithDeadEnd', p => p
        .startEvent('StartEvent')
        .userTask('TaskWithNoOutgoing')
        // No sequence flow from TaskWithNoOutgoing to EndEvent
        .endEvent('EndEvent')
        .sequenceFlow('StartEvent', 'TaskWithNoOutgoing')
      )
    );

    const result = await validateProcess(processWithDeadEnd);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.type === 'dead_end')).toBe(true);
  });

  test('should validate gateway consistency', async () => {
    const processWithGateway = flow('ProcessWithGateway', f => f
      .process('ProcessWithGateway', p => p
        .startEvent('StartEvent')
        .exclusiveGateway('XORGateway')
        .userTask('Task1')
        .userTask('Task2')
        .exclusiveGateway('JoinGateway')
        .endEvent('EndEvent')

        .sequenceFlow('StartEvent', 'XORGateway')
        .sequenceFlow('XORGateway', 'Task1')
          .condition('${amount < 1000}')
        .sequenceFlow('XORGateway', 'Task2')
          .condition('${amount >= 1000}')
        .sequenceFlow('Task1', 'JoinGateway')
        .sequenceFlow('Task2', 'JoinGateway')
        .sequenceFlow('JoinGateway', 'EndEvent')
      )
    );

    const result = await validateProcess(processWithGateway);

    expect(result.valid).toBe(true);
    expect(result.errors.filter(e => e.type.includes('gateway'))).toHaveLength(0);
  });

  test('should detect missing start event', async () => {
    const processWithoutStart = flow('ProcessWithoutStart', f => f
      .process('ProcessWithoutStart', p => p
        // No start event
        .userTask('UserTask1')
        .endEvent('EndEvent')
        .sequenceFlow('UserTask1', 'EndEvent')
      )
    );

    const result = await validateProcess(processWithoutStart);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.type === 'start_event_multiple')).toBe(true);
  });

  test('should detect missing end event', async () => {
    const processWithoutEnd = flow('ProcessWithoutEnd', f => f
      .process('ProcessWithoutEnd', p => p
        .startEvent('StartEvent')
        .userTask('UserTask1')
        // No end event
        .sequenceFlow('StartEvent', 'UserTask1')
      )
    );

    const result = await validateProcess(processWithoutEnd);

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.type === 'end_event_missing')).toBe(true);
  });

  test('should validate complex process', async () => {
    const complexProcess = flow('ComplexProcess', f => f
      .process('ComplexProcess', p => p
        // Events
        .startEvent('StartEvent')
        .intermediateCatchEvent('TimerEvent')
        .boundaryEvent('ErrorBoundary')
        .endEvent('EndEvent')

        // Tasks
        .userTask('ReviewTask')
        .serviceTask('ProcessTask')
        .scriptTask('ScriptTask')

        // Gateways
        .exclusiveGateway('DecisionPoint')
        .parallelGateway('ParallelSplit')
        .parallelGateway('ParallelJoin')

        // Subprocess
        .embeddedSubprocess('SubProcess')

        // Flows
        .sequenceFlow('StartEvent', 'ReviewTask')
        .sequenceFlow('ReviewTask', 'DecisionPoint')
        .sequenceFlow('DecisionPoint', 'ProcessTask')
          .condition('${approved}')
        .sequenceFlow('DecisionPoint', 'ScriptTask')
          .condition('${!approved}')
        .sequenceFlow('ProcessTask', 'ParallelSplit')
        .sequenceFlow('ScriptTask', 'ParallelSplit')
        .sequenceFlow('ParallelSplit', 'TimerEvent')
        .sequenceFlow('ParallelSplit', 'SubProcess')
        .sequenceFlow('TimerEvent', 'ParallelJoin')
        .sequenceFlow('SubProcess', 'ParallelJoin')
        .sequenceFlow('ParallelJoin', 'EndEvent')
      )
    );

    const result = await validateProcess(complexProcess);

    // Complex processes may have warnings but should not have critical errors
    expect(result.errors.filter(e => e.severity === 'error')).toHaveLength(0);
    expect(result.statistics.complexityScore).toBeGreaterThan(0);
  });
});
