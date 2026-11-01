import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('build-native-media-macos.py')
spec = importlib.util.spec_from_file_location('native_media', SCRIPT)
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


class ReproductionCleanupTest(unittest.TestCase):
    def test_only_equal_regular_copy_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original.img'
            duplicate = Path(directory) / 'reproduced.img'
            original.write_bytes(b'original')
            duplicate.write_bytes(b'different')
            self.assertFalse(media.remove_reproduced_copy(original, duplicate))
            self.assertEqual(duplicate.read_bytes(), b'different')
            duplicate.write_bytes(b'original')
            self.assertTrue(media.remove_reproduced_copy(original, duplicate))
            self.assertEqual(original.read_bytes(), b'original')
            self.assertFalse(duplicate.exists())

    def test_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original.img'
            duplicate = Path(directory) / 'reproduced.img'
            original.write_bytes(b'original')
            duplicate.symlink_to(original)
            self.assertFalse(media.remove_reproduced_copy(original, duplicate))
            self.assertTrue(duplicate.is_symlink())


if __name__ == '__main__':
    unittest.main()
