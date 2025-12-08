"""
Clinical Corrector - Medical Ultrasound De-identification Engine

This module provides tools for de-identifying patient information in
ultrasound videos while maintaining a realistic medical appearance.
Optimized for CPU-only execution on resource-constrained devices.
"""

import cv2
import numpy as np
try:
    from paddleocr import PaddleOCR
except ImportError:
    # Dummy mock for systems where PaddleOCR cannot be installed (e.g. Python 3.14)
    class PaddleOCR:
        def __init__(self, **kwargs):
            print("Warning: PaddleOCR not available. OCR features disabled.")
        def predict(self, img):
            return []

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
import os
from typing import Optional, Tuple, List, Dict


class ClinicalCorrector:
    """
    A class for de-identifying medical ultrasound videos by detecting
    and replacing burned-in patient information with new text overlays.
    """

    def __init__(self):
        """
        Initialize PaddleOCR with CPU-only mode for Steam Deck compatibility.
        Uses English language model for medical text detection.
        """
        # Force CPU mode for efficiency on Steam Deck (Arch Linux)
        # Newer PaddleOCR versions use different parameter names
        import os
        os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU by hiding GPUs
        
        # Initialize with aggressive detection settings for medical images
        # det_db_thresh=0.1 means "even 10% confidence counts as text"
        self.ocr = PaddleOCR(lang='en', det_db_thresh=0.1)

    def detect_static_text(self, video_path: str) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect static text regions (like patient name) by scanning only
        the first and last 5 frames for CPU efficiency.

        Static text appears in the same location across frames, so we
        find text boxes that appear consistently in both sets.

        Args:
            video_path: Path to the input video file

        Returns:
            Bounding box tuple (x, y, width, height) of static text region,
            or None if no consistent text region is found
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 10:
            # For very short videos, scan all frames
            frame_indices = list(range(total_frames))
        else:
            # Only scan first 5 and last 5 frames for speed
            frame_indices = list(range(5)) + list(range(total_frames - 5, total_frames))

        # Collect all detected text boxes from sampled frames
        all_boxes: List[List[Tuple[int, int, int, int]]] = []

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            # Pre-process frame for better OCR detection ("The Glasses")
            frame_processed = self._preprocess_for_ocr(frame)

            # Run OCR on the processed frame (newer PaddleOCR uses .predict())
            result = self.ocr.predict(frame_processed)

            # Scale boxes back to original size (we upscaled 2x)
            scale_factor = 2

            frame_boxes = []
            # New API returns dict with 'rec_texts', 'rec_scores', 'det_boxes'
            if result and isinstance(result, list) and len(result) > 0:
                res = result[0]  # First image result
                if isinstance(res, dict) and 'det_boxes' in res:
                    # New API format: dict with det_boxes
                    for box_points in res['det_boxes']:
                        x_coords = [p[0] for p in box_points]
                        y_coords = [p[1] for p in box_points]
                        # Scale back to original size
                        x = int(min(x_coords) / scale_factor)
                        y = int(min(y_coords) / scale_factor)
                        w = int((max(x_coords) - min(x_coords)) / scale_factor)
                        h = int((max(y_coords) - min(y_coords)) / scale_factor)
                        frame_boxes.append((x, y, w, h))
                elif isinstance(res, list):
                    # Old API format: list of [box, (text, score)]
                    for line in res:
                        box_points = line[0]
                        x_coords = [p[0] for p in box_points]
                        y_coords = [p[1] for p in box_points]
                        # Scale back to original size
                        x = int(min(x_coords) / scale_factor)
                        y = int(min(y_coords) / scale_factor)
                        w = int((max(x_coords) - min(x_coords)) / scale_factor)
                        h = int((max(y_coords) - min(y_coords)) / scale_factor)
                        frame_boxes.append((x, y, w, h))

            all_boxes.append(frame_boxes)

        cap.release()

        # Find boxes that appear consistently (static text)
        # A box is "static" if it appears in similar positions across frames
        if not all_boxes or not all_boxes[0]:
            return None

        # Use the first frame's boxes as reference
        reference_boxes = all_boxes[0]
        static_box = None
        max_consistency = 0

        for ref_box in reference_boxes:
            consistency = 0
            for frame_boxes in all_boxes[1:]:
                for box in frame_boxes:
                    # Check if boxes overlap significantly (within 20 pixels)
                    if self._boxes_overlap(ref_box, box, tolerance=20):
                        consistency += 1
                        break

            # Track the most consistent box
            if consistency > max_consistency:
                max_consistency = consistency
                static_box = ref_box

        # Only return if box appears in at least half the sampled frames
        if max_consistency >= len(all_boxes) // 2:
            return static_box

        return None

    def _preprocess_for_ocr(self, frame: np.ndarray) -> np.ndarray:
        """
        Pre-process frame for better OCR detection ("The Glasses").

        1. Upscale 2x - small text is hard for AI to read
        2. Convert to grayscale and threshold - makes white text pop

        Args:
            frame: Input BGR frame

        Returns:
            Processed frame optimized for OCR
        """
        # Step 1: Upscale by 2x
        h, w = frame.shape[:2]
        upscaled = cv2.resize(frame, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

        # Step 2: Convert to grayscale
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)

        # Step 3: Apply threshold to make white text pop against black background
        # Pixels > 200 become 255 (white), others become 0 (black)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # Convert back to BGR for OCR (PaddleOCR expects 3 channels)
        processed = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

        return processed

    def _boxes_overlap(
        self,
        box1: Tuple[int, int, int, int],
        box2: Tuple[int, int, int, int],
        tolerance: int = 20
    ) -> bool:
        """
        Check if two bounding boxes overlap within a tolerance.

        Args:
            box1: First box (x, y, w, h)
            box2: Second box (x, y, w, h)
            tolerance: Pixel tolerance for position matching

        Returns:
            True if boxes are in similar positions
        """
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2

        # Check if centers are within tolerance
        center1 = (x1 + w1 // 2, y1 + h1 // 2)
        center2 = (x2 + w2 // 2, y2 + h2 // 2)

        dx = abs(center1[0] - center2[0])
        dy = abs(center1[1] - center2[1])

        return dx <= tolerance and dy <= tolerance

    def generate_medical_overlay(
        self,
        text: str,
        width: int,
        height: int,
        auto_scale: bool = False
    ) -> np.ndarray:
        """
        Create a realistic medical ultrasound text overlay with noise.

        The overlay mimics the grainy appearance of ultrasound displays
        by adding Gaussian blur and speckle noise to the text.

        Args:
            text: The text to render (e.g., "PATIENT: JONES"). Supports multi-line with \n
            width: Width of the overlay image
            height: Height of the overlay image
            auto_scale: If True, automatically scale font to fit long text

        Returns:
            NumPy array (BGR) containing the noisy text overlay
        """
        # Create black background
        overlay = np.zeros((height, width, 3), dtype=np.uint8)

        # Split text into lines
        lines = text.split('\n')
        num_lines = len(lines)
        
        # Calculate text size and position for centering
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Find the longest line for scaling
        longest_line = max(lines, key=len) if lines else text
        
        if auto_scale:
            # Smart auto-scaling: find the largest font that fits the width
            # Start with a reasonable scale and reduce until text fits
            font_scale = min(width, height) / 200.0  # Start larger
            font_scale = max(0.3, min(font_scale, 2.0))  # Initial clamp
            thickness = max(1, int(font_scale * 1.5))
            
            # Iteratively reduce font size until longest line fits with margin
            max_text_width = int(width * 0.95)  # Leave 5% margin on each side
            for _ in range(20):  # Max 20 iterations
                (text_width, text_height), baseline = cv2.getTextSize(
                    longest_line, font, font_scale, thickness
                )
                if text_width <= max_text_width:
                    break
                font_scale *= 0.9  # Reduce by 10%
                thickness = max(1, int(font_scale * 1.5))
            
            # Ensure minimum readable size
            font_scale = max(0.25, font_scale)
            thickness = max(1, thickness)
        else:
            # Original fixed scaling logic
            font_scale = min(width, height) / 300.0  # Scale based on region size
            font_scale = max(0.4, min(font_scale, 1.5))  # Clamp to reasonable range
            thickness = max(1, int(font_scale * 2))

        # Get line height for spacing
        (_, line_height), baseline = cv2.getTextSize(
            "Ay", font, font_scale, thickness  # Use "Ay" to get full height
        )
        line_spacing = int(line_height * 1.3)  # Add 30% spacing between lines
        
        # Calculate total text block height
        total_text_height = num_lines * line_spacing
        
        # Starting Y position - top aligned with small padding
        start_y = int(height * 0.35) + line_height  # Start about 1/3 down
        
        # Left margin
        left_margin = max(8, int(width * 0.02))  # 2% margin or minimum 8px
        
        # Draw each line
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Left-aligned
            x = left_margin
            y = start_y + (i * line_spacing)
            
            # Draw white text on black background
            cv2.putText(
                overlay,
                line,
                (x, y),
                font,
                font_scale,
                (255, 255, 255),  # White text
                thickness,
                cv2.LINE_AA  # Anti-aliased for smoother edges
            )

        # Apply Gaussian blur to soften edges (mimics CRT/LCD display blur)
        overlay = cv2.GaussianBlur(overlay, (3, 3), 0)

        # Add speckle noise to simulate ultrasound display grain
        # Generate random noise pattern
        noise = np.random.normal(0, 25, overlay.shape).astype(np.float32)

        # Apply noise only to non-black areas (preserve background)
        mask = cv2.cvtColor(overlay, cv2.COLOR_BGR2GRAY) > 10
        mask_3ch = np.stack([mask] * 3, axis=-1)

        # Add noise and clip to valid range
        overlay_float = overlay.astype(np.float32)
        overlay_float = np.where(mask_3ch, overlay_float + noise, overlay_float)
        overlay = np.clip(overlay_float, 0, 255).astype(np.uint8)

        # Add subtle background speckle for authenticity
        bg_noise = np.random.randint(0, 15, overlay.shape, dtype=np.uint8)
        overlay = cv2.add(overlay, bg_noise)

        return overlay

    def process_video(
        self,
        input_path: str,
        output_path: str,
        new_name: str
    ) -> bool:
        """
        Process a video to replace detected patient information.

        Steps:
        1. Detect static text region (patient name location)
        2. Draw black box over original text to scrub it
        3. Overlay new noisy text in the same region
        4. Save the de-identified video

        Args:
            input_path: Path to input video file
            output_path: Path for output video file
            new_name: New patient identifier text

        Returns:
            True if processing succeeded, False otherwise
        """
        # Detect where the static text is located
        text_box = self.detect_static_text(input_path)

        # Open input video
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {input_path}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        # Create output video writer
        out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

        # If no text detected, use a default region (top-left corner)
        if text_box is None:
            # Default to top-left region where patient info typically appears
            text_box = (10, 10, 200, 30)

        x, y, w, h = text_box

        # Add padding around detected text region
        padding = 5
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(frame_width - x, w + 2 * padding)
        h = min(frame_height - y, h + 2 * padding)

        # Generate the replacement overlay once (same for all frames)
        overlay = self.generate_medical_overlay(new_name, w, h)

        # Process each frame
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Step 1: Draw solid black box to scrub original text
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 0), -1)

            # Step 2: Overlay the new noisy text
            frame[y:y + h, x:x + w] = overlay

            # Write the processed frame
            out.write(frame)

        # Cleanup
        cap.release()
        out.release()

        return os.path.exists(output_path)

    def inject_audit_tags(
        self,
        dicom_path: str,
        original_text: str,
        new_text: str
    ) -> bool:
        """
        Inject private audit tags into a DICOM file for APP 10 compliance.

        Records the de-identification change in a private tag group (0x0009)
        to maintain an audit trail of modifications.

        Args:
            dicom_path: Path to the DICOM file
            original_text: Original patient identifier that was removed
            new_text: New identifier that was applied

        Returns:
            True if injection succeeded, False otherwise
        """
        try:
            # Load the DICOM file
            ds = pydicom.dcmread(dicom_path)

            # Create private block in group 0x0009
            # Private tags require a private creator element
            private_creator = "ClinicalCorrector"

            # Add private creator (0009,0010) - reserves block 0x10
            block = ds.private_block(0x0009, private_creator, create=True)

            # Add audit information as private tags
            # Element 0x01: Original text that was de-identified
            block.add_new(0x01, 'LO', original_text[:64])  # LO max 64 chars

            # Element 0x02: New replacement text
            block.add_new(0x02, 'LO', new_text[:64])

            # Element 0x03: Timestamp of modification
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            block.add_new(0x03, 'DT', timestamp)

            # Element 0x04: Software version identifier
            block.add_new(0x04, 'LO', "ClinicalCorrector v1.0")

            # Save the modified DICOM file
            ds.save_as(dicom_path)

            return True

        except Exception as e:
            print(f"Error injecting audit tags: {e}")
            return False
