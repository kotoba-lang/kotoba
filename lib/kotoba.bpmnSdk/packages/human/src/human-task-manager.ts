// Merkle DAG: human_task_manager
// Human Task Manager - ユーザー割り当てとタスク管理

import type { BpmnRuntime, ExecutionContext, RuntimeEvent } from '@etzhayyim/bpmn-sdk-runtime';
import type {
  HumanTask,
  TaskStatus,
  TaskAssignment,
  TaskComment,
  TaskAttachment,
  TaskSLA,
  TaskEvent,
} from './types.js';

export class HumanTaskManager {
  private runtime: BpmnRuntime;
  private tasks = new Map<string, HumanTask>();
  private assignments = new Map<string, TaskAssignment>();
  private slas = new Map<string, TaskSLA>();
  private eventListeners = new Set<(event: TaskEvent) => void>();

  constructor(runtime: BpmnRuntime) {
    this.runtime = runtime;
    this.setupRuntimeListeners();
  }

  /**
   * タスクを作成
   */
  async createTask(
    processId: string,
    instanceId: string,
    activityId: string,
    options: {
      name: string;
      description?: string;
      priority?: number;
      assignee?: string;
      candidateUsers?: string[];
      candidateGroups?: string[];
      dueDate?: Date;
      formKey?: string;
      variables?: Record<string, any>;
      slaDefinition?: any; // SLADefinition
    }
  ): Promise<HumanTask> {
    const taskId = this.generateTaskId();
    const now = new Date();

    const task: HumanTask = {
      id: taskId,
      processId,
      instanceId,
      activityId,
      name: options.name,
      description: options.description,
      priority: options.priority || 0,
      assignee: options.assignee,
      candidateUsers: options.candidateUsers,
      candidateGroups: options.candidateGroups,
      dueDate: options.dueDate,
      status: options.assignee ? 'reserved' : 'ready',
      createdAt: now,
      variables: options.variables,
      formKey: options.formKey,
      comments: [],
      attachments: [],
    };

    this.tasks.set(taskId, task);

    // SLA設定
    if (options.slaDefinition) {
      const sla: TaskSLA = {
        taskId,
        slaDefinition: options.slaDefinition,
        startTime: now,
        breached: false,
      };
      this.slas.set(taskId, sla);
      this.scheduleSLACheck(taskId);
    }

    this.emitEvent({
      type: 'task.created',
      taskId,
      processId,
      instanceId,
      timestamp: now,
    });

    return task;
  }

  /**
   * タスクを取得
   */
  getTask(taskId: string): HumanTask | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * ユーザーのタスク一覧を取得
   */
  getTasksForUser(userId: string): HumanTask[] {
    return Array.from(this.tasks.values()).filter(task =>
      task.assignee === userId ||
      task.candidateUsers?.includes(userId) ||
      task.candidateGroups?.some(group => this.userInGroup(userId, group))
    );
  }

  /**
   * タスクを請求（claim）
   */
  async claimTask(taskId: string, userId: string): Promise<void> {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    if (task.status !== 'created' && task.status !== 'ready' && task.status !== 'reserved') {
      throw new Error(`Task ${taskId} is not claimable`);
    }

    // 候補者チェック
    if (task.candidateUsers && !task.candidateUsers.includes(userId)) {
      throw new Error(`User ${userId} is not a candidate for task ${taskId}`);
    }

    if (task.candidateGroups && !task.candidateGroups.some(group => this.userInGroup(userId, group))) {
      throw new Error(`User ${userId} is not in candidate groups for task ${taskId}`);
    }

    const now = new Date();
    task.status = 'in_progress';
    task.assignee = userId;
    task.claimedBy = userId;
    task.claimedAt = now;

    const assignment: TaskAssignment = {
      taskId,
      assignee: userId,
      assignedBy: userId, // 自己請求の場合
      assignedAt: now,
      reason: 'claimed',
    };

    this.assignments.set(taskId, assignment);

    this.emitEvent({
      type: 'task.claimed',
      taskId,
      processId: task.processId,
      instanceId: task.instanceId,
      userId,
      timestamp: now,
    });
  }

  /**
   * タスクを割り当て
   */
  async assignTask(taskId: string, assignee: string, assignedBy: string): Promise<void> {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    const now = new Date();
    task.assignee = assignee;
    task.status = 'created';

    const assignment: TaskAssignment = {
      taskId,
      assignee,
      assignedBy,
      assignedAt: now,
      reason: 'assigned',
    };

    this.assignments.set(taskId, assignment);

    this.emitEvent({
      type: 'task.assigned',
      taskId,
      processId: task.processId,
      instanceId: task.instanceId,
      userId: assignedBy,
      timestamp: now,
      data: { assignee },
    });
  }

  /**
   * タスクを完了
   */
  async completeTask(taskId: string, userId: string, variables?: Record<string, any>): Promise<void> {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    if (task.assignee !== userId) {
      throw new Error(`Task ${taskId} is not assigned to user ${userId}`);
    }

    if (task.status !== 'in_progress' && task.status !== 'reserved') {
      throw new Error(`Task ${taskId} is not in progress`);
    }

    const now = new Date();
    task.status = 'completed';
    task.completedAt = now;
    task.outcome = variables;
    task.variables = { ...task.variables, ...variables };

    // プロセスを再開
    await this.runtime.sendMessage(task.processId, task.instanceId, task.activityId, {
      taskId,
      variables: task.variables,
    });

    this.emitEvent({
      type: 'task.completed',
      taskId,
      processId: task.processId,
      instanceId: task.instanceId,
      userId,
      timestamp: now,
      data: { variables },
    });
  }

