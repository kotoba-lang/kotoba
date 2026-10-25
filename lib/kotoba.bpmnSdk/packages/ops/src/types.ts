// Merkle DAG: ops_types
// Operations and Monitoring Types

export interface MonitoringConfig {
  serviceName: string;
  serviceVersion?: string;
  environment?: string;

  // OpenTelemetry設定
  otel: {
    endpoint?: string;
    headers?: Record<string, string>;
    serviceName?: string;
    serviceVersion?: string;
  };

  // メトリクス設定
  metrics: {
    enabled: boolean;
    interval: number; // ミリ秒
    prefix?: string;
  };

  // ログ設定
  logging: {
    level: LogLevel;
    format: LogFormat;
    destination: LogDestination;
  };

  // アラート設定
  alerts: {
    enabled: boolean;
    thresholds: AlertThresholds;
    webhooks?: string[];
  };
}

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';
export type LogFormat = 'json' | 'text' | 'structured';
export type LogDestination = 'console' | 'file' | 'remote';

export interface AlertThresholds {
  maxProcessInstances: number;
  maxActiveTasks: number;
  maxErrorRate: number; // 0-1
  maxAverageDuration: number; // ミリ秒
  slaBreachRate: number; // 0-1
}

export interface ProcessMetrics {
  // インスタンスメトリクス
  totalInstances: number;
  activeInstances: number;
  completedInstances: number;
  failedInstances: number;

  // パフォーマンスメトリクス
  averageDuration: number;
  medianDuration: number;
  p95Duration: number;
  p99Duration: number;

  // タスクメトリクス
  totalTasks: number;
  activeTasks: number;
  completedTasks: number;
  failedTasks: number;

  // SLAメトリクス
  slaCompliance: number; // 0-1
  slaBreaches: number;
  averageSlaDuration: number;

  // エラーメトリクス
  errorRate: number; // 0-1
  errorCount: number;
  retryCount: number;

  // リソースメトリクス
  memoryUsage: number;
  cpuUsage: number;
  threadCount: number;
}

export interface TraceSpan {
  id: string;
  parentId?: string;
  name: string;
  startTime: Date;
  endTime?: Date;
  duration?: number;
  attributes: Record<string, any>;
  events: SpanEvent[];
  status: SpanStatus;
}

export interface SpanEvent {
  name: string;
  timestamp: Date;
  attributes: Record<string, any>;
}

export type SpanStatus = 'ok' | 'error' | 'unset';

export interface LogEntry {
  timestamp: Date;
  level: LogLevel;
  message: string;
  context: LogContext;
  error?: Error;
  stack?: string;
}

export interface LogContext {
  processId?: string;
  instanceId?: string;
  activityId?: string;
  userId?: string;
  sessionId?: string;
  requestId?: string;
  correlationId?: string;
  [key: string]: any;
}

export interface Alert {
  id: string;
  type: AlertType;
  severity: AlertSeverity;
  title: string;
  description: string;
  context: AlertContext;
  timestamp: Date;
  acknowledged: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: Date;
}

export type AlertType =
  | 'high_instance_count'
  | 'high_error_rate'
  | 'sla_breach'
  | 'long_running_process'
  | 'system_resource'
  | 'task_timeout'
  | 'process_failure';

export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface AlertContext {
  processId?: string;
  instanceId?: string;
  threshold: number;
  actual: number;
  metadata?: Record<string, any>;
}

export interface HealthStatus {
  status: HealthStatusType;
  timestamp: Date;
  checks: HealthCheck[];
  uptime: number;
  version: string;
}

export type HealthStatusType = 'healthy' | 'degraded' | 'unhealthy';

export interface HealthCheck {
  name: string;
  status: 'pass' | 'fail' | 'warn';
  description?: string;
  duration: number;
  error?: string;
}

export interface PerformanceSnapshot {
  timestamp: Date;
  metrics: ProcessMetrics;
  processMetrics?: Record<string, ProcessMetrics>;
  spans: TraceSpan[];
  activeTraces: number;
  memoryUsage: NodeJS.MemoryUsage;
  cpuUsage: number;
  eventLoopDelay: number;
}
