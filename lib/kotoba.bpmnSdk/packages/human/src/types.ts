// Merkle DAG: human_task_types
// Human Task Management Types

export interface HumanTask {
  id: string;
  processId: string;
  instanceId: string;
  activityId: string;
  name: string;
  description?: string;
  priority?: number;
  dueDate?: Date;
  assignee?: string;
  claimedBy?: string;
  candidateUsers?: string[];
  candidateGroups?: string[];
  status: TaskStatus;
  createdAt: Date;
  claimedAt?: Date;
  completedAt?: Date;
  variables?: Record<string, any>;
  outcome?: Record<string, any>;
  formKey?: string;
  formData?: Record<string, any>;
  comments?: TaskComment[];
  attachments?: TaskAttachment[];
}

export type TaskStatus =
  | 'created'    // 作成済み
  | 'ready'      // 実行可能
  | 'reserved'   // 予約済み（誰かに割り当て済み）
  | 'in_progress' // 進行中
  | 'suspended'  // 一時停止
  | 'completed'  // 完了
  | 'failed'     // 失敗
  | 'error'      // エラー
  | 'exited';    // 終了

export interface TaskComment {
  id: string;
  userId: string;
  message: string;
  timestamp: Date;
  type?: 'comment' | 'system';
}

export interface TaskAttachment {
  id: string;
  name: string;
  description?: string;
  url: string;
  type: string;
  size: number;
  userId: string;
  timestamp: Date;
}

export interface TaskAssignment {
  taskId: string;
  assignee: string;
  assignedBy: string;
  assignedAt: Date;
  reason?: string;
}

export interface TaskSLA {
  taskId: string;
  slaDefinition: SLADefinition;
  startTime: Date;
  endTime?: Date;
  breached: boolean;
  breachedAt?: Date;
  breachTime?: Date;
  warningTime?: Date;
  warningThreshold?: number; // パーセント
  escalationActions?: EscalationAction[];
}

export interface SLADefinition {
  name: string;
  duration: number; // ミリ秒
  businessHours?: BusinessHours;
  calendarId?: string;
}

export interface BusinessHours {
  timezone: string;
  workingDays: number[]; // 0=日曜日, 1=月曜日, ...
  workingHours: {
    start: string; // HH:MM
    end: string;   // HH:MM
  };
}

export interface EscalationAction {
  id: string;
  type: 'reassign' | 'notify' | 'escalate';
  trigger: 'warning' | 'breach';
  delay?: number; // ミリ秒
  targetUsers?: string[];
  targetGroups?: string[];
  message?: string;
}

export interface TaskEvent {
  type: TaskEventType;
  taskId: string;
  processId: string;
  instanceId: string;
  userId?: string;
  timestamp: Date;
  data?: any;
  oldAssignee?: string;
  newAssignee?: string;
}

export type TaskEventType =
  | 'task.created'
  | 'task.assigned'
  | 'task.claimed'
  | 'task.unclaimed'
  | 'task.reassigned'
  | 'task.completed'
  | 'task.failed'
  | 'task.suspended'
  | 'task.resumed'
  | 'task.escalated'
  | 'task.sla.warning'
  | 'task.sla.breached'
  | 'task.comment.added'
  | 'task.attachment.added';
