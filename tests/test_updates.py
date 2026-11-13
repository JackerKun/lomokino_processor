import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

from lomokino.ui import LomoKinoGUI
from lomokino.updates import fetch_latest_release, is_newer_release, latest_release_tag


def release(tag, **fields):
    return json.dumps({'tag_name': tag, 'draft': False, 'prerelease': False, **fields}).encode()


class ReleaseVersionTests(unittest.TestCase):
    def test_compares_numeric_versions(self):
        self.assertTrue(is_newer_release('v4.0.10', '4.0.9'))
        self.assertTrue(is_newer_release('v5.0.0', '4.9.9'))
        self.assertFalse(is_newer_release('v4.0.9', '4.0.10'))
        self.assertFalse(is_newer_release('v4.0.10', '4.0.10'))
        self.assertFalse(is_newer_release(None, '4.0.10'))

    def test_reads_formal_release_tag(self):
        self.assertEqual(latest_release_tag(release('v4.0.3')), 'v4.0.3')

    def test_ignores_drafts_prereleases_and_invalid_responses(self):
        for data in (release('v4.1.0', draft=True), release('v4.1.0', prerelease=True),
                     release('v4.1.0-rc.1'), release('v4.1.0/../latest'), release(40100),
                     b'{"tag_name": "v4.1.0"}', b'{"message": "API rate limit exceeded"}',
                     b'[]', b'<html>Bad gateway</html>', b'\xff'):
            with self.subTest(data=data):
                self.assertIsNone(latest_release_tag(data))

    def test_worker_writes_only_a_valid_release_tag(self):
        with TemporaryDirectory() as folder, patch('urllib.request.build_opener') as build_opener:
            destination = Path(folder) / 'tag'
            response = MagicMock(status=200)
            build_opener.return_value.open.return_value.__enter__.return_value = response
            response.read.return_value = release('v4.0.10', prerelease=True)
            self.assertNotEqual(fetch_latest_release(destination), 0)
            self.assertFalse(destination.exists())
            response.read.return_value = release('v4.0.10')
            self.assertEqual(fetch_latest_release(destination), 0)
            self.assertEqual(destination.read_text(encoding='ascii'), 'v4.0.10')


class UpdateWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for_check(self, window):
        deadline = time.monotonic() + 5
        while not window.check_update_action.isEnabled() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(window.check_update_action.isEnabled())
        self.assertTrue(window.isVisible())

    def test_failed_or_stalled_worker_leaves_window_usable_and_allows_retry(self):
        window = LomoKinoGUI()
        self.addCleanup(window.close)
        window.show()
        self.assertFalse(window.update_notice.isVisible())
        with patch.object(window._update_check, '_worker_arguments',
                          return_value=['-c', 'import os; os.abort()']):
            window.check_updates()
            self.wait_for_check(window)
        self.assertFalse(window.update_notice.isVisible())

        with patch('lomokino.update_process.TIMEOUT_MS', 150), patch.object(
                window._update_check, '_worker_arguments', return_value=['-c', 'import time; time.sleep(30)']):
            window.check_update_action.trigger()
            self.assertFalse(window.check_update_action.isEnabled())
            self.wait_for_check(window)
        self.assertIn('暂时无法检查更新', window.update_message.text())

        def write_result(destination):
            return ['-c', f'from pathlib import Path; Path({str(destination)!r}).write_text("v999.0.0")']

        with patch.object(window._update_check, '_worker_arguments', side_effect=write_result):
            window.check_update_action.trigger()
            self.wait_for_check(window)
        self.assertTrue(window.update_download.isVisible())
        self.assertTrue(window.update_page.toString().endswith('/releases/tag/v999.0.0'))
