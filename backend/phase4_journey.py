import json
import math
import os
import uuid
from datetime import datetime, timezone


# ============================================================
# ROADLINK — PHASE 4
# Vehicle Journey Reconstruction
# ============================================================
#
# This module reconstructs a vehicle journey from observations
# across multiple cameras.
#
# IMPORTANT:
# The current test data is controlled data.
# It demonstrates the journey engine and does not claim to be
# live city-wide camera telemetry.
# ============================================================


# ------------------------------------------------------------
# Camera network
# ------------------------------------------------------------

CAMERAS = {

    "CAM-A": {
        "name": "North Junction",
        "latitude": 18.6000,
        "longitude": 73.8000,
    },

    "CAM-B": {
        "name": "Central Junction",
        "latitude": 18.6050,
        "longitude": 73.8100,
    },

    "CAM-C": {
        "name": "East Junction",
        "latitude": 18.6100,
        "longitude": 73.8200,
    },

    "CAM-D": {
        "name": "Hospital Junction",
        "latitude": 18.6150,
        "longitude": 73.8300,
    },
}


# ------------------------------------------------------------
# Known road connections
# ------------------------------------------------------------

ROAD_SEGMENTS = {

    ("CAM-A", "CAM-B"): {
        "distance_km": 1.4,
    },

    ("CAM-B", "CAM-C"): {
        "distance_km": 1.2,
    },

    ("CAM-C", "CAM-D"): {
        "distance_km": 1.1,
    },

    ("CAM-A", "CAM-C"): {
        "distance_km": 2.3,
    },

    ("CAM-B", "CAM-D"): {
        "distance_km": 2.2,
    },
}


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

MAX_REASONABLE_SPEED_KMH = 120.0

MIN_TRAVEL_TIME_SECONDS = 1.0


# ============================================================
# Utility functions
# ============================================================

def parse_time(value):
    """
    Convert ISO timestamp to timezone-aware datetime.
    """

    if isinstance(value, datetime):
        return value

    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00"
        )
    )


def calculate_distance_km(
    camera_a,
    camera_b
):
    """
    Retrieve the known road distance between two cameras.
    """

    direct = ROAD_SEGMENTS.get(
        (
            camera_a,
            camera_b
        )
    )

    if direct:
        return direct["distance_km"]

    reverse = ROAD_SEGMENTS.get(
        (
            camera_b,
            camera_a
        )
    )

    if reverse:
        return reverse["distance_km"]

    return None


def calculate_speed(
    distance_km,
    start_time,
    end_time
):
    """
    Calculate journey segment speed.
    """

    start = parse_time(
        start_time
    )

    end = parse_time(
        end_time
    )

    seconds = (
        end - start
    ).total_seconds()

    if seconds <= 0:
        return None

    if seconds < MIN_TRAVEL_TIME_SECONDS:
        return None

    speed_kmh = (
        distance_km /
        (seconds / 3600)
    )

    return speed_kmh


# ============================================================
# Journey reconstruction
# ============================================================

