// Merkle DAG: bpmn_task_types
// BPMN 2.0 Task/Activity 型定義 - 完全網羅

import type { BaseElement, FlowElement, Expression } from './common.js';

// Task Types
export type TaskType =
  | 'service'
  | 'user'
  | 'manual'
  | 'script'
  | 'businessRule'
  | 'send'
  | 'receive'
  | 'callActivity';

// Base Task interface
export interface BaseTask extends FlowElement {
  readonly taskType: TaskType;
  readonly default?: string; // Default sequence flow
  readonly ioSpecification?: InputOutputSpecification;
}

// Service Task - Automated service call
export interface ServiceTask extends BaseTask {
  readonly taskType: 'service';
  readonly implementation?: string; // ##WebService, ##unspecified, etc.
  readonly operationRef?: string;
  readonly class?: string; // Java class
  readonly delegateExpression?: Expression;
  readonly expression?: Expression;
  readonly resultVariable?: string;
  readonly topic?: string; // For external tasks
  readonly type?: string; // External task type
  readonly taskPriority?: string;
}

// User Task - Human-performed task
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

// Manual Task - Unmodeled human activity
export interface ManualTask extends BaseTask {
  readonly taskType: 'manual';
}

// Script Task - Script execution
export interface ScriptTask extends BaseTask {
  readonly taskType: 'script';
  readonly scriptFormat?: string;
  readonly script?: string;
  readonly resultVariable?: string;
}

// Business Rule Task - DMN execution
export interface BusinessRuleTask extends BaseTask {
  readonly taskType: 'businessRule';
  readonly implementation?: string;
  readonly decisionRef?: string;
  readonly resultVariable?: string;
  readonly ruleVariablesInputRef?: string;
  readonly rulesVariablesOutputRef?: string;
  readonly exclude?: boolean;
}

// Send Task - Message sending
export interface SendTask extends BaseTask {
  readonly taskType: 'send';
  readonly implementation?: string;
  readonly operationRef?: string;
  readonly messageRef?: string;
}

// Receive Task - Message receiving
export interface ReceiveTask extends BaseTask {
  readonly taskType: 'receive';
  readonly implementation?: string;
  readonly operationRef?: string;
  readonly messageRef?: string;
  readonly instantiate?: boolean;
}

// Call Activity - Reusable subprocess call
export interface CallActivity extends BaseTask {
  readonly taskType: 'callActivity';
  readonly calledElement?: string; // Process ID to call
  readonly calledElementBinding?: CalledElementBinding;
  readonly calledElementVersion?: string;
  readonly calledElementVersionTag?: string;
  readonly caseRef?: string; // CMMN case reference
  readonly caseBinding?: CalledElementBinding;
  readonly caseVersion?: string;
  readonly inputData?: InputOutputBinding[];
  readonly outputData?: InputOutputBinding[];
}

export type CalledElementBinding = 'latest' | 'deployment' | 'version' | 'versionTag';

// Union type for all tasks
export type Task =
  | ServiceTask
  | UserTask
  | ManualTask
  | ScriptTask
  | BusinessRuleTask
  | SendTask
  | ReceiveTask
  | CallActivity;

// Input/Output Specifications
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
