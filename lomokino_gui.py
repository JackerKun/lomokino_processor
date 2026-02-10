#!/usr/bin/env python3
"""
LomoKino GUI Application
A cross-platform GUI for processing LomoKino film strips into videos
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QGroupBox, QSlider, QSpinBox, QProgressBar, QMessageBox,
    QSplitter, QScrollArea, QGridLayout, QComboBox, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRect, QPoint, QMimeData
from PyQt6.QtGui import QPixmap, QIcon, QImage, QPainter, QPen, QColor, QDrag
import cv2
import numpy as np
from lomokino_processor import LomoKinoProcessor


class SelectionBox:
    """Represents a selection box for manual frame extraction"""

    def __init__(self, rect, index=0):
        self.rect = rect  # QRect
        self.index = index
        self.selected = False
        self.resize_edge = None  # Which edge is being resized: 'top', 'bottom', 'left', 'right'

    def contains_point(self, point):
        """Check if point is inside this box"""
        return self.rect.contains(point)

    def get_resize_edge(self, point, threshold=10):
        """Check if point is near an edge for resizing"""
        rect = self.rect

        # Check edges
        if abs(point.y() - rect.top()) < threshold:
            if abs(point.x() - rect.left()) < threshold:
                return 'top-left'
            elif abs(point.x() - rect.right()) < threshold:
                return 'top-right'
            return 'top'
        elif abs(point.y() - rect.bottom()) < threshold:
            if abs(point.x() - rect.left()) < threshold:
                return 'bottom-left'
            elif abs(point.x() - rect.right()) < threshold:
                return 'bottom-right'
            return 'bottom'
        elif abs(point.x() - rect.left()) < threshold:
            return 'left'
        elif abs(point.x() - rect.right()) < threshold:
            return 'right'

        return None

    def move_to(self, point):
        """Move box to new position (top-left corner)"""
        self.rect.moveTo(point)

    def move_by(self, dx, dy):
        """Move box by offset"""
        self.rect.translate(dx, dy)

    def resize(self, edge, dx, dy):
        """Resize box from specific edge"""
        if edge == 'top':
            self.rect.setTop(self.rect.top() + dy)
        elif edge == 'bottom':
            self.rect.setBottom(self.rect.bottom() + dy)
        elif edge == 'left':
            self.rect.setLeft(self.rect.left() + dx)
        elif edge == 'right':
            self.rect.setRight(self.rect.right() + dx)
        elif edge == 'top-left':
            self.rect.setTop(self.rect.top() + dy)
            self.rect.setLeft(self.rect.left() + dx)
        elif edge == 'top-right':
            self.rect.setTop(self.rect.top() + dy)
            self.rect.setRight(self.rect.right() + dx)
        elif edge == 'bottom-left':
            self.rect.setBottom(self.rect.bottom() + dy)
            self.rect.setLeft(self.rect.left() + dx)
        elif edge == 'bottom-right':
            self.rect.setBottom(self.rect.bottom() + dy)
            self.rect.setRight(self.rect.right() + dx)


class InteractiveFilmPreview(QLabel):
    """Interactive film preview with manual selection boxes"""

    boxes_changed = pyqtSignal()  # Signal when boxes change

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(300)
        self.setMaximumWidth(600)
        self.setMinimumHeight(400)
        self.setStyleSheet("""
            background-color: #333;
            color: white;
            border-radius: 5px;
        """)
        self.setText("选择胶片查看预览")

        self.original_pixmap = None
        self.display_pixmap = None
        self.current_image = None  # Store the actual image (cv2)
        self.selection_boxes = []  # List of SelectionBox objects
        self.selected_box = None
        self.dragging = False
        self.resizing = False
        self.resize_edge = None
        self.drag_start = None
        self.default_box_height = 100

        # Zoom functionality
        self.zoom_factor = 1.0
        self.min_zoom = 0.25  # Allow shrinking to 25% (half of container width)
        self.max_zoom = 5.0

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_image(self, image_path, cv_image=None):
        """Set the image to display"""
        self.original_pixmap = QPixmap(image_path)
        self.current_image = cv_image
        self.selection_boxes = []
        self.zoom_factor = 1.0  # Reset zoom when loading new image
        self.update_display()

    def set_zoom(self, zoom_factor):
        """Set zoom factor"""
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, zoom_factor))
        self.update_display()
        # Emit signal for UI update
        self.boxes_changed.emit()  # Reuse this signal to notify zoom change

    def zoom_in(self):
        """Zoom in by 25%"""
        self.set_zoom(self.zoom_factor * 1.25)

    def zoom_out(self):
        """Zoom out by 25%"""
        self.set_zoom(self.zoom_factor / 1.25)

    def zoom_reset(self):
        """Reset zoom to 100%"""
        self.set_zoom(1.0)

    def update_display(self):
        """Update the display with selection boxes"""
        if self.original_pixmap is None:
            return

        # Create a copy to draw on
        display_pixmap = self.original_pixmap.copy()

        # Draw selection boxes on the original size pixmap
        if self.selection_boxes:
            painter = QPainter(display_pixmap)

            for i, box in enumerate(self.selection_boxes):
                # Draw box
                if box.selected:
                    pen = QPen(QColor(0, 255, 0), 3)  # Green for selected
                else:
                    pen = QPen(QColor(255, 255, 0), 2)  # Yellow for normal
                painter.setPen(pen)
                painter.drawRect(box.rect)

                # Draw index number
                painter.setPen(QPen(QColor(255, 255, 255)))
                font = painter.font()
                font.setPointSize(12)
                painter.setFont(font)
                painter.drawText(box.rect.topLeft() + QPoint(5, 20), f"#{i+1}")

            painter.end()

        # Apply zoom factor
        zoomed_width = int(display_pixmap.width() * self.zoom_factor)
        zoomed_height = int(display_pixmap.height() * self.zoom_factor)

        # Scale the pixmap with zoom
        scaled = display_pixmap.scaled(
            zoomed_width,
            zoomed_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.display_pixmap = scaled
        self.setPixmap(scaled)

        # Adjust widget size to match pixmap (important for scroll area)
        self.resize(scaled.size())
        self.setMinimumSize(scaled.size())
        self.setMaximumSize(scaled.size())

        # Force scroll area to update its scroll bars
        self.updateGeometry()

    def add_box(self, y_position=None):
        """Add a new selection box"""
        if self.original_pixmap is None:
            return

        # Calculate box dimensions - use full width
        width = self.original_pixmap.width()  # Use full width
        height = self.default_box_height
        x = 0  # Start at left edge

        if y_position is None:
            # Place at bottom of last box or at top
            if self.selection_boxes:
                last_box = self.selection_boxes[-1]
                y = last_box.rect.bottom() + 10
            else:
                y = 50
        else:
            y = y_position

        rect = QRect(x, y, width, height)
        box = SelectionBox(rect, len(self.selection_boxes))
        self.selection_boxes.append(box)
        self.update_display()
        self.boxes_changed.emit()

    def duplicate_box(self, box_index):
        """Duplicate a selection box"""
        if 0 <= box_index < len(self.selection_boxes):
            original = self.selection_boxes[box_index]
            new_rect = QRect(original.rect)
            new_rect.translate(0, original.rect.height() + 10)
            new_box = SelectionBox(new_rect, len(self.selection_boxes))
            self.selection_boxes.append(new_box)
            self.update_display()
            self.boxes_changed.emit()

    def remove_box(self, box_index):
        """Remove a selection box"""
        if 0 <= box_index < len(self.selection_boxes):
            del self.selection_boxes[box_index]
            # Reindex remaining boxes
            for i, box in enumerate(self.selection_boxes):
                box.index = i
            self.update_display()
            self.boxes_changed.emit()

    def clear_boxes(self):
        """Clear all selection boxes"""
        self.selection_boxes = []
        self.selected_box = None
        self.update_display()
        self.boxes_changed.emit()

    def get_selected_regions(self):
        """Extract image regions from selection boxes"""
        if self.current_image is None or not self.selection_boxes:
            return []

        regions = []
        img_height, img_width = self.current_image.shape[:2]

        print(f"[DEBUG] Image size: {img_width} x {img_height}")
        print(f"[DEBUG] Total boxes: {len(self.selection_boxes)}")

        for i, box in enumerate(self.selection_boxes):
            # box.rect is already in original image coordinates
            # No need to scale again!
            x = box.rect.x()
            y = box.rect.y()
            w = box.rect.width()
            h = box.rect.height()

            print(f"[DEBUG] Box #{i+1}: x={x}, y={y}, w={w}, h={h}")

            # Clamp coordinates to image bounds
            x1 = max(0, min(x, img_width - 1))
            y1 = max(0, min(y, img_height - 1))
            x2 = max(0, min(x + w, img_width))
            y2 = max(0, min(y + h, img_height))

            # Check if region is valid
            if x2 > x1 and y2 > y1:
                region = self.current_image[y1:y2, x1:x2]
                if region.size > 0:
                    regions.append(region)
                    print(f"[DEBUG] ✓ Box #{i+1} extracted: {region.shape}")
                else:
                    print(f"[DEBUG] ✗ Box #{i+1} region is empty")
            else:
                print(f"[DEBUG] ✗ Box #{i+1} invalid coordinates: ({x1},{y1}) to ({x2},{y2})")

        print(f"[DEBUG] Successfully extracted {len(regions)} regions")
        return regions

    def get_scale_factors(self):
        """Get scale factors between display and original pixmap"""
        if self.original_pixmap is None or self.display_pixmap is None:
            return 1.0, 1.0

        scale_x = self.original_pixmap.width() / self.display_pixmap.width()
        scale_y = self.original_pixmap.height() / self.display_pixmap.height()
        return scale_x, scale_y

    def display_to_original_coords(self, point):
        """Convert display coordinates to original pixmap coordinates"""
        if self.original_pixmap is None or self.display_pixmap is None:
            return point  # Return as-is if no conversion possible

        scale_x, scale_y = self.get_scale_factors()

        # Account for centering offset
        x_offset = (self.width() - self.display_pixmap.width()) // 2
        y_offset = (self.height() - self.display_pixmap.height()) // 2

        display_x = point.x() - x_offset
        display_y = point.y() - y_offset

        original_x = int(display_x * scale_x)
        original_y = int(display_y * scale_y)

        return QPoint(original_x, original_y)

    def mousePressEvent(self, event):
        """Handle mouse press for dragging/resizing boxes"""
        if event.button() == Qt.MouseButton.LeftButton and self.selection_boxes:
            # Early return if no image loaded
            if self.original_pixmap is None or self.display_pixmap is None:
                return

            # Convert display coordinates to original coordinates
            original_point = self.display_to_original_coords(event.pos())

            # Find which box was clicked
            for box in self.selection_boxes:
                # Check if clicking on edge for resizing
                resize_edge = box.get_resize_edge(original_point)
                if resize_edge:
                    box.selected = True
                    self.selected_box = box
                    self.resizing = True
                    self.resize_edge = resize_edge
                    self.drag_start = original_point
                    self.update_display()
                    return
                # Check if clicking inside for moving
                elif box.contains_point(original_point):
                    box.selected = True
                    self.selected_box = box
                    self.dragging = True
                    self.drag_start = original_point
                    self.update_display()
                    return
                else:
                    box.selected = False
            self.update_display()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging/resizing boxes and cursor changes"""
        # Early return if no image loaded
        if self.original_pixmap is None or self.display_pixmap is None:
            return

        original_point = self.display_to_original_coords(event.pos())

        if self.resizing and self.selected_box:
            # Resize the box
            delta_x = original_point.x() - self.drag_start.x()
            delta_y = original_point.y() - self.drag_start.y()
            self.selected_box.resize(self.resize_edge, delta_x, delta_y)
            self.drag_start = original_point
            self.update_display()
        elif self.dragging and self.selected_box:
            # Move the box
            delta_x = original_point.x() - self.drag_start.x()
            delta_y = original_point.y() - self.drag_start.y()
            self.selected_box.move_by(delta_x, delta_y)
            self.drag_start = original_point
            self.update_display()
        else:
            # Update cursor based on hover position
            cursor = Qt.CursorShape.ArrowCursor
            for box in self.selection_boxes:
                edge = box.get_resize_edge(original_point)
                if edge:
                    # Set resize cursor based on edge
                    if edge in ['top', 'bottom']:
                        cursor = Qt.CursorShape.SizeVerCursor
                    elif edge in ['left', 'right']:
                        cursor = Qt.CursorShape.SizeHorCursor
                    elif edge in ['top-left', 'bottom-right']:
                        cursor = Qt.CursorShape.SizeFDiagCursor
                    elif edge in ['top-right', 'bottom-left']:
                        cursor = Qt.CursorShape.SizeBDiagCursor
                    break
                elif box.contains_point(original_point):
                    cursor = Qt.CursorShape.SizeAllCursor
                    break
            self.setCursor(cursor)

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resizing = False
            self.resize_edge = None

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if event.angleDelta().y() > 0:
            # Zoom in
            self.zoom_in()
        else:
            # Zoom out
            self.zoom_out()
        event.accept()


