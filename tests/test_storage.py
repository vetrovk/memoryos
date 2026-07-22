from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from memoryos.config import database_path
from memoryos.storage import connect


class StorageTests(unittest.TestCase):
    def test_connect_uses_current_database_without_touching_legacy_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            legacy = home / "_system" / "memory.sqlite3"
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b"legacy database placeholder")

            con = connect(home)
            con.close()

            self.assertEqual(legacy.read_bytes(), b"legacy database placeholder")
            self.assertTrue(database_path(home).exists())
