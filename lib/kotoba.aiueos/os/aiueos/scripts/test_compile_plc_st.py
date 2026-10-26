import importlib.util
import pathlib
import sys
import unittest


PATH = pathlib.Path(__file__).with_name("compile-plc-st.py")
SPEC = importlib.util.spec_from_file_location("compile_plc_st", PATH)
compiler = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = compiler
SPEC.loader.exec_module(compiler)


MOTOR = """
PROGRAM Motor
VAR_INPUT
  Enable : BOOL;
  Sensor : DINT;
END_VAR
VAR_OUTPUT
  MotorOn : BOOL;
  Command : DINT;
END_VAR
Command := Sensor + 1;
MotorOn := Enable AND Command < 100;
END_PROGRAM
"""


class StructuredTextCompilerTest(unittest.TestCase):
    def test_motor_program_lowers_to_transactional_capability_calls(self):
        generated = compiler.compile_source(MOTOR)
        self.assertIn("plc-v-command (plc-dint (+ plc-v-sensor 1))", generated)
        self.assertIn("plc-v-motoron (and plc-v-enable (< plc-v-command 100))", generated)
        positions = [generated.index(f"(cap-call {number} ")
                     for number in (16, 17, 19, 18)]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("(bit-and plc-v-command 4294967295)", generated)
        self.assertIn("commit (if (= watchdog 1) (cap-call 18 2) 0)", generated)

    def test_generation_is_deterministic_and_case_insensitive(self):
        self.assertEqual(compiler.compile_source(MOTOR), compiler.compile_source(MOTOR))
        lower = MOTOR.lower().replace("program motor", "PROGRAM motor")
        lower = lower.replace("end_program", "END_PROGRAM")
        lower = lower.replace("var_input", "VAR_INPUT").replace("var_output", "VAR_OUTPUT")
        lower = lower.replace("end_var", "END_VAR")
        lower = lower.replace("bool", "BOOL").replace("dint", "DINT")
        self.assertIn("(ns aiueos.plc.motor", compiler.compile_source(lower))

    def test_unbounded_control_flow_is_refused(self):
        source = MOTOR.replace("Command := Sensor + 1;", "WHILE Enable DO Command := 1; END_WHILE;")
        with self.assertRaises(compiler.PlcCompileError):
            compiler.compile_source(source)

    def test_output_read_before_assignment_is_refused(self):
        source = MOTOR.replace("Command := Sensor + 1;", "Command := Command + 1;")
        with self.assertRaisesRegex(compiler.PlcCompileError, "read before assignment"):
            compiler.compile_source(source)

    def test_bool_dint_type_mismatch_is_refused(self):
        source = MOTOR.replace("Command := Sensor + 1;", "Command := Enable;")
        with self.assertRaisesRegex(compiler.PlcCompileError, "type mismatch"):
            compiler.compile_source(source)

    def test_every_output_must_be_staged_once(self):
        missing = MOTOR.replace("MotorOn := Enable AND Command < 100;", "")
        with self.assertRaisesRegex(compiler.PlcCompileError, "outputs not assigned"):
            compiler.compile_source(missing)
        duplicate = MOTOR.replace("END_PROGRAM", "MotorOn := FALSE;\nEND_PROGRAM")
        with self.assertRaisesRegex(compiler.PlcCompileError, "more than once"):
            compiler.compile_source(duplicate)


if __name__ == "__main__":
    unittest.main()
