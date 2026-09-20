import json
import os
import uuid
from collections import Counter
from datetime import datetime

from phase2_2_traffic import analyze_video


# ============================================================
# ROADLINK — PHASE 2.3
# Traffic Alert Engine
# ============================================================


ALERT_PERSISTENCE_FRAMES = 30

# Speed anomaly is deliberately conservative.
# This is NOT a legal speeding threshold.
SPEED_ANOMALY_KMH = 100.0

# Require repeated observations before creating
# a speed anomaly alert.
SPEED_ANOMALY_REQUIRED = 5


def create_alert(
    alert_type,
    severity,
    frame,
    message,
    details=None,
):
    """
    Create one normalized RoadLink alert.
    """

    return {
        "alert_id": uuid.uuid4().hex[:10],

        "type": alert_type,

        "severity": severity,

        "status": "active",

        "frame": frame,

        "created_at": datetime.utcnow().isoformat(),

        "message": message,

        "details": details or {},
    }


def analyze_alerts(report):
    """
    Analyze the Phase 2.2 frame-level traffic report
    and generate deduplicated traffic alerts.
    """

    frame_records = report.get(
        "frame_records",
        []
    )

    alerts = []

    active_condition = None
    condition_start_frame = None

    speed_anomaly_count = 0
    speed_anomaly_start = None

    alert_counts = Counter()

    # --------------------------------------------------------
    # Traffic state alert processing
    # --------------------------------------------------------

    for record in frame_records:

        frame = record["frame"]

        active_vehicles = record[
            "active_vehicles"
        ]

        average_speed = record[
            "average_speed_kmh"
        ]

        traffic = record[
            "traffic"
        ]

        state = traffic[
            "state"
        ]

        # ----------------------------------------------------
        # Determine whether the current frame represents
        # an alert-worthy traffic condition.
        # ----------------------------------------------------

        current_condition = None

        if state == "CRITICAL":

            current_condition = "CRITICAL_TRAFFIC"

        elif state == "HIGH":

            current_condition = "HIGH_TRAFFIC"

        elif (
            state == "MODERATE"
            and average_speed is not None
            and average_speed < 15
        ):

            current_condition = "SLOW_TRAFFIC"

        # ----------------------------------------------------
        # Start / continue / resolve traffic condition
        # ----------------------------------------------------

        if current_condition == active_condition:

            # Condition continues.
            pass

        else:

            # ------------------------------------------------
            # Previous condition ended.
            # ------------------------------------------------

            if active_condition is not None:

                # Find when the previous condition started.
                if condition_start_frame is not None:

                    duration_frames = (
                        frame -
                        condition_start_frame
                    )

                    duration_seconds = (
                        duration_frames /
                        report["video"]["fps"]
                    )

                    # Only create an alert if the condition
                    # actually persisted long enough.
                    if (
                        duration_frames
                        >= ALERT_PERSISTENCE_FRAMES
                    ):

                        severity = (
                            "critical"
                            if active_condition
                            == "CRITICAL_TRAFFIC"
                            else "warning"
                        )

                        title_map = {
                            "CRITICAL_TRAFFIC":
                                "Critical traffic congestion",

                            "HIGH_TRAFFIC":
                                "High traffic congestion",

                            "SLOW_TRAFFIC":
                                "Persistent slow traffic",
                        }

                        message = (
                            f"{title_map[active_condition]} "
                            f"detected for "
                            f"{duration_seconds:.1f} seconds."
                        )

                        alert = create_alert(
                            alert_type=
                                active_condition,

                            severity=severity,

                            frame=
                                condition_start_frame,

                            message=message,

                            details={
                                "duration_seconds":
                                    round(
                                        duration_seconds,
                                        2
                                    ),

                                "ended_frame":
                                    frame,

                                "peak_active_vehicles":
                                    None,

                                "average_speed_kmh":
                                    average_speed,
                            },
                        )

                        alerts.append(alert)

                        alert_counts[
                            active_condition
                        ] += 1

            # ------------------------------------------------
            # Start new condition.
            # ------------------------------------------------

            active_condition = (
                current_condition
            )

            condition_start_frame = (
                frame
                if current_condition is not None
                else None
            )

    # --------------------------------------------------------
    # Handle condition continuing until video ends.
    # --------------------------------------------------------

    if active_condition is not None:

        final_frame = (
            frame_records[-1]["frame"]
            if frame_records
            else 0
        )

        if condition_start_frame is not None:

            duration_frames = (
                final_frame -
                condition_start_frame
            )

            duration_seconds = (
                duration_frames /
                report["video"]["fps"]
            )

            if (
                duration_frames
                >= ALERT_PERSISTENCE_FRAMES
            ):

                severity = (
                    "critical"
                    if active_condition
                    == "CRITICAL_TRAFFIC"
                    else "warning"
                )

                title_map = {
                    "CRITICAL_TRAFFIC":
                        "Critical traffic congestion",

                    "HIGH_TRAFFIC":
                        "High traffic congestion",

                    "SLOW_TRAFFIC":
                        "Persistent slow traffic",
                }

                alert = create_alert(
                    alert_type=
                        active_condition,

                    severity=severity,

                    frame=
                        condition_start_frame,

                    message=(
                        f"{title_map[active_condition]} "
                        f"continued until the end of "
                        f"the analyzed video."
                    ),

                    details={
                        "duration_seconds":
                            round(
                                duration_seconds,
                                2
                            ),

                        "ended_frame":
                            final_frame,
                    },
                )

                alerts.append(alert)

                alert_counts[
                    active_condition
                ] += 1

    # --------------------------------------------------------
    # Speed anomaly detection
    # --------------------------------------------------------
    #
    # This does NOT call the event "speeding violation".
    # It only identifies repeated unusually high estimated
    # speed measurements.
    # --------------------------------------------------------

    for record in frame_records:

        frame = record["frame"]

        average_speed = record[
            "average_speed_kmh"
        ]

        if (
            average_speed is not None
            and average_speed
            >= SPEED_ANOMALY_KMH
        ):

            if speed_anomaly_count == 0:

                speed_anomaly_start = frame

            speed_anomaly_count += 1

        else:

            if (
                speed_anomaly_count
                >= SPEED_ANOMALY_REQUIRED
            ):

                alerts.append(
                    create_alert(
                        alert_type=
                            "SPEED_ANOMALY",

                        severity="info",

                        frame=
                            speed_anomaly_start,

                        message=(
                            "Repeated unusually high "
                            "estimated vehicle speed "
                            "measurements detected."
                        ),

                        details={
                            "measurements":
                                speed_anomaly_count,

                            "threshold_kmh":
                                SPEED_ANOMALY_KMH,
                        },
                    )
                )

                alert_counts[
                    "SPEED_ANOMALY"
                ] += 1

            speed_anomaly_count = 0
            speed_anomaly_start = None

    # --------------------------------------------------------
    # Speed anomaly at end of video
    # --------------------------------------------------------

    if (
        speed_anomaly_count
        >= SPEED_ANOMALY_REQUIRED
    ):

        alerts.append(
            create_alert(
                alert_type="SPEED_ANOMALY",

                severity="info",

                frame=
                    speed_anomaly_start,

                message=(
                    "Repeated unusually high "
                    "estimated vehicle speed "
                    "measurements detected."
                ),

                details={
                    "measurements":
                        speed_anomaly_count,

                    "threshold_kmh":
                        SPEED_ANOMALY_KMH,
                },
            )
        )

        alert_counts[
            "SPEED_ANOMALY"
        ] += 1

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    return {
        "total_alerts": len(alerts),

        "alert_counts": dict(
            alert_counts
        ),

        "alerts": alerts,
    }


