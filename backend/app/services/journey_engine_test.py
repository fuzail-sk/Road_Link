from app.services.journey_engine import (
    JourneyEngine,
)


def main() -> None:

    engine = JourneyEngine()

    observations = [
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-A",
            "camera_name": "North Junction",
            "timestamp": "2026-09-19T10:00:00+05:30",
        },
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-B",
            "camera_name": "Central Junction",
            "timestamp": "2026-09-19T10:03:00+05:30",
            "distance_from_previous_km": 1.4,
        },
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-C",
            "camera_name": "East Junction",
            "timestamp": "2026-09-19T10:05:30+05:30",
            "distance_from_previous_km": 1.2,
        },
        {
            "vehicle_id": "VEHICLE-017",
            "camera_id": "CAM-D",
            "camera_name": "Hospital Junction",
            "timestamp": "2026-09-19T10:08:00+05:30",
            "distance_from_previous_km": 1.1,
        },
    ]

    journey = (
        engine.reconstruct_journey(
            observations
        )
    )

    print(
        "\n========== VEHICLE JOURNEY TEST =========="
    )

    print(
        "Journey ID:",
        journey["journey_id"],
    )

    print(
        "Vehicle ID:",
        journey["vehicle_id"],
    )

    print(
        "First seen:",
        journey["first_seen"],
    )

    print(
        "Last seen:",
        journey["last_seen"],
    )

    print(
        "Duration:",
        journey["duration_minutes"],
        "minutes",
    )

    print(
        "Distance:",
        journey["distance_km"],
        "km",
    )

    print(
        "Average estimated speed:",
        journey[
            "average_estimated_speed_kmh"
        ],
        "km/h",
    )

    print(
        "Cameras:",
        journey["camera_count"],
    )

    print(
        "Status:",
        journey["status"],
    )

    assert (
        journey["vehicle_id"]
        == "VEHICLE-017"
    )

    assert (
        journey["distance_km"]
        == 3.7
    )

    assert (
        journey["duration_minutes"]
        == 8.0
    )

    assert (
        journey["camera_count"]
        == 4
    )

    assert (
        journey["status"]
        == "NORMAL"
    )

    print(
        "\nVehicle identity: PASS"
    )

    print(
        "Distance reconstruction: PASS"
    )

    print(
        "Duration reconstruction: PASS"
    )

    print(
        "Multi-camera journey: PASS"
    )

    print(
        "Journey status: PASS"
    )

    print(
        "\nJOURNEY ENGINE VALIDATION PASSED"
    )


if __name__ == "__main__":
    main()
