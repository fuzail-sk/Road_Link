import json
import os
import uuid
from datetime import datetime, timezone


# ============================================================
# ROADLINK — PHASE 3
# Emergency Corridor Intelligence
# ============================================================
#
# This module evaluates candidate emergency corridors using
# traffic conditions on each road segment.
#
# IMPORTANT:
# This is a controlled corridor recommendation engine.
# It does NOT control traffic signals.
# It does NOT claim to navigate a real city road network.
# ============================================================


# ------------------------------------------------------------
# Traffic penalties
# ------------------------------------------------------------

TRAFFIC_PENALTY = {
    "LOW": 0,
    "MODERATE": 20,
    "HIGH": 50,
    "CRITICAL": 100,
}


# ------------------------------------------------------------
# Corridor configuration
# ------------------------------------------------------------

MIN_ROUTE_SPEED_KMH = 5.0


def normalize_segment(segment):
    """
    Normalize one road segment into a predictable structure.
    """

    traffic_state = str(
        segment.get(
            "traffic_state",
            "LOW"
        )
    ).upper()

    if traffic_state not in TRAFFIC_PENALTY:
        traffic_state = "LOW"

    distance_km = float(
        segment.get(
            "distance_km",
            1.0
        )
    )

    average_speed_kmh = float(
        segment.get(
            "average_speed_kmh",
            30.0
        )
    )

    return {
        "road_id":
            segment.get(
                "road_id",
                "unknown"
            ),

        "from":
            segment.get(
                "from",
                "unknown"
            ),

        "to":
            segment.get(
                "to",
                "unknown"
            ),

        "distance_km":
            distance_km,

        "average_speed_kmh":
            average_speed_kmh,

        "traffic_state":
            traffic_state,

        "traffic_penalty":
            TRAFFIC_PENALTY[
                traffic_state
            ],
    }


def estimate_travel_time(
    distance_km,
    speed_kmh
):
    """
    Estimate segment travel time in seconds.

    This is an analytical estimate, not a live navigation
    ETA.
    """

    speed_kmh = max(
        speed_kmh,
        MIN_ROUTE_SPEED_KMH
    )

    hours = (
        distance_km /
        speed_kmh
    )

    return hours * 3600


def score_segment(segment):
    """
    Calculate the cost of traversing a road segment.

    Lower score = more suitable for emergency routing.

    The score combines:

    - estimated travel time
    - traffic congestion penalty
    - severe congestion penalty
    """

    segment = normalize_segment(
        segment
    )

    travel_time_seconds = estimate_travel_time(
        segment["distance_km"],
        segment["average_speed_kmh"]
    )

    congestion_penalty = (
        segment["traffic_penalty"]
        * 2
    )

    if segment["traffic_state"] == "CRITICAL":

        congestion_penalty += 100

    elif segment["traffic_state"] == "HIGH":

        congestion_penalty += 50

    total_cost = (
        travel_time_seconds
        +
        congestion_penalty
    )

    segment["estimated_travel_time_seconds"] = round(
        travel_time_seconds,
        2
    )

    segment["route_cost"] = round(
        total_cost,
        2
    )

    return segment


def score_corridor(
    corridor
):
    """
    Score an entire emergency corridor.
    """

    segments = [
        score_segment(segment)
        for segment in corridor[
            "segments"
        ]
    ]

    total_distance = sum(
        segment["distance_km"]
        for segment in segments
    )

    total_travel_time = sum(
        segment[
            "estimated_travel_time_seconds"
        ]
        for segment in segments
    )

    total_cost = sum(
        segment["route_cost"]
        for segment in segments
    )

    states = [
        segment["traffic_state"]
        for segment in segments
    ]

    critical_segments = states.count(
        "CRITICAL"
    )

    high_segments = states.count(
        "HIGH"
    )

    moderate_segments = states.count(
        "MODERATE"
    )

    return {

        "corridor_id":
            corridor["corridor_id"],

        "name":
            corridor["name"],

        "origin":
            corridor["origin"],

        "destination":
            corridor["destination"],

        "segments":
            segments,

        "total_distance_km":
            round(
                total_distance,
                2
            ),

        "estimated_travel_time_seconds":
            round(
                total_travel_time,
                2
            ),

        "estimated_travel_time_minutes":
            round(
                total_travel_time / 60,
                2
            ),

        "route_cost":
            round(
                total_cost,
                2
            ),

        "critical_segments":
            critical_segments,

        "high_segments":
            high_segments,

        "moderate_segments":
            moderate_segments,

        "traffic_states":
            states,
    }


