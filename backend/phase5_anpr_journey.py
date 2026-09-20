import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone

from phase4_journey import reconstruct_journey


# ============================================================
# ROADLINK — PHASE 5
# ANPR + VEHICLE JOURNEY INTEGRATION
# ============================================================
#
# Purpose:
#   Connect ANPR observations to a reconstructed vehicle
#   journey.
#
# This controlled test demonstrates:
#
#   Vehicle tracking
#          +
#   Plate recognition
#          +
#   Camera observations
#          ↓
#   Unified vehicle journey
#
# IMPORTANT:
# This is controlled test data.
# It does not claim live multi-camera telemetry.
# ============================================================


# ------------------------------------------------------------
# ANPR configuration
# ------------------------------------------------------------

PLATE_CONFIDENCE_THRESHOLD = 0.70

PLATE_AGREEMENT_RATIO = 0.60


# ============================================================
# Plate normalization
# ============================================================

def normalize_plate(value):
    """
    Normalize an OCR plate result.

    Removes spaces, punctuation and converts to uppercase.
    """

    if not value:
        return ""

    return "".join(
        character
        for character in value.upper()
        if character.isalnum()
    )


# ============================================================
# Plate consensus
# ============================================================

def determine_plate_consensus(
    observations
):
    """
    Determine the most strongly supported plate across
    multiple ANPR observations.
    """

    valid = []

    for observation in observations:

        plate = normalize_plate(
            observation.get(
                "plate"
            )
        )

        confidence = float(
            observation.get(
                "plate_confidence",
                0
            )
        )

        if (
            plate
            and confidence
            >= PLATE_CONFIDENCE_THRESHOLD
        ):

            valid.append(
                {
                    "plate": plate,
                    "confidence": confidence,
                }
            )

    if not valid:

        return {
            "plate": None,
            "confidence": 0,
            "supporting_observations": 0,
            "total_observations": len(
                observations
            ),
            "status": "NO_CONFIDENT_PLATE",
        }

    # --------------------------------------------------------
    # Weighted voting.
    # --------------------------------------------------------

    votes = {}

    for item in valid:

        plate = item["plate"]

        confidence = item[
            "confidence"
        ]

        votes[plate] = (
            votes.get(
                plate,
                0
            )
            + confidence
        )

    winning_plate = max(
        votes,
        key=votes.get
    )

    supporting = sum(
        1
        for item in valid
        if item["plate"]
        == winning_plate
    )

    weighted_confidence = (
        votes[winning_plate]
        /
        sum(
            item["confidence"]
            for item in valid
        )
    )

    support_ratio = (
        supporting
        /
        len(observations)
    )

    if (
        support_ratio
        >= PLATE_AGREEMENT_RATIO
    ):

        status = "CONFIRMED"

    else:

        status = "LOW_SUPPORT"

    return {

        "plate":
            winning_plate,

        "confidence":
            round(
                weighted_confidence,
                3
            ),

        "supporting_observations":
            supporting,

        "total_observations":
            len(observations),

        "support_ratio":
            round(
                support_ratio,
                3
            ),

        "status":
            status,
    }


# ============================================================
# Unified vehicle record
# ============================================================

def build_vehicle_record(
    observations
):
    """
    Combine journey reconstruction and ANPR consensus
    into one RoadLink vehicle record.
    """

    if not observations:

        raise ValueError(
            "No observations supplied."
        )

    vehicle_ids = set(
        observation[
            "vehicle_id"
        ]
        for observation
        in observations
    )

    # --------------------------------------------------------
    # The controlled integration expects all observations
    # to belong to one persistent tracked vehicle.
    # --------------------------------------------------------

    if len(vehicle_ids) != 1:

        raise ValueError(
            "Observations contain multiple "
            "vehicle IDs."
        )

    vehicle_id = next(
        iter(vehicle_ids)
    )

    journey = reconstruct_journey(
        observations
    )

    plate_consensus = (
        determine_plate_consensus(
            observations
        )
    )

    return {

        "vehicle_record_id":
            uuid.uuid4().hex[:10],

        "vehicle_id":
            vehicle_id,

        "plate":
            plate_consensus[
                "plate"
            ],

        "plate_status":
            plate_consensus[
                "status"
            ],

        "plate_confidence":
            plate_consensus[
                "confidence"
            ],

        "plate_support":
            plate_consensus[
                "supporting_observations"
            ],

        "journey_id":
            journey[
                "journey_id"
            ],

        "journey_status":
            journey[
                "journey_status"
            ],

        "first_seen":
            journey[
                "first_seen"
            ],

        "last_seen":
            journey[
                "last_seen"
            ],

        "journey_duration_minutes":
            journey[
                "journey_duration_minutes"
            ],

        "total_distance_km":
            journey[
                "total_distance_km"
            ],

        "average_estimated_speed_kmh":
            journey[
                "average_estimated_speed_kmh"
            ],

        "camera_count":
            journey[
                "camera_count"
            ],

        "camera_timeline":
            journey[
                "timeline"
            ],

        "journey_segments":
            journey[
                "segments"
            ],

        "journey_anomalies":
            journey[
                "anomalies"
            ],

        "anpr_observations":
            [
                {
                    "camera_id":
                        observation[
                            "camera_id"
                        ],

                    "timestamp":
                        observation[
                            "timestamp"
                        ],

                    "plate":
                        normalize_plate(
                            observation.get(
                                "plate"
                            )
                        ),

                    "plate_confidence":
                        observation.get(
                            "plate_confidence"
                        ),
                }
                for observation
                in observations
            ],
    }


