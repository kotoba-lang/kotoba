// Jest setup for E2E integration tests

// Global test setup
beforeAll(async () => {
  // Setup any global test configuration
  console.log('🔧 Setting up E2E integration tests...');
});

afterAll(async () => {
  // Cleanup after all tests
  console.log('🧹 Cleaning up E2E integration tests...');
});

// Custom matchers
expect.extend({
  toBeValidBpmnProcess(received) {
    const pass = received &&
      typeof received === 'object' &&
      received.definitions &&
      received.definitions.processes &&
      received.definitions.processes.length > 0;

    return {
      message: () => `Expected ${received} to be a valid BPMN process`,
      pass,
    };
  },

  toHaveValidTasks(received) {
    const pass = received &&
      Array.isArray(received) &&
      received.every(task => task.type === 'task' && task.id && task.name);

    return {
      message: () => `Expected ${received} to contain valid tasks`,
      pass,
    };
  },

  toBeCompletedTask(received) {
    const pass = received &&
      received.status === 'completed' &&
      received.completedAt instanceof Date;

    return {
      message: () => `Expected task to be completed`,
      pass,
    };
  }
});

// Declare custom matchers
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeValidBpmnProcess(): R;
      toHaveValidTasks(): R;
      toBeCompletedTask(): R;
    }
  }
}
