// Merkle DAG: dsl_task_builders
// DSL Task Builders - Service/User/Manual/Script/BusinessRule/Send/Receive/CallActivity

import type { TaskIR } from '@etzhayyim/bpmn-sdk-core';
import type { DslContext, MutableTaskIR } from '../bpmn-dsl.js';

// Base Task Builder
export class BaseTaskBuilder {
  protected context: DslContext;
  protected task: MutableTaskIR;

  constructor(context: DslContext, task: MutableTaskIR) {
    this.context = context;
    this.task = task;
  }

  // Set task name
  name(name: string): this {
    this.task.name = name;
    return this;
  }
}

// Service Task Builder
export class ServiceTaskBuilder extends BaseTaskBuilder {
  implementation(impl: string): this {
    (this.task as any).implementation = impl;
    return this;
  }

  topic(topic: string): this {
    (this.task as any).topic = topic;
    return this;
  }

  operation(operationRef: string): this {
    (this.task as any).operationRef = operationRef;
    return this;
  }

  javaClass(className: string): this {
    (this.task as any).class = className;
    return this;
  }

  delegateExpression(expression: string): this {
    (this.task as any).delegateExpression = expression;
    return this;
  }

  expression(expression: string): this {
    (this.task as any).expression = expression;
    return this;
  }

  resultVariable(variable: string): this {
    (this.task as any).resultVariable = variable;
    return this;
  }
}

// User Task Builder
export class UserTaskBuilder extends BaseTaskBuilder {
  assignee(assignee: string): this {
    (this.task as any).assignee = assignee;
    return this;
  }

  candidateUsers(users: string): this {
    (this.task as any).candidateUsers = users;
    return this;
  }

  candidateGroups(groups: string[]): this {
    (this.task as any).candidateGroups = groups;
    return this;
  }

  dueDate(dueDate: string): this {
    (this.task as any).dueDate = dueDate;
    return this;
  }

  formKey(formKey: string): this {
    (this.task as any).formKey = formKey;
    return this;
  }
}

// Manual Task Builder
export class ManualTaskBuilder extends BaseTaskBuilder {
  // Manual tasks don't have special configurations beyond the base
}

// Script Task Builder
export class ScriptTaskBuilder extends BaseTaskBuilder {
  script(script: string): this {
    (this.task as any).script = script;
    return this;
  }

  scriptFormat(format: string): this {
    // Note: scriptFormat is not in current TaskIR, might need to add
    return this;
  }

  resultVariable(variable: string): this {
    (this.task as any).resultVariable = variable;
    return this;
  }
}

// Business Rule Task Builder
export class BusinessRuleTaskBuilder extends BaseTaskBuilder {
  decisionRef(decisionRef: string): this {
    (this.task as any).decisionRef = decisionRef;
    return this;
  }

  resultVariable(variable: string): this {
    (this.task as any).resultVariable = variable;
    return this;
  }
}

// Send Task Builder
export class SendTaskBuilder extends BaseTaskBuilder {
  message(messageRef: string): this {
    (this.task as any).messageRef = messageRef;
    return this;
  }

  operation(operationRef: string): this {
    (this.task as any).operationRef = operationRef;
    return this;
  }
}

// Receive Task Builder
export class ReceiveTaskBuilder extends BaseTaskBuilder {
  message(messageRef: string): this {
    (this.task as any).messageRef = messageRef;
    return this;
  }

  operation(operationRef: string): this {
    (this.task as any).operationRef = operationRef;
    return this;
  }

  instantiate(instantiate: boolean = true): this {
    (this.task as any).instantiate = instantiate;
    return this;
  }
}

// Call Activity Builder
export class CallActivityBuilder extends BaseTaskBuilder {
  calledElement(processId: string): this {
    (this.task as any).calledElement = processId;
    return this;
  }
}
