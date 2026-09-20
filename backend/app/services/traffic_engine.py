from __future__ import annotations

from collections import deque
from typing import Iterable

from app.config import (
    DENSITY_LOW_MAX,
    DENSITY_MODERATE_MAX,
    DENSITY_HIGH_MAX,
    SPEED_FREE_FLOW_MIN,
    SPEED_SLOWING_MIN,
    SPEED_SLOW_MIN,
)


class TrafficEngine:
    """
    Traffic intelligence based on tracked vehicle observations.

    Density is the primary signal.
    Speed is a supporting signal.

    The thresholds and scoring rules are the validated
    RoadLink Phase 2.2 prototype rules.
    """

    DENSITY_SCORES = {
        "LOW": 0,
        "MODERATE": 35,
        "HIGH": 70,
        "CRITICAL": 100,
    }

    SPEED_SCORES = {
        "FREE_FLOW": 0,
        "SLOWING": 25,
        "SLOW": 60,
        "STOPPED_OR_CRAWLING": 85,
        "UNKNOWN": 0,
    }

    def __init__(
        self,
        persistence_window: int = 5,
    ):
        self.persistence_window = persistence_window
        self.recent_states: deque[str] = deque(
            maxlen=persistence_window
        )

    @staticmethod
    def calculate_density_category(
        active_vehicle_count: int,
    ) -> str:
        if active_vehicle_count <= DENSITY_LOW_MAX:
            return "LOW"

        if active_vehicle_count <= DENSITY_MODERATE_MAX:
            return "MODERATE"

        if active_vehicle_count <= DENSITY_HIGH_MAX:
            return "HIGH"

        return "CRITICAL"

    @staticmethod
    def calculate_speed_category(
        average_speed_kmh: float | None,
    ) -> str:
        if average_speed_kmh is None:
            return "UNKNOWN"

        if average_speed_kmh >= SPEED_FREE_FLOW_MIN:
            return "FREE_FLOW"

        if average_speed_kmh >= SPEED_SLOWING_MIN:
            return "SLOWING"

        if average_speed_kmh >= SPEED_SLOW_MIN:
            return "SLOW"

        return "STOPPED_OR_CRAWLING"

    @classmethod
    def calculate_traffic_score(
        cls,
        density_category: str,
        speed_category: str,
    ) -> float:

        density_score = cls.DENSITY_SCORES.get(
            density_category,
            0,
        )

        speed_score = cls.SPEED_SCORES.get(
            speed_category,
            0,
        )

        score = (
            density_score * 0.70
            + speed_score * 0.30
        )

        return round(score, 2)

    def determine_traffic_state(
        self,
        density_category: str,
        speed_category: str,
    ) -> str:

        # LOW density is always LOW.
        if density_category == "LOW":
            state = "LOW"

        # MODERATE density remains MODERATE.
        elif density_category == "MODERATE":
            state = "MODERATE"

        # HIGH density requires slow/stopped traffic
        # and persistence before becoming HIGH.
        elif density_category == "HIGH":
            severe_speed = speed_category in (
                "SLOW",
                "STOPPED_OR_CRAWLING",
            )

            if severe_speed and self._persistent(
                "HIGH"
            ):
                state = "HIGH"
            else:
                state = "MODERATE"

        # CRITICAL density requires severe speed
        # and persistence before becoming CRITICAL.
        elif density_category == "CRITICAL":
            severe_speed = speed_category in (
                "SLOW",
                "STOPPED_OR_CRAWLING",
            )

            if severe_speed and self._persistent(
                "CRITICAL"
            ):
                state = "CRITICAL"
            else:
                state = "HIGH"

        else:
            state = "LOW"

        self.recent_states.append(state)

        return state

    def _persistent(
        self,
        target_state: str,
    ) -> bool:

        if not self.recent_states:
            return False

        required = min(
            self.persistence_window,
            len(self.recent_states) + 1,
        )

        recent_count = sum(
            1
            for state in self.recent_states
            if state == target_state
        )

        return recent_count >= required - 1

    def analyze_snapshot(
        self,
        vehicle_observations: Iterable[dict],
    ) -> dict:

        observations = list(
            vehicle_observations
        )

        unique_ids = {
            observation.get("track_id")
            for observation in observations
            if observation.get("track_id") is not None
            and observation.get("track_id") >= 0
        }

        active_vehicle_count = len(
            unique_ids
        )

        valid_speeds = [
            float(observation["speed_kmh"])
            for observation in observations
            if observation.get("speed_valid")
            and observation.get("speed_kmh") is not None
        ]

        average_speed = (
            sum(valid_speeds) / len(valid_speeds)
            if valid_speeds
            else None
        )

        peak_speed = (
            max(valid_speeds)
            if valid_speeds
            else None
        )

        density_category = (
            self.calculate_density_category(
                active_vehicle_count
            )
        )

        speed_category = (
            self.calculate_speed_category(
                average_speed
            )
        )

        traffic_score = (
            self.calculate_traffic_score(
                density_category,
                speed_category,
            )
        )

        traffic_state = (
            self.determine_traffic_state(
                density_category,
                speed_category,
            )
        )

        return {
            "active_vehicle_count": active_vehicle_count,
            "average_speed_kmh": (
                round(average_speed, 2)
                if average_speed is not None
                else None
            ),
            "peak_speed_kmh": (
                round(peak_speed, 2)
                if peak_speed is not None
                else None
            ),
            "valid_speed_samples": len(
                valid_speeds
            ),
            "density_category": density_category,
            "speed_category": speed_category,
            "traffic_score": traffic_score,
            "traffic_state": traffic_state,
        }

    def reset(self) -> None:
        self.recent_states.clear()


traffic_engine = TrafficEngine()
