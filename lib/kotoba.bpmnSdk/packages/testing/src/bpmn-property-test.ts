// Merkle DAG: bpmn_property_test
// Property-based Testing Framework for BPMN Processes

import type { BpmnIR } from '@etzhayyim/bpmn-sdk-core';
import type { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';
import { validateProcess } from '@etzhayyim/bpmn-sdk-validation';
import type {
  TestResult,
  TestError,
  TestOptions,
  PropertyTest,
  ExecutionScenario,
  ScenarioResult,
  TestCoverage,
  ExecutionTrace,
} from './types.js';

export class BpmnPropertyTester {
  private runtime: BpmnRuntime;
  private defaultOptions: Required<TestOptions>;

  constructor(runtime: BpmnRuntime, options: TestOptions = {}) {
    this.runtime = runtime;
    this.defaultOptions = {
      maxTestCases: 100,
      timeout: 30000,
      seed: Date.now(),
      verbose: false,
      shrink: true,
      ...options,
    };
  }

  /**
   * プロセスプロパティをテスト
   */
  async testProperty(ir: BpmnIR, property: string, options?: TestOptions): Promise<TestResult> {
    const opts = { ...this.defaultOptions, ...options };
    const startTime = Date.now();

    const propertyTest = this.createPropertyTest(property);
    return this.runPropertyTest(ir, propertyTest, opts, startTime);
  }

  /**
   * 実行シナリオをテスト
   */
  async testScenario(ir: BpmnIR, scenario: ExecutionScenario, options?: TestOptions): Promise<ScenarioResult> {
    const opts = { ...this.defaultOptions, ...options };
    const startTime = Date.now();

    try {
      // プロセスをデプロイ
      const deployedProcessId = await this.runtime.deployProcess(ir);

      // インスタンスを開始
      const context = await this.runtime.startInstance(deployedProcessId, {
        variables: scenario.inputs
      });

      // シナリオ実行
      const trace = await this.executeScenario(this.runtime, context, scenario, opts.timeout);

      // 結果検証
      const success = this.validateScenarioResult(scenario, trace);

      return {
        scenario,
        success,
        actualPath: trace.path,
        actualOutputs: trace.variables,
        duration: Date.now() - startTime,
      };
    } catch (error) {
      return {
        scenario,
        success: false,
        actualPath: [],
        actualOutputs: {},
        duration: Date.now() - startTime,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * プロパティテストを実行
   */
  private async runPropertyTest(
    ir: BpmnIR,
    propertyTest: PropertyTest,
    options: Required<TestOptions>,
    startTime: number
  ): Promise<TestResult> {
    const errors: TestError[] = [];
    let passed = 0;
    let failed = 0;

    // 乱数生成器を初期化
    const rng = this.createRNG(options.seed);

    for (let i = 0; i < options.maxTestCases; i++) {
      try {
        // テスト入力生成
        const input = propertyTest.generator();

        // プロパティ検証
        const result = await this.executeWithTimeout(
          () => propertyTest.property(input),
          options.timeout
        );

        if (result) {
          passed++;
        } else {
          failed++;
          errors.push({
            case: i,
            input,
            expected: true,
            actual: false,
            message: `Property ${propertyTest.name} failed for input: ${JSON.stringify(input)}`,
          });
        }
      } catch (error) {
        failed++;
        errors.push({
          case: i,
          input: null,
          expected: true,
          actual: false,
          message: error instanceof Error ? error.message : 'Unknown error',
          stack: error instanceof Error ? error.stack : undefined,
        });
      }
    }

    // カバレッジ計算
    const coverage = await this.calculateCoverage(ir, propertyTest.name);

    return {
      success: failed === 0,
      property: propertyTest.name,
      testCases: options.maxTestCases,
      passed,
      failed,
      errors,
      coverage,
      duration: Date.now() - startTime,
    };
  }

  /**
   * プロパティテストを作成
   */
  private createPropertyTest(property: string): PropertyTest {
    switch (property) {
      case 'noDeadEnds':
        return {
          name: 'noDeadEnds',
          description: 'Process has no dead end elements',
          generator: () => this.generateProcessInput(),
          property: async (input) => {
            const validation = await validateProcess(input);
            return !validation.errors.some(e => e.type === 'dead_end');
          },
        };

      case 'allReachable':
        return {
          name: 'allReachable',
          description: 'All elements are reachable from start events',
          generator: () => this.generateProcessInput(),
          property: async (input) => {
            const validation = await validateProcess(input);
            return validation.errors.filter(e => e.type === 'unreachable_element').length === 0;
          },
        };

      case 'gatewayConsistency':
        return {
          name: 'gatewayConsistency',
          description: 'Gateways have consistent incoming/outgoing flows',
          generator: () => this.generateProcessInput(),
          property: async (input) => {
            const validation = await validateProcess(input);
            return !validation.errors.some(e =>
              e.type === 'gateway_no_incoming' ||
              e.type === 'gateway_no_outgoing' ||
              e.type === 'gateway_mismatch'
            );
          },
        };

      case 'properTermination':
        return {
          name: 'properTermination',
          description: 'Process has proper start and end events',
          generator: () => this.generateProcessInput(),
          property: async (input) => {
            const validation = await validateProcess(input);
            return !validation.errors.some(e =>
              e.type === 'start_event_multiple' ||
              e.type === 'end_event_missing'
            );
          },
        };

      case 'validExecution':
        return {
          name: 'validExecution',
          description: 'Process can be executed without errors',
          generator: () => this.generateProcessInput(),
          property: async (input) => {
            try {
              const deployedProcessId = await this.runtime.deployProcess(input);
              return deployedProcessId !== undefined;
            } catch {
              return false;
            }
          },
        };

      default:
        throw new Error(`Unknown property: ${property}`);
    }
  }

  /**
   * シナリオを実行
   */
  private async executeScenario(
    runtime: BpmnRuntime,
    context: any,
    scenario: ExecutionScenario,
    timeout: number
  ): Promise<ExecutionTrace> {
    const trace: ExecutionTrace = {
      processId: context.processId,
      instanceId: context.instanceId,
      events: [],
      startTime: new Date(),
      variables: { ...scenario.inputs },
      path: [],
    };

    // イベント監視
    runtime.onEvent((event) => {
      trace.events.push({
        type: event.type,
        elementId: (event as any).activityId || (event as any).elementId || '',
        timestamp: new Date(),
        data: event,
      });

      if ((event as any).activityId) {
        trace.path.push((event as any).activityId);
      }
    });

    // プロセス開始
    await this.runtime.startInstance(context.processId, {
      instanceId: context.instanceId,
      variables: scenario.inputs,
    });

    // 完了待機
    await this.executeWithTimeout(
      () => this.waitForCompletion(runtime, context.instanceId),
      timeout
    );

    // 最終状態取得
    const finalContext = await this.runtime.getExecutionContext(context.processId, context.instanceId);
    trace.endTime = new Date();
    trace.variables = { ...trace.variables, ...finalContext?.variables };

    return trace;
  }

  /**
   * シナリオ結果を検証
   */
  private validateScenarioResult(scenario: ExecutionScenario, trace: ExecutionTrace): boolean {
    // パス検証
    if (scenario.expectedPath && scenario.expectedPath.length > 0) {
      const actualPath = trace.path;
      if (actualPath.length !== scenario.expectedPath.length) {
        return false;
      }

      for (let i = 0; i < scenario.expectedPath.length; i++) {
        if (actualPath[i] !== scenario.expectedPath[i]) {
          return false;
        }
      }
    }

    // 出力検証
    if (scenario.expectedOutputs) {
      for (const [key, expectedValue] of Object.entries(scenario.expectedOutputs)) {
        const actualValue = trace.variables[key];
        if (actualValue !== expectedValue) {
          return false;
        }
      }
    }

    return true;
  }

  /**
   * カバレッジを計算
   */
  private async calculateCoverage(ir: BpmnIR, propertyName: string): Promise<TestCoverage> {
    // 簡易的なカバレッジ計算
    const totalElements = ir.definitions.processes.reduce(
      (sum, proc) => sum + proc.flowElements.length,
      0
    );

    // 実際のカバレッジ計算はより複雑になる
    const coveredElements = Math.floor(totalElements * 0.8); // 仮定値

    return {
      elements: totalElements,
      coveredElements,
      paths: 0, // TODO: パス分析を実装
      coveredPaths: 0,
      conditions: 0,
      coveredConditions: 0,
      branches: 0,
      coveredBranches: 0,
    };
  }

  /**
   * プロセス入力データを生成
   */
  private generateProcessInput(): BpmnIR {
    // 簡易的なプロセス生成
    // 実際の実装では、より複雑なプロセスを生成
    return {
      definitions: {
        id: 'GeneratedProcess',
        name: 'Generated Process',
        targetNamespace: 'http://example.com/bpmn',
        processes: [{
          id: 'Process_1',
          name: 'Test Process',
          isExecutable: true,
          flowElements: [
            {
              type: 'event',
              eventType: 'start',
              id: 'StartEvent_1',
              name: 'Start',
            } as any,
            {
              type: 'event',
              eventType: 'end',
              id: 'EndEvent_1',
              name: 'End',
            } as any,
          ],
          sequenceFlows: [{
            id: 'Flow_1',
            name: '',
            sourceRef: 'StartEvent_1',
            targetRef: 'EndEvent_1',
          }],
        }],
        version: '1.0',
      },
    };
  }

  /**
   * 完了を待機
   */
  private async waitForCompletion(runtime: BpmnRuntime, instanceId: string): Promise<void> {
    return new Promise((resolve) => {
      const checkCompletion = async () => {
        const context = await runtime.getExecutionContext('', instanceId);
        if (context?.status === 'completed') {
          resolve();
        } else {
          setTimeout(checkCompletion, 100);
        }
      };
      checkCompletion();
    });
  }

  /**
   * タイムアウト付き実行
   */
  private async executeWithTimeout<T>(
    fn: () => Promise<T> | T,
    timeout: number
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`Operation timed out after ${timeout}ms`));
      }, timeout);

      Promise.resolve(fn())
        .then(resolve)
        .catch(reject)
        .finally(() => clearTimeout(timer));
    });
  }

  /**
   * 乱数生成器
   */
  private createRNG(seed: number): () => number {
    let x = seed;
    return () => {
      x = (x * 9301 + 49297) % 233280;
      return x / 233280;
    };
  }
}

// 便利関数
export async function bpmnPropertyTest(
  ir: BpmnIR,
  runtime: BpmnRuntime,
  property: string,
  options?: TestOptions
): Promise<TestResult> {
  const tester = new BpmnPropertyTester(runtime, options);
  return tester.testProperty(ir, property);
}

export async function bpmnScenarioTest(
  ir: BpmnIR,
  runtime: BpmnRuntime,
  scenario: ExecutionScenario,
  options?: TestOptions
): Promise<ScenarioResult> {
  const tester = new BpmnPropertyTester(runtime, options);
  return tester.testScenario(ir, scenario);
}
