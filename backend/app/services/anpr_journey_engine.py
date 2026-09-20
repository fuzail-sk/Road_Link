from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.journey_engine import JourneyEngine


class ANPRJourneyEngine:
    """
    Integrates ANPR observations with RoadLink
    vehicle journey reconstruction.

    ANPR is treated as an identity layer:
        vehicle_id -> plate observations -> plate consensus
        -> reconstructed journey
    """

    def __init__(
        self,
        confidence_threshold: float = 0.70,
        support_ratio_threshold: float = 0.60,
    ):
        self.confidence_threshold = (
            confidence_threshold
        )

        self.support_ratio_threshold = (
            support_ratio_threshold
        )

        self.journey_engine = JourneyEngine()

    @staticmethod
    def normalize_plate(
        plate: str | None,
    ) -> str | None:

        if not plate:
            return None

        normalized = "".join(
            character
            for character in plate.upper()
            if character.isalnum()
        )

        return normalized or None

    def determine_plate_consensus(
        self,
        observations: list[dict[str, Any]],
    ) -> dict[str, Any]:

        if not observations:
            return {
                "plate": None,
                "status": "NOT_AVAILABLE",
                "confidence": 0.0,
                "support_count": 0,
                "total_observations": 0,
                "support_ratio": 0.0,
            }

        valid_observations = []

        for observation in observations:

            plate = self.normalize_plate(
                observation.get("plate")
            )

            confidence = float(
                observation.get(
                    "confidence",
                    0.0,
                )
            )

            if (
                plate
                and confidence
                >= self.confidence_threshold
            ):
                valid_observations.append(
                    {
                        "plate": plate,
                        "confidence": confidence,
                    }
                )

        if not valid_observations:
            return {
                "plate": None,
                "status": "UNCONFIRMED",
                "confidence": 0.0,
                "support_count": 0,
                "total_observations": len(
                    observations
                ),
                "support_ratio": 0.0,
            }

        plate_counts = Counter(
            item["plate"]
            for item in valid_observations
        )

        consensus_plate, support_count = (
            plate_counts.most_common(1)[0]
        )

        total_observations = len(
            observations
        )

        support_ratio = (
            support_count
            / total_observations
        )

        matching_confidences = [
            item["confidence"]
            for item in valid_observations
            if item["plate"]
            == consensus_plate
        ]

        average_confidence = (
            sum(matching_confidences)
            / len(matching_confidences)
        )

        if (
            support_ratio
            >= self.support_ratio_threshold
        ):
            status = "CONFIRMED"
        else:
            status = "UNCONFIRMED"

        return {
            "plate": consensus_plate,
            "status": status,
            "confidence": round(
                average_confidence,
                2,
            ),
            "support_count": support_count,
            "total_observations": (
                total_observations
            ),
            "support_ratio": round(
                support_ratio,
                2,
            ),
        }

    def build_vehicle_record(
        self,
        journey_observations: list[
            dict[str, Any]
        ],
        anpr_observations: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:

        if not journey_observations:
            raise ValueError(
                "Journey observations "
                "are required."
            )

        vehicle_ids = {
            observation["vehicle_id"]
            for observation
            in journey_observations
        }

        if len(vehicle_ids) != 1:
            raise ValueError(
                "Journey observations must "
                "belong to one vehicle."
            )

        vehicle_id = next(
            iter(vehicle_ids)
        )

        plate_consensus = (
            self.determine_plate_consensus(
                anpr_observations
            )
        )

        journey = (
            self.journey_engine
            .reconstruct_journey(
                journey_observations
            )
        )

        return {
            "vehicle_id": vehicle_id,
            "plate": plate_consensus[
                "plate"
            ],
            "plate_status": plate_consensus[
                "status"
            ],
            "plate_confidence": (
                plate_consensus[
                    "confidence"
                ]
            ),
            "plate_support_count": (
                plate_consensus[
                    "support_count"
                ]
            ),
            "plate_total_observations": (
                plate_consensus[
                    "total_observations"
                ]
            ),
            "plate_support_ratio": (
                plate_consensus[
                    "support_ratio"
                ]
            ),
            "journey": journey,
        }


anpr_journey_engine = (
    ANPRJourneyEngine()
)
