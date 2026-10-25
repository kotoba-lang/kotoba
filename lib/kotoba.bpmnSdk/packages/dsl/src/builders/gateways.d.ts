import type { DslContext, MutableGatewayIR, MutableSequenceFlowIR } from '../bpmn-dsl.js';
export declare class BaseGatewayBuilder {
    protected context: DslContext;
    protected gateway: MutableGatewayIR;
    constructor(context: DslContext, gateway: MutableGatewayIR);
    default(flowId: string): this;
}
export declare class ExclusiveGatewayBuilder extends BaseGatewayBuilder {
}
export declare class InclusiveGatewayBuilder extends BaseGatewayBuilder {
}
export declare class ParallelGatewayBuilder extends BaseGatewayBuilder {
}
export declare class EventBasedGatewayBuilder extends BaseGatewayBuilder {
    instantiate(instantiate?: boolean): this;
    exclusive(): this;
    parallel(): this;
}
export declare class ComplexGatewayBuilder extends BaseGatewayBuilder {
    activationCondition(condition: string): this;
}
export declare class SequenceFlowBuilder {
    private context;
    private flow;
    constructor(context: DslContext, flow: MutableSequenceFlowIR);
    condition(expression: string): this;
    immediate(immediate?: boolean): this;
}
//# sourceMappingURL=gateways.d.ts.map