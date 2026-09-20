from app.services.anpr_journey_engine import (
    ANPRJourneyEngine,
)


def main() -> None:

    engine = ANPRJourneyEngine(
        confidence_threshold=0.70,
        support_ratio_threshold=0.60,
    )

    journey_observations = [
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

    vehicle = (
        engine.build_vehicle_record(
            journey_observations,
            anpr_observations,
        )
    )

    journey = vehicle["journey"]

    print(
        "\n========== ANPR + JOURNEY TEST =========="
    )

    print(
        "Vehicle ID:",
        vehicle["vehicle_id"],
    )

    print(
        "Plate:",
        vehicle["plate"],
    )

    print(
        "Plate status:",
        vehicle["plate_status"],
    )

    print(
        "Plate confidence:",
        vehicle["plate_confidence"],
    )

    print(
        "Plate support:",
        f'{vehicle["plate_support_count"]}/'
        f'{vehicle["plate_total_observations"]}',
    )

    print(
        "Support ratio:",
        vehicle["plate_support_ratio"],
    )

    print(
        "Journey ID:",
        journey["journey_id"],
    )

    print(
        "Journey duration:",
        journey["duration_minutes"],
        "minutes",
    )

    print(
        "Journey distance:",
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
        "Cameras observed:",
        journey["camera_count"],
    )

    print(
        "Journey status:",
        journey["status"],
    )

    assert (
        vehicle["vehicle_id"]
        == "VEHICLE-017"
    )

    assert (
        vehicle["plate"]
        == "MH12AB1234"
    )

    assert (
        vehicle["plate_status"]
        == "CONFIRMED"
    )

    assert (
        vehicle["plate_confidence"]
        == 0.92
    )

    assert (
        vehicle["plate_support_count"]
        == 4
    )

    assert (
        vehicle["plate_total_observations"]
        == 4
    )

    assert (
        vehicle["plate_support_ratio"]
        == 1.0
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
        "\nVehicle identity preserved: PASS"
    )

    print(
        "Plate normalization: PASS"
    )

    print(
        "Plate consensus: PASS"
    )

    print(
        "Plate supported across cameras: PASS"
    )

    print(
        "Journey connected to vehicle: PASS"
    )

    print(
        "Four-camera journey: PASS"
    )

    print(
        "Distance preserved: PASS"
    )

    print(
        "Journey status: PASS"
    )

    print(
        "\nANPR + JOURNEY INTEGRATION "
        "VALIDATION PASSED"
    )


if __name__ == "__main__":
    main()