def reconstruct_journey(
    observations
):
    """
    Build a chronological journey from camera observations
    belonging to one tracked vehicle.
    """

    if not observations:
        raise ValueError(
            "No vehicle observations supplied."
        )

    # --------------------------------------------------------
    # Sort observations chronologically.
    # --------------------------------------------------------

    observations = sorted(
        observations,
        key=lambda item:
            parse_time(
                item["timestamp"]
            )
    )

    vehicle_id = observations[0][
        "vehicle_id"
    ]

    plate = observations[0].get(
        "plate"
    )

    segments = []

    anomalies = []

    total_distance = 0.0

    total_seconds = 0.0

    # --------------------------------------------------------
    # Process consecutive camera observations.
    # --------------------------------------------------------

    for index in range(
        len(observations) - 1
    ):

        current = observations[
            index
        ]

        next_observation = observations[
            index + 1
        ]

        current_camera = current[
            "camera_id"
        ]

        next_camera = next_observation[
            "camera_id"
        ]

        distance_km = calculate_distance_km(
            current_camera,
            next_camera
        )

        start_time = current[
            "timestamp"
        ]

        end_time = next_observation[
            "timestamp"
        ]

        start = parse_time(
            start_time
        )

        end = parse_time(
            end_time
        )

        duration_seconds = (
            end - start
        ).total_seconds()

        # ----------------------------------------------------
        # Unknown road connection.
        # ----------------------------------------------------

        if distance_km is None:

            anomalies.append({

                "type":
                    "UNKNOWN_ROUTE",

                "from_camera":
                    current_camera,

                "to_camera":
                    next_camera,

                "message":
                    "No known road connection "
                    "exists between these camera "
                    "observations.",
            })

            continue

        # ----------------------------------------------------
        # Invalid time.
        # ----------------------------------------------------

        if duration_seconds <= 0:

            anomalies.append({

                "type":
                    "INVALID_TIME",

                "from_camera":
                    current_camera,

                "to_camera":
                    next_camera,

                "message":
                    "Next camera observation "
                    "does not occur after the "
                    "previous observation.",
            })

            continue

        speed_kmh = calculate_speed(
            distance_km,
            start_time,
            end_time
        )

        # ----------------------------------------------------
        # Speed anomaly.
        # ----------------------------------------------------

        if (
            speed_kmh is not None
            and speed_kmh
            > MAX_REASONABLE_SPEED_KMH
        ):

            anomalies.append({

                "type":
                    "SPEED_ANOMALY",

                "from_camera":
                    current_camera,

                "to_camera":
                    next_camera,

                "estimated_speed_kmh":
                    round(
                        speed_kmh,
                        2
                    ),

                "message":
                    "Estimated segment speed "
                    "exceeds the configured "
                    "data-quality threshold.",
            })

        # ----------------------------------------------------
        # Create journey segment.
        # ----------------------------------------------------

        segment = {

            "from_camera":
                current_camera,

            "from_camera_name":
                CAMERAS.get(
                    current_camera,
                    {}
                ).get(
                    "name",
                    current_camera
                ),

            "to_camera":
                next_camera,

            "to_camera_name":
                CAMERAS.get(
                    next_camera,
                    {}
                ).get(
                    "name",
                    next_camera
                ),

            "distance_km":
                round(
                    distance_km,
                    2
                ),

            "start_time":
                start_time,

            "end_time":
                end_time,

            "duration_seconds":
                round(
                    duration_seconds,
                    2
                ),

            "estimated_speed_kmh":
                (
                    round(
                        speed_kmh,
                        2
                    )
                    if speed_kmh
                    is not None
                    else None
                ),
        }

        segments.append(
            segment
        )

        total_distance += (
            distance_km
        )

        total_seconds += (
            duration_seconds
        )

    # --------------------------------------------------------
    # Overall journey statistics.
    # --------------------------------------------------------

    first_seen = observations[0][
        "timestamp"
    ]

    last_seen = observations[-1][
        "timestamp"
    ]

    journey_duration_seconds = (
        parse_time(last_seen)
        -
        parse_time(first_seen)
    ).total_seconds()

    average_speed = None

    if (
        total_seconds > 0
        and total_distance > 0
    ):

        average_speed = (
            total_distance /
            (total_seconds / 3600)
        )

    # --------------------------------------------------------
    # Journey timeline.
    # --------------------------------------------------------

    timeline = []

    for observation in observations:

        camera_id = observation[
            "camera_id"
        ]

        timeline.append({

            "camera_id":
                camera_id,

            "camera_name":
                CAMERAS.get(
                    camera_id,
                    {}
                ).get(
                    "name",
                    camera_id
                ),

            "timestamp":
                observation[
                    "timestamp"
                ],

            "plate":
                observation.get(
                    "plate"
                ),

            "confidence":
                observation.get(
                    "confidence"
                ),
        })

    return {

        "journey_id":
            uuid.uuid4().hex[:10],

        "vehicle_id":
            vehicle_id,

        "plate":
            plate,

        "first_seen":
            first_seen,

        "last_seen":
            last_seen,

        "journey_duration_seconds":
            round(
                journey_duration_seconds,
                2
            ),

        "journey_duration_minutes":
            round(
                journey_duration_seconds
                / 60,
                2
            ),

        "total_distance_km":
            round(
                total_distance,
                2
            ),

        "average_estimated_speed_kmh":
            (
                round(
                    average_speed,
                    2
                )
                if average_speed
                is not None
                else None
            ),

        "camera_count":
            len(
                timeline
            ),

        "timeline":
            timeline,

        "segments":
            segments,

        "anomalies":
            anomalies,

        "journey_status":
            (
                "ANOMALY_DETECTED"
                if anomalies
                else "NORMAL"
            ),
    }


# ============================================================
# CONTROLLED TEST DATA
# ============================================================

