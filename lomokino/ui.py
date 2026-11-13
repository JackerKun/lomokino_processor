"""LomoKino Studio: inspect scans, edit source-pixel crops, then export that exact sequence."""
from dataclasses import replace
from pathlib import Path
import argparse
import copy
import os
import sys
import threading
import traceback
import cv2
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QRectF, QLocale, QUrl
from PyQt6.QtGui import QAction, QKeySequence, QUndoStack, QUndoCommand, QColor, QPainter, QPen, QIcon, QTransform, QPalette, QDesktopServices
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QToolButton, QMenu, QToolBar, QSplitter, QScrollArea, QStackedWidget,
    QListWidget, QListWidgetItem, QAbstractItemView, QTabWidget, QFormLayout, QGroupBox,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QFileDialog, QMessageBox, QProgressBar,
    QDialog, QGraphicsView, QGraphicsScene, QFrame)
from . import __version__
from .models import CropRect, FrameRegion, DetectionSettings
from .engine import (load_document, save_project, load_project, ordered_regions, frame_lookup,
    frame_image, export_sequence, export_video, MissingSources, IMAGE_SUFFIXES, natural_key, to8)
from .canvas import FilmCanvas, pixmap
from .update_process import UpdateCheck
from .updates import PROJECT_URL, is_newer_release

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
IMAGE_FILTER = '扫描图片 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp)'
STYLE = '''
QMainWindow, QDialog { background: #151b20; color: #edf1f1; }
QWidget { background: #1b2329; font-family: "PingFang SC", "Microsoft YaHei UI", sans-serif; font-size: 13px; color: #e2e8e9; }
QLabel { background: transparent; }
QGroupBox, QScrollArea > QWidget > QWidget { background: #1b2329; }
QListWidget::item:selected { color: #edf1f1; }
QLabel#brand { font-size: 22px; font-weight: 700; color: #f0e3cc; }
QLabel#muted, QLabel#status { color: #a7b5ba; font-size: 12px; }
QLabel#sectionTitle { color: #edf1f1; font-weight: 600; }
QLabel#emptyTitle { font-size: 29px; font-weight: 600; color: #eee4d3; }
QLabel#preview { background: #0f1418; border: 1px solid #344148; border-radius: 6px; }
QWidget#header { background: #1d262c; border-bottom: 1px solid #344148; }
QWidget#footer { background: #1d262c; border-top: 1px solid #344148; }
QWidget#updateNotice { background: transparent; }
QWidget#sidebar, QWidget#inspector { background: #1b2329; }
QWidget#emptyStage, QWidget#emptyActions { background: #172026; }
QToolBar { border: 0; spacing: 7px; padding: 8px; background: #1b2329; }
QToolBar::separator { background: #39464d; width: 1px; margin: 5px; }
QToolButton, QPushButton { background: #29363f; border: 1px solid #40515a; border-radius: 5px; padding: 6px 10px; min-height: 20px; }
QToolBar QToolButton#qt_toolbar_ext_button { padding: 0; qproperty-text: '»'; qproperty-toolButtonStyle: ToolButtonTextOnly; qproperty-toolTip: '更多画布工具'; }
QToolButton:hover, QPushButton:hover { background: #354650; border-color: #657c87; }
QToolButton:pressed, QPushButton:pressed { background: #202c34; }
QPushButton#primary { background: #dbad68; color: #182126; font-weight: 600; border-color: #e6bd7f; }
QPushButton#primary:hover { background: #e6bd7f; }
QPushButton#primary:pressed { background: #c99856; }
QToolButton:checked, QPushButton:checked { background: #48605e; border-color: #89c9ba; }
QPushButton:disabled, QToolButton:disabled, QPushButton#primary:disabled { color: #7f9098; background: #212b32; border-color: #303d45; }
QPushButton:focus, QToolButton:focus, QPushButton#primary:focus { border-color: #e6bd7f; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #11191e; border: 1px solid #41515b; border-radius: 4px; padding: 5px; min-height: 21px; selection-background-color: #526b65; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #89b2ab; }
QComboBox QAbstractItemView { background: #25323b; selection-background-color: #526b65; }
QListWidget { background: #172026; border: 0; outline: 0; }
QListWidget::item { padding: 7px; border: 1px solid transparent; border-radius: 5px; }
QListWidget::item:selected { background: #344a4c; border: 1px solid #86b6ab; }
QListWidget::item:hover:!selected { background: #26353e; }
QGroupBox { font-weight: 600; border: 1px solid #36454d; border-radius: 6px; margin-top: 15px; padding: 12px 9px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 4px; color: #d3e5df; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #202c34; padding: 9px 18px; color: #9daeb5; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #f4e7d2; border-bottom: 2px solid #d9b37b; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #172026; width: 10px; }
QScrollBar:horizontal { background: #172026; height: 10px; }
QScrollBar::handle { background: #465a65; border-radius: 4px; min-height: 25px; min-width: 25px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QProgressBar { border: 0; background: #293941; height: 7px; border-radius: 3px; text-align: center; }
QProgressBar::chunk { background: #b5c8a5; border-radius: 3px; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QSplitter::handle { background: #344249; width: 2px; height: 2px; }
QMenuBar, QMenu { background: #1d282f; color: #e1e9e8; }
QMenu::item:selected { background: #425e59; }
QMessageBox { background: #202d35; }
'''


def label(text='', muted=False):
    widget = QLabel(text)
    if muted: widget.setObjectName('muted')
    widget.setWordWrap(True)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if primary: widget.setObjectName('primary')
    return widget


def scroll_page():
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(12, 8, 12, 15)
    layout.setSpacing(10)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(page)
    return scroll, layout


def number(low=0, high=100000, value=0):
    widget = QSpinBox()
    widget.setLocale(QLocale.c())
    widget.setRange(low, high)
    widget.setValue(value)
    widget.setKeyboardTracking(False)
    return widget


class Worker(QThread):
    progress = pyqtSignal(int, int, str)
    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
        self.cancelled = threading.Event()
        self.result = None
        self.error = None
    def run(self):
        try: self.result = self.function(self.progress.emit, self.cancelled.is_set)
        except InterruptedError as error: self.error = ('cancel', str(error), '')
        except Exception as error: self.error = ('error', str(error), traceback.format_exc())


class EditCommand(QUndoCommand):
    def __init__(self, window, before, after, text):
        super().__init__(text)
        self.window, self.before, self.after = window, before, after
    def undo(self): self.window.restore(self.before)
    def redo(self): self.window.restore(self.after)


class Timeline(QListWidget):
    reordered = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setIconSize(QSize(150, 72))
        self.setGridSize(QSize(170, 116))
        self.setMovement(QListWidget.Movement.Snap)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMinimumHeight(130)
        self.setAccessibleName('确认帧序列，可拖动排序')
    def dropEvent(self, event):
        super().dropEvent(event)
        self.reordered.emit()


