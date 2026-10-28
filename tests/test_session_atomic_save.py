import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.session import SessionManager


class SessionAtomicSaveTests(unittest.TestCase):
    def test_failed_cancellation_save_does_not_truncate_previous_pending(self):
        with tempfile.TemporaryDirectory() as directory, patch("src.core.session.HISTORY_DIR", Path(directory)):
            session = SessionManager("atomic")
            session.save_pending("workflow", {"pending_action": "confirm_image_workflow_correction"})
            with patch("src.core.session.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    session.clear_pending()
            self.assertTrue(SessionManager("atomic").has_pending())
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
            session.clear_pending()
            self.assertFalse(SessionManager("atomic").has_pending())


if __name__ == "__main__":
    unittest.main()
