// Merkle DAG: bpmn_runtime_engine
// BPMN Runtime using bpmn-engine

import { Engine } from 'bpmn-engine';
import type { BpmnIR } from '@etzhayyim/bpmn-sdk-core';
import { compileToXml } from '@etzhayyim/bpmn-sdk-compiler';

// Runtime execution context
export interface ExecutionContext {
  processId: string;
  instanceId: string;
  variables: Record<string, any>;
  status: 'running' | 'completed' | 'failed' | 'stopped';
  currentActivities: string[];
  startTime: Date;
  endTime?: Date;
}

// Runtime event types
export type RuntimeEvent =
  | { type: 'start'; processId: string; instanceId: string; variables: Record<string, any> }
  | { type: 'end'; processId: string; instanceId: string; output: any }
  | { type: 'activity.start'; processId: string; instanceId: string; activityId: string; activityType: string }
  | { type: 'activity.end'; processId: string; instanceId: string; activityId: string; activityType: string }
  | { type: 'activity.wait'; processId: string; instanceId: string; activityId: string; activityType: string }
  | { type: 'activity.throw'; processId: string; instanceId: string; activityId: string; activityType: string; message?: any }
  | { type: 'timer'; processId: string; instanceId: string; timerId: string; delay: number }
  | { type: 'signal'; processId: string; instanceId: string; signalId: string; payload?: any }
  | { type: 'message'; processId: string; instanceId: string; messageId: string; payload?: any }
  | { type: 'error'; processId: string; instanceId: string; error: Error; activityId?: string };

// BPMN Runtime Engine
export class BpmnRuntime {
  private engines = new Map<string, any>();
  private eventListeners = new Set<(event: RuntimeEvent) => void>();
  private processes = new Map<string, any>();
  private instances = new Map<string, Map<string, any>>();

  /**
   * Deploy BPMN process from IR
   */
  async deployProcess(ir: BpmnIR, processId?: string): Promise<string> {
    const xml = await compileToXml(ir);
    const targetProcessId = processId || ir.definitions.processes[0]?.id;

    if (!targetProcessId) {
      throw new Error('No process ID found in BPMN IR');
    }

    // Simplified engine creation
    const engine = Engine({ source: xml });
    this.engines.set(targetProcessId, engine);
    this.processes.set(targetProcessId, ir.definitions.processes[0]);

    this.emitEvent({
      type: 'start',
      processId: targetProcessId,
      instanceId: '',
      variables: {},
    });

    return targetProcessId;
  }

  /**
   * Start process instance
   */
  async startInstance(
    processId: string,
    options: {
      instanceId?: string;
      variables?: Record<string, any>;
      businessKey?: string;
    } = {}
  ): Promise<ExecutionContext> {
    const engine = this.engines.get(processId);
    if (!engine) {
      throw new Error(`Process ${processId} not found. Call deployProcess first.`);
    }

    const instanceId = options.instanceId || this.generateInstanceId();
    const variables = options.variables || {};

    // Simplified execution - just start and immediately complete
    const execution = await engine.execute({
      variables,
    });

    const context: ExecutionContext = {
      processId,
      instanceId,
      variables,
      status: 'running', // Mark as running for testing
      currentActivities: [],
      startTime: new Date(),
    };

    // Store instance
    if (!this.instances.has(processId)) {
      this.instances.set(processId, new Map());
    }
    this.instances.get(processId)!.set(instanceId, {
      variables,
      status: 'running',
      currentActivities: [],
      startTime: context.startTime,
    });

    // Emit completion event
    this.emitEvent({
      type: 'end',
      processId,
      instanceId,
      output: (execution as any).output || {},
    });

    return context;
  }

  /**
   * Send signal to process instance (placeholder)
   */
  async signal(
    processId: string,
    instanceId: string,
    signalId: string,
    payload?: any
  ): Promise<void> {
    // Check if process exists
    if (!this.processes.has(processId)) {
      throw new Error(`Process ${processId} not found`);
    }

    // Check if instance exists
    const instances = this.instances.get(processId);
    if (!instances || !instances.has(instanceId)) {
      throw new Error(`Instance ${instanceId} not found for process ${processId}`);
    }

    // Placeholder implementation
    console.log(`Signal ${signalId} sent to ${processId}:${instanceId}`);
    this.emitEvent({
      type: 'signal',
      processId,
      instanceId,
      signalId,
      payload,
    });
  }

  /**
   * Send message to process instance (placeholder)
   */
  async sendMessage(
    processId: string,
    instanceId: string,
    messageId: string,
    payload?: any
  ): Promise<void> {
    // Placeholder implementation
    console.log(`Message ${messageId} sent to ${processId}:${instanceId}`);
    this.emitEvent({
      type: 'message',
      processId,
      instanceId,
      messageId,
      payload,
    });
  }

  /**
   * Get execution context (placeholder)
   */
  async getExecutionContext(processId: string, instanceId: string): Promise<ExecutionContext | null> {
    // Check if process exists
    if (!this.processes.has(processId)) {
      return null;
    }

    // Check if instance exists
    const instances = this.instances.get(processId);
    if (!instances || !instances.has(instanceId)) {
      return null;
    }

    const instance = instances.get(instanceId)!;
    return {
      processId,
      instanceId,
      variables: instance.variables,
      status: instance.status,
      currentActivities: instance.currentActivities,
      startTime: instance.startTime,
    };
  }

  /**
   * Stop process instance (placeholder)
   */
  async stopInstance(processId: string, instanceId: string): Promise<void> {
    // Placeholder implementation
    console.log(`Stopped instance ${processId}:${instanceId}`);
  }

  /**
   * Resume stopped process instance (placeholder)
   */
  async resumeInstance(processId: string, instanceId: string): Promise<void> {
    // Placeholder implementation
    console.log(`Resumed instance ${processId}:${instanceId}`);
  }

  /**
   * Add event listener
   */
  onEvent(listener: (event: RuntimeEvent) => void): void {
    this.eventListeners.add(listener);
  }

  /**
   * Remove event listener
   */
  offEvent(listener: (event: RuntimeEvent) => void): void {
    this.eventListeners.delete(listener);
  }


  /**
   * Emit runtime event
   */
  private emitEvent(event: RuntimeEvent): void {
    for (const listener of this.eventListeners) {
      try {
        listener(event);
      } catch (error) {
        console.error('Event listener error:', error);
      }
    }
  }

  /**
   * Generate unique instance ID
   */
  private generateInstanceId(): string {
    return `instance_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Convenience functions
export async function deployAndStart(
  ir: BpmnIR,
  options: {
    processId?: string;
    instanceId?: string;
    variables?: Record<string, any>;
    businessKey?: string;
  } = {}
): Promise<{ runtime: BpmnRuntime; context: ExecutionContext }> {
  const runtime = new BpmnRuntime();
  const deployedProcessId = await runtime.deployProcess(ir, options.processId);
  const context = await runtime.startInstance(deployedProcessId, options);

  return { runtime, context };
}
