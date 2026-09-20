import json
import os
import uuid
from datetime import datetime, timezone

from phase2_3_alerts import analyze_alerts


# ============================================================
# ROADLINK — CONTROLLED ALERT ENGINE TEST
# ============================================================
#
# This is NOT production traffic data.
#
# It creates controlled frame-level traffic conditions to
# verify that the Phase 2.3 alert engine behaves correctly.
# ============================================================


FPS = 30.0


def make_frame(
    frame,
    active_vehicles,
    average_speed,
    traffic_state,
):
    """
    Create one controlled traffic measurement.
    """

    return {
        "frame": frame,

        "active_vehicles":
            active_vehicles,

        "average_speed_kmh":
            average_speed,

        "traffic": {
            "state":
                traffic_state,

            "score":
                0,

            "density_category":
                (
                    "LOW"
                    if active_vehicles <= 3
                    else "MODERATE"
                    if active_vehicles <= 7
                    else "HIGH"
                    if active_vehicles <= 12
                    else "CRITICAL"
                ),

            "speed_category":
                (
                    "FREE_FLOW"
                    if average_speed >= 30
                    else "SLOWING"
                    if average_speed >= 20
                    else "SLOW"
                    if average_speed >= 10
                    else "STOPPED_OR_CRAWLING"
                ),

            "density_score": 0,

            "speed_score": 0,

            "persistent_moderate":
                False,

            "persistent_high":
                False,
        },
    }


def build_test_scenario():
    """
    Construct a controlled traffic scenario.

    Timeline:

    0–5 sec
        LOW traffic

    5–15 sec
        HIGH traffic

    15–25 sec
        CRITICAL traffic

    25–30 sec
        LOW traffic again
    """

    frames = []

    frame = 1

    # --------------------------------------------------------
    # Scenario 1 — Normal traffic
    # --------------------------------------------------------

    print(
        "Scenario 1: LOW traffic"
    )

    for _ in range(
        int(5 * FPS)
    ):

        frames.append(
            make_frame(
                frame=frame,

                active_vehicles=2,

                average_speed=35.0,

                traffic_state="LOW",
            )
        )

        frame += 1

    # --------------------------------------------------------
    # Scenario 2 — Persistent HIGH traffic
    # --------------------------------------------------------

    print(
        "Scenario 2: HIGH traffic"
    )

    for _ in range(
        int(10 * FPS)
    ):

        frames.append(
            make_frame(
                frame=frame,

                active_vehicles=9,

                average_speed=12.0,

                traffic_state="HIGH",
            )
        )

        frame += 1

    # --------------------------------------------------------
    # Scenario 3 — Persistent CRITICAL traffic
    # --------------------------------------------------------

    print(
        "Scenario 3: CRITICAL traffic"
    )

    for _ in range(
        int(10 * FPS)
    ):

        frames.append(
            make_frame(
                frame=frame,

                active_vehicles=14,

                average_speed=6.0,

                traffic_state="CRITICAL",
            )
        )

        frame += 1

    # --------------------------------------------------------
    # Scenario 4 — Traffic clears
    # --------------------------------------------------------

    print(
        "Scenario 4: Traffic clears"
    )

    for _ in range(
        int(5 * FPS)
    ):

        frames.append(
            make_frame(
                frame=frame,

                active_vehicles=2,

                average_speed=35.0,

                traffic_state="LOW",
            )
        )

        frame += 1

    return frames


def main():

    print()
    print("=" * 70)
    print("ROADLINK — CONTROLLED ALERT ENGINE TEST")
    print("=" * 70)
    print()

    frame_records = build_test_scenario()

    report = {

        "analysis_id":
            "CONTROLLED-"
            + uuid.uuid4().hex[:8],

        "source_video":
            "CONTROLLED_TEST_DATA",

        "video": {
            "fps":
                FPS,

            "total_frames":
                len(frame_records),

            "duration_seconds":
                len(frame_records) / FPS,
        },

        "unique_vehicle_ids":
            0,

        "average_active_vehicles":
            0,

        "peak_active_vehicles":
            14,

        "average_valid_estimated_speed_kmh":
            0,

        "peak_valid_estimated_speed_kmh":
            0,

        "traffic_states": {},

        "frame_records":
            frame_records,
    }

    # --------------------------------------------------------
    # Run the actual Phase 2.3 alert engine.
    # --------------------------------------------------------

    print()
    print(
        "Running Phase 2.3 alert engine..."
    )
    print()

    result = analyze_alerts(
        report
    )

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CONTROLLED TEST RESULTS")
    print("=" * 70)
    print()

    print(
        f"Total alerts generated: "
        f"{result['total_alerts']}"
    )

    print(
        f"Alert counts: "
        f"{result['alert_counts']}"
    )

    print()

    if result["alerts"]:

        print("Generated alerts:")
        print()

        for index, alert in enumerate(
            result["alerts"],
            start=1
        ):

            print(
                f"{index}. "
                f"[{alert['severity'].upper()}] "
                f"{alert['type']}"
            )

            print(
                f"   Start frame: "
                f"{alert['frame']}"
            )

            print(
                f"   {alert['message']}"
            )

            print()

    else:

        print(
            "ERROR: No alerts were generated."
        )

    # --------------------------------------------------------
    # Expected behavior
    # --------------------------------------------------------

    alert_types = [
        alert["type"]
        for alert in result["alerts"]
    ]

    high_detected = (
        "HIGH_TRAFFIC"
        in alert_types
    )

    critical_detected = (
        "CRITICAL_TRAFFIC"
        in alert_types
    )

    duplicate_high = (
        alert_types.count(
            "HIGH_TRAFFIC"
        )
        > 1
    )

    duplicate_critical = (
        alert_types.count(
            "CRITICAL_TRAFFIC"
        )
        > 1
    )

    print("=" * 70)
    print("VALIDATION")
    print("=" * 70)
    print()

    print(
        "HIGH_TRAFFIC detected: "
        + (
            "PASS"
            if high_detected
            else "FAIL"
        )
    )

    print(
        "CRITICAL_TRAFFIC detected: "
        + (
            "PASS"
            if critical_detected
            else "FAIL"
        )
    )

    print(
        "HIGH alert deduplication: "
        + (
            "PASS"
            if not duplicate_high
            else "FAIL"
        )
    )

    print(
        "CRITICAL alert deduplication: "
        + (
            "PASS"
            if not duplicate_critical
            else "FAIL"
        )
    )

    # --------------------------------------------------------
    # Save test report.
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
        "roadlink-controlled-alert-test.json"
    )

    test_report = {

        "test_type":
            "CONTROLLED_ALERT_ENGINE_TEST",

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "scenario": {

            "normal_duration_seconds":
                5,

            "high_duration_seconds":
                10,

            "critical_duration_seconds":
                10,

            "recovery_duration_seconds":
                5,
        },

        "expected": {

            "HIGH_TRAFFIC":
                True,

            "CRITICAL_TRAFFIC":
                True,

            "duplicate_high":
                False,

            "duplicate_critical":
                False,
        },

        "actual":
            result,

        "validation": {

            "high_detected":
                high_detected,

            "critical_detected":
                critical_detected,

            "high_deduplicated":
                not duplicate_high,

            "critical_deduplicated":
                not duplicate_critical,
        },
    }

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            test_report,
            file,
            indent=2
        )

    print()
    print(
        f"Test report: "
        f"{output_path}"
    )

    print()

    if (
        high_detected
        and critical_detected
        and not duplicate_high
        and not duplicate_critical
    ):

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
