"""Conservative gap segmentation, paired perforation evidence and optional deskew."""
from dataclasses import dataclass
import cv2
import numpy as np
from .models import CropRect, FrameRegion, DetectionSettings


def gray8(image):
    image = image if image.dtype == np.uint8 else (image / 257).clip(0, 255).astype(np.uint8)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def runs(mask, minimum=1):
    edges = np.diff(np.pad(np.asarray(mask, dtype=np.int8), (1, 1)))
    return [(int(a), int(b)) for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)) if b - a >= minimum]


def perforation_bounds(gray):
    """Only remove side rails when BOTH sides contain repeated hole-like contours."""
    h, w = gray.shape
    if h < w * 1.7: return 0, w, False
    edges = cv2.Canny(gray, 12, 35)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    groups = []
    for side in [0, 1]:
        candidates = []
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            if not (w * .055 < bw < w * .115 and w * .045 < bh < w * .10 and 1.15 < bw / bh < 2.1): continue
            if (side == 0 and x + bw < w * .24) or (side == 1 and x > w * .76):
                if not any(abs(y - b[1]) < 3 and abs(x - b[0]) < 3 for b in candidates):
                    candidates.append((x, y, bw, bh))
        clusters = []
        for candidate in sorted(candidates, key=lambda b: b[0] + b[2] / 2):
            center = candidate[0] + candidate[2] / 2
            if clusters and abs(center - np.median([b[0] + b[2] / 2 for b in clusters[-1]])) < w * .035:
                clusters[-1].append(candidate)
            else: clusters.append([candidate])
        valid = []
        for cluster in clusters:
            if len(cluster) < 5 or max(b[1] for b in cluster) - min(b[1] for b in cluster) < h * .45:
                continue
            ys = np.asarray([b[1] + b[3] / 2 for b in cluster])
            pitches = np.linspace(w * .105, w * .17, 180)
            periodicity = np.max(np.abs(np.mean(np.exp(2j * np.pi * ys[:, None] / pitches[None, :]), axis=0)))
            if periodicity >= .76: valid.append(cluster)
        if not valid: return 0, w, False
        # Use the inward cluster, avoiding printed edge numbers.
        groups.append(max(valid, key=lambda c: np.median([b[0] + b[2] / 2 for b in c])) if side == 0
                      else min(valid, key=lambda c: np.median([b[0] + b[2] / 2 for b in c])))
    left = int(round(np.median([x + bw for x, _, bw, _ in groups[0]])))
    right = int(round(np.median([x for x, _, _, _ in groups[1]])))
    if not w * .64 < right - left < w * .8: return 0, w, False
    return left, right, True


def estimate_skew(gray):
    h, w = gray.shape
    scale = min(1., 1600 / max(h, w))
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(small, 40, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, threshold=50,
                            minLineLength=max(40, int(small.shape[1] * .55)), maxLineGap=12)
    if lines is None: return 0., 0.
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) <= 6: angles.append(float(angle))
    if len(angles) < 3: return 0., 0.
    center = float(np.median(angles))
    agreement = float(np.mean(np.abs(np.asarray(angles) - center) < .4))
    return (center, agreement) if agreement >= .6 else (0., agreement)


def rectify(image, angle):
    if abs(angle) < .01: return image
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    nw, nh = int(np.ceil(w * cos + h * sin)), int(np.ceil(h * cos + w * sin))
    matrix[0, 2] += (nw - w) / 2
    matrix[1, 2] += (nh - h) / 2
    return cv2.warpAffine(image, matrix, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)


@dataclass
class DetectionResult:
    image: np.ndarray
    regions: list
    warnings: list
    angle: float
    threshold: float
    gutters: list
    content_bounds: tuple
    perforations: bool
    profile: np.ndarray


def _segment_band(band, width, minimum, settings, polarity):
    values = 255 - band if polarity == 'light' else band
    profile = np.quantile(values, .95, axis=1)
    floor = float(np.percentile(profile, 1))
    contrast = float(np.median(profile) - floor)
    allowance = {'low': (.065, 12., 4.), 'high': (.15, 28., 7.)}.get(settings.sensitivity, (.1, 20., 5.))
    threshold = settings.threshold or floor + max(allowance[2], min(allowance[1], contrast * allowance[0]))
    mask = (profile < threshold).astype(np.uint8).reshape(-1, 1)
    kernel = max(3, int(width * .004) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((kernel, 1), np.uint8)).ravel()
    gutters = runs(mask, max(2, int(width * .0015)))
    h = len(profile)
    # A thin scene line between two short fragments is weaker than the wider
    # physical gaps around it. Merge those fragments instead of inventing frames.
    internal_widths = [b - a for a, b in gutters if a > 0 and b < h]
    if len(internal_widths) >= 3:
        reference = float(np.percentile(internal_widths, 75))
        expected = width / 2.8
        keep = []
        for index, (start, end) in enumerate(gutters):
            previous = gutters[index - 1][1] if index else 0
            following = gutters[index + 1][0] if index + 1 < len(gutters) else h
            before, after = start - previous, following - end
            scene_line = (end - start < reference * .55 and before < expected * .7 and after < expected * .7
                          and expected * .65 < following - previous < expected * 1.4)
            if not scene_line: keep.append((start, end))
        gutters = keep
    cursor, segments = 0, []
    for start, end in gutters + [(h, h)]:
        if start - cursor >= minimum: segments.append((cursor, start))
        cursor = end
    if len(segments) < 2 or contrast < 12:
        score = -10.
    else:
        heights = np.asarray([b - a for a, b in segments])
        expected = width / 2.8
        plausibility = float(np.mean(np.exp(-np.abs(np.log(heights / expected)) * 2)))
        internal = [b - a for a, b in gutters if a > 0 and b < h]
        thin_gap = float(np.median(internal) / expected) if internal else 1.
        coverage = float(np.sum(heights) / h)
        uniformity = float(np.std(heights) / max(1, np.mean(heights)))
        score = plausibility * 3 + min(1., contrast / 100) + coverage - uniformity - thin_gap
    return profile, threshold, contrast, gutters, segments, score


