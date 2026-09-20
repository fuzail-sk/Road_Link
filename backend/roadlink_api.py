from pathlib import Path
import json
import time
import uuid

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
VIDEO_DIR = ASSETS_DIR / "videos"
MODEL_PATH = ASSETS_DIR / "models" / "yolo11n.pt"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


app = FastAPI(
    title="RoadLink Traffic Intelligence API",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount(
    "/outputs",
    StaticFiles(directory=str(OUTPUT_DIR)),
    name="outputs",
)


@app.get("/")
def root():
    return {
        "product": "RoadLink",
        "service": "Traffic Intelligence API",
        "status": "online",
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai": MODEL_PATH.exists(),
        "model": MODEL_PATH.name,
        "vehicle_classes": list(VEHICLE_CLASSES.values()),
    }


def analyze_video(video_path: Path):
    if not MODEL_PATH.exists():
        raise RuntimeError(f"Vehicle model not found: {MODEL_PATH}")

    if not video_path.exists():
        raise RuntimeError(f"Video not found: {video_path}")

    run_id = uuid.uuid4().hex[:10]

    output_video = OUTPUT_DIR / f"roadlink-analysis-{run_id}.mp4"
    output_json = OUTPUT_DIR / f"roadlink-analysis-{run_id}.json"

    model = YOLO(str(MODEL_PATH))

    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        raise RuntimeError("Unable to open input video.")

    fps = capture.get(cv2.CAP_PROP_FPS)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

    if not fps or fps <= 0:
        fps = 25.0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        str(output_video),
        fourcc,
        fps,
        (width, height),
    )

    if not writer.isOpened():
        capture.release()
        raise RuntimeError("Unable to create output video.")

    started = time.time()

    frame_index = 0
    frames_processed = 0

    all_track_ids = set()
    class_counts = {
        "car": 0,
        "motorcycle": 0,
        "bus": 0,
        "truck": 0,
    }

    track_first_seen = {}
    track_last_seen = {}

    samples = []

    while True:
        success, frame = capture.read()

        if not success:
            break

        frame_index += 1
        frames_processed += 1

        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.35,
            classes=list(VEHICLE_CLASSES.keys()),
            verbose=False,
        )

        result = results[0]

        annotated = frame.copy()

        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes

            xyxy = boxes.xyxy.cpu().numpy()
            confidences = boxes.conf.cpu().numpy()
            class_ids = boxes.cls.cpu().numpy().astype(int)

            track_ids = None

            if boxes.id is not None:
                track_ids = boxes.id.cpu().numpy().astype(int)

            for index in range(len(xyxy)):
                x1, y1, x2, y2 = map(int, xyxy[index])

                confidence = float(confidences[index])
                class_id = int(class_ids[index])

                vehicle_type = VEHICLE_CLASSES.get(
                    class_id,
                    "unknown",
                )

                if vehicle_type == "unknown":
                    continue

                if track_ids is not None:
                    track_id = int(track_ids[index])
                else:
                    track_id = -1

                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)

                timestamp_seconds = frame_index / fps

                if track_id >= 0:
                    all_track_ids.add(track_id)

                    if track_id not in track_first_seen:
                        track_first_seen[track_id] = timestamp_seconds

                    track_last_seen[track_id] = timestamp_seconds

                    class_counts[vehicle_type] += 1

                    if len(samples) < 1000:
                        samples.append(
                            {
                                "track_id": track_id,
                                "vehicle_type": vehicle_type,
                                "confidence": round(confidence, 4),
                                "frame": frame_index,
                                "timestamp_seconds": round(
                                    timestamp_seconds,
                                    3,
                                ),
                                "bbox": [
                                    x1,
                                    y1,
                                    x2,
                                    y2,
                                ],
                                "center": [
                                    center_x,
                                    center_y,
                                ],
                            }
                        )

                label = (
                    f"ID {track_id} | "
                    f"{vehicle_type.upper()} | "
                    f"{confidence:.2f}"
                )

                cv2.rectangle(
                    annotated,
                    (x1, y1),
                    (x2, y2),
                    (255, 255, 255),
                    2,
                )

                label_y = max(y1 - 10, 20)

                cv2.rectangle(
                    annotated,
                    (x1, label_y - 22),
                    (
                        x1 + max(170, len(label) * 9),
                        label_y + 2,
                    ),
                    (0, 0, 0),
                    -1,
                )

                cv2.putText(
                    annotated,
                    label,
                    (x1 + 4, label_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        # RoadLink control-room information bar.
        cv2.rectangle(
            annotated,
            (0, 0),
            (width, 42),
            (0, 0, 0),
            -1,
        )

        status_text = (
            f"ROADLINK | "
            f"FRAME {frame_index}/{total_frames} | "
            f"TRACKED {len(all_track_ids)}"
        )

        cv2.putText(
            annotated,
            status_text,
            (14, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        writer.write(annotated)

    capture.release()
    writer.release()

    elapsed = time.time() - started

    track_durations = []

    for track_id in sorted(all_track_ids):
        first_seen = track_first_seen.get(track_id, 0)
        last_seen = track_last_seen.get(track_id, first_seen)

        track_durations.append(
            {
                "track_id": track_id,
                "first_seen_seconds": round(first_seen, 3),
                "last_seen_seconds": round(last_seen, 3),
                "duration_seconds": round(
                    max(0, last_seen - first_seen),
                    3,
                ),
            }
        )

    report = {
        "product": "RoadLink",
        "analysis_id": run_id,
        "source_video": video_path.name,
        "output_video": output_video.name,
        "video": {
            "fps": round(fps, 3),
            "width": width,
            "height": height,
            "total_frames": total_frames,
            "frames_processed": frames_processed,
            "duration_seconds": round(
                total_frames / fps if fps else 0,
                3,
            ),
        },
        "performance": {
            "processing_seconds": round(elapsed, 3),
            "frames_per_second": round(
                frames_processed / elapsed if elapsed else 0,
                3,
            ),
        },
        "tracking": {
            "unique_vehicle_ids": len(all_track_ids),
            "class_observations": class_counts,
            "track_durations": track_durations,
        },
        "samples": samples,
    }

    output_json.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    return {
        "analysis_id": run_id,
        "source_video": video_path.name,
        "output_video": f"/outputs/{output_video.name}",
        "report": f"/outputs/{output_json.name}",
        "unique_vehicle_ids": len(all_track_ids),
        "frames_processed": frames_processed,
        "processing_seconds": round(elapsed, 3),
        "class_observations": class_counts,
    }


@app.post("/api/video/analyze-sample")
def analyze_sample_video():
    video_path = VIDEO_DIR / "ParkingVideo.mp4"

    try:
        return analyze_video(video_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/api/video/sample")
def sample_video_info():
    video_path = VIDEO_DIR / "ParkingVideo.mp4"

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail="ParkingVideo.mp4 not found.",
        )

    return {
        "name": video_path.name,
        "path": str(video_path),
        "exists": True,
    }
