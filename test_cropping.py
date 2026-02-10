#!/usr/bin/env python3
"""Test frame extraction with updated cropping parameters"""

import cv2
import os
from lomokino_processor import LomoKinoProcessor

# Test on old.jpg which should have 8 frames
test_file = "demo/old.jpg"

if not os.path.exists(test_file):
    print(f"File not found: {test_file}")
    exit(1)

print(f"Testing frame extraction on: {test_file}")
print("=" * 60)

# Load image
image = cv2.imread(test_file)
if image is None:
    print(f"Failed to load image: {test_file}")
    exit(1)

print(f"Image dimensions: {image.shape[1]} x {image.shape[0]}")

# Create processor
processor = LomoKinoProcessor(output_dir="test_output")

# Detect frame boundaries
frame_separators = processor.detect_frames(image)
print(f"\nDetected {len(frame_separators)-1} frame boundaries")
print(f"Separator positions: {frame_separators}")

# Extract frames
frames = processor.extract_frames(image, frame_separators)
print(f"\nExtracted {len(frames)} valid frames")

# Show frame dimensions
print("\nFrame dimensions:")
for i, frame in enumerate(frames):
    h, w = frame.shape[:2]
    print(f"  Frame {i+1}: {w} x {h}")

# Calculate what percentage of original width is preserved
if frames:
    avg_width = sum(f.shape[1] for f in frames) / len(frames)
    width_percentage = (avg_width / image.shape[1]) * 100
    print(f"\nAverage frame width: {avg_width:.1f}px ({width_percentage:.1f}% of original)")

print("\n" + "=" * 60)
print(f"✓ Expected: 8 frames")
print(f"✓ Got: {len(frames)} frames")

if len(frames) == 8:
    print("✅ Frame count is CORRECT!")
else:
    print(f"❌ Frame count is INCORRECT (expected 8, got {len(frames)})")

# Save extracted frames for visual inspection
os.makedirs("test_output/old_frames", exist_ok=True)
for i, frame in enumerate(frames):
    frame_path = f"test_output/old_frames/frame_{i+1:02d}.jpg"
    cv2.imwrite(frame_path, frame)

print(f"\n✓ Frames saved to: test_output/old_frames/")
print("✓ Please check if frames are complete (not cut off on sides)")
