from __future__ import annotations

from app.services.emergency_engine import (
    EmergencyEngine,
)


def main() -> None:

    engine = EmergencyEngine()

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

    recommendation = result[
        "recommendation"
    ]

    print(
        "\n========== EMERGENCY CORRIDOR TEST =========="
    )

    print(
        "Recommended corridor:",
        recommendation["corridor_id"],
    )

    print(
        "Name:",
        recommendation["name"],
    )

    print(
        "Distance:",
        recommendation[
            "total_distance_km"
        ],
        "km",
    )

    print(
        "Estimated travel time:",
        recommendation[
            "estimated_travel_time_minutes"
        ],
        "minutes",
    )

    print(
        "Total route cost:",
        recommendation[
            "total_cost"
        ],
    )

    print(
        "Decision support only:",
        result[
            "decision_support_only"
        ],
    )

    print(
        "Live navigation:",
        result[
            "live_navigation"
        ],
    )

    print(
        "Signal control:",
        result[
            "signal_control"
        ],
    )

    assert (
        recommendation["corridor_id"]
        == "CORRIDOR-B"
    )

    assert (
        result[
            "decision_support_only"
        ]
        is True
    )

    assert (
        result["live_navigation"]
        is False
    )

    assert (
        result["signal_control"]
        is False
    )

    print(
        "\nRECOMMENDED CORRIDOR TEST: PASS"
    )

    print(
        "EMERGENCY ENGINE VALIDATION PASSED"
    )


if __name__ == "__main__":
    main()
