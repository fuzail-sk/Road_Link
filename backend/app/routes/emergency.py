from fastapi import APIRouter, HTTPException
from typing import Any

from app.services.emergency_engine import EmergencyEngine

router = APIRouter(
    prefix="/api/emergency",
    tags=["Emergency"],
)

engine = EmergencyEngine()


@router.get("/status")
def emergency_status():
    return {
        "module": "Emergency Corridor Recommendation",
        "status": "ready",
        "decision_support_only": True,
        "live_navigation": False,
        "signal_control": False,
    }


@router.post("/recommend")
def recommend_corridor(
    payload: dict[str, Any],
):
    corridors = payload.get(
        "corridors",
        [],
    )

    if not corridors:
        raise HTTPException(
            status_code=400,
            detail="corridors are required",
        )

    try:
        result = engine.recommend_corridor(
            corridors
        )

        return {
            "success": True,
            "data": result,
        }

    except (ValueError, TypeError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@router.post("/test")
def emergency_test():
    """
    Controlled emergency scenario.

    Each corridor contains road segments because
    EmergencyEngine scores the individual segments
    before aggregating the corridor.
    """

    corridors = [
        {
            "corridor_id": "CORRIDOR-A",
            "name": "Main Road",
            "segments": [
                {
                    "segment_id": "A1",
                    "distance_km": 2.0,
                    "traffic_state": "HIGH",
                    "average_speed_kmh": 11.0,
                }
            ],
        },
        {
            "corridor_id": "CORRIDOR-B",
            "name": "Ring Road",
            "segments": [
                {
                    "segment_id": "B1",
                    "distance_km": 2.6,
                    "traffic_state": "LOW",
                    "average_speed_kmh": 33.5,
                }
            ],
        },
        {
            "corridor_id": "CORRIDOR-C",
            "name": "Market Road",
            "segments": [
                {
                    "segment_id": "C1",
                    "distance_km": 1.8,
                    "traffic_state": "CRITICAL",
                    "average_speed_kmh": 7.0,
                }
            ],
        },
    ]

    result = engine.recommend_corridor(
        corridors
    )

    return {
        "success": True,
        "controlled_test": True,
        "data": result,
    }
