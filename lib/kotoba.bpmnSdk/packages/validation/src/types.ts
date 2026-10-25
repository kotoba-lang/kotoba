// Merkle DAG: validation_types
// Static Validation Types

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  statistics: ValidationStatistics;
}

export interface ValidationError {
  type: ValidationErrorType;
  message: string;
  elementId?: string;
  elementType?: string;
  severity: 'error' | 'warning' | 'info';
  position?: {
    line?: number;
    column?: number;
  };
  suggestion?: string;
}

export type ValidationErrorType =
  // 到達性関連
  | 'unreachable_element'
  | 'dead_end'
  | 'isolated_element'
  // ゲートウェイ関連
  | 'gateway_no_incoming'
  | 'gateway_no_outgoing'
  | 'gateway_mismatch'
  | 'xor_no_default'
  | 'inclusive_no_default'
  // イベント関連
  | 'event_no_definition'
  | 'start_event_multiple'
  | 'end_event_missing'
  | 'boundary_event_invalid'
  // フロー関連
  | 'sequence_flow_no_condition'
  | 'sequence_flow_invalid_target'
  | 'sequence_flow_cycle'
  // 構造関連
  | 'subprocess_no_elements'
  | 'subprocess_no_start'
  | 'missing_participant'
  // BPMN仕様関連
  | 'invalid_element_type'
  | 'missing_required_attribute'
  | 'invalid_reference';

export interface ValidationStatistics {
  totalElements: number;
  elementsByType: Record<string, number>;
  reachableElements: number;
  unreachableElements: number;
  deadEnds: number;
  cycles: number;
  complexityScore: number;
}

export interface ValidationOptions {
  // 到達性分析の設定
  checkReachability?: boolean;
  checkDeadEnds?: boolean;
  checkCycles?: boolean;

  // 構造検証の設定
  checkGatewayConsistency?: boolean;
  checkEventConsistency?: boolean;
  checkFlowConsistency?: boolean;

  // BPMN仕様準拠チェック
  strictBpmnCompliance?: boolean;

  // パフォーマンス設定
  maxComplexityScore?: number;
  timeoutMs?: number;
}

export interface ReachabilityGraph {
  nodes: Set<string>;
  edges: Map<string, Set<string>>;
  startNodes: Set<string>;
  endNodes: Set<string>;
  reachableNodes: Set<string>;
  unreachableNodes: Set<string>;
  deadEndNodes: Set<string>;
  cycles: string[][];
}

export interface GatewayAnalysis {
  exclusiveGateways: GatewayFlow[];
  inclusiveGateways: GatewayFlow[];
  parallelGateways: GatewayFlow[];
  complexGateways: GatewayFlow[];
}

export interface GatewayFlow {
  gatewayId: string;
  incomingFlows: string[];
  outgoingFlows: string[];
  defaultFlow?: string;
  hasConditions: boolean;
  isBalanced: boolean;
}

export interface ProcessMetrics {
  cyclomaticComplexity: number;
  controlFlowComplexity: number;
  dataFlowComplexity: number;
  elementCount: number;
  connectionDensity: number;
  averagePathLength: number;
}
