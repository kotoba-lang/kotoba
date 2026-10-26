import importlib.util
import pathlib
import sys
import unittest


PATH = pathlib.Path(__file__).with_name("make-plc-signature-material.py")
SPEC = importlib.util.spec_from_file_location("make_plc_signature_material", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SignatureMaterialTests(unittest.TestCase):
    def test_der_signature_becomes_fixed_width(self):
        der = bytes.fromhex("3006020101020102")
        raw = MODULE.raw_signature(der)
        self.assertEqual(len(raw), 64)
        self.assertEqual(raw[31], 1)
        self.assertEqual(raw[63], 2)

    def test_signature_trailing_bytes_are_refused(self):
        with self.assertRaises(ValueError):
            MODULE.raw_signature(bytes.fromhex("300602010102010200"))

    def test_public_key_requires_p256_identifiers(self):
        prefix = bytes.fromhex("301306072a8648ce3d020106082a8648ce3d030107")
        der = prefix + b"\x03\x42\x00\x04" + bytes(range(1, 65))
        self.assertEqual(MODULE.raw_public_key(der), bytes(range(1, 65)))
        with self.assertRaises(ValueError):
            MODULE.raw_public_key(b"\x03\x42\x00\x04" + bytes(range(1, 65)))


if __name__ == "__main__":
    unittest.main()
