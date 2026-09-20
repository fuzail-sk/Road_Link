from pathlib import Path
import json
import time
import uuid
from collections import defaultdict, deque

import cv2
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "assets" / "models" / "yolo11n.pt"
VIDEO_PATH = BASE_DIR / "assets" / "videos" / "ParkingVideo.mp4"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


# =========================================================
# SPEED CALIBRATION
# =========================================================
#
# Prototype calibration.
#
# 10 physical meters are currently represented by
# 100 pixels in the image.
#
# IMPORTANT:
# These values must eventually be measured from the
# actual camera/road scene.
#

REFERENCE_DISTANCE_METERS = 10.0
REFERENCE_DISTANCE_PIXELS = 100.0

METERS_PER_PIXEL = (
    REFERENCE_DISTANCE_METERS /
    REFERENCE_DISTANCE_PIXELS
)


# =========================================================
# SPEED ENGINE
# =========================================================

# Number of historical positions used for movement.
POSITION_HISTORY_SIZE = 8

# Minimum number of positions before calculating speed.
MIN_POSITION_SAMPLES = 4

# Maximum accepted estimated speed.
#
# This is a DATA-QUALITY filter, not a legal speed limit.
#
MAX_VALID_SPEED_KMH = 120.0

# Maximum jump between two consecutive observations.
#
# Helps reject tracker ID switches / sudden detection jumps.
MAX_POSITION_JUMP_PIXELS = 80.0

# Number of recent speed values used for smoothing.
SPEED_SMOOTHING_WINDOW = 5


# =========================================================
# TRAFFIC ENGINE
# =========================================================

LOW_MAX_ACTIVE = 3
MODERATE_MAX_ACTIVE = 7
HIGH_MAX_ACTIVE = 12


def classify_traffic(active_vehicles: int) -> str:

    if active_vehicles <= LOW_MAX_ACTIVE:
        return "LOW"

    if active_vehicles <= MODERATE_MAX_ACTIVE:
        return "MODERATE"

    if active_vehicles <= HIGH_MAX_ACTIVE:
        return "HIGH"

    return "CRITICAL"


def pixel_distance(point_a, point_b):

    ax, ay = point_a
    bx, by = point_b

    dx = bx - ax
    dy = by - ay

    return (
        (dx * dx + dy * dy) ** 0.5
    )


def calculate_speed_from_history(history):

    if len(history) < MIN_POSITION_SAMPLES:
        return None, None

    first = history[0]
    last = history[-1]

    elapsed = (
        last["time"] -
        first["time"]
    )

    if elapsed <= 0:
        return None, None

    distance_pixels = pixel_distance(
        first["center"],
        last["center"]
    )

    # Reject a sudden tracker jump.
    if distance_pixels > MAX_POSITION_JUMP_PIXELS * (
        len(history) - 1
    ):
        return None, "position_jump"

    distance_meters = (
        distance_pixels *
        METERS_PER_PIXEL
    )

    meters_per_second = (
        distance_meters /
        elapsed
    )

    kmh = (
        meters_per_second *
        3.6
    )

    if kmh < 0:
        return None, "negative_speed"

    if kmh > MAX_VALID_SPEED_KMH:
        return None, "speed_outlier"

    return round(kmh, 2), None


