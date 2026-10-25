import type { FlowElement, Expression } from './common.js';
export type GatewayType = 'exclusive' | 'inclusive' | 'parallel' | 'eventBased' | 'complex';
export interface BaseGateway extends FlowElement {
    readonly gatewayType: GatewayType;
    readonly default?: string;
}
export interface ExclusiveGateway extends BaseGateway {
    readonly gatewayType: 'exclusive';
}
export interface InclusiveGateway extends BaseGateway {
    readonly gatewayType: 'inclusive';
}
export interface ParallelGateway extends BaseGateway {
    readonly gatewayType: 'parallel';
}
export interface EventBasedGateway extends BaseGateway {
    readonly gatewayType: 'eventBased';
    readonly instantiate?: boolean;
    readonly eventGatewayType?: EventGatewayType;
}
export type EventGatewayType = 'Exclusive' | 'Parallel';
export interface ComplexGateway extends BaseGateway {
    readonly gatewayType: 'complex';
    readonly activationCondition?: Expression;
    readonly default?: string;
}
export type Gateway = ExclusiveGateway | InclusiveGateway | ParallelGateway | EventBasedGateway | ComplexGateway;
//# sourceMappingURL=gateways.d.ts.map