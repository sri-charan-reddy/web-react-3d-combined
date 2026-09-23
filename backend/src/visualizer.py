"""OpenCV-based visualization and manual demonstration tool for Part 2.

This module provides:
- Live 2D canvas rendering of:
  1. Ground-Truth motion trajectory (GREEN)
  2. Actual optical measurements (YELLOW), including rejected outlier markers
  3. Kalman predicted / corrected tracking trajectory (BLUE)
  4. Virtual Camera Field of View (FOV) rectangle and optical axis crosshair
  5. Local Search bounding radius circle, pattern waypoints, and scan target (CYAN/ORANGE)
- Visual cues for state machine transitions (TRACKING, PREDICTING, SEARCHING, REACQUIRING, LOST).
- Real-time telemetry Heads-Up Display (HUD) indicating Frame, Detection, State,
  Confidence, Miss Count, Measurement Acceptance, Camera FOV, and Local Search status.
"""

from typing import List, Optional, Tuple
import cv2
import numpy as np

from config import VisualizerConfig
from src.tracking_state import BeaconMeasurement, TrackingResult, TrackingState, PerformanceMetrics
from src.virtual_camera import VirtualCamera, CameraTelemetry
from src.camera_controller import CameraController, ControllerMode
from src.local_search import LocalSearch, LocalSearchTelemetry
from src.atmospheric_turbulence import AtmosphericTurbulence, TurbulenceLevel, TurbulenceTelemetry


