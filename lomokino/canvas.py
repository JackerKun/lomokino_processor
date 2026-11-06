"""QGraphicsScene keeps crop overlays in image pixels at every zoom / DPI scale."""
import cv2
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor, QPainter, QFont, QTransform
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem
from .models import CropRect, resize_rect
from .engine import to8


def pixmap(image, maximum=4096):
    image = to8(image)
    h, w = image.shape[:2]
    if max(h, w) > maximum:
        ratio = maximum / max(h, w)
        image = cv2.resize(image, (max(1, round(w * ratio)), max(1, round(h * ratio))), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return QPixmap.fromImage(QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy())


class CropItem(QGraphicsRectItem):
    def __init__(self, region, number, canvas):
        super().__init__(0, 0, region.rect.width, region.rect.height)
        self.canvas, self.region_id, self.number = canvas, region.id, number
        self.attention, self.enabled_frame = region.confidence < .8 and not region.reviewed, region.enabled
        self.setPos(region.rect.x, region.rect.y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self.resizing = None
        self.initial = None

    def geometry(self):
        return CropRect.from_edges(self.pos().x(), self.pos().y(), self.pos().x() + self.rect().width(), self.pos().y() + self.rect().height())

    def set_geometry(self, rect):
        self.prepareGeometryChange()
        self.setRect(0, 0, rect.width, rect.height)
        self.setPos(rect.x, rect.y)
        self.update()

    def boundingRect(self):
        return super().boundingRect().adjusted(-24, -24, 24, 24)

    def handle_at(self, point):
        tolerance = 8 / max(.02, self.canvas.transform().m11())
        r = self.rect()
        x, y = point.x(), point.y()
        left, right = abs(x) <= tolerance, abs(x - r.width()) <= tolerance
        top, bottom = abs(y) <= tolerance, abs(y - r.height()) <= tolerance
        if not (-tolerance <= x <= r.width() + tolerance and -tolerance <= y <= r.height() + tolerance): return None
        return '-'.join(filter(None, ['top' if top else ('bottom' if bottom else ''), 'left' if left else ('right' if right else '')])) or None

    def paint(self, painter, option, widget=None):
        scale = max(.02, self.canvas.transform().m11())
        color = QColor('#eab86c' if self.attention else '#82d3c4')
        if not self.enabled_frame: color = QColor('#87919b')
        if self.isSelected(): color = QColor('#ffe0a3')
        pen = QPen(color, 2 if self.isSelected() else 1)
        pen.setCosmetic(True)
        if not self.enabled_frame: pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 18 if self.isSelected() else 4))
        painter.drawRect(self.rect())
        font = QFont()
        font.setPixelSize(max(1, round(12 / scale)))
        painter.setFont(font)
        r = self.rect()
        label = f'{self.number:02d}' + (' · 待复查' if self.attention else '') + (' · 排除' if not self.enabled_frame else '')
        painter.fillRect(QRectF(0, 0, min(r.width(), 120 / scale), min(r.height(), 23 / scale)), QColor('#17252a'))
        painter.setPen(color)
        painter.drawText(QPointF(6 / scale, 16 / scale), label)
        if self.isSelected():
            painter.setBrush(color)
            half = 3.5 / scale
            for x, y in [(0, 0), (r.width() / 2, 0), (r.width(), 0), (0, r.height() / 2),
                         (r.width(), r.height() / 2), (0, r.height()), (r.width() / 2, r.height()), (r.width(), r.height())]:
                painter.drawRect(QRectF(x - half, y - half, half * 2, half * 2))

    def hoverMoveEvent(self, event):
        handle = self.handle_at(event.pos())
        if handle in ('top-left', 'bottom-right'): cursor = Qt.CursorShape.SizeFDiagCursor
        elif handle in ('top-right', 'bottom-left'): cursor = Qt.CursorShape.SizeBDiagCursor
        elif handle in ('top', 'bottom'): cursor = Qt.CursorShape.SizeVerCursor
        elif handle: cursor = Qt.CursorShape.SizeHorCursor
        else: cursor = Qt.CursorShape.SizeAllCursor
        self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            bounds = self.canvas.image_bounds
            return QPointF(max(0, min(value.x(), bounds.width() - self.rect().width())),
                           max(0, min(value.y(), bounds.height() - self.rect().height())))
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return super().mousePressEvent(event)
        self.initial, self.press_position = self.geometry(), event.scenePos()
        self.resizing = self.handle_at(event.pos())
        if self.resizing:
            self.scene().clearSelection()
            self.setSelected(True)
            event.accept()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = event.scenePos() - self.press_position
            rect = resize_rect(self.initial, self.resizing, delta.x(), delta.y(),
                               round(self.canvas.image_bounds.width()), round(self.canvas.image_bounds.height()))
            self.set_geometry(rect)
            event.accept()
        else: super().mouseMoveEvent(event)
        self.canvas.regionPreview.emit(self.region_id, self.geometry())

    def mouseReleaseEvent(self, event):
        if not self.resizing: super().mouseReleaseEvent(event)
        self.resizing = None
        rect = self.geometry()
        self.set_geometry(rect)
        if self.initial is not None and rect != self.initial:
            self.canvas.regionEdited.emit(self.region_id, rect)
        self.initial = None

    def mouseDoubleClickEvent(self, event):
        self.canvas.regionInspect.emit(self.region_id)
        event.accept()


