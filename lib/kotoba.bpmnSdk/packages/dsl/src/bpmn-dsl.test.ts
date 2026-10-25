import { describe, it, expect } from 'vitest';
import { flow, FlowBuilder, ProcessBuilder } from './bpmn-dsl.js';

describe('@etzhayyim/bpmn-sdk-dsl', () => {
  describe('flow()', () => {
    it('should create a basic process', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p => p);
      });

      expect(result).toBeDefined();
      expect(result.definitions.processes).toHaveLength(1);
      expect(result.definitions.processes[0].id).toBe('TestProcess');
    });

    it('should handle complex process with tasks and gateways', () => {
      const result = flow('ComplexProcess', f => {
        f.process('ComplexProcess', p => {
          p.startEvent('Start');
          p.userTask('Task1');
          p.exclusiveGateway('Gateway1');
          p.serviceTask('Task2');
          p.endEvent('End');
          p.sequenceFlow('Start', 'Task1');
          p.sequenceFlow('Task1', 'Gateway1');
          p.sequenceFlow('Gateway1', 'Task2').condition('${amount > 100}');
          p.sequenceFlow('Task2', 'End');
        });
      });

      expect(result.definitions.processes[0].flowElements).toHaveLength(5);
      expect(result.definitions.processes[0].sequenceFlows).toHaveLength(4);
    });
  });

  describe('flow()', () => {
    it('should create a basic process', () => {
      const result = flow('TestFlow', f => {
        f.process('TestProcess', p => p);
      });

      expect(result).toBeDefined();
      expect(result.definitions.processes).toHaveLength(1);
      expect(result.definitions.processes[0].id).toBe('TestProcess');
    });
  });

  describe('ProcessBuilder', () => {
    it('should add start event', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p => p.startEvent('StartEvent'));
      });

      expect(result.definitions.processes[0].flowElements).toHaveLength(1);
      expect(result.definitions.processes[0].flowElements[0].id).toBe('StartEvent');
    });

    it('should add user task', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p => p.userTask('UserTask'));
      });

      expect(result.definitions.processes[0].flowElements).toHaveLength(1);
      expect(result.definitions.processes[0].flowElements[0].id).toBe('UserTask');
      expect((result.definitions.processes[0].flowElements[0] as any).taskType).toBe('user');
    });

    it('should add service task', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p => p.serviceTask('ServiceTask'));
      });

      expect(result.definitions.processes[0].flowElements).toHaveLength(1);
      expect(result.definitions.processes[0].flowElements[0].id).toBe('ServiceTask');
      expect((result.definitions.processes[0].flowElements[0] as any).taskType).toBe('service');
    });

    it('should add exclusive gateway', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p => p.exclusiveGateway('ExclusiveGateway'));
      });

      expect(result.definitions.processes[0].flowElements).toHaveLength(1);
      expect(result.definitions.processes[0].flowElements[0].id).toBe('ExclusiveGateway');
      expect((result.definitions.processes[0].flowElements[0] as any).gatewayType).toBe('exclusive');
    });

    it('should support method chaining', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p =>
          p.startEvent('StartEvent')
           .userTask('UserTask')
           .endEvent('EndEvent')
        );
      });

      expect(result.definitions.processes[0].flowElements).toHaveLength(3);
      expect(result.definitions.processes[0].flowElements[0].id).toBe('StartEvent');
      expect(result.definitions.processes[0].flowElements[1].id).toBe('UserTask');
      expect(result.definitions.processes[0].flowElements[2].id).toBe('EndEvent');
    });

    it('should add sequence flow', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p => p.sequenceFlow('Source', 'Target'));
      });

      expect(result.definitions.processes[0].sequenceFlows).toHaveLength(1);
      expect(result.definitions.processes[0].sequenceFlows[0].sourceRef).toBe('Source');
      expect(result.definitions.processes[0].sequenceFlows[0].targetRef).toBe('Target');
    });

    it('should add sequence flow with condition', () => {
      const result = flow('TestProcess', f => {
        f.process('TestProcess', p => p.sequenceFlow('Source', 'Target').condition('${amount > 100}'));
      });

      expect(result.definitions.processes[0].sequenceFlows).toHaveLength(1);
      expect((result.definitions.processes[0].sequenceFlows[0] as any).conditionExpression).toBe('${amount > 100}');
    });
  });

  describe('DSL Builders', () => {
    it('should create all event types', () => {
      const builders = [
        'startEvent',
        'endEvent',
        'intermediateCatchEvent',
        'boundaryEvent',
      ] as const;

      builders.forEach(builderName => {
        const result = flow('TestProcess', f => {
          f.process('TestProcess', p => {
            if (builderName === 'boundaryEvent') {
              // boundaryEvent needs attachedToRef parameter
              (p as any)[builderName]('SomeTask', 'TestEvent', 'Test Event');
            } else {
              (p as any)[builderName]('TestEvent', 'Test Event');
            }
          });
        });

        expect(result.definitions.processes[0].flowElements).toHaveLength(1);
        // DSL uses explicit ID when provided
        expect(result.definitions.processes[0].flowElements[0].id).toBe('TestEvent');
      });
    });

    it('should create all task types', () => {
      const taskTypes = [
        { method: 'userTask', type: 'user' },
        { method: 'serviceTask', type: 'service' },
        { method: 'manualTask', type: 'manual' },
        { method: 'scriptTask', type: 'script' },
        { method: 'businessRuleTask', type: 'businessRule' },
        { method: 'sendTask', type: 'send' },
        { method: 'receiveTask', type: 'receive' },
      ];

      taskTypes.forEach(({ method, type }) => {
        const result = flow('TestProcess', f => {
          f.process('TestProcess', p => (p as any)[method]('TestTask', 'Test Task'));
        });

        expect(result.definitions.processes[0].flowElements).toHaveLength(1);
        // DSL uses explicit ID when provided
        expect(result.definitions.processes[0].flowElements[0].id).toBe('TestTask');
        expect((result.definitions.processes[0].flowElements[0] as any).taskType).toBe(type);
      });
    });

    it('should create all gateway types', () => {
      const gatewayTypes = [
        { method: 'exclusiveGateway', type: 'exclusive' },
        { method: 'inclusiveGateway', type: 'inclusive' },
        { method: 'parallelGateway', type: 'parallel' },
        { method: 'eventBasedGateway', type: 'eventBased' },
        { method: 'complexGateway', type: 'complex' },
      ];

      gatewayTypes.forEach(({ method, type }) => {
        const result = flow('TestProcess', f => {
          f.process('TestProcess', p => (p as any)[method]('TestGateway', 'Test Gateway'));
        });

        expect(result.definitions.processes[0].flowElements).toHaveLength(1);
        // DSL uses explicit ID when provided
        expect(result.definitions.processes[0].flowElements[0].id).toBe('TestGateway');
        expect((result.definitions.processes[0].flowElements[0] as any).gatewayType).toBe(type);
      });
    });
  });
});
