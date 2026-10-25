// Merkle DAG: bpmn_internal_representation
// BPMN 2.0 内部表現 (IR) - DSL → XML 変換の中間層
// Utility functions for IR manipulation
export class BpmnIRUtils {
    static generateId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    static validateIR(ir) {
        const errors = [];
        // Basic validation
        if (!ir.definitions.id) {
            errors.push('Definitions must have an id');
        }
        if (!ir.definitions.targetNamespace) {
            errors.push('Definitions must have a targetNamespace');
        }
        // Validate processes
        ir.definitions.processes.forEach((process, index) => {
            if (!process.id) {
                errors.push(`Process ${index} must have an id`);
            }
            if (process.flowElements.length === 0) {
                errors.push(`Process ${process.id} must have at least one flow element`);
            }
        });
        return {
            valid: errors.length === 0,
            errors,
        };
    }
}
//# sourceMappingURL=bpmn-ir.js.map