def detect(image, settings=None):
    settings = settings or DetectionSettings()
    if min(image.shape[:2]) < 8: raise ValueError('扫描图片太小，无法识别胶片帧')
    if not 0 <= settings.expected_count <= 10000 or settings.frame_height < 0 or settings.min_frame_distance < 0:
        raise ValueError('等距数量限 0–10000，帧高与最小距离不可为负数')
    if settings.inset < 0 or not np.isfinite(settings.threshold) or not 0 <= settings.threshold <= 255:
        raise ValueError('内缩不可为负数，亮度阈值限 0–255')
    gray = gray8(image)
    angle = float(settings.angle)
    if not np.isfinite(angle): raise ValueError('校正角度必须为有限数值')
    warnings = []
    if settings.deskew and abs(angle) < .01:
        angle, confidence = estimate_skew(gray)
        if confidence < .6: warnings.append('倾斜证据不足，未自动旋转；可手动设置校正角度')
    if abs(angle) > 6: raise ValueError('倾斜校正限 ±6°；横向扫描请先选择旋转方向')
    image = rectify(image, angle)
    gray = gray8(image)
    h, w = gray.shape
    left, right, holes = perforation_bounds(gray) if settings.remove_perforations else (0, w, False)
    band = gray[:, left + int((right - left) * .18):right - int((right - left) * .18)]
    minimum = settings.min_frame_distance or max(8, int((right - left) / 2.72 * .24))
    choices = ['dark', 'light'] if settings.polarity == 'auto' else [settings.polarity]
    if any(value not in ('dark', 'light') for value in choices): raise ValueError('不支持的分隔带类型')
    candidates = [(value, _segment_band(band, right - left, minimum, settings, value)) for value in choices]
    polarity, candidate = max(candidates, key=lambda item: item[1][-1])
    profile, threshold, contrast, gutters, segments, score = candidate
    fallback = False
    if settings.frame_height > 0 or settings.expected_count > 0:
        top = gutters[0][1] if gutters and gutters[0][0] == 0 else 0
        bottom = gutters[-1][0] if gutters and gutters[-1][1] == h else h
        if settings.expected_count:
            boundaries = np.linspace(top, bottom, settings.expected_count + 1).round().astype(int)
        else:
            boundaries = list(range(top, bottom, settings.frame_height)) + [bottom]
        segments = list(zip(boundaries[:-1], boundaries[1:]))
        fallback = True
        warnings.append('当前为等距网格，未推断每条分隔带；请逐帧检查')
    elif len(segments) < 2 or contrast < 12:
        if not segments: segments = [(0, h)]
        warnings.append('分隔证据不足，没有强行按固定帧数切割；请手动校对')
        fallback = True
    median_height = float(np.median([b - a for a, b in segments])) if segments else 0
    regions = []
    for index, (a, b) in enumerate(segments):
        inset = max(0, settings.inset)
        rect = CropRect(left + inset, int(a) + inset, right - left - inset * 2, int(b - a) - inset * 2).clamp(w, h)
        if rect.width < 2 or rect.height < 2:
            warnings.append('内缩边距过大，部分空裁切框未保留')
            continue
        confidence = .55 if fallback or (median_height and median_height < (right - left) / 2.8 * .55) else .96
        note = '等距网格待复查' if fallback else ('浅色分隔带' if polarity == 'light' else '深色分隔带')
        if median_height and abs(rect.height / median_height - 1) > .25:
            confidence = min(confidence, .65)
            note = '边缘残帧或不规则帧高，请复查'
        regions.append(FrameRegion(rect, confidence, note=note))
    if any(r.confidence < .8 for r in regions): warnings.append('橙色标记帧建议复查；暗场与不规则扫描可能需要手动调整')
    if not regions: raise ValueError('没有有效裁切框，请减小内缩边距或等距帧数')
    result = DetectionResult(image, regions, warnings, angle, float(threshold), gutters, (left, right), holes, profile)
    result.polarity = polarity
    return result
