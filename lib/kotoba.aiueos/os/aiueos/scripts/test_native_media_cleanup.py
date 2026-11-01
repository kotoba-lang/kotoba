import importlib.util
from pathlib import Path
import tempfile
import unittest
import native_media_retention as retention

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

    def test_controls_restore_exact_bytes_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.img').write_bytes(b'012345')
            for index, (operation, offset) in enumerate((('flip', 2), ('truncate', None), ('append-zero', None))):
                name = f'control-{index}.img'
                control = root / name
                expected = retention.reconstruct(b'012345', operation, offset)
                control.write_bytes(expected)
                record = retention.make_record(root, name, 'source.img', operation, offset)
                self.assertTrue(retention.discard_control(root, record))
                self.assertEqual((root / 'source.img').read_bytes(), b'012345')
                self.assertEqual(retention.restore_control(root, record).read_bytes(), expected)
                with self.assertRaises(FileExistsError):
                    retention.restore_control(root, record)

    def test_changed_source_and_control_are_not_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, control = root / 'source.img', root / 'control.img'
            source.write_bytes(b'1234')
            control.write_bytes(b'123')
            record = retention.make_record(root, control.name, source.name, 'truncate', None)
            control.write_bytes(b'xxx')
            self.assertFalse(retention.discard_control(root, record))
            control.write_bytes(b'123')
            source.write_bytes(b'xxxx')
            with self.assertRaises(ValueError):
                retention.discard_control(root, record)
            self.assertEqual(control.read_bytes(), b'123')


if __name__ == '__main__':
    unittest.main()
