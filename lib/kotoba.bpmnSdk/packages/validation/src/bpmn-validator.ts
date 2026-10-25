// Merkle DAG: bpmn_validator
// BPMN Static Validator - 到達性分析とプロセス検証

import type { BpmnIR, ProcessIR, FlowElementIR } from '@etzhayyim/bpmn-sdk-core';
import type {
  ValidationResult,
  ValidationError,
  ValidationOptions,
  ReachabilityGraph,
  GatewayAnalysis,
  ProcessMetrics,
} from './types.js';

export class BpmnValidator {
  private options: Required<ValidationOptions>;

  constructor(options: ValidationOptions = {}) {
    this.options = {
      checkReachability: true,
      checkDeadEnds: true,
      checkCycles: true,
      checkGatewayConsistency: true,
      checkEventConsistency: true,
      checkFlowConsistency: true,
      strictBpmnCompliance: false,
      maxComplexityScore: 50,
      timeoutMs: 30000,
      ...options,
    };
  }

  /**
   * BPMNプロセスを検証
   */
  async validateProcess(ir: BpmnIR): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];

    // 各プロセスを検証
    for (const process of ir.definitions.processes) {
      const processResult = await this.validateProcessIR(process);
      errors.push(...processResult.errors);
      warnings.push(...processResult.warnings);
    }

    // 全体的な統計を計算
    const statistics = this.calculateStatistics(ir, errors, warnings);

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      statistics,
    };
  }

  /**
   * プロセスIRを検証
   */
  private async validateProcessIR(process: ProcessIR): Promise<{ errors: ValidationError[], warnings: ValidationError[] }> {
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];

    // 到達性分析
    if (this.options.checkReachability) {
      const reachability = this.analyzeReachability(process);
      errors.push(...this.validateReachability(reachability, process.id));
    }

    // デッドエンドチェック
    if (this.options.checkDeadEnds) {
      const deadEnds = this.findDeadEnds(process);
      for (const elementId of deadEnds) {
        errors.push({
          type: 'dead_end',
          message: `Element ${elementId} has no outgoing flows`,
          elementId,
          severity: 'error',
        });
      }
    }

    // ゲートウェイ一貫性チェック
    if (this.options.checkGatewayConsistency) {
      const gatewayErrors = this.validateGatewayConsistency(process);
      errors.push(...gatewayErrors);
    }

    // イベント一貫性チェック
    if (this.options.checkEventConsistency) {
      const eventErrors = this.validateEventConsistency(process);
      errors.push(...eventErrors);
    }

    // フロー一貫性チェック
    if (this.options.checkFlowConsistency) {
      const flowErrors = this.validateFlowConsistency(process);
      errors.push(...flowErrors);
    }

    // BPMN仕様準拠チェック
    if (this.options.strictBpmnCompliance) {
      const complianceErrors = this.validateBpmnCompliance(process);
      errors.push(...complianceErrors);
    }

    return { errors, warnings };
  }

  /**
   * 到達性分析
   */
  private analyzeReachability(process: ProcessIR): ReachabilityGraph {
    const nodes = new Set<string>();
    const edges = new Map<string, Set<string>>();
    const startNodes = new Set<string>();
    const endNodes = new Set<string>();

    // ノードとエッジを構築
    for (const element of process.flowElements) {
      nodes.add(element.id);

      // Start/Endイベントの特定
      if (element.type === 'event') {
        if ((element as any).eventType === 'start') {
          startNodes.add(element.id);
        } else if ((element as any).eventType === 'end') {
          endNodes.add(element.id);
        }
      }
    }

    // シーケンスフローをエッジとして追加
    for (const flow of process.sequenceFlows) {
      if (!edges.has(flow.sourceRef)) {
        edges.set(flow.sourceRef, new Set());
      }
      edges.get(flow.sourceRef)!.add(flow.targetRef);
    }

    // 到達可能ノードを計算
    const reachableNodes = new Set<string>();
    const visited = new Set<string>();

    const dfs = (nodeId: string) => {
      if (visited.has(nodeId)) return;
      visited.add(nodeId);
      reachableNodes.add(nodeId);

      const neighbors = edges.get(nodeId);
      if (neighbors) {
        for (const neighbor of neighbors) {
          dfs(neighbor);
        }
      }
    };

    // スタートノードから探索開始
    for (const startNode of startNodes) {
      dfs(startNode);
    }

    // 到達不能ノードを特定
    const unreachableNodes = new Set<string>();
    for (const node of nodes) {
      if (!reachableNodes.has(node)) {
        unreachableNodes.add(node);
      }
    }

    // デッドエンドを特定
    const deadEndNodes = new Set<string>();
    for (const node of reachableNodes) {
      const neighbors = edges.get(node);
      if (!neighbors || neighbors.size === 0) {
        if (!endNodes.has(node)) {
          deadEndNodes.add(node);
        }
      }
    }

    return {
      nodes,
      edges,
      startNodes,
      endNodes,
      reachableNodes,
      unreachableNodes,
      deadEndNodes,
      cycles: [], // サイクル検出は別途実装
    };
  }

  /**
   * 到達性を検証
   */
  private validateReachability(reachability: ReachabilityGraph, processId: string): ValidationError[] {
    const errors: ValidationError[] = [];

    // 到達不能ノードのエラー
    for (const nodeId of reachability.unreachableNodes) {
      errors.push({
        type: 'unreachable_element',
        message: `Element ${nodeId} is unreachable from any start event`,
        elementId: nodeId,
        severity: 'error',
        suggestion: 'Add sequence flows to connect this element to the process flow',
      });
    }

    return errors;
  }

  /**
   * デッドエンドを検出
   */
  private findDeadEnds(process: ProcessIR): string[] {
    const deadEnds: string[] = [];
    const flowTargets = new Set<string>();

    // すべてのフローのターゲットを収集
    for (const flow of process.sequenceFlows) {
      flowTargets.add(flow.targetRef);
    }

    // アウトゴーイングフローを持たない要素を検出
    for (const element of process.flowElements) {
      if (element.type === 'event' && (element as any).eventType === 'end') {
        continue; // EndイベントはデッドエンドとしてOK
      }

      const hasOutgoing = process.sequenceFlows.some(flow => flow.sourceRef === element.id);
      if (!hasOutgoing) {
        deadEnds.push(element.id);
      }
    }

    return deadEnds;
  }

  /**
   * ゲートウェイ一貫性を検証
   */
  private validateGatewayConsistency(process: ProcessIR): ValidationError[] {
    const errors: ValidationError[] = [];

    for (const element of process.flowElements) {
      if (element.type === 'gateway') {
        const gateway = element as any;

        // 入力フロー数のチェック
        const incomingFlows = process.sequenceFlows.filter(flow => flow.targetRef === element.id);
        if (incomingFlows.length === 0) {
          errors.push({
            type: 'gateway_no_incoming',
            message: `Gateway ${element.id} has no incoming flows`,
            elementId: element.id,
            severity: 'error',
          });
        }

        // 出力フロー数のチェック
        const outgoingFlows = process.sequenceFlows.filter(flow => flow.sourceRef === element.id);
        if (outgoingFlows.length === 0) {
          errors.push({
            type: 'gateway_no_outgoing',
            message: `Gateway ${element.id} has no outgoing flows`,
            elementId: element.id,
            severity: 'error',
          });
        }

        // XORゲートウェイのデフォルトフロー検証
        if (gateway.gatewayType === 'exclusive' && outgoingFlows.length > 1) {
          const hasConditions = outgoingFlows.some(flow => flow.conditionExpression);
          if (hasConditions && !gateway.default) {
            errors.push({
              type: 'xor_no_default',
              message: `Exclusive gateway ${element.id} with conditions must have a default flow`,
              elementId: element.id,
              severity: 'error',
            });
          }
        }
      }
    }

    return errors;
  }

  /**
   * イベント一貫性を検証
   */
  private validateEventConsistency(process: ProcessIR): ValidationError[] {
    const errors: ValidationError[] = [];
    let startEventCount = 0;
    let endEventCount = 0;

    for (const element of process.flowElements) {
      if (element.type === 'event') {
        const event = element as any;

        // Startイベント数のチェック
        if (event.eventType === 'start') {
          startEventCount++;
        }

        // Endイベント数のチェック
        if (event.eventType === 'end') {
          endEventCount++;
        }

        // イベント定義のチェック
        if (event.eventDefinitions && event.eventDefinitions.length === 0) {
          errors.push({
            type: 'event_no_definition',
            message: `Event ${element.id} has no event definitions`,
            elementId: element.id,
            severity: 'error',
          });
        }

        // Boundaryイベントのチェック
        if (event.eventType === 'boundary') {
          if (!event.attachedToRef) {
            errors.push({
              type: 'boundary_event_invalid',
              message: `Boundary event ${element.id} must be attached to an activity`,
              elementId: element.id,
              severity: 'error',
            });
          }
        }
      }
    }

    // Startイベント数の検証
    if (startEventCount === 0) {
      errors.push({
        type: 'start_event_multiple',
        message: 'Process must have at least one start event',
        severity: 'error',
      });
    }

    // Endイベント数の検証
    if (endEventCount === 0) {
      errors.push({
        type: 'end_event_missing',
        message: 'Process must have at least one end event',
        severity: 'error',
      });
    }

    return errors;
  }

  /**
   * フロー一貫性を検証
   */
  private validateFlowConsistency(process: ProcessIR): ValidationError[] {
    const errors: ValidationError[] = [];

    for (const flow of process.sequenceFlows) {
      // ソース要素の存在チェック
      const sourceExists = process.flowElements.some(el => el.id === flow.sourceRef);
      if (!sourceExists) {
        errors.push({
          type: 'sequence_flow_invalid_target',
          message: `Sequence flow ${flow.id} references non-existent source ${flow.sourceRef}`,
          elementId: flow.id,
          severity: 'error',
        });
      }

      // ターゲット要素の存在チェック
      const targetExists = process.flowElements.some(el => el.id === flow.targetRef);
      if (!targetExists) {
        errors.push({
          type: 'sequence_flow_invalid_target',
          message: `Sequence flow ${flow.id} references non-existent target ${flow.targetRef}`,
          elementId: flow.id,
          severity: 'error',
        });
      }
    }

    return errors;
  }

  /**
   * BPMN仕様準拠を検証
   */
  private validateBpmnCompliance(process: ProcessIR): ValidationError[] {
    const errors: ValidationError[] = [];

    // BPMN仕様に基づく追加検証
    for (const element of process.flowElements) {
      // 必須属性のチェック
      if (!element.id) {
        errors.push({
          type: 'missing_required_attribute',
          message: `Element is missing required 'id' attribute`,
          elementId: element.id,
          severity: 'error',
        });
      }

      // 要素固有の検証
      switch (element.type) {
        case 'task':
          const task = element as any;
          if (!task.taskType) {
            errors.push({
              type: 'missing_required_attribute',
              message: `Task ${element.id} is missing required 'taskType' attribute`,
              elementId: element.id,
              severity: 'error',
            });
          }
          break;

        case 'gateway':
          const gateway = element as any;
          if (!gateway.gatewayType) {
            errors.push({
              type: 'missing_required_attribute',
              message: `Gateway ${element.id} is missing required 'gatewayType' attribute`,
              elementId: element.id,
              severity: 'error',
            });
          }
          break;
      }
    }

    return errors;
  }

  /**
   * 検証統計を計算
   */
  private calculateStatistics(ir: BpmnIR, errors: ValidationError[], warnings: ValidationError[]): any {
    const elementsByType: Record<string, number> = {};

    for (const process of ir.definitions.processes) {
      for (const element of process.flowElements) {
        elementsByType[element.type] = (elementsByType[element.type] || 0) + 1;
      }
    }

    const totalElements = Object.values(elementsByType).reduce((sum, count) => sum + count, 0);
    const errorElements = new Set(errors.map(e => e.elementId).filter(Boolean));
    const unreachableCount = errors.filter(e => e.type === 'unreachable_element').length;
    const deadEndCount = errors.filter(e => e.type === 'dead_end').length;

    return {
      totalElements,
      elementsByType,
      reachableElements: totalElements - unreachableCount,
      unreachableElements: unreachableCount,
      deadEnds: deadEndCount,
      cycles: 0, // TODO: サイクル検出を実装
      complexityScore: this.calculateComplexityScore(ir),
    };
  }

  /**
   * 複雑度スコアを計算
   */
  private calculateComplexityScore(ir: BpmnIR): number {
    let score = 0;

    for (const process of ir.definitions.processes) {
      // 要素数によるスコア
      score += process.flowElements.length * 0.5;

      // ゲートウェイによるスコア
      const gatewayCount = process.flowElements.filter(el => el.type === 'gateway').length;
      score += gatewayCount * 2;

      // イベントによるスコア
      const eventCount = process.flowElements.filter(el => el.type === 'event').length;
      score += eventCount * 1;

      // シーケンスフローによるスコア
      score += process.sequenceFlows.length * 0.3;
    }

    return Math.round(score);
  }
}

// 便利関数
export async function validateProcess(ir: BpmnIR, options?: ValidationOptions): Promise<ValidationResult> {
  const validator = new BpmnValidator(options);
  return validator.validateProcess(ir);
}
