import importlib.util
import json
import pathlib
import unittest


PATH = pathlib.Path(__file__).with_name("make-plc-native-receipt.py")
SPEC = importlib.util.spec_from_file_location("make_plc_native_receipt", PATH)
maker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(maker)


class PlcDeploymentInputTest(unittest.TestCase):
    RFC_SIGNATURE = bytes.fromhex(
        "efd48b2aacb6a8fd1140dd9cd45e81d69d2c877b56aaf991c34d0ea84eaf3716"
        "f7cb1c942d657c41d436c7a1b6e29f65f3e900dbb9aff4064dc4ab2f843acda8")
    RFC_DIGEST = bytes.fromhex(
        "af2bdbe1aa9b6ec1e2ade1d694f41fc71a831d0268e9891562113d8a62add1bf")
    RFC_PUBLIC = bytes.fromhex(
        "60fed4ba255a9d31c961eb74c6356d68c049b8923b61fa6ce669622e60f29fb6"
        "7903fe1008b8bc99a41ae9e95628bc64f2f1b20c2d7e9f5177a3c294d4462299")

    def test_p256_signature_and_tamper(self):
        self.assertTrue(maker.ecdsa_p256_sha256_valid(
            self.RFC_SIGNATURE, self.RFC_PUBLIC, self.RFC_DIGEST))
        bad = bytearray(self.RFC_SIGNATURE)
        bad[-1] ^= 1
        self.assertFalse(maker.ecdsa_p256_sha256_valid(
            bytes(bad), self.RFC_PUBLIC, self.RFC_DIGEST))

    def test_shipped_motor_map_and_admission_are_valid(self):
        examples = PATH.parents[1] / "plc" / "examples"
        io_map = json.loads((examples / "motor-io-map.json").read_text())
        admission = json.loads((examples / "motor-admission.json").read_text())
        frontend_path = PATH.with_name("compile-plc-st.py")
        frontend = maker.load_frontend(frontend_path)
        source = (examples / "motor.st").read_text()
        _, inputs, outputs, _ = frontend.Parser(source).parse()
        maker.validate_io_map(io_map, inputs, outputs)
        duplicate_sink = {**io_map, "outputs": [dict(item) for item in io_map["outputs"]]}
        duplicate_sink["outputs"][1]["sink"] = duplicate_sink["outputs"][0]["sink"]
        with self.assertRaisesRegex(ValueError, "sinks"):
            maker.validate_io_map(duplicate_sink, inputs, outputs)
        self.assertEqual(5, maker.validate_admission(admission)["priority"])

    def test_io_map_requires_exact_indices_and_safe_outputs(self):
        valid = {"format": "aiueos-plc-io-map/v1",
                 "inputs": [{"index": 0}, {"index": 1}],
                 "outputs": [{"index": 0, "safe_value": 0},
                             {"index": 1, "safe_value": -1}]}
        maker.validate_io_map(valid, 2, 2)
        invalid = {**valid, "outputs": [{"index": 0, "safe_value": 0}]}
        with self.assertRaisesRegex(ValueError, "output map"):
            maker.validate_io_map(invalid, 2, 2)
        invalid = {**valid, "outputs": [{"index": 0},
                                         {"index": 1, "safe_value": 0}]}
        with self.assertRaisesRegex(ValueError, "safe value"):
            maker.validate_io_map(invalid, 2, 2)

    def test_admission_requires_nested_timing_envelope(self):
        valid = {"format": "aiueos-plc-admission/v1", "priority": 5,
                 "cycle_us": 10000, "deadline_us": 8000,
                 "budget_us": 1000, "wcet_us": 700}
        self.assertEqual(700, maker.validate_admission(valid)["wcet_us"])
        for key, value in (("wcet_us", 1001), ("budget_us", 8001),
                           ("deadline_us", 10001)):
            invalid = {**valid, key: value}
            with self.assertRaisesRegex(ValueError, "WCET"):
                maker.validate_admission(invalid)

    def test_deployment_requires_physical_io_and_rta_evidence(self):
        io_map = {"format": "aiueos-plc-io-map/v1",
                  "inputs": [{"index": 0}],
                  "outputs": [{"index": 0, "safe_value": 0}]}
        with self.assertRaisesRegex(ValueError, "driver"):
            maker.validate_io_map(io_map, 1, 1, qualified=True)
        admission = {"format": "aiueos-plc-admission/v1", "priority": 5,
                     "cycle_us": 10000, "deadline_us": 8000,
                     "budget_us": 1000, "wcet_us": 700}
        with self.assertRaisesRegex(ValueError, "response-time"):
            maker.validate_admission(admission, qualified=True)


if __name__ == "__main__":
    unittest.main()
