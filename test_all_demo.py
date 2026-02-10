#!/usr/bin/env python3
"""Test frame extraction on all demo images"""

import cv2
import os
import glob
from lomokino_processor import LomoKinoProcessor

# Find all demo images
demo_files = sorted(glob.glob("demo/*.jpg"))

if not demo_files:
    print("No demo files found")
    exit(1)

print("Testing frame extraction on all demo images")
print("=" * 80)

# Create processor
processor = LomoKinoProcessor(output_dir="test_output")

results = []

for test_file in demo_files:
    filename = os.path.basename(test_file)

    # Load image
    image = cv2.imread(test_file)
    if image is None:
        print(f"❌ Failed to load: {filename}")
        continue

    # Detect and extract frames
    frame_separators = processor.detect_frames(image)
    frames = processor.extract_frames(image, frame_separators)

    # Calculate average dimensions
    if frames:
        avg_width = sum(f.shape[1] for f in frames) / len(frames)
        avg_height = sum(f.shape[0] for f in frames) / len(frames)
        width_pct = (avg_width / image.shape[1]) * 100
    else:
        avg_width = avg_height = width_pct = 0

    results.append({
        'file': filename,
        'img_size': f"{image.shape[1]}x{image.shape[0]}",
        'frames': len(frames),
        'avg_size': f"{avg_width:.0f}x{avg_height:.0f}",
        'width_pct': width_pct
    })

    print(f"{filename:15} | {image.shape[1]:4}x{image.shape[0]:4} | "
          f"{len(frames):2} frames | avg: {avg_width:3.0f}x{avg_height:3.0f} | "
          f"width: {width_pct:4.1f}%")

print("=" * 80)
print(f"\nTotal images tested: {len(results)}")
print(f"Average frames per image: {sum(r['frames'] for r in results) / len(results):.1f}")
print(f"Average width preservation: {sum(r['width_pct'] for r in results) / len(results):.1f}%")

# Check if any image has excessive frame count (likely over-detection)
over_detected = [r for r in results if r['frames'] > 12]
if over_detected:
    print(f"\n⚠️  Potential over-detection:")
    for r in over_detected:
        print(f"   {r['file']}: {r['frames']} frames")
else:
    print(f"\n✅ No over-detection issues found")
