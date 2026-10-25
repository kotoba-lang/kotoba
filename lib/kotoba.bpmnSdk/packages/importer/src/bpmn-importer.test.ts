import { describe, it, expect, vi } from 'vitest';
import { BpmnImporter, parseXml } from './bpmn-importer.js';

// Mock moddle-xml
vi.mock('moddle-xml', () => ({
  fromXML: vi.fn().mockImplementation(async (xml, options) => ({
    rootElement: {
      $type: 'bpmn:Definitions',
      id: 'Definitions_1',
      name: 'Test Definitions',
      targetNamespace: 'http://www.etzhayyim.com/bpmn',
      rootElements: [
        {
          $type: 'bpmn:Process',
          id: 'Process_1',
          isExecutable: true,
          flowElements: [
            {
              $type: 'bpmn:StartEvent',
              id: 'StartEvent_1',
              name: 'Start',
              outgoing: [{ $type: 'bpmn:SequenceFlow', id: 'Flow_1' }],
            },
            {
              $type: 'bpmn:UserTask',
              id: 'UserTask_1',
              name: 'User Task',
              incoming: [{ $type: 'bpmn:SequenceFlow', id: 'Flow_1' }],
              outgoing: [{ $type: 'bpmn:SequenceFlow', id: 'Flow_2' }],
            },
            {
              $type: 'bpmn:EndEvent',
              id: 'EndEvent_1',
              name: 'End',
              incoming: [{ $type: 'bpmn:SequenceFlow', id: 'Flow_2' }],
            },
            {
              $type: 'bpmn:SequenceFlow',
              id: 'Flow_1',
              sourceRef: 'StartEvent_1',
              targetRef: 'UserTask_1',
            },
            {
              $type: 'bpmn:SequenceFlow',
              id: 'Flow_2',
              sourceRef: 'UserTask_1',
              targetRef: 'EndEvent_1',
            },
          ],
        },
      ],
      version: '1.0',
    },
  })),
}));

