from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO

from app.config import (
    OUTPUTS_DIR,
    VEHICLE_CLASSES,
    YOLO_MODEL_PATH,
)
from app.services.speed_estimator import SpeedEstimator


class VehicleTracker:
    def __init__(
        self,
        model_path: str | Path = YOLO_MODEL_PATH,
        confidence: float = 0.35,
    ):
        self.model_path = Path(model_path)
        self.confidence = confidence

        if not self.model_path.exists():
            raise RuntimeError(
                f"Vehicle model not found: {self.model_path}"
            )

        self.model = YOLO(str(self.model_path))

    @staticmethod
    def center_of_bbox(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> tuple[int, int]:
        return (
            int((x1 + x2) / 2),
            int((y1 + y2) / 2),
        )

    def track_frame(
        self,
        frame: Any,
        frame_index: int = 0,
        fps: float = 30.0,
        speed_estimator: SpeedEstimator | None = None,
    ) -> list[dict[str, Any]]:

        estimator = speed_estimator or SpeedEstimator()

        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=self.confidence,
            classes=list(VEHICLE_CLASSES.keys()),
            verbose=False,
        )

        if not results:
            return []

        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            return []

        boxes = result.boxes

        xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        class_ids = boxes.cls.cpu().numpy().astype(int)

        track_ids = (
            boxes.id.cpu().numpy().astype(int)
            if boxes.id is not None
            else None
        )

        observations: list[dict[str, Any]] = []

        for index in range(len(xyxy)):
            x1, y1, x2, y2 = map(
                int,
                xyxy[index],
            )

            class_id = int(class_ids[index])

            vehicle_type = VEHICLE_CLASSES.get(
                class_id,
                "unknown",
            )

            if vehicle_type == "unknown":
                continue

            confidence = float(confidences[index])

            track_id = (
                int(track_ids[index])
                if track_ids is not None
                else -1
            )

            center = self.center_of_bbox(
                x1,
                y1,
                x2,
                y2,
            )

            speed_result = estimator.calculate_speed(
                track_id=track_id,
                center=center,
                frame_index=frame_index,
                fps=fps,
            )

            observations.append(
                {
                    "track_id": track_id,
                    "vehicle_type": vehicle_type,
                    "confidence": round(confidence, 4),
                    "bbox": [x1, y1, x2, y2],
                    "center": [center[0], center[1]],
                    "speed_kmh": speed_result.get("speed_kmh"),
                    "speed_valid": speed_result.get("valid", False),
                    "speed_reason": speed_result.get("reason"),
                }
            )

        return observations

    def analyze_video(
        self,
        video_path: str | Path,
        output_prefix: str = "roadlink-tracking",
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

        fps = capture.get(
            cv2.CAP_PROP_FPS
        )

        if fps <= 0:
            fps = 30.0

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

        total_frames = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        output_path = (
            OUTPUTS_DIR / f"{output_prefix}.mp4"
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

        estimator = SpeedEstimator()

        unique_vehicle_ids: set[int] = set()
        class_observations: dict[str, int] = {
            vehicle_type: 0
            for vehicle_type in VEHICLE_CLASSES.values()
        }

        speed_samples: list[float] = []
        rejected_speed_measurements = 0
        rejection_reasons: dict[str, int] = {}

        frame_index = 0
        processed_frames = 0

        while True:
            success, frame = capture.read()

            if not success:
                break

            observations = self.track_frame(
                frame=frame,
                frame_index=frame_index,
                fps=fps,
                speed_estimator=estimator,
            )

            for observation in observations:
                track_id = observation["track_id"]

                if track_id >= 0:
                    unique_vehicle_ids.add(
                        track_id
                    )

                vehicle_type = observation[
                    "vehicle_type"
                ]

                if vehicle_type in class_observations:
                    class_observations[
                        vehicle_type
                    ] += 1

                if observation["speed_valid"]:
                    speed_kmh = observation[
                        "speed_kmh"
                    ]

                    if speed_kmh is not None:
                        speed_samples.append(
                            float(speed_kmh)
                        )
                else:
                    reason = observation[
                        "speed_reason"
                    ]

                    if reason not in (
                        "insufficient_history",
                        None,
                    ):
                        rejected_speed_measurements += 1

                        rejection_reasons[
                            reason
                        ] = (
                            rejection_reasons.get(
                                reason,
                                0,
                            )
                            + 1
                        )

                x1, y1, x2, y2 = observation[
                    "bbox"
                ]

                track_id = observation[
                    "track_id"
                ]

                vehicle_type = observation[
                    "vehicle_type"
                ]

                speed = observation[
                    "speed_kmh"
                ]

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

            cv2.putText(
                frame,
                f"RoadLink | Frame {frame_index}",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            writer.write(frame)

            processed_frames += 1
            frame_index += 1

        capture.release()
        writer.release()

        average_speed = (
            sum(speed_samples)
            / len(speed_samples)
            if speed_samples
            else None
        )

        peak_speed = (
            max(speed_samples)
            if speed_samples
            else None
        )

        return {
            "source_video": video_path.name,
            "output_video": str(output_path),
            "fps": round(fps, 3),
            "width": width,
            "height": height,
            "total_frames": total_frames,
            "frames_processed": processed_frames,
            "unique_vehicle_ids": len(
                unique_vehicle_ids
            ),
            "class_observations": class_observations,
            "average_valid_estimated_speed_kmh": (
                round(average_speed, 2)
                if average_speed is not None
                else None
            ),
            "peak_valid_estimated_speed_kmh": (
                round(peak_speed, 2)
                if peak_speed is not None
                else None
            ),
            "valid_speed_samples": len(
                speed_samples
            ),
            "rejected_speed_measurements": (
                rejected_speed_measurements
            ),
            "rejection_reasons": rejection_reasons,
            "calibration": estimator.calibration_info(),
        }


vehicle_tracker = VehicleTracker()
