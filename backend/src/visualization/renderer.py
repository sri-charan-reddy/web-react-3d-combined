"""FSOC Environment Renderer using OpenCV and NumPy.

This module provides high-quality dark-mode rendering of the virtual FSOC environment,
terminals, optical beacon, camera FOV wedge, line-of-sight path, and telemetry HUD.
"""

import math
import cv2
import numpy as np
from typing import Tuple

from ..simulation.environment import FSOCEnvironment


class EnvironmentRenderer:
    """Renders the FSOC simulation environment using OpenCV graphics primitives.
    
    Color Palette (BGR):
        - Background: (20, 16, 12) - Deep Slate Black
        - Grid: (35, 30, 24) - Subtle Slate
        - Terminal A (Local): (255, 200, 50) - Bright Cyan/Teal
        - Terminal B (Remote): (50, 180, 255) - Amber/Gold
        - Beacon Core: (255, 255, 255) - White
        - Beacon Glow: (100, 220, 255) - Warm Optical Yellow
        - FOV Cone Fill: (230, 180, 40) - Semi-transparent Teal
        - FOV Boundary Rays: (255, 220, 80) - Cyan Accent
        - Line of Sight: (80, 80, 80) - Muted Neutral
        - Text HUD: (240, 240, 240) - Bright White
    """

    COLOR_BG = (20, 16, 12)
    COLOR_GRID = (35, 30, 24)
    COLOR_BORDER = (60, 50, 40)
    
    COLOR_TERM_A = (255, 200, 50)     # BGR Cyan/Teal
    COLOR_TERM_B = (50, 180, 255)     # BGR Amber
    COLOR_BEACON_CORE = (255, 255, 255)
    COLOR_BEACON_GLOW = (80, 220, 255) # Warm Yellow Glow
    
    COLOR_FOV_FILL = (230, 180, 40)
    COLOR_FOV_RAY = (255, 210, 80)
    COLOR_LOS = (120, 120, 120)
    
    COLOR_TEXT = (240, 240, 240)
    COLOR_TEXT_DIM = (160, 160, 160)
    COLOR_HUD_BG = (35, 28, 20)
    COLOR_HUD_BORDER = (80, 70, 50)

    def __init__(self, environment: FSOCEnvironment, window_name: str = "FSOC PAT System - Phase 1") -> None:
        self.env = environment
        self.window_name = window_name

    def render(self) -> np.ndarray:
        """Draws complete simulation frame image.
        
        Returns:
            np.ndarray: OpenCV BGR image array (height, width, 3).
        """
        # Create base canvas background
        frame = np.full((self.env.height, self.env.width, 3), self.COLOR_BG, dtype=np.uint8)

        # 1. Draw coordinate grid
        if self.env.grid_visible:
            self._draw_grid(frame)

        # 2. Draw Camera FOV Wedge (translucent sector cone)
        self._draw_camera_fov(frame)

        # 3. Draw Optical Line of Sight (LOS) baseline
        self._draw_line_of_sight(frame)

        # 4. Draw Terminal A (Local)
        self._draw_terminal_a(frame)

        # 5. Draw Terminal B (Remote) & Optical Beacon
        self._draw_terminal_b_and_beacon(frame)

        # 6. Draw HUD Telemetry & Banner Overlay
        self._draw_hud_telemetry(frame)

        return frame

    def _draw_grid(self, frame: np.ndarray) -> None:
        """Draws subtle background grid lines and coordinate tick marks."""
        step = self.env.grid_spacing
        for x in range(0, self.env.width, step):
            cv2.line(frame, (x, 0), (x, self.env.height), self.COLOR_GRID, 1)
        for y in range(0, self.env.height, step):
            cv2.line(frame, (0, y), (self.env.width, y), self.COLOR_GRID, 1)

        # Outer frame border
        cv2.rectangle(frame, (0, 0), (self.env.width - 1, self.env.height - 1), self.COLOR_BORDER, 2)

    def _draw_camera_fov(self, frame: np.ndarray) -> None:
        """Calculates FOV wedge geometry dynamically from camera properties and renders sector cone."""
        cam = self.env.camera
        fov_range = self.env.fov_range_px

        # Obtain exact wedge arc polygon from VirtualCamera geometry calculation
        wedge_poly = cam.get_fov_wedge_polygon(fov_range_px=fov_range, num_arc_points=36)
        
        # Render translucent semi-transparent FOV cone
        overlay = frame.copy()
        cv2.fillPoly(overlay, [wedge_poly], self.COLOR_FOV_FILL)
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)

        # Render FOV boundary rays (Left & Right)
        left_end, center_end, right_end = cam.get_fov_boundary_rays(fov_range)
        cam_pt = (int(round(cam.x)), int(round(cam.y)))
        
        left_pt = (int(round(left_end[0])), int(round(left_end[1])))
        right_pt = (int(round(right_end[0])), int(round(right_end[1])))
        center_pt = (int(round(center_end[0])), int(round(center_end[1])))

        cv2.line(frame, cam_pt, left_pt, self.COLOR_FOV_RAY, 2, cv2.LINE_AA)
        cv2.line(frame, cam_pt, right_pt, self.COLOR_FOV_RAY, 2, cv2.LINE_AA)

        # Draw optical boresight center axis line (dashed)
        self._draw_dashed_line(frame, cam_pt, center_pt, self.COLOR_FOV_RAY, 1, dash_len=8)

    def _draw_line_of_sight(self, frame: np.ndarray) -> None:
        """Renders baseline optical path between Local and Remote terminals."""
        pt_a = (int(round(self.env.terminal_a.x)), int(round(self.env.terminal_a.y)))
        pt_b = (int(round(self.env.terminal_b.x)), int(round(self.env.terminal_b.y)))

        # Thin dashed optical baseline
        self._draw_dashed_line(frame, pt_a, pt_b, self.COLOR_LOS, 1, dash_len=6)
        
        # Label LOS path
        mid_x = (pt_a[0] + pt_b[0]) // 2
        mid_y = (pt_a[1] + pt_b[1]) // 2 - 12
        cv2.putText(
            frame, "OPTICAL LINE OF SIGHT (LOS)", (mid_x - 90, mid_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_TEXT_DIM, 1, cv2.LINE_AA
        )

    def _draw_terminal_a(self, frame: np.ndarray) -> None:
        """Renders Terminal A (Local Node) housing and camera lens representation."""
        tx, ty = int(round(self.env.terminal_a.x)), int(round(self.env.terminal_a.y))
        
        # Main housing square
        size = 22
        cv2.rectangle(frame, (tx - size, ty - size), (tx + size, ty + size), (30, 25, 20), -1)
        cv2.rectangle(frame, (tx - size, ty - size), (tx + size, ty + size), self.COLOR_TERM_A, 2)
        
        # Camera aperture ring
        cv2.circle(frame, (tx, ty), 10, self.COLOR_TERM_A, 2, cv2.LINE_AA)
        cv2.circle(frame, (tx, ty), 4, self.COLOR_TERM_A, -1, cv2.LINE_AA)

        # Pointing direction indicator vector
        cam = self.env.camera
        rad = math.radians(cam.orientation_deg)
        ptr_x = int(round(tx + (size + 10) * math.cos(rad)))
        ptr_y = int(round(ty + (size + 10) * math.sin(rad)))
        cv2.arrowedLine(frame, (tx, ty), (ptr_x, ptr_y), self.COLOR_TERM_A, 2, tipLength=0.35)

        # Terminal labels
        cv2.putText(
            frame, self.env.terminal_a.name.upper(), (tx - 55, ty + size + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TERM_A, 1, cv2.LINE_AA
        )
        cv2.putText(
            frame, f"POS: ({tx}, {ty})", (tx - 45, ty + size + 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_TEXT_DIM, 1, cv2.LINE_AA
        )

    def _draw_terminal_b_and_beacon(self, frame: np.ndarray) -> None:
        """Renders Terminal B (Remote Node) housing and bright multi-layer optical beacon."""
        tx, ty = int(round(self.env.terminal_b.x)), int(round(self.env.terminal_b.y))
        bcn = self.env.beacon

        # Terminal B housing (Octagonal / Box target structure)
        size = 24
        cv2.rectangle(frame, (tx - size, ty - size), (tx + size, ty + size), (25, 20, 30), -1)
        cv2.rectangle(frame, (tx - size, ty - size), (tx + size, ty + size), self.COLOR_TERM_B, 2)

        # Optical Beacon rendering with multi-layer radial glow
        if bcn.active and bcn.intensity > 0:
            bx, by = int(round(bcn.x)), int(round(bcn.y))
            r = int(round(bcn.radius * bcn.intensity))

            # Radial translucent glow layers
            glow_overlay = frame.copy()
            glow_layers = [r * 4.0, r * 2.8, r * 1.8]
            alphas = [0.12, 0.20, 0.35]

            for g_rad, alpha in zip(glow_layers, alphas):
                cv2.circle(glow_overlay, (bx, by), int(round(g_rad)), self.COLOR_BEACON_GLOW, -1, cv2.LINE_AA)
                cv2.addWeighted(glow_overlay, alpha, frame, 1.0 - alpha, 0, frame)

            # Solid inner bright core
            cv2.circle(frame, (bx, by), max(3, int(r * 0.7)), self.COLOR_BEACON_GLOW, -1, cv2.LINE_AA)
            cv2.circle(frame, (bx, by), max(2, int(r * 0.35)), self.COLOR_BEACON_CORE, -1, cv2.LINE_AA)
            
            # Beacon target reticle rings
            cv2.circle(frame, (bx, by), r + 8, self.COLOR_TERM_B, 1, cv2.LINE_AA)

        # Terminal labels
        cv2.putText(
            frame, self.env.terminal_b.name.upper(), (tx - 55, ty + size + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TERM_B, 1, cv2.LINE_AA
        )
        status_str = f"BEACON: {'ACTIVE' if bcn.active else 'OFF'} ({int(bcn.intensity*100)}%)"
        cv2.putText(
            frame, status_str, (tx - 55, ty + size + 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_BEACON_GLOW if bcn.active else self.COLOR_TEXT_DIM,
            1, cv2.LINE_AA
        )

    def _draw_hud_telemetry(self, frame: np.ndarray) -> None:
        """Draws top title banner, telemetry information box, and footer key hints."""
        # Top Banner Header
        cv2.rectangle(frame, (0, 0), (self.env.width, 36), (30, 24, 18), -1)
        cv2.line(frame, (0, 36), (self.env.width, 36), self.COLOR_HUD_BORDER, 1)
        
        cv2.putText(
            frame, "FSOC PAT SYSTEM  |  PHASE 1: VIRTUAL ENVIRONMENT DEMO", (20, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.COLOR_TEXT, 2, cv2.LINE_AA
        )
        
        cv2.putText(
            frame, "[ COLLEGE PROJECT - ROUND-1 EVALUATION ]", (self.env.width - 340, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_TERM_A, 1, cv2.LINE_AA
        )

        # Telemetry Card Box (Top Left)
        box_x, box_y, box_w, box_h = 20, 50, 360, 160
        overlay = frame.copy()
        cv2.rectangle(overlay, (box_x, box_y), (box_x + box_w, box_y + box_h), self.COLOR_HUD_BG, -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), self.COLOR_HUD_BORDER, 1)

        # Header inside Telemetry box
        cv2.putText(
            frame, "SYSTEM TELEMETRY", (box_x + 12, box_y + 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TERM_A, 1, cv2.LINE_AA
        )
        cv2.line(frame, (box_x + 10, box_y + 28), (box_x + box_w - 10, box_y + 28), self.COLOR_HUD_BORDER, 1)

        # Telemetry metrics lines
        cam = self.env.camera
        bcn = self.env.beacon
        dist = self.env.get_baseline_distance()

        lines = [
            f"Local Node    : {self.env.terminal_a.terminal_id} ({int(self.env.terminal_a.x)}, {int(self.env.terminal_a.y)})",
            f"Remote Node   : {self.env.terminal_b.terminal_id} ({int(self.env.terminal_b.x)}, {int(self.env.terminal_b.y)})",
            f"Baseline Path : {dist:.1f} px",
            f"Camera Angle  : {cam.orientation_deg:.1f} deg  (FOV: {cam.fov_deg:.1f} deg)",
            f"Beacon Status : {'EMITTING' if bcn.active else 'OFF'} (P={bcn.intensity:.2f})",
            f"Sim Clock     : {self.env.sim_time:.2f} s  |  Frames: {self.env.frame_count}"
        ]

        start_y = box_y + 46
        for i, line in enumerate(lines):
            cv2.putText(
                frame, line, (box_x + 12, start_y + i * 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_TEXT, 1, cv2.LINE_AA
            )

        # Bottom Footer Control Hint
        cv2.rectangle(frame, (0, self.env.height - 28), (self.env.width, self.env.height), (24, 18, 14), -1)
        cv2.line(frame, (0, self.env.height - 28), (self.env.width, self.env.height - 28), self.COLOR_HUD_BORDER, 1)
        cv2.putText(
            frame, "CONTROLS: Press [ Q ] or [ ESC ] to exit simulation",
            (20, self.env.height - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.COLOR_TEXT_DIM, 1, cv2.LINE_AA
        )
        cv2.putText(
            frame, "STATUS: SIMULATION OPERATIONAL",
            (self.env.width - 260, self.env.height - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (100, 220, 120), 1, cv2.LINE_AA
        )

    def _draw_dashed_line(
        self, frame: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int],
        color: Tuple[int, int, int], thickness: int = 1, dash_len: int = 6
    ) -> None:
        """Helper function to draw dashed lines between two points."""
        dist = math.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])
        if dist == 0:
            return
        
        dashes = int(dist / dash_len)
        dx = (pt2[0] - pt1[0]) / dashes
        dy = (pt2[1] - pt1[1]) / dashes

        for i in range(0, dashes, 2):
            start = (int(round(pt1[0] + i * dx)), int(round(pt1[1] + i * dy)))
            end = (int(round(pt1[0] + min(i + 1, dashes) * dx)), int(round(pt1[1] + min(i + 1, dashes) * dy)))
            cv2.line(frame, start, end, color, thickness, cv2.LINE_AA)