class ConfirmDialog(QDialog):
    """Custom confirmation dialog with visible buttons"""

    def __init__(self, parent=None, title="确认", message="确定要执行此操作吗?"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.result_value = False

        # Set minimum size to ensure buttons are visible
        self.setMinimumSize(400, 150)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Message label
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(message_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumSize(100, 35)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        cancel_btn.clicked.connect(self.on_cancel)
        button_layout.addWidget(cancel_btn)

        # Confirm button
        confirm_btn = QPushButton("确定")
        confirm_btn.setMinimumSize(100, 35)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        confirm_btn.clicked.connect(self.on_confirm)
        button_layout.addWidget(confirm_btn)

        layout.addLayout(button_layout)

    def on_confirm(self):
        """Handle confirm button click"""
        self.result_value = True
        self.accept()

    def on_cancel(self):
        """Handle cancel button click"""
        self.result_value = False
        self.reject()


class FrameViewerDialog(QDialog):
    """Dialog for viewing frames in full size with navigation"""

    def __init__(self, frames, current_index=0, parent=None):
        super().__init__(parent)
        self.frames = frames
        self.current_index = current_index
        self.setWindowTitle(f"帧 {current_index + 1} / {len(frames)}")
        self.setModal(True)
        self.setMinimumSize(800, 600)

        self.init_ui()
        self.show_current_frame()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Frame display label
        self.frame_label = QLabel()
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setStyleSheet("background-color: #000; border: 2px solid #333;")
        layout.addWidget(self.frame_label, stretch=1)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()

        prev_btn = QPushButton("⬅️ 上一帧")
        prev_btn.clicked.connect(self.show_previous)
        prev_btn.setMinimumSize(120, 40)
        prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        nav_layout.addWidget(prev_btn)
        self.prev_btn = prev_btn

        # Frame counter
        self.counter_label = QLabel()
        self.counter_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 0 20px;")
        nav_layout.addWidget(self.counter_label)

        next_btn = QPushButton("下一帧 ➡️")
        next_btn.clicked.connect(self.show_next)
        next_btn.setMinimumSize(120, 40)
        next_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        nav_layout.addWidget(next_btn)
        self.next_btn = next_btn

        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        # Close button
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumSize(100, 35)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def show_current_frame(self):
        """Display the current frame"""
        if 0 <= self.current_index < len(self.frames):
            frame = self.frames[self.current_index]

            # Convert numpy array to QPixmap
            height, width = frame.shape[:2]
            bytes_per_line = 3 * width
            if len(frame.shape) == 2:
                # Grayscale
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            else:
                # Color
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)

            # Scale to fit display while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.frame_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.frame_label.setPixmap(scaled_pixmap)

            # Update counter and title
            self.counter_label.setText(f"{self.current_index + 1} / {len(self.frames)}")
            self.setWindowTitle(f"帧 {self.current_index + 1} / {len(self.frames)}")

            # Update button states
            self.prev_btn.setEnabled(self.current_index > 0)
            self.next_btn.setEnabled(self.current_index < len(self.frames) - 1)

    def show_previous(self):
        """Show previous frame"""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_frame()

    def show_next(self):
        """Show next frame"""
        if self.current_index < len(self.frames) - 1:
            self.current_index += 1
            self.show_current_frame()

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key.Key_Left:
            self.show_previous()
        elif event.key() == Qt.Key.Key_Right:
            self.show_next()
        elif event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Handle resize to update frame display"""
        super().resizeEvent(event)
        self.show_current_frame()


class FilmStripListWidget(QListWidget):
    """List widget for film strip images"""

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setIconSize(QSize(80, 80))
        self.setMaximumWidth(250)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 5px;
            }
            QListWidget::item {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 8px;
                margin: 3px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border: 2px solid #2196f3;
            }
        """)

    def dragEnterEvent(self, event):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Handle drag move event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """Handle drop event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                    if self.main_window:
                        self.main_window.add_film(file_path)
        else:
            super().dropEvent(event)


class FrameThumbnail(QWidget):
    """Single frame thumbnail with delete button"""

    def __init__(self, frame, index, parent=None):
        super().__init__(parent)
        self.frame = frame
        self.index = index
        self.parent_widget = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Frame image container
        frame_container = QWidget()
        frame_layout = QVBoxLayout(frame_container)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Frame image
        frame_widget = QLabel()
        frame_widget.setFixedSize(120, 120)
        frame_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_widget.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #ddd;
                border-radius: 3px;
            }
        """)

        # Convert frame to QPixmap
        if len(self.frame.shape) == 3:
            h, w, ch = self.frame.shape
            bytes_per_line = ch * w
            rgb_frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
            q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            pixmap = pixmap.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio)
            frame_widget.setPixmap(pixmap)

        frame_layout.addWidget(frame_widget)

        # Delete button (overlay on top right)
        delete_btn = QPushButton("×")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        delete_btn.clicked.connect(self.delete_frame)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Position delete button at top right
        delete_btn.setParent(frame_container)
        delete_btn.move(100, 2)

        layout.addWidget(frame_container)

        # Frame label
        label = QLabel(f"帧 {self.index + 1}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 10px; color: #666; margin: 0; padding: 0;")
        label.setFixedHeight(16)
        layout.addWidget(label)

        self.setFixedSize(126, 140)

    def delete_frame(self):
        """Delete this frame"""
        if self.parent_widget:
            self.parent_widget.remove_frame(self.index)

    def mouseDoubleClickEvent(self, event):
        """Handle double click to view frame in full size"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.parent_widget:
                self.parent_widget.view_frame(self.index)
        super().mouseDoubleClickEvent(event)


class ExtractedFramesWidget(QWidget):
    """Widget to display extracted frames as draggable thumbnails"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames = []
        self.frame_widgets = []
        self.main_window = None  # Will be set by parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Scroll area for frames
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for frame thumbnails
        self.frames_container = QWidget()
        self.frames_layout = QGridLayout(self.frames_container)
        self.frames_layout.setSpacing(6)  # 减小网格间距到6px
        self.frames_layout.setContentsMargins(5, 5, 5, 5)  # 减小容器边距
        self.frames_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)  # 左上对齐

        scroll.setWidget(self.frames_container)
        layout.addWidget(scroll)

        self.setStyleSheet("""
            QWidget {
                background-color: #fafafa;
            }
        """)

    def set_frames(self, frames):
        """Display extracted frames"""
        # Clear previous frames
        for widget in self.frame_widgets:
            widget.deleteLater()
        self.frame_widgets.clear()

        self.frames = frames

        # Display frames in two columns (better space utilization)
        cols = 2  # Two columns to fit the area width without horizontal scrolling
        for i, frame in enumerate(frames):
            row = i // cols
            col = i % cols

            # Create frame thumbnail with delete button
            frame_thumb = FrameThumbnail(frame, i, self)

            self.frames_layout.addWidget(frame_thumb, row, col)
            self.frame_widgets.append(frame_thumb)

    def remove_frame(self, index):
        """Remove a frame by index"""
        dialog = ConfirmDialog(
            self,
            title="确认删除",
            message=f"确定要删除帧 {index + 1} 吗?"
        )
        dialog.exec()

        # 检查用户的选择
        if dialog.result_value:
            # Remove from frames list
            if 0 <= index < len(self.frames):
                del self.frames[index]

                # Update main window's frames
                if self.main_window:
                    self.main_window.current_frames = self.frames.copy()
                    self.main_window.update_stats()

                # Refresh display
                self.set_frames(self.frames)

                # Update info label
                if self.main_window:
                    self.main_window.frames_info_label.setText(f"成功提取 {len(self.frames)} 帧")

    def view_frame(self, index):
        """View frame in full size"""
        if 0 <= index < len(self.frames) and len(self.frames) > 0:
            # Create and show frame viewer dialog
            viewer = FrameViewerDialog(self.frames, index, self)
            viewer.exec()

    def clear_all_frames(self):
        """Clear all extracted frames"""
        if len(self.frames) == 0:
            return

        dialog = ConfirmDialog(
            self,
            title="确认清空",
            message=f"确定要清空所有 {len(self.frames)} 个帧吗？"
        )
        dialog.exec()

        if dialog.result_value:
            # Clear all frames
            self.frames.clear()

            # Update main window
            if self.main_window:
                self.main_window.current_frames = []
                self.main_window.update_stats()
                self.main_window.frames_info_label.setText("提取的帧将显示在这里\n可拖动帧来调整顺序")

            # Refresh display
            self.set_frames(self.frames)


