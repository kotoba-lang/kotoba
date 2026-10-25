import { describe, it, expect, beforeEach } from 'vitest';
import { HumanTaskManager } from './human-task-manager.js';
import { BpmnRuntime } from '@etzhayyim/bpmn-sdk-runtime';

describe('@etzhayyim/bpmn-sdk-human', () => {
  let runtime: BpmnRuntime;
  let taskManager: HumanTaskManager;

  beforeEach(() => {
    runtime = new BpmnRuntime();
    taskManager = new HumanTaskManager(runtime);
  });

  describe('HumanTaskManager', () => {
    it('should instantiate correctly', () => {
      expect(taskManager).toBeDefined();
      expect(taskManager).toBeInstanceOf(HumanTaskManager);
    });

    describe('createTask()', () => {
      it('should create a human task', async () => {
        const taskData = {
          processId: 'process-1',
          instanceId: 'instance-1',
          activityId: 'activity-1',
          name: 'Review Document',
          description: 'Please review the attached document',
          assignee: 'user@example.com',
          priority: 1,
          dueDate: new Date(Date.now() + 24 * 60 * 60 * 1000),
          slaDefinition: {
            duration: 24 * 60 * 60 * 1000
          }
        };

        const task = await taskManager.createTask(
          taskData.processId,
          taskData.instanceId,
          taskData.activityId,
          taskData
        );

        expect(task).toBeDefined();
        expect(task.id).toBeDefined();
        expect(task.name).toBe(taskData.name);
        expect(task.assignee).toBe(taskData.assignee);
        expect(task.status).toBe('reserved');
        expect(task.createdAt).toBeInstanceOf(Date);
      });

      it('should create task with candidate users', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          {
            name: 'Review Task',
            candidateUsers: ['user1@example.com', 'user2@example.com']
          }
        );

        expect(task.candidateUsers).toEqual(['user1@example.com', 'user2@example.com']);
      });

      it('should create task with candidate groups', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          {
            name: 'Review Task',
            candidateGroups: ['reviewers', 'managers']
          }
        );

        expect(task.candidateGroups).toEqual(['reviewers', 'managers']);
      });
    });

    describe('claimTask()', () => {
      it('should claim a task for a user', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Test Task', assignee: 'user@example.com' }
        );

        await taskManager.claimTask(task.id, 'user@example.com');

        const updatedTask = await taskManager.getTaskById(task.id);
        expect(updatedTask?.status).toBe('in_progress');
        expect(updatedTask?.claimedBy).toBe('user@example.com');
        expect(updatedTask?.claimedAt).toBeInstanceOf(Date);
      });

      it('should throw error when claiming already claimed task', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Test Task', assignee: 'user@example.com' }
        );

        await taskManager.claimTask(task.id, 'user@example.com');

        await expect(taskManager.claimTask(task.id, 'other-user@example.com'))
          .rejects.toThrow('not claimable');
      });

      it('should throw error for non-existent task', async () => {
        await expect(taskManager.claimTask('non-existent', 'user@example.com'))
          .rejects.toThrow('Task');
      });
    });

    describe('completeTask()', () => {
      it('should complete a claimed task', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          {
            name: 'Test Task',
            assignee: 'user@example.com'
          }
        );

        await taskManager.claimTask(task.id, 'user@example.com');

        await taskManager.completeTask(task.id, 'user@example.com', {
          decision: 'approved',
          comments: 'Task completed successfully'
        });

        const updatedTask = await taskManager.getTaskById(task.id);
        expect(updatedTask?.status).toBe('completed');
        expect(updatedTask?.completedAt).toBeInstanceOf(Date);
        expect(updatedTask?.outcome).toEqual({
          decision: 'approved',
          comments: 'Task completed successfully'
        });
      });

      it('should throw error when completing unclaimed task', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Test Task' }
        );

        await expect(taskManager.completeTask(task.id, 'user@example.com', {}))
          .rejects.toThrow('Task');
      });

      it('should throw error when non-assignee tries to complete task', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Test Task', assignee: 'user@example.com' }
        );

        await taskManager.claimTask(task.id, 'user@example.com');

        await expect(taskManager.completeTask(task.id, 'other-user@example.com', {}))
          .rejects.toThrow('Task');
      });
    });

    describe('getTasksForUser()', () => {
      it('should return tasks assigned to user', async () => {
        await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Task 1', assignee: 'user@example.com' }
        );

        await taskManager.createTask(
          'process-2',
          'instance-2',
          'activity-2',
          { name: 'Task 2', assignee: 'user@example.com' }
        );

        await taskManager.createTask(
          'process-3',
          'instance-3',
          'activity-3',
          { name: 'Task 3', assignee: 'other-user@example.com' }
        );

        const userTasks = taskManager.getTasksForUser('user@example.com');

        expect(userTasks).toHaveLength(2);
        expect(userTasks.every(task => task.assignee === 'user@example.com')).toBe(true);
      });

      it('should return tasks for candidate user', async () => {
        await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          {
            name: 'Task 1',
            candidateUsers: ['user@example.com', 'user2@example.com']
          }
        );

        const userTasks = taskManager.getTasksForUser('user@example.com');

        expect(userTasks).toHaveLength(1);
        expect(userTasks[0].candidateUsers).toContain('user@example.com');
      });

      it('should return tasks for candidate group', async () => {
        await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          {
            name: 'Task 1',
            candidateGroups: ['reviewers', 'managers']
          }
        );

        const userTasks = taskManager.getTasksForUser('user@example.com', ['reviewers']);

        expect(userTasks).toHaveLength(1);
        expect(userTasks[0].candidateGroups).toContain('reviewers');
      });
    });

    describe('getTaskById()', () => {
      it('should return task by ID', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Test Task' }
        );

        const retrievedTask = await taskManager.getTaskById(task.id);

        expect(retrievedTask).toEqual(task);
      });

      it('should return null for non-existent task', async () => {
        const task = await taskManager.getTaskById('non-existent');

        expect(task).toBeNull();
      });
    });

    describe('reassignTask()', () => {
      it('should reassign task to another user', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Test Task', assignee: 'user1@example.com' }
        );

        await taskManager.reassignTask(task.id, 'user2@example.com');

        const updatedTask = await taskManager.getTaskById(task.id);
        expect(updatedTask?.assignee).toBe('user2@example.com');
        expect(updatedTask?.status).toBe('reserved'); // Reassignment resets status
      });
    });

    describe('Task Status Transitions', () => {
      it('should handle full task lifecycle', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          { name: 'Lifecycle Test', assignee: 'user@example.com' }
        );

        expect(task.status).toBe('reserved');

        await taskManager.claimTask(task.id, 'user@example.com');
        let updatedTask = await taskManager.getTaskById(task.id);
        expect(updatedTask?.status).toBe('in_progress');

        await taskManager.completeTask(task.id, 'user@example.com', {});
        updatedTask = await taskManager.getTaskById(task.id);
        expect(updatedTask?.status).toBe('completed');
      });
    });

    describe('SLA Management', () => {
      it('should track SLA violations', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          {
            name: 'SLA Test',
            assignee: 'user@example.com',
            slaDefinition: {
              duration: 1000 // 1 second
            }
          }
        );

        // Wait for SLA violation
        await new Promise(resolve => setTimeout(resolve, 1100));

        const violations = taskManager.getSlaViolations();
        expect(violations).toHaveLength(1);
        expect(violations[0].taskId).toBe(task.id);
      });

      it('should handle SLA compliance', async () => {
        const task = await taskManager.createTask(
          'process-1',
          'instance-1',
          'activity-1',
          {
            name: 'SLA Test',
            assignee: 'user@example.com',
            slaDefinition: {
              duration: 24 * 60 * 60 * 1000 // 24 hours
            }
          }
        );

        const violations = taskManager.getSlaViolations();
        expect(violations).toHaveLength(0);
      });
    });
  });
});
// @vitest-environment node
