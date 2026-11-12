#!/usr/bin/env python3
"""Negative controls for check-fp-state-probe.py, run against the serial excerpts committed beside the
JUN-855 evidence README (real logs) and tampered copies of them."""
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parents[2] / "90-docs/evidence/jun-855-fp-state-preemption-20261106/serial"
spec = importlib.util.spec_from_file_location("gate", HERE / "check-fp-state-probe.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def run(text, expect):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "serial.log"
        p.write_text(text)
        return gate.main(["--serial", str(p), "--expect", expect])


class Gate(unittest.TestCase):
    def log(self, name):
        return (EVIDENCE / (name + ".txt")).read_text()

    def test_stock_kernel_is_clobbered_and_not_preserved(self):
        self.assertEqual(run(self.log("measure"), "clobbered"), 0)
        self.assertEqual(run(self.log("measure"), "preserved"), 1)

    def test_poison_control_is_clobbered(self):
        self.assertEqual(run(self.log("poison"), "clobbered"), 0)

    def test_fxsave_kernel_is_preserved_and_not_clobbered(self):
        self.assertEqual(run(self.log("fxsave"), "preserved"), 0)
        self.assertEqual(run(self.log("fxsave"), "clobbered"), 1)

    def test_one_injected_event_breaks_preserved(self):
        t = self.log("fxsave").replace("p1{domain=3 checks=", "p1{domain=3 checks=", 1)
        t = re.sub(r"(p1\{domain=3 checks=\d+ xmm_events=)0", r"\g<1>1", t, count=1)
        self.assertNotEqual(t, self.log("fxsave"))
        self.assertEqual(run(t, "preserved"), 1)

    def test_vacuous_run_is_refused_even_when_all_zero(self):
        t = re.sub(r"user_switches_during=\d+", "user_switches_during=3", self.log("fxsave"))
        self.assertEqual(run(t, "preserved"), 1)
        t = re.sub(r"(p0\{domain=2 checks=)\d+", r"\g<1>10", self.log("fxsave"))
        self.assertEqual(run(t, "preserved"), 1)

    def test_missing_or_duplicated_probe_line_is_malformed(self):
        t = "\n".join(l for l in self.log("fxsave").splitlines() if "AIUEOS_FP_PROBE" not in l)
        self.assertEqual(run(t, "preserved"), 2)
        self.assertEqual(run(self.log("fxsave") + self.log("fxsave"), "preserved"), 2)

    def test_missing_ring3_marker_fails(self):
        t = "\n".join(l for l in self.log("fxsave").splitlines() if "RING3_OK" not in l)
        self.assertEqual(run(t, "preserved"), 1)


if __name__ == "__main__":
    unittest.main()
