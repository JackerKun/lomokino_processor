import json
import unittest

from lomokino.updates import is_newer_release, latest_release_tag


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