def build_controlled_observations():

    base = (
        "2026-09-19T10:"
    )

    observations = [

        {
            "vehicle_id":
                "VEHICLE-017",

            "plate":
                "MH12AB1234",

            "camera_id":
                "CAM-A",

            "timestamp":
                "2026-09-19T10:00:00+05:30",

            "confidence":
                0.94,
        },

        {
            "vehicle_id":
                "VEHICLE-017",

            "plate":
                "MH12AB1234",

            "camera_id":
                "CAM-B",

            "timestamp":
                "2026-09-19T10:03:00+05:30",

            "confidence":
                0.96,
        },

        {
            "vehicle_id":
                "VEHICLE-017",

            "plate":
                "MH12AB1234",

            "camera_id":
                "CAM-C",

            "timestamp":
                "2026-09-19T10:05:30+05:30",

            "confidence":
                0.95,
        },

        {
            "vehicle_id":
                "VEHICLE-017",

            "plate":
                "MH12AB1234",

            "camera_id":
                "CAM-D",

            "timestamp":
                "2026-09-19T10:08:00+05:30",

            "confidence":
                0.93,
        },
    ]

    return observations


# ============================================================
# TEST
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "ROADLINK — PHASE 4 "
        "VEHICLE JOURNEY RECONSTRUCTION"
    )
    print("=" * 70)
    print()

    observations = (
        build_controlled_observations()
    )

    print(
        "Controlled observations:"
    )

    for observation in observations:

        print(
            f"  {observation['camera_id']} "
            f"→ "
            f"{observation['timestamp']} "
            f"→ "
            f"{observation['plate']}"
        )

    print()

    print(
        "Reconstructing vehicle journey..."
    )

    journey = reconstruct_journey(
        observations
    )

    print()

    print("=" * 70)
    print("JOURNEY RESULT")
    print("=" * 70)
    print()

    print(
        f"Journey ID: "
        f"{journey['journey_id']}"
    )

    print(
        f"Vehicle ID: "
        f"{journey['vehicle_id']}"
    )

    print(
        f"Plate: "
        f"{journey['plate']}"
    )

    print(
        f"First seen: "
        f"{journey['first_seen']}"
    )

    print(
        f"Last seen: "
        f"{journey['last_seen']}"
    )

    print(
        f"Duration: "
        f"{journey['journey_duration_minutes']} min"
    )

    print(
        f"Distance: "
        f"{journey['total_distance_km']} km"
    )

    print(
        f"Average estimated speed: "
        f"{journey['average_estimated_speed_kmh']} km/h"
    )

    print(
        f"Cameras: "
        f"{journey['camera_count']}"
    )

    print(
        f"Status: "
        f"{journey['journey_status']}"
    )

    print()

    print(
        "Journey timeline:"
    )

    for point in journey[
        "timeline"
    ]:

        print(
            f"  {point['timestamp']} "
            f"| "
            f"{point['camera_name']} "
            f"({point['camera_id']})"
        )

    print()

    print(
        "Journey segments:"
    )

    for segment in journey[
        "segments"
    ]:

        print(
            f"  "
            f"{segment['from_camera']} "
            f"→ "
            f"{segment['to_camera']} "
            f"| "
            f"{segment['distance_km']} km "
            f"| "
            f"{segment['duration_seconds']} sec "
            f"| "
            f"{segment['estimated_speed_kmh']} km/h"
        )

    print()

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    checks = {

        "vehicle_identified":
            journey["vehicle_id"]
            == "VEHICLE-017",

        "plate_preserved":
            journey["plate"]
            == "MH12AB1234",

        "four_cameras":
            journey["camera_count"]
            == 4,

        "three_segments":
            len(
                journey["segments"]
            )
            == 3,

        "distance_reconstructed":
            abs(
                journey[
                    "total_distance_km"
                ]
                -
                3.7
            )
            < 0.01,

        "normal_journey":
            journey[
                "journey_status"
            ]
            == "NORMAL",
    }

    print("=" * 70)
    print("VALIDATION")
    print("=" * 70)
    print()

    all_passed = True

    for name, passed in checks.items():

        print(
            f"{name}: "
            + (
                "PASS"
                if passed
                else "FAIL"
            )
        )

        if not passed:
            all_passed = False

    # --------------------------------------------------------
    # Save report
    # --------------------------------------------------------

    output_dir = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        "storage",
        "outputs"
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    output_path = os.path.join(
        output_dir,
        "roadlink-vehicle-journey-test.json"
    )

    report = {

        "test_type":
            "CONTROLLED_VEHICLE_JOURNEY_TEST",

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_observations":
            observations,

        "validation":
            checks,

        "journey":
            journey,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=2
        )

    print()
    print(
        f"Test report: "
        f"{output_path}"
    )

    print()

    if all_passed:

        print(
            "OVERALL RESULT: PASS"
        )

    else:

        print(
            "OVERALL RESULT: FAIL"
        )

    print()


if __name__ == "__main__":
    main()
