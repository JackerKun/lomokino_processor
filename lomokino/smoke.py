"""Headless check usable inside a frozen app without a display server."""
from pathlib import Path
import json
import numpy as np
from .models import CropRect, FrameRegion, FilmDocument
from .engine import export_video, export_sequence, read_image


def verify_package(destination):
    folder = Path(destination)
    folder.mkdir(parents=True, exist_ok=True)
    image = np.full((80, 240, 3), (40, 120, 180), dtype=np.uint8)
    document = FilmDocument('self-test', image, [FrameRegion(CropRect(0, 0, 240, 80)) for _ in range(3)])
    order = [r.id for r in document.regions]
    try:
        result = export_video([document], order, folder / 'package-test.mp4', {'fps': 6})
        export_sequence([document], order, folder / 'frames')
        assert read_image(folder / 'frames/frame_00001.png').shape == image.shape
        (folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return 0
    except Exception as error:
        (folder / 'error.txt').write_text(str(error), encoding='utf-8')
        return 1
