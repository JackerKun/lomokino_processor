"""Regression tests for source-pixel coordinates across GUI zoom and edits."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from pathlib import Path
import numpy as np
from PyQt6.QtWidgets import QApplication, QAbstractSpinBox, QGraphicsPixmapItem
from PyQt6.QtCore import QLocale, QPointF, Qt
from PyQt6.QtTest import QTest
from lomokino.models import CropRect, FrameRegion, FilmDocument
from lomokino.canvas import FilmCanvas
from lomokino.ui import LomoKinoGUI

APP = QApplication.instance() or QApplication([])

class NumericLocaleTests(unittest.TestCase):
    def test_project_parameters_use_ascii_digits_and_decimal_point(self):
        previous = QLocale()
        self.addCleanup(QLocale.setDefault, previous)
        for name in ('zh_Hans_HK', 'zh_Hans_MO', 'ar_EG', 'de_DE'):
            with self.subTest(locale=name):
                QLocale.setDefault(QLocale(name))
                window = LomoKinoGUI()
                try:
                    controls = window.findChildren(QAbstractSpinBox)
                    self.assertIn(window.angle, controls)
                    self.assertIn(window.fps, controls)
                    for control in controls:
                        self.assertEqual(control.locale().zeroDigit(), '0')
                        self.assertEqual(control.locale().decimalPoint(), '.')
                        self.assertEqual(control.locale().name(), 'C')

                    window.inset.setValue(3)
                    self.assertEqual(window.inset.text(), '3 px')
                    window.inset.stepUp()
                    self.assertEqual(window.inset.text(), '4 px')

                    window.angle.lineEdit().setText('-1.25 °')
                    window.angle.interpretText()
                    self.assertAlmostEqual(window.angle.value(), -1.25)
                    window.angle.stepUp()
                    self.assertEqual(window.angle.text(), '-1.15 °')

                    window.fps.lineEdit().setText('23.98 FPS')
                    window.fps.interpretText()
                    self.assertAlmostEqual(window.fps.value(), 23.98)
                    self.assertEqual(window.fps.text(), '23.98 FPS')
                finally:
                    window.setWindowModified(False)
                    window.close()


class CanvasTests(unittest.TestCase):
    def setUp(self):
        self.rect = CropRect(100, 240, 400, 150)
        self.region = FrameRegion(self.rect)
        self.document = FilmDocument('test.png', np.zeros((1200, 800, 3), np.uint8), [self.region])
        self.canvas = FilmCanvas()
        self.canvas.resize(700, 500)
        self.canvas.show()
        self.canvas.set_document(self.document, self.region.id)
        APP.processEvents()

    def tearDown(self): self.canvas.close()

    def test_zoom_scroll_resize_preserve_source_pixel_edges(self):
        for factor in (.2, .5, 1, 2.75, 6):
            self.canvas.zoom_to(factor)
            self.canvas.horizontalScrollBar().setValue(40)
            self.canvas.verticalScrollBar().setValue(160)
            point = self.canvas.mapToScene(self.canvas.mapFromScene(QPointF(231, 359)))
            self.assertLessEqual(abs(point.x() - 231), 1 / factor)
            self.assertLessEqual(abs(point.y() - 359), 1 / factor)
            self.assertEqual(self.canvas.items_by_id[self.region.id].geometry(), self.rect)
        self.canvas.resize(500, 700)
        APP.processEvents()
        self.assertEqual(self.canvas.items_by_id[self.region.id].geometry(), self.rect)

    def test_long_strip_preview_rounding_cannot_shift_crop_y(self):
        doc = FilmDocument('long.png', np.zeros((12000, 123, 3), np.uint8), [])
        self.canvas.set_document(doc)
        item = next(i for i in self.canvas.scene().items() if isinstance(i, QGraphicsPixmapItem))
        bounds = item.sceneBoundingRect()
        self.assertAlmostEqual(bounds.width(), 123)
        self.assertAlmostEqual(bounds.height(), 12000)

    def test_typing_a_multidigit_coordinate_commits_once(self):
        window = LomoKinoGUI()
        try:
            window.documents = [self.document]
            window.order = [self.region.id]
            window.active_document_id = self.document.id
            window.active_region_id = self.region.id
            window.refresh_all()
            spin = window.coordinates['height']
            spin.setFocus()
            spin.selectAll()
            QTest.keyClicks(spin, '125')
            self.assertEqual(window.current_region()[1].rect.height, 150)
            QTest.keyClick(spin, Qt.Key.Key_Return)
            self.assertEqual(window.current_region()[1].rect.height, 125)
            self.assertEqual(window.undo_stack.count(), 1)
        finally:
            window.setWindowModified(False)
            window.close()

    def test_numeric_edit_preview_and_undo_share_one_geometry(self):
        window = LomoKinoGUI()
        try:
            window.documents = [self.document]
            window.order = [self.region.id]
            window.active_document_id = self.document.id
            window.active_region_id = self.region.id
            window.refresh_all()
            for key, value in [('width', 200), ('height', 80), ('x', 123), ('y', 345)]:
                window.coordinates[key].setValue(value)
                window.coordinates_changed()
            expected = CropRect(123, 345, 200, 80)
            self.assertEqual(window.current_region()[1].rect, expected)
            self.assertEqual(window.canvas.items_by_id[self.region.id].geometry(), expected)
            self.assertTrue(window.current_region()[1].reviewed)
            window.undo_stack.undo()
            self.assertEqual(window.current_region()[1].rect.y, 240)
            window.undo_stack.redo()
            self.assertEqual(window.current_region()[1].rect, expected)
        finally:
            window.setWindowModified(False)
            window.close()