def recommend_corridor(
    emergency,
    corridors
):
    """
    Evaluate all candidate corridors and select the
    lowest-cost corridor.

    The result includes the evaluated alternatives so
    an operator can understand why the recommendation
    was produced.
    """

    evaluated = [
        score_corridor(corridor)
        for corridor in corridors
    ]

    if not evaluated:
        raise ValueError(
            "No candidate emergency corridors supplied."
        )

    # Sort by total route cost.
    evaluated.sort(
        key=lambda item:
            item["route_cost"]
    )

    recommended = evaluated[0]

    # --------------------------------------------------------
    # Build explanation
    # --------------------------------------------------------

    reasons = []

    if recommended[
        "critical_segments"
    ] == 0:

        reasons.append(
            "No critical traffic segments "
            "were detected on the recommended "
            "corridor."
        )

    if recommended[
        "high_segments"
    ] == 0:

        reasons.append(
            "No high-congestion segments "
            "were detected on the recommended "
            "corridor."
        )

    reasons.append(
        "The corridor has the lowest calculated "
        "emergency routing cost among the "
        "evaluated alternatives."
    )

    return {

        "recommendation_id":
            uuid.uuid4().hex[:10],

        "emergency": emergency,

        "recommended_corridor":
            recommended,

        "alternatives":
            evaluated,

        "reasoning":
            reasons,

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


# ============================================================
# CONTROLLED TEST
# ============================================================


def build_controlled_scenario():

    emergency = {

        "incident_id":
            "EMG-TEST-001",

        "emergency_type":
            "AMBULANCE",

        "origin":
            "Camera-A",

        "destination":
            "Hospital-Central",
    }


    # --------------------------------------------------------
    # Corridor A
    # --------------------------------------------------------
    #
    # Shorter route but significant congestion.
    #

    corridor_a = {

        "corridor_id":
            "CORRIDOR-A",

        "name":
            "Main Road Corridor",

        "origin":
            "Camera-A",

        "destination":
            "Hospital-Central",

        "segments": [

            {
                "road_id":
                    "A1",

                "from":
                    "Camera-A",

                "to":
                    "Junction-1",

                "distance_km":
                    1.0,

                "average_speed_kmh":
                    12,

                "traffic_state":
                    "HIGH",
            },

            {
                "road_id":
                    "A2",

                "from":
                    "Junction-1",

                "to":
                    "Hospital-Central",

                "distance_km":
                    1.0,

                "average_speed_kmh":
                    10,

                "traffic_state":
                    "HIGH",
            },
        ],
    }


    # --------------------------------------------------------
    # Corridor B
    # --------------------------------------------------------
    #
    # Slightly longer but mostly free flowing.
    #

    corridor_b = {

        "corridor_id":
            "CORRIDOR-B",

        "name":
            "Ring Road Corridor",

        "origin":
            "Camera-A",

        "destination":
            "Hospital-Central",

        "segments": [

            {
                "road_id":
                    "B1",

                "from":
                    "Camera-A",

                "to":
                    "Junction-2",

                "distance_km":
                    1.4,

                "average_speed_kmh":
                    35,

                "traffic_state":
                    "LOW",
            },

            {
                "road_id":
                    "B2",

                "from":
                    "Junction-2",

                "to":
                    "Hospital-Central",

                "distance_km":
                    1.2,

                "average_speed_kmh":
                    32,

                "traffic_state":
                    "LOW",
            },
        ],
    }


    # --------------------------------------------------------
    # Corridor C
    # --------------------------------------------------------
    #
    # Very congested alternative.
    #

    corridor_c = {

        "corridor_id":
            "CORRIDOR-C",

        "name":
            "Market Road Corridor",

        "origin":
            "Camera-A",

        "destination":
            "Hospital-Central",

        "segments": [

            {
                "road_id":
                    "C1",

                "from":
                    "Camera-A",

                "to":
                    "Market-Junction",

                "distance_km":
                    0.8,

                "average_speed_kmh":
                    6,

                "traffic_state":
                    "CRITICAL",
            },

            {
                "road_id":
                    "C2",

                "from":
                    "Market-Junction",

                "to":
                    "Hospital-Central",

                "distance_km":
                    1.0,

                "average_speed_kmh":
                    8,

                "traffic_state":
                    "CRITICAL",
            },
        ],
    }


    return (
        emergency,
        [
            corridor_a,
            corridor_b,
            corridor_c,
        ]
    )


def main():

    print()
    print("=" * 70)
    print(
        "ROADLINK — PHASE 3 "
        "EMERGENCY CORRIDOR INTELLIGENCE"
    )
    print("=" * 70)
    print()

    emergency, corridors = (
        build_controlled_scenario()
    )

    print(
        "Emergency type: "
        f"{emergency['emergency_type']}"
    )

    print(
        "Origin: "
        f"{emergency['origin']}"
    )

    print(
        "Destination: "
        f"{emergency['destination']}"
    )

    print()
    print(
        "Evaluating candidate corridors..."
    )
    print()

    result = recommend_corridor(
        emergency,
        corridors
    )

    # --------------------------------------------------------
    # Print evaluated alternatives.
    # --------------------------------------------------------

    print(
        "CORRIDOR ANALYSIS"
    )

    print(
        "-" * 70
    )

    for corridor in result[
        "alternatives"
    ]:

        print(
            f"{corridor['corridor_id']} "
            f"| {corridor['name']}"
        )

        print(
            f"  Distance: "
            f"{corridor['total_distance_km']} km"
        )

        print(
            f"  Estimated time: "
            f"{corridor['estimated_travel_time_minutes']} min"
        )

        print(
            f"  Route cost: "
            f"{corridor['route_cost']}"
        )

        print(
            f"  Traffic states: "
            f"{corridor['traffic_states']}"
        )

        print()

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    recommended = result[
        "recommended_corridor"
    ]

    print("=" * 70)
    print(
        "EMERGENCY CORRIDOR RECOMMENDATION"
    )
    print("=" * 70)
    print()

    print(
        f"Recommended corridor: "
        f"{recommended['corridor_id']}"
    )

    print(
        f"Route: "
        f"{recommended['name']}"
    )

    print(
        f"Estimated travel time: "
        f"{recommended['estimated_travel_time_minutes']} min"
    )

    print(
        f"Route cost: "
        f"{recommended['route_cost']}"
    )

    print()

    print(
        "Reasoning:"
    )

    for reason in result[
        "reasoning"
    ]:

        print(
            f"  • {reason}"
        )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    expected_corridor = (
        "CORRIDOR-B"
    )

    passed = (
        recommended["corridor_id"]
        == expected_corridor
    )

    print()
    print("=" * 70)
    print("VALIDATION")
    print("=" * 70)
    print()

    print(
        "Emergency corridor selection: "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    # --------------------------------------------------------
    # Save report.
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
        "roadlink-emergency-corridor-test.json"
    )

    report = {

        "test_type":
            "CONTROLLED_EMERGENCY_CORRIDOR_TEST",

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "expected_corridor":
            expected_corridor,

        "actual_corridor":
            recommended[
                "corridor_id"
            ],

        "validation":
            {
                "passed":
                    passed
            },

        "result":
            result,
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

    if passed:

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
