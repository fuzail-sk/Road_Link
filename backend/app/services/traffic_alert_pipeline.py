from __future__ import annotations

from typing import Any

from app.services.alert_engine import AlertEngine
from app.services.traffic_engine import TrafficEngine


class TrafficAlertPipeline:
    """
    Connects RoadLink traffic intelligence with the alert engine.

    Flow:
        Traffic observations
            ↓
        TrafficEngine
            ↓
        Traffic snapshot
            ↓
        AlertEngine
            ↓
        New alerts
    """

    def __init__(
        self,
        persistence_required: int = 3,
    ):
        self.traffic_engine = TrafficEngine()
        self.alert_engine = AlertEngine(
            persistence_required=persistence_required
        )

    def process_observations(
        self,
        vehicle_observations: list[dict[str, Any]],
    ) -> dict[str, Any]:

        traffic_snapshot = (
            self.traffic_engine.analyze_snapshot(
                vehicle_observations
            )
        )

        alerts = self.alert_engine.evaluate(
            traffic_snapshot
        )

        return {
            "traffic": traffic_snapshot,
            "alerts": alerts,
        }

    def process_snapshot(
        self,
        traffic_snapshot: dict[str, Any],
    ) -> dict[str, Any]:

        alerts = self.alert_engine.evaluate(
            traffic_snapshot
        )

        return {
            "traffic": traffic_snapshot,
            "alerts": alerts,
        }

    def reset(self) -> None:
        self.alert_engine.reset()


def build_snapshot(
    traffic_state: str,
    average_speed_kmh: float | None,
    active_vehicle_count: int,
    traffic_score: float,
) -> dict[str, Any]:

    return {
        "traffic_state": traffic_state,
        "average_speed_kmh": average_speed_kmh,
        "active_vehicle_count": active_vehicle_count,
        "traffic_score": traffic_score,
    }


def main() -> None:

    pipeline = TrafficAlertPipeline(
        persistence_required=3
    )

    print("\n========== TRAFFIC + ALERT PIPELINE ==========")

    # -------------------------------------------------
    # LOW traffic
    # -------------------------------------------------

    low = build_snapshot(
        traffic_state="LOW",
        average_speed_kmh=30.0,
        active_vehicle_count=2,
        traffic_score=0.0,
    )

    result = pipeline.process_snapshot(low)

    print("\nLOW:")
    print(result)

    assert result["traffic"]["traffic_state"] == "LOW"
    assert result["alerts"] == []

    # -------------------------------------------------
    # HIGH traffic persistence
    # -------------------------------------------------

    high = build_snapshot(
        traffic_state="HIGH",
        average_speed_kmh=12.0,
        active_vehicle_count=8,
        traffic_score=70.0,
    )

    print("\nHIGH #1:")
    result = pipeline.process_snapshot(high)
    print(result)
    assert result["alerts"] == []

    print("\nHIGH #2:")
    result = pipeline.process_snapshot(high)
    print(result)
    assert result["alerts"] == []

    print("\nHIGH #3:")
    result = pipeline.process_snapshot(high)
    print(result)

    high_alerts = result["alerts"]

    assert len(high_alerts) == 1
    assert (
        high_alerts[0]["alert_type"]
        == "HIGH_TRAFFIC"
    )

    # -------------------------------------------------
    # HIGH duplicate prevention
    # -------------------------------------------------

    print("\nHIGH DUPLICATE:")
    result = pipeline.process_snapshot(high)
    print(result)

    assert result["alerts"] == []

    # -------------------------------------------------
    # Clear HIGH condition
    # -------------------------------------------------

    print("\nLOW - CLEAR HIGH:")
    result = pipeline.process_snapshot(low)
    print(result)

    assert result["alerts"] == []

    # -------------------------------------------------
    # CRITICAL traffic persistence
    # -------------------------------------------------

    critical = build_snapshot(
        traffic_state="CRITICAL",
        average_speed_kmh=5.0,
        active_vehicle_count=13,
        traffic_score=100.0,
    )

    print("\nCRITICAL #1:")
    result = pipeline.process_snapshot(critical)
    print(result)
    assert result["alerts"] == []

    print("\nCRITICAL #2:")
    result = pipeline.process_snapshot(critical)
    print(result)
    assert result["alerts"] == []

    print("\nCRITICAL #3:")
    result = pipeline.process_snapshot(critical)
    print(result)

    critical_alerts = result["alerts"]

    assert len(critical_alerts) == 1
    assert (
        critical_alerts[0]["alert_type"]
        == "CRITICAL_TRAFFIC"
    )

    # -------------------------------------------------
    # Final validation
    # -------------------------------------------------

    print("\n========== VALIDATION SUMMARY ==========")

    print(
        "HIGH alert generated: PASS"
    )

    print(
        "HIGH duplicate prevention: PASS"
    )

    print(
        "HIGH condition clearing: PASS"
    )

    print(
        "CRITICAL alert generated: PASS"
    )

    print(
        "Traffic -> Alert integration: PASS"
    )

    print(
        "\nTRAFFIC + ALERT PIPELINE VALIDATION PASSED"
    )


if __name__ == "__main__":
    main()
