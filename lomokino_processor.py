#!/usr/bin/env python3
"""
LomoKino Film Strip Processor
Processes lomokino film strips by extracting individual frames and creating videos
"""

import cv2
import numpy as np
import os
import glob
from pathlib import Path
import argparse

class LomoKinoProcessor:
    def __init__(self, frame_height=None, output_dir="output", min_frame_distance=None, detection_sensitivity="auto"):
        self.frame_height = frame_height
        self.output_dir = output_dir
        self.min_frame_distance = min_frame_distance  # Minimum distance between frames
        self.detection_sensitivity = detection_sensitivity  # "auto", "low", "medium", "high"
        os.makedirs(output_dir, exist_ok=True)
    
    def detect_frames(self, image):
        """Detect individual frames in a lomokino film strip with improved algorithm"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape

        # Auto-detect image type and set sensitivity
        if self.detection_sensitivity == "auto":
            # Small images (like old.jpg 365x800) need medium sensitivity
            if width < 500 and height < 1000:
                sensitivity = "medium"  # Changed from "low" to "medium"
            elif width < 800 or height < 1500:
                sensitivity = "medium"
            else:
                sensitivity = "high"
        else:
            sensitivity = self.detection_sensitivity

        # Set minimum distance based on sensitivity and image size
        if self.min_frame_distance is not None:
            min_distance = self.min_frame_distance
        else:
            # Auto-calculate minimum distance
            if sensitivity == "low":
                # For small images, frames should be at least 12% of height apart
                min_distance = max(int(height * 0.12), 60)
            elif sensitivity == "medium":
                min_distance = max(int(height * 0.10), 50)
            else:  # high
                min_distance = max(int(height * 0.08), 40)

        # Method 1: Try multiple Canny thresholds for edge detection
        frame_separators = []

        # Adjust Canny parameters based on sensitivity
        if sensitivity == "low":
            # More conservative - only detect strong edges
            canny_params = [(50, 150)]
            hough_threshold_ratio = 0.35  # Require longer lines
        elif sensitivity == "medium":
            canny_params = [(30, 100), (50, 150)]
            hough_threshold_ratio = 0.30
        else:  # high
            canny_params = [(30, 100), (50, 150), (70, 200)]
            hough_threshold_ratio = 0.25

        for low, high in canny_params:
            edges = cv2.Canny(gray, low, high, apertureSize=3)

            # Use sensitivity-adjusted threshold for HoughLines
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=int(width*hough_threshold_ratio))

            if lines is not None:
                for rho, theta in lines[:, 0]:
                    # More lenient horizontal line detection
                    if abs(theta - np.pi/2) < 0.25:  # Horizontal lines
                        y = int(rho / np.sin(theta))
                        if 0 < y < height:
                            frame_separators.append(y)

        # Remove duplicates and sort
        frame_separators = sorted(list(set(frame_separators)))

        # Merge separators using sensitivity-based minimum distance
        merged_separators = []

        if frame_separators:
            merged_separators.append(frame_separators[0])
            for sep in frame_separators[1:]:
                if sep - merged_separators[-1] > min_distance:
                    merged_separators.append(sep)

        frame_separators = merged_separators

        # Method 2: If we still don't have enough frames, try brightness analysis
        # But be more conservative for low sensitivity
        if sensitivity == "high" and len(frame_separators) < 3:
            # Calculate mean brightness for each row
            row_means = np.mean(gray, axis=1)

            # Simple moving average to smooth the signal
            window_size = int(height * 0.02)  # 2% of image height
            if window_size < 3:
                window_size = 3
            smoothed = np.convolve(row_means, np.ones(window_size)/window_size, mode='same')

            # Find local minima (dark lines) more aggressively
            threshold = np.percentile(smoothed, 15)  # Bottom 15% brightness

            # Minimum distance between frames
            search_window = max(int(height * 0.08), 30)

            # Look for valleys in brightness
            for i in range(search_window, height-search_window):
                # Check if this is a local minimum in a larger window
                window_before = smoothed[i-search_window:i]
                window_after = smoothed[i:i+search_window]

                if smoothed[i] < threshold:
                    # Check if it's darker than most neighbors
                    if smoothed[i] < np.percentile(window_before, 30) and \
                       smoothed[i] < np.percentile(window_after, 30):
                        frame_separators.append(i)

            # Remove duplicates and sort
            frame_separators = sorted(list(set(frame_separators)))

            # Merge again with minimum distance
            merged_separators = []
            if frame_separators:
                merged_separators.append(frame_separators[0])
                for sep in frame_separators[1:]:
                    if sep - merged_separators[-1] > min_distance:
                        merged_separators.append(sep)

            frame_separators = merged_separators

        # If still failed, use adaptive frame estimation
        if len(frame_separators) < 2:
            # Estimate number of frames based on image aspect ratio
            aspect_ratio = height / width

            # Typical lomokino frame is about 1:1.5 aspect ratio
            # So if image is very tall, it has more frames
            if aspect_ratio > 6:
                estimated_frames = 8
            elif aspect_ratio > 4:
                estimated_frames = 6
            elif aspect_ratio > 2.5:
                estimated_frames = 4
            else:
                estimated_frames = 3

            if self.frame_height is None:
                self.frame_height = height // estimated_frames

            frame_separators = list(range(0, height, self.frame_height))

        # Ensure we have start and end points
        if 0 not in frame_separators:
            frame_separators.insert(0, 0)
        if height not in frame_separators:
            frame_separators.append(height)

        return frame_separators
    
    def detect_content_boundaries(self, frame):
        """Detect the actual content boundaries within a frame to remove black borders"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape

        # Analyze brightness along edges to find content boundaries
        # Check rows for top and bottom boundaries
        row_means = np.mean(gray, axis=1)

        # Use more conservative threshold to preserve content
        max_brightness = np.max(row_means)
        mean_brightness = np.mean(row_means)

        # Adjust threshold based on overall brightness
        # Use lower threshold (keep more content)
        if mean_brightness < 30:
            threshold = max_brightness * 0.05  # Very dark images
        elif mean_brightness < 60:
            threshold = max_brightness * 0.08
        else:
            threshold = max_brightness * 0.12

        # Find top boundary
        top = 0
        for i in range(height):
            if row_means[i] > threshold:
                top = max(0, i - 3)  # More padding
                break

        # Find bottom boundary
        bottom = height
        for i in range(height - 1, -1, -1):
            if row_means[i] > threshold:
                bottom = min(height, i + 4)  # More padding
                break

        # Check columns for left and right boundaries
        col_means = np.mean(gray, axis=0)
        max_col_brightness = np.max(col_means)
        mean_col_brightness = np.mean(col_means)

        # Use more conservative threshold for columns
        if mean_col_brightness < 30:
            col_threshold = max_col_brightness * 0.05
        elif mean_col_brightness < 60:
            col_threshold = max_col_brightness * 0.08
        else:
            col_threshold = max_col_brightness * 0.12

        # Find left boundary
        left = 0
        for i in range(width):
            if col_means[i] > col_threshold:
                left = max(0, i - 3)  # More padding
                break

        # Find right boundary
        right = width
        for i in range(width - 1, -1, -1):
            if col_means[i] > col_threshold:
                right = min(width, i + 4)  # More padding
                break

        # Ensure we have valid boundaries
        if bottom <= top or right <= left:
            return 0, height, 0, width

        # Additional check: don't crop too much
        # Keep at least 60% of original dimensions
        height_ratio = (bottom - top) / height
        width_ratio = (right - left) / width

        if height_ratio < 0.6:
            # Too much vertical cropping, use full height
            top = 0
            bottom = height

        if width_ratio < 0.6:
            # Too much horizontal cropping, use full width
            left = 0
            right = width

        return top, bottom, left, right
    
    def extract_frames(self, image, frame_separators):
        """Extract individual frames from the film strip with smart content detection"""
        frames = []
        height, width = image.shape[:2]

        # More conservative initial crop to remove only sprocket holes
        # Reduce from 18%-82% to 8%-92% to preserve more content
        rough_crop_left = int(width * 0.08)
        rough_crop_right = int(width * 0.92)

        for i in range(len(frame_separators) - 1):
            y1 = frame_separators[i]
            y2 = frame_separators[i + 1]

            # Calculate frame height
            frame_height = y2 - y1

            # Add some padding to avoid cutting off image content
            padding = int(frame_height * 0.03)  # Slightly more padding
            y1 = max(0, y1 + padding)
            y2 = min(height, y2 - padding)

            # Filter out very small frames (likely separators)
            # Minimum frame height should be at least 8% of image height
            min_frame_height = max(int(height * 0.08), 40)

            if y2 - y1 > min_frame_height:  # Increased minimum frame height
                # First rough crop to remove sprockets
                rough_frame = image[y1:y2, rough_crop_left:rough_crop_right]

                if rough_frame.size > 0:
                    # Detect actual content boundaries within the rough frame
                    content_y1, content_y2, content_x1, content_x2 = self.detect_content_boundaries(rough_frame)

                    # Extract the final content area
                    if content_y2 > content_y1 and content_x2 > content_x1:
                        final_frame = rough_frame[content_y1:content_y2, content_x1:content_x2]

                        # Check final frame dimensions
                        final_height, final_width = final_frame.shape[:2]

                        # Only add frame if it has reasonable dimensions
                        # Should be at least 20% of rough frame size
                        if final_height > rough_frame.shape[0] * 0.2 and \
                           final_width > rough_frame.shape[1] * 0.2:
                            frames.append(final_frame)
                        else:
                            # Content detection was too aggressive, use rough frame
                            frames.append(rough_frame)
                    else:
                        # Fallback to rough frame if content detection fails
                        frames.append(rough_frame)

        return frames
    
    def create_video(self, frames, output_path, fps=12):
        """Create video from extracted frames with consistent sizing"""
        if not frames:
            print("No frames to create video")
            return False

        # Find the most common aspect ratio and reasonable dimensions
        # Calculate median width and height to avoid outliers
        widths = [f.shape[1] for f in frames]
        heights = [f.shape[0] for f in frames]

        # Use median dimensions as target
        target_width = int(np.median(widths))
        target_height = int(np.median(heights))

        # Ensure dimensions are even (required by some codecs)
        if target_width % 2 != 0:
            target_width += 1
        if target_height % 2 != 0:
            target_height += 1

        print(f"Target video dimensions: {target_width} x {target_height}")

        # Define codec and create VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))

        # Process each frame
        for i, frame in enumerate(frames):
            h, w = frame.shape[:2]

            # Calculate scaling to fit within target dimensions while maintaining aspect ratio
            scale = min(target_width / w, target_height / h)

            new_w = int(w * scale)
            new_h = int(h * scale)

            # Resize frame
            resized_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

            # Create black canvas of target size
            canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)

            # Calculate position to center the frame
            x_offset = (target_width - new_w) // 2
            y_offset = (target_height - new_h) // 2

            # Place resized frame on canvas
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_frame

            out.write(canvas)

        out.release()
        print(f"Video saved: {output_path}")
        return True
    
    def process_image(self, image_path, output_name=None):
        """Process a single lomokino image"""
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return False
        
        print(f"Processing: {image_path}")
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"Failed to load image: {image_path}")
            return False
        
        # Detect frame boundaries
        frame_separators = self.detect_frames(image)
        print(f"Detected {len(frame_separators)-1} frames")
        
        # Extract frames
        frames = self.extract_frames(image, frame_separators)
        print(f"Extracted {len(frames)} valid frames")
        
        if not frames:
            print("No frames extracted")
            return False
        
        # Save individual frames
        if output_name is None:
            output_name = Path(image_path).stem
        
        frames_dir = os.path.join(self.output_dir, f"{output_name}_frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        for i, frame in enumerate(frames):
            frame_path = os.path.join(frames_dir, f"frame_{i:03d}.jpg")
            cv2.imwrite(frame_path, frame)
        
        print(f"Frames saved to: {frames_dir}")
        
        # Create video
        video_path = os.path.join(self.output_dir, f"{output_name}_video.mp4")
        success = self.create_video(frames, video_path)
        
        return success
    
    def process_multiple_images(self, image_pattern="*.jpg"):
        """Process multiple lomokino images"""
        image_files = glob.glob(image_pattern)
        image_files.sort()
        
        if not image_files:
            print(f"No images found matching pattern: {image_pattern}")
            return False
        
        print(f"Found {len(image_files)} images to process")
        
        for image_file in image_files:
            self.process_image(image_file)
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Process LomoKino film strips')
    parser.add_argument('input', nargs='?', default='*.jpg', help='Input image file or pattern (default: *.jpg)')
    parser.add_argument('--output-dir', '-o', default='output', help='Output directory (default: output)')
    parser.add_argument('--frame-height', '-f', type=int, help='Manual frame height override')
    parser.add_argument('--fps', type=int, default=12, help='Video frame rate (default: 12)')
    
    args = parser.parse_args()
    
    processor = LomoKinoProcessor(
        frame_height=args.frame_height,
        output_dir=args.output_dir
    )
    
    # Check if input is a single file or pattern
    if os.path.isfile(args.input):
        processor.process_image(args.input)
    else:
        processor.process_multiple_images(args.input)

if __name__ == "__main__":
    main()