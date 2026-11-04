import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import native_text_margin as m

SHA = "2387a32d37554cbed0c3691a30ae00ea2bc65a7ffff9c698563e7e0a570b58a6"
ROW = {"textMargin": {"warnBelowBytes": 8192, "failBelowBytes": 2048,
                      "calibrations": [{"compilerSha256": SHA, "textSegmentOverheadBytes": 10400}]}}
CAP = 2097152


def elf(text_filesz, extra_exec=False):
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<Q", header, 32, 64)
    struct.pack_into("<HH", header, 54, 56, 3 if extra_exec else 2)
    loads = [struct.pack("<IIQQQQQQ", 1, 5, 4096, 0x101000, 0, text_filesz, text_filesz, 4096),
             struct.pack("<IIQQQQQQ", 1, 6, 0, 0x400000, 0, 4096, 4096, 4096)]
    if extra_exec:
        loads.append(struct.pack("<IIQQQQQQ", 1, 5, 0, 0x800000, 0, 16, 16, 4096))
    return bytes(header) + b"".join(loads)


class TextMargin(unittest.TestCase):
    def test_ok_warn_fail_follow_the_estimated_margin(self):
        # margin = cap - (text - overhead)
        self.assertEqual(m.text_margin(elf(CAP + 10400 - 20000), CAP, SHA, ROW)["state"], "OK")
        self.assertEqual(m.text_margin(elf(CAP + 10400 - 5000), CAP, SHA, ROW)["state"], "WARN")
        self.assertEqual(m.text_margin(elf(CAP + 10400 - 1000), CAP, SHA, ROW)["state"], "FAIL")
        self.assertEqual(m.text_margin(elf(CAP + 10400 + 1), CAP, SHA, ROW)["estimatedMarginBytes"], -1)

    def test_unknown_compiler_is_uncalibrated_not_trusted(self):
        record = m.text_margin(elf(CAP), CAP, "0" * 64, ROW)
        self.assertEqual(record["state"], "UNCALIBRATED")
        self.assertNotIn("estimatedMarginBytes", record)

    def test_missing_configuration_is_reported(self):
        self.assertEqual(m.text_margin(elf(CAP), CAP, SHA, {})["state"], "UNCONFIGURED")

    def test_malformed_images_are_refused(self):
        with self.assertRaises(ValueError):
            m.text_margin(b"MZ" + bytes(100), CAP, SHA, ROW)
        with self.assertRaises(ValueError):
            m.text_margin(elf(CAP, extra_exec=True), CAP, SHA, ROW)


if __name__ == "__main__":
    unittest.main()
