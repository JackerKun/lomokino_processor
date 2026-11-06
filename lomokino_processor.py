#!/usr/bin/env python3
"""LomoKino Studio command line and legacy processor adapter."""
import argparse
import glob
import json
from pathlib import Path
import sys
import numpy as np
from lomokino.detection import detect
from lomokino.models import DetectionSettings, FilmDocument, FrameRegion, CropRect
from lomokino.engine import (load_document, load_project, save_project, export_sequence,
                             export_video, frame_image, natural_key)


class LomoKinoProcessor:
    def __init__(self, frame_height=None, output_dir='output', min_frame_distance=None,
                 sensitivity='auto', fps=12, codec='h264'):
        self.frame_height = frame_height
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_frame_distance = min_frame_distance
        self.sensitivity = sensitivity
        self.fps, self.codec = fps, codec
        self._source = self._result = None

    def detect_frames(self, image):
        self._source = image
        self._result = detect(image, DetectionSettings(frame_height=self.frame_height or 0,
            min_frame_distance=self.min_frame_distance or 0, sensitivity=self.sensitivity))
        regions = self._result.regions
        return [regions[0].rect.y] + [(a.rect.bottom + b.rect.y) // 2 for a, b in zip(regions, regions[1:])] + [regions[-1].rect.bottom]

    def extract_frames(self, image, boundaries):
        if image is self._source and self._result is not None:
            return [r.rect.crop(self._result.image) for r in self._result.regions]
        return [image[max(0, int(a)):min(image.shape[0], int(b))].copy()
                for a, b in zip(boundaries, boundaries[1:]) if b > a]

    def detect_content_boundaries(self, frame):
        return 0, frame.shape[1]

    def create_video(self, frames, output_path, fps=None):
        documents = [FilmDocument('', image, [FrameRegion(CropRect(0, 0, image.shape[1], image.shape[0]))]) for image in frames]
        export_video(documents, [r.id for d in documents for r in d.regions], output_path,
                     {'fps': self.fps if fps is None else fps, 'codec': self.codec})
        return True

    def process_image(self, image_path):
        document, _ = load_document(image_path, DetectionSettings(frame_height=self.frame_height or 0,
            min_frame_distance=self.min_frame_distance or 0, sensitivity=self.sensitivity))
        order = [r.id for r in document.regions]
        stem = Path(image_path).stem
        export_sequence([document], order, self.output_dir / (stem + '_frames'))
        export_video([document], order, self.output_dir / (stem + '_video.mp4'), {'fps': self.fps, 'codec': self.codec})
        return True

    def process_multiple_images(self, image_paths):
        results = [self.process_image(path) for path in sorted(image_paths, key=natural_key)]
        return all(results)


def main(argv=None):
    parser = argparse.ArgumentParser(description='扫描胶片 → 可复查裁切 → PNG/JPEG 序列与 MP4')
    parser.add_argument('images', nargs='*')
    parser.add_argument('--project', help='读取 GUI 保存的工程，使用其裁切和顺序')
    parser.add_argument('--output-dir', '-o', default='output')
    parser.add_argument('--fps', type=float, default=None)
    parser.add_argument('--frame-height', type=int, default=0)
    parser.add_argument('--expected-count', type=int, default=0)
    parser.add_argument('--sensitivity', choices=['auto', 'low', 'high'], default='auto')
    parser.add_argument('--polarity', choices=['auto', 'dark', 'light'], default='auto')
    parser.add_argument('--orientation', choices=['auto', 'vertical', 'horizontal', 'horizontal-cw'], default='auto')
    parser.add_argument('--deskew', action='store_true')
    parser.add_argument('--angle', type=float, default=0)
    parser.add_argument('--inset', type=int, default=0)
    parser.add_argument('--codec', choices=['h264', 'mp4v'], default=None)
    parser.add_argument('--invert', action='store_true', default=None)
    parser.add_argument('--frames-only', action='store_true')
    parser.add_argument('--format', choices=['png', 'jpg'], default='png')
    args = parser.parse_args(argv)
    if args.project and args.images: parser.error('--project 与输入扫描图请二选一')
    try:
        if args.project:
            documents, order, options, _ = load_project(args.project)
        else:
            paths = []
            for pattern in args.images:
                paths.extend(glob.glob(pattern) or [pattern])
            paths = sorted(dict.fromkeys(paths), key=natural_key)
            if not paths: parser.error('请传入扫描图，或使用 --project')
            settings = DetectionSettings(sensitivity=args.sensitivity, polarity=args.polarity,
                frame_height=args.frame_height, expected_count=args.expected_count,
                deskew=args.deskew, angle=args.angle, inset=args.inset)
            documents = [load_document(p, settings, args.orientation)[0] for p in paths]
            order = [r.id for d in documents for r in d.regions]
            options = {}
        for key in ('fps', 'codec', 'invert'):
            if getattr(args, key) is not None: options[key] = getattr(args, key)
        options.setdefault('fps', 12)
        options.setdefault('codec', 'h264')
        destination = Path(args.output_dir)
        count = export_sequence(documents, order, destination / 'frames', options, args.format)
        save_project(destination / 'project.lomokino.json', documents, order, options)
        summary = {'frames': count, 'sequence': str(destination / 'frames')}
        if not args.frames_only:
            summary['video'] = export_video(documents, order, destination / 'movie.mp4', options)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(f'处理失败：{error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
