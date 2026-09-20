from fastapi import APIRouter, HTTPException
from typing import Any

from app.services.anpr_journey_engine import (
    ANPRJourneyEngine,
)

router = APIRouter(
    prefix="/api/journeys",
    tags=["Journeys"],
)

engine = ANPRJourneyEngine()


@router.get("/status")
def journey_status():
    return {
        "module": "Vehicle Journey + ANPR",
        "status": "ready",
        "confidence_threshold": (
            engine.confidence_threshold
        ),
        "support_ratio_threshold": (
            engine.support_ratio_threshold
        ),
    }


@router.post("/reconstruct")
def reconstruct_journey(
    payload: dict[str, Any],
):
    journey_observations = payload.get(
        "journey_observations",
        []
    )

    anpr_observations = payload.get(
        "anpr_observations",
        []
    )

    if not journey_observations:
        raise HTTPException(
            status_code=400,
            detail=(
                "journey_observations "
                "are required"
            ),
        )

    try:
        result = (
            engine.build_vehicle_record(
                journey_observations,
                anpr_observations,
            )
        )

        return {
            "success": True,
            "data": result,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@router.post("/test")
def journey_test():

    journey_observations = [
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-A",
            "camera_name": "North Junction",
            "timestamp": (
                "2026-09-19T10:00:00+05:30"
            ),
        },
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-B",
            "camera_name": "Central Junction",
            "timestamp": (
                "2026-09-19T10:03:00+05:30"
            ),
            "distance_from_previous_km": 1.4,
        },
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-C",
            "camera_name": "East Junction",
            "timestamp": (
                "2026-09-19T10:05:30+05:30"
            ),
            "distance_from_previous_km": 1.2,
        },
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-D",
            "camera_name": "Hospital Junction",
            "timestamp": (
                "2026-09-19T10:08:00+05:30"
            ),
            "distance_from_previous_km": 1.1,
        },
    ]

    anpr_observations = [
        {
            "camera_id": "CAM-A",
            "plate": "MH12AB1234",
            "confidence": 0.94,
        },
        {
            "camera_id": "CAM-B",
            "plate": "MH12AB1234",
            "confidence": 0.91,
        },
        {
            "camera_id": "CAM-C",
            "plate": "MH12 AB1234",
            "confidence": 0.88,
        },
        {
            "camera_id": "CAM-D",
            "plate": "MH12AB1234",
            "confidence": 0.96,
        },
    ]

    result = (
        engine.build_vehicle_record(
            journey_observations,
            anpr_observations,
        )
    )

    return {
        "success": True,
        "controlled_test": True,
        "data": result,
    }
