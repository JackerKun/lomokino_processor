#!/usr/bin/env python3
"""
Test script for improved frame detection
"""

import cv2
import os
from lomokino_processor import LomoKinoProcessor

def test_detection(image_path):
    """Test frame detection on a single image"""
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(image_path)}")
    print(f"{'='*60}")

    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Failed to load image")
        return

    height, width = image.shape[:2]
    print(f"Image size: {width} x {height}")
    print(f"Aspect ratio: {height/width:.2f}")

    # Create processor
    processor = LomoKinoProcessor()

    # Detect frames
    frame_separators = processor.detect_frames(image)
    num_frames = len(frame_separators) - 1
    print(f"\n✓ Detected {num_frames} frames")

    # Show separator positions
    print(f"\nFrame separators at: {frame_separators}")

    # Extract frames
    frames = processor.extract_frames(image, frame_separators)
    print(f"✓ Extracted {len(frames)} valid frames")

    # Show frame dimensions
    if frames:
        print(f"\nFrame dimensions:")
        for i, frame in enumerate(frames):
            h, w = frame.shape[:2]
            print(f"  Frame {i+1}: {w} x {h}")

    return len(frames)

def main():
    """Test all demo images"""
    demo_dir = "demo"

    if not os.path.exists(demo_dir):
        print(f"❌ Demo directory not found: {demo_dir}")
        return

    # Get all jpg files
    image_files = sorted([f for f in os.listdir(demo_dir) if f.endswith('.jpg')])

    if not image_files:
        print(f"❌ No images found in {demo_dir}")
        return

    print(f"\n{'#'*60}")
    print(f"# Testing Frame Detection on {len(image_files)} images")
    print(f"{'#'*60}")

    results = {}

    for image_file in image_files:
        image_path = os.path.join(demo_dir, image_file)
        num_frames = test_detection(image_path)
        results[image_file] = num_frames

    # Summary
    print(f"\n{'#'*60}")
    print(f"# SUMMARY")
    print(f"{'#'*60}")
    print(f"\nDetection results:")
    for filename, count in results.items():
        status = "✓" if count > 0 else "❌"
        print(f"  {status} {filename}: {count} frames")

if __name__ == "__main__":
    main()
