import type { BpmnIR } from '@etzhayyim/bpmn-sdk-core';
export interface ExecutionContext {
    processId: string;
    instanceId: string;
    variables: Record<string, any>;
    status: 'running' | 'completed' | 'failed' | 'stopped';
    currentActivities: string[];
    startTime: Date;
    endTime?: Date;
}
export type RuntimeEvent = {
    type: 'start';
    processId: string;
    instanceId: string;
    variables: Record<string, any>;
} | {
    type: 'end';
    processId: string;
    instanceId: string;
    output: any;
} | {
    type: 'activity.start';
    processId: string;
    instanceId: string;
    activityId: string;
    activityType: string;
} | {
    type: 'activity.end';
    processId: string;
    instanceId: string;
    activityId: string;
    activityType: string;
} | {
    type: 'activity.wait';
    processId: string;
    instanceId: string;
    activityId: string;
    activityType: string;
} | {
    type: 'activity.throw';
    processId: string;
    instanceId: string;
    activityId: string;
    activityType: string;
    message?: any;
} | {
    type: 'timer';
    processId: string;
    instanceId: string;
    timerId: string;
    delay: number;
} | {
    type: 'signal';
    processId: string;
    instanceId: string;
    signalId: string;
    payload?: any;
} | {
    type: 'message';
    processId: string;
    instanceId: string;
    messageId: string;
    payload?: any;
} | {
    type: 'error';
    processId: string;
    instanceId: string;
    error: Error;
    activityId?: string;
};
export declare class BpmnRuntime {
    private engines;
    private eventListeners;
    private processes;
    private instances;
    /**
     * Deploy BPMN process from IR
     */
    deployProcess(ir: BpmnIR, processId?: string): Promise<string>;
    /**
     * Start process instance
     */
    startInstance(processId: string, options?: {
        instanceId?: string;
        variables?: Record<string, any>;
        businessKey?: string;
    }): Promise<ExecutionContext>;
    /**
     * Send signal to process instance (placeholder)
     */
    signal(processId: string, instanceId: string, signalId: string, payload?: any): Promise<void>;
    /**
     * Send message to process instance (placeholder)
     */
    sendMessage(processId: string, instanceId: string, messageId: string, payload?: any): Promise<void>;
    /**
     * Get execution context (placeholder)
     */
    getExecutionContext(processId: string, instanceId: string): Promise<ExecutionContext | null>;
    /**
     * Stop process instance (placeholder)
     */
    stopInstance(processId: string, instanceId: string): Promise<void>;
    /**
     * Resume stopped process instance (placeholder)
     */
    resumeInstance(processId: string, instanceId: string): Promise<void>;
    /**
     * Add event listener
     */
    onEvent(listener: (event: RuntimeEvent) => void): void;
    /**
     * Remove event listener
     */
    offEvent(listener: (event: RuntimeEvent) => void): void;
    /**
     * Emit runtime event
     */
    private emitEvent;
    /**
     * Generate unique instance ID
     */
    private generateInstanceId;
}
export declare function deployAndStart(ir: BpmnIR, options?: {
    processId?: string;
    instanceId?: string;
    variables?: Record<string, any>;
    businessKey?: string;
}): Promise<{
    runtime: BpmnRuntime;
    context: ExecutionContext;
}>;
//# sourceMappingURL=bpmn-runtime.d.ts.map