class FilmCanvas(QGraphicsView):
    regionEdited = pyqtSignal(str, object)
    regionPreview = pyqtSignal(str, object)
    regionAdded = pyqtSignal(object)
    regionDelete = pyqtSignal(str)
    regionSelected = pyqtSignal(str)
    regionInspect = pyqtSignal(str)
    zoomChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor('#11161b'))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_bounds = QRectF()
        self.items_by_id = {}
        self.drawing = False
        self.draw_item = None
        self.pan_position = None
        self.space_down = False
        self.auto_fit = True
        self.scene().selectionChanged.connect(self._selected)
        self.setObjectName('filmCanvas')
        self.setAccessibleName('原图裁切画布')

    def set_document(self, document, selected_id=None, refit=True):
        self.scene().blockSignals(True)
        self.scene().clear()
        self.items_by_id = {}
        h, w = document.image.shape[:2]
        self.image_bounds = QRectF(0, 0, w, h)
        preview = pixmap(document.image)
        item = self.scene().addPixmap(preview)
        item.setTransform(QTransform.fromScale(w / preview.width(), h / preview.height()))
        item.setZValue(0)
        for index, region in enumerate(document.regions, 1):
            crop = CropItem(region, index, self)
            self.scene().addItem(crop)
            self.items_by_id[region.id] = crop
            if region.id == selected_id: crop.setSelected(True)
        self.scene().setSceneRect(self.image_bounds)
        self.scene().blockSignals(False)
        if refit: self.fit_all()

    def _selected(self):
        items = [i for i in self.scene().selectedItems() if isinstance(i, CropItem)]
        if items: self.regionSelected.emit(items[0].region_id)

    def select_region(self, region_id, center=False):
        self.scene().blockSignals(True)
        self.scene().clearSelection()
        item = self.items_by_id.get(region_id)
        if item:
            item.setSelected(True)
            if center: self.ensureVisible(item, 20, 20)
        self.scene().blockSignals(False)

    def fit_all(self):
        if self.image_bounds.isEmpty(): return
        self.auto_fit = True
        self.fitInView(self.image_bounds, Qt.AspectRatioMode.KeepAspectRatio)
        self.zoomChanged.emit(self.transform().m11())

    def fit_width(self):
        if self.image_bounds.isEmpty(): return
        self.auto_fit = False
        self.resetTransform()
        factor = max(.02, (self.viewport().width() - 30) / self.image_bounds.width())
        self.scale(factor, factor)
        self.zoomChanged.emit(self.transform().m11())

    def zoom_to(self, factor):
        self.auto_fit = False
        self.resetTransform()
        factor = max(.02, min(12., factor))
        self.scale(factor, factor)
        self.zoomChanged.emit(factor)

    def zoom_by(self, factor): self.zoom_to(self.transform().m11() * factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.auto_fit: self.fit_all()

    def set_draw_mode(self, active):
        self.drawing = active
        self.setCursor(Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or (self.space_down and event.button() == Qt.MouseButton.LeftButton):
            self.pan_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if self.drawing and event.button() == Qt.MouseButton.LeftButton and not self.image_bounds.isEmpty():
            self.draw_origin = self.mapToScene(event.position().toPoint())
            self.draw_item = self.scene().addRect(QRectF(self.draw_origin, self.draw_origin), QPen(QColor('#ffe0a3'), 1))
            self.draw_item.setZValue(100)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pan_position is not None:
            point = event.position().toPoint()
            delta = point - self.pan_position
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.pan_position = point
            return
        if self.draw_item:
            self.draw_item.setRect(QRectF(self.draw_origin, self.mapToScene(event.position().toPoint())).normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.pan_position is not None:
            self.pan_position = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if self.draw_item:
            rect = self.draw_item.rect()
            crop = CropRect.from_edges(rect.left(), rect.top(), rect.right(), rect.bottom()).clamp(
                round(self.image_bounds.width()), round(self.image_bounds.height()))
            self.scene().removeItem(self.draw_item)
            self.draw_item = None
            if crop.width >= 2 and crop.height >= 2: self.regionAdded.emit(crop)
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
            event.accept()
        else: super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space_down = True
            event.accept()
            return
        items = [i for i in self.scene().selectedItems() if isinstance(i, CropItem)]
        if items and event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.regionDelete.emit(items[0].region_id)
            return
        if items and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx = step * (int(event.key() == Qt.Key.Key_Right) - int(event.key() == Qt.Key.Key_Left))
            dy = step * (int(event.key() == Qt.Key.Key_Down) - int(event.key() == Qt.Key.Key_Up))
            item = items[0]
            item.setPos(item.pos() + QPointF(dx, dy))
            item.set_geometry(item.geometry())
            self.regionEdited.emit(item.region_id, item.geometry())
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space: self.space_down = False
        super().keyReleaseEvent(event)
