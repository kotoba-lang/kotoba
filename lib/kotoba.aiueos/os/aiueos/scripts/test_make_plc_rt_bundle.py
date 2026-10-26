import hashlib
import importlib.util
import pathlib
import sys
import unittest


PATH = pathlib.Path(__file__).with_name("make-plc-rt-bundle.py")
SPEC = importlib.util.spec_from_file_location("make_plc_rt_bundle", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BundleTests(unittest.TestCase):
    def test_bad_signature_is_refused(self):
        with self.assertRaisesRegex(ValueError, "signature is invalid"):
            MODULE.make_bundle(bytes(8280), bytes(64), bytes(64))

    def test_parser_refuses_digest_mutation_before_signature_use(self):
        blob = (b"AIUPLC1\0" + (1).to_bytes(4, "little") +
                (8280).to_bytes(4, "little") + bytes(128) +
                hashlib.sha256(bytes(8280)).digest() + bytes(8280))
        mutated = bytearray(blob)
        mutated[-1] = 1
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            MODULE.parse_bundle(bytes(mutated))

    def test_parser_refuses_trailing_bytes(self):
        blob = (b"AIUPLC1\0" + (1).to_bytes(4, "little") +
                (8280).to_bytes(4, "little") + bytes(160) + bytes(8281))
        with self.assertRaisesRegex(ValueError, "bounds"):
            MODULE.parse_bundle(blob)


if __name__ == "__main__":
    unittest.main()
