from __future__ import annotations

from collections import deque
from typing import Deque

from app.config import (
    REFERENCE_DISTANCE_METERS,
    REFERENCE_IMAGE_DISTANCE_PIXELS,
    SPEED_MAX_VALID_KMH,
)


class SpeedEstimator:
    """
    Prototype speed estimator for tracked vehicles.

    IMPORTANT:
    The current calibration is a prototype calibration.
    Real-world km/h values require measured camera calibration
    and known road geometry.
    """

    def __init__(
        self,
        reference_distance_meters: float = REFERENCE_DISTANCE_METERS,
        reference_image_distance_pixels: float = REFERENCE_IMAGE_DISTANCE_PIXELS,
        history_size: int = 8,
        min_samples: int = 4,
        smoothing_window: int = 5,
        max_valid_speed_kmh: float = SPEED_MAX_VALID_KMH,
    ):
        if reference_distance_meters <= 0:
            raise ValueError("Reference distance must be greater than zero.")

        if reference_image_distance_pixels <= 0:
            raise ValueError(
                "Reference image distance must be greater than zero."
            )

        self.reference_distance_meters = reference_distance_meters
        self.reference_image_distance_pixels = reference_image_distance_pixels
        self.meters_per_pixel = (
            reference_distance_meters / reference_image_distance_pixels
        )

        self.history_size = history_size
        self.min_samples = min_samples
        self.smoothing_window = smoothing_window
        self.max_valid_speed_kmh = max_valid_speed_kmh

        self.position_history: dict[int, Deque[tuple[int, int, int]]] = {}
        self.speed_history: dict[int, Deque[float]] = {}

    @staticmethod
    def distance_pixels(
        previous_position: tuple[int, int],
        current_position: tuple[int, int],
    ) -> float:
        dx = current_position[0] - previous_position[0]
        dy = current_position[1] - previous_position[1]

        return (dx * dx + dy * dy) ** 0.5

    def calculate_speed(
        self,
        track_id: int,
        center: tuple[int, int],
        frame_index: int,
        fps: float,
    ) -> dict:
        if fps <= 0:
            return {
                "speed_kmh": None,
                "valid": False,
                "reason": "invalid_fps",
            }

        history = self.position_history.setdefault(
            track_id,
            deque(maxlen=self.history_size),
        )

        current = (int(center[0]), int(center[1]), int(frame_index))

        if history:
            previous = history[-1]

            pixel_distance = self.distance_pixels(
                (previous[0], previous[1]),
                (current[0], current[1]),
            )

            frame_delta = current[2] - previous[2]

            if frame_delta <= 0:
                history.append(current)

                return {
                    "speed_kmh": None,
                    "valid": False,
                    "reason": "invalid_frame_delta",
                }

            time_seconds = frame_delta / fps

            distance_meters = pixel_distance * self.meters_per_pixel

            speed_mps = distance_meters / time_seconds
            speed_kmh = speed_mps * 3.6

            history.append(current)

            if speed_kmh > self.max_valid_speed_kmh:
                return {
                    "speed_kmh": None,
                    "valid": False,
                    "reason": "speed_outlier",
                    "raw_speed_kmh": round(speed_kmh, 2),
                }

            if speed_kmh < 0:
                return {
                    "speed_kmh": None,
                    "valid": False,
                    "reason": "negative_speed",
                }

            speeds = self.speed_history.setdefault(
                track_id,
                deque(maxlen=self.smoothing_window),
            )

            speeds.append(speed_kmh)

            smoothed_speed = sum(speeds) / len(speeds)

            return {
                "speed_kmh": round(smoothed_speed, 2),
                "valid": True,
                "reason": "ok",
                "raw_speed_kmh": round(speed_kmh, 2),
                "distance_meters": round(distance_meters, 4),
                "time_seconds": round(time_seconds, 4),
            }

        history.append(current)

        return {
            "speed_kmh": None,
            "valid": False,
            "reason": "insufficient_history",
        }

    def reset_track(self, track_id: int) -> None:
        self.position_history.pop(track_id, None)
        self.speed_history.pop(track_id, None)

    def reset(self) -> None:
        self.position_history.clear()
        self.speed_history.clear()

    def calibration_info(self) -> dict:
        return {
            "reference_distance_meters": self.reference_distance_meters,
            "reference_image_distance_pixels": (
                self.reference_image_distance_pixels
            ),
            "meters_per_pixel": round(self.meters_per_pixel, 6),
            "calibration_status": "prototype",
            "real_world_calibration_required": True,
            "max_valid_speed_kmh": self.max_valid_speed_kmh,
        }


speed_estimator = SpeedEstimator()
