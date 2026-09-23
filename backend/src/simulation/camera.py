"""Virtual Camera Image Generator for FSOC Simulation.

This module models optical frame capture from the VirtualCamera sensor,
projecting 2D world-space target beacons into camera sensor image coordinates (BGR).
"""

import math
from typing import Tuple, Optional
import numpy as np
import cv2

from .terminal import VirtualCamera
from .beacon import OpticalBeacon


class VirtualCameraSensor:
    """Simulates physical image capture of an optical beacon onto a camera sensor matrix.
    
    Color Palette (BGR):
        - Sensor Background: (15, 12, 10) - Dark slate sensor noise floor
        - Beacon Core: (255, 255, 255) - Bright white optical saturation
        - Beacon Outer Glow: (80, 220, 255) - Warm yellow optical emission
    """

    COLOR_BG = (15, 12, 10)
    COLOR_BEACON_CORE = (255, 255, 255)
    COLOR_BEACON_GLOW = (80, 220, 255)

    def __init__(self, camera: VirtualCamera) -> None:
        self.camera = camera

    def project_beacon_to_image(
        self, beacon: OpticalBeacon
    ) -> Optional[Tuple[int, int, float]]:
        """Projects world-coordinate optical beacon position into camera sensor image space.
        
        Args:
            beacon (OpticalBeacon): Target optical beacon instance.
            
        Returns:
            Optional[Tuple[int, int, float]]: (u, v, angular_offset_deg) in sensor pixel space
            if inside FOV, otherwise None.
        """
        if not beacon.active or beacon.intensity <= 0.0:
            return None

        # 1. Vector from camera to beacon in world coordinates
        dx = beacon.x - self.camera.x
        dy = beacon.y - self.camera.y
        dist = math.hypot(dx, dy)

        if dist < 1e-5:
            return None

        # 2. Absolute angle in world space (0° = +X right, 90° = +Y down)
        beacon_angle_deg = math.degrees(math.atan2(dy, dx))

        # 3. Relative angular offset from camera optical axis (orientation)
        angle_diff_deg = beacon_angle_deg - self.camera.orientation_deg
        
        # Normalize angle_diff_deg to [-180, 180] range
        angle_diff_deg = (angle_diff_deg + 180.0) % 360.0 - 180.0

        # 4. Check horizontal FOV angular boundary
        half_fov_deg = self.camera.fov_deg / 2.0
        if abs(angle_diff_deg) > half_fov_deg:
            return None  # Beacon lies outside camera FOV sector

        # 5. Project relative angle to horizontal image coordinate (u)
        # u = (width / 2) * (1 + angle_diff / half_fov)
        img_w = self.camera.image_width
        img_h = self.camera.image_height

        u_frac = angle_diff_deg / half_fov_deg
        u = int(round((img_w / 2.0) * (1.0 + u_frac)))
        
        # Vertical image coordinate (v) - centered along optical plane
        v = int(round(img_h / 2.0))

        # Ensure inside sensor bounds
        if 0 <= u < img_w and 0 <= v < img_h:
            return (u, v, angle_diff_deg)

        return None

    def capture_frame(self, beacon: OpticalBeacon) -> np.ndarray:
        """Generates sensor image frame (BGR NumPy array).
        
        Args:
            beacon (OpticalBeacon): Target optical beacon instance.
            
        Returns:
            np.ndarray: BGR image matrix of shape (image_height, image_width, 3).
        """
        img_w = self.camera.image_width
        img_h = self.camera.image_height

        # Create dark sensor canvas frame
        frame = np.full((img_h, img_w, 3), self.COLOR_BG, dtype=np.uint8)

        # Project beacon into camera frame
        proj = self.project_beacon_to_image(beacon)
        if proj is not None:
            u, v, angle_offset = proj
            
            # Base spot radius on beacon parameters & intensity
            r = max(4, int(round(beacon.radius * beacon.intensity)))

            # Multi-layer radial glow representing optical spot bloom on CCD/CMOS sensor
            glow_overlay = frame.copy()
            glow_radii = [r * 3.5, r * 2.2, r * 1.4]
            alphas = [0.15, 0.30, 0.50]

            for g_rad, alpha in zip(glow_radii, alphas):
                cv2.circle(glow_overlay, (u, v), int(round(g_rad)), self.COLOR_BEACON_GLOW, -1, cv2.LINE_AA)
                cv2.addWeighted(glow_overlay, alpha, frame, 1.0 - alpha, 0, frame)

            # Bright inner saturation core
            cv2.circle(frame, (u, v), max(3, int(r * 0.6)), self.COLOR_BEACON_GLOW, -1, cv2.LINE_AA)
            cv2.circle(frame, (u, v), max(2, int(r * 0.3)), self.COLOR_BEACON_CORE, -1, cv2.LINE_AA)

        return frame
