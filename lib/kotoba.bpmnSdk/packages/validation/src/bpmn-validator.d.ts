import type { BpmnIR } from '@etzhayyim/bpmn-sdk-core';
import type { ValidationResult, ValidationOptions } from './types.js';
export declare class BpmnValidator {
    private options;
    constructor(options?: ValidationOptions);
    /**
     * BPMNプロセスを検証
     */
    validateProcess(ir: BpmnIR): Promise<ValidationResult>;
    /**
     * プロセスIRを検証
     */
    private validateProcessIR;
    /**
     * 到達性分析
     */
    private analyzeReachability;
    /**
     * 到達性を検証
     */
    private validateReachability;
    /**
     * デッドエンドを検出
     */
    private findDeadEnds;
    /**
     * ゲートウェイ一貫性を検証
     */
    private validateGatewayConsistency;
    /**
     * イベント一貫性を検証
     */
    private validateEventConsistency;
    /**
     * フロー一貫性を検証
     */
    private validateFlowConsistency;
    /**
     * BPMN仕様準拠を検証
     */
    private validateBpmnCompliance;
    /**
     * 検証統計を計算
     */
    private calculateStatistics;
    /**
     * 複雑度スコアを計算
     */
    private calculateComplexityScore;
}
export declare function validateProcess(ir: BpmnIR, options?: ValidationOptions): Promise<ValidationResult>;
//# sourceMappingURL=bpmn-validator.d.ts.map