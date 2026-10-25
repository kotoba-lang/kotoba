// Merkle DAG: testing_types
// Property-based Testing Types

export interface TestResult {
  success: boolean;
  property: string;
  testCases: number;
  passed: number;
  failed: number;
  errors: TestError[];
  coverage: TestCoverage;
  duration: number;
}

export interface TestError {
  case: number;
  input: any;
  expected: any;
  actual: any;
  message: string;
  stack?: string;
}

export interface TestCoverage {
  elements: number;
  coveredElements: number;
  paths: number;
  coveredPaths: number;
  conditions: number;
  coveredConditions: number;
  branches: number;
  coveredBranches: number;
}

export interface TestOptions {
  maxTestCases?: number;
  timeout?: number;
  seed?: number;
  verbose?: boolean;
  shrink?: boolean;
}

export interface PropertyTest {
  name: string;
  description: string;
  generator: () => any;
  property: (input: any) => Promise<boolean> | boolean;
  options?: TestOptions;
}

export type ProcessProperty =
  | 'noDeadEnds'
  | 'allReachable'
  | 'gatewayConsistency'
  | 'properTermination'
  | 'noCycles'
  | 'validExecution'
  | 'dataFlow'
  | 'timingConstraints'
  | 'resourceAvailability'
  | 'exceptionHandling';

export interface ExecutionScenario {
  id: string;
  description: string;
  inputs: Record<string, any>;
  expectedPath: string[];
  expectedOutputs: Record<string, any>;
  timeout?: number;
}

export interface ScenarioResult {
  scenario: ExecutionScenario;
  success: boolean;
  actualPath: string[];
  actualOutputs: Record<string, any>;
  duration: number;
  error?: string;
}

export interface TestSuite {
  name: string;
  description: string;
  properties: PropertyTest[];
  scenarios: ExecutionScenario[];
  setup?: () => Promise<void>;
  teardown?: () => Promise<void>;
}

export interface TestRunner {
  runPropertyTest(property: PropertyTest): Promise<TestResult>;
  runScenarioTest(scenario: ExecutionScenario): Promise<ScenarioResult>;
  runTestSuite(suite: TestSuite): Promise<{
    properties: TestResult[];
    scenarios: ScenarioResult[];
    summary: {
      total: number;
      passed: number;
      failed: number;
      coverage: TestCoverage;
    };
  }>;
}

export interface DataGenerator<T = any> {
  generate(): T;
  shrink(value: T): T[];
  isValid(value: T): boolean;
}

export interface ExecutionTrace {
  processId: string;
  instanceId: string;
  events: TraceEvent[];
  startTime: Date;
  endTime?: Date;
  variables: Record<string, any>;
  path: string[];
}

export interface TraceEvent {
  type: string;
  elementId: string;
  timestamp: Date;
  data?: any;
}
