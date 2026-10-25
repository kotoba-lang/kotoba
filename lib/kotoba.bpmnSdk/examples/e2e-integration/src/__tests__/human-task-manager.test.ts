// Human Task Manager Integration Tests

import { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';
import { HumanTaskManager } from '@etzhayyim/bpmn-sdk-human';
import { flow } from '@etzhayyim/bpmn-sdk-dsl';

describe.skip('HumanTaskManager Integration', () => {
  let runtime: BpmnRuntime;
  let taskManager: HumanTaskManager;
  let testProcess: any;

  beforeEach(async () => {
    runtime = new BpmnRuntime();
    taskManager = new HumanTaskManager(runtime);

    // Create a simple process with user task
    testProcess = flow('TestProcess', f => {
      f.process('TestProcess', p => {
        p.startEvent('StartEvent');
        p.userTask('UserTask1');
        p.endEvent('EndEvent');
        p.sequenceFlow('StartEvent', 'UserTask1');
        p.sequenceFlow('UserTask1', 'EndEvent');
      });
    });
  });

  afterEach(async () => {
    // Cleanup
  });

  test('should create and manage human tasks', async () => {
    // Deploy process
    const processId = await runtime.deployProcess(testProcess);

    // Create a human task manually (normally done by runtime events)
    const task = await taskManager.createTask(
      processId,
      'test-instance-1',
      'UserTask1',
      {
        name: 'Test User Task',
        description: 'A test human task',
        priority: 1,
        assignee: 'test@example.com',
        dueDate: new Date(Date.now() + 24 * 60 * 60 * 1000)
      }
    );

    expect(task).toBeDefined();
    expect(task.id).toBeDefined();
    expect(task.name).toBe('Test User Task');
    expect(task.status).toBe('reserved'); // Assigned directly
    expect(task.assignee).toBe('test@example.com');
  });

  test('should handle task lifecycle', async () => {
    const processId = await runtime.deployProcess(testProcess);

    const task = await taskManager.createTask(
      processId,
      'test-instance-2',
      'UserTask1',
      {
        name: 'Lifecycle Test Task',
        candidateUsers: ['user1@example.com', 'user2@example.com']
      }
    );

    expect(task.status).toBe('ready'); // Has candidates, not assigned

    // Claim task
    await taskManager.claimTask(task.id, 'user1@example.com');
    const claimedTask = taskManager.getTask(task.id);
    expect(claimedTask?.status).toBe('in_progress');
    expect(claimedTask?.assignee).toBe('user1@example.com');

    // Complete task
    await taskManager.completeTask(task.id, 'user1@example.com', {
      result: 'completed',
      outputData: { approved: true }
    });

    const completedTask = taskManager.getTask(task.id);
    expect(completedTask?.status).toBe('completed');
    expect(completedTask?.completedAt).toBeInstanceOf(Date);
  });

  test('should handle task assignment', async () => {
    const processId = await runtime.deployProcess(testProcess);

    const task = await taskManager.createTask(
      processId,
      'test-instance-3',
      'UserTask1',
      {
        name: 'Assignment Test Task',
        candidateUsers: ['user1@example.com']
      }
    );

    // Assign to specific user
    await taskManager.assignTask(task.id, 'user2@example.com', 'admin@example.com');

    const assignedTask = taskManager.getTask(task.id);
    expect(assignedTask?.assignee).toBe('user2@example.com');
    expect(assignedTask?.status).toBe('reserved');
  });

  test('should handle task comments', async () => {
    const processId = await runtime.deployProcess(testProcess);

    const task = await taskManager.createTask(
      processId,
      'test-instance-4',
      'UserTask1',
      {
        name: 'Comment Test Task'
      }
    );

    // Add comment
    const comment = await taskManager.addComment(
      task.id,
      'user1@example.com',
      'This is a test comment'
    );

    expect(comment.id).toBeDefined();
    expect(comment.message).toBe('This is a test comment');
    expect(comment.userId).toBe('user1@example.com');
    expect(comment.timestamp).toBeInstanceOf(Date);

    const updatedTask = taskManager.getTask(task.id);
    expect(updatedTask?.comments).toHaveLength(1);
    expect(updatedTask?.comments?.[0].message).toBe('This is a test comment');
  });

  test('should filter tasks by user', async () => {
    const processId = await runtime.deployProcess(testProcess);

    // Create tasks for different users
    await taskManager.createTask(processId, 'instance-1', 'UserTask1', {
      name: 'Task 1',
      assignee: 'user1@example.com'
    });

    await taskManager.createTask(processId, 'instance-2', 'UserTask1', {
      name: 'Task 2',
      candidateUsers: ['user1@example.com', 'user2@example.com']
    });

    await taskManager.createTask(processId, 'instance-3', 'UserTask1', {
      name: 'Task 3',
      candidateGroups: ['group1']
    });

    const user1Tasks = taskManager.getTasksForUser('user1@example.com');
    expect(user1Tasks).toHaveLength(2); // assigned + candidate

    const user2Tasks = taskManager.getTasksForUser('user2@example.com');
    expect(user2Tasks).toHaveLength(1); // only candidate
  });
});
