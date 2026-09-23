"""Optical Boresight Alignment Error Calculator.

This module computes spatial pixel errors (error_x, error_y), radial displacement,
angular pointing error, and alignment states ("ALIGNED", "MISALIGNED", "LOST")
by comparing detected beacon centroids with camera sensor optical center geometry.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import math

from .beacon_detector import DetectionResult


@dataclass
class AlignmentResult:
    """Encapsulates pointing alignment error metrics relative to optical boresight center.
    
    Attributes:
        detected (bool): True if beacon spot was detected in sensor image frame.
        aligned (bool): True if radial_error is within the configured tolerance threshold.
        error_x (Optional[float]): Horizontal pixel displacement from optical center (u_det - u_center).
        error_y (Optional[float]): Vertical pixel displacement from optical center (v_det - v_center).
        radial_error (Optional[float]): Total Euclidean pixel distance sqrt(error_x^2 + error_y^2).
        angular_error_deg (Optional[float]): Angular offset from optical boresight axis in degrees.
        alignment_state (str): Operational status string ("ALIGNED", "MISALIGNED", "LOST").
    """
    detected: bool
    aligned: bool
    error_x: Optional[float] = None
    error_y: Optional[float] = None
    radial_error: Optional[float] = None
    angular_error_deg: Optional[float] = None
    alignment_state: str = "LOST"

    def to_dict(self) -> Dict[str, Any]:
        """Returns alignment result metrics as a dictionary."""
        return {
            "detected": self.detected,
            "aligned": self.aligned,
            "error_x": self.error_x,
            "error_y": self.error_y,
            "radial_error": self.radial_error,
            "angular_error_deg": self.angular_error_deg,
            "alignment_state": self.alignment_state,
        }


class AlignmentCalculator:
    """Calculates optical boresight alignment errors from beacon perception results.
    
    Attributes:
        image_width (int): Sensor image resolution width in pixels (e.g. 1280).
        image_height (int): Sensor image resolution height in pixels (e.g. 720).
        fov_deg (float): Camera horizontal field-of-view spread in degrees (e.g. 35.0).
        tolerance_px (float): Maximum radial pixel error for ALIGNED status (e.g. 15.0).
    """

    def __init__(
        self,
        image_width: int = 1280,
        image_height: int = 720,
        fov_deg: float = 35.0,
        tolerance_px: float = 15.0,
    ) -> None:
        self.image_width = int(image_width)
        self.image_height = int(image_height)
        self.fov_deg = float(fov_deg)
        self.tolerance_px = float(tolerance_px)

    def calculate(self, detection_result: DetectionResult) -> AlignmentResult:
        """Computes alignment error metrics from a DetectionResult.
        
        Args:
            detection_result (DetectionResult): Perception result from beacon detector.
            
        Returns:
            AlignmentResult: Data structure containing pixel offsets, radial error,
            angular offset, and alignment state ("ALIGNED", "MISALIGNED", "LOST").
        """
        if not detection_result.detected or detection_result.center_x is None or detection_result.center_y is None:
            return AlignmentResult(
                detected=False,
                aligned=False,
                error_x=None,
                error_y=None,
                radial_error=None,
                angular_error_deg=None,
                alignment_state="LOST",
            )

        # 1. Calculate optical center dynamically from sensor dimensions
        center_x = self.image_width / 2.0
        center_y = self.image_height / 2.0

        # 2. Compute pixel displacements relative to optical center
        error_x = float(detection_result.center_x - center_x)
        error_y = float(detection_result.center_y - center_y)

        # 3. Compute Euclidean radial error distance
        radial_error = float(math.hypot(error_x, error_y))

        # 4. Determine alignment state based on tolerance threshold
        if radial_error <= self.tolerance_px:
            aligned = True
            alignment_state = "ALIGNED"
        else:
            aligned = False
            alignment_state = "MISALIGNED"

        # 5. Compute horizontal angular displacement from camera FOV
        half_width = self.image_width / 2.0
        half_fov = self.fov_deg / 2.0

        if half_width > 0:
            angular_error_deg = float((error_x / half_width) * half_fov)
        else:
            angular_error_deg = 0.0

        return AlignmentResult(
            detected=True,
            aligned=aligned,
            error_x=error_x,
            error_y=error_y,
            radial_error=radial_error,
            angular_error_deg=angular_error_deg,
            alignment_state=alignment_state,
        )