def run():

    print()
    print("=" * 65)
    print("ROADLINK — PHASE 2.3 ALERT ENGINE")
    print("=" * 65)
    print()

    # --------------------------------------------------------
    # Reuse the validated Phase 2.2 pipeline.
    # --------------------------------------------------------

    print(
        "Running Phase 2.2 traffic intelligence..."
    )

    report = analyze_video()

    print()
    print(
        "Analyzing traffic conditions for alerts..."
    )
    print()

    alert_report = analyze_alerts(
        report
    )

    analysis_id = report[
        "analysis_id"
    ]

    output_path = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        "storage",
        "outputs",
        f"roadlink-alerts-{analysis_id}.json"
    )

    final_report = {

        "analysis_id":
            analysis_id,

        "source_video":
            report["source_video"],

        "traffic_summary": {

            "unique_vehicle_ids":
                report[
                    "unique_vehicle_ids"
                ],

            "average_active_vehicles":
                report[
                    "average_active_vehicles"
                ],

            "peak_active_vehicles":
                report[
                    "peak_active_vehicles"
                ],

            "average_estimated_speed_kmh":
                report[
                    "average_valid_estimated_speed_kmh"
                ],

            "peak_estimated_speed_kmh":
                report[
                    "peak_valid_estimated_speed_kmh"
                ],

            "traffic_states":
                report[
                    "traffic_states"
                ],
        },

        "alert_engine": {

            "persistence_frames":
                ALERT_PERSISTENCE_FRAMES,

            "speed_anomaly_threshold_kmh":
                SPEED_ANOMALY_KMH,

            "speed_anomaly_required_measurements":
                SPEED_ANOMALY_REQUIRED,
        },

        "alerts":
            alert_report,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            final_report,
            file,
            indent=2
        )

    print("=" * 65)
    print("PHASE 2.3 COMPLETE")
    print("=" * 65)
    print()

    print(
        f"Analysis ID: "
        f"{analysis_id}"
    )

    print(
        f"Total alerts: "
        f"{alert_report['total_alerts']}"
    )

    print(
        f"Alert counts: "
        f"{alert_report['alert_counts']}"
    )

    print()

    if alert_report["alerts"]:

        print("Generated alerts:")
        print()

        for alert in alert_report[
            "alerts"
        ]:

            print(
                f"[{alert['severity'].upper()}] "
                f"{alert['type']} "
                f"at frame "
                f"{alert['frame']}"
            )

            print(
                f"  {alert['message']}"
            )

            print()

    else:

        print(
            "No traffic alerts generated."
        )

        print(
            "This is expected for the current "
            "low-density sample video."
        )

    print(
        f"Alert report: "
        f"{output_path}"
    )

    print()


if __name__ == "__main__":
    run()
