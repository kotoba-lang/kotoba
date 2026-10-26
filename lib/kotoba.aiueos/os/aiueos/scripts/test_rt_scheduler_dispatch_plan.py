import pathlib
import unittest


COUNT = 16
STRIDE = 16
UNUSED, READY, RUNNING, BLOCKED = range(4)
FIFO, RR = range(2)


def table(*tasks):
    data = bytearray(COUNT * STRIDE)
    for slot, task in enumerate(tasks):
        base = slot * STRIDE
        state, priority, policy, budget, deadline, sequence = task
        data[base:base + 7] = bytes(
            [state, priority, priority, policy, budget, deadline, sequence]
        )
    return data


def plan(data, current, quantum_expired=False):
    ready = []
    for slot in range(COUNT):
        base = slot * STRIDE
        if data[base] == READY and data[base + 4] and data[base + 5]:
            ready.append((data[base + 2], data[base + 6], slot))
    best_priority, _, best = min(ready, default=(255, 255, 255))
    base = current * STRIDE
    current_state = data[base]
    current_priority = data[base + 2]
    current_policy = data[base + 3]
    budget = data[base + 4]
    deadline = data[base + 5]
    current_eligible = current_state == RUNNING and budget > 0 and deadline > 0
    higher = best != 255 and current_eligible and best_priority < current_priority
    rotate = (best != 255 and current_eligible
              and best_priority == current_priority
              and current_policy == RR and quantum_expired)
    selected = best if not current_eligible or higher or rotate else current
    if selected == 255:
        return 0
    selected_priority = data[selected * STRIDE + 2]
    return ((selected + 1)
            | ((selected != current) << 8)
            | (higher << 9)
            | (rotate << 10)
            | ((current_state == RUNNING and budget == 0) << 11)
            | ((current_state == RUNNING and deadline == 0) << 12)
            | (selected_priority << 16))


class RtSchedulerPlanTest(unittest.TestCase):
    def test_higher_priority_ready_task_preempts_immediately(self):
        data = table(
            (RUNNING, 20, FIFO, 10, 10, 1),
            (READY, 5, FIFO, 10, 10, 2),
        )
        recipe = plan(data, 0)
        self.assertEqual(2, recipe & 0xff)
        self.assertTrue(recipe & (1 << 8))
        self.assertTrue(recipe & (1 << 9))

    def test_fifo_current_continues_at_equal_priority(self):
        data = table(
            (RUNNING, 5, FIFO, 10, 10, 1),
            (READY, 5, FIFO, 10, 10, 2),
        )
        self.assertEqual(1, plan(data, 0, quantum_expired=True) & 0xff)

    def test_round_robin_rotates_only_when_quantum_expires(self):
        data = table(
            (RUNNING, 5, RR, 10, 10, 1),
            (READY, 5, RR, 10, 10, 2),
        )
        self.assertEqual(1, plan(data, 0) & 0xff)
        recipe = plan(data, 0, quantum_expired=True)
        self.assertEqual(2, recipe & 0xff)
        self.assertTrue(recipe & (1 << 10))

    def test_budget_exhaustion_makes_running_task_ineligible(self):
        data = table(
            (RUNNING, 1, FIFO, 0, 10, 1),
            (READY, 20, FIFO, 10, 10, 2),
        )
        recipe = plan(data, 0)
        self.assertEqual(2, recipe & 0xff)
        self.assertTrue(recipe & (1 << 11))

    def test_effective_priority_is_scheduler_authority(self):
        data = table(
            (RUNNING, 20, FIFO, 10, 10, 1),
            (READY, 5, FIFO, 10, 10, 2),
        )
        data[2] = 3  # priority-ceiling boost of the lock holder
        self.assertEqual(1, plan(data, 0) & 0xff)

    def test_kotoba_source_keeps_native_boundary(self):
        source = pathlib.Path(__file__).parents[1] / "kotoba" / "rt-scheduler-dispatch-plan.kotoba"
        text = source.read_text()
        self.assertIn("defn aiueos-scheduler-dispatch-plan", text)
        for forbidden in ("linux", "java", "jvm", "pthread", "malloc"):
            self.assertNotIn(forbidden, text.lower())

    def test_linked_policy_has_distinct_kernel_symbol_and_digest(self):
        kotoba = pathlib.Path(__file__).parents[1] / "kotoba"
        linkage = (kotoba / "rt-scheduler-dispatch-plan.linkage.edn").read_text()
        self.assertTrue((kotoba / "rt-scheduler-dispatch-plan.o").is_file())
        self.assertIn('"kotoba_aiueos_rt_scheduler_plan"', linkage)
        self.assertIn(
            '"5ca14a7962a63c54ae33af451bd06a994f7fce6c1a3392615bd5a40c29d3372b"',
            linkage,
        )


if __name__ == "__main__":
    unittest.main()
