import { createDmnViewer } from "@etzhayyim/bpmn-sdk-dmn";

const container = document.getElementById("app")!;

const sample = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/"
  xmlns:dmndi="https://www.omg.org/spec/DMN/20191111/DMNDI/"
  xmlns:di="http://www.omg.org/spec/DI/"
  xmlns:dc="http://www.omg.org/spec/DMN/20180521/DC/"
  id="definitions_1" name="sample" namespace="http://example.com/dmn" >
  <decision id="Decision_1" name="Decision">
    <decisionTable id="decisionTable_1" hitPolicy="FIRST"/>
  </decision>
  <dmndi:DMNDI>
    <dmndi:DMNDiagram>
      <dmndi:DMNShape dmnElementRef="Decision_1">
        <dc:Bounds x="100" y="100" width="180" height="80" />
      </dmndi:DMNShape>
    </dmndi:DMNDiagram>
  </dmndi:DMNDI>
</definitions>`;

void (async () => {
  const viewer = await createDmnViewer({ container });
  await viewer.importXML(sample);
})();