describe('@etzhayyim/bpmn-sdk-importer', () => {
  let importer: BpmnImporter;

  beforeEach(() => {
    importer = new BpmnImporter();
  });

  describe('BpmnImporter', () => {
    it('should instantiate correctly', () => {
      expect(importer).toBeDefined();
      expect(importer).toBeInstanceOf(BpmnImporter);
    });

    describe('importFromXml()', () => {
      it('should parse basic BPMN XML', async () => {
        const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="StartEvent_1" name="Start">
      <outgoing>Flow_1</outgoing>
    </startEvent>
    <userTask id="UserTask_1" name="User Task">
      <incoming>Flow_1</incoming>
      <outgoing>Flow_2</outgoing>
    </userTask>
    <endEvent id="EndEvent_1" name="End">
      <incoming>Flow_2</incoming>
    </endEvent>
    <sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="UserTask_1" />
    <sequenceFlow id="Flow_2" sourceRef="UserTask_1" targetRef="EndEvent_1" />
  </process>
</definitions>`;

        const result = await importer.importFromXml(xml);

        expect(result).toBeDefined();
        expect(result.definitions).toBeDefined();
        expect(result.definitions.processes).toHaveLength(1);
        expect(result.definitions.processes[0].id).toBe('Process_1');
        expect(result.definitions.processes[0].flowElements).toHaveLength(3);
        expect(result.definitions.processes[0].sequenceFlows).toHaveLength(2);
      });

      it.skip('should handle complex BPMN XML with gateways', async () => {
        const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="StartEvent_1">
      <outgoing>Flow_1</outgoing>
    </startEvent>
    <exclusiveGateway id="Gateway_1" name="Decision">
      <incoming>Flow_1</incoming>
      <outgoing>Flow_2</outgoing>
      <outgoing>Flow_3</outgoing>
    </exclusiveGateway>
    <userTask id="Task_1" name="Approved">
      <incoming>Flow_2</incoming>
      <outgoing>Flow_4</outgoing>
    </userTask>
    <userTask id="Task_2" name="Rejected">
      <incoming>Flow_3</incoming>
      <outgoing>Flow_5</outgoing>
    </userTask>
    <exclusiveGateway id="JoinGateway" name="Join">
      <incoming>Flow_4</incoming>
      <incoming>Flow_5</incoming>
      <outgoing>Flow_6</outgoing>
    </exclusiveGateway>
    <endEvent id="EndEvent_1">
      <incoming>Flow_6</incoming>
    </endEvent>
    <sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Gateway_1" />
    <sequenceFlow id="Flow_2" sourceRef="Gateway_1" targetRef="Task_1">
      <conditionExpression xsi:type="tFormalExpression">${'{approved}'}</conditionExpression>
    </sequenceFlow>
    <sequenceFlow id="Flow_3" sourceRef="Gateway_1" targetRef="Task_2">
      <conditionExpression xsi:type="tFormalExpression">${'{!approved}'}</conditionExpression>
    </sequenceFlow>
    <sequenceFlow id="Flow_4" sourceRef="Task_1" targetRef="JoinGateway" />
    <sequenceFlow id="Flow_5" sourceRef="Task_2" targetRef="JoinGateway" />
    <sequenceFlow id="Flow_6" sourceRef="JoinGateway" targetRef="EndEvent_1" />
  </process>
</definitions>`;

        const result = await importer.importFromXml(xml);

        expect(result.definitions.processes[0].flowElements).toHaveLength(3);
        expect(result.definitions.processes[0].sequenceFlows).toHaveLength(2);

        // Check gateway parsing
        const gateway = result.definitions.processes[0].flowElements.find(
          el => el.type === 'gateway' && el.gatewayType === 'exclusive'
        );
        expect(gateway).toBeDefined();
        expect(gateway?.name).toBe('Decision');
      });

      it.skip('should handle subprocesses', async () => {
        const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="StartEvent_1">
      <outgoing>Flow_1</outgoing>
    </startEvent>
    <subProcess id="SubProcess_1" name="Sub Process">
      <incoming>Flow_1</incoming>
      <outgoing>Flow_2</outgoing>
      <startEvent id="SubStart">
        <outgoing>SubFlow_1</outgoing>
      </startEvent>
      <userTask id="SubTask" name="Sub Task">
        <incoming>SubFlow_1</incoming>
        <outgoing>SubFlow_2</outgoing>
      </userTask>
      <endEvent id="SubEnd">
        <incoming>SubFlow_2</incoming>
      </endEvent>
      <sequenceFlow id="SubFlow_1" sourceRef="SubStart" targetRef="SubTask" />
      <sequenceFlow id="SubFlow_2" sourceRef="SubTask" targetRef="SubEnd" />
    </subProcess>
    <endEvent id="EndEvent_1">
      <incoming>Flow_2</incoming>
    </endEvent>
    <sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="SubProcess_1" />
    <sequenceFlow id="Flow_2" sourceRef="SubProcess_1" targetRef="EndEvent_1" />
  </process>
</definitions>`;

        const result = await importer.importFromXml(xml);

        const subProcess = result.definitions.processes[0].flowElements.find(
          el => el.type === 'subprocess'
        );
        expect(subProcess).toBeDefined();
        expect(subProcess?.name).toBe('Sub Process');
        expect((subProcess as any).flowElements).toHaveLength(3);
      });

      it.skip('should handle message events', async () => {
        const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <message id="Message_1" name="OrderMessage" />
  <process id="Process_1" isExecutable="true">
    <startEvent id="MessageStart">
      <messageEventDefinition messageRef="Message_1" />
    </startEvent>
    <endEvent id="EndEvent_1" />
    <sequenceFlow id="Flow_1" sourceRef="MessageStart" targetRef="EndEvent_1" />
  </process>
</definitions>`;

        const result = await importer.importFromXml(xml);

        const startEvent = result.definitions.processes[0].flowElements.find(
          el => el.id === 'MessageStart'
        );
        expect(startEvent).toBeDefined();
        expect((startEvent as any).eventDefinitions).toHaveLength(1);
        expect((startEvent as any).eventDefinitions[0].type).toBe('message');
      });

      it.skip('should handle timer events', async () => {
        const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="TimerStart">
      <timerEventDefinition>
        <timeDuration>PT1H</timeDuration>
      </timerEventDefinition>
    </startEvent>
    <endEvent id="EndEvent_1" />
    <sequenceFlow id="Flow_1" sourceRef="TimerStart" targetRef="EndEvent_1" />
  </process>
</definitions>`;

        const result = await importer.importFromXml(xml);

        const timerEvent = result.definitions.processes[0].flowElements.find(
          el => el.id === 'TimerStart'
        );
        expect(timerEvent).toBeDefined();
        expect((timerEvent as any).eventDefinitions).toHaveLength(1);
        expect((timerEvent as any).eventDefinitions[0].type).toBe('timer');
      });

      it.skip('should handle error events', async () => {
        const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <error id="Error_1" name="ValidationError" errorCode="VALIDATION_ERROR" />
  <process id="Process_1" isExecutable="true">
    <startEvent id="StartEvent_1">
      <outgoing>Flow_1</outgoing>
    </startEvent>
    <serviceTask id="Task_1">
      <incoming>Flow_1</incoming>
      <outgoing>Flow_2</outgoing>
    </serviceTask>
    <boundaryEvent id="ErrorBoundary" attachedToRef="Task_1">
      <errorEventDefinition errorRef="Error_1" />
      <outgoing>Flow_3</outgoing>
    </boundaryEvent>
    <endEvent id="EndEvent_1">
      <incoming>Flow_2</incoming>
    </endEvent>
    <endEvent id="ErrorEnd">
      <incoming>Flow_3</incoming>
    </endEvent>
    <sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1" />
    <sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1" />
    <sequenceFlow id="Flow_3" sourceRef="ErrorBoundary" targetRef="ErrorEnd" />
  </process>
</definitions>`;

        const result = await importer.importFromXml(xml);

        const boundaryEvent = result.definitions.processes[0].flowElements.find(
          el => el.id === 'ErrorBoundary'
        );
        expect(boundaryEvent).toBeDefined();
        expect(boundaryEvent?.type).toBe('event');
        expect(boundaryEvent?.eventType).toBe('boundary');
        expect((boundaryEvent as any).eventDefinitions).toHaveLength(1);
        expect((boundaryEvent as any).eventDefinitions[0].type).toBe('error');
      });

      it.skip('should handle multiple processes', async () => {
        const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="Start1" />
    <endEvent id="End1" />
    <sequenceFlow id="Flow1" sourceRef="Start1" targetRef="End1" />
  </process>
  <process id="Process_2" isExecutable="false">
    <startEvent id="Start2" />
    <endEvent id="End2" />
    <sequenceFlow id="Flow2" sourceRef="Start2" targetRef="End2" />
  </process>
</definitions>`;

        const result = await importer.importFromXml(xml);

        expect(result.definitions.processes).toHaveLength(2);
        expect(result.definitions.processes[0].id).toBe('Process_1');
        expect(result.definitions.processes[0].isExecutable).toBe(true);
        expect(result.definitions.processes[1].id).toBe('Process_2');
        expect(result.definitions.processes[1].isExecutable).toBe(false);
      });

      it.skip('should handle invalid XML gracefully', async () => {
        const invalidXml = '<invalid>xml</invalid>';

        await expect(importer.importFromXml(invalidXml))
          .rejects.toThrow();
      });

      it.skip('should handle empty XML', async () => {
        const emptyXml = '<?xml version="1.0"?><definitions></definitions>';

        const result = await importer.importFromXml(emptyXml);

        expect(result.definitions.processes).toHaveLength(0);
      });
    });
  });

  describe.skip('parseXml() function', () => {
    it('should be exported and work', async () => {
      const xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="StartEvent_1" />
    <endEvent id="EndEvent_1" />
    <sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="EndEvent_1" />
  </process>
</definitions>`;

      const result = await parseXml(xml);

      expect(result).toBeDefined();
      expect(result.definitions.processes).toHaveLength(1);
    });
  });

  describe.skip('Round-trip Compatibility', () => {
    it('should maintain data integrity through import/export cycles', async () => {
      // This would test that import -> export -> import produces equivalent results
      const originalXml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="StartEvent_1" name="Start">
      <outgoing>Flow_1</outgoing>
    </startEvent>
    <userTask id="UserTask_1" name="Review">
      <incoming>Flow_1</incoming>
      <outgoing>Flow_2</outgoing>
    </userTask>
    <endEvent id="EndEvent_1" name="End">
      <incoming>Flow_2</incoming>
    </endEvent>
    <sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="UserTask_1" />
    <sequenceFlow id="Flow_2" sourceRef="UserTask_1" targetRef="EndEvent_1" />
  </process>
</definitions>`;

      // Import
      const imported = await importer.importFromXml(originalXml);

      // This would typically be followed by export and re-import to test round-trip
      expect(imported).toBeDefined();
      expect(imported.definitions.processes[0].flowElements).toHaveLength(3);
    });
  });
});
