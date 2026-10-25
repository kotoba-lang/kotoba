import type { BpmnIR } from '@etzhayyim/bpmn-sdk-core';
export declare class BpmnCompiler {
    constructor();
    /**
     * Compile BPMN IR to BPMN 2.0 XML string
     */
    compileToXml(ir: BpmnIR): Promise<string>;
    /**
     * Create BPMN Definitions element from IR
     */
    private createDefinitions;
}
export declare function compileToXml(ir: BpmnIR): Promise<string>;
//# sourceMappingURL=bpmn-compiler.d.ts.map