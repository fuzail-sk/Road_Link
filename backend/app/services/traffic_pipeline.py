from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from app.config import VIDEOS_DIR, OUTPUTS_DIR
from app.services.vehicle_tracker import VehicleTracker
from app.services.speed_estimator import SpeedEstimator
from app.services.traffic_engine import TrafficEngine


def analyze_traffic_video(
    video_path: str | Path,
    output_prefix: str = "roadlink-traffic-test",
) -> dict[str, Any]:

    video_path = Path(video_path)

    if not video_path.exists():
        raise RuntimeError(
            f"Video not found: {video_path}"
        )

    OUTPUTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():
        raise RuntimeError(
            f"Could not open video: {video_path}"
        )

    fps = capture.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 30.0

    width = int(
        capture.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    total_frames = int(
        capture.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    output_path = (
        OUTPUTS_DIR
        / f"{output_prefix}.mp4"
    )

    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    if not writer.isOpened():
        capture.release()
        raise RuntimeError(
            f"Could not create output video: {output_path}"
        )

    tracker = VehicleTracker()

    # IMPORTANT:
    # One SpeedEstimator must live for the entire video.
    # This preserves position history between frames.
    speed_estimator = SpeedEstimator()

    traffic_engine = TrafficEngine()

    traffic_state_counts: dict[str, int] = {
        "LOW": 0,
        "MODERATE": 0,
        "HIGH": 0,
        "CRITICAL": 0,
    }

    density_counts: dict[str, int] = {
        "LOW": 0,
        "MODERATE": 0,
        "HIGH": 0,
        "CRITICAL": 0,
    }

    speed_category_counts: dict[str, int] = {
        "FREE_FLOW": 0,
        "SLOWING": 0,
        "SLOW": 0,
        "STOPPED_OR_CRAWLING": 0,
        "UNKNOWN": 0,
    }

    active_vehicle_samples: list[int] = []
    valid_average_speeds: list[float] = []
    traffic_scores: list[float] = []

    frame_index = 0
    frames_processed = 0
    unique_vehicle_ids: set[int] = set()

    while True:
        success, frame = capture.read()

        if not success:
            break

        observations = tracker.track_frame(
            frame=frame,
            frame_index=frame_index,
            fps=fps,
            speed_estimator=speed_estimator,
        )

        for observation in observations:

            track_id = observation.get(
                "track_id",
                -1,
            )

            if track_id >= 0:
                unique_vehicle_ids.add(
                    track_id
                )

            x1, y1, x2, y2 = observation[
                "bbox"
            ]

            vehicle_type = observation[
                "vehicle_type"
            ]

            speed = observation.get(
                "speed_kmh"
            )

            label = (
                f"ID {track_id} | "
                f"{vehicle_type}"
            )

            if speed is not None:
                label += (
                    f" | "
                    f"{speed:.1f} km/h"
                )

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (255, 255, 255),
                2,
            )

            cv2.putText(
                frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        traffic = traffic_engine.analyze_snapshot(
            observations
        )

        traffic_state = traffic[
            "traffic_state"
        ]

        density_category = traffic[
            "density_category"
        ]

        speed_category = traffic[
            "speed_category"
        ]

        traffic_state_counts[
            traffic_state
        ] += 1

        density_counts[
            density_category
        ] += 1

        speed_category_counts[
            speed_category
        ] += 1

        active_vehicle_samples.append(
            traffic[
                "active_vehicle_count"
            ]
        )

        if traffic[
            "average_speed_kmh"
        ] is not None:
            valid_average_speeds.append(
                traffic[
                    "average_speed_kmh"
                ]
            )

        traffic_scores.append(
            traffic[
                "traffic_score"
            ]
        )

        cv2.putText(
            frame,
            (
                f"Traffic: {traffic_state} | "
                f"Density: {density_category}"
            ),
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            (
                f"Vehicles: "
                f"{traffic['active_vehicle_count']} | "
                f"Speed: "
                f"{traffic['average_speed_kmh']}"
            ),
            (20, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            (
                f"Score: "
                f"{traffic['traffic_score']:.1f}"
            ),
            (20, 84),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        writer.write(frame)

        frames_processed += 1
        frame_index += 1

    capture.release()
    writer.release()

    average_active_vehicles = (
        sum(active_vehicle_samples)
        / len(active_vehicle_samples)
        if active_vehicle_samples
        else 0.0
    )

    peak_active_vehicles = (
        max(active_vehicle_samples)
        if active_vehicle_samples
        else 0
    )

    average_speed = (
        sum(valid_average_speeds)
        / len(valid_average_speeds)
        if valid_average_speeds
        else None
    )

    peak_speed = (
        max(valid_average_speeds)
        if valid_average_speeds
        else None
    )

    average_traffic_score = (
        sum(traffic_scores)
        / len(traffic_scores)
        if traffic_scores
        else 0.0
    )

    return {
        "source_video": video_path.name,
        "output_video": str(output_path),
        "fps": round(fps, 3),
        "total_frames": total_frames,
        "frames_processed": frames_processed,
        "unique_vehicle_ids": len(
            unique_vehicle_ids
        ),
        "average_active_vehicles": round(
            average_active_vehicles,
            2,
        ),
        "peak_active_vehicles": (
            peak_active_vehicles
        ),
        "average_estimated_speed_kmh": (
            round(average_speed, 2)
            if average_speed is not None
            else None
        ),
        "peak_estimated_speed_kmh": (
            round(peak_speed, 2)
            if peak_speed is not None
            else None
        ),
        "average_traffic_score": round(
            average_traffic_score,
            2,
        ),
        "traffic_states": traffic_state_counts,
        "density_categories": density_counts,
        "speed_categories": speed_category_counts,
        "calibration_status": "prototype",
        "real_world_calibration_required": True,
    }


if __name__ == "__main__":
    result = analyze_traffic_video(
        VIDEOS_DIR / "ParkingVideo.mp4"
    )

    print("TRAFFIC PIPELINE RESULT")
    print("=======================")

    for key, value in result.items():
        print(f"{key}: {value}")