class VideoProcessThread(QThread):
    """Thread for processing film strips to video"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, film_paths, output_path, params):
        super().__init__()
        self.film_paths = film_paths
        self.output_path = output_path
        self.params = params

    def run(self):
        try:
            self.progress.emit(10, "正在处理胶片图片...")

            # Get sensitivity setting
            sensitivity_map = {
                0: "auto",  # 自动
                1: "low",   # 低 (保守)
                2: "medium",  # 中 (推荐)
                3: "high"   # 高 (激进)
            }
            sensitivity = sensitivity_map.get(self.params.get('sensitivity', 0), "auto")
            min_distance = self.params.get('min_distance', 0)
            if min_distance == 0:
                min_distance = None

            processor = LomoKinoProcessor(
                frame_height=self.params.get('frame_height'),
                output_dir=os.path.dirname(self.output_path),
                min_frame_distance=min_distance,
                detection_sensitivity=sensitivity
            )

            all_frames = []

            # Process each film strip
            for i, film_path in enumerate(self.film_paths):
                self.progress.emit(
                    10 + int((i / len(self.film_paths)) * 60),
                    f"处理胶片 {i+1}/{len(self.film_paths)}"
                )

                # Load image
                image = cv2.imread(film_path)
                if image is None:
                    continue

                # Detect and extract frames
                frame_separators = processor.detect_frames(image)
                frames = processor.extract_frames(image, frame_separators)
                all_frames.extend(frames)

            if not all_frames:
                self.finished.emit(False, "没有提取到有效的帧")
                return

            self.progress.emit(70, f"共提取 {len(all_frames)} 帧，正在生成视频...")

            # Create video
            success = processor.create_video(
                all_frames,
                self.output_path,
                fps=self.params.get('fps', 12)
            )

            self.progress.emit(100, "完成!")

            if success:
                self.finished.emit(True, f"视频已保存到: {self.output_path}\n共包含 {len(all_frames)} 帧")
            else:
                self.finished.emit(False, "视频生成失败")

        except Exception as e:
            self.finished.emit(False, f"错误: {str(e)}")


class LomoKinoGUI(QMainWindow):
    """Main GUI window for LomoKino processor"""

    def __init__(self):
        super().__init__()
        self.film_paths = []
        self.current_film_index = -1
        self.current_frames = []
        self.processor = LomoKinoProcessor()
        self.params = {
            'fps': 12,
            'frame_height': None
        }
        self.setAcceptDrops(True)  # Enable drag and drop
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("LomoKino 胶片处理工具")
        self.setMinimumSize(1500, 900)  # 增加最小尺寸以适应左右布局

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left panel - Film strips list
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel)

        # Center panel - Preview and extracted frames
        center_panel = self.create_center_panel()
        main_layout.addWidget(center_panel, stretch=3)

        # Right panel - Parameters
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel)

        # Apply global stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #fafafa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
            QLabel {
                font-size: 13px;
            }
        """)

    def create_left_panel(self):
        """Create left panel with film strip list"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Title
        title = QLabel("胶片图片列表")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Hint
        hint = QLabel("添加胶片扫描图\n(每张图包含多个画面帧)\n\n💡 可拖拽文件到此处")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Film list
        self.film_list = FilmStripListWidget(parent=None, main_window=self)
        self.film_list.itemSelectionChanged.connect(self.on_film_selected)
        layout.addWidget(self.film_list)

        # Buttons
        btn_layout = QVBoxLayout()

        add_btn = QPushButton("➕ 添加胶片")
        add_btn.clicked.connect(self.add_films_dialog)
        btn_layout.addWidget(add_btn)

        remove_btn = QPushButton("➖ 移除选中")
        remove_btn.clicked.connect(self.remove_selected_film)
        btn_layout.addWidget(remove_btn)

        clear_btn = QPushButton("🗑️ 清空列表")
        clear_btn.clicked.connect(self.clear_films)
        clear_btn.setStyleSheet("background-color: #f44336;")
        btn_layout.addWidget(clear_btn)

        layout.addLayout(btn_layout)

        # Count label
        self.count_label = QLabel("胶片数量: 0")
        self.count_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.count_label)

        panel.setMaximumWidth(280)
        return panel

    def create_center_panel(self):
        """Create center panel with preview and extracted frames"""
        panel = QWidget()
        layout = QHBoxLayout(panel)  # 改为水平布局

        # Left side - Film preview (vertical)
        preview_group = QGroupBox("胶片预览")
        preview_layout = QVBoxLayout(preview_group)

        # Zoom controls
        zoom_controls = QHBoxLayout()

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setToolTip("缩小 (鼠标滚轮向下)")
        zoom_out_btn.setFixedSize(35, 35)
        zoom_out_btn.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        zoom_out_btn.clicked.connect(lambda: self.film_preview.zoom_out())
        zoom_controls.addWidget(zoom_out_btn)

        zoom_reset_btn = QPushButton("100%")
        zoom_reset_btn.setToolTip("重置缩放到100%")
        zoom_reset_btn.setFixedSize(50, 35)
        zoom_reset_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        zoom_reset_btn.clicked.connect(lambda: self.film_preview.zoom_reset())
        zoom_controls.addWidget(zoom_reset_btn)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("放大 (鼠标滚轮向上)")
        zoom_in_btn.setFixedSize(35, 35)
        zoom_in_btn.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        zoom_in_btn.clicked.connect(lambda: self.film_preview.zoom_in())
        zoom_controls.addWidget(zoom_in_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("font-size: 11px; color: #666; margin-left: 10px;")
        zoom_controls.addWidget(self.zoom_label)

        zoom_controls.addStretch()
        preview_layout.addLayout(zoom_controls)

        # Wrap preview in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(False)  # Important for zooming
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the image when small
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # Show horizontal scroll when needed
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Use interactive film preview
        self.film_preview = InteractiveFilmPreview()
        self.film_preview.boxes_changed.connect(self.on_boxes_changed)
        scroll_area.setWidget(self.film_preview)

        # Store scroll area reference
        self.preview_scroll_area = scroll_area

        preview_layout.addWidget(scroll_area, stretch=1)  # Give preview more space

        # Manual selection controls
        manual_controls = QGroupBox("手动选择框")
        manual_controls.setMaximumHeight(120)  # Limit height to compact size
        manual_layout = QVBoxLayout(manual_controls)
        manual_layout.setSpacing(4)
        manual_layout.setContentsMargins(6, 6, 6, 6)

        # Single row with all buttons (compact)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        add_box_btn = QPushButton("➕")
        add_box_btn.clicked.connect(self.add_selection_box)
        add_box_btn.setToolTip("添加选择框")
        add_box_btn.setFixedWidth(35)
        btn_row.addWidget(add_box_btn)

        duplicate_box_btn = QPushButton("📋")
        duplicate_box_btn.clicked.connect(self.duplicate_selection_box)
        duplicate_box_btn.setToolTip("复制选择框")
        duplicate_box_btn.setFixedWidth(35)
        btn_row.addWidget(duplicate_box_btn)

        remove_box_btn = QPushButton("🗑️")
        remove_box_btn.clicked.connect(self.remove_selection_box)
        remove_box_btn.setToolTip("删除选择框")
        remove_box_btn.setFixedWidth(35)
        btn_row.addWidget(remove_box_btn)

        clear_boxes_btn = QPushButton("🧹")
        clear_boxes_btn.clicked.connect(self.clear_selection_boxes)
        clear_boxes_btn.setToolTip("清空所有")
        clear_boxes_btn.setStyleSheet("background-color: #f44336;")
        clear_boxes_btn.setFixedWidth(35)
        btn_row.addWidget(clear_boxes_btn)

        btn_row.addStretch()
        manual_layout.addLayout(btn_row)

        # Extract button (wider)
        extract_manual_btn = QPushButton("✂️ 提取")
        extract_manual_btn.clicked.connect(self.extract_manual_regions)
        extract_manual_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        manual_layout.addWidget(extract_manual_btn)

        # Box count label (smaller)
        self.box_count_label = QLabel("框: 0")
        self.box_count_label.setStyleSheet("color: #666; font-size: 11px;")
        manual_layout.addWidget(self.box_count_label)

        preview_layout.addWidget(manual_controls, stretch=0)  # No stretch for controls

        layout.addWidget(preview_group, stretch=2)  # Preview gets 2x space (double width)

        # Right side - Extracted frames
        frames_group = QGroupBox("提取的帧")
        frames_layout = QVBoxLayout(frames_group)

        # Info and clear button row
        info_row = QHBoxLayout()

        self.frames_info_label = QLabel("提取的帧将显示在这里\n可拖动帧来调整顺序")
        self.frames_info_label.setStyleSheet("color: #666; font-style: italic;")
        info_row.addWidget(self.frames_info_label, stretch=1)

        # Clear all frames button
        clear_all_btn = QPushButton("🗑️ 清空所有帧")
        clear_all_btn.clicked.connect(self.clear_all_frames)
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff5722;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e64a19;
            }
        """)
        clear_all_btn.setToolTip("清空所有已提取的帧")
        info_row.addWidget(clear_all_btn)

        frames_layout.addLayout(info_row)

        self.extracted_frames_widget = ExtractedFramesWidget()
        self.extracted_frames_widget.main_window = self  # 设置主窗口引用
        frames_layout.addWidget(self.extracted_frames_widget)

        layout.addWidget(frames_group, stretch=1)  # Frames get 1x space (preview is 2x)

        return panel

    def create_right_panel(self):
        """Create right panel with parameters"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Parameters group
        params_group = QGroupBox("处理参数")
        params_layout = QVBoxLayout(params_group)

        # Frame height control
        frame_height_layout = QHBoxLayout()
        frame_height_layout.addWidget(QLabel("帧高度:"))

        self.auto_detect_radio = QPushButton("自动检测")
        self.auto_detect_radio.setCheckable(True)
        self.auto_detect_radio.setChecked(True)
        self.auto_detect_radio.clicked.connect(self.on_auto_detect_toggled)
        frame_height_layout.addWidget(self.auto_detect_radio)

        frame_height_layout.addWidget(QLabel("手动:"))
        self.frame_height_spin = QSpinBox()
        self.frame_height_spin.setRange(50, 1000)
        self.frame_height_spin.setValue(200)
        self.frame_height_spin.setEnabled(False)
        self.frame_height_spin.valueChanged.connect(self.on_frame_height_changed)
        frame_height_layout.addWidget(self.frame_height_spin)

        params_layout.addLayout(frame_height_layout)

        # FPS control
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("视频帧率 (FPS):"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(12)
        self.fps_spin.valueChanged.connect(self.on_fps_changed)
        fps_layout.addWidget(self.fps_spin)
        fps_layout.addStretch()
        params_layout.addLayout(fps_layout)

        # Detection sensitivity control
        sensitivity_layout = QHBoxLayout()
        sensitivity_layout.addWidget(QLabel("检测灵敏度:"))
        self.sensitivity_combo = QComboBox()
        self.sensitivity_combo.addItems(["自动", "低 (保守)", "中 (推荐)", "高 (激进)"])
        self.sensitivity_combo.setCurrentIndex(0)  # Default to "auto"
        self.sensitivity_combo.setToolTip("低: 适合小尺寸图片\n中: 适合大多数情况\n高: 检测更多帧")
        sensitivity_layout.addWidget(self.sensitivity_combo)
        sensitivity_layout.addStretch()
        params_layout.addLayout(sensitivity_layout)

        # Minimum frame distance control
        min_distance_layout = QHBoxLayout()
        min_distance_layout.addWidget(QLabel("最小帧间距:"))
        self.min_distance_spin = QSpinBox()
        self.min_distance_spin.setRange(0, 200)
        self.min_distance_spin.setValue(0)
        self.min_distance_spin.setSuffix(" px")
        self.min_distance_spin.setSpecialValueText("自动")
        self.min_distance_spin.setToolTip("帧之间的最小距离，0表示自动")
        min_distance_layout.addWidget(self.min_distance_spin)
        min_distance_layout.addStretch()
        params_layout.addLayout(min_distance_layout)

        layout.addWidget(params_group)

        # Info group
        info_group = QGroupBox("统计信息")
        info_layout = QVBoxLayout(info_group)

        self.total_frames_label = QLabel("总帧数: 0")
        self.total_frames_label.setStyleSheet("color: #333; font-size: 14px;")
        info_layout.addWidget(self.total_frames_label)

        self.video_duration_label = QLabel("预计时长: 0 秒")
        self.video_duration_label.setStyleSheet("color: #666; font-size: 12px;")
        info_layout.addWidget(self.video_duration_label)

        layout.addWidget(info_group)

        # Process button
        process_btn = QPushButton("🎬 提取所有帧")
        process_btn.clicked.connect(self.process_current_film)
        process_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                font-size: 14px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        layout.addWidget(process_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Generate video button
        self.generate_btn = QPushButton("🎥 生成视频")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                font-size: 16px;
                padding: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_video)
        self.generate_btn.setEnabled(False)
        layout.addWidget(self.generate_btn)

        layout.addStretch()

        panel.setMaximumWidth(350)
        return panel

    def add_films_dialog(self):
        """Open file dialog to add film strips"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择胶片扫描图",
            "",
            "图片文件 (*.jpg *.jpeg *.png)"
        )
        for file in files:
            self.add_film(file)

    def add_film(self, file_path):
        """Add a film strip to the list"""
        if file_path in self.film_paths:
            return

        self.film_paths.append(file_path)

        # Create list item
        item = QListWidgetItem()

        # Create thumbnail
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio)
            item.setIcon(QIcon(pixmap))

        item.setText(Path(file_path).name)
        item.setData(Qt.ItemDataRole.UserRole, file_path)

        self.film_list.addItem(item)
        self.update_count_label()

    def remove_selected_film(self):
        """Remove selected film from list"""
        current_item = self.film_list.currentItem()
        if current_item:
            file_path = current_item.data(Qt.ItemDataRole.UserRole)
            self.film_paths.remove(file_path)
            self.film_list.takeItem(self.film_list.row(current_item))
            self.update_count_label()

            # Clear preview if this was the selected film
            if self.film_list.count() == 0:
                self.film_preview.clear()
                self.film_preview.setText("选择胶片查看预览")
                self.extracted_frames_widget.set_frames([])
                self.current_frames = []
                self.current_film_index = -1
                self.update_stats()
                self.generate_btn.setEnabled(False)

    def clear_films(self):
        """Clear all films"""
        dialog = ConfirmDialog(
            self,
            title="确认清空",
            message="确定要清空所有胶片吗?"
        )
        dialog.exec()

        if dialog.result_value:
            # Disconnect signal temporarily to avoid errors
            self.film_list.itemSelectionChanged.disconnect(self.on_film_selected)

            # Clear data
            self.film_paths.clear()
            self.film_list.clear()
            self.current_film_index = -1
            self.film_preview.clear()
            self.film_preview.setText("选择胶片查看预览")
            self.extracted_frames_widget.set_frames([])
            self.current_frames = []
            self.update_count_label()
            self.update_stats()
            self.generate_btn.setEnabled(False)

            # Reconnect signal
            self.film_list.itemSelectionChanged.connect(self.on_film_selected)

    def on_film_selected(self):
        """Handle film selection"""
        current_item = self.film_list.currentItem()
        if current_item:
            file_path = current_item.data(Qt.ItemDataRole.UserRole)
            self.show_film_preview(file_path)
            # Check if file_path still exists in list before getting index
            if file_path in self.film_paths:
                self.current_film_index = self.film_paths.index(file_path)
            else:
                self.current_film_index = -1

    def show_film_preview(self, file_path):
        """Show preview of selected film strip"""
        # Load image with OpenCV for processing
        cv_image = cv2.imread(file_path)
        if cv_image is not None:
            self.film_preview.set_image(file_path, cv_image)

    def add_selection_box(self):
        """Add a new selection box"""
        self.film_preview.add_box()

    def duplicate_selection_box(self):
        """Duplicate the selected box"""
        if self.film_preview.selected_box:
            index = self.film_preview.selection_boxes.index(self.film_preview.selected_box)
            self.film_preview.duplicate_box(index)
        else:
            QMessageBox.warning(self, "提示", "请先选择一个选择框（点击黄色框）")

    def remove_selection_box(self):
        """Remove the selected box"""
        if self.film_preview.selected_box:
            dialog = ConfirmDialog(
                self,
                title="确认删除",
                message="确定要删除选中的选择框吗?"
            )
            dialog.exec()

            if dialog.result_value:
                index = self.film_preview.selection_boxes.index(self.film_preview.selected_box)
                self.film_preview.remove_box(index)
        else:
            QMessageBox.warning(self, "提示", "请先选择一个选择框（点击黄色框）")

    def clear_selection_boxes(self):
        """Clear all selection boxes"""
        if not self.film_preview.selection_boxes:
            return

        dialog = ConfirmDialog(
            self,
            title="确认清空",
            message="确定要清空所有选择框吗?"
        )
        dialog.exec()

        if dialog.result_value:
            self.film_preview.clear_boxes()

    def extract_manual_regions(self):
        """Extract frames from manual selection boxes and append to existing frames"""
        regions = self.film_preview.get_selected_regions()

        if not regions:
            QMessageBox.warning(self, "警告", "没有选择框或无法提取帧！\n请先添加选择框并调整位置。")
            return

        # Append to existing frames instead of replacing
        if not hasattr(self, 'current_frames') or self.current_frames is None:
            self.current_frames = []

        original_count = len(self.current_frames)
        self.current_frames.extend(regions)
        new_count = len(self.current_frames)

        # Update display with all frames
        self.extracted_frames_widget.set_frames(self.current_frames)
        self.frames_info_label.setText(
            f"总共 {new_count} 帧（新增 {len(regions)} 帧，原有 {original_count} 帧）"
        )
        self.status_label.setText(f"手动提取了 {len(regions)} 帧，总计 {new_count} 帧")

        # Update stats
        self.update_stats()

        # Enable generate button
        self.generate_btn.setEnabled(True)

    def clear_all_frames(self):
        """Clear all extracted frames"""
        if self.extracted_frames_widget:
            self.extracted_frames_widget.clear_all_frames()

    def on_boxes_changed(self):
        """Handle selection boxes change and zoom updates"""
        count = len(self.film_preview.selection_boxes)
        self.box_count_label.setText(f"框: {count}")

        # Update zoom label
        zoom_percent = int(self.film_preview.zoom_factor * 100)
        self.zoom_label.setText(f"{zoom_percent}%")

    def process_current_film(self):
        """Process all film strips and extract frames"""
        if not self.film_paths:
            QMessageBox.warning(self, "警告", "请先添加胶片!")
            return

        try:
            # Update processor parameters
            if not self.auto_detect_radio.isChecked():
                self.processor.frame_height = self.frame_height_spin.value()
            else:
                self.processor.frame_height = None

            # Get detection sensitivity
            sensitivity_map = {
                0: "auto",    # 自动
                1: "low",     # 低 (保守)
                2: "medium",  # 中 (推荐)
                3: "high"     # 高 (激进)
            }
            sensitivity = sensitivity_map.get(self.sensitivity_combo.currentIndex(), "auto")
            self.processor.detection_sensitivity = sensitivity

            # Get minimum frame distance
            min_distance = self.min_distance_spin.value()
            if min_distance == 0:
                self.processor.min_frame_distance = None
            else:
                self.processor.min_frame_distance = min_distance

            all_frames = []

            # Show progress
            self.status_label.setText("正在处理胶片...")
            QApplication.processEvents()

            # Process each film strip
            for i, film_path in enumerate(self.film_paths):
                self.status_label.setText(f"正在处理胶片 {i+1}/{len(self.film_paths)}...")
                QApplication.processEvents()

                # Load image
                image = cv2.imread(film_path)
                if image is None:
                    continue

                # Detect and extract frames
                frame_separators = self.processor.detect_frames(image)
                frames = self.processor.extract_frames(image, frame_separators)
                all_frames.extend(frames)

            if not all_frames:
                QMessageBox.warning(self, "警告", "没有检测到有效的帧!")
                self.status_label.setText("")
                return

            # Store and display frames
            self.current_frames = all_frames
            self.extracted_frames_widget.set_frames(all_frames)
            self.frames_info_label.setText(f"成功提取 {len(all_frames)} 帧")
            self.status_label.setText(f"从 {len(self.film_paths)} 张胶片提取了 {len(all_frames)} 帧")

            # Update stats
            self.update_stats()

            # Enable generate button
            self.generate_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")
            self.status_label.setText("")

    def generate_video(self):
        """Generate video from all film strips"""
        if not self.film_paths:
            QMessageBox.warning(self, "警告", "请先添加胶片!")
            return

        # Ask for output file
        output_file, _ = QFileDialog.getSaveFileName(
            self,
            "保存视频",
            "lomokino_output.mp4",
            "视频文件 (*.mp4)"
        )

        if not output_file:
            return

        # Update params with current settings
        self.params['sensitivity'] = self.sensitivity_combo.currentIndex()
        self.params['min_distance'] = self.min_distance_spin.value()

        # Disable UI during processing
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Start processing thread
        self.process_thread = VideoProcessThread(
            self.film_paths,
            output_file,
            self.params
        )
        self.process_thread.progress.connect(self.on_progress)
        self.process_thread.finished.connect(self.on_finished)
        self.process_thread.start()

    def on_auto_detect_toggled(self, checked):
        """Handle auto detect toggle"""
        self.frame_height_spin.setEnabled(not checked)
        if checked:
            self.params['frame_height'] = None
        else:
            self.params['frame_height'] = self.frame_height_spin.value()

    def on_frame_height_changed(self, value):
        """Handle frame height change"""
        if not self.auto_detect_radio.isChecked():
            self.params['frame_height'] = value

    def on_fps_changed(self, value):
        """Handle FPS change"""
        self.params['fps'] = value
        self.update_stats()

    def update_count_label(self):
        """Update film count label"""
        self.count_label.setText(f"胶片数量: {len(self.film_paths)}")

    def update_stats(self):
        """Update statistics"""
        total_frames = len(self.current_frames)
        self.total_frames_label.setText(f"总帧数: {total_frames}")

        if total_frames > 0 and self.params['fps'] > 0:
            duration = total_frames / self.params['fps']
            self.video_duration_label.setText(f"预计时长: {duration:.1f} 秒")
        else:
            self.video_duration_label.setText("预计时长: 0 秒")

    def on_progress(self, value, message):
        """Handle progress updates"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def on_finished(self, success, message):
        """Handle processing completion"""
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)

        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "错误", message)

        self.status_label.setText("")

    def dragEnterEvent(self, event):
        """Handle drag enter event for main window"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Handle drag move event for main window"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop event for main window"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                    self.add_film(file_path)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = LomoKinoGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
