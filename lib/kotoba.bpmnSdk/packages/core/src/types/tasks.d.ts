import type { BaseElement, FlowElement, Expression } from './common.js';
export type TaskType = 'service' | 'user' | 'manual' | 'script' | 'businessRule' | 'send' | 'receive' | 'callActivity';
export interface BaseTask extends FlowElement {
    readonly taskType: TaskType;
    readonly default?: string;
    readonly ioSpecification?: InputOutputSpecification;
}
export interface ServiceTask extends BaseTask {
    readonly taskType: 'service';
    readonly implementation?: string;
    readonly operationRef?: string;
    readonly class?: string;
    readonly delegateExpression?: Expression;
    readonly expression?: Expression;
    readonly resultVariable?: string;
    readonly topic?: string;
    readonly type?: string;
    readonly taskPriority?: string;
}
export interface UserTask extends BaseTask {
    readonly taskType: 'user';
    readonly assignee?: Expression;
    readonly candidateUsers?: Expression;
    readonly candidateGroups?: Expression;
    readonly dueDate?: Expression;
    readonly followUpDate?: Expression;
    readonly priority?: Expression;
    readonly formKey?: string;
    readonly formRef?: string;
    readonly renderType?: string;
    readonly skipExpression?: Expression;
}
export interface ManualTask extends BaseTask {
    readonly taskType: 'manual';
}
export interface ScriptTask extends BaseTask {
    readonly taskType: 'script';
    readonly scriptFormat?: string;
    readonly script?: string;
    readonly resultVariable?: string;
}
export interface BusinessRuleTask extends BaseTask {
    readonly taskType: 'businessRule';
    readonly implementation?: string;
    readonly decisionRef?: string;
    readonly resultVariable?: string;
    readonly ruleVariablesInputRef?: string;
    readonly rulesVariablesOutputRef?: string;
    readonly exclude?: boolean;
}
export interface SendTask extends BaseTask {
    readonly taskType: 'send';
    readonly implementation?: string;
    readonly operationRef?: string;
    readonly messageRef?: string;
}
export interface ReceiveTask extends BaseTask {
    readonly taskType: 'receive';
    readonly implementation?: string;
    readonly operationRef?: string;
    readonly messageRef?: string;
    readonly instantiate?: boolean;
}
export interface CallActivity extends BaseTask {
    readonly taskType: 'callActivity';
    readonly calledElement?: string;
    readonly calledElementBinding?: CalledElementBinding;
    readonly calledElementVersion?: string;
    readonly calledElementVersionTag?: string;
    readonly caseRef?: string;
    readonly caseBinding?: CalledElementBinding;
    readonly caseVersion?: string;
    readonly inputData?: InputOutputBinding[];
    readonly outputData?: InputOutputBinding[];
}
export type CalledElementBinding = 'latest' | 'deployment' | 'version' | 'versionTag';
export type Task = ServiceTask | UserTask | ManualTask | ScriptTask | BusinessRuleTask | SendTask | ReceiveTask | CallActivity;
export interface InputOutputSpecification extends BaseElement {
    readonly inputSets?: InputSet[];
    readonly outputSets?: OutputSet[];
    readonly dataInputs?: DataInput[];
    readonly dataOutputs?: DataOutput[];
}
export interface InputSet extends BaseElement {
    readonly name?: string;
    readonly dataInputRefs?: string[];
    readonly optionalInputRefs?: string[];
    readonly whileExecutingInputRefs?: string[];
    readonly outputSetRefs?: string[];
}
export interface OutputSet extends BaseElement {
    readonly name?: string;
    readonly dataOutputRefs?: string[];
    readonly optionalOutputRefs?: string[];
    readonly whileExecutingOutputRefs?: string[];
    readonly inputSetRefs?: string[];
}
export interface DataInput extends BaseElement {
    readonly name?: string;
    readonly isCollection?: boolean;
    readonly itemSubjectRef?: string;
}
export interface DataOutput extends BaseElement {
    readonly name?: string;
    readonly isCollection?: boolean;
    readonly itemSubjectRef?: string;
}
export interface InputOutputBinding {
    readonly inputDataRef: string;
    readonly outputDataRef: string;
    readonly operationRef?: string;
}
//# sourceMappingURL=tasks.d.ts.map