  /**
   * タスクにコメントを追加
   */
  async addComment(taskId: string, userId: string, message: string): Promise<TaskComment> {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    const comment: TaskComment = {
      id: this.generateCommentId(),
      userId,
      message,
      timestamp: new Date(),
      type: 'comment',
    };

    task.comments = task.comments || [];
    task.comments.push(comment);

    this.emitEvent({
      type: 'task.comment.added',
      taskId,
      processId: task.processId,
      instanceId: task.instanceId,
      userId,
      timestamp: comment.timestamp,
      data: { commentId: comment.id },
    });

    return comment;
  }

  /**
   * SLA違反をチェック
   */
  private scheduleSLACheck(taskId: string): void {
    const sla = this.slas.get(taskId);
    if (!sla) return;

    const breachTime = new Date(sla.startTime.getTime() + sla.slaDefinition.duration);
    sla.breachTime = breachTime;

    // Warning time (e.g., 80% of duration)
    const warningDuration = sla.slaDefinition.duration * 0.8;
    sla.warningTime = new Date(sla.startTime.getTime() + warningDuration);

    setTimeout(() => {
      this.checkSLABreach(taskId);
    }, breachTime.getTime() - Date.now());
  }

  private checkSLABreach(taskId: string): void {
    const sla = this.slas.get(taskId);
    const task = this.tasks.get(taskId);

    if (!sla || !task) return;

    if (task.status === 'completed') return;

    sla.breached = true;
    sla.breachedAt = new Date();

    this.emitEvent({
      type: 'task.sla.breached',
      taskId,
      processId: task.processId,
      instanceId: task.instanceId,
      timestamp: sla.breachedAt,
    });

    // エスカレーション実行
    this.executeEscalationActions(taskId, 'breach');
  }

  private executeEscalationActions(taskId: string, trigger: 'warning' | 'breach'): void {
    const sla = this.slas.get(taskId);
    if (!sla?.escalationActions) return;

    const actions = sla.escalationActions.filter(action => action.trigger === trigger);

    for (const action of actions) {
      // エスカレーション実行ロジック
      console.log(`Executing escalation action: ${action.type} for task ${taskId}`);
    }
  }

  private userInGroup(userId: string, groupId: string): boolean {
    // 実際の実装では、ユーザー管理システムと連携
    return true; // 簡易実装
  }

  private generateTaskId(): string {
    return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateCommentId(): string {
    return `comment_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private setupRuntimeListeners(): void {
    // BPMNランタイムからのイベントを監視
    this.runtime.onEvent((event: RuntimeEvent) => {
      if (event.type === 'activity.wait' && event.activityType === 'userTask') {
        // User Taskが待機状態になったら、人手タスクを作成
        this.createTask(
          event.processId,
          event.instanceId,
          event.activityId,
          {
            name: event.activityId,
            // 実際の実装では、プロセス定義から詳細情報を取得
          }
        );
      }
    });
  }

  private emitEvent(event: TaskEvent): void {
    for (const listener of this.eventListeners) {
      listener(event);
    }
  }

  /**
   * イベントリスナーを追加
   */
  onEvent(listener: (event: TaskEvent) => void): void {
    this.eventListeners.add(listener);
  }

  /**
   * イベントリスナーを削除
   */
  offEvent(listener: (event: TaskEvent) => void): void {
    this.eventListeners.delete(listener);
  }

  /**
   * タスクIDでタスクを取得
   */
  async getTaskById(taskId: string): Promise<HumanTask | null> {
    return this.tasks.get(taskId) || null;
  }

  /**
   * タスクを再割当
   */
  async reassignTask(taskId: string, newAssignee: string): Promise<void> {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    const oldAssignee = task.assignee;
    task.assignee = newAssignee;
    task.status = 'reserved'; // 再割当時はステータスをリセット
    task.claimedBy = undefined;
    task.claimedAt = undefined;

    // コメントを追加
    if (oldAssignee) {
      this.addComment(taskId, 'system', `Task reassigned from ${oldAssignee} to ${newAssignee}`);
    } else {
      this.addComment(taskId, 'system', `Task assigned to ${newAssignee}`);
    }

    this.emitEvent({
      type: 'task.reassigned',
      taskId,
      processId: task.processId,
      instanceId: task.instanceId,
      oldAssignee,
      newAssignee,
      timestamp: new Date(),
    });
  }

  /**
   * SLA違反を取得
   */
  getSlaViolations(): Array<{ taskId: string; violation: 'warning' | 'breach' }> {
    const violations: Array<{ taskId: string; violation: 'warning' | 'breach' }> = [];
    const now = Date.now();

    for (const [taskId, sla] of this.slas) {
      if (sla.breachTime && now > sla.breachTime.getTime()) {
        violations.push({ taskId, violation: 'breach' });
      } else if (sla.warningTime && now > sla.warningTime.getTime()) {
        violations.push({ taskId, violation: 'warning' });
      }
    }

    return violations;
  }
}
