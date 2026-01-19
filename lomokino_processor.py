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
    def __init__(self, frame_height=None, output_dir="output"):
        self.frame_height = frame_height
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def detect_frames(self, image):
        """Detect individual frames in a lomokino film strip"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # Find horizontal lines (frame separators)
        # Use edge detection to find frame boundaries
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect horizontal lines using HoughLines
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=int(width*0.3))
        
        frame_separators = []
        if lines is not None:
            for rho, theta in lines[:, 0]:
                # Only consider nearly horizontal lines
                if abs(theta - np.pi/2) < 0.2:
                    y = int(rho / np.sin(theta))
                    if 0 < y < height:
                        frame_separators.append(y)
        
        # Sort separators and remove duplicates
        frame_separators = sorted(list(set(frame_separators)))
        
        # If automatic detection fails, use estimated frame height
        if len(frame_separators) < 2:
            if self.frame_height is None:
                # Estimate frame height based on image dimensions
                # Typical lomokino has 8-10 frames per strip
                estimated_frames = 8
                self.frame_height = height // estimated_frames
            
            frame_separators = list(range(0, height, self.frame_height))
        
        return frame_separators
    
    def detect_content_boundaries(self, frame):
        """Detect the actual content boundaries within a frame to remove black borders"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # Analyze brightness along edges to find content boundaries
        # Check rows for top and bottom boundaries
        row_means = np.mean(gray, axis=1)
        threshold = np.max(row_means) * 0.15  # 15% of max brightness
        
        # Find top boundary
        top = 0
        for i in range(height):
            if row_means[i] > threshold:
                top = max(0, i - 2)  # Small padding
                break
        
        # Find bottom boundary  
        bottom = height
        for i in range(height - 1, -1, -1):
            if row_means[i] > threshold:
                bottom = min(height, i + 3)  # Small padding
                break
        
        # Check columns for left and right boundaries
        col_means = np.mean(gray, axis=0)
        threshold = np.max(col_means) * 0.15  # 15% of max brightness
        
        # Find left boundary
        left = 0
        for i in range(width):
            if col_means[i] > threshold:
                left = max(0, i - 2)  # Small padding
                break
        
        # Find right boundary
        right = width
        for i in range(width - 1, -1, -1):
            if col_means[i] > threshold:
                right = min(width, i + 3)  # Small padding
                break
        
        # Ensure we have valid boundaries
        if bottom <= top or right <= left:
            return 0, height, 0, width
        
        return top, bottom, left, right
    
    def extract_frames(self, image, frame_separators):
        """Extract individual frames from the film strip with smart content detection"""
        frames = []
        height, width = image.shape[:2]
        
        # Initial rough crop to remove sprocket holes  
        rough_crop_left = int(width * 0.18)
        rough_crop_right = int(width * 0.82)
        
        for i in range(len(frame_separators) - 1):
            y1 = frame_separators[i]
            y2 = frame_separators[i + 1]
            
            # Add some padding to avoid cutting off image content
            padding = int((y2 - y1) * 0.02)
            y1 = max(0, y1 + padding)
            y2 = min(height, y2 - padding)
            
            if y2 - y1 > 20:  # Minimum frame height
                # First rough crop to remove sprockets
                rough_frame = image[y1:y2, rough_crop_left:rough_crop_right]
                
                if rough_frame.size > 0:
                    # Detect actual content boundaries within the rough frame
                    content_y1, content_y2, content_x1, content_x2 = self.detect_content_boundaries(rough_frame)
                    
                    # Extract the final content area
                    if content_y2 > content_y1 and content_x2 > content_x1:
                        final_frame = rough_frame[content_y1:content_y2, content_x1:content_x2]
                        
                        # Only add frame if it has reasonable dimensions
                        if final_frame.shape[0] > 10 and final_frame.shape[1] > 10:
                            frames.append(final_frame)
                    else:
                        # Fallback to rough frame if content detection fails
                        frames.append(rough_frame)
        
        return frames
    
    def create_video(self, frames, output_path, fps=12):
        """Create video from extracted frames"""
        if not frames:
            print("No frames to create video")
            return False
        
        # Get dimensions from first frame
        height, width = frames[0].shape[:2]
        
        # Define codec and create VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        for frame in frames:
            # Resize frame if needed to match first frame dimensions
            if frame.shape[:2] != (height, width):
                frame = cv2.resize(frame, (width, height))
            out.write(frame)
        
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