class Profile(QWidget):
    def __init__(self):
        super().__init__()
        self.profile = None
        self.threshold = 0
        self.setFixedHeight(78)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#10191e'))
        if self.profile is None: return
        profile = self.profile
        width, height = self.width(), self.height()
        painter.setPen(QPen(QColor('#82bbac'), 1))
        step = max(1, len(profile) // width)
        points = [(int(i / max(1, len(profile) - 1) * (width - 1)), int((1 - profile[i] / 255) * (height - 4)) + 2) for i in range(0, len(profile), step)]
        for a, b in zip(points[:-1], points[1:]): painter.drawLine(*a, *b)
        painter.setPen(QPen(QColor('#d9a86a'), 1, Qt.PenStyle.DashLine))
        y = round((1 - self.threshold / 255) * (height - 4)) + 2
        painter.drawLine(0, y, width, y)


class FrameDialog(QDialog):
    def __init__(self, window, region_id):
        super().__init__(window)
        self.window = window
        self.keys = [r.id for d, r in ordered_regions(window.documents, window.order)]
        if region_id not in self.keys: self.keys.append(region_id)
        self.index = self.keys.index(region_id)
        self.setWindowTitle('逐帧检查 · LomoKino Studio')
        self.resize(1160, 700)
        layout = QVBoxLayout(self)
        self.info = label()
        layout.addWidget(self.info)
        self.view = QGraphicsView(QGraphicsScene(self))
        self.view.setBackgroundBrush(QColor('#0b1014'))
        layout.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addWidget(button('← 上一帧', lambda: self.move(-1)))
        row.addWidget(button('适合窗口', self.fit))
        row.addWidget(button('1:1 像素', lambda: self.view.resetTransform()))
        row.addWidget(button('下一帧 →', lambda: self.move(1)))
        row.addWidget(button('关闭', self.accept))
        layout.addLayout(row)
        for shortcut, offset in [('Left', -1), ('Right', 1)]:
            action = QAction(self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda checked=False, value=offset: self.move(value))
            self.addAction(action)
        self.render()
    def move(self, offset):
        self.index = (self.index + offset) % len(self.keys)
        self.render()
    def render(self):
        document, region = frame_lookup(self.window.documents)[self.keys[self.index]]
        image = frame_image(document, region, self.window.export_options())
        self.view.scene().clear()
        preview = pixmap(image, 4096)
        self.item = self.view.scene().addPixmap(preview)
        self.item.setTransform(QTransform.fromScale(image.shape[1] / preview.width(), image.shape[0] / preview.height()))
        self.view.scene().setSceneRect(QRectF(0, 0, image.shape[1], image.shape[0]))
        self.info.setText(f'{self.index + 1}/{len(self.keys)}  ·  {document.name}  ·  {image.shape[1]} × {image.shape[0]} px  ·  原图矩形 {region.rect.x}, {region.rect.y}, {region.rect.width}, {region.rect.height}')
        QTimer.singleShot(0, self.fit)
    def fit(self): self.view.fitInView(self.view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class LomoKinoGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.documents = []
        self.order = []
        self.active_document_id = None
        self.active_region_id = None
        self.project_path = None
        self.last_directory = str(Path.home())
        self.job = None
        self._refreshing = False
        self._manual_update_check = False
        self._update_check = UpdateCheck(self)
        self._update_check.finished.connect(self.update_check_finished)
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(30)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_playback_frame)
        self.setAcceptDrops(True)
        self.setMinimumSize(1040, 680)
        self.resize(1560, 960)
        self.setWindowTitle(f'LomoKino Studio {__version__} · 未命名项目[*]')
        if (ROOT / 'assets/icon.png').exists(): self.setWindowIcon(QIcon(str(ROOT / 'assets/icon.png')))
        self.build_ui()
        self.setStyleSheet(STYLE)
        self.update_summary()

    def action(self, text, callback, shortcut=None):
        action = QAction(text, self)
        action.triggered.connect(callback)
        if shortcut: action.setShortcut(QKeySequence(shortcut))
        return action

    def build_ui(self):
        file_menu = self.menuBar().addMenu('项目')
        for title, callback, key in [('导入扫描条…', self.import_files, 'Ctrl+O'), ('打开项目…', self.open_project, 'Ctrl+Shift+O'),
                                     ('保存项目', self.save, 'Ctrl+S'), ('项目另存为…', self.save_as, 'Ctrl+Shift+S')]:
            file_menu.addAction(self.action(title, callback, key))
        file_menu.addAction(self.action('新建项目', self.new_project, 'Ctrl+N'))
        file_menu.addSeparator()
        file_menu.addAction(self.action('载入无人物示例', self.load_demo))
        edit_menu = self.menuBar().addMenu('编辑')
        undo = self.undo_stack.createUndoAction(self, '撤销')
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        redo = self.undo_stack.createRedoAction(self, '重做')
        redo.setShortcuts([QKeySequence('Ctrl+Shift+Z'), QKeySequence('Ctrl+Y')])
        edit_menu.addActions([undo, redo])
        edit_menu.addAction(self.action('反转全部帧顺序', self.reverse_order))
        help_menu = self.menuBar().addMenu('帮助')
        help_menu.addAction(self.action('操作指南', self.show_help))
        help_menu.addSeparator()
        self.check_update_action = self.action('检查更新', lambda: self.check_updates(manual=True))
        help_menu.addAction(self.check_update_action)
        help_menu.addAction(self.action('在 GitHub 查看项目', lambda: QDesktopServices.openUrl(QUrl(PROJECT_URL))))
        main = QWidget()
        root = QVBoxLayout(main)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.header = QWidget()
        self.header.setObjectName('header')
        header = QHBoxLayout(self.header)
        header.setContentsMargins(16, 12, 16, 12)
        header.setSpacing(8)
        brand = QVBoxLayout()
        brand.setSpacing(4)
        name = label('LomoKino Studio')
        name.setObjectName('brand')
        name.setWordWrap(False)
        brand.addWidget(name)
        workflow = label('扫描  /  校对  /  导出', True)
        workflow.setWordWrap(False)
        brand.addWidget(workflow)
        header.addLayout(brand)
        header.addStretch()
        header.addWidget(button('打开项目', self.open_project))
        header.addWidget(button('保存项目', self.save))
        header.addWidget(button('＋ 导入扫描条', self.import_files, True))
        root.addWidget(self.header)
        self.body = QSplitter(Qt.Orientation.Horizontal)
        self.body.addWidget(self.build_sidebar())
        self.body.addWidget(self.build_workspace(undo, redo))
        self.body.addWidget(self.build_inspector())
        self.body.setStretchFactor(1, 1)
        self.body.setSizes([230, 1000, 310])
        root.addWidget(self.body, 1)
        footer = QWidget()
        footer.setObjectName('footer')
        row = QHBoxLayout(footer)
        row.setContentsMargins(14, 7, 14, 7)
        self.status = label('就绪 · 原片只读，裁切与顺序保存在项目文件中', True)
        self.status.setObjectName('status')
        row.addWidget(self.status, 1)
        self.update_notice = QWidget()
        self.update_notice.setObjectName('updateNotice')
        update_row = QHBoxLayout(self.update_notice)
        update_row.setContentsMargins(0, 0, 0, 0)
        self.update_message = label()
        update_row.addWidget(self.update_message)
        self.update_page = None
        self.update_download = button('去下载', self.open_update_page)
        update_row.addWidget(self.update_download)
        dismiss = button('关闭', self.update_notice.hide)
        dismiss.setAccessibleName('关闭更新提示')
        update_row.addWidget(dismiss)
        self.update_notice.hide()
        row.addWidget(self.update_notice)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(180)
        self.progress.setTextVisible(False)
        self.progress.hide()
        row.addWidget(self.progress)
        self.cancel_button = button('取消任务', self.cancel_job)
        self.cancel_button.hide()
        row.addWidget(self.cancel_button)
        root.addWidget(footer)
        self.setCentralWidget(main)
        view_menu = self.menuBar().addMenu('视图')
        for text, widget in [('素材侧栏', self.sidebar), ('属性侧栏', self.inspector)]:
            action = QAction(text, self, checkable=True, checked=True)
            action.toggled.connect(widget.setVisible)
            view_menu.addAction(action)

    def build_sidebar(self):
        self.sidebar = QWidget()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setMinimumWidth(180)
        self.sidebar.setMaximumWidth(340)
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = label('扫描素材')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        layout.addWidget(label('支持多张拖入 · 按文件名自然排序', True))
        self.film_list = QListWidget()
        self.film_list.setIconSize(QSize(44, 66))
        self.film_list.currentItemChanged.connect(self.film_selected)
        self.film_list.setAccessibleName('扫描素材列表')
        layout.addWidget(self.film_list, 1)
        layout.addWidget(button('识别全部扫描条', lambda: self.analyze(True)))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button('添加', self.import_files))
        row.addWidget(button('移除', self.remove_document))
        layout.addLayout(row)
        layout.addWidget(button('载入无人物示例', self.load_demo))
        self.source_summary = label('', True)
        layout.addWidget(self.source_summary)
        return self.sidebar

    def build_workspace(self, undo, redo):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.canvas_toolbar = QToolBar()
        for text, callback in [('适合窗口', lambda: self.canvas.fit_all()), ('适合宽度', lambda: self.canvas.fit_width()),
                               ('−', lambda: self.canvas.zoom_by(.8)), ('1:1', lambda: self.canvas.zoom_to(1)),
                               ('＋', lambda: self.canvas.zoom_by(1.25))]:
            self.canvas_toolbar.addAction(self.action(text, callback))
        self.zoom_text = label('100%', True)
        self.canvas_toolbar.addWidget(self.zoom_text)
        self.canvas_toolbar.addSeparator()
        self.draw_action = QAction('＋ 画裁切框', self, checkable=True)
        self.draw_action.toggled.connect(lambda active: self.canvas.set_draw_mode(active))
        self.canvas_toolbar.addAction(self.draw_action)
        self.canvas_toolbar.addAction(undo)
        self.canvas_toolbar.addAction(redo)
        layout.addWidget(self.canvas_toolbar)
        self.center_split = QSplitter(Qt.Orientation.Vertical)
        self.stage = QStackedWidget()
        self.empty = QWidget()
        self.empty.setObjectName('emptyStage')
        empty = QVBoxLayout(self.empty)
        empty.setContentsMargins(24, 24, 24, 24)
        empty.setSpacing(8)
        empty.addStretch()
        title = label('从胶片扫描条开始')
        title.setObjectName('emptyTitle')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(title)
        subtitle = label('导入扫描条后自动分帧，校对裁切和顺序后即可导出。', True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(subtitle)
        empty.addSpacing(12)
        actions = QWidget()
        actions.setObjectName('emptyActions')
        actions.setFixedWidth(288)
        action_row = QHBoxLayout(actions)
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addWidget(button('＋ 导入扫描条', self.import_files, True), 1)
        action_row.addWidget(button('载入无人物示例', self.load_demo), 1)
        empty.addWidget(actions, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch()
        self.stage.addWidget(self.empty)
        self.canvas = FilmCanvas()
        self.canvas.regionSelected.connect(self.select_region)
        self.canvas.regionEdited.connect(self.edit_region)
        self.canvas.regionPreview.connect(self.preview_geometry)
        self.canvas.regionAdded.connect(self.add_region)
        self.canvas.regionDelete.connect(self.delete_region)
        self.canvas.regionInspect.connect(self.inspect_region)
        self.canvas.zoomChanged.connect(lambda value: self.zoom_text.setText(f'{value * 100:.0f}%'))
        self.stage.addWidget(self.canvas)
        self.center_split.addWidget(self.stage)
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(10, 8, 10, 3)
        row = QHBoxLayout()
        self.sequence_summary = label('确认帧序列 · 0 帧')
        self.sequence_summary.setObjectName('sectionTitle')
        row.addWidget(self.sequence_summary, 1)
        self.play_button = button('▶ 预演', self.toggle_playback)
        row.addWidget(self.play_button)
        row.addWidget(button('反转顺序', self.reverse_order))
        row.addWidget(button('放大当前帧', lambda: self.inspect_region(self.active_region_id)))
        bottom_layout.addLayout(row)
        self.timeline = Timeline()
        self.timeline.currentItemChanged.connect(self.timeline_selected)
        self.timeline.reordered.connect(self.timeline_reordered)
        bottom_layout.addWidget(self.timeline)
        bottom_layout.addWidget(label('拖动缩略图改变播放顺序 · 灰色帧不导出 · 双击裁切框可放大检查', True))
        self.center_split.addWidget(bottom)
        self.center_split.setSizes([700, 190])
        self.center_split.setStretchFactor(0, 1)
        layout.addWidget(self.center_split, 1)
        return page

    def build_inspector(self):
        self.inspector = QWidget()
        self.inspector.setObjectName('inspector')
        self.inspector.setMinimumWidth(270)
        self.inspector.setMaximumWidth(380)
        layout = QVBoxLayout(self.inspector)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        crop_scroll, crop = scroll_page()
        self.crop_info = label('选择一个裁切框，检查实际坐标与成片。', True)
        crop.addWidget(self.crop_info)
        self.preview = QLabel('当前帧预览')
        self.preview.setObjectName('preview')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(115)
        self.preview.setMaximumHeight(170)
        crop.addWidget(self.preview)
        fields = QGroupBox('像素坐标 · 原图工作区')
        form = QFormLayout(fields)
        self.coordinates = {}
        for key, name in [('x', 'X'), ('y', 'Y'), ('width', '宽度'), ('height', '高度')]:
            spin = number(0 if key in ('x', 'y') else 2)
            spin.setSuffix(' px')
            spin.setAccessibleName(f'裁切{name}像素')
            spin.valueChanged.connect(self.coordinates_changed)
            self.coordinates[key] = spin
            form.addRow(name, spin)
        crop.addWidget(fields)
        self.enabled_box = QCheckBox('包含此帧 · 取消勾选即排除')
        self.enabled_box.setChecked(True)
        self.enabled_box.toggled.connect(self.enable_region)
        crop.addWidget(self.enabled_box)
        self.reviewed_box = QCheckBox('已逐帧复查此框')
        self.reviewed_box.toggled.connect(self.review_region)
        crop.addWidget(self.reviewed_box)
        crop.addWidget(button('当前扫描条标记已复查', self.review_document))
        buttons = QHBoxLayout()
        buttons.addWidget(button('复制当前框', self.duplicate_region))
        buttons.addWidget(button('删除框', lambda: self.delete_region(self.active_region_id)))
        crop.addLayout(buttons)
        crop.addWidget(label('方向键移动 1 px · Shift 方向键移动 10 px\nCtrl / ⌘ + 滚轮缩放 · 空格拖动平移', True))
        self.warning_label = label('', True)
        crop.addWidget(self.warning_label)
        crop.addStretch()
        self.tabs.addTab(crop_scroll, '裁切')
        detect_scroll, detect_layout = scroll_page()
        detect_layout.addWidget(label('识别是候选框，导出前请逐帧确认。', True))
        detection_group = QGroupBox('扫描与识别')
        form = QFormLayout(detection_group)
        self.orientation = QComboBox()
        self.orientation.addItems(['自动判断横 / 竖', '竖向扫描', '横向 · 逆时针 90°', '横向 · 顺时针 90°'])
        form.addRow('输入方向', self.orientation)
        self.sensitivity = QComboBox()
        self.sensitivity.addItems(['自动（推荐）', '保守', '敏感'])
        form.addRow('检测灵敏度', self.sensitivity)
        self.polarity = QComboBox()
        self.polarity.addItems(['自动 · 深 / 浅分隔', '深色分隔带', '浅色分隔带'])
        form.addRow('分隔带类型', self.polarity)
        self.expected_count = number(0, 200)
        self.expected_count.setSpecialValueText('自动识别')
        form.addRow('等距帧数', self.expected_count)
        self.manual_height = number(0, 100000)
        self.manual_height.setSpecialValueText('关闭')
        form.addRow('等距帧高', self.manual_height)
        self.inset = number(0, 100)
        self.inset.setSuffix(' px')
        form.addRow('内缩边距', self.inset)
        self.holes = QCheckBox('检测到成对齿孔时去除边轨')
        self.holes.setChecked(True)
        form.addRow(self.holes)
        self.deskew = QCheckBox('尝试自动校正倾斜')
        form.addRow(self.deskew)
        self.angle = QDoubleSpinBox()
        self.angle.setLocale(QLocale.c())
        self.angle.setRange(-6, 6)
        self.angle.setDecimals(2)
        self.angle.setSingleStep(.1)
        self.angle.setSuffix(' °')
        self.angle.setKeyboardTracking(False)
        form.addRow('手动校正角度', self.angle)
        detect_layout.addWidget(detection_group)
        detect_layout.addWidget(button('重新识别当前扫描条', lambda: self.analyze(False), True))
        detect_layout.addWidget(label('重新识别会替换对应扫描条的候选框，可撤销。\n等距模式包含黑带，请手动校对；倾斜校正会重采样，原片不修改。', True))
        self.profile = Profile()
        detect_layout.addWidget(self.profile)
        self.analysis_text = label('浅绿：逐行亮度 · 金线：黑带阈值', True)
        detect_layout.addWidget(self.analysis_text)
        detect_layout.addStretch()
        self.tabs.addTab(detect_scroll, '识别')
        export_scroll, export = scroll_page()
        self.export_summary = label('按下方确认帧序列导出，不重新识别原片。', True)
        export.addWidget(self.export_summary)
        video = QGroupBox('视频设置')
        form = QFormLayout(video)
        self.fps = QDoubleSpinBox()
        self.fps.setLocale(QLocale.c())
        self.fps.setRange(1, 60)
        self.fps.setValue(12)
        self.fps.setSingleStep(1)
        self.fps.setSuffix(' FPS')
        self.fps.setKeyboardTracking(False)
        self.fps.valueChanged.connect(self.options_changed)
        form.addRow('播放帧率', self.fps)
        self.output_width, self.output_height = number(0, 8192), number(0, 8192)
        for control in [self.output_width, self.output_height]:
            control.setSpecialValueText('原始中位尺寸')
            control.valueChanged.connect(self.options_changed)
        form.addRow('输出宽度', self.output_width)
        form.addRow('输出高度', self.output_height)
        self.fit_mode = QComboBox()
        self.fit_mode.addItems(['适合画面 · 留黑边', '铺满画面 · 居中裁切'])
        self.fit_mode.currentIndexChanged.connect(self.options_changed)
        form.addRow('尺寸不同时', self.fit_mode)
        self.codec = QComboBox()
        self.codec.addItems(['H.264 / FFmpeg（推荐）', 'MPEG-4 Part 2 / OpenCV'])
        self.codec.currentIndexChanged.connect(self.options_changed)
        form.addRow('编码器', self.codec)
        export.addWidget(video)
        transform = QGroupBox('画面处理 · 非破坏性')
        form = QFormLayout(transform)
        self.invert = QCheckBox('反相（简单负片）')
        self.invert.toggled.connect(self.options_changed)
        form.addRow(self.invert)
        self.rotation = QComboBox()
        self.rotation.addItems(['不旋转', '顺时针 90°', '旋转 180°', '逆时针 90°'])
        self.rotation.currentIndexChanged.connect(self.options_changed)
        form.addRow('画面方向', self.rotation)
        export.addWidget(transform)
        export.addWidget(button('导出 MP4 视频…', self.export_movie, True))
        export.addWidget(button('导出无损 PNG 序列…', lambda: self.export_images('png')))
        export.addWidget(button('导出 JPEG 序列…', lambda: self.export_images('jpg')))
        export.addWidget(label('反相仅做亮度翻转，不校正彩色负片色罩。\nPNG 保留源图 8 / 16 位深度；JPEG 和视频为 8 位。\n图片序列不缩放；视频按设置适配尺寸。\n输出附裁切清单，可追溯来源和坐标。', True))
        export.addStretch()
        self.tabs.addTab(export_scroll, '导出')
        layout.addWidget(self.tabs)
        return self.inspector

    def snapshot(self):
        return [(d, [r.to_dict() for r in d.regions]) for d in self.documents], list(self.order), self.active_document_id, self.active_region_id

    def restore(self, state):
        docs, order, document_id, region_id = state
        self.documents = [replace(d, regions=[FrameRegion.from_dict(r) for r in regions]) for d, regions in docs]
        self.order = list(order)
        self.active_document_id, self.active_region_id = document_id, region_id
        self.setWindowModified(True)
        self.refresh_all(refit=False)

    def change(self, text, function):
        if self.job: return
        before = self.snapshot()
        function()
        after = self.snapshot()
        self.undo_stack.push(EditCommand(self, before, after, text))

    def current_document(self):
        return next((d for d in self.documents if d.id == self.active_document_id), None)

    def current_region(self): return frame_lookup(self.documents).get(self.active_region_id)

    def refresh_all(self, refit=False):
        self._refreshing = True
        self.film_list.blockSignals(True)
        self.film_list.clear()
        for document in self.documents:
            h, w = document.image.shape[:2]
            item = QListWidgetItem(QIcon(pixmap(document.image, 160)), f'{document.name}\n{w} × {h} · {len(document.regions)} 帧')
            item.setData(Qt.ItemDataRole.UserRole, document.id)
            item.setToolTip(document.path)
            item.setSizeHint(QSize(200, 85))
            self.film_list.addItem(item)
            if document.id == self.active_document_id: self.film_list.setCurrentItem(item)
        self.film_list.blockSignals(False)
        if self.documents and self.current_document() is None: self.active_document_id = self.documents[0].id
        self.stage.setCurrentIndex(1 if self.documents else 0)
        document = self.current_document()
        if document: self.canvas.set_document(document, self.active_region_id, refit)
        self.refresh_timeline()
        self._refreshing = False
        self.refresh_inspector()
        self.update_summary()

    def refresh_timeline(self):
        self.timeline.blockSignals(True)
        self.timeline.clear()
        for index, (document, region) in enumerate(ordered_regions(self.documents, self.order, False), 1):
            image = frame_image(document, region, self.export_options())
            icon = pixmap(image, 220)
            item = QListWidgetItem(QIcon(icon), f'{index:03d} · {document.name}\n' + ('排除' if not region.enabled else ('✓ 已复查' if region.reviewed else ('待复查' if region.confidence < .8 else f'{region.rect.width} × {region.rect.height}'))))
            item.setData(Qt.ItemDataRole.UserRole, region.id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not region.enabled: item.setForeground(QColor('#8a9499'))
            self.timeline.addItem(item)
            if region.id == self.active_region_id: self.timeline.setCurrentItem(item)
        self.timeline.blockSignals(False)

    def update_summary(self):
        count = len(ordered_regions(self.documents, self.order))
        total = len(self.order)
        seconds = count / self.fps.value()
        self.sequence_summary.setText(f'确认帧序列 · {count}/{total} 帧 · {seconds:.2f} 秒')
        self.sequence_summary.setToolTip(f'{count} 帧参与导出，共 {total} 帧')
        self.source_summary.setText(f'{len(self.documents)} 张扫描条 · {total} 个裁切框\n原片只读，编辑可撤销')
        self.export_summary.setText(f'{count} 帧 · {self.fps.value():g} FPS · {seconds:.2f} 秒\n导出使用当前确认序列，不重新检测。')
        self.play_button.setEnabled(count > 0)

    def film_selected(self, current, previous=None):
        if not current or self._refreshing: return
        self.timer.stop()
        self.play_button.setText('▶ 预演')
        self.active_document_id = current.data(Qt.ItemDataRole.UserRole)
        document = self.current_document()
        self.active_region_id = document.regions[0].id if document.regions else None
        self.canvas.set_document(document, self.active_region_id, True)
        self.profile.profile = None
        self.profile.update()
        self.refresh_inspector()
        self.sync_timeline_selection()

    def select_region(self, key):
        if key not in frame_lookup(self.documents): return
        self.active_region_id = key
        self.refresh_inspector()
        self.sync_timeline_selection()

    def sync_timeline_selection(self):
        self.timeline.blockSignals(True)
        for i in range(self.timeline.count()):
            item = self.timeline.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.active_region_id:
                self.timeline.setCurrentItem(item)
                break
        self.timeline.blockSignals(False)

    def timeline_selected(self, current, previous=None):
        if not current or self._refreshing: return
        key = current.data(Qt.ItemDataRole.UserRole)
        pair = frame_lookup(self.documents).get(key)
        if not pair: return
        document, region = pair
        changed = self.active_document_id != document.id
        self.active_document_id, self.active_region_id = document.id, key
        if changed:
            self.canvas.set_document(document, key, False)
            self.film_list.blockSignals(True)
            for index in range(self.film_list.count()):
                if self.film_list.item(index).data(Qt.ItemDataRole.UserRole) == document.id:
                    self.film_list.setCurrentRow(index)
            self.film_list.blockSignals(False)
        self.canvas.select_region(key, center=True)
        self.refresh_inspector()

    def timeline_reordered(self):
        order = [self.timeline.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.timeline.count())]
        if order != self.order: self.change('调整帧序列', lambda: setattr(self, 'order', order))

    def refresh_inspector(self):
        pair = self.current_region()
        self._refreshing = True
        for spin in self.coordinates.values(): spin.setEnabled(bool(pair))
        self.enabled_box.setEnabled(bool(pair))
        self.reviewed_box.setEnabled(bool(pair))
        document = self.current_document()
        if document:
            self.warning_label.setText('\n'.join(document.warnings) or '绿色框为分隔候选；边缘残帧以橙色提示，请复查。')
        if pair:
            document, region = pair
            for key, spin in self.coordinates.items():
                spin.blockSignals(True)
                maximum = {'x': document.image.shape[1] - region.rect.width, 'y': document.image.shape[0] - region.rect.height,
                           'width': document.image.shape[1] - region.rect.x, 'height': document.image.shape[0] - region.rect.y}[key]
                spin.setMaximum(maximum)
                spin.setValue(getattr(region.rect, key))
                spin.blockSignals(False)
            self.enabled_box.blockSignals(True)
            self.enabled_box.setChecked(region.enabled)
            self.enabled_box.blockSignals(False)
            self.reviewed_box.blockSignals(True)
            self.reviewed_box.setChecked(region.reviewed)
            self.reviewed_box.blockSignals(False)
            self.crop_info.setText(f'{document.name}\n{region.rect.width} × {region.rect.height} px · ' + ('已复查' if region.reviewed else ('建议复查' if region.confidence < .8 else '自动候选')))
            self.render_preview(document, region)
        else:
            self.crop_info.setText('选择裁切框，或使用“画裁切框”添加一帧。')
            self.preview.clear()
            self.preview.setText('当前帧预览')
        self._refreshing = False

    def render_preview(self, document, region):
        image = frame_image(document, region, self.export_options())
        self.preview.setPixmap(pixmap(image, 1000).scaled(max(160, self.preview.width() - 8), 140,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def preview_geometry(self, key, rect):
        pair = frame_lookup(self.documents).get(key)
        if pair:
            document, region = pair
            self.render_preview(document, replace(region, rect=rect))
            for name, spin in self.coordinates.items():
                spin.blockSignals(True)
                spin.setValue(getattr(rect, name))
                spin.blockSignals(False)

    def edit_region(self, key, rect):
        pair = frame_lookup(self.documents).get(key)
        if pair and pair[1].rect != rect:
            def update():
                pair[1].rect = rect
                pair[1].reviewed = True
            self.change('修改裁切坐标', update)

    def coordinates_changed(self):
        if self._refreshing: return
        pair = self.current_region()
        if not pair: return
        document, region = pair
        width, height = document.image.shape[1], document.image.shape[0]
        values = {key: spin.value() for key, spin in self.coordinates.items()}
        values['width'] = min(max(2, values['width']), width)
        values['height'] = min(max(2, values['height']), height)
        values['x'] = min(values['x'], width - values['width'])
        values['y'] = min(values['y'], height - values['height'])
        rect = CropRect(**values)
        if rect != region.rect: self.edit_region(region.id, rect)
        else: self.refresh_inspector()

    def enable_region(self, value):
        if self._refreshing: return
        pair = self.current_region()
        if pair and pair[1].enabled != value:
            self.change('包含 / 排除此帧', lambda: setattr(pair[1], 'enabled', value))

    def add_region(self, rect):
        document = self.current_document()
        if not document: return
        region = FrameRegion(rect, confidence=1, note='手动裁切', reviewed=True)
        def change():
            document.regions.append(region)
            self.order.append(region.id)
            self.active_region_id = region.id
        self.change('添加裁切框', change)
        self.draw_action.setChecked(False)

    def review_region(self, value):
        if self._refreshing: return
        pair = self.current_region()
        if pair and pair[1].reviewed != value:
            self.change('标记帧复查状态', lambda: setattr(pair[1], 'reviewed', value))

    def review_document(self):
        document = self.current_document()
        if document:
            self.change('标记扫描条已复查', lambda: [setattr(r, 'reviewed', True) for r in document.regions])

    def new_project(self):
        if self.job or not self.needs_save(): return
        self.documents, self.order = [], []
        self.active_document_id = self.active_region_id = self.project_path = None
        self.undo_stack.clear()
        self.apply_options({})
        self.canvas.scene().clear()
        self.canvas.image_bounds = QRectF()
        self.canvas.items_by_id.clear()
        self.refresh_all()
        self.setWindowTitle(f'LomoKino Studio {__version__} · 未命名项目[*]')
        self.setWindowModified(False)
        self.status.setText('新项目 · 导入扫描条开始')

    def duplicate_region(self):
        pair = self.current_region()
        if not pair: return
        document, region = pair
        rect = region.rect
        new_y = min(document.image.shape[0] - rect.height, rect.bottom + 5)
        self.add_region(CropRect(rect.x, max(0, new_y), rect.width, rect.height))

    def delete_region(self, key):
        pair = frame_lookup(self.documents).get(key)
        if not pair: return
        document, region = pair
        def change():
            document.regions.remove(region)
            self.order.remove(key)
            self.active_region_id = document.regions[0].id if document.regions else None
        self.change('删除裁切框', change)

    def remove_document(self):
        document = self.current_document()
        if not document: return
        def change():
            keys = {r.id for r in document.regions}
            self.documents.remove(document)
            self.order = [key for key in self.order if key not in keys]
            self.active_document_id = self.documents[0].id if self.documents else None
            self.active_region_id = None
        self.change('移除扫描条', change)

    def reverse_order(self):
        if self.order: self.change('反转帧序列', lambda: self.order.reverse())

    def inspect_region(self, key):
        if key and key in frame_lookup(self.documents): FrameDialog(self, key).exec()

    def export_options(self):
        if not hasattr(self, 'fps'): return {}
        return {'fps': self.fps.value(), 'width': self.output_width.value(), 'height': self.output_height.value(),
                'fit': 'fit' if self.fit_mode.currentIndex() == 0 else 'fill', 'codec': 'h264' if self.codec.currentIndex() == 0 else 'mp4v',
                'invert': self.invert.isChecked(), 'rotation': self.rotation.currentIndex() * 90}

    def options_changed(self):
        if self._refreshing: return
        self.setWindowModified(True)
        if self.documents:
            self.refresh_timeline()
            self.refresh_inspector()
        self.update_summary()
        if self.timer.isActive(): self.timer.setInterval(round(1000 / self.fps.value()))

    def apply_options(self, options):
        self._refreshing = True
        self.fps.setValue(options.get('fps', 12))
        self.output_width.setValue(options.get('width', 0))
        self.output_height.setValue(options.get('height', 0))
        self.fit_mode.setCurrentIndex(0 if options.get('fit', 'fit') == 'fit' else 1)
        self.codec.setCurrentIndex(0 if options.get('codec', 'h264') == 'h264' else 1)
        self.invert.setChecked(options.get('invert', False))
        self.rotation.setCurrentIndex(options.get('rotation', 0) // 90)
        self._refreshing = False

    def toggle_playback(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText('▶ 预演')
        else:
            if not ordered_regions(self.documents, self.order): return
            self.timer.start(round(1000 / self.fps.value()))
            self.play_button.setText('Ⅱ 暂停')
            self.next_playback_frame()

    def next_playback_frame(self):
        keys = [r.id for d, r in ordered_regions(self.documents, self.order)]
        if not keys:
            self.timer.stop()
            return
        index = (keys.index(self.active_region_id) + 1) % len(keys) if self.active_region_id in keys else 0
        for i in range(self.timeline.count()):
            item = self.timeline.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == keys[index]: self.timeline.setCurrentItem(item); break

    def run_job(self, function, callback):
        if self.job: return
        self.timer.stop()
        self.play_button.setText('▶ 预演')
        self.body.setEnabled(False)
        self.header.setEnabled(False)
        self.menuBar().setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.cancel_button.show()
        job = Worker(function, self)
        self.job = job
        job.progress.connect(lambda value, total, text: (self.progress.setValue(round(value / max(1, total) * 100)), self.status.setText(text)))
        job.finished.connect(lambda: self.finish_job(job, callback))
        job.start()

    def finish_job(self, job, callback):
        self.job = None
        self.body.setEnabled(True)
        self.header.setEnabled(True)
        self.menuBar().setEnabled(True)
        self.progress.hide()
        self.cancel_button.hide()
        if job.error:
            kind, message, details = job.error
            self.status.setText(message)
            if kind != 'cancel':
                dialog = QMessageBox(QMessageBox.Icon.Critical, '操作未完成', message, parent=self)
                dialog.setDetailedText(details)
                dialog.exec()
        else:
            try: callback(job.result)
            except Exception as error: self.error(str(error))
        job.deleteLater()

    def cancel_job(self):
        if self.job:
            self.job.cancelled.set()
            self.status.setText('正在取消；当前帧处理结束后清理临时输出…')

    def detection_settings(self):
        return DetectionSettings(sensitivity=['auto', 'low', 'high'][self.sensitivity.currentIndex()],
            polarity=['auto', 'dark', 'light'][self.polarity.currentIndex()],
            expected_count=self.expected_count.value(), frame_height=self.manual_height.value(),
            remove_perforations=self.holes.isChecked(), deskew=self.deskew.isChecked(),
            angle=self.angle.value(), inset=self.inset.value())

    def input_orientation(self): return ['auto', 'vertical', 'horizontal', 'horizontal-cw'][self.orientation.currentIndex()]

    def import_files(self):
        if self.job: return
        files, _ = QFileDialog.getOpenFileNames(self, '导入扫描条', self.last_directory, IMAGE_FILTER)
        if files: self.import_paths(files)

    def import_paths(self, files):
        existing = {d.path for d in self.documents}
        paths = sorted({str(Path(p).resolve()) for p in files if Path(p).suffix.lower() in IMAGE_SUFFIXES} - existing, key=natural_key)
        if not paths:
            self.status.setText('没有新的可导入图片；已存在的扫描条不会重复添加')
            return
        self.last_directory = str(Path(paths[0]).parent)
        settings, orientation = self.detection_settings(), self.input_orientation()
        def task(progress, cancelled):
            documents, analyses = [], []
            for index, path in enumerate(paths):
                if cancelled(): raise InterruptedError('导入已取消')
                progress(index, len(paths), f'识别 {index + 1}/{len(paths)} · {Path(path).name}')
                document, analysis = load_document(path, copy.deepcopy(settings), orientation)
                documents.append(document)
                analyses.append(analysis)
            return documents, analyses
        def done(result):
            documents, analyses = result
            def change():
                self.documents.extend(documents)
                self.order.extend(r.id for d in documents for r in d.regions)
                self.active_document_id = documents[0].id
                self.active_region_id = documents[0].regions[0].id if documents[0].regions else None
            self.change('导入扫描条', change)
            self.canvas.fit_all()
            self.set_analysis(analyses[0])
            self.status.setText(f'已导入 {len(documents)} 张扫描条，请校对裁切框后导出')
        self.run_job(task, done)

    def load_demo(self):
        folder = ROOT / 'assets' / 'demo'
        if not folder.exists():
            selected = QFileDialog.getExistingDirectory(self, '选择包含 demo 扫描图的文件夹', self.last_directory)
            if not selected: return
            folder = Path(selected)
        files = [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES] if folder.is_dir() else []
        if files: self.import_paths(files)
        else: self.status.setText('未找到合成示例，请选择 assets/demo 文件夹')

    def set_analysis(self, analysis):
        self.profile.profile, self.profile.threshold = analysis.profile, analysis.threshold
        self.profile.update()
        self.analysis_text.setText(f'{"浅色" if analysis.polarity == "light" else "深色"}阈值 {analysis.threshold:.1f} · {len(analysis.gutters)} 段分隔\n横向范围 {analysis.content_bounds[0]}–{analysis.content_bounds[1]} px · ' + ('成对齿孔' if analysis.perforations else '保留完整宽度'))

    def analyze(self, all_documents=False):
        if self.job or not self.documents: return
        targets = self.documents if all_documents else [self.current_document()]
        settings, orientation = self.detection_settings(), self.input_orientation()
        def task(progress, cancelled):
            result = []
            for index, old in enumerate(targets):
                if cancelled(): raise InterruptedError('重新识别已取消')
                progress(index, len(targets), f'重新识别 {index + 1}/{len(targets)} · {old.name}')
                result.append(load_document(old.path, copy.deepcopy(settings), orientation, old.id))
            return result
        def done(result):
            replaced = {document.id: document for document, analysis in result}
            def change():
                lookup = frame_lookup(self.documents)
                updated, inserted = [], set()
                for key in self.order:
                    source_id = lookup[key][0].id
                    if source_id not in replaced: updated.append(key)
                    elif source_id not in inserted:
                        updated.extend(r.id for r in replaced[source_id].regions)
                        inserted.add(source_id)
                for source_id, document in replaced.items():
                    if source_id not in inserted: updated.extend(r.id for r in document.regions)
                self.documents = [replaced.get(document.id, document) for document in self.documents]
                self.order = updated
                document = self.current_document()
                self.active_region_id = document.regions[0].id if document.regions else None
            self.change('重新识别裁切', change)
            self.canvas.fit_all()
            self.set_analysis(result[0][1])
            self.status.setText('候选框已更新；橙色标记帧请复查，可撤销此次识别')
        self.run_job(task, done)

    def needs_save(self):
        if not self.isWindowModified(): return True
        answer = QMessageBox.question(self, '项目尚未保存', '保存当前项目后继续？',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Cancel: return False
        if answer == QMessageBox.StandardButton.Save: return self.save()
        return True

    def save(self):
        if self.job: return False
        if not self.project_path: return self.save_as()
        try:
            save_project(self.project_path, self.documents, self.order, self.export_options())
            self.setWindowModified(False)
            self.status.setText(f'项目已保存 · {self.project_path}')
            return True
        except Exception as error:
            self.error(str(error))
            return False

    def save_as(self):
        if self.job: return False
        path, _ = QFileDialog.getSaveFileName(self, '保存项目（不包含源图片）', self.project_path or str(Path(self.last_directory) / '我的胶片电影.lomokino.json'), 'LomoKino 项目 (*.lomokino.json)')
        if not path: return False
        if not path.endswith('.lomokino.json'): path += '.lomokino.json'
        self.project_path = path
        self.setWindowTitle(f'LomoKino Studio {__version__} · {Path(path).name}[*]')
        return self.save()

    def open_project(self):
        if self.job or not self.needs_save(): return
        path, _ = QFileDialog.getOpenFileName(self, '打开 LomoKino 项目', self.last_directory, 'LomoKino 项目 (*.lomokino.json *.json)')
        if path: self.open_project_path(path)

    def open_project_path(self, path):
        replacements = {}
        # Resolve missing sources in the UI before loading on the worker thread.
        import json
        try:
            raw = json.loads(Path(path).read_text(encoding='utf-8'))
            for source in raw.get('sources', []):
                candidate = Path(source['path'])
                if not candidate.is_absolute(): candidate = Path(path).resolve().parent / candidate
                if not candidate.is_file():
                    replacement, _ = QFileDialog.getOpenFileName(self, f'重新定位源文件：{Path(source["path"]).name}', '', IMAGE_FILTER)
                    if not replacement: return
                    replacements[source['path']] = replacement
        except Exception as error: self.error(str(error)); return
        def task(progress, cancelled):
            progress(0, 1, '正在恢复项目与原图坐标…')
            result = load_project(path, replacements)
            if cancelled(): raise InterruptedError('打开项目已取消')
            return result
        def done(result):
            self.documents, self.order, options, warnings = result
            self.project_path = str(Path(path).resolve())
            self.apply_options(options)
            self.active_document_id = self.documents[0].id if self.documents else None
            self.active_region_id = self.order[0] if self.order else None
            pair = frame_lookup(self.documents).get(self.active_region_id)
            if pair: self.active_document_id = pair[0].id
            self.undo_stack.clear()
            self.refresh_all(True)
            self.setWindowTitle(f'LomoKino Studio {__version__} · {Path(path).name}[*]')
            self.setWindowModified(bool(replacements))
            self.status.setText('项目已恢复；' + ('；'.join(warnings) if warnings else '帧序列和裁切坐标已还原'))
        self.run_job(task, done)

    def export_movie(self):
        if self.job or not ordered_regions(self.documents, self.order): self.status.setText('请先导入并确认至少一帧'); return
        path, _ = QFileDialog.getSaveFileName(self, '导出当前确认序列', str(Path(self.last_directory) / 'lomokino_movie.mp4'), 'MP4 视频 (*.mp4)')
        if not path: return
        if not path.lower().endswith('.mp4'): path += '.mp4'
        self.last_directory = str(Path(path).parent)
        documents, order, options = list(self.documents), list(self.order), self.export_options()
        def task(progress, cancelled): return export_video(documents, order, path, options, progress, cancelled)
        def done(result):
            self.status.setText(f'视频已验证并保存 · {result["frames"]} 帧 · {result["width"]} × {result["height"]} · {result["seconds"]:.2f} 秒 · {path}')
            QMessageBox.information(self, '导出完成', self.status.text())
        self.run_job(task, done)

    def export_images(self, extension):
        if self.job or not ordered_regions(self.documents, self.order): self.status.setText('请先导入并确认至少一帧'); return
        parent = QFileDialog.getExistingDirectory(self, '选择导出父文件夹（将新建独立序列文件夹）', self.last_directory)
        if not parent: return
        self.last_directory = parent
        from datetime import datetime
        destination = Path(parent) / ('LomoKino_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + extension)
        documents, order, options = list(self.documents), list(self.order), self.export_options()
        def task(progress, cancelled): return export_sequence(documents, order, destination, options, extension, progress, cancelled)
        def done(count):
            self.status.setText(f'已导出 {count} 帧与 frames.json 裁切清单 · {destination}')
            QMessageBox.information(self, '图片序列已保存', self.status.text())
        self.run_job(task, done)

    def error(self, message): QMessageBox.critical(self, '操作未完成', message)

    def show_help(self):
        QMessageBox.information(self, '使用指南', '1. 导入扫描条，查看自动候选框。\n2. 在原图上拖动框或八个边角；右侧可输入像素坐标。\n3. 橙色帧为待复查，取消包含即可排除。\n4. 拖动下方缩略图排序，导出始终使用该序列。\n5. 保存 .lomokino.json 继续编辑；源图片需另外保留。\n\nCtrl / ⌘ + 滚轮缩放，空格拖动平移；方向键移动 1 px，Shift 10 px。\nCtrl / ⌘ + Z 撤销，Shift + Ctrl / ⌘ + Z 重做。\n自动识别不保证所有曝光和扫描条件下准确，导出前请逐帧校对。')

    def check_updates(self, manual=False):
        if not self.check_update_action.isEnabled():
            return
        self._manual_update_check = manual
        self.check_update_action.setEnabled(False)
        if manual:
            self.show_update_notice('正在检查更新…')
        self._update_check.start()

    def update_check_finished(self, tag):
        manual, self._manual_update_check = self._manual_update_check, False
        self.check_update_action.setEnabled(True)
        if is_newer_release(tag, __version__):
            self.show_update_notice(f'发现新版本 {tag}', QUrl(f'{PROJECT_URL}/releases/tag/{tag}'))
        elif manual:
            message = f'当前版本 v{__version__}，暂无更新' if tag else '暂时无法检查更新，请稍后重试'
            self.show_update_notice(message)

    def show_update_notice(self, message, page=None):
        self.update_message.setText(message)
        self.update_page = page
        self.update_download.setVisible(page is not None)
        self.update_notice.show()

    def open_update_page(self):
        if self.update_page is not None:
            QDesktopServices.openUrl(self.update_page)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        if self.job: return
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.import_paths(files)

    def closeEvent(self, event):
        if self.job:
            self.cancel_job()
            event.ignore()
            self.status.setText('任务正在取消，请等待清理完成后关闭窗口')
            return
        self.timer.stop()
        if self.needs_save():
            self._update_check.stop()
            event.accept()
        else:
            event.ignore()


def main(argv=None):
    parser = argparse.ArgumentParser(description='LomoKino Studio')
    parser.add_argument('files', nargs='*')
    parser.add_argument('--self-test', metavar='OUTPUT_FOLDER', help='验证打包依赖和 H.264 编码后退出')
    parser.add_argument('--demo', action='store_true', help='载入内置无人物合成扫描条')
    parser.add_argument('--project', help='打开 .lomokino.json 项目')
    parser.add_argument('--no-update-check', action='store_true', help='本次启动跳过自动检查更新')
    args = parser.parse_args(argv)
    if args.self_test:
        from .smoke import verify_package
        return verify_package(args.self_test)
    app = QApplication.instance()
    if app is None:
        if sys.platform == 'darwin' and not getattr(sys, 'frozen', False):
            from .macos import set_source_app_name
            set_source_app_name('LomoKino Studio')
        app = QApplication(sys.argv[:1])
    app.setApplicationName('LomoKino Studio')
    app.setApplicationVersion(__version__)
    app.setStyle('Fusion')
    palette = QPalette()
    for role, color in [(QPalette.ColorRole.Window, '#1b2329'), (QPalette.ColorRole.WindowText, '#e2e8e9'),
                        (QPalette.ColorRole.Base, '#11191e'), (QPalette.ColorRole.AlternateBase, '#25323b'),
                        (QPalette.ColorRole.Text, '#e2e8e9'), (QPalette.ColorRole.Button, '#29363f'),
                        (QPalette.ColorRole.ButtonText, '#e2e8e9'), (QPalette.ColorRole.Highlight, '#344a4c'),
                        (QPalette.ColorRole.HighlightedText, '#ffffff'), (QPalette.ColorRole.ToolTipBase, '#25323b'),
                        (QPalette.ColorRole.ToolTipText, '#edf1f1')]:
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    window = LomoKinoGUI()
    screen = app.primaryScreen().availableGeometry()
    window.resize(min(1560, screen.width() - 40), min(960, screen.height() - 60))
    window.show()
    if not args.no_update_check:
        QTimer.singleShot(0, window.check_updates)
    if args.project: QTimer.singleShot(0, lambda: window.open_project_path(args.project))
    elif args.demo: QTimer.singleShot(0, window.load_demo)
    elif args.files: QTimer.singleShot(0, lambda: window.import_paths(args.files))
    return app.exec()
