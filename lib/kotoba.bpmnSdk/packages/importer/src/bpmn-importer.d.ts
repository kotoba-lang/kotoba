import type { BpmnIR } from '@etzhayyim/bpmn-sdk-core';
export declare class BpmnImporter {
    private moddle;
    constructor();
    /**
     * Import BPMN XML to IR
     */
    importFromXml(xml: string): Promise<BpmnIR>;
    /**
     * Create IR from BPMN Definitions
     */
    private createIR;
    /**
     * Create Process IR from BPMN Process
     */
    private createProcessIR;
    /**
     * Create Flow Element IR from BPMN element
     */
    private createFlowElementIR;
    /**
     * Create Event IR
     */
    private createEventIR;
    /**
     * Create Task IR
     */
    private createTaskIR;
    /**
     * Create Gateway IR
     */
    private createGatewayIR;
    /**
     * Create Sequence Flow IR
     */
    private createSequenceFlowIR;
    /**
     * Create Event Definition IR
     */
    private createEventDefinitionIR;
}
export declare function importFromXml(xml: string): Promise<BpmnIR>;
//# sourceMappingURL=bpmn-importer.d.ts.map