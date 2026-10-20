"""Lossless storage and preservation of locally regenerated research tables."""

from pathlib import Path
import tempfile
import unittest

from scripts.prepare_processed_tables import pack_table, packed_path, restore_table, check_table


class ProcessedTableStorageTests(unittest.TestCase):
    def test_exact_round_trip_and_deterministic_packing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.csv"
            original = b'\xef\xbb\xbfmodel,value\r\n"a,b",1\r\n'
            path.write_bytes(original)
            pack_table(path)
            packed = packed_path(path).read_bytes()
            pack_table(path)
            self.assertEqual(packed_path(path).read_bytes(), packed)
            self.assertEqual(path.read_bytes(), original)
            path.unlink()
            restore_table(path)
            self.assertEqual(path.read_bytes(), original)
            check_table(path)

    def test_restore_preserves_differing_local_csv_and_reports_stale_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.csv"
            path.write_bytes(b"old data\n")
            pack_table(path)
            path.write_bytes(b"new local data\n")
            with self.assertRaisesRegex(ValueError, "--pack"):
                restore_table(path)
            self.assertEqual(path.read_bytes(), b"new local data\n")
            pack_table(path)
            check_table(path)

    def test_corrupt_archive_does_not_leave_partial_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.csv"
            packed_path(path).write_bytes(b"not gzip")
            with self.assertRaises(OSError):
                restore_table(path)
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [packed_path(path)])


if __name__ == "__main__":
    unittest.main()
