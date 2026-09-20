from __future__ import annotations

from typing import Any


class EmergencyEngine:
    """
    RoadLink Emergency Corridor Recommendation Engine.

    This engine evaluates candidate road segments/corridors
    using distance, traffic state and estimated speed.

    It produces a recommendation for an emergency route.

    Important:
        This is a decision-support/recommendation system.
        It does not control traffic signals and does not provide
        live navigation unless connected to an appropriate
        real-time road-network source.
    """

    TRAFFIC_PENALTIES = {
        "LOW": 0.0,
        "MODERATE": 1.25,
        "HIGH": 2.5,
        "CRITICAL": 4.0,
    }

    SEVERE_STATES = {
        "HIGH",
        "CRITICAL",
    }

    DEFAULT_EMERGENCY_SPEED_KMH = 40.0

    def __init__(
        self,
        emergency_speed_kmh: float = DEFAULT_EMERGENCY_SPEED_KMH,
    ):
        self.emergency_speed_kmh = (
            emergency_speed_kmh
        )

    @staticmethod
    def normalize_segment(
        segment: dict[str, Any],
    ) -> dict[str, Any]:

        traffic_state = str(
            segment.get(
                "traffic_state",
                "LOW",
            )
        ).upper()

        if traffic_state not in {
            "LOW",
            "MODERATE",
            "HIGH",
            "CRITICAL",
        }:
            traffic_state = "LOW"

        distance_km = float(
            segment.get(
                "distance_km",
                0.0,
            )
        )

        average_speed_kmh = segment.get(
            "average_speed_kmh"
        )

        if (
            average_speed_kmh is None
            or float(average_speed_kmh) <= 0
        ):
            average_speed_kmh = (
                self_default_speed(
                    traffic_state
                )
            )

        return {
            **segment,
            "traffic_state": traffic_state,
            "distance_km": distance_km,
            "average_speed_kmh": float(
                average_speed_kmh
            ),
        }

    def estimate_travel_time(
        self,
        segment: dict[str, Any],
    ) -> float:

        normalized = self.normalize_segment(
            segment
        )

        distance_km = normalized[
            "distance_km"
        ]

        speed_kmh = normalized[
            "average_speed_kmh"
        ]

        if speed_kmh <= 0:
            return float("inf")

        return (
            distance_km / speed_kmh
        ) * 60.0

    def score_segment(
        self,
        segment: dict[str, Any],
    ) -> dict[str, Any]:

        normalized = self.normalize_segment(
            segment
        )

        traffic_state = normalized[
            "traffic_state"
        ]

        travel_time = (
            self.estimate_travel_time(
                normalized
            )
        )

        congestion_penalty = (
            self.TRAFFIC_PENALTIES[
                traffic_state
            ]
            * normalized["distance_km"]
        )

        severe_penalty = 0.0

        if traffic_state in self.SEVERE_STATES:
            severe_penalty = (
                5.0
                * normalized["distance_km"]
            )

        total_cost = (
            travel_time
            + congestion_penalty
            + severe_penalty
        )

        return {
            **normalized,
            "estimated_travel_time_minutes": round(
                travel_time,
                2,
            ),
            "congestion_penalty": round(
                congestion_penalty,
                2,
            ),
            "severe_congestion_penalty": round(
                severe_penalty,
                2,
            ),
            "total_cost": round(
                total_cost,
                2,
            ),
        }

    def score_corridor(
        self,
        corridor: dict[str, Any],
    ) -> dict[str, Any]:

        segments = corridor.get(
            "segments",
            []
        )

        scored_segments = [
            self.score_segment(segment)
            for segment in segments
        ]

        total_distance = sum(
            segment["distance_km"]
            for segment in scored_segments
        )

        total_time = sum(
            segment[
                "estimated_travel_time_minutes"
            ]
            for segment in scored_segments
        )

        total_cost = sum(
            segment["total_cost"]
            for segment in scored_segments
        )

        return {
            "corridor_id": corridor.get(
                "corridor_id"
            ),
            "name": corridor.get(
                "name"
            ),
            "segments": scored_segments,
            "total_distance_km": round(
                total_distance,
                2,
            ),
            "estimated_travel_time_minutes": round(
                total_time,
                2,
            ),
            "total_cost": round(
                total_cost,
                2,
            ),
        }

    def recommend_corridor(
        self,
        corridors: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:

        if not corridors:
            raise ValueError(
                "At least one corridor is required."
            )

        scored_corridors = [
            self.score_corridor(
                corridor
            )
            for corridor in corridors
        ]

        ranked = sorted(
            scored_corridors,
            key=lambda corridor: (
                corridor["total_cost"]
            ),
        )

        recommended = ranked[0]

        alternatives = ranked[1:]

        severe_segments = [
            segment
            for segment in recommended[
                "segments"
            ]
            if segment["traffic_state"]
            in self.SEVERE_STATES
        ]

        if severe_segments:
            reason = (
                "Recommended corridor has the "
                "lowest calculated emergency route "
                "cost among the supplied alternatives."
            )
        else:
            reason = (
                "Recommended corridor has the "
                "lowest calculated emergency travel "
                "cost among the supplied alternatives."
            )

        return {
            "recommendation": recommended,
            "alternatives": alternatives,
            "reason": reason,
            "decision_support_only": True,
            "live_navigation": False,
            "signal_control": False,
        }


def self_default_speed(
    traffic_state: str,
) -> float:

    return {
        "LOW": 40.0,
        "MODERATE": 25.0,
        "HIGH": 15.0,
        "CRITICAL": 7.0,
    }.get(
        traffic_state,
        20.0,
    )


emergency_engine = EmergencyEngine()