class TrackingVisualizer:
    """Renders real-time 2D beacon motion, optical detections, Kalman tracks, and telemetry HUD."""

    def __init__(self, config: Optional[VisualizerConfig] = None) -> None:
        """Initialize visualization canvas dimensions, color palettes, and trajectory trails.
        
        Args:
            config: Visualizer configuration settings.
        """
        self.config = config or VisualizerConfig()
        self.ground_truth_history: List[Tuple[float, float]] = []
        self.measurement_history: List[Optional[Tuple[float, float]]] = []
        self.kalman_history: List[Tuple[float, float]] = []
        
        # Color palette (BGR format for OpenCV)
        self.COLOR_BG = (22, 24, 28)             # Dark slate background
        self.COLOR_GRID = (36, 40, 48)           # Background grid
        self.COLOR_GT = (0, 230, 115)            # GREEN for ground truth
        self.COLOR_GT_TRAIL = (0, 140, 70)       # Dimmer green trail
        self.COLOR_MEAS = (0, 215, 255)          # YELLOW / GOLD for optical measurements
        self.COLOR_MEAS_TRAIL = (0, 120, 160)    # Dimmer gold points
        self.COLOR_KALMAN = (255, 175, 40)       # BLUE / CYAN for Kalman track (BGR: 255, 175, 40)
        self.COLOR_KALMAN_TRAIL = (180, 110, 20) # Dimmer blue trail
        self.COLOR_CAMERA_FOV = (140, 130, 80)   # Subtle slate-blue for camera FOV rectangle
        self.COLOR_SEARCH = (0, 215, 255)        # Vivid gold/cyan for local search
        self.COLOR_TEXT_PRIMARY = (240, 240, 240)
        self.COLOR_TEXT_MUTED = (160, 160, 160)
        
        # State-specific colors
        self.STATE_COLORS = {
            TrackingState.UNINITIALIZED: (140, 140, 140),  # Gray
            TrackingState.TRACKING: (50, 220, 50),         # Bright Green
            TrackingState.PREDICTING: (0, 165, 255),       # Orange
            TrackingState.SEARCHING: (0, 215, 255),        # Bright Gold / Yellow
            TrackingState.REACQUIRING: (255, 220, 0),      # Cyan / Gold
            TrackingState.LOST: (50, 50, 235)              # Bright Red
        }

    def render_frame(
        self,
        ground_truth: Tuple[float, float],
        measurement: BeaconMeasurement,
        tracking_result: TrackingResult,
        frame_idx: int,
        fps_display: float = 30.0,
        camera: Optional[VirtualCamera] = None,
        controller: Optional[CameraController] = None,
        search: Optional[LocalSearch] = None,
        turbulence: Optional[AtmosphericTurbulence] = None,
        metrics: Optional[PerformanceMetrics] = None
    ) -> np.ndarray:
        """Render a single visualization frame combining GT, Measurement, Kalman track, Camera FOV, Search, Turbulence, and HUD.
        
        Args:
            ground_truth: True (x, y) beacon position.
            measurement: BeaconMeasurement containing detection status and measured (x, y).
            tracking_result: TrackingResult containing Kalman predicted/corrected state and FSM telemetry.
            frame_idx: Current simulation frame count.
            fps_display: Live measured FPS.
            camera: Optional VirtualCamera instance to render FOV bounds.
            controller: Optional CameraController instance to render pan/tilt telemetry.
            search: Optional LocalSearch instance to render local search bounds and target.
            turbulence: Optional AtmosphericTurbulence instance to render turbulence telemetry.
            metrics: Optional PerformanceMetrics instance to display tracking accuracy and latency.
            
        Returns:
            np.ndarray: BGR image canvas suitable for cv2.imshow.
        """
        # 1. Create base canvas with grid
        canvas = np.full(
            (self.config.canvas_height, self.config.canvas_width, 3),
            self.COLOR_BG,
            dtype=np.uint8
        )
        self._draw_grid(canvas)

        # 2. Draw Virtual Camera FOV rectangle if enabled
        if camera is not None and getattr(self.config, "show_camera_fov", True):
            self._draw_camera_fov(canvas, camera, tracking_result)

        # 3. Draw Local Search Region & Waypoints if searching
        if search is not None and getattr(self.config, "show_local_search", True):
            self._draw_local_search(canvas, search, tracking_result)

        # 4. Update trajectory histories
        self.ground_truth_history.append(ground_truth)
        if len(self.ground_truth_history) > self.config.trail_length:
            self.ground_truth_history.pop(0)

        meas_pos = measurement.position if measurement.detected else None
        self.measurement_history.append(meas_pos)
        if len(self.measurement_history) > self.config.trail_length:
            self.measurement_history.pop(0)

        kalman_pos = tracking_result.position
        self.kalman_history.append(kalman_pos)
        if len(self.kalman_history) > self.config.trail_length:
            self.kalman_history.pop(0)

        # 5. Draw Ground Truth Trajectory Trail (GREEN)
        if self.config.show_ground_truth and len(self.ground_truth_history) >= 2:
            pts = np.array(self.ground_truth_history, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(canvas, [pts], isClosed=False, color=self.COLOR_GT_TRAIL, thickness=2, lineType=cv2.LINE_AA)

        # 6. Draw Measurement History Dots (YELLOW)
        if self.config.show_measurements:
            for pt in self.measurement_history:
                if pt is not None:
                    cv2.circle(canvas, (int(pt[0]), int(pt[1])), 2, self.COLOR_MEAS_TRAIL, -1, lineType=cv2.LINE_AA)

        # 7. Draw Kalman Track Trajectory Trail (BLUE)
        if len(self.kalman_history) >= 2:
            k_pts = np.array(self.kalman_history, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(canvas, [k_pts], isClosed=False, color=self.COLOR_KALMAN_TRAIL, thickness=2, lineType=cv2.LINE_AA)

        # 8. Draw Ground Truth Beacon Position (GREEN circle)
        if self.config.show_ground_truth:
            gt_x, gt_y = int(ground_truth[0]), int(ground_truth[1])
            cv2.circle(canvas, (gt_x, gt_y), 9, self.COLOR_GT, 2, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (gt_x, gt_y), 3, self.COLOR_GT, -1, lineType=cv2.LINE_AA)
            cv2.putText(canvas, "GT", (gt_x + 12, gt_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_GT, 1, cv2.LINE_AA)

        # 9. Draw Optical Measurement (YELLOW or RED if outlier)
        if measurement.detected and measurement.position is not None:
            m_x, m_y = int(measurement.position[0]), int(measurement.position[1])
            if tracking_result.measurement_accepted:
                # Valid accepted measurement
                cv2.circle(canvas, (m_x, m_y), 13, self.COLOR_MEAS, 1, lineType=cv2.LINE_AA)
                cv2.drawMarker(canvas, (m_x, m_y), self.COLOR_MEAS, markerType=cv2.MARKER_CROSS, markerSize=14, thickness=1, line_type=cv2.LINE_AA)
                cv2.putText(canvas, "MEAS", (m_x + 16, m_y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLOR_MEAS, 1, cv2.LINE_AA)
            else:
                # Rejected outlier measurement
                cv2.circle(canvas, (m_x, m_y), 18, (0, 0, 255), 2, lineType=cv2.LINE_AA)
                cv2.drawMarker(canvas, (m_x, m_y), (0, 0, 255), markerType=cv2.MARKER_TILTED_CROSS, markerSize=16, thickness=2, line_type=cv2.LINE_AA)
                cv2.putText(canvas, "OUTLIER (REJECTED)", (m_x + 22, m_y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 80, 255), 2, cv2.LINE_AA)

        # 10. Draw Kalman Track Position (BLUE circle / target with state-specific label)
        if tracking_result.state != TrackingState.UNINITIALIZED:
            k_x, k_y = int(kalman_pos[0]), int(kalman_pos[1])
            state_col = self.STATE_COLORS.get(tracking_result.state, self.COLOR_KALMAN)
            cv2.circle(canvas, (k_x, k_y), 16, state_col, 2, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (k_x, k_y), 3, state_col, -1, lineType=cv2.LINE_AA)
            
            mode_lbl = f"KALMAN ({tracking_result.state.name})"
            cv2.putText(canvas, mode_lbl, (k_x + 18, k_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, state_col, 1, cv2.LINE_AA)

        # 11. Draw Telemetry HUD
        self._draw_hud(
            canvas,
            ground_truth,
            measurement,
            tracking_result,
            frame_idx,
            fps_display,
            camera,
            controller,
            search,
            turbulence,
            metrics
        )

        return canvas

    def _draw_local_search(
        self,
        canvas: np.ndarray,
        search: LocalSearch,
        tracking_result: TrackingResult
    ) -> None:
        """Render bounded search radius circle, search target waypoint, and scan vectors."""
        if tracking_result.state != TrackingState.SEARCHING and not search.is_active:
            return

        cx, cy = int(search.search_center[0]), int(search.search_center[1])
        radius = int(search.config.search_radius_px)
        
        # 1. Bounded search radius circle around Kalman prediction
        cv2.circle(canvas, (cx, cy), radius, (60, 140, 180), 1, lineType=cv2.LINE_AA)
        
        # 2. Draw search target waypoint and scan line
        tx, ty = int(search.search_target[0]), int(search.search_target[1])
        cv2.line(canvas, (cx, cy), (tx, ty), (0, 180, 230), 1, lineType=cv2.LINE_AA)
        cv2.drawMarker(canvas, (tx, ty), (0, 220, 255), markerType=cv2.MARKER_DIAMOND, markerSize=12, thickness=2, line_type=cv2.LINE_AA)
        
        wp_str = f"SEARCH WP #{search.step_index + 1}"
        cv2.putText(canvas, wp_str, (tx + 10, ty + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 220, 255), 1, cv2.LINE_AA)

    def _draw_camera_fov(
        self,
        canvas: np.ndarray,
        camera: VirtualCamera,
        tracking_result: Optional[TrackingResult] = None
    ) -> None:
        """Render virtual camera FOV bounding box, optical center reticle, and servo line."""
        min_x, max_x, min_y, max_y = camera.get_fov_bounds()
        x1, y1 = int(min_x), int(min_y)
        x2, y2 = int(max_x), int(max_y)

        # Draw FOV boundary rectangle
        cv2.rectangle(canvas, (x1, y1), (x2, y2), self.COLOR_CAMERA_FOV, 1)

        # Draw corner brackets for tactical/instrument look
        b_len = 16
        col = (180, 170, 110)
        # Top-left
        cv2.line(canvas, (x1, y1), (x1 + b_len, y1), col, 2)
        cv2.line(canvas, (x1, y1), (x1, y1 + b_len), col, 2)
        # Top-right
        cv2.line(canvas, (x2, y1), (x2 - b_len, y1), col, 2)
        cv2.line(canvas, (x2, y1), (x2, y1 + b_len), col, 2)
        # Bottom-left
        cv2.line(canvas, (x1, y2), (x1 + b_len, y2), col, 2)
        cv2.line(canvas, (x1, y2), (x1, y2 - b_len), col, 2)
        # Bottom-right
        cv2.line(canvas, (x2, y2), (x2 - b_len, y2), col, 2)
        cv2.line(canvas, (x2, y2), (x2, y2 - b_len), col, 2)

        # Center reticle
        cx, cy = int(camera.center[0]), int(camera.center[1])
        cv2.drawMarker(canvas, (cx, cy), self.COLOR_CAMERA_FOV, markerType=cv2.MARKER_CROSS, markerSize=14, thickness=1, line_type=cv2.LINE_AA)
        
        # Draw line from camera center to Kalman track to show servo error
        if tracking_result is not None and tracking_result.state in (TrackingState.TRACKING, TrackingState.PREDICTING, TrackingState.SEARCHING, TrackingState.REACQUIRING):
            kx, ky = int(tracking_result.position[0]), int(tracking_result.position[1])
            cv2.line(canvas, (cx, cy), (kx, ky), (80, 100, 140), 1, lineType=cv2.LINE_AA)

        # FOV label
        fov_str = f"VIRTUAL CAMERA FOV [{int(camera.fov_width)}x{int(camera.fov_height)}]"
        cv2.putText(canvas, fov_str, (x1 + 8, y1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.40, col, 1, cv2.LINE_AA)

    def _draw_grid(self, canvas: np.ndarray, step: int = 80) -> None:
        """Draw subtle Cartesian grid lines across the canvas."""
        h, w = canvas.shape[:2]
        for x in range(0, w, step):
            cv2.line(canvas, (x, 0), (x, h), self.COLOR_GRID, 1)
        for y in range(0, h, step):
            cv2.line(canvas, (0, y), (w, y), self.COLOR_GRID, 1)

    def _draw_hud(
        self,
        canvas: np.ndarray,
        ground_truth: Tuple[float, float],
        measurement: BeaconMeasurement,
        tracking_result: TrackingResult,
        frame_idx: int,
        fps: float,
        camera: Optional[VirtualCamera] = None,
        controller: Optional[CameraController] = None,
        search: Optional[LocalSearch] = None,
        turbulence: Optional[AtmosphericTurbulence] = None,
        metrics: Optional[PerformanceMetrics] = None
    ) -> None:
        """Render top-left telemetry HUD card and status alert banners."""
        card_w = 510
        card_h = 425 if (camera is not None and turbulence is not None) else 350
        sub_img = canvas[15:15 + card_h, 15:15 + card_w]
        white_rect = np.zeros(sub_img.shape, dtype=np.uint8)
        res = cv2.addWeighted(sub_img, 0.35, white_rect, 0.65, 1.0)
        canvas[15:15 + card_h, 15:15 + card_w] = res
        cv2.rectangle(canvas, (15, 15), (15 + card_w, 15 + card_h), (60, 68, 80), 1)

        # Header
        cv2.putText(canvas, "SIH PART 2 - PREDICTIVE TRACKING & DISTURBANCE", (26, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (100, 200, 255), 1, cv2.LINE_AA)
        cv2.line(canvas, (26, 46), (26 + card_w - 24, 46), (60, 68, 80), 1)

        line_y = 66
        spacing = 20

        # 1. Frame & FPS
        cv2.putText(canvas, f"Frame: {frame_idx:04d}  |  FPS: {fps:.1f}", (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TEXT_PRIMARY, 1, cv2.LINE_AA)
        
        # 2. Detection Available
        line_y += spacing
        if measurement.detected:
            det_text = "Detection: YES (Optical Signal Received)"
            det_color = (50, 220, 50)
        else:
            det_text = "Detection: NO (Out of FOV / Occluded)"
            det_color = (50, 50, 235)

        cv2.putText(canvas, det_text, (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, det_color, 1, cv2.LINE_AA)

        # 3. Ground Truth Coordinates
        line_y += spacing
        gt_str = f"Ground Truth: ({ground_truth[0]:.1f}, {ground_truth[1]:.1f})"
        cv2.putText(canvas, gt_str, (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_GT, 1, cv2.LINE_AA)

        # 4. Measurement Coordinates
        line_y += spacing
        if measurement.detected and measurement.position is not None:
            meas_str = f"Measurement:  ({measurement.position[0]:.1f}, {measurement.position[1]:.1f})"
            meas_color = self.COLOR_MEAS
        else:
            meas_str = "Measurement:  NONE"
            meas_color = (50, 50, 235)

        cv2.putText(canvas, meas_str, (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, meas_color, 1, cv2.LINE_AA)

        # 5. Kalman Track Coordinates
        line_y += spacing
        k_str = f"Kalman Track: ({tracking_result.position[0]:.1f}, {tracking_result.position[1]:.1f})"
        cv2.putText(canvas, k_str, (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_KALMAN, 1, cv2.LINE_AA)

        # 6. Velocity
        line_y += spacing
        vel_str = f"Velocity:     ({tracking_result.velocity[0]:.1f}, {tracking_result.velocity[1]:.1f}) px/s"
        cv2.putText(canvas, vel_str, (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TEXT_PRIMARY, 1, cv2.LINE_AA)

        # 7. State & Miss Count
        line_y += spacing
        st_color = self.STATE_COLORS.get(tracking_result.state, (200, 200, 200))
        st_str = f"State: {tracking_result.state.name}  |  Miss Count: {tracking_result.miss_count}"
        cv2.putText(canvas, st_str, (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.47, st_color, 2, cv2.LINE_AA)

        # 8. Confidence Health Bar
        line_y += spacing
        conf_pct = int(tracking_result.confidence * 100)
        cv2.putText(canvas, f"Confidence: {tracking_result.confidence:.2f} ({conf_pct}%)", (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TEXT_PRIMARY, 1, cv2.LINE_AA)
        
        # Draw confidence bar
        bar_x = 240
        bar_w = 230
        bar_h = 10
        cv2.rectangle(canvas, (bar_x, line_y - 10), (bar_x + bar_w, line_y), (50, 54, 62), -1)
        fill_w = int(bar_w * max(0.0, min(1.0, tracking_result.confidence)))
        fill_col = (50, 220, 50) if tracking_result.confidence > 0.6 else ((0, 165, 255) if tracking_result.confidence > 0.3 else (50, 50, 235))
        if fill_w > 0:
            cv2.rectangle(canvas, (bar_x, line_y - 10), (bar_x + fill_w, line_y), fill_col, -1)
        cv2.rectangle(canvas, (bar_x, line_y - 10), (bar_x + bar_w, line_y), (90, 95, 105), 1)

        # 9. Measurement Accepted Status
        line_y += spacing
        if measurement.detected:
            if tracking_result.measurement_accepted:
                acc_str = "Measurement Accepted: YES (Gating Passed)"
                acc_col = (50, 220, 50)
            else:
                acc_str = "Measurement Accepted: NO (OUTLIER REJECTED)"
                acc_col = (50, 50, 235)
        else:
            acc_str = "Measurement Accepted: N/A (No Detection)"
            acc_col = self.COLOR_TEXT_MUTED

        cv2.putText(canvas, acc_str, (26, line_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, acc_col, 1, cv2.LINE_AA)

        # 10. Virtual Camera Telemetry
        if camera is not None:
            line_y += spacing
            in_fov = camera.is_in_fov(ground_truth)
            fov_color = (50, 220, 50) if in_fov else (0, 165, 255)
            fov_status = "INSIDE FOV" if in_fov else "OUTSIDE FOV"
            cam_str = f"Camera Center: ({camera.pan:.1f}, {camera.tilt:.1f})  |  Beacon: {fov_status}"
            cv2.putText(canvas, cam_str, (26, line_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, fov_color, 1, cv2.LINE_AA)

        # 11. Local Search Telemetry
        if search is not None:
            line_y += spacing
            if tracking_result.state == TrackingState.SEARCHING:
                s_status = f"SCANNING (WP #{search.step_index+1}/{len(search.pattern_offsets)})"
                s_col = (0, 215, 255)
            else:
                s_status = "STANDBY"
                s_col = self.COLOR_TEXT_MUTED
            s_str = f"Local Search: {s_status}  |  Radius: {int(search.config.search_radius_px)} px"
            cv2.putText(canvas, s_str, (26, line_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.43, s_col, 1, cv2.LINE_AA)

        # 12. Atmospheric Turbulence Telemetry
        if turbulence is not None:
            line_y += spacing
            t_telem = turbulence.get_telemetry()
            if t_telem.enabled:
                t_col = (0, 220, 255) if t_telem.level == TurbulenceLevel.MEDIUM else ((50, 220, 50) if t_telem.level == TurbulenceLevel.LOW else (0, 140, 255))
                t_str = f"Atmospheric Turb: {t_telem.level.value} | Offset: ({t_telem.offset_x:+.1f}, {t_telem.offset_y:+.1f}) px | Disp: {t_telem.displacement:.1f} px"
            else:
                t_col = self.COLOR_TEXT_MUTED
                t_str = "Atmospheric Turb: OFF (Press [T] to toggle)"
            cv2.putText(canvas, t_str, (26, line_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.43, t_col, 1, cv2.LINE_AA)

        # 13. Tracking Performance Error Telemetry
        if metrics is not None:
            line_y += spacing
            p_str = f"Track Error: {metrics.current_tracking_error_px:.1f} px (Avg: {metrics.avg_tracking_error_px:.1f} px, Max: {metrics.max_tracking_error_px:.1f} px) | Lock: {metrics.lock_retention_pct:.1f}%"
            cv2.putText(canvas, p_str, (26, line_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 210, 255), 1, cv2.LINE_AA)

        # Top Center Alert Banners
        if measurement.detected and not tracking_result.measurement_accepted:
            banner_text = "--- OUTLIER DETECTED: MEASUREMENT REJECTED BY GATING ---"
            text_size = cv2.getTextSize(banner_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)[0]
            b_x = (self.config.canvas_width - text_size[0]) // 2
            cv2.rectangle(canvas, (b_x - 14, 18), (b_x + text_size[0] + 14, 52), (0, 0, 180), -1)
            cv2.putText(canvas, banner_text, (b_x, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)
        elif tracking_result.state == TrackingState.LOST:
            banner_text = f"--- TRACKING LOST: SEARCH & PREDICTION LIMIT EXCEEDED ---"
            text_size = cv2.getTextSize(banner_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)[0]
            b_x = (self.config.canvas_width - text_size[0]) // 2
            cv2.rectangle(canvas, (b_x - 14, 18), (b_x + text_size[0] + 14, 52), (0, 0, 180), -1)
            cv2.putText(canvas, banner_text, (b_x, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)
        elif tracking_result.state == TrackingState.SEARCHING:
            banner_text = f"--- LOCAL SEARCH ACTIVE: SCANNING REGION AROUND KALMAN PREDICTION ---"
            text_size = cv2.getTextSize(banner_text, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 2)[0]
            b_x = (self.config.canvas_width - text_size[0]) // 2
            cv2.rectangle(canvas, (b_x - 14, 18), (b_x + text_size[0] + 14, 52), (0, 140, 200), -1)
            cv2.putText(canvas, banner_text, (b_x, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 2, cv2.LINE_AA)
        elif tracking_result.state == TrackingState.PREDICTING:
            banner_text = f"--- OCCLUSION: KALMAN PREDICTIVE SERVOING (Miss {tracking_result.miss_count}) ---"
            text_size = cv2.getTextSize(banner_text, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 2)[0]
            b_x = (self.config.canvas_width - text_size[0]) // 2
            cv2.rectangle(canvas, (b_x - 14, 18), (b_x + text_size[0] + 14, 52), (0, 100, 200), -1)
            cv2.putText(canvas, banner_text, (b_x, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 2, cv2.LINE_AA)
        elif tracking_result.state == TrackingState.REACQUIRING:
            banner_text = "--- BEACON REACQUIRED: RE-LOCKING TRACKING & SERVO ---"
            text_size = cv2.getTextSize(banner_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)[0]
            b_x = (self.config.canvas_width - text_size[0]) // 2
            cv2.rectangle(canvas, (b_x - 14, 18), (b_x + text_size[0] + 14, 52), (0, 140, 0), -1)
            cv2.putText(canvas, banner_text, (b_x, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)

    def reset(self) -> None:
        """Clear all historical trajectory trails."""
        self.ground_truth_history.clear()
        self.measurement_history.clear()
        self.kalman_history.clear()
