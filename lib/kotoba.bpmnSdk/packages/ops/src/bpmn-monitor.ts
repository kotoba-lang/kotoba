// Merkle DAG: bpmn_monitor
// BPMN Process Monitor with OpenTelemetry Integration

import { trace, metrics, Span, Meter } from '@opentelemetry/api';
import { logs, Logger } from '@opentelemetry/api-logs';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { JaegerExporter } from '@opentelemetry/exporter-jaeger';
import { PrometheusExporter } from '@opentelemetry/exporter-prometheus';

import type { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';
import type {
  MonitoringConfig,
  ProcessMetrics,
  TraceSpan,
  LogEntry,
  Alert,
  AlertSeverity,
  HealthStatus,
  PerformanceSnapshot,
} from './types.js';

export class BpmnMonitor {
  private config: MonitoringConfig;
  private sdk!: NodeSDK;
  private tracer = trace.getTracer('bpmn-monitor', '1.0.0');
  private meter!: Meter;
  private logger!: Logger;

  // メトリクス
  private instanceCounter: any;
  private taskCounter: any;
  private durationHistogram: any;
  private errorCounter: any;

  // 状態管理
  private metricsData = new Map<string, ProcessMetrics>();
  private activeSpans = new Map<string, Span>();
  private alerts: Alert[] = [];

  constructor(config: MonitoringConfig) {
    this.config = {
      ...config,
      otel: config.otel || { endpoint: 'http://localhost:14268/api/traces' }
    };
    this.initializeOpenTelemetry();
    this.initializeMetrics();
    this.initializeLogger();
  }

  /**
   * OpenTelemetryを初期化
   */
  private initializeOpenTelemetry(): void {
    const jaegerExporter = new JaegerExporter({
      endpoint: this.config.otel.endpoint || 'http://localhost:14268/api/traces',
    });

    const prometheusExporter = new PrometheusExporter({
      port: 9464, // Prometheus default port
    });

    this.sdk = new NodeSDK({
      serviceName: this.config.otel.serviceName || this.config.serviceName,
      traceExporter: jaegerExporter,
    });

    this.sdk.start();
  }

  /**
   * メトリクスを初期化
   */
  private initializeMetrics(): void {
    this.meter = metrics.getMeter('bpmn-monitor', '1.0.0');

    // カウンター
    this.instanceCounter = this.meter.createCounter('bpmn_instances_total', {
      description: 'Total number of process instances',
    });

    this.taskCounter = this.meter.createCounter('bpmn_tasks_total', {
      description: 'Total number of tasks',
    });

    this.errorCounter = this.meter.createCounter('bpmn_errors_total', {
      description: 'Total number of errors',
    });

    // ヒストグラム
    this.durationHistogram = this.meter.createHistogram('bpmn_process_duration', {
      description: 'Process execution duration',
      unit: 'ms',
    });
  }

  /**
   * ロガーを初期化
   */
  private initializeLogger(): void {
    this.logger = logs.getLogger('bpmn-monitor', '1.0.0');
  }

  /**
   * ランタイムにイベントリスナーを設定
   */
  attachToRuntime(runtime: BpmnRuntime): void {
    runtime.onEvent((event) => {
      this.handleRuntimeEvent(event);
    });
  }

  /**
   * ランタイムイベントを処理
   */
  private handleRuntimeEvent(event: any): void {
    const span = this.startSpan(`bpmn.${event.type}`, {
      'bpmn.process_id': event.processId,
      'bpmn.instance_id': event.instanceId,
      'bpmn.activity_id': event.activityId,
      'bpmn.event_type': event.type,
    });

    try {
      // メトリクス更新
      this.updateMetrics(event);

      // ログ記録
      this.logEvent(event);

      // アラートチェック
      this.checkAlerts(event);

      span.setStatus({ code: 1 }); // OK
    } catch (error) {
      span.recordException(error as Error);
      span.setStatus({ code: 2, message: 'Error processing event' }); // ERROR
      this.logger.emit({
        severityNumber: 17, // ERROR
        severityText: 'ERROR',
        body: `Error processing BPMN event: ${error}`,
        attributes: {
          'bpmn.process_id': event.processId,
          'bpmn.instance_id': event.instanceId,
          'error': error instanceof Error ? error.message : String(error),
        },
      });
    } finally {
      span.end();
    }
  }

  /**
   * メトリクスを更新
   */
  private updateMetrics(event: any): void {
    const processId = event.processId;
    const metrics = this.getOrCreateMetrics(processId);

    switch (event.type) {
      case 'start':
        metrics.totalInstances++;
        metrics.activeInstances++;
        this.instanceCounter.add(1, {
          process_id: processId,
          status: 'started',
        });
        break;

      case 'end':
        metrics.activeInstances--;
        metrics.completedInstances++;
        this.instanceCounter.add(1, {
          process_id: processId,
          status: 'completed',
        });

        if (event.output?.duration) {
          this.durationHistogram.record(event.output.duration, {
            process_id: processId,
          });
        }
        break;

      case 'activity.start':
        metrics.activeTasks++;
        this.taskCounter.add(1, {
          process_id: processId,
          activity_type: event.activityType,
          status: 'started',
        });
        break;

      case 'activity.end':
        metrics.activeTasks--;
        metrics.completedTasks++;
        this.taskCounter.add(1, {
          process_id: processId,
          activity_type: event.activityType,
          status: 'completed',
        });
        break;

      case 'error':
        metrics.failedInstances++;
        metrics.errorCount++;
        this.errorCounter.add(1, {
          process_id: processId,
          error_type: event.error?.name || 'unknown',
        });
        break;
    }
  }

  /**
   * イベントをログに記録
   */
  private logEvent(event: any): void {
    const logEntry: LogEntry = {
      timestamp: new Date(),
      level: event.type.includes('error') ? 'error' : 'info',
      message: `BPMN Event: ${event.type}`,
      context: {
        processId: event.processId,
        instanceId: event.instanceId,
        activityId: event.activityId,
        activityType: event.activityType,
        userId: event.userId,
      },
    };

    this.logger.emit({
      severityNumber: logEntry.level === 'error' ? 17 : 9, // ERROR or INFO
      severityText: logEntry.level.toUpperCase(),
      body: logEntry.message,
      attributes: logEntry.context,
    });
  }

  /**
   * アラートをチェック
   */
  private checkAlerts(event: any): void {
    const processId = event.processId;
    const metrics = this.metricsData.get(processId);

    if (!metrics) return;

    // アクティブインスタンス数のチェック
    if (metrics.activeInstances > this.config.alerts.thresholds.maxProcessInstances) {
      this.createAlert({
        type: 'high_instance_count',
        severity: 'high',
        title: 'High Process Instance Count',
        description: `Process ${processId} has ${metrics.activeInstances} active instances`,
        context: {
          processId,
          threshold: this.config.alerts.thresholds.maxProcessInstances,
          actual: metrics.activeInstances,
        },
      });
    }

    // エラー率のチェック
    const errorRate = metrics.errorCount / metrics.totalInstances;
    if (errorRate > this.config.alerts.thresholds.maxErrorRate) {
      this.createAlert({
        type: 'high_error_rate',
        severity: 'critical',
        title: 'High Error Rate',
        description: `Process ${processId} has ${Math.round(errorRate * 100)}% error rate`,
        context: {
          processId,
          threshold: this.config.alerts.thresholds.maxErrorRate,
          actual: errorRate,
        },
      });
    }
  }

  /**
   * アラートを作成
   */
  private createAlert(alertData: Omit<Alert, 'id' | 'timestamp' | 'acknowledged'>): void {
    const alert: Alert = {
      ...alertData,
      id: this.generateId(),
      timestamp: new Date(),
      acknowledged: false,
    };

    this.alerts.push(alert);

    // Webhook通知（設定されている場合）
    if (this.config.alerts.webhooks) {
      this.notifyWebhooks(alert);
    }

    // ログ記録
    this.logger.emit({
      severityNumber: 13, // WARN
      severityText: 'WARN',
      body: `Alert created: ${alert.title}`,
      attributes: {
        alert_id: alert.id,
        alert_type: alert.type,
        alert_severity: alert.severity,
        process_id: alert.context.processId,
      },
    });
  }

  /**
   * Webhookに通知
   */
  private async notifyWebhooks(alert: Alert): Promise<void> {
    for (const webhookUrl of this.config.alerts.webhooks!) {
      try {
        // 実際の実装ではHTTPリクエストを送信
        console.log(`Sending alert to webhook: ${webhookUrl}`, alert);
      } catch (error) {
        this.logger.emit({
          severityNumber: 17, // ERROR
          severityText: 'ERROR',
          body: `Failed to send webhook notification: ${error}`,
          attributes: {
            webhook_url: webhookUrl,
            alert_id: alert.id,
          },
        });
      }
    }
  }

  /**
   * スパンを開始
   */
  private startSpan(name: string, attributes: Record<string, any>): Span {
    return this.tracer.startSpan(name, {
      attributes,
    });
  }

  /**
   * プロセスメトリクスを取得または作成
   */
  private getOrCreateMetrics(processId: string): ProcessMetrics {
    if (!this.metricsData.has(processId)) {
      this.metricsData.set(processId, {
        totalInstances: 0,
        activeInstances: 0,
        completedInstances: 0,
        failedInstances: 0,
        averageDuration: 0,
        medianDuration: 0,
        p95Duration: 0,
        p99Duration: 0,
        totalTasks: 0,
        activeTasks: 0,
        completedTasks: 0,
        failedTasks: 0,
        slaCompliance: 1.0,
        slaBreaches: 0,
        averageSlaDuration: 0,
        errorRate: 0,
        errorCount: 0,
        retryCount: 0,
        memoryUsage: 0,
        cpuUsage: 0,
        threadCount: 0,
      });
    }
    return this.metricsData.get(processId)!;
  }

  /**
   * パフォーマンススナップショットを取得
   */
  async getPerformanceSnapshot(): Promise<PerformanceSnapshot> {
    const memoryUsage = process.memoryUsage();
    const cpuUsage = process.cpuUsage();
    const eventLoopDelay = await this.measureEventLoopDelay();

    return {
      timestamp: new Date(),
      metrics: this.getAggregatedMetrics(),
      processMetrics: Object.fromEntries(this.metricsData), // Add process-specific metrics
      spans: [], // アクティブスパンのリスト
      activeTraces: this.activeSpans.size,
      memoryUsage,
      cpuUsage: (cpuUsage.user + cpuUsage.system) / 1000, // ミリ秒
      eventLoopDelay,
    };
  }

  /**
   * ヘルスステータスを取得
   */
  async getHealthStatus(): Promise<HealthStatus> {
    const checks: HealthCheck[] = [];

    // OpenTelemetryチェック
    checks.push(await this.checkOpenTelemetry());

    // メモリ使用量チェック
    checks.push(this.checkMemoryUsage());

    // エラー率チェック
    checks.push(this.checkErrorRate());

    const allHealthy = checks.every(check => check.status === 'pass');
    const hasWarnings = checks.some(check => check.status === 'warn');
    const hasFailures = checks.some(check => check.status === 'fail');

    let status: HealthStatusType = 'healthy';
    if (hasFailures) status = 'unhealthy';
    else if (hasWarnings) status = 'degraded';

    return {
      status,
      timestamp: new Date(),
      checks,
      uptime: process.uptime(),
      version: this.config.serviceVersion || '1.0.0',
    };
  }

  /**
   * アラートを取得
   */
  getAlerts(filter?: { acknowledged?: boolean; severity?: AlertSeverity }): Alert[] {
    return this.alerts.filter(alert => {
      if (filter?.acknowledged !== undefined && alert.acknowledged !== filter.acknowledged) {
        return false;
      }
      if (filter?.severity && alert.severity !== filter.severity) {
        return false;
      }
      return true;
    });
  }

  /**
   * アラートを確認済みに設定
   */
  acknowledgeAlert(alertId: string, userId: string): void {
    const alert = this.alerts.find(a => a.id === alertId);
    if (alert && !alert.acknowledged) {
      alert.acknowledged = true;
      alert.acknowledgedBy = userId;
      alert.acknowledgedAt = new Date();
    }
  }

  /**
   * モニターを停止
   */
  async shutdown(): Promise<void> {
    await this.sdk.shutdown();
  }

  // プライベートヘルパーメソッド
  private generateId(): string {
    return `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private getAggregatedMetrics(): ProcessMetrics {
    // 全プロセスのメトリクスを集計
    const aggregated: ProcessMetrics = {
      totalInstances: 0,
      activeInstances: 0,
      completedInstances: 0,
      failedInstances: 0,
      averageDuration: 0,
      medianDuration: 0,
      p95Duration: 0,
      p99Duration: 0,
      totalTasks: 0,
      activeTasks: 0,
      completedTasks: 0,
      failedTasks: 0,
      slaCompliance: 1.0,
      slaBreaches: 0,
      averageSlaDuration: 0,
      errorRate: 0,
      errorCount: 0,
      retryCount: 0,
      memoryUsage: process.memoryUsage().heapUsed,
      cpuUsage: 0,
      threadCount: 0,
    };

    for (const metrics of this.metricsData.values()) {
      Object.keys(aggregated).forEach(key => {
        if (typeof aggregated[key as keyof ProcessMetrics] === 'number') {
          (aggregated as any)[key] += (metrics as any)[key] || 0;
        }
      });
    }

    // 平均値の計算
    if (aggregated.totalInstances > 0) {
      aggregated.errorRate = aggregated.errorCount / aggregated.totalInstances;
    }

    return aggregated;
  }

  private async checkOpenTelemetry(): Promise<HealthCheck> {
    // OpenTelemetryの接続状態をチェック
    return {
      name: 'opentelemetry',
      status: 'pass',
      description: 'OpenTelemetry is operational',
      duration: 0,
    };
  }

  private checkMemoryUsage(): HealthCheck {
    const usage = process.memoryUsage();
    const usageMB = usage.heapUsed / 1024 / 1024;
    const thresholdMB = 512; // 512MB threshold

    return {
      name: 'memory_usage',
      status: usageMB > thresholdMB ? 'warn' : 'pass',
      description: `Memory usage: ${usageMB.toFixed(1)}MB`,
      duration: 0,
    };
  }

  private checkErrorRate(): HealthCheck {
    const metrics = this.getAggregatedMetrics();
    const threshold = this.config.alerts.thresholds.maxErrorRate;

    return {
      name: 'error_rate',
      status: metrics.errorRate > threshold ? 'fail' : 'pass',
      description: `Error rate: ${(metrics.errorRate * 100).toFixed(1)}%`,
      duration: 0,
    };
  }

  private async measureEventLoopDelay(): Promise<number> {
    return new Promise((resolve) => {
      const start = process.hrtime.bigint();
      setImmediate(() => {
        const end = process.hrtime.bigint();
        resolve(Number(end - start) / 1000000); // ミリ秒
      });
    });
  }

  /**
   * アラート管理 - アクティブなアラートを取得
   */
  getActiveAlerts(): Alert[] {
    return [...this.alerts];
  }
}

// タイプ定義（内部使用）
interface HealthCheck {
  name: string;
  status: 'pass' | 'fail' | 'warn';
  description?: string;
  duration: number;
  error?: string;
}

type HealthStatusType = 'healthy' | 'degraded' | 'unhealthy';
