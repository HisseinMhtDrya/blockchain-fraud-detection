import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_config import load_local_environment


class LocalEnvironmentTests(unittest.TestCase):
    def test_loads_values_and_preserves_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / ".env"
            config_path.write_text(
                '# local settings\nFROM_FILE="file value"\nEMPTY=\nPRESERVED=file value\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"PRESERVED": "process value"}, clear=True):
                load_local_environment(config_path)
                self.assertEqual(os.environ["FROM_FILE"], "file value")
                self.assertNotIn("EMPTY", os.environ)
                self.assertEqual(os.environ["PRESERVED"], "process value")

    def test_missing_file_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            load_local_environment(Path(directory) / "missing.env")

    def test_invalid_setting_reports_line_without_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / ".env"
            config_path.write_text("NOT A KEY=secret-value\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 1") as error:
                load_local_environment(config_path)
        self.assertNotIn("secret-value", str(error.exception))


if __name__ == "__main__":
    unittest.main()
