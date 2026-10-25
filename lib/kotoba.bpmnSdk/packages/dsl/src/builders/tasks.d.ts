import type { DslContext, MutableTaskIR } from '../bpmn-dsl.js';
export declare class BaseTaskBuilder {
    protected context: DslContext;
    protected task: MutableTaskIR;
    constructor(context: DslContext, task: MutableTaskIR);
}
export declare class ServiceTaskBuilder extends BaseTaskBuilder {
    implementation(impl: string): this;
    topic(topic: string): this;
    operation(operationRef: string): this;
    javaClass(className: string): this;
    delegateExpression(expression: string): this;
    expression(expression: string): this;
    resultVariable(variable: string): this;
}
export declare class UserTaskBuilder extends BaseTaskBuilder {
    assignee(assignee: string): this;
    candidateUsers(users: string): this;
    candidateGroups(groups: string): this;
    formKey(formKey: string): this;
}
export declare class ManualTaskBuilder extends BaseTaskBuilder {
}
export declare class ScriptTaskBuilder extends BaseTaskBuilder {
    script(script: string): this;
    scriptFormat(format: string): this;
    resultVariable(variable: string): this;
}
export declare class BusinessRuleTaskBuilder extends BaseTaskBuilder {
    decisionRef(decisionRef: string): this;
    resultVariable(variable: string): this;
}
export declare class SendTaskBuilder extends BaseTaskBuilder {
    message(messageRef: string): this;
    operation(operationRef: string): this;
}
export declare class ReceiveTaskBuilder extends BaseTaskBuilder {
    message(messageRef: string): this;
    operation(operationRef: string): this;
    instantiate(instantiate?: boolean): this;
}
export declare class CallActivityBuilder extends BaseTaskBuilder {
    calledElement(processId: string): this;
}
//# sourceMappingURL=tasks.d.ts.map