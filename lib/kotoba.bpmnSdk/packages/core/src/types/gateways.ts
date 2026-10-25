// Merkle DAG: bpmn_gateway_types
// BPMN 2.0 Gateway 型定義 - 完全網羅

import type { FlowElement, Expression } from './common.js';

// Gateway Types
export type GatewayType = 'exclusive' | 'inclusive' | 'parallel' | 'eventBased' | 'complex';

// Base Gateway interface
export interface BaseGateway extends FlowElement {
  readonly gatewayType: GatewayType;
  readonly default?: string; // Default sequence flow (for exclusive/inclusive)
}

// Exclusive Gateway (XOR) - Only one path
export interface ExclusiveGateway extends BaseGateway {
  readonly gatewayType: 'exclusive';
}

// Inclusive Gateway (OR) - One or more paths
export interface InclusiveGateway extends BaseGateway {
  readonly gatewayType: 'inclusive';
}

// Parallel Gateway (AND) - All paths
export interface ParallelGateway extends BaseGateway {
  readonly gatewayType: 'parallel';
}

// Event-based Gateway - Routes based on first event
export interface EventBasedGateway extends BaseGateway {
  readonly gatewayType: 'eventBased';
  readonly instantiate?: boolean;
  readonly eventGatewayType?: EventGatewayType;
}

export type EventGatewayType = 'Exclusive' | 'Parallel';

// Complex Gateway - Custom routing logic
export interface ComplexGateway extends BaseGateway {
  readonly gatewayType: 'complex';
  readonly activationCondition?: Expression;
  readonly default?: string;
}

// Union type for all gateways
export type Gateway =
  | ExclusiveGateway
  | InclusiveGateway
  | ParallelGateway
  | EventBasedGateway
  | ComplexGateway;
