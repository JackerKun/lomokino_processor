import copy
import json
import os
import tempfile
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
import cv2
import numpy as np
from lomokino.models import CropRect, FrameRegion, DetectionSettings, FilmDocument, resize_rect
from lomokino.detection import detect, rectify
from lomokino.engine import (load_document, frame_image, export_sequence, export_video, load_project,
    save_project, write_image, read_image, MissingSources, fit_frame, ordered_regions)

ROOT = Path(__file__).resolve().parents[1]


def strip(count=4, width=280, frame_height=100, gap=9, scene_line=False):
    rng = np.random.default_rng(7)
    height = count * frame_height + (count - 1) * gap
    image = np.zeros((height, width, 3), np.uint8)
    for i in range(count):
        y = i * (frame_height + gap)
        image[y:y + frame_height] = rng.integers(70, 235, (frame_height, width, 3), dtype=np.uint8)
        if scene_line: image[y + 50:y + 53] = 0
    return image


class GeometryTests(unittest.TestCase):
    def test_half_open_crop_includes_last_pixel(self):
        image = np.arange(10 * 12 * 3, dtype=np.uint16).reshape(10, 12, 3)
        np.testing.assert_array_equal(CropRect(11, 9, 1, 1).crop(image), image[9:10, 11:12])
        np.testing.assert_array_equal(CropRect(0, 0, 12, 10).crop(image), image)

    def test_clamp_never_wraps_negative_indices(self):
        self.assertEqual(CropRect(-3, -4, 12, 14).clamp(8, 9), CropRect(0, 0, 8, 9))
        with self.assertRaises(ValueError): CropRect(100, 100, 8, 8).crop(np.zeros((10, 10, 3), np.uint8))

    def test_eight_resize_handles_cannot_invert_or_leave_source(self):
        rect = CropRect(20, 30, 100, 80)
        for handle in ['top', 'bottom', 'left', 'right', 'top-left', 'top-right', 'bottom-left', 'bottom-right']:
            for delta in [-500, 500]:
                result = resize_rect(rect, handle, delta, delta, 200, 200)
                self.assertGreaterEqual(min(result.width, result.height), 2)
                self.assertEqual(result, result.clamp(200, 200))


class DetectionTests(unittest.TestCase):
    def test_known_gaps_and_picture_lines(self):
        image = strip(scene_line=True)
        result = detect(image)
        self.assertEqual(len(result.regions), 4)
        for i, region in enumerate(result.regions):
            self.assertEqual(region.rect, CropRect(0, i * 109, 280, 100))

    def test_negative_and_sixteen_bit_use_same_geometry(self):
        image = strip()
        expected = [r.rect for r in detect(image).regions]
        for variant in [255 - image, image.astype(np.uint16) * 257]:
            self.assertEqual([r.rect for r in detect(variant).regions], expected)
        self.assertEqual(detect(255 - image).polarity, 'light')

    def test_uniform_mode_is_explicit_and_uncertain(self):
        result = detect(strip(), DetectionSettings(expected_count=5))
        self.assertEqual(len(result.regions), 5)
        self.assertTrue(all(r.confidence < .8 for r in result.regions))
        self.assertTrue(result.warnings)

    def test_blank_scan_does_not_invent_eight_frames(self):
        result = detect(np.zeros((600, 300, 3), np.uint8))
        self.assertEqual(len(result.regions), 1)
        self.assertTrue(result.warnings)
        with self.assertRaises(ValueError): detect(np.zeros((2, 3, 3), np.uint8))

    def test_supplied_demo_counts_and_no_blanket_side_crop(self):
        expected = {'1.jpg': 4, '2.jpg': 4, '3.jpg': 4, '4.jpg': 4, '5.jpg': 4, '6.jpg': 4,
                    '7.jpg': 3, '8.jpg': 9, 'old.jpg': 8}
        expected = {name: count for name, count in expected.items() if (ROOT / 'demo' / name).is_file()}
        if not expected: self.skipTest('No original photographic fixtures in this checkout')
        for name, count in expected.items():
            with self.subTest(name=name):
                image = read_image(ROOT / 'demo' / name)
                result = detect(image)
                self.assertEqual(len(result.regions), count)
                self.assertEqual(len(detect(255 - image).regions), count)
                if name != 'old.jpg': self.assertEqual(result.content_bounds, (0, image.shape[1]))
                else:
                    self.assertTrue(result.perforations)
                    self.assertLess(abs(result.content_bounds[0] - 59), 5)
                    self.assertLess(abs(result.content_bounds[1] - 311), 5)

    def test_bundled_person_free_scan_has_eight_frames(self):
        source = ROOT / 'assets/demo/synthetic_long_scan.png'
        self.assertTrue(source.is_file())
        document, _ = load_document(source)
        self.assertEqual(len(document.regions), 8)
        self.assertEqual(document.image.shape[:2], (2206, 713))

    def test_invalid_angles_and_empty_grid_fail_clearly(self):
        for settings in [DetectionSettings(angle=float('nan')), DetectionSettings(inset=1000),
                         DetectionSettings(expected_count=10001), DetectionSettings(threshold=float('inf'))]:
            with self.subTest(settings=settings), self.assertRaises(ValueError): detect(strip(), settings)

    def test_skew_expands_canvas_without_modifying_input(self):
        image = strip()
        before = image.copy()
        rotated = rectify(image, 2.5)
        self.assertGreater(rotated.shape[0], image.shape[0])
        self.assertGreater(rotated.shape[1], image.shape[1])
        np.testing.assert_array_equal(image, before)


class ProjectExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lomokino-tests-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / '中文 扫描.png'
        self.image = strip()
        write_image(self.source, self.image)
        self.document, _ = load_document(self.source)
        self.order = [r.id for r in self.document.regions]

    def test_unicode_path_and_sixteen_bit_lossless_sequence(self):
        source = self.folder / '16位.png'
        write_image(source, self.image.astype(np.uint16) * 257)
        document, _ = load_document(source)
        destination = self.folder / '无损输出'
        export_sequence([document], [r.id for r in document.regions], destination)
        result = read_image(destination / 'frame_00001.png')
        self.assertEqual(result.dtype, np.uint16)
        np.testing.assert_array_equal(result, document.regions[0].rect.crop(document.image))

    def test_order_exclusion_and_manifest_match_exact_pixels(self):
        self.document.regions[1].enabled = False
        self.document.regions[2].rect = CropRect(17, 220, 150, 70)
        order = list(reversed(self.order))
        destination = self.folder / 'frames'
        self.assertEqual(export_sequence([self.document], order, destination), 3)
        records = json.loads((destination / 'frames.json').read_text())['frames']
        for record, (document, region) in zip(records, ordered_regions([self.document], order)):
            np.testing.assert_array_equal(read_image(destination / record['file']), region.rect.crop(document.image))
            self.assertEqual(record['region_id'], region.id)
        with self.assertRaises(FileExistsError): export_sequence([self.document], order, destination)

    def test_project_roundtrip_preserves_manual_edits_and_relative_paths(self):
        self.document.regions[0].rect = CropRect(9, 8, 200, 70)
        self.document.regions[0].reviewed = True
        self.document.regions[1].enabled = False
        order = list(reversed(self.order))
        project = self.folder / 'test.lomokino.json'
        save_project(project, [self.document], order, {'fps': 5, 'invert': True})
        data = json.loads(project.read_text())
        self.assertFalse(Path(data['sources'][0]['path']).is_absolute())
        docs, restored, options, warnings = load_project(project)
        self.assertEqual(restored, order)
        self.assertEqual(docs[0].regions[0].rect, CropRect(9, 8, 200, 70))
        self.assertTrue(docs[0].regions[0].reviewed)
        self.assertFalse(docs[0].regions[1].enabled)
        self.assertEqual(options['fps'], 5)

    def test_missing_source_requires_relink(self):
        project = self.folder / 'test.lomokino.json'
        save_project(project, [self.document], self.order, {})
        moved = self.folder / 'moved.png'
        self.source.rename(moved)
        with self.assertRaises(MissingSources): load_project(project)
        docs, order, _, _ = load_project(project, {self.source.name: str(moved)})
        self.assertEqual(order, self.order)
        self.assertEqual(Path(docs[0].path), moved.resolve())

    def test_project_rejects_duplicate_or_missing_frame_ids(self):
        project = self.folder / 'test.lomokino.json'
        save_project(project, [self.document], self.order, {})
        value = json.loads(project.read_text())
        value['frame_order'].append(value['frame_order'][0])
        project.write_text(json.dumps(value))
        with self.assertRaises(ValueError): load_project(project)

    def test_cancelled_sequence_leaves_no_partial_folder(self):
        destination = self.folder / 'cancelled'
        with self.assertRaises(InterruptedError):
            export_sequence([self.document], self.order, destination, cancelled=lambda: True)
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.folder.glob('.lomokino-frames-*')))

    def test_h264_export_reads_back_the_edited_order_and_fps(self):
        self.document.regions[0].enabled = False
        destination = self.folder / 'movie.mp4'
        metadata = export_video([self.document], list(reversed(self.order)), destination, {'fps': 5, 'codec': 'h264'})
        self.assertEqual(metadata['frames'], 3)
        capture = cv2.VideoCapture(str(destination))
        self.assertTrue(capture.isOpened())
        self.assertEqual(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 3)
        self.assertAlmostEqual(capture.get(cv2.CAP_PROP_FPS), 5, delta=.05)
        capture.release()

    def test_late_video_cancel_preserves_previous_destination(self):
        destination = self.folder / 'existing.mp4'
        destination.write_bytes(b'previous-file')
        stop = False
        def progress(index, total, message):
            nonlocal stop
            if index == total: stop = True
        with self.assertRaises(InterruptedError):
            export_video([self.document], self.order, destination, {'fps': 5, 'codec': 'mp4v'}, progress, lambda: stop)
        self.assertEqual(destination.read_bytes(), b'previous-file')
        self.assertFalse(list(self.folder.glob('.existing.*.mp4')))

    def test_horizontal_scan_is_canonicalized_without_interpolation(self):
        horizontal = self.folder / '横条.png'
        write_image(horizontal, cv2.rotate(self.image, cv2.ROTATE_90_CLOCKWISE))
        document, _ = load_document(horizontal)
        np.testing.assert_array_equal(document.image, self.image)
        self.assertEqual(len(document.regions), 4)

    def test_cli_uses_saved_crops_order_and_requested_fps(self):
        self.document.regions[1].enabled = False
        self.document.regions[2].rect = CropRect(17, 220, 150, 70)
        project = self.folder / 'cli.lomokino.json'
        order = list(reversed(self.order))
        save_project(project, [self.document], order, {'fps': 12})
        destination = self.folder / 'cli-output'
        run = subprocess.run([sys.executable, str(ROOT / 'lomokino_processor.py'), '--project', str(project),
                              '-o', str(destination), '--fps', '7'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['video']['frames'], 3)
        records = json.loads((destination / 'frames/frames.json').read_text())['frames']
        self.assertEqual([r['region_id'] for r in records], [key for key in order if key != self.order[1]])
        capture = cv2.VideoCapture(str(destination / 'movie.mp4'))
        self.assertAlmostEqual(capture.get(cv2.CAP_PROP_FPS), 7, delta=.05)
        capture.release()

    def test_video_fitting_never_stretches_a_picture(self):
        image = np.full((50, 200, 3), 200, np.uint8)
        fitted = fit_frame(image, (200, 100), 'fit')
        self.assertEqual(fitted.shape, (100, 200, 3))
        self.assertTrue(np.all(fitted[:25] == 0))
        self.assertTrue(np.all(fitted[25:75] == 200))


if __name__ == '__main__': unittest.main()