# ============================================================
# Controlled test
# ============================================================

def build_controlled_observations():

    return [

        {
            "vehicle_id":
                "VEHICLE-017",

            "plate":
                "MH12AB1234",

            "plate_confidence":
                0.94,

            "camera_id":
                "CAM-A",

            "timestamp":
                "2026-09-19T10:00:00+05:30",
        },

        {
            "vehicle_id":
                "VEHICLE-017",

            "plate":
                "MH12AB1234",

            "plate_confidence":
                0.91,

            "camera_id":
                "CAM-B",

            "timestamp":
                "2026-09-19T10:03:00+05:30",
        },

        {
            "vehicle_id":
                "VEHICLE-017",

            # Slight OCR variation intentionally introduced.
            "plate":
                "MH12 AB1234",

            "plate_confidence":
                0.88,

            "camera_id":
                "CAM-C",

            "timestamp":
                "2026-09-19T10:05:30+05:30",
        },

        {
            "vehicle_id":
                "VEHICLE-017",

            "plate":
                "MH12AB1234",

            "plate_confidence":
                0.96,

            "camera_id":
                "CAM-D",

            "timestamp":
                "2026-09-19T10:08:00+05:30",
        },
    ]


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "ROADLINK — PHASE 5 "
        "ANPR + JOURNEY INTEGRATION"
    )
    print("=" * 70)
    print()

    observations = (
        build_controlled_observations()
    )

    print(
        "ANPR observations:"
    )

    for observation in observations:

        print(
            f"  "
            f"{observation['camera_id']} "
            f"| "
            f"{observation['plate']} "
            f"| confidence="
            f"{observation['plate_confidence']}"
        )

    print()

    print(
        "Building unified vehicle record..."
    )

    vehicle_record = (
        build_vehicle_record(
            observations
        )
    )

    print()

    print("=" * 70)
    print("UNIFIED VEHICLE RECORD")
    print("=" * 70)
    print()

    print(
        f"Vehicle ID: "
        f"{vehicle_record['vehicle_id']}"
    )

    print(
        f"Plate: "
        f"{vehicle_record['plate']}"
    )

    print(
        f"Plate status: "
        f"{vehicle_record['plate_status']}"
    )

    print(
        f"Plate confidence: "
        f"{vehicle_record['plate_confidence']}"
    )

    print(
        f"Plate support: "
        f"{vehicle_record['plate_support']}/"
        f"{len(observations)}"
    )

    print(
        f"Journey ID: "
        f"{vehicle_record['journey_id']}"
    )

    print(
        f"Journey duration: "
        f"{vehicle_record['journey_duration_minutes']} min"
    )

    print(
        f"Journey distance: "
        f"{vehicle_record['total_distance_km']} km"
    )

    print(
        f"Average estimated speed: "
        f"{vehicle_record['average_estimated_speed_kmh']} km/h"
    )

    print(
        f"Cameras observed: "
        f"{vehicle_record['camera_count']}"
    )

    print()

    print(
        "Camera timeline:"
    )

    for point in vehicle_record[
        "camera_timeline"
    ]:

        print(
            f"  "
            f"{point['timestamp']} "
            f"| "
            f"{point['camera_name']} "
            f"| "
            f"{point['camera_id']}"
        )

    print()

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    checks = {

        "vehicle_identity_preserved":
            vehicle_record[
                "vehicle_id"
            ]
            == "VEHICLE-017",

        "plate_normalized":
            vehicle_record[
                "plate"
            ]
            == "MH12AB1234",

        "plate_confirmed":
            vehicle_record[
                "plate_status"
            ]
            == "CONFIRMED",

        "plate_supported_by_all":
            vehicle_record[
                "plate_support"
            ]
            == 4,

        "journey_connected":
            bool(
                vehicle_record[
                    "journey_id"
                ]
            ),

        "four_camera_journey":
            vehicle_record[
                "camera_count"
            ]
            == 4,

        "distance_preserved":
            abs(
                vehicle_record[
                    "total_distance_km"
                ]
                -
                3.7
            )
            < 0.01,

        "normal_journey":
            vehicle_record[
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
        "roadlink-anpr-journey-integration-test.json"
    )

    report = {

        "test_type":
            "CONTROLLED_ANPR_JOURNEY_INTEGRATION",

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_observations":
            observations,

        "validation":
            checks,

        "vehicle_record":
            vehicle_record,
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
