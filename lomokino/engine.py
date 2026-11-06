"""Source loading, editable project state and atomic sequence/video export."""
from dataclasses import asdict
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import cv2
import numpy as np
from .models import CropRect, FrameRegion, DetectionSettings, FilmDocument
from .detection import detect

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp'}
PROJECT_VERSION = 1


def natural_key(value):
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r'(\d+)', str(value))]


def read_image(path):
    path = Path(path)
    try:
        data = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
    except (OSError, cv2.error) as error:
        raise ValueError(f'无法读取 {path.name}：{error}') from error
    if image is None or image.size == 0: raise ValueError(f'图片格式不支持或文件损坏：{path.name}')
    if image.dtype not in (np.uint8, np.uint16): raise ValueError('目前支持 8 / 16 位整数扫描图')
    return image


def to8(image):
    return image if image.dtype == np.uint8 else np.rint(image.astype(np.float64) / 257).clip(0, 255).astype(np.uint8)


def load_document(path, settings=None, orientation='auto', document_id=None):
    settings = settings or DetectionSettings()
    path = Path(path).resolve()
    image = read_image(path)
    warnings = []
    if orientation == 'auto': orientation = 'horizontal' if image.shape[1] > image.shape[0] else 'vertical'
    if orientation == 'horizontal':
        image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        warnings.append('横向扫描已逆时针旋转 90°；请检查画面方向与序列顺序')
    elif orientation == 'horizontal-cw': image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    result = detect(image, settings)
    image = result.image
    image.setflags(write=False)
    stat = path.stat()
    document = FilmDocument(str(path), image, result.regions, angle=result.angle, orientation=orientation,
                            warnings=warnings + result.warnings, settings=settings,
                            fingerprint={'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns})
    if document_id: document.id = document_id
    return document, result


def transform_frame(image, invert=False, rotation=0):
    if invert:
        maximum = np.iinfo(image.dtype).max
        image = maximum - image
    rotation %= 360
    if rotation == 90: return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180: return cv2.rotate(image, cv2.ROTATE_180)
    if rotation == 270: return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def frame_lookup(documents):
    return {region.id: (document, region) for document in documents for region in document.regions}


def ordered_regions(documents, order, enabled_only=True):
    lookup = frame_lookup(documents)
    return [lookup[key] for key in order if key in lookup and (not enabled_only or lookup[key][1].enabled)]


def frame_image(document, region, options=None):
    options = options or {}
    return transform_frame(region.rect.crop(document.image), options.get('invert', False), options.get('rotation', 0))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def project_data(documents, order, options, base=None):
    sources = []
    for document in documents:
        path = document.path
        if base:
            try: path = Path(os.path.relpath(path, base)).as_posix()
            except ValueError: pass  # Windows drive mismatch: retain absolute path.
        sources.append({'id': document.id, 'path': path, 'fingerprint': document.fingerprint,
                        'settings': asdict(document.settings), 'orientation': document.orientation,
                        'applied_angle': document.angle, 'regions': [r.to_dict() for r in document.regions]})
    return {'format': 'lomokino-studio', 'version': PROJECT_VERSION, 'sources': sources,
            'frame_order': list(order), 'export': dict(options)}


def save_project(path, documents, order, options):
    atomic_json(path, project_data(documents, order, options, Path(path).resolve().parent))


class MissingSources(FileNotFoundError):
    def __init__(self, paths):
        self.paths = paths
        super().__init__('缺少源文件：' + '、'.join(Path(p).name for p in paths))


def load_project(path, replacements=None):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('format') != 'lomokino-studio' or data.get('version') != PROJECT_VERSION:
        raise ValueError('不是支持的 LomoKino Studio 项目文件')
    replacements = replacements or {}
    missing, resolved = [], []
    for source in data['sources']:
        original = source['path']
        candidate = Path(replacements.get(original, original))
        if not candidate.is_absolute(): candidate = path.parent / candidate
        if not candidate.is_file(): missing.append(original)
        resolved.append(candidate)
    if missing: raise MissingSources(missing)
    documents, warnings, seen = [], [], set()
    for source, candidate in zip(data['sources'], resolved):
        settings = DetectionSettings(**source.get('settings', {}))
        # Reuse the angle chosen at save time; do not rerun auto deskew on reopen.
        settings.angle = float(source.get('applied_angle', settings.angle))
        automatic = settings.deskew
        settings.deskew = False
        document, _ = load_document(candidate, settings, source.get('orientation', 'vertical'), source['id'])
        settings.deskew = automatic
        document.regions = [FrameRegion.from_dict(r) for r in source['regions']]
        for region in document.regions:
            if region.id in seen: raise ValueError('项目中出现重复帧 ID')
            seen.add(region.id)
            clamped = region.rect.clamp(document.image.shape[1], document.image.shape[0])
            if clamped != region.rect or clamped.width < 2 or clamped.height < 2:
                raise ValueError(f'{candidate.name} 的裁切超出图像范围，请重新定位源文件')
        if document.fingerprint != source.get('fingerprint', {}):
            document.warnings.append('源文件大小或修改时间已变化，请复查裁切')
            warnings.append(f'{candidate.name}：源文件变化')
        documents.append(document)
    order = data['frame_order']
    if len(order) != len(set(order)) or set(order) != seen:
        raise ValueError('项目帧序列与裁切记录不一致')
    return documents, order, data.get('export', {}), warnings


def write_image(path, image, quality=95):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in ('.jpg', '.jpeg'): image = to8(image)
    ok, data = cv2.imencode(suffix, image, [cv2.IMWRITE_JPEG_QUALITY, quality] if suffix in ('.jpg', '.jpeg') else [])
    if not ok: raise RuntimeError(f'编码图片失败：{path.name}')
    path.write_bytes(data.tobytes())


def export_sequence(documents, order, destination, options=None, extension='png', progress=None, cancelled=None):
    if extension not in ('png', 'jpg', 'jpeg'): raise ValueError('序列格式仅支持 PNG / JPEG')
    selected = ordered_regions(documents, order)
    if not selected: raise ValueError('没有可导出的已启用帧')
    destination = Path(destination)
    if destination.exists(): raise FileExistsError('为避免覆盖，请选择新的导出文件夹')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.lomokino-frames-', dir=destination.parent))
    try:
        records = []
        for index, (document, region) in enumerate(selected):
            if cancelled and cancelled(): raise InterruptedError('导出已取消，未写入最终文件夹')
            name = f'frame_{index + 1:05d}.{extension}'
            image = frame_image(document, region, options)
            write_image(stage / name, image)
            records.append({'file': name, 'source': document.path, 'rect': asdict(region.rect),
                            'working_size': [document.image.shape[1], document.image.shape[0]],
                            'source_orientation': document.orientation, 'deskew_angle': document.angle,
                            'frame_rotation': (options or {}).get('rotation', 0),
                            'invert': (options or {}).get('invert', False), 'region_id': region.id,
                            'confidence': region.confidence, 'width': image.shape[1], 'height': image.shape[0],
                            'bit_depth': 16 if image.dtype == np.uint16 and extension == 'png' else 8})
            if progress: progress(index + 1, len(selected), name)
        atomic_json(stage / 'frames.json', {'format': 'lomokino-frame-manifest', 'version': 1, 'frames': records})
        if cancelled and cancelled(): raise InterruptedError('导出已取消，未写入最终文件夹')
        os.rename(stage, destination)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return len(selected)


def video_dimensions(selected, options):
    rotation = options.get('rotation', 0) % 180
    dimensions = [(r.rect.height, r.rect.width) if rotation else (r.rect.width, r.rect.height) for _, r in selected]
    width = int(options.get('width') or np.median([w for w, h in dimensions]))
    height = int(options.get('height') or np.median([h for w, h in dimensions]))
    return max(2, width + width % 2), max(2, height + height % 2)


def fit_frame(frame, size, mode='fit'):
    width, height = size
    h, w = frame.shape[:2]
    scale = (max if mode == 'fill' else min)(width / w, height / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    frame = cv2.resize(to8(frame), (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4)
    if mode == 'fill': return frame[(nh - height) // 2:(nh - height) // 2 + height, (nw - width) // 2:(nw - width) // 2 + width]
    canvas = np.zeros((height, width, 3), np.uint8)
    x, y = (width - nw) // 2, (height - nh) // 2
    canvas[y:y + nh, x:x + nw] = frame
    return canvas


def _ffmpeg_writer(destination, size, fps, codec, log):
    import imageio_ffmpeg
    encoding = (['-c:v', 'libx264', '-crf', '18', '-preset', 'medium']
                if codec == 'h264' else ['-c:v', 'mpeg4', '-q:v', '2', '-vtag', 'mp4v'])
    return subprocess.Popen([
        imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'bgr24',
        '-s', f'{size[0]}x{size[1]}', '-r', str(fps), '-i', '-', '-an',
        *encoding, '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destination)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def export_video(documents, order, destination, options=None, progress=None, cancelled=None):
    options = options or {}
    fps = float(options.get('fps', 12))
    if not np.isfinite(fps) or not 1 <= fps <= 60: raise ValueError('帧率必须在 1–60 FPS 之间')
    selected = ordered_regions(documents, order)
    if not selected: raise ValueError('没有可导出的已启用帧')
    size = video_dimensions(selected, options)
    if max(size) > 8192: raise ValueError('视频尺寸上限为 8192 像素，请降低输出尺寸')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Check directory writability before starting an encoder, so permission
    # failures produce a filesystem error instead of a misleading broken pipe.
    descriptor, temporary = tempfile.mkstemp(prefix='.' + destination.stem + '.', suffix='.mp4', dir=destination.parent)
    os.close(descriptor)
    temp = Path(temporary)
    backend = options.get('codec', 'h264')
    process, writer = None, None
    log = tempfile.TemporaryFile()
    try:
        if backend == 'h264':
            process = _ffmpeg_writer(temp, size, fps, backend, log)
        elif backend == 'mp4v':
            writer = cv2.VideoWriter(str(temp), cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
            if not writer.isOpened():
                # Some OpenCV wheels lack an MPEG-4 encoder (notably Intel macOS).
                # The bundled FFmpeg supports the same codec without system installs.
                writer.release()
                writer = None
                process = _ffmpeg_writer(temp, size, fps, backend, log)
        else: raise ValueError('不支持的编码器')
        for index, (document, region) in enumerate(selected):
            if cancelled and cancelled(): raise InterruptedError('视频导出已取消，未覆盖目标文件')
            frame = fit_frame(frame_image(document, region, options), size, options.get('fit', 'fit'))
            if process:
                try: process.stdin.write(frame.tobytes())
                except BrokenPipeError as error:
                    process.wait(timeout=10)
                    log.seek(0)
                    details = log.read().decode(errors='replace')[-3000:]
                    raise RuntimeError('FFmpeg 提前退出：' + details) from error
            else: writer.write(frame)
            if progress: progress(index + 1, len(selected), f'编码 {index + 1}/{len(selected)}')
        if process:
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                log.seek(0)
                raise RuntimeError('FFmpeg 编码失败：' + log.read().decode(errors='replace')[-2000:])
        else:
            writer.release()
            writer = None
        if not temp.exists() or temp.stat().st_size == 0: raise RuntimeError('视频为空，未写入目标文件')
        capture = cv2.VideoCapture(str(temp))
        count = round(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        valid = capture.isOpened() and count == len(selected)
        capture.release()
        if not valid: raise RuntimeError(f'视频复核失败：期望 {len(selected)} 帧，读回 {count} 帧')
        if cancelled and cancelled(): raise InterruptedError('视频导出已取消，未覆盖目标文件')
        os.replace(temp, destination)
        return {'frames': len(selected), 'fps': fps, 'width': size[0], 'height': size[1],
                'seconds': len(selected) / fps, 'codec': backend}
    finally:
        if writer is not None: writer.release()
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        log.close()
        temp.unlink(missing_ok=True)
