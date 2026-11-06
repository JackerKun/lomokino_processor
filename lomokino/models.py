"""Pixel geometry uses half-open bounds: [x, x + width), [y, y + height)."""
from dataclasses import dataclass, field, asdict
from math import floor, ceil
from pathlib import Path
import uuid
import numpy as np


@dataclass(frozen=True)
class CropRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self): return self.x + self.width
    @property
    def bottom(self): return self.y + self.height

    def clamp(self, width, height):
        x1, y1 = max(0, min(self.x, width)), max(0, min(self.y, height))
        x2, y2 = max(x1, min(self.right, width)), max(y1, min(self.bottom, height))
        return CropRect(x1, y1, x2 - x1, y2 - y1)

    @classmethod
    def from_edges(cls, x1, y1, x2, y2):
        # Snap pixel-edge geometry consistently for preview, project and export.
        x, y, right, bottom = map(lambda n: int(round(n)), (x1, y1, x2, y2))
        return cls(min(x, right), min(y, bottom), abs(right - x), abs(bottom - y))

    def crop(self, image):
        rect = self.clamp(image.shape[1], image.shape[0])
        if rect.width < 1 or rect.height < 1:
            raise ValueError("裁切区域为空，请检查坐标")
        return image[rect.y:rect.bottom, rect.x:rect.right].copy()


@dataclass
class FrameRegion:
    rect: CropRect
    confidence: float = 1.0
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    note: str = ""
    reviewed: bool = False

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data):
        return cls(rect=CropRect(**data['rect']), confidence=float(data.get('confidence', 1)),
                   enabled=bool(data.get('enabled', True)), id=data.get('id', uuid.uuid4().hex),
                   note=data.get('note', ''), reviewed=bool(data.get('reviewed', False)))


@dataclass
class DetectionSettings:
    sensitivity: str = "auto"
    polarity: str = "auto"
    threshold: float = 0  # zero selects a measured strip-specific threshold
    expected_count: int = 0
    frame_height: int = 0
    min_frame_distance: int = 0
    remove_perforations: bool = True
    deskew: bool = False
    angle: float = 0
    inset: int = 0


@dataclass
class FilmDocument:
    path: str
    image: np.ndarray
    regions: list[FrameRegion]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    angle: float = 0
    orientation: str = "vertical"
    warnings: list[str] = field(default_factory=list)
    settings: DetectionSettings = field(default_factory=DetectionSettings)
    fingerprint: dict = field(default_factory=dict)

    @property
    def name(self): return Path(self.path).name


def resize_rect(rect, handle, dx, dy, image_width, image_height, minimum=2):
    """Resize in source-pixel coordinates without inversion or escaping image bounds."""
    x1, y1, x2, y2 = rect.x, rect.y, rect.right, rect.bottom
    if 'left' in handle: x1 = max(0, min(x2 - minimum, round(x1 + dx)))
    if 'right' in handle: x2 = min(image_width, max(x1 + minimum, round(x2 + dx)))
    if 'top' in handle: y1 = max(0, min(y2 - minimum, round(y1 + dy)))
    if 'bottom' in handle: y2 = min(image_height, max(y1 + minimum, round(y2 + dy)))
    return CropRect(x1, y1, x2 - x1, y2 - y1)