def run_phase2():

    if not MODEL_PATH.exists():
        raise RuntimeError(
            f"YOLO model not found: {MODEL_PATH}"
        )

    if not VIDEO_PATH.exists():
        raise RuntimeError(
            f"Video not found: {VIDEO_PATH}"
        )

    analysis_id = uuid.uuid4().hex[:10]

    output_video = (
        OUTPUT_DIR /
        f"roadlink-phase2-robust-{analysis_id}.mp4"
    )

    output_report = (
        OUTPUT_DIR /
        f"roadlink-phase2-robust-{analysis_id}.json"
    )

    model = YOLO(str(MODEL_PATH))

    capture = cv2.VideoCapture(
        str(VIDEO_PATH)
    )

    if not capture.isOpened():
        raise RuntimeError(
            "Unable to open ParkingVideo.mp4"
        )

    fps = capture.get(
        cv2.CAP_PROP_FPS
    )

    if not fps or fps <= 0:
        fps = 25.0

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

    fourcc = cv2.VideoWriter_fourcc(
        *"mp4v"
    )

    writer = cv2.VideoWriter(
        str(output_video),
        fourcc,
        fps,
        (width, height)
    )

    if not writer.isOpened():
        capture.release()

        raise RuntimeError(
            "Unable to create Phase 2 output video."
        )

    started = time.time()

    frame_index = 0
    frames_processed = 0

    unique_vehicle_ids = set()

    # ---------------------------------------------------------
    # TRACK HISTORY
    # ---------------------------------------------------------

    position_history = defaultdict(
        lambda: deque(
            maxlen=POSITION_HISTORY_SIZE
        )
    )

    speed_history = defaultdict(
        lambda: deque(
            maxlen=SPEED_SMOOTHING_WINDOW
        )
    )

    latest_speed = {}

    maximum_valid_speed = defaultdict(
        float
    )

    observations = defaultdict(int)

    vehicle_types = {}

    # ---------------------------------------------------------
    # QUALITY STATISTICS
    # ---------------------------------------------------------

    speed_samples = []

    rejected_speed_measurements = defaultdict(
        int
    )

    # ---------------------------------------------------------
    # TRAFFIC TIMELINE
    # ---------------------------------------------------------

    traffic_timeline = []

    traffic_state_frames = defaultdict(
        int
    )

    recent_active_counts = deque(
        maxlen=15
    )

    # ---------------------------------------------------------
    # FRAME PROCESSING
    # ---------------------------------------------------------

    while True:

        success, frame = capture.read()

        if not success:
            break

        frame_index += 1
        frames_processed += 1

        current_time = (
            frame_index / fps
        )

        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.35,
            classes=list(
                VEHICLE_CLASSES.keys()
            ),
            verbose=False,
        )

        result = results[0]

        annotated = frame.copy()

        current_tracks = {}

        if (
            result.boxes is not None
            and len(result.boxes) > 0
        ):

            boxes = result.boxes

            xyxy = (
                boxes.xyxy
                .cpu()
                .numpy()
            )

            confidences = (
                boxes.conf
                .cpu()
                .numpy()
            )

            class_ids = (
                boxes.cls
                .cpu()
                .numpy()
                .astype(int)
            )

            track_ids = None

            if boxes.id is not None:

                track_ids = (
                    boxes.id
                    .cpu()
                    .numpy()
                    .astype(int)
                )

            if track_ids is not None:

                for index in range(
                    len(xyxy)
                ):

                    track_id = int(
                        track_ids[index]
                    )

                    class_id = int(
                        class_ids[index]
                    )

                    vehicle_type = (
                        VEHICLE_CLASSES.get(
                            class_id
                        )
                    )

                    if vehicle_type is None:
                        continue

                    confidence = float(
                        confidences[index]
                    )

                    x1, y1, x2, y2 = map(
                        int,
                        xyxy[index]
                    )

                    center = (
                        int((x1 + x2) / 2),
                        int((y1 + y2) / 2),
                    )

                    unique_vehicle_ids.add(
                        track_id
                    )

                    vehicle_types[
                        track_id
                    ] = vehicle_type

                    observations[
                        track_id
                    ] += 1

                    current_tracks[
                        track_id
                    ] = {
                        "center": center,
                        "type": vehicle_type,
                        "confidence": confidence,
                        "bbox": [
                            x1,
                            y1,
                            x2,
                            y2,
                        ],
                    }

                    # -----------------------------------------
                    # POSITION HISTORY
                    # -----------------------------------------

                    position_history[
                        track_id
                    ].append(
                        {
                            "center": center,
                            "time": current_time,
                        }
                    )

                    # -----------------------------------------
                    # SPEED ESTIMATION
                    # -----------------------------------------

                    speed, rejection_reason = (
                        calculate_speed_from_history(
                            position_history[
                                track_id
                            ]
                        )
                    )

                    if speed is not None:

                        speed_history[
                            track_id
                        ].append(speed)

                        smoothed_speed = (
                            sum(
                                speed_history[
                                    track_id
                                ]
                            )
                            /
                            len(
                                speed_history[
                                    track_id
                                ]
                            )
                        )

                        smoothed_speed = round(
                            smoothed_speed,
                            2
                        )

                        latest_speed[
                            track_id
                        ] = smoothed_speed

                        maximum_valid_speed[
                            track_id
                        ] = max(
                            maximum_valid_speed[
                                track_id
                            ],
                            smoothed_speed
                        )

                        speed_samples.append(
                            smoothed_speed
                        )

                    elif rejection_reason:

                        rejected_speed_measurements[
                            rejection_reason
                        ] += 1

                    # -----------------------------------------
                    # DRAW TRACK
                    # -----------------------------------------

                    current_vehicle_speed = (
                        latest_speed.get(
                            track_id
                        )
                    )

                    if current_vehicle_speed is not None:

                        label = (
                            f"ID {track_id} | "
                            f"{vehicle_type.upper()} | "
                            f"{current_vehicle_speed:.1f} km/h"
                        )

                    else:

                        label = (
                            f"ID {track_id} | "
                            f"{vehicle_type.upper()}"
                        )

                    cv2.rectangle(
                        annotated,
                        (x1, y1),
                        (x2, y2),
                        (255, 255, 255),
                        2,
                    )

                    label_y = max(
                        y1 - 10,
                        22
                    )

                    label_width = max(
                        190,
                        len(label) * 9
                    )

                    cv2.rectangle(
                        annotated,
                        (
                            x1,
                            label_y - 22
                        ),
                        (
                            x1 + label_width,
                            label_y + 2
                        ),
                        (0, 0, 0),
                        -1,
                    )

                    cv2.putText(
                        annotated,
                        label,
                        (
                            x1 + 4,
                            label_y - 5
                        ),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )

        # -----------------------------------------------------
        # TRAFFIC DENSITY
        # -----------------------------------------------------

        active_vehicles = len(
            current_tracks
        )

        recent_active_counts.append(
            active_vehicles
        )

        smoothed_active = (
            sum(
                recent_active_counts
            )
            /
            len(
                recent_active_counts
            )
        )

        traffic_state = classify_traffic(
            round(smoothed_active)
        )

        traffic_state_frames[
            traffic_state
        ] += 1

        traffic_timeline.append(
            {
                "frame": frame_index,
                "time_seconds": round(
                    current_time,
                    3
                ),
                "active_vehicles":
                    active_vehicles,
                "smoothed_active_vehicles":
                    round(
                        smoothed_active,
                        2
                    ),
                "traffic_state":
                    traffic_state,
            }
        )

        # -----------------------------------------------------
        # HEADER
        # -----------------------------------------------------

        cv2.rectangle(
            annotated,
            (0, 0),
            (width, 82),
            (0, 0, 0),
            -1,
        )

        header_1 = (
            "ROADLINK | "
            "TRAFFIC INTELLIGENCE"
        )

        header_2 = (
            f"ACTIVE: {active_vehicles} | "
            f"STATE: {traffic_state} | "
            f"TRACKED: "
            f"{len(unique_vehicle_ids)}"
        )

        cv2.putText(
            annotated,
            header_1,
            (14, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            annotated,
            header_2,
            (14, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        writer.write(
            annotated
        )

    capture.release()
    writer.release()

    processing_seconds = (
        time.time() - started
    )

    # =========================================================
    # AGGREGATE METRICS
    # =========================================================

    average_active = 0.0

    peak_active = 0

    if traffic_timeline:

        average_active = (
            sum(
                item[
                    "active_vehicles"
                ]
                for item in
                traffic_timeline
            )
            /
            len(
                traffic_timeline
            )
        )

        peak_active = max(
            item[
                "active_vehicles"
            ]
            for item in
            traffic_timeline
        )

    average_speed = 0.0

    peak_speed = 0.0

    if speed_samples:

        average_speed = (
            sum(speed_samples)
            /
            len(speed_samples)
        )

        peak_speed = max(
            speed_samples
        )

    # ---------------------------------------------------------
    # VEHICLE SUMMARY
    # ---------------------------------------------------------

    vehicle_summary = []

    for track_id in sorted(
        unique_vehicle_ids
    ):

        vehicle_summary.append(
            {
                "track_id":
                    track_id,

                "vehicle_type":
                    vehicle_types.get(
                        track_id,
                        "unknown"
                    ),

                "observations":
                    observations.get(
                        track_id,
                        0
                    ),

                "latest_valid_speed_kmh":
                    round(
                        latest_speed.get(
                            track_id,
                            0
                        ),
                        2
                    ),

                "maximum_valid_speed_kmh":
                    round(
                        maximum_valid_speed.get(
                            track_id,
                            0
                        ),
                        2
                    ),

                "speed_samples":
                    len(
                        speed_history.get(
                            track_id,
                            []
                        )
                    ),
            }
        )

    # =========================================================
    # REPORT
    # =========================================================

    report = {

        "product":
            "RoadLink",

        "phase":
            "Phase 2.1 - Robust Speed Engine",

        "analysis_id":
            analysis_id,

        "source_video":
            VIDEO_PATH.name,

        "output_video":
            output_video.name,

        "calibration": {

            "enabled":
                True,

            "reference_distance_meters":
                REFERENCE_DISTANCE_METERS,

            "reference_distance_pixels":
                REFERENCE_DISTANCE_PIXELS,

            "meters_per_pixel":
                round(
                    METERS_PER_PIXEL,
                    6
                ),

            "note":
                "Prototype calibration. "
                "Replace with measured camera "
                "scene calibration before using "
                "speed as an accurate real-world "
                "measurement."
        },

        "speed_engine": {

            "position_history_size":
                POSITION_HISTORY_SIZE,

            "minimum_position_samples":
                MIN_POSITION_SAMPLES,

            "smoothing_window":
                SPEED_SMOOTHING_WINDOW,

            "maximum_valid_speed_kmh":
                MAX_VALID_SPEED_KMH,

            "maximum_position_jump_pixels":
                MAX_POSITION_JUMP_PIXELS,
        },

        "video": {

            "fps":
                round(
                    fps,
                    3
                ),

            "width":
                width,

            "height":
                height,

            "total_frames":
                total_frames,

            "frames_processed":
                frames_processed,

            "duration_seconds":
                round(
                    total_frames / fps,
                    3
                ),
        },

        "tracking": {

            "unique_vehicle_ids":
                len(
                    unique_vehicle_ids
                ),

            "average_active_vehicles":
                round(
                    average_active,
                    2
                ),

            "peak_active_vehicles":
                peak_active,
        },

        "speed": {

            "valid_samples":
                len(
                    speed_samples
                ),

            "average_valid_estimated_kmh":
                round(
                    average_speed,
                    2
                ),

            "peak_valid_estimated_kmh":
                round(
                    peak_speed,
                    2
                ),

            "rejected_measurements":
                sum(
                    rejected_speed_measurements.values()
                ),

            "rejection_reasons":
                dict(
                    rejected_speed_measurements
                ),
        },

        "traffic": {

            "state_frames":
                dict(
                    traffic_state_frames
                ),

            "thresholds": {

                "low_max_active":
                    LOW_MAX_ACTIVE,

                "moderate_max_active":
                    MODERATE_MAX_ACTIVE,

                "high_max_active":
                    HIGH_MAX_ACTIVE,

                "above_high":
                    "CRITICAL",
            },
        },

        "vehicles":
            vehicle_summary,

        "timeline":
            traffic_timeline,

        "performance": {

            "processing_seconds":
                round(
                    processing_seconds,
                    3
                ),

            "processing_fps":
                round(
                    frames_processed /
                    processing_seconds
                    if processing_seconds
                    else 0,
                    2
                ),
        },
    }

    output_report.write_text(
        json.dumps(
            report,
            indent=2
        ),
        encoding="utf-8"
    )

    return {

        "analysis_id":
            analysis_id,

        "output_video":
            str(
                output_video
            ),

        "report":
            str(
                output_report
            ),

        "unique_vehicle_ids":
            len(
                unique_vehicle_ids
            ),

        "average_active_vehicles":
            round(
                average_active,
                2
            ),

        "peak_active_vehicles":
            peak_active,

        "average_valid_estimated_speed_kmh":
            round(
                average_speed,
                2
            ),

        "peak_valid_estimated_speed_kmh":
            round(
                peak_speed,
                2
            ),

        "valid_speed_samples":
            len(
                speed_samples
            ),

        "rejected_speed_measurements":
            sum(
                rejected_speed_measurements.values()
            ),

        "rejection_reasons":
            dict(
                rejected_speed_measurements
            ),

        "traffic_states":
            dict(
                traffic_state_frames
            ),

        "processing_seconds":
            round(
                processing_seconds,
                2
            ),
    }


if __name__ == "__main__":

    print()
    print("=" * 64)
    print("ROADLINK - PHASE 2.1")
    print("ROBUST SPEED + TRAFFIC ENGINE")
    print("=" * 64)
    print()

    result = run_phase2()

    print()
    print(
        json.dumps(
            result,
            indent=2
        )
    )

    print()
    print(
        "Phase 2.1 analysis completed."
    )
