"""Classical OpenCV Optical Beacon Detector.

This module processes camera sensor BGR images to detect and locate high-intensity
optical beacon emission spots using classical computer vision techniques (grayscale conversion,
brightness thresholding, contour extraction, and spatial moments analysis).
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np


@dataclass
class DetectionResult:
    """Encapsulates the detection metrics for an optical beacon in camera sensor space.
    
    Attributes:
        detected (bool): True if a valid optical beacon spot was detected.
        center_x (Optional[float]): Horizontal image coordinate (u) of beacon centroid in pixels.
        center_y (Optional[float]): Vertical image coordinate (v) of beacon centroid in pixels.
        confidence (float): Detection confidence score [0.0 - 1.0].
        area (float): Area of detected optical spot contour in pixels^2.
        peak_intensity (int): Maximum grayscale pixel intensity [0 - 255] in detected region.
        radius (float): Equivalent circular radius of detected spot in pixels.
    """
    detected: bool
    center_x: Optional[float] = None
    center_y: Optional[float] = None
    confidence: float = 0.0
    area: float = 0.0
    peak_intensity: int = 0
    radius: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Returns detection result metrics as a dictionary."""
        return {
            "detected": self.detected,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "confidence": self.confidence,
            "area": self.area,
            "peak_intensity": self.peak_intensity,
            "radius": self.radius,
        }


class ClassicalBeaconDetector:
    """Detector using classical computer vision methods for optical beacon spot detection.
    
    Processing Pipeline:
        1. BGR to Grayscale conversion
        2. Binary intensity thresholding for bright spot isolation
        3. Contour extraction & bounding filtering (area & peak brightness)
        4. Spatial moments calculation for sub-pixel centroid (center_x, center_y)
    """

    def __init__(
        self,
        intensity_threshold: int = 160,
        min_area: float = 4.0,
        max_area: float = 5000.0,
        min_peak_brightness: int = 180,
    ) -> None:
        self.intensity_threshold = int(intensity_threshold)
        self.min_area = float(min_area)
        self.max_area = float(max_area)
        self.min_peak_brightness = int(min_peak_brightness)

    def detect(self, camera_image: np.ndarray) -> DetectionResult:
        """Processes a BGR camera sensor frame to detect an optical beacon spot.
        
        Args:
            camera_image (np.ndarray): BGR image matrix of shape (height, width, 3).
            
        Returns:
            DetectionResult: Data structure containing detection flag, centroid, and confidence.
        """
        if camera_image is None or camera_image.size == 0:
            return DetectionResult(detected=False)

        # 1. Convert BGR to Grayscale
        if len(camera_image.shape) == 3 and camera_image.shape[2] == 3:
            gray = cv2.cvtColor(camera_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = camera_image.copy()

        # 2. Binary intensity thresholding to isolate bright optical emission
        _, binary = cv2.threshold(gray, self.intensity_threshold, 255, cv2.THRESH_BINARY)

        # 3. Contour extraction
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_candidate: Optional[Tuple[float, float, float, float, int, float]] = None
        best_score = -1.0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.min_area <= area <= self.max_area):
                continue

            # Calculate mask to evaluate peak brightness inside candidate contour
            mask = np.zeros_like(gray, dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            
            _, max_val, _, _ = cv2.minMaxLoc(gray, mask=mask)
            peak_val = int(max_val)

            if peak_val < self.min_peak_brightness:
                continue

            # 4. Spatial moments for sub-pixel centroid calculation
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue

            cx = float(M["m10"] / M["m00"])
            cy = float(M["m01"] / M["m00"])

            # Compute equivalent circle radius
            radius = float(np.sqrt(area / np.pi))

            # Calculate confidence metric combining brightness ratio & circular compactness
            brightness_factor = peak_val / 255.0
            perimeter = cv2.arcLength(cnt, True)
            circularity = (4.0 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0.0
            circularity = min(1.0, max(0.0, circularity))

            confidence = float(0.7 * brightness_factor + 0.3 * circularity)

            if confidence > best_score:
                best_score = confidence
                best_candidate = (cx, cy, confidence, area, peak_val, radius)

        if best_candidate is not None:
            cx, cy, confidence, area, peak_val, radius = best_candidate
            return DetectionResult(
                detected=True,
                center_x=cx,
                center_y=cy,
                confidence=confidence,
                area=area,
                peak_intensity=peak_val,
                radius=radius
            )

        return DetectionResult(detected=False)
