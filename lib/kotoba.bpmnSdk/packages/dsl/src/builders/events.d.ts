import type { DslContext, MutableEventIR } from '../bpmn-dsl.js';
export declare class BaseEventBuilder {
    protected context: DslContext;
    protected event: MutableEventIR;
    constructor(context: DslContext, event: MutableEventIR);
    message(messageRef?: string): this;
    signal(signalRef?: string): this;
    error(errorRef?: string): this;
    timer(config: {
        timeDate?: string;
        timeCycle?: string;
        timeDuration?: string;
    }): this;
    compensation(activityRef?: string, waitForCompletion?: boolean): this;
    conditional(condition: string): this;
    link(name?: string): this;
    terminate(): this;
    cancel(): this;
    escalation(escalationRef?: string): this;
    multiple(): this;
    parallelMultiple(): this;
}
export declare class StartEventBuilder extends BaseEventBuilder {
}
export declare class EndEventBuilder extends BaseEventBuilder {
}
export declare class IntermediateCatchEventBuilder extends BaseEventBuilder {
}
export declare class BoundaryEventBuilder extends BaseEventBuilder {
    nonInterrupting(): this;
    interrupting(): this;
}
//# sourceMappingURL=events.d.ts.map