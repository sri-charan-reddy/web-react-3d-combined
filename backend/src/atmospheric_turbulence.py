"""Atmospheric Turbulence and Optical Disturbance Simulation for Part 2.

This module provides:
- First-order Gauss-Markov (Autoregressive AR(1)) beam wander and optical turbulence model.
- Realistic temporal correlation (smooth frame-to-frame drift mimicking Greenwood frequency optical jitter).
- Configurable turbulence severity levels: OFF, LOW, MEDIUM, HIGH.
- Strictly bounded displacement envelope ensuring disturbance stays within physical aperture limits.
- Optical scintillation / signal quality fluctuation modeling.
- Strict isolation: perturbs ONLY the simulated optical observation feed, NEVER modifying Ground Truth.
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple
import numpy as np

from config import AtmosphericTurbulenceConfig, TurbulenceLevel


@dataclass
class TurbulenceTelemetry:
    """Telemetry snapshot of atmospheric turbulence state."""
    enabled: bool
    level: TurbulenceLevel
    offset_x: float
    offset_y: float
    displacement: float
    scintillation_factor: float


class AtmosphericTurbulence:
    """Simulates temporally correlated beam wander and optical turbulence in FSOC links."""

    def __init__(self, config: Optional[AtmosphericTurbulenceConfig] = None) -> None:
        """Initialize atmospheric turbulence model with correlation and strength parameters.
        
        Args:
            config: AtmosphericTurbulenceConfig instance.
        """
        self.config = config or AtmosphericTurbulenceConfig()
        self.rng = np.random.RandomState(self.config.random_seed)
        
        self.level: TurbulenceLevel = self.config.level if self.config.enabled else TurbulenceLevel.OFF
        self.current_offset: np.ndarray = np.zeros(2, dtype=np.float64)  # [dx, dy]
        self.scintillation_factor: float = 1.0

    def set_level(self, level: TurbulenceLevel) -> None:
        """Set turbulence severity level.
        
        Args:
            level: TurbulenceLevel enum value (OFF, LOW, MEDIUM, HIGH).
        """
        self.level = level
        if level == TurbulenceLevel.OFF:
            self.current_offset = np.zeros(2, dtype=np.float64)
            self.scintillation_factor = 1.0

    def toggle_level(self) -> TurbulenceLevel:
        """Cycle through turbulence severity levels: OFF -> LOW -> MEDIUM -> HIGH -> OFF.
        
        Returns:
            New active TurbulenceLevel.
        """
        cycle = [
            TurbulenceLevel.OFF,
            TurbulenceLevel.LOW,
            TurbulenceLevel.MEDIUM,
            TurbulenceLevel.HIGH
        ]
        curr_idx = cycle.index(self.level)
        next_idx = (curr_idx + 1) % len(cycle)
        self.set_level(cycle[next_idx])
        return self.level

    def _get_level_params(self) -> Tuple[float, float]:
        """Get standard deviation and max displacement for current severity level.
        
        Returns:
            Tuple of (sigma_std, max_displacement).
        """
        if self.level == TurbulenceLevel.LOW:
            return self.config.std_low, self.config.max_displacement_low
        elif self.level == TurbulenceLevel.MEDIUM:
            return self.config.std_medium, self.config.max_displacement_medium
        elif self.level == TurbulenceLevel.HIGH:
            return self.config.std_high, self.config.max_displacement_high
        else:
            return 0.0, 0.0

    def apply(self, optical_position: Tuple[float, float]) -> Tuple[float, float]:
        """Apply atmospheric turbulence perturbation to observed optical coordinates.
        
        Note: The input optical_position is NEVER mutated. A new perturbed coordinate tuple is returned.
        Ground truth state is completely untouched.
        
        Args:
            optical_position: Pure optical beacon coordinates (x, y).
            
        Returns:
            Perturbed optical coordinates (x + dx, y + dy).
        """
        if self.level == TurbulenceLevel.OFF:
            self.current_offset = np.zeros(2, dtype=np.float64)
            self.scintillation_factor = 1.0
            return (float(optical_position[0]), float(optical_position[1]))

        sigma, max_disp = self._get_level_params()
        rho = float(np.clip(self.config.temporal_correlation, 0.0, 0.999))
        
        # 1. First-order Gauss-Markov AR(1) innovation
        # dx_t = rho * dx_{t-1} + sqrt(1 - rho^2) * sigma * w_t
        innovation_scale = math.sqrt(max(0.0, 1.0 - rho * rho)) * sigma
        noise = self.rng.normal(0.0, 1.0, size=2)
        
        new_offset = rho * self.current_offset + innovation_scale * noise
        
        # 2. Enforce strict bounded displacement envelope
        disp = math.sqrt(new_offset[0] ** 2 + new_offset[1] ** 2)
        if max_disp > 0.0 and disp > max_disp:
            new_offset = new_offset * (max_disp / disp)
            disp = max_disp
            
        self.current_offset = new_offset
        
        # 3. Scintillation / intensity fluctuation
        if self.config.enable_scintillation and self.config.scintillation_std > 0:
            scint_noise = self.rng.normal(0.0, self.config.scintillation_std)
            # Log-normal intensity fluctuation normalized near 1.0
            self.scintillation_factor = float(np.clip(math.exp(scint_noise - 0.5 * self.config.scintillation_std**2), 0.6, 1.2))
        else:
            self.scintillation_factor = 1.0

        # Return perturbed optical position
        pert_x = float(optical_position[0] + self.current_offset[0])
        pert_y = float(optical_position[1] + self.current_offset[1])
        return (pert_x, pert_y)

    def get_telemetry(self) -> TurbulenceTelemetry:
        """Retrieve telemetry snapshot of atmospheric turbulence status.
        
        Returns:
            TurbulenceTelemetry instance.
        """
        disp = float(math.sqrt(self.current_offset[0] ** 2 + self.current_offset[1] ** 2))
        return TurbulenceTelemetry(
            enabled=(self.level != TurbulenceLevel.OFF),
            level=self.level,
            offset_x=float(self.current_offset[0]),
            offset_y=float(self.current_offset[1]),
            displacement=disp,
            scintillation_factor=self.scintillation_factor
        )

    def reset(self) -> None:
        """Reset internal turbulence state and random number generator."""
        self.rng = np.random.RandomState(self.config.random_seed)
        self.current_offset = np.zeros(2, dtype=np.float64)
        self.scintillation_factor = 1.0
        self.level = self.config.level if self.config.enabled else TurbulenceLevel.OFF
