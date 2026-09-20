from __future__ import annotations

from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from typing import Any


class JourneyEngine:
    """
    RoadLink vehicle journey reconstruction engine.

    Reconstructs a vehicle journey from observations
    collected across a monitored camera network.

    Each observation should contain:
        vehicle_id
        camera_id
        camera_name
        timestamp
        latitude / longitude (optional)
        distance_from_previous_km (optional)
    """

    def __init__(
        self,
        max_reasonable_speed_kmh: float = 120.0,
    ):
        self.max_reasonable_speed_kmh = (
            max_reasonable_speed_kmh
        )

    @staticmethod
    def parse_time(
        timestamp: str,
    ) -> datetime:

        return datetime.fromisoformat(
            timestamp
        )

    @staticmethod
    def calculate_distance_km(
        first: dict[str, Any],
        second: dict[str, Any],
    ) -> float:

        # Prefer an explicitly supplied road-network
        # distance because it represents the monitored
        # road segment rather than straight-line distance.
        if (
            second.get(
                "distance_from_previous_km"
            )
            is not None
        ):
            return float(
                second[
                    "distance_from_previous_km"
                ]
            )

        # Fall back to geographic coordinates when
        # available.
        lat1 = first.get("latitude")
        lon1 = first.get("longitude")
        lat2 = second.get("latitude")
        lon2 = second.get("longitude")

        if None in (
            lat1,
            lon1,
            lat2,
            lon2,
        ):
            return 0.0

        earth_radius_km = 6371.0

        lat1 = radians(float(lat1))
        lon1 = radians(float(lon1))
        lat2 = radians(float(lat2))
        lon2 = radians(float(lon2))

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            sin(dlat / 2) ** 2
            + cos(lat1)
            * cos(lat2)
            * sin(dlon / 2) ** 2
        )

        c = 2 * atan2(
            sqrt(a),
            sqrt(1 - a),
        )

        return (
            earth_radius_km * c
        )

    @staticmethod
    def calculate_speed(
        distance_km: float,
        start_time: datetime,
        end_time: datetime,
    ) -> float | None:

        duration_seconds = (
            end_time - start_time
        ).total_seconds()

        if duration_seconds <= 0:
            return None

        return (
            distance_km
            / (duration_seconds / 3600.0)
        )

    def reconstruct_journey(
        self,
        observations: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:

        if not observations:
            raise ValueError(
                "At least one vehicle observation "
                "is required."
            )

        ordered = sorted(
            observations,
            key=lambda observation:
                self.parse_time(
                    observation["timestamp"]
                ),
        )

        vehicle_ids = {
            observation["vehicle_id"]
            for observation in ordered
        }

        if len(vehicle_ids) != 1:
            raise ValueError(
                "All observations must belong to "
                "the same vehicle."
            )

        vehicle_id = ordered[0][
            "vehicle_id"
        ]

        first_time = self.parse_time(
            ordered[0]["timestamp"]
        )

        last_time = self.parse_time(
            ordered[-1]["timestamp"]
        )

        total_distance = 0.0
        segment_records = []

        for index in range(
            1,
            len(ordered),
        ):

            previous = ordered[
                index - 1
            ]

            current = ordered[
                index
            ]

            distance = (
                self.calculate_distance_km(
                    previous,
                    current,
                )
            )

            segment_start = (
                self.parse_time(
                    previous[
                        "timestamp"
                    ]
                )
            )

            segment_end = (
                self.parse_time(
                    current[
                        "timestamp"
                    ]
                )
            )

            segment_speed = (
                self.calculate_speed(
                    distance,
                    segment_start,
                    segment_end,
                )
            )

            if (
                segment_speed is not None
                and segment_speed
                > self.max_reasonable_speed_kmh
            ):
                segment_speed = None

            total_distance += distance

            segment_records.append(
                {
                    "from_camera": previous[
                        "camera_id"
                    ],
                    "to_camera": current[
                        "camera_id"
                    ],
                    "distance_km": round(
                        distance,
                        2,
                    ),
                    "start_time": (
                        previous[
                            "timestamp"
                        ]
                    ),
                    "end_time": (
                        current[
                            "timestamp"
                        ]
                    ),
                    "estimated_speed_kmh": (
                        round(
                            segment_speed,
                            2,
                        )
                        if segment_speed
                        is not None
                        else None
                    ),
                }
            )

        duration_minutes = (
            last_time - first_time
        ).total_seconds() / 60.0

        average_speed = None

        if duration_minutes > 0:
            average_speed = (
                total_distance
                / (duration_minutes / 60.0)
            )

            if (
                average_speed
                > self.max_reasonable_speed_kmh
            ):
                average_speed = None

        cameras_observed = []

        for observation in ordered:
            camera_id = observation[
                "camera_id"
            ]

            if (
                camera_id
                not in cameras_observed
            ):
                cameras_observed.append(
                    camera_id
                )

        if average_speed is None:
            journey_status = (
                "REVIEW_REQUIRED"
            )
        else:
            journey_status = "NORMAL"

        journey_id = (
            f"JOURNEY-"
            f"{vehicle_id}-"
            f"{first_time.strftime('%Y%m%d%H%M%S')}"
        )

        return {
            "journey_id": journey_id,
            "vehicle_id": vehicle_id,
            "first_seen": (
                ordered[0]["timestamp"]
            ),
            "last_seen": (
                ordered[-1]["timestamp"]
            ),
            "duration_minutes": round(
                duration_minutes,
                2,
            ),
            "distance_km": round(
                total_distance,
                2,
            ),
            "average_estimated_speed_kmh": (
                round(
                    average_speed,
                    2,
                )
                if average_speed
                is not None
                else None
            ),
            "cameras_observed": (
                cameras_observed
            ),
            "camera_count": len(
                cameras_observed
            ),
            "segments": segment_records,
            "status": journey_status,
        }


journey_engine = JourneyEngine()
