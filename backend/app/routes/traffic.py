from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.traffic_alert_pipeline import (
    TrafficAlertPipeline,
)

router = APIRouter(
    prefix="/api/traffic",
    tags=["Traffic"],
)

_pipeline = TrafficAlertPipeline(
    persistence_required=3
)


@router.get("/status")
def traffic_status() -> dict[str, Any]:
    """
    Basic traffic intelligence API status.
    """
    return {
        "status": "ok",
        "service": "traffic-intelligence",
        "alert_integration": True,
        "persistence_required": 3,
    }


@router.post("/test")
def test_traffic_alert_pipeline() -> dict[str, Any]:
    """
    Controlled API test for Traffic -> Alert integration.

    This endpoint deliberately uses controlled observations.
    It does NOT represent real traffic conditions.
    """

    pipeline = TrafficAlertPipeline(
        persistence_required=3
    )

    low_snapshot = {
        "traffic_state": "LOW",
        "average_speed_kmh": 30.0,
        "active_vehicle_count": 2,
        "traffic_score": 0.0,
    }

    high_snapshot = {
        "traffic_state": "HIGH",
        "average_speed_kmh": 12.0,
        "active_vehicle_count": 8,
        "traffic_score": 70.0,
    }

    critical_snapshot = {
        "traffic_state": "CRITICAL",
        "average_speed_kmh": 5.0,
        "active_vehicle_count": 13,
        "traffic_score": 100.0,
    }

    results = []

    # LOW
    results.append(
        pipeline.process_snapshot(
            low_snapshot
        )
    )

    # HIGH persistence
    for _ in range(3):
        results.append(
            pipeline.process_snapshot(
                high_snapshot
            )
        )

    # Clear HIGH
    results.append(
        pipeline.process_snapshot(
            low_snapshot
        )
    )

    # CRITICAL persistence
    for _ in range(3):
        results.append(
            pipeline.process_snapshot(
                critical_snapshot
            )
        )

    alerts = [
        alert
        for result in results
        for alert in result["alerts"]
    ]

    return {
        "status": "ok",
        "message": (
            "Controlled traffic-alert "
            "integration test completed."
        ),
        "controlled_test": True,
        "results": results,
        "alerts_generated": len(alerts),
        "alerts": alerts,
    }


@router.post("/snapshot")
def process_traffic_snapshot(
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """
    Process a traffic snapshot through the
    Traffic -> Alert pipeline.

    This endpoint is intended for integration
    with future video-processing workers.
    """

    result = _pipeline.process_snapshot(
        snapshot
    )

    return {
        "status": "ok",
        "result": result,
    }
