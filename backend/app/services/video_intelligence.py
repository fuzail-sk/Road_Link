from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import cv2

from app.config import VIDEOS_DIR, OUTPUTS_DIR
from app.services.vehicle_tracker import vehicle_tracker
from app.services.speed_estimator import SpeedEstimator
from app.services.traffic_engine import TrafficEngine
from app.services.alert_engine import AlertEngine


class VideoIntelligenceService:
    """
    End-to-end RoadLink video intelligence pipeline.

    Video
      -> YOLO + ByteTrack
      -> persistent vehicle IDs
      -> speed estimation
      -> traffic intelligence
      -> alert engine
      -> analysis report
    """

    def __init__(
        self,
        persistence_required: int = 3,
    ):
        self.tracker = vehicle_tracker
        self.speed_estimator = SpeedEstimator()
        self.traffic_engine = TrafficEngine()
        self.alert_engine = AlertEngine(
            persistence_required=persistence_required
        )

    def analyze(
        self,
        video_path: Path,
    ) -> dict[str, Any]:

        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(
                f"Video not found: {video_path}"
            )

        analysis_id = uuid.uuid4().hex[:10]

        capture = cv2.VideoCapture(
            str(video_path)
        )

        if not capture.isOpened():
            raise RuntimeError(
                f"Unable to open video: {video_path}"
            )

        fps = capture.get(
            cv2.CAP_PROP_FPS
        )

        if not fps or fps <= 0:
            fps = 30.0

        frame_count = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        width = int(
            capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )

        height = int(
            capture.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
        )

        started_at = time.perf_counter()

        output_video_path = (
            OUTPUTS_DIR
            / f"roadlink-video-intelligence-{analysis_id}.mp4"
        )

        ffmpeg_path = shutil.which("ffmpeg")

        if not ffmpeg_path:
            raise RuntimeError(
                "FFmpeg was not found on PATH. "
                "Install FFmpeg before running video intelligence."
            )

        ffmpeg_command = [
            ffmpeg_path,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "-",
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_video_path),
        ]

        video_process = subprocess.Popen(
            ffmpeg_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        frames_processed = 0

        unique_vehicle_ids: set[int] = set()

        active_vehicle_counts: list[int] = []
        average_speeds: list[float] = []
        peak_speeds: list[float] = []
        traffic_scores: list[float] = []

        traffic_states: Counter[str] = Counter()
        density_categories: Counter[str] = Counter()
        speed_categories: Counter[str] = Counter()

        generated_alerts: list[
            dict[str, Any]
        ] = []

        while True:

            success, frame = capture.read()

            if not success:
                break

            observations = (
                self.tracker.track_frame(
                    frame=frame,
                    frame_index=frames_processed,
                    fps=fps,
                    speed_estimator=(
                        self.speed_estimator
                    ),
                )
            )

            for observation in observations:

                track_id = observation.get(
                    "track_id"
                )

                if track_id is not None:
                    unique_vehicle_ids.add(
                        int(track_id)
                    )

            traffic_snapshot = (
                self.traffic_engine
                .analyze_snapshot(
                    observations
                )
            )

            alerts = (
                self.alert_engine.evaluate(
                    traffic_snapshot
                )
            )

            generated_alerts.extend(
                alerts
            )

            active_count = traffic_snapshot.get(
                "active_vehicle_count",
                0,
            )

            average_speed = (
                traffic_snapshot.get(
                    "average_speed_kmh"
                )
            )

            peak_speed = (
                traffic_snapshot.get(
                    "peak_speed_kmh"
                )
            )

            traffic_score = (
                traffic_snapshot.get(
                    "traffic_score"
                )
            )

            traffic_state = (
                traffic_snapshot.get(
                    "traffic_state",
                    "UNKNOWN",
                )
            )

            density_category = (
                traffic_snapshot.get(
                    "density_category",
                    "UNKNOWN",
                )
            )

            speed_category = (
                traffic_snapshot.get(
                    "speed_category",
                    "UNKNOWN",
                )
            )

            active_vehicle_counts.append(
                active_count
            )

            if average_speed is not None:
                average_speeds.append(
                    float(average_speed)
                )

            if peak_speed is not None:
                peak_speeds.append(
                    float(peak_speed)
                )

            if traffic_score is not None:
                traffic_scores.append(
                    float(traffic_score)
                )

            traffic_states[
                traffic_state
            ] += 1

            density_categories[
                density_category
            ] += 1

            speed_categories[
                speed_category
            ] += 1

            # --------------------------------------------------------
            # Annotated browser-compatible RoadLink video
            # --------------------------------------------------------
            annotated_frame = frame.copy()

            for observation in observations:

                bbox = observation.get("bbox")

                track_id = observation.get(
                    "track_id"
                )

                vehicle_type = observation.get(
                    "vehicle_type",
                    "vehicle",
                )

                confidence = observation.get(
                    "confidence",
                    0.0,
                )

                if bbox and len(bbox) == 4:

                    x1, y1, x2, y2 = [
                        int(value)
                        for value in bbox
                    ]

                    cv2.rectangle(
                        annotated_frame,
                        (x1, y1),
                        (x2, y2),
                        (255, 255, 255),
                        2,
                    )

                    label = (
                        f"{vehicle_type} | ID {track_id}"
                        if track_id is not None
                        else f"{vehicle_type}"
                    )

                    cv2.putText(
                        annotated_frame,
                        label,
                        (x1, max(25, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 255, 255),
                        2,
                        cv2.LINE_AA,
                    )

                    cv2.putText(
                        annotated_frame,
                        f"{confidence:.2f}",
                        (x1, min(height - 10, y2 + 20)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )

            overlay_lines = [
                f"ROADLINK | TRAFFIC: {traffic_state}",
                f"ACTIVE VEHICLES: {active_count}",
                (
                    f"AVG SPEED: {float(average_speed):.1f} km/h"
                    if average_speed is not None
                    else "AVG SPEED: N/A"
                ),
                (
                    f"TRAFFIC SCORE: {float(traffic_score):.1f}"
                    if traffic_score is not None
                    else "TRAFFIC SCORE: N/A"
                ),
            ]

            y = 32

            for line in overlay_lines:

                cv2.putText(
                    annotated_frame,
                    line,
                    (18, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

                y += 28

            if video_process.stdin is None:
                raise RuntimeError(
                    "FFmpeg video input stream was not available."
                )

            try:

                video_process.stdin.write(
                    annotated_frame.tobytes()
                )

            except BrokenPipeError as exc:

                stderr = (
                    video_process.stderr.read().decode(
                        "utf-8",
                        errors="replace",
                    )
                    if video_process.stderr
                    else ""
                )

                raise RuntimeError(
                    "FFmpeg stopped while encoding RoadLink output video. "
                    + stderr[-2000:]
                ) from exc

            frames_processed += 1

        capture.release()

        if video_process.stdin is not None:
            video_process.stdin.close()

        ffmpeg_stderr = (
            video_process.stderr.read().decode(
                "utf-8",
                errors="replace",
            )
            if video_process.stderr
            else ""
        )

        ffmpeg_return_code = video_process.wait()

        if ffmpeg_return_code != 0:
            raise RuntimeError(
                "FFmpeg failed to encode the RoadLink output video. "
                + ffmpeg_stderr[-3000:]
            )

        if not output_video_path.exists():
            raise RuntimeError(
                f"RoadLink output video was not created: "
                f"{output_video_path}"
            )

        processing_seconds = (
            time.perf_counter()
            - started_at
        )

        def average(
            values: list[float],
        ) -> float | None:

            if not values:
                return None

            return round(
                sum(values) / len(values),
                2,
            )

        analysis = {
            "analysis_id": analysis_id,
            "source_video": video_path.name,
            "video": {
                "fps": round(fps, 2),
                "frame_count": frame_count,
                "resolution": (
                    f"{width}x{height}"
                ),
            },
            "processing": {
                "frames_processed": (
                    frames_processed
                ),
                "processing_seconds": round(
                    processing_seconds,
                    2,
                ),
            },
            "vehicles": {
                "unique_vehicle_ids": len(
                    unique_vehicle_ids
                ),
                "average_active_vehicles": average(
                    [
                        float(x)
                        for x in active_vehicle_counts
                    ]
                ),
                "peak_active_vehicles": (
                    max(
                        active_vehicle_counts
                    )
                    if active_vehicle_counts
                    else 0
                ),
            },
            "speed": {
                "average_estimated_speed_kmh": average(
                    average_speeds
                ),
                "peak_estimated_speed_kmh": (
                    round(
                        max(peak_speeds),
                        2,
                    )
                    if peak_speeds
                    else None
                ),
                "valid_speed_samples": len(
                    average_speeds
                ),
            },
            "traffic": {
                "average_traffic_score": average(
                    traffic_scores
                ),
                "traffic_states": dict(
                    traffic_states
                ),
                "density_categories": dict(
                    density_categories
                ),
                "speed_categories": dict(
                    speed_categories
                ),
            },
            "alerts": {
                "total_generated": len(
                    generated_alerts
                ),
                "by_type": dict(
                    Counter(
                        alert["alert_type"]
                        for alert in generated_alerts
                    )
                ),
                "items": generated_alerts,
            },
            "calibration": (
                self.speed_estimator
                .calibration_info()
            ),
            "output_video": (
                f"/outputs/{output_video_path.name}"
            ),
            "video_encoding": {
                "codec": "H.264",
                "container": "MP4",
                "browser_compatible": True,
            },
        }

        report_path = (
            OUTPUTS_DIR
            / (
                f"roadlink-video-intelligence-"
                f"{analysis_id}.json"
            )
        )

        report_path.write_text(
            json.dumps(
                analysis,
                indent=2,
            ),
            encoding="utf-8",
        )

        analysis["report"] = (
            f"/outputs/{report_path.name}"
        )

        return analysis


def main() -> None:

    video_path = (
        VIDEOS_DIR
        / "ParkingVideo.mp4"
    )

    print(
        "\n========== ROADLINK END-TO-END VIDEO INTELLIGENCE =========="
    )

    service = VideoIntelligenceService(
        persistence_required=3
    )

    result = service.analyze(
        video_path
    )

    print(
        "\n========== RESULT =========="
    )

    print(
        "Analysis ID:",
        result["analysis_id"],
    )

    print(
        "Unique vehicles:",
        result["vehicles"][
            "unique_vehicle_ids"
        ],
    )

    print(
        "Frames processed:",
        result["processing"][
            "frames_processed"
        ],
    )

    print(
        "Average active vehicles:",
        result["vehicles"][
            "average_active_vehicles"
        ],
    )

    print(
        "Peak active vehicles:",
        result["vehicles"][
            "peak_active_vehicles"
        ],
    )

    print(
        "Average estimated speed:",
        result["speed"][
            "average_estimated_speed_kmh"
        ],
    )

    print(
        "Peak estimated speed:",
        result["speed"][
            "peak_estimated_speed_kmh"
        ],
    )

    print(
        "Average traffic score:",
        result["traffic"][
            "average_traffic_score"
        ],
    )

    print(
        "Traffic states:",
        result["traffic"][
            "traffic_states"
        ],
    )

    print(
        "Alerts generated:",
        result["alerts"][
            "total_generated"
        ],
    )

    print(
        "Alert types:",
        result["alerts"][
            "by_type"
        ],
    )

    print(
        "Calibration:",
        result["calibration"][
            "calibration_status"
        ],
    )

    print(
        "Report:",
        result["report"],
    )

    print(
        "\nEND-TO-END VIDEO INTELLIGENCE TEST PASSED"
    )


if __name__ == "__main__":
